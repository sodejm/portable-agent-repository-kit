"""Test source documentation without executing the inspected source."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agent/check_code_documentation.py"
SPEC = importlib.util.spec_from_file_location("code_documentation", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DocumentationTests(unittest.TestCase):
    """Pin AST coverage, legacy exceptions and filesystem failure behavior."""

    def setUp(self) -> None:
        """Create a policy-controlled repository without Git metadata."""
        self.temp = tempfile.TemporaryDirectory(prefix="park-source-docs-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".agents").mkdir()
        self.policy = {
            "version": 1, "extensions": [".py"],
            "exclude_dirs": [".git", ".venv", "__pycache__", ".claude/skills"],
            "private_statement_threshold": 10,
        }
        self.write_json(".agents/code-documentation.json", self.policy)
        self.write_json(".agents/code-documentation-baseline.json", {"version": 1, "files": []})

    def write_json(self, path: str, value: object) -> None:
        """Write a synthetic configuration fixture under the isolated root."""
        (self.root / path).write_text(json.dumps(value), encoding="utf-8")

    def source(self, text: str, name: str = "example.py") -> Path:
        """Create a source fixture without importing or executing it."""
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_check(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
        """Run the real command against the synthetic repository."""
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True, capture_output=True, check=False, cwd=self.root, env=env,
        )

    def test_missing_empty_and_placeholder_docstrings(self) -> None:
        """Reject absent or meaningless module and public declaration prose."""
        for doc, rule in (("", "missing-docstring"), ('""""""\n', "missing-docstring"),
                          ('"""TODO"""\n', "placeholder-docstring"),
                          ('"""..."""\n', "placeholder-docstring")):
            with self.subTest(doc=doc):
                self.source(doc + "def public():\n    pass\n")
                result = self.run_check()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f":<module>:{rule}", result.stdout)
                self.assertIn(":public:", result.stdout)

    def test_valid_native_docstrings_and_nonexecution(self) -> None:
        """Accept documented APIs without evaluating decorators or statements."""
        self.source('''"""Document a synthetic interface."""
raise RuntimeError("must never execute")
@unknown_decorator
async def fetch():
    """Return the cached record.

    The caller owns the returned record.
    """
    return None
class Public:
    """Hold a synthetic record."""
    def __init__(self):
        """Initialize an empty record."""
        self.value = None
    def read(self):
        """Return the current record."""
        return self.value
''')
        self.assertEqual(self.run_check().returncode, 0)

    def test_public_async_and_methods_are_checked(self) -> None:
        """Check decorated async APIs and protocol methods by qualified name."""
        self.source('''"""Describe the module."""
@decorator
async def fetch():
    pass
class Public:
    def __init__(self):
        pass
    def read(self):
        pass
''')
        result = self.run_check()
        for symbol in ("fetch", "Public", "Public.__init__", "Public.read"):
            self.assertIn(f":{symbol}:missing-docstring", result.stdout)

    def test_private_statement_threshold_and_nested_boundaries(self) -> None:
        """Count control-flow statements but not a nested function's body."""
        for count, expected in ((9, 0), (10, 1)):
            with self.subTest(count=count):
                body = "    pass\n" * count
                self.source('"""Describe the module."""\ndef _internal():\n' + body)
                self.assertEqual(self.run_check().returncode, expected)
        self.source('''"""Describe the module."""
def outer():
    """Build a local helper."""
    def inner():
        pass
    return inner
def _small():
    def _large():
''' + "        pass\n" * 10 + "    return _large\n")
        result = self.run_check()
        self.assertIn(":_small._large:missing-docstring", result.stdout)
        self.assertNotIn(":_small:missing-docstring", result.stdout)
        self.assertNotIn(":outer.inner:", result.stdout)

    def test_complex_control_flow_and_private_classes(self) -> None:
        """Require complex internals even inside a private class."""
        self.source('''"""Describe the module."""
class _Private:
    def work(self):
        if True:
''' + "            pass\n" * 9)
        self.assertIn(":_Private.work:missing-docstring", self.run_check().stdout)

    def test_summary_separator(self) -> None:
        """Require a blank line between summary and extended prose."""
        self.source('"""Describe the module.\nMore details without a separator.\n"""\n')
        self.assertIn("summary-separator", self.run_check().stdout)

    def test_strings_do_not_create_declarations(self) -> None:
        """Do not recognize fake declarations embedded in ordinary strings."""
        self.source('"""Describe the module."""\nEXAMPLE = "def fake(): pass"\n')
        self.assertEqual(self.run_check().returncode, 0)

    def test_syntax_error_is_not_source_disclosure(self) -> None:
        """Fail on invalid Python without echoing its source or machine path."""
        self.source('SECRET_SENTINEL = "unterminated\n')
        result = self.run_check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("parse-error", result.stderr)
        self.assertNotIn("SECRET_SENTINEL", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_python_encoding_cookie(self) -> None:
        """Honor a valid source encoding instead of assuming UTF-8."""
        path = self.source("")
        path.write_bytes('# coding: latin-1\n"""Document café records."""\n'.encode("latin-1"))
        self.assertEqual(self.run_check().returncode, 0)

    def baseline_source(self) -> None:
        """Record the current inventory as an explicit legacy fixture."""
        result = self.run_check("--inventory-json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_json(".agents/code-documentation-baseline.json", json.loads(result.stdout))

    def test_baseline_only_excuses_identical_contents_and_known_rules(self) -> None:
        """Reject changed legacy files and violations absent from the baseline."""
        self.source("def existing():\n    pass\n")
        self.baseline_source()
        baseline = self.root / ".agents/code-documentation-baseline.json"
        original = baseline.read_bytes()
        self.assertEqual(self.run_check().returncode, 0)
        self.source("def existing():\n    return 1\n")
        self.assertEqual(self.run_check().returncode, 1)
        self.assertEqual(baseline.read_bytes(), original)
        self.source("def existing():\n    pass\n")
        value = json.loads(original)
        value["files"][0]["violations"] = ["<module>:missing-docstring"]
        self.write_json(".agents/code-documentation-baseline.json", value)
        self.assertEqual(self.run_check().returncode, 1)

    def test_new_and_deleted_files(self) -> None:
        """Allow a removed legacy file but reject an untracked new source."""
        path = self.source("def existing():\n    pass\n")
        self.baseline_source()
        path.unlink()
        self.assertEqual(self.run_check().returncode, 0)
        self.source("def new():\n    pass\n", "new.py")
        self.assertEqual(self.run_check().returncode, 1)

    def test_inventory_is_stable_and_nonmutating(self) -> None:
        """Produce deterministic relative-path inventory and leave policy untouched."""
        self.source("pass\n", "z.py")
        self.source("pass\n", "a.py")
        before = (self.root / ".agents/code-documentation-baseline.json").read_bytes()
        first, second = self.run_check("--inventory-json"), self.run_check("--inventory-json")
        self.assertEqual(first.stdout, second.stdout)
        inventory = json.loads(first.stdout)
        self.assertEqual([item["path"] for item in inventory["files"]], ["a.py", "z.py"])
        self.assertEqual(inventory["files"][0]["sha256"], hashlib.sha256(b"pass\n").hexdigest())
        self.assertEqual((self.root / ".agents/code-documentation-baseline.json").read_bytes(), before)

    def test_malformed_and_duplicate_policy(self) -> None:
        """Fail closed on unknown fields, types, duplicate keys and unsafe exclusions."""
        path = self.root / ".agents/code-documentation.json"
        for field, value in (("version", True), ("unknown", 1), ("exclude_dirs", ["../"]),
                             ("exclude_dirs", ["."]), ("extensions", [".rs"]),
                             ("private_statement_threshold", 0)):
            with self.subTest(field=field, value=value):
                self.write_json(".agents/code-documentation.json", {**self.policy, field: value})
                self.assertEqual(self.run_check().returncode, 2)
        path.write_text('{"version":1,"version":1}', encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 2)

    def test_duplicate_and_unsafe_baseline_entries(self) -> None:
        """Reject duplicate paths and path traversal rather than accepting exceptions."""
        self.source("pass\n")
        self.baseline_source()
        value = json.loads((self.root / ".agents/code-documentation-baseline.json").read_text())
        entry = value["files"][0]
        for entries in ([entry, entry], [{**entry, "path": "../outside.py"}],
                        [{**entry, "sha256": "invalid"}], [{**entry, "extra": True}]):
            self.write_json(".agents/code-documentation-baseline.json", {"version": 1, "files": entries})
            self.assertEqual(self.run_check().returncode, 2)

    def test_symlink_sources_and_configuration_are_rejected(self) -> None:
        """Do not follow source, directory or policy symlinks outside the root."""
        with tempfile.TemporaryDirectory(prefix="park-external-docs-") as external:
            outside = Path(external) / "outside.py"
            outside.write_text("PRIVATE_SENTINEL\n")
            for name, target in (("linked.py", outside), ("linked", Path(external))):
                link = self.root / name
                link.symlink_to(target)
                result = self.run_check()
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("PRIVATE_SENTINEL", result.stdout + result.stderr)
                link.unlink()
            config = self.root / ".agents/code-documentation.json"
            config.unlink()
            config.symlink_to(outside)
            self.assertEqual(self.run_check().returncode, 2)

    def test_generated_copies_are_excluded_not_canonical_sources(self) -> None:
        """Skip declared generated adapters while checking their canonical sources."""
        self.source("pass\n", ".claude/skills/sample/worker.py")
        self.assertEqual(self.run_check().returncode, 0)
        self.source("pass\n", ".agents/skills/sample/worker.py")
        self.assertEqual(self.run_check().returncode, 1)

    def test_oversized_and_unreadable_source(self) -> None:
        """Bound reads and sanitize failures without printing the source or OS message."""
        source = self.source('"""Describe the module."""\n')
        with mock.patch.object(Path, "open", side_effect=PermissionError("PRIVATE_SENTINEL")):
            with self.assertRaisesRegex(CHECKER.CheckError, "example.py:unreadable-file"):
                CHECKER._read(self.root, "example.py")
        with source.open("wb") as stream:
            stream.truncate(CHECKER.MAX_BYTES + 1)
        result = self.run_check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid-file-size-or-type", result.stderr)
        self.assertNotIn(str(self.root), result.stderr)

    def test_unicode_docstrings_are_not_placeholders(self) -> None:
        """Accept useful summaries in non-Latin scripts without requiring English."""
        for summary in ("处理用户请求。", "ユーザーの要求を処理する。", "Обработать запрос.", "Επεξεργασία αιτήματος."):
            with self.subTest(summary=summary):
                self.source(f'"""{summary}"""\n')
                result = self.run_check()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_punctuation_wrapped_placeholders_are_rejected(self) -> None:
        """Reject empty markers and decorated TODOs without excluding Unicode prose."""
        for summary in ("-", "--", "`...`", "[TODO]", "`TODO`", "TODO -", "# TODO", "TODO()", "(TBD)"):
            with self.subTest(summary=summary):
                self.source(f'"""{summary}"""\n')
                result = self.run_check()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("placeholder-docstring", result.stdout)

    def test_parser_warnings_do_not_disclose_source_or_change_result(self) -> None:
        """Suppress parser warnings even when the environment promotes them to errors."""
        self.source('"""Describe the module."""\nPAT = "PRIVATE_SENTINEL \\d+"\n')
        for env in (None, {**os.environ, "PYTHONWARNINGS": "error"}):
            result = self.run_check(env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("PRIVATE_SENTINEL", result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")

    def test_registered_directory_alias_checks_only_canonical_source(self) -> None:
        """Allow declared internal aliases without hiding their canonical violations."""
        self.policy["directory_aliases"] = {"aliases/tool": "extensions/tool"}
        self.write_json(".agents/code-documentation.json", self.policy)
        canonical = self.source('"""Describe the module."""\n', "extensions/tool/source.py")
        alias = self.root / "aliases/tool"
        alias.parent.mkdir()
        alias.symlink_to(canonical.parent, target_is_directory=True)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 files", result.stdout)
        canonical.write_text("pass\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("extensions/tool/source.py", result.stdout)
        self.assertNotIn("aliases/tool/source.py", result.stdout)
        alias.unlink()
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.run_check().returncode, 2)

    def test_alias_cannot_point_to_excluded_or_aliased_scope(self) -> None:
        """Reject exclusions and alias chains that could omit canonical checks."""
        for aliases in ({"tool": ".venv/tool"}, {"tool": "other", "other": "tool"},
                        {"tool": "../outside"}):
            self.write_json(".agents/code-documentation.json", {**self.policy, "directory_aliases": aliases})
            self.assertEqual(self.run_check().returncode, 2)

    def test_non_utf8_path_is_a_configuration_error(self) -> None:
        """Reject unencodable paths before they reach JSON or diagnostic output."""
        with self.assertRaises(CHECKER.CheckError):
            CHECKER._relative("bad\udcff.py")


if __name__ == "__main__":
    unittest.main()

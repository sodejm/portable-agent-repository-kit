"""Exercise generation, privacy boundaries and portable contract behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATE = ROOT / "scripts" / "create_project.py"
sys.path.insert(0, str(ROOT / "scripts"))
from _template_common import copy_template, synchronize_claude_skills


class TemplateTests(unittest.TestCase):
    """Validate template output using isolated synthetic repositories."""

    def test_creator_guidance_exposes_interview_and_scripted_options(self) -> None:
        """Keep agent-led setup aligned with the public project creation command."""
        help_text = subprocess.check_output([sys.executable, str(CREATE), "--help"], text=True)
        skills = (".agents/skills/template-project-creator", ".claude/skills/template-project-creator")
        for directory in skills:
            instructions = (ROOT / directory / "SKILL.md").read_text(encoding="utf-8")
            for flag in ("--interactive", "--languages", "--context", "--assurance", "--license"):
                with self.subTest(directory=directory, flag=flag):
                    self.assertIn(flag, help_text)
                    self.assertIn(flag, instructions)

    def test_distribution_excludes_private_configuration_and_audit_reports(self) -> None:
        """Keep private sentinels out of distribution and adapter copies."""
        with tempfile.TemporaryDirectory(prefix="park-privacy-") as temp:
            source, destination = Path(temp) / "source", Path(temp) / "copy"
            skill = source / ".agents/skills/example-audit"
            (skill / "config").mkdir(parents=True)
            public = skill / "config/churn.example.json"
            public.write_text('{"repositories": []}\n', encoding="utf-8")
            private_paths = [
                source / "churn-v1-example.json", source / "settings.local.json",
                skill / "config/churn.local.json", skill / "churn-v1-example.md",
            ]
            for path in private_paths:
                path.write_text("synthetic private sentinel\n", encoding="utf-8")
            synchronize_claude_skills(source)
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "add", "-f", "."], cwd=source, check=True)
            copy_template(source, destination)
            self.assertTrue((destination / public.relative_to(source)).is_file())
            for root in (source / ".claude/skills/example-audit", destination / ".claude/skills/example-audit"):
                self.assertTrue((root / "config/churn.example.json").is_file())
                self.assertFalse((root / "config/churn.local.json").exists())
                self.assertFalse((root / "churn-v1-example.md").exists())
            for path in private_paths:
                self.assertFalse((destination / path.relative_to(source)).exists())
                self.assertEqual(path.read_text(encoding="utf-8"), "synthetic private sentinel\n")

    def test_distribution_uses_git_inventory(self) -> None:
        """Distribute tracked content without collecting developer files."""
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "src", Path(temp) / "dst"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            (source / "public.txt").write_text("distributed")
            (source / "credentials.txt").write_text("private fixture")
            subprocess.run(["git", "add", "public.txt"], cwd=source, check=True)
            copy_template(source, output)
            self.assertEqual([p.name for p in output.iterdir()], ["public.txt"])

    def test_distribution_requires_source_inventory(self) -> None:
        """Reject a directory without an inventory before collecting any files."""
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "src", Path(temp) / "dst"
            source.mkdir()
            (source / ".env").write_text("private fixture")
            with self.assertRaisesRegex(RuntimeError, "Git checkout"):
                copy_template(source, output)
            self.assertFalse(output.exists())

    def test_distribution_rejects_tracked_symlink(self) -> None:
        """Reject a tracked path redirected to a private file."""
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "src", Path(temp) / "dst"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            outside = Path(temp) / "private.txt"
            outside.write_text("private fixture")
            (source / "public.txt").symlink_to(outside)
            subprocess.run(["git", "add", "public.txt"], cwd=source, check=True)
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                copy_template(source, output)
            self.assertFalse((output / "public.txt").exists())

    def create(self, destination: Path, license_choice: str = "mit") -> subprocess.CompletedProcess[str]:
        """Generate a synthetic project outside the source tree and return CLI output."""
        create_script = CREATE
        try:
            destination.resolve().relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            # This repository intentionally refuses to generate a project inside its
            # own source tree. Some restricted runners place TMPDIR inside the checkout,
            # so exercise the same invariant from an isolated template copy.
            isolated_source = destination.parent / "template-source"
            shutil.copytree(
                ROOT,
                isolated_source,
                ignore=shutil.ignore_patterns(
                    ".git",
                    destination.parent.name,
                    "__pycache__",
                    "*.pyc",
                ),
            )
            tracked = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=ROOT)
            subprocess.run(["git", "init", "-q", str(isolated_source)], check=True)
            subprocess.run(["git", "update-index", "--add", "-z", "--stdin"], cwd=isolated_source,
                           input=tracked, check=True)
            create_script = isolated_source / "scripts" / "create_project.py"
        return subprocess.run(
            [
                sys.executable,
                str(create_script),
                str(destination),
                "--name",
                "Example Service",
                "--description",
                "A generated repository used to test PARK.",
                "--github-owner",
                "example-owner",
                "--license",
                license_choice,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_make_init_configures_template_once(self) -> None:
        """Exercise the README interview and its read-only second invocation."""
        with tempfile.TemporaryDirectory(prefix="park-init-") as temp:
            root = Path(temp) / "project"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", Path(temp).name,
            ))
            answers = "Example Project\nA sample for PARK.\npython,go\ncli,api\n\nmit\n"
            result = subprocess.run(["make", "init"], cwd=root, input=answers,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Run `make assurance` after committing", result.stdout)
            profile = root / ".park/profile.json"
            self.assertEqual(json.loads(profile.read_bytes()), {
                "version": 1, "languages": ["python", "go"],
                "contexts": ["cli", "api"], "assurance": "medium",
            })
            self.assertIn("Authorize each operation", (root / ".specify/memory/constitution.md").read_text())
            self.assertTrue((root / ".specify/templates/spec-template.md").is_file())
            self.assertTrue((root / ".squad/team.md").is_file())
            self.assertIn("# Example Project", (root / "README.md").read_text())
            self.assertIn("A sample for PARK.", (root / "README.md").read_text())
            self.assertIn("MIT License", (root / "LICENSE").read_text())
            self.assertFalse((root / ".portable-agent-template").exists())
            profile_bytes = profile.read_bytes()
            repeat = subprocess.run(["make", "init"], cwd=root, input="", text=True, capture_output=True)
            self.assertEqual(repeat.returncode, 0, repeat.stderr)
            self.assertIn("Project initialized", repeat.stdout)
            self.assertIn("make assurance to scan the current commit", repeat.stdout)
            self.assertEqual(profile.read_bytes(), profile_bytes)

    def test_make_init_requires_complete_answers(self) -> None:
        """Reject an interrupted interview or invalid answers without writing files."""
        with tempfile.TemporaryDirectory(prefix="park-init-") as temp:
            root = Path(temp) / "project"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", Path(temp).name,
            ))
            for answers, message in (
                ("Example\n", "interview ended before setup was complete"),
                ("Example\nTest project\npython\nmobile\n", "unknown context"),
                ("Example\nTest project\n\n\n\ninvalid\n", "unknown license choice"),
            ):
                with self.subTest(message=message):
                    result = subprocess.run(["make", "init"], cwd=root, input=answers,
                                            text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stderr)
                    self.assertNotIn("after committing", result.stdout)
                    self.assertTrue((root / ".portable-agent-template").is_file())
                    self.assertFalse((root / ".park").exists())
                    for path in ("README.md", "LICENSE"):
                        self.assertEqual((root / path).read_bytes(), (ROOT / path).read_bytes())

    def test_create_project_and_validate_generated_repository(self) -> None:
        """Check generated policy, skill resources and the full consumer gate."""
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "example-service"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((destination / ".portable-agent-template").exists())
            self.assertFalse((destination / "docs/superpowers").exists())
            self.assertTrue((destination / "extensions/goblin-council/install.py").is_file())
            self.assertTrue((destination / "extensions/goblin-council/.codex/config.toml").is_file())
            self.assertFalse((destination / ".agents/skills/goblin").exists())
            self.assertFalse((destination / ".claude/skills/goblin").exists())
            model = (destination / "docs/THREAT_MODEL.md").read_text(encoding="utf-8")
            self.assertIn("# Example Service threat model", model)
            self.assertIn("Architecture inventory pending", model)
            self.assertNotIn("scripts/_template_common.py", model)
            self.assertNotIn("bfc41923fb497b495e95dc7dee644313b51b368b", model)
            coverage = (destination / "docs/security/REVIEW_COVERAGE.md").read_text(encoding="utf-8")
            self.assertIn("# Example Service existing-code human review coverage", coverage)
            self.assertIn("No human review", coverage)
            self.assertNotIn("bfc41923fb497b495e95dc7dee644313b51b368b", coverage)
            review_policy = json.loads(
                (destination / ".github/review-policy.json").read_text(encoding="utf-8")
            )
            self.assertEqual(review_policy["repository"], "example-owner/example-service")
            self.assertIsNone(review_policy["owner_review"])
            self.assertIsNone(review_policy["required_reviewer"])
            self.assertNotIn(
                "sodejm",
                json.dumps(review_policy),
                "generated projects must not inherit PARK's owner exception",
            )
            generated_review_docs = (
                destination / "docs/OWNER_REVIEW_POLICY.md"
            ).read_text(encoding="utf-8")
            self.assertIn("no configured owner exception", generated_review_docs)
            self.assertNotIn("sodejm", generated_review_docs)
            self.assertTrue((destination / "LICENSE").is_file())
            self.assertIn("# Example Service", (destination / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((destination / ".claude/skills/.park-generated").is_file())
            for parent in (".agents/skills", ".claude/skills"):
                for resource in (
                    "SKILL.md", "references/source-documentation.md", "references/provenance.md"
                ):
                    self.assertTrue((destination / parent / "clear-writing" / resource).is_file())
            self.assertTrue((destination / "docs/CODE_DOCUMENTATION.md").is_file())
            self.assertTrue(
                (destination / ".agents/skills/agent-workboard/scripts/workboard.py").is_file()
            )
            self.assertTrue(
                (destination / ".claude/skills/agent-workboard/scripts/workboard.py").is_file()
            )
            git_init = subprocess.run(
                ["git", "init", "--quiet"],
                cwd=destination,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(git_init.returncode, 0, git_init.stderr)
            workboard = destination / ".agents/skills/agent-workboard/scripts/workboard.py"
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(workboard),
                    "--cwd",
                    str(destination),
                    "--json",
                    "init",
                ],
                cwd=destination,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(json.loads(initialized.stdout)["storage_kind"], "git")
            self.assertTrue((destination / ".git/codex/workboard.sqlite3").is_file())
            self.assertFalse((destination / ".agents/skills/template-project-creator").exists())
            self.assertFalse((destination / ".claude/skills/template-project-creator").exists())
            check = subprocess.run(
                [sys.executable, "scripts/agent/check.py"],
                cwd=destination,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_nonempty_destination_is_never_overwritten(self) -> None:
        """Reject an occupied destination without changing its sentinel."""
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "existing"
            destination.mkdir()
            sentinel = destination / "important.txt"
            sentinel.write_text("preserve me\n", encoding="utf-8")
            result = self.create(destination)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")
            self.assertIn("refusing to overwrite", result.stderr)

    def test_none_is_an_explicit_license_choice(self) -> None:
        """Allow a consumer to choose no license instead of silently choosing one."""
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "unlicensed-project"
            result = self.create(destination, "none")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((destination / "LICENSE").exists())

    def test_generated_repository_rejects_broken_markdown_links(self) -> None:
        """Reject missing local documentation targets in generated projects."""
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "broken-docs-project"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            readme = destination / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n[Missing guide](docs/MISSING.md)\n",
                encoding="utf-8",
            )
            check = subprocess.run(
                [sys.executable, "scripts/agent/validate_contract.py"],
                cwd=destination,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(check.returncode, 1)
            self.assertIn("Markdown target does not exist", check.stderr)

    def test_contract_requires_portable_clear_writing(self) -> None:
        """Reject a missing skill even when no Markdown link refers to it."""
        with tempfile.TemporaryDirectory(prefix="park-docs-contract-") as temp:
            destination = Path(temp) / "example-service"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = destination / ".agents/skills/clear-writing/SKILL.md"
            # The gate must require the skill independently of prose links.
            if skill.exists():
                skill.unlink()
            check = subprocess.run(
                [sys.executable, "scripts/agent/validate_contract.py"],
                cwd=destination, text=True, capture_output=True, check=False,
            )
            self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
            self.assertIn("missing required path: .agents/skills/clear-writing/SKILL.md", check.stderr)

    def test_generated_documentation_gate_without_git_and_with_new_code(self) -> None:
        """Check consumer code before Git init, after init and before its first commit."""
        with tempfile.TemporaryDirectory(prefix="park-generated-docs-") as temp:
            destination = Path(temp) / "example-service"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)

            def check() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "scripts/agent/check_code_documentation.py"],
                    cwd=destination, text=True, capture_output=True, check=False,
                )

            self.assertFalse((destination / ".git").exists())
            result = check()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            subprocess.run(["git", "init", "--quiet"], cwd=destination, check=True)
            self.assertEqual(check().returncode, 0)
            code = destination / "consumer.py"
            code.write_text("def process():\n    pass\n", encoding="utf-8")
            result = check()
            self.assertEqual(result.returncode, 1)
            self.assertIn("consumer.py:1:<module>:missing-docstring", result.stdout)
            code.write_text(
                '"""Provide a synthetic consumer API."""\n'
                'def process():\n    """Return no value for this synthetic example."""\n    return None\n',
                encoding="utf-8",
            )
            self.assertEqual(check().returncode, 0)

    def test_generated_gate_accepts_registered_goblin_installation(self) -> None:
        """Preserve supported project-local skill links while checking canonical code."""
        with tempfile.TemporaryDirectory(prefix="park-goblin-docs-") as temp:
            destination = Path(temp) / "example-service"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = subprocess.run(
                [sys.executable, "extensions/goblin-council/install.py", "--skills-dir", ".agents/skills"],
                cwd=destination, text=True, capture_output=True, check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            result = subprocess.run(
                [sys.executable, "scripts/agent/check_code_documentation.py"],
                cwd=destination, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

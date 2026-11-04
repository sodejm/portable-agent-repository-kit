#!/usr/bin/env python3
"""Check Python documentation structure without importing inspected source.

Run from any directory with --root to select a repository. The default root is
the checkout containing this script. Normal checks are read-only; --inventory-json
prints candidate legacy exceptions for explicit review, never writes them.
Exit 0 means the configured Python scope passes, 1 means documentation violations,
and 2 means unsafe or invalid input prevented a complete check.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath


POLICY = ".agents/code-documentation.json"
BASELINE = ".agents/code-documentation-baseline.json"
MAX_BYTES = 8 * 1024 * 1024
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
PLACEHOLDERS = {"", "todo", "tbd", "fixme", "pass", "documentation", "docstring"}
RULES = {"missing-docstring", "placeholder-docstring", "summary-separator"}


class CheckError(ValueError):
    """Signal a sanitized diagnostic suitable for a public validation log."""


def _relative(value: object) -> str:
    """Validate a canonical relative path without interpreting shell syntax."""
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise CheckError("invalid-relative-path")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value or value == "."
            or ".." in path.parts or "\\" in value or ":" in value):
        raise CheckError("invalid-relative-path")
    return value


def _read(root: Path, relative: str) -> bytes:
    """Read a bounded regular file, rejecting symlinks in every path component.

    This protects ordinary static checkout inspection, not concurrent mutation by
    another local actor. Repository checks assume a trusted, stable workspace.
    """
    current = root
    try:
        for part in PurePosixPath(_relative(relative)).parts:
            current = current / part
            if current.is_symlink():
                raise CheckError(f"{relative}:symlink-not-allowed")
        info = current.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise CheckError(f"{relative}:invalid-file-size-or-type")
        with current.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise CheckError(f"{relative}:file-too-large")
        return data
    except OSError as error:
        raise CheckError(f"{relative}:unreadable-file") from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON keys instead of accepting a hidden override."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckError("duplicate-json-key")
        result[key] = value
    return result


def _json(root: Path, relative: str) -> dict:
    """Load a JSON object while suppressing source and raw exception details."""
    try:
        value = json.loads(_read(root, relative), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise CheckError(f"{relative}:invalid-json") from error
    if not isinstance(value, dict):
        raise CheckError(f"{relative}:expected-object")
    return value


def load_policy(root: Path) -> dict:
    """Validate the versioned Python scope; unsupported parser claims fail closed."""
    policy = _json(root, POLICY)
    if set(policy) != {"version", "extensions", "exclude_dirs", "private_statement_threshold"}:
        raise CheckError(f"{POLICY}:invalid-fields")
    if type(policy["version"]) is not int or policy["version"] != 1:
        raise CheckError(f"{POLICY}:unsupported-version")
    if policy["extensions"] != [".py"]:
        raise CheckError(f"{POLICY}:unsupported-language-scope")
    threshold = policy["private_statement_threshold"]
    if type(threshold) is not int or not 1 <= threshold <= 100:
        raise CheckError(f"{POLICY}:invalid-statement-threshold")
    excludes = policy["exclude_dirs"]
    if not isinstance(excludes, list):
        raise CheckError(f"{POLICY}:invalid-exclusions")
    validated = [_relative(item) for item in excludes]
    if len(set(validated)) != len(validated):
        raise CheckError(f"{POLICY}:duplicate-exclusions")
    return policy


def load_baseline(root: Path) -> dict[str, dict]:
    """Read exact-content exceptions; reject ambiguous or malformed records."""
    value = _json(root, BASELINE)
    if (set(value) != {"version", "files"} or type(value["version"]) is not int
            or value["version"] != 1 or not isinstance(value["files"], list)):
        raise CheckError(f"{BASELINE}:invalid-schema")
    result = {}
    for entry in value["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "violations"}:
            raise CheckError(f"{BASELINE}:invalid-entry")
        path = _relative(entry["path"])
        if path in result or not path.endswith(".py"):
            raise CheckError(f"{BASELINE}:duplicate-or-invalid-path")
        digest = entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CheckError(f"{BASELINE}:invalid-digest")
        violations = entry["violations"]
        if not isinstance(violations, list) or not violations:
            raise CheckError(f"{BASELINE}:invalid-violations")
        for rule in violations:
            if (not isinstance(rule, str) or ":" not in rule
                    or not rule.rsplit(":", 1)[0] or rule.rsplit(":", 1)[1] not in RULES):
                raise CheckError(f"{BASELINE}:invalid-rule")
        if len(set(violations)) != len(violations):
            raise CheckError(f"{BASELINE}:duplicate-rule")
        result[path] = entry
    return result


def _excluded(parts: tuple[str, ...], exclusions: list[str]) -> bool:
    """Match directory names anywhere, or multi-part prefixes at the root."""
    for value in exclusions:
        prefix = PurePosixPath(value).parts
        if len(prefix) == 1 and prefix[0] in parts:
            return True
        if parts[:len(prefix)] == prefix:
            return True
    return False


def python_paths(root: Path, exclusions: list[str]) -> list[str]:
    """Discover untracked as well as tracked Python files without following links."""
    result = []

    def failed_walk(error: OSError) -> None:
        raise CheckError("source-discovery:unreadable-directory") from error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=failed_walk):
        parent = Path(directory).relative_to(root)
        kept = []
        for name in sorted(dirs):
            path = parent / name
            if _excluded(path.parts, exclusions):
                continue
            if (root / path).is_symlink():
                raise CheckError(f"{path.as_posix()}:symlink-not-allowed")
            kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            if name.endswith(".py"):
                result.append(_relative((parent / name).as_posix()))
    return sorted(result)


def _statement_count(node: ast.AST) -> int:
    """Count executable statements, excluding nested declaration bodies and prose."""
    count = 0
    pending = list(node.body)
    while pending:
        child = pending.pop()
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
            continue
        if isinstance(child, ast.stmt):
            count += 1
        if not isinstance(child, DEFINITIONS):
            pending.extend(ast.iter_child_nodes(child))
    return count


def _public_name(name: str) -> bool:
    """Treat protocol dunders as public while preserving private-name conventions."""
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _doc_rule(node: ast.AST) -> str | None:
    """Return one structural defect, not a prose-quality or semantic judgment."""
    doc = ast.get_docstring(node, clean=True)
    if doc is None or not doc.strip():
        return "missing-docstring"
    summary = doc.splitlines()[0].strip()
    words = re.sub(r"[^a-z]+", " ", summary.lower()).strip()
    if words in PLACEHOLDERS:
        return "placeholder-docstring"
    lines = doc.splitlines()
    if len(lines) > 1 and lines[1].strip():
        return "summary-separator"
    return None


def inspect_source(data: bytes, path: str, threshold: int) -> list[tuple[int, str, str]]:
    """Return line, qualified symbol and rule for required Python documentation.

    Public means a public-named module declaration or member of public classes;
    it does not infer dynamic exports. Nested definitions and private declarations
    are checked at the configured statement threshold. Source is parsed, never run.
    """
    try:
        tree = ast.parse(data, filename=path)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise CheckError(f"{path}:parse-error") from error
    violations = []

    def inspect(node: ast.AST, names: tuple[str, ...], public_scope: bool) -> None:
        """Traverse lexical scopes without mistaking nested functions for public APIs."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, DEFINITIONS):
                qualified = names + (child.name,)
                public = public_scope and _public_name(child.name)
                if public or _statement_count(child) >= threshold:
                    rule = _doc_rule(child)
                    if rule:
                        violations.append((child.lineno, ".".join(qualified), rule))
                inspect(child, qualified, public and isinstance(child, ast.ClassDef))
            else:
                inspect(child, names, public_scope)

    rule = _doc_rule(tree)
    if rule:
        violations.append((1, "<module>", rule))
    try:
        inspect(tree, (), True)
    except RecursionError as error:
        raise CheckError(f"{path}:source-too-deep") from error
    return sorted(violations)


def collect(root: Path, policy: dict) -> list[dict]:
    """Collect exact source digests and structural diagnostics in stable path order."""
    records = []
    for path in python_paths(root, policy["exclude_dirs"]):
        data = _read(root, path)
        records.append({
            "path": path, "sha256": hashlib.sha256(data).hexdigest(),
            "diagnostics": inspect_source(data, path, policy["private_statement_threshold"]),
        })
    return records


def main(argv: list[str] | None = None) -> int:
    """Check a repository or print an explicit, nonmutating baseline inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--inventory-json", action="store_true", help="print all current violations, ignoring legacy exceptions")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise CheckError("invalid-repository-root")
        policy = load_policy(root)
        baseline = {} if args.inventory_json else load_baseline(root)
        records = collect(root, policy)
        if args.inventory_json:
            entries = [{
                "path": item["path"], "sha256": item["sha256"],
                "violations": sorted({f"{symbol}:{rule}" for _, symbol, rule in item["diagnostics"]}),
            } for item in records if item["diagnostics"]]
            print(json.dumps({"version": 1, "files": entries}, indent=2, sort_keys=True))
            return 0
        failures, legacy = 0, 0
        for item in records:
            entry = baseline.get(item["path"], {})
            unchanged = entry.get("sha256") == item["sha256"]
            for line, symbol, rule in item["diagnostics"]:
                if unchanged and f"{symbol}:{rule}" in entry.get("violations", []):
                    legacy += 1
                    continue
                print(f"{item['path']}:{line}:{symbol}:{rule}")
                failures += 1
        print(f"Python AST documentation: {len(records)} files; {failures} violations; {legacy} unchanged legacy exceptions.")
        print("Coverage: Python structure only; prose accuracy, skill use and other languages require separate evidence.")
        return 1 if failures else 0
    except CheckError as error:
        print(f"code-documentation: {error}", file=sys.stderr)
    except (OSError, RuntimeError):
        print("code-documentation: inaccessible-root-or-input", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

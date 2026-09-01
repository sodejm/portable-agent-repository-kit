#!/usr/bin/env python3
"""Run PARK's complete dependency-free validation suite."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(command: list[str]) -> bool:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode == 0


def validate_python() -> bool:
    ok = True
    for path in sorted(ROOT.rglob("*.py")):
        if ".git" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            print(f"error: {error}", file=sys.stderr)
            ok = False
    if ok:
        print("Python sources parse successfully.")
    return ok


def main() -> int:
    checks = [
        validate_python(),
        run([sys.executable, "scripts/agent/validate_contract.py"]),
        run([sys.executable, "scripts/agent/sync_adapters.py", "--check"]),
    ]
    if (ROOT / "tests").is_dir():
        checks.append(run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
    if (ROOT / ".git").exists():
        checks.append(run(["git", "diff", "--check"]))
    if all(checks):
        print("All PARK checks passed.")
        return 0
    print("One or more PARK checks failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

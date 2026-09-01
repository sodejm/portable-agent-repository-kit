#!/usr/bin/env python3
"""Report whether the local environment can validate and use PARK."""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print(f"PARK root: {ROOT}")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    required_missing = []
    for command, required in (("git", True), ("make", False), ("gh", False)):
        location = shutil.which(command)
        status = location or ("MISSING (required)" if required else "not installed (optional)")
        print(f"{command}: {status}")
        if required and not location:
            required_missing.append(command)
    print("Template marker: " + ("present" if (ROOT / ".portable-agent-template").is_file() else "configured project"))
    if required_missing:
        print("Missing required commands: " + ", ".join(required_missing), file=sys.stderr)
        return 1
    print("Environment is ready for PARK's dependency-free checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

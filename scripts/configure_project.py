#!/usr/bin/env python3
"""Configure a repository created with GitHub's PARK template button."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_profile import add_arguments, collect
from _template_common import TemplateError, configure_project, display_path


def parser() -> argparse.ArgumentParser:
    """Define shared profile options for an existing clone."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--path", type=Path, default=Path.cwd())
    add_arguments(result)
    return result


def main() -> int:
    """Configure a fresh, marked project once."""
    args = parser().parse_args()
    root = args.path.expanduser()
    try:
        settings = collect(args)
        configure_project(root, **settings)
    except (TemplateError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Configured {settings['name']} at {display_path(root)}")
    print("Next: review the generated files, run `make check`, and commit the result.")
    print("Run `make assurance` after committing to scan the generated project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

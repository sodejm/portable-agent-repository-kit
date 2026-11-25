#!/usr/bin/env python3
"""Create a configured project from PARK at an arbitrary local path."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from project_profile import add_arguments, collect

from _template_common import (
    ensure_empty_destination,
    TemplateError,
    configure_project,
    copy_template,
    display_path,
    initialize_git,
    template_root,
)


def parser() -> argparse.ArgumentParser:
    """Define interactive and scripted project creation options."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("destination", type=Path)
    add_arguments(result)
    result.add_argument("--init-git", action="store_true")
    return result


def main() -> int:
    """Publish the project only after generation and optional Git initialization succeed."""
    args = parser().parse_args()
    destination = args.destination.expanduser().absolute()
    try:
        settings = collect(args)
        source = template_root()
        if destination.is_symlink() or destination.resolve().is_relative_to(source):
            raise TemplateError("choose a destination outside the template without a symlink")
        ensure_empty_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
            project = Path(staging) / "project"
            copy_template(source, project)
            configure_project(project, **settings)
            if args.init_git:
                initialize_git(project, args.default_branch)
            ensure_empty_destination(destination)
            project.rename(destination)
    except (TemplateError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Created {settings['name']} at {display_path(destination)}")
    print("Run `make check` and review the generated project constitution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

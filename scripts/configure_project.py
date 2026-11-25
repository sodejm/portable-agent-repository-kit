#!/usr/bin/env python3
"""Configure a repository created with GitHub's PARK template button."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _template_common import LICENSE_CHOICES, TemplateError, configure_project, display_path


def parser() -> argparse.ArgumentParser:
    """Build the interface shared by unattended setup and the make init prompts."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--path", type=Path, default=Path.cwd())
    result.add_argument("--interactive", action="store_true", help="prompt for missing project details")
    result.add_argument("--name")
    result.add_argument("--description")
    result.add_argument("--slug")
    result.add_argument("--github-owner")
    result.add_argument("--license", choices=LICENSE_CHOICES)
    result.add_argument("--copyright-holder")
    result.add_argument("--default-branch")
    return result


def main() -> int:
    """Collect project details before handing any writes to the guarded configurator."""
    cli = parser()
    args = cli.parse_args()
    if args.interactive:
        try:
            for key, prompt in (
                ("name", "Project name"),
                ("description", "Description"),
                ("github_owner", "GitHub owner (optional)"),
                ("slug", "Repository slug (Enter to derive it from the project name)"),
                ("default_branch", "Default branch [main]"),
                ("license", "License (" + ", ".join(LICENSE_CHOICES) + ")"),
            ):
                if getattr(args, key) is None:
                    setattr(args, key, input(prompt + ": ").strip() or None)
        except (EOFError, KeyboardInterrupt):
            cli.exit(2, "\nSetup cancelled before writing project files.\n")
    for key in ("name", "description", "license"):
        if getattr(args, key) is None:
            cli.error(f"--{key} is required")
    root = args.path.expanduser()
    try:
        configure_project(
            root,
            name=args.name,
            description=args.description,
            slug=args.slug,
            github_owner=args.github_owner,
            license_choice=args.license,
            copyright_holder=args.copyright_holder,
            default_branch=args.default_branch if args.default_branch is not None else "main",
        )
    except TemplateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Configured {args.name} at {display_path(root)}")
    print("Next: review the generated files, run `make check`, and commit the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

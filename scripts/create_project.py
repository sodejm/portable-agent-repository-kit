#!/usr/bin/env python3
"""Create a configured project from PARK at an arbitrary local path."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _template_common import (
    LICENSE_CHOICES,
    TemplateError,
    configure_project,
    copy_template,
    display_path,
    initialize_git,
    template_root,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("destination", type=Path)
    result.add_argument("--name", required=True)
    result.add_argument("--description", required=True)
    result.add_argument("--slug")
    result.add_argument("--github-owner")
    result.add_argument("--license", required=True, choices=LICENSE_CHOICES)
    result.add_argument("--copyright-holder")
    result.add_argument("--default-branch", default="main")
    result.add_argument("--init-git", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    destination = args.destination.expanduser()
    try:
        copy_template(template_root(), destination)
        configure_project(
            destination,
            name=args.name,
            description=args.description,
            slug=args.slug,
            github_owner=args.github_owner,
            license_choice=args.license,
            copyright_holder=args.copyright_holder,
            default_branch=args.default_branch,
        )
        if args.init_git:
            initialize_git(destination, args.default_branch)
    except TemplateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Created {args.name} at {display_path(destination)}")
    print("Next: review the generated files, run `make check`, and commit the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

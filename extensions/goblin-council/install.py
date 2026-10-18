#!/usr/bin/env python3
"""Register optional Codex skills without replacing existing configuration."""
import argparse
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent
NAMES = ("goblin", "goblin-max")


def install(destination, *, uninstall=False, dry_run=False):
    destination = Path(destination).expanduser().absolute()
    actions = []
    for name in NAMES:
        source = PACKAGE / ".agents" / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Incomplete package: {name}")
        target = destination / name
        owned = target.is_symlink() and target.resolve() == source.resolve()
        exists = target.exists() or target.is_symlink()
        if exists and not owned:
            raise ValueError(f"Refusing to replace or remove existing entry: {target}")
        if uninstall and owned:
            actions.append(("remove", target, source))
        elif not uninstall and not exists:
            actions.append(("link", target, source))
    for action, target, source in actions:
        print(f"{('Would ' if dry_run else '')}{action}: {target}")
    if dry_run:
        return
    created = []
    try:
        for action, target, source in actions:
            if action == "remove":
                # Recheck ownership immediately before removal.
                if not target.is_symlink() or target.resolve() != source.resolve():
                    raise ValueError(f"Entry changed during uninstall: {target}")
                target.unlink()
            else:
                destination.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source, target_is_directory=True)
                created.append((target, source))
    except (OSError, ValueError):
        for target, source in reversed(created):
            if target.is_symlink() and target.resolve() == source.resolve():
                target.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 11) or sys.platform == "win32":
        parser.error("Goblin Council requires Python 3.11+ on macOS or Linux")
    try:
        install(args.skills_dir, uninstall=args.uninstall, dry_run=args.dry_run)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Goblin Council: {error}\n")


if __name__ == "__main__":
    main()

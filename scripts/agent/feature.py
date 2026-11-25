#!/usr/bin/env python3
"""Start a feature using the project's installed Spec Kit templates."""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path


def main():
    """Create all three documents together and preserve existing feature work."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", nargs="?", default=os.environ.get("NAME"))
    slug = parser.parse_args().slug
    if not slug or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        parser.error("choose a lowercase feature name such as refund-transfer")
    root = Path(__file__).resolve().parents[2]
    specs = root / "specs"
    if specs.is_symlink() or (specs / slug).exists() or (specs / slug).is_symlink():
        parser.error("feature path already exists or is redirected")
    specs.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=specs) as temp:
            draft = Path(temp) / "feature"
            draft.mkdir()
            for kind in ("spec", "plan", "tasks"):
                shutil.copyfile(root / ".specify/templates" / f"{kind}-template.md", draft / f"{kind}.md")
            draft.rename(specs / slug)
    except OSError as error:
        print(f"Feature creation failed: {error}", file=sys.stderr)
        return 1
    print(f"Record the requested behavior and acceptance cases in specs/{slug}/spec.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATE = ROOT / "scripts" / "create_project.py"


class TemplateTests(unittest.TestCase):
    def create(self, destination: Path, license_choice: str = "mit") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(CREATE),
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

    def test_create_project_and_validate_generated_repository(self) -> None:
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "example-service"
            result = self.create(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((destination / ".portable-agent-template").exists())
            self.assertTrue((destination / "LICENSE").is_file())
            self.assertIn("# Example Service", (destination / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((destination / ".claude/skills/.park-generated").is_file())
            check = subprocess.run(
                [sys.executable, "scripts/agent/check.py"],
                cwd=destination,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_nonempty_destination_is_never_overwritten(self) -> None:
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
        with tempfile.TemporaryDirectory(prefix="park-test-") as temp:
            destination = Path(temp) / "unlicensed-project"
            result = self.create(destination, "none")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((destination / "LICENSE").exists())


if __name__ == "__main__":
    unittest.main()

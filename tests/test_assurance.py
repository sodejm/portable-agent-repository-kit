"""Exercise the generated repository through its setup and feature commands."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AssuranceTests(unittest.TestCase):
    """Validate the public setup path with new and existing inputs."""

    def test_interview_builds_financial_project(self):
        """Seed the local integrations and select only requested project guidance."""
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "ledger"
            result = subprocess.run(
                [sys.executable, ROOT / "scripts/create_project.py", project, "--interactive"],
                input="Ledger\nTransfer funds\nGo\nweb,financial\n\nnone\n",
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((project / ".park/profile.json").read_text())
            self.assertEqual(profile["assurance"], "critical")
            self.assertEqual(profile["languages"], ["go"])
            constitution = (project / ".specify/memory/constitution.md").read_text()
            self.assertIn("idempotency", constitution)
            self.assertIn("tenant", constitution)
            self.assertIn("go test", constitution)
            self.assertNotIn("pytest", constitution)
            self.assertTrue((project / ".squad/team.md").exists())
            subprocess.run(["make", "init"], cwd=project, check=True, capture_output=True)
            command = [sys.executable, "scripts/agent/feature.py", "refund"]
            subprocess.run(command, cwd=project, check=True)
            spec = project / "specs/refund/spec.md"
            self.assertIn("User Scenarios", spec.read_text())
            spec.write_text("accepted behavior")
            self.assertNotEqual(subprocess.run(command, cwd=project, capture_output=True).returncode, 0)
            self.assertEqual(spec.read_text(), "accepted behavior")

    def test_invalid_profile_preserves_destination(self):
        """Invalid input cannot partially initialize a destination."""
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "invalid"
            result = subprocess.run(
                [sys.executable, ROOT / "scripts/create_project.py", project, "--name", "Invalid",
                 "--description", "Synthetic test", "--license", "none", "--context", "financal"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("context", result.stderr)
            self.assertFalse(project.exists())

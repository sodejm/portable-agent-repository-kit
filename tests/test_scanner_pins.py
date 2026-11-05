"""Keep reviewed scanner pins and contributor installation guidance synchronized."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScannerPinTests(unittest.TestCase):
    """Validate the reviewed release pair offline, without querying a mutable feed."""

    def test_reviewed_scanner_releases_match_installation_guide(self) -> None:
        """Require both approved versions and their upstream release references."""
        policy = json.loads((ROOT / "tools/push_gate/policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["tools"], {"semgrep": "1.183.0", "trivy": "0.76.1"})
        guide = (ROOT / "docs/LOCAL_PUSH_GATE.md").read_text(encoding="utf-8")
        for name, version in policy["tools"].items():
            with self.subTest(scanner=name):
                self.assertIn(f"**{version}**", guide)
                self.assertIn(f"/releases/tag/v{version}", guide)

    def test_validation_dependencies_match_reviewed_releases_and_guide(self) -> None:
        """Keep the optional toolchain and its Python prerequisite documented."""
        requirements = (ROOT / "tools/push_gate/requirements.txt").read_text(encoding="utf-8")
        pins = dict(line.split("==") for line in requirements.splitlines() if line)
        self.assertEqual(pins, {
            "ruff": "0.17.3", "coverage": "7.17.2",
            "build": "1.6.1", "pip-audit": "2.10.1",
        })
        guide = (ROOT / "docs/LOCAL_PUSH_GATE.md").read_text(encoding="utf-8")
        for version in pins.values():
            self.assertIn(version, guide)
        self.assertIn("Python >=3.11", guide)

    def test_workflow_actions_use_reviewed_release_commits(self) -> None:
        """Require immutable action references for both validation and review."""
        checkout = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
        setup = "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0"
        for name in ("repository-contract.yml", "owner-review-gate.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn(checkout, workflow)
            if name == "repository-contract.yml":
                self.assertIn(setup, workflow)


if __name__ == "__main__":
    unittest.main()

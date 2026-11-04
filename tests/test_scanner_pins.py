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


if __name__ == "__main__":
    unittest.main()

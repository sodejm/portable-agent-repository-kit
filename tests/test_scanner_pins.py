"""Check scanner release selection, tool policy and installation guidance."""

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SPEC = importlib.util.spec_from_file_location("scanner_release", ROOT / "tools/push_gate/scanner_release.py")
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


def wheel(platform):
    """Build release metadata for a synthetic wheel."""
    name = f"semgrep-9.8.7-py3-none-{platform}.whl"
    return dict(packagetype="bdist_wheel", yanked=False, filename=name,
                url=f"https://files.pythonhosted.org/packages/{name}", digests={"sha256": "a" * 64})


class ScannerPinTests(unittest.TestCase):
    """Exercise stable release selection against synthetic upstream responses."""

    def test_reviewed_scanner_releases_match_installation_guide(self):
        """Use latest for each scanner and document the shared selector."""
        policy = json.loads((ROOT / "tools/push_gate/policy.json").read_text())
        self.assertEqual(policy["tools"], dict.fromkeys(("gitleaks", "semgrep", "trivy"), "latest"))
        self.assertIn("latest", (ROOT / "docs/LOCAL_PUSH_GATE.md").read_text())

    def test_release_archive_identity(self):
        """Require the correct release asset, provider URL and digest."""
        for tool, (repo, pattern) in RELEASE.GITHUB.items():
            name = pattern.format("9.8.7")
            url = f"https://github.com/{repo}/releases/download/v9.8.7/{name}"
            item = dict(name=name, browser_download_url=url, digest="sha256:" + "a" * 64)
            data = dict(tag_name="v9.8.7", draft=False, prerelease=False, assets=[item])
            self.assertEqual(RELEASE.artifact(tool, data, "linux-x86_64"),
                             {"version": "9.8.7", "url": url, "sha256": "a" * 64})
            with self.assertRaises(ValueError):
                RELEASE.artifact(tool, data, "macos-arm64")
            for delta in (dict(draft=True), dict(prerelease=True), dict(assets=[]),
                          dict(assets=[item, item]), dict(assets=[dict(item, digest=None)]),
                          dict(assets=[dict(item, browser_download_url="https://example.invalid")])):
                with self.subTest(tool=tool, delta=delta), self.assertRaises(ValueError):
                    RELEASE.artifact(tool, {**data, **delta}, "linux-x86_64")

    def test_invalid_wheel_identity(self):
        """Reject withdrawn, redirected, unsupported or digestless distributions."""
        item = wheel("manylinux_2_34_x86_64")
        for delta in (dict(yanked=True), dict(url="https://example.invalid"),
                      dict(digests={"sha256": ""}), dict(filename="other.whl")):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                RELEASE.artifact("semgrep", {"info": {"version": "9.8.7"}, "urls": [dict(item, **delta)]}, "linux-x86_64")
        with self.assertRaises(ValueError):
            RELEASE.release_version("semgrep", {"info": {"version": "9.8.7rc1"}})

    def test_validation_dependencies_match_reviewed_releases_and_guide(self) -> None:
        """Keep the optional toolchain and its Python prerequisite documented."""
        requirements = (ROOT / "tools/push_gate/requirements.txt").read_text(encoding="utf-8")
        pins = dict(line.split("==") for line in requirements.splitlines() if "==" in line)
        self.assertEqual(pins, {
            "ruff": "0.17.6", "coverage": "7.17.5",
            "build": "1.6.1",
        })
        guide = (ROOT / "docs/LOCAL_PUSH_GATE.md").read_text(encoding="utf-8")
        self.assertIn("pip-audit>=2.10.1", requirements.splitlines())
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

    def test_codeql_extended_workflow_covers_actions_and_python(self) -> None:
        """Keep the scheduled security scan scoped and pinned to reviewed actions."""
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
        codeql = "github/codeql-action/"
        release = "@1bd86f2fdb4b86187fa4059f16f31a3202acc9ea # v4.39.4"
        self.assertIn("name: CodeQL extended", workflow)
        self.assertIn("cron: \"23 4 * * 1\"", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertIn("language: [actions, python]", workflow)
        self.assertIn("queries: security-extended", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("security-events: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(f"{codeql}init{release}", workflow)
        self.assertIn(f"{codeql}analyze{release}", workflow)


if __name__ == "__main__":
    unittest.main()

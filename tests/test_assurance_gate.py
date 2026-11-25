"""Exercise assurance orchestration on real commits with controlled scanner outcomes."""

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import assurance


class AssuranceGateTests(unittest.TestCase):
    """Check tier selection, evidence publication and release prerequisites."""
    def setUp(self):
        """Create a temporary repository with a critical-capable review policy."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        for directory in (".park", ".github", "tools/push_gate"):
            (self.root / directory).mkdir(parents=True)
        (self.root / "tools/push_gate/policy.json").write_text('{"tools":{"gitleaks":"9.8.7"}}')
        (self.root / ".github/review-policy.json").write_text('{"require_independent_review": true}')
        self.output = Path(self.temp.name) / "output"

    def git(self, *args):
        """Run Git against the isolated fixture with a disposable identity."""
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                       cwd=self.root, check=True, capture_output=True)

    def commit_level(self, level):
        """Commit the requested assurance profile."""
        (self.root / ".park/profile.json").write_text(json.dumps({"version": 1, "assurance": level}))
        self.git("add", ".")
        self.git("commit", "-qm", level)

    def test_cumulative_checks(self):
        """Exercise each tier against the same baseline and check inventory output."""
        original = assurance.gate.run
        commands = []

        def scanner(argv, cwd, **kwargs):
            if argv[0] == "git":
                return original(argv, cwd, **kwargs)
            commands.append(argv[:2])
            if argv == ["gitleaks", "version"]:
                return b"9.8.7"
            if argv[0] == "trivy":
                Path(argv[argv.index("--output") + 1]).write_text('{"bomFormat": "CycloneDX"}')
            return b""

        with mock.patch.object(assurance.gate, "run", side_effect=scanner), mock.patch.object(assurance.gate, "scanners") as baseline:
            for index, level in enumerate(assurance.LEVELS):
                with self.subTest(level=level):
                    commands.clear()
                    self.commit_level(level)
                    assurance.scan(self.root, self.output)
                    self.assertEqual(commands[:3], [["gitleaks", "version"], ["gitleaks", "git"], ["gitleaks", "dir"]])
                    self.assertEqual(baseline.call_count, index + 1)
                    self.assertEqual(["trivy", "fs"] in commands, level != "low")
                    self.assertEqual((self.output / "sbom.cdx.json").exists(), level != "low")

    def test_failed_evidence(self):
        """Reject failed scans, dated recovery records and weakened review policy."""
        self.commit_level("critical")
        original = assurance.gate.run

        def fail_secret_scan(argv, cwd, **kwargs):
            if argv == ["gitleaks", "version"]:
                return b"9.8.7"
            if argv[0] == "gitleaks":
                raise assurance.gate.GateError("synthetic secret finding")
            return original(argv, cwd, **kwargs)

        with mock.patch.object(assurance.gate, "run", side_effect=fail_secret_scan):
            with self.assertRaises(assurance.gate.GateError):
                assurance.scan(self.root, self.output)
        self.assertFalse(self.output.exists())
        today = dt.date(2026, 1, 1)
        record = dict(date=today.isoformat(), environment="test", procedure="restore", evidence="run-17", reviewer="reviewer", result="passed")
        path = self.root / ".park/recovery.json"
        path.write_text(json.dumps(record))
        assurance.check_recovery(self.root, today)
        for age in (-1, 91):
            with self.assertRaises(ValueError):
                assurance.check_recovery(self.root, today + dt.timedelta(days=age))
        (self.root / ".github/review-policy.json").write_text("{}")
        with self.assertRaises(ValueError):
            assurance.tier(self.root)

    def test_ci_uses_policy_scanner_version(self):
        """Exercise wheel selection without fetching archives or installing tools."""
        shell_setup = self.root / "test-shell"
        shell_setup.write_text("""curl() { :; }
sha256sum() { cat >/dev/null; test -z "$FAIL_HASH"; }
tar() { echo extracted >> "$GITHUB_WORKSPACE/calls"; }
python3() {
    echo "$4 $5" >> "$GITHUB_WORKSPACE/calls"
    echo '{"url":"https://example.invalid/archive","sha256":"fixture","version":"9.8.7"}'
}
""")
        env = {**os.environ, "BASH_ENV": str(shell_setup), "RUNNER_TEMP": self.temp.name,
               "GITHUB_WORKSPACE": str(self.root), "GITHUB_PATH": str(self.root / "runner-path"), "FAIL_HASH": ""}
        command = ["bash", str(ROOT / "scripts/ci/install_assurance_tools.sh")]
        calls = self.root / "calls"
        subprocess.run(command, env=env, check=True, capture_output=True)
        lines = calls.read_text().splitlines()
        self.assertEqual(lines[:4], ["gitleaks artifact", "extracted", "trivy artifact", "extracted"])
        self.assertTrue(lines[4].startswith("latest "))
        calls.unlink()
        result = subprocess.run(command, env={**env, "FAIL_HASH": "1"}, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.read_text().splitlines(), ["gitleaks artifact"])

    def test_critical_owner_needs_separate_reviewer(self):
        """Apply exact-head approval rules to the owner as well as contributors."""
        import test_review_gate as fixture
        gate = fixture.review_gate
        policy = gate.Policy("sodejm/portable-agent-repository-kit", gate.Identity("sodejm", "User"),
                             gate.Reviewer("sodejm", "User", "write", True), independent=True)
        owner = gate.Pull(7, fixture.HEAD, "sodejm", "open")
        with self.assertRaisesRegex(gate.GateError, "same account"):
            gate.evaluate_pull(fixture.FakeGitHub(author="sodejm"), policy, owner)
        pull = gate.Pull(7, fixture.HEAD, "contributor", "open")
        self.assertFalse(gate.evaluate_pull(fixture.FakeGitHub(), policy, pull).allowed)
        approved = fixture.FakeGitHub(reviews=[fixture.review(1, "APPROVED")])
        self.assertTrue(gate.evaluate_pull(approved, policy, pull).allowed)

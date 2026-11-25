"""Regression tests for exact-commit push policy and failure propagation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "local_push_gate", ROOT / "tools/push_gate/gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class PolicyTests(unittest.TestCase):
    """Exercise closed policy and meaningful assertion detection."""

    def test_assertions_must_change(self):
        """Require changed assertions rather than comments or deleted tests."""
        self.assertFalse(
            GATE.executable_test(
                "test_a.py", "assert x == 1", "# comment\nassert x == 1"
            )
        )
        self.assertFalse(GATE.executable_test("test_a.py", "assert x == 1", ""))
        self.assertTrue(
            GATE.executable_test("test_a.py", "assert x == 1", "assert x == 2")
        )
        self.assertTrue(GATE.executable_test("a.test.ts", "", "expect(result).toBe(2)"))

    def test_latest_requires_current_native_engine(self):
        """Block scanning with a stale binary when upstream publishes a new release."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(
                    GATE,
                    "run",
                    side_effect=[b"semgrep-core version: 1.0.0 (a5341ae595)", b"2.0.0"],
                ) as run,
                patch.object(GATE, "scanner_run") as scan,
                self.assertRaisesRegex(GATE.GateError, "2.0.0"),
            ):
                GATE.scanners(root, [], {"tools": {"semgrep": "latest"}}, {}, root)
            self.assertEqual(run.call_args.args[0][-2:], ["semgrep", "version"])
            scan.assert_not_called()

    def test_unsupported_and_default_updates_fail(self):
        """Reject default-branch updates, tags and deletions before execution."""
        sha = "a" * 40
        for target, revision in (
            ("refs/heads/main", sha),
            ("refs/tags/v1", sha),
            ("refs/heads/topic", "0" * 40),
        ):
            with self.subTest(target=target, revision=revision):
                with self.assertRaises(GATE.GateError):
                    GATE.parse_updates(
                        f"refs/heads/topic {revision} {target} {'0' * 40}", "main"
                    )
        self.assertEqual(
            GATE.parse_updates(f"HEAD {sha} refs/heads/topic {'0' * 40}", "main")[0][1],
            sha,
        )

    def test_absent_executable_fails_closed(self):
        """A missing prerequisite must raise the gate's controlled failure."""
        with self.assertRaises(GATE.GateError):
            GATE.run(["push-gate-deliberately-absent-2fcb63a7"], ROOT)

    def test_terraform_assertions_must_change(self):
        """Distinguish executable Terraform assertions from comment-only edits."""
        self.assertFalse(
            GATE.executable_test(
                "main.tftest.hcl", "condition = true", "# note\ncondition = true"
            )
        )
        self.assertTrue(
            GATE.executable_test(
                "main.tftest.hcl", "condition = true", "condition = output.ok == true"
            )
        )

    def test_inherited_overrides_removed(self):
        """Caller scanner settings must not weaken the trusted policy."""
        os.environ["TRIVY_SKIP_FILES"] = "*"
        os.environ["SEMGREP_RULES"] = "unreviewed"
        try:
            self.assertNotIn("TRIVY_SKIP_FILES", GATE.clean_environment())
            self.assertNotIn("SEMGREP_RULES", GATE.clean_environment())
        finally:
            del os.environ["TRIVY_SKIP_FILES"]
            del os.environ["SEMGREP_RULES"]


class NativeScannerTests(unittest.TestCase):
    """Protect native dispatch, reserved ignores and complete report handling."""

    def test_native_entrypoints_must_share_the_engine(self):
        """Reject missing names and a separate launcher despite matching versions."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            core = root / "semgrep-core"
            scanner = root / "osemgrep"
            core.write_text("native fixture")
            core.chmod(0o755)
            env = {"PATH": str(root)}
            with self.assertRaises(GATE.GateError):
                GATE.native_scanner(env)
            os.link(core, scanner)
            self.assertEqual(GATE.native_scanner(env), str(scanner))
            scanner.unlink()
            shutil.copyfile(core, scanner)
            scanner.chmod(0o755)
            with self.assertRaises(GATE.GateError):
                GATE.native_scanner(env)

    def test_reserved_ignore_rejected_at_every_depth(self):
        """Reject committed ignore names and case aliases before launching tools."""
        for name in (
            ".park-semgrep-ignore",
            "sub/.park-semgrep-ignore",
            "a/b/.park-semgrep-ignore/hidden.py",
            ".PARK-SEMGREP-IGNORE",
            "sub/.Park-Semgrep-Ignore",
            "a/b/.pArK-sEmGrEp-IgNoRe/hidden.py",
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("*\n")
                with (
                    patch.object(GATE, "run") as run,
                    patch.object(GATE, "scanner_run") as scan,
                ):
                    with self.assertRaisesRegex(
                        GATE.GateError, "Reserved Semgrep ignore"
                    ):
                        GATE.scanners(root, [name], {"tools": {}}, {}, root)
                    run.assert_not_called()
                    scan.assert_not_called()

    def test_raw_native_version_requires_exact_output(self):
        """Version prose or another version must fail before any scan."""
        policy = {"tools": {"semgrep": "1.186.0", "trivy": "0.76.2"}}
        for output in (b"1.186.0 extra", b"1.186.00", b"wrapper 1.186.0", b"1.185.0"):
            with (
                self.subTest(output=output),
                tempfile.TemporaryDirectory() as temporary,
            ):
                with patch.object(GATE, "run", return_value=output) as run:
                    with self.assertRaises(GATE.GateError):
                        GATE.scanners(Path(temporary), [], policy, {}, Path(temporary))
                    self.assertEqual(
                        run.call_args.args[0], ["semgrep-core", "-version"]
                    )

    def test_stdout_reports_fail_closed_and_stay_private(self):
        """Missing, malformed and structurally incomplete JSON cannot pass."""
        for payload in (
            b"",
            b"private-token",
            b"[]",
            b"{}",
            b'{"results": []}',
            b'{"results": [], "errors": null}',
        ):
            with (
                self.subTest(payload=payload),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                result = subprocess.CompletedProcess([], 0, payload, b"private-token")
                with patch.object(GATE.subprocess, "run", return_value=result):
                    with self.assertRaises(GATE.GateError) as failure:
                        GATE.scanner_run(
                            ["osemgrep"], root, {}, root / "report.json", "results"
                        )
                    self.assertNotIn("private-token", str(failure.exception))

    def test_inline_trivy_suppression_still_blocks(self):
        """Native migration cannot permit repository inline suppressions."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample.tf").write_text("# trivy:ignore:AVD-SYNTHETIC\n")
            with patch.object(
                GATE,
                "run",
                side_effect=[b"semgrep-core version: 1.186.0 (e7f7148977)", b"0.76.2"],
            ):
                with self.assertRaisesRegex(GATE.GateError, "Inline Trivy suppression"):
                    GATE.scanners(
                        root,
                        ["sample.tf"],
                        {"tools": {"semgrep": "1.186.0", "trivy": "0.76.2"}},
                        {},
                        root,
                    )

    def test_findings_and_analysis_errors_block_even_on_zero_exit(self):
        """A scanner exit code cannot override findings in either report format."""
        reports = [
            {"results": [{"check_id": "test-rule", "path": "input.py"}], "errors": []},
            {"results": [], "errors": [{"path": "input.py"}]},
            {
                "Results": [
                    {
                        "Target": "input.tf",
                        "ExperimentalModifiedFindings": [
                            {"Severity": "HIGH", "ID": "suppressed-test-rule"}
                        ],
                    }
                ]
            },
        ]
        policy = {"tools": {"semgrep": "1.186.0", "trivy": "0.76.2"}}
        for report in reports:
            with (
                self.subTest(report=report),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)

                def scan(argv, snapshot, env, path, key, candidate=report):
                    """Return the candidate finding after an empty preceding scan."""
                    if key == "results" and "Results" in candidate:
                        return {"results": [], "errors": []}
                    return candidate

                with (
                    patch.object(
                        GATE,
                        "run",
                        side_effect=[
                            b"semgrep-core version: 1.186.0 (e7f7148977)",
                            b"0.76.2",
                        ],
                    ),
                    patch.object(GATE, "native_scanner", return_value="osemgrep"),
                    patch.object(GATE, "scanner_run", side_effect=scan),
                ):
                    with self.assertRaises(GATE.GateError):
                        GATE.scanners(root, [], policy, {}, root)

    def test_trivy_missing_and_malformed_reports_block(self):
        """Trivy must write a structurally valid report even after a zero exit."""
        for report in (
            None,
            [],
            {},
            {"Results": None},
            {"Results": [None]},
            {"Results": [{"Secrets": [{"Severity": None}]}]},
        ):
            with (
                self.subTest(report=report),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                path = root / "trivy.json"
                if report is not None:
                    path.write_text(json.dumps(report))
                result = subprocess.CompletedProcess(
                    [], 0, b"private-token", b"private-token"
                )
                with patch.object(GATE.subprocess, "run", return_value=result):
                    with self.assertRaises(GATE.GateError) as failure:
                        GATE.scanner_run(["trivy"], root, {}, path, "Results")
                    self.assertNotIn("private-token", str(failure.exception))

    def test_stdout_report_persisted_and_diagnostics_escaped(self):
        """Save native JSON without printing source text or terminal controls."""
        report = {
            "results": [
                {
                    "check_id": "rule\nspoof",
                    "path": "input\x1b.py",
                    "extra": {"lines": "private-token"},
                }
            ],
            "errors": [],
        }
        payload = json.dumps(report).encode()
        result = subprocess.CompletedProcess([], 0, payload, b"private-token")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "semgrep.json"
            with (
                patch.object(GATE.subprocess, "run", return_value=result),
                patch("sys.stderr") as stderr,
            ):
                self.assertEqual(
                    GATE.scanner_run(["osemgrep"], root, {}, path, "results"), report
                )
            self.assertEqual(path.read_bytes(), payload)
            output = "".join(call.args[0] for call in stderr.write.call_args_list)
            self.assertNotIn("private-token", output)
            self.assertIn(r"rule\nspoof", output)
            self.assertIn(r"input\u001b.py", output)


def handoff_record(code, stage):
    """Describe an ordinary callable and its two observable outcomes."""
    paths = [code, "tests/test_behavior.py"]
    return {
        "stage": stage,
        "request": "Clamp a negative count to zero while preserving positive counts.",
        "scope": "Expose clamp_count in the count module and exercise its public input.",
        "setup": "Use Python 3 and the standard library unittest runner.",
        "constraints": "Return integers and accept zero as a valid count.",
        "steps": [
            {
                "action": "Define clamp_count(value) and add positive and negative input tests.",
                "paths": paths,
                "verify": {
                    "command": "python3 -m unittest discover -s tests -p test_behavior.py",
                    "expected": "Both tests pass for positive and negative inputs.",
                },
            }
        ],
        "acceptance": [
            {
                "kind": kind,
                "entrypoint": "clamp_count(value)",
                "given": given,
                "when": "Call clamp_count with the given integer.",
                "then": expected,
                "paths": paths,
                "runner": "unittest",
                "test": "tests/test_behavior.py::Counts::test_" + kind,
            }
            for kind, given, expected in [
                ("success", "A count of 4", "Return 4"),
                ("boundary", "A count of -1", "Return 0"),
            ]
        ],
        "pending": [],
    }


def write_handoff(root, record):
    """Write the feature's versioned plan in the fixture repository."""
    path = root / "docs/session-plans/clamp-count.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def write_count(root, code, boundary="self.assertEqual(clamp(-1), 0)"):
    """Install the public function and separate executable acceptance cases."""
    source = root / code
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "def clamp_count(value):\n    return max(0, value)\n", encoding="utf-8"
    )
    suite = root / "tests/test_behavior.py"
    suite.parent.mkdir(exist_ok=True)
    suite.write_text(
        "import runpy\nimport unittest\n"
        f"clamp = runpy.run_path({code!r})['clamp_count']\n"
        "class Counts(unittest.TestCase):\n"
        "    def test_success(self):\n        self.assertEqual(clamp(4), 4)\n"
        f"    def test_boundary(self):\n        {boundary}\n",
        encoding="utf-8",
    )


def exercise_handoff_success(root, git, code):
    """Commit a plan for future files and push it, then implement and push the feature."""
    before = git("rev-parse", "HEAD").stdout
    write_handoff(root, {"stage": "plan"})
    git("add", "docs")
    write_handoff(root, handoff_record(code, "plan"))
    result = git("commit", "-m", "Incomplete staged plan", success=False)
    assert result.returncode and b"request needs concrete text" in result.stderr, (
        result.stderr
    )
    assert git("rev-parse", "HEAD").stdout == before
    incomplete = handoff_record(code, "plan")
    incomplete["steps"][0]["verify"] = {"command": "python3 -m unittest"}
    write_handoff(root, incomplete)
    git("add", "docs")
    result = git("commit", "-m", "Omit the expected result", success=False)
    assert result.returncode and b"step.verify.expected" in result.stderr
    assert git("rev-parse", "HEAD").stdout == before
    write_handoff(root, handoff_record(code, "plan"))
    git("add", "docs")
    git("commit", "-m", "Plan count behavior")
    git("push", "origin", "feature/gate")
    write_count(root, code)
    git("add", code, "tests/test_behavior.py")
    result = git("commit", "-m", "Implementation without mapping", success=False)
    assert (
        result.returncode
        and b"missing implementation acceptance coverage" in result.stderr
    )
    write_handoff(root, handoff_record(code, "implementation"))
    git("add", "docs")
    git("commit", "-m", "Implement count behavior")
    git("push", "origin", "feature/gate")
    assert (
        git("rev-parse", "HEAD").stdout.strip()
        in git("ls-remote", "origin", "feature/gate").stdout
    )


def exercise_handoff_rejections(root, git, code):
    """Keep the remote branch absent for skipped, failing, and missing acceptance."""
    record = handoff_record(code, "implementation")
    write_handoff(root, record)
    for body, expected in [
        ("pass", b"empty acceptance test"),
        ("self.skipTest('unavailable')", b"required test did not pass"),
        ("self.assertEqual(clamp(-1), 7)", b"required test did not pass"),
    ]:
        write_count(root, code, body)
        git("add", "docs", code, "tests/test_behavior.py")
        git("commit", "-m", "Record a boundary case")
        result = git("push", "origin", "feature/gate", success=False)
        assert result.returncode and expected in result.stderr + result.stdout, (
            result.stderr
        )
        assert not git("ls-remote", "origin", "feature/gate").stdout
    write_count(root, code)
    (root / code).write_text(
        "def clamp_count(value):\n    return value\n", encoding="utf-8"
    )
    git("add", code, "tests/test_behavior.py")
    git("commit", "-m", "Remove the clamp while retaining its tests")
    result = git("push", "origin", "feature/gate", success=False)
    assert (
        result.returncode
        and b"required test did not pass" in result.stdout + result.stderr
    )
    assert not git("ls-remote", "origin", "feature/gate").stdout
    # Restore the implementation so the next failure isolates the missing selector.
    write_count(root, code)
    git("add", code)
    record["acceptance"][1]["test"] = "tests/test_missing.py::Counts::test_boundary"
    write_handoff(root, record)
    git("add", "docs")
    git("commit", "-m", "Point to missing selector")
    result = git("push", "origin", "feature/gate", success=False)
    assert (
        result.returncode
        and b"missing acceptance test" in result.stderr + result.stdout
    ), result.stderr
    assert not git("ls-remote", "origin", "feature/gate").stdout


class RemoteTests(unittest.TestCase):
    """Disposable remotes prove nonzero gates prevent remote updates.

    Scanner doubles exercise orchestration; real scanners require separate runs.
    """

    def setUp(self):
        """Install fixture policy and scanner doubles in a disposable local repo."""
        self.directory = tempfile.TemporaryDirectory(prefix="push-gate-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(
            os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1"
        )
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.command(
            "git", "init", "--quiet", "--bare", str(self.remote), cwd=self.root
        )
        self.command(
            "git", "init", "--quiet", "-b", "main", str(self.repo), cwd=self.root
        )
        self.command("git", "config", "user.name", "Synthetic Gate Test")
        self.command("git", "config", "user.email", "gate@example.test")
        self.command("git", "config", "commit.gpgsign", "false")
        self.command("git", "remote", "add", "origin", str(self.remote))
        shutil.copytree(ROOT / "tools/push_gate", self.repo / "tools/push_gate")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_local_push_gate.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            " def test_ok(self):\n  self.assertTrue(True)\n"
        )
        (self.repo / "implementation.py").write_text("VALUE = 1\n")
        (self.repo / ".gitattributes").write_text("committed-only.py export-ignore\n")
        (self.repo / "committed-only.py").write_text("VALUE = 1\n")
        policy = {
            "default_branch": "main",
            "tools": {"semgrep": "1.181.0", "trivy": "0.76.0"},
            "test_areas": [
                {
                    "name": "application",
                    "implementation": [r"^implementation\.py$"],
                    "tests": [r"^tests/.*\.py$"],
                }
            ],
            "checks": [
                [
                    "{python}",
                    "-c",
                    "import implementation; assert implementation.VALUE == 1",
                ]
            ],
        }
        if self._testMethodName.startswith("test_handoff"):
            policy["session_handoffs"] = True
            policy["checks"] = [
                [
                    "{python}",
                    "tools/push_gate/session_delivery.py",
                    "push",
                    "{base}",
                    "{sha}",
                ]
            ]
        (self.repo / "tools/push_gate/policy.json").write_text(json.dumps(policy))
        self.commit("fixture baseline")
        self.command("git", "push", "--quiet", "origin", "main")
        self.command("git", "checkout", "--quiet", "-b", "feature/gate")
        scanner = """#!/usr/bin/env python3
import json,pathlib,sys
name=pathlib.Path(sys.argv[0]).name
if '-version' in sys.argv or '--version' in sys.argv:
 print('semgrep-core version: 1.181.0 (0123456789)' if name=='semgrep-core' else 'Version: 0.76.0');sys.exit(0)
assert not pathlib.Path('private-untracked.txt').exists()
assert pathlib.Path('committed-only.py').exists()
if name=='osemgrep':
 print(json.dumps({'results': [], 'errors': []}))
 name='semgrep'
else:
 report=pathlib.Path(sys.argv[sys.argv.index('--output')+1])
 report.write_text(json.dumps({'Results': []}))
if pathlib.Path(name+'-fail').exists(): sys.exit(1)
"""
        for name in ("semgrep-core", "trivy"):
            path = self.bin / name
            path.write_text(scanner)
            path.chmod(0o755)
        os.link(self.bin / "semgrep-core", self.bin / "osemgrep")
        self.command(sys.executable, "tools/push_gate/gate.py", "install")
        (self.repo / "private-untracked.txt").write_text(
            "PRIVATE LOCAL DATA MUST NEVER BE SCANNED\n"
        )

    def command(self, *argv, cwd=None, success=True):
        """Run a fixture command and require success unless failure is the subject."""
        result = subprocess.run(
            argv, cwd=cwd or self.repo, env=self.env, capture_output=True, check=False
        )
        if success:
            self.assertEqual(
                result.returncode, 0, result.stderr.decode(errors="replace")
            )
        return result

    def commit(self, message):
        """Record fixture changes while keeping the private untracked canary out."""
        self.command("git", "add", "--", ".", ":(exclude)private-untracked.txt")
        self.command("git", "commit", "--quiet", "--allow-empty", "-m", message)
        return self.command("git", "rev-parse", "HEAD").stdout.strip()

    def remote_tip(self):
        """Read the disposable remote's tested branch without modifying it."""
        return self.command(
            "git", "ls-remote", "origin", "refs/heads/feature/gate"
        ).stdout

    def fixture_git(self, *args, success=True):
        """Invoke the installed hooks with the disposable Git configuration."""
        return self.command("git", *args, success=success)

    def test_handoff_success(self):
        """Deliver a planning-only change and its eventual working implementation."""
        exercise_handoff_success(self.repo, self.fixture_git, "implementation.py")

    def test_handoff_rejections(self):
        """Refuse skipped, failing, and missing selectors even with a passing neighbor."""
        exercise_handoff_rejections(self.repo, self.fixture_git, "implementation.py")

    def test_success_uses_pushed_commit_with_dirty_worktree(self):
        """Dirty implementation content must not replace the pushed snapshot."""
        sha = self.commit("successful fixture")
        (self.repo / "implementation.py").write_text(
            "raise RuntimeError('dirty file must not run')\n"
        )
        self.command("git", "push", "--quiet", "origin", "feature/gate")
        self.assertIn(sha, self.remote_tip())

    def test_push_validates_selected_commit_when_head_differs(self):
        """Validate the explicitly pushed SHA even when HEAD would fail checks."""
        selected = self.commit("selected good commit").decode()
        (self.repo / "implementation.py").write_text("VALUE = 2\n")
        self.commit("bad HEAD that is not being pushed")
        self.command(
            "git", "push", "--quiet", "origin", selected + ":refs/heads/feature/gate"
        )
        self.assertIn(selected.encode(), self.remote_tip())

    def test_nonbehavioral_exemption_requires_exact_hashes(self):
        """Accept reviewed equivalent content and reject a stale exemption."""
        original = (self.repo / "implementation.py").read_text()
        changed = original.rstrip() + "  # documented equivalent comment\n"
        (self.repo / "implementation.py").write_text(changed)
        exemption = {
            "implementation.py": {
                "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
                "reason": (
                    "Only an explanatory comment changes; execution remains equivalent."
                ),
            }
        }
        (self.repo / "push-gate-nonbehavioral.json").write_text(json.dumps(exemption))
        self.commit("exact nonbehavioral exemption")
        self.command("git", "push", "--quiet", "origin", "feature/gate")
        original_tip = self.remote_tip()
        (self.repo / "implementation.py").write_text(changed + "# stale exemption\n")
        self.commit("stale exemption must fail")
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Meaningful test update", result.stderr)
        self.assertEqual(self.remote_tip(), original_tip)

    def test_checks_and_scanners_prevent_remote_update(self):
        """Each scanner and canonical-check failure must preserve the remote tip."""
        self.command("git", "push", "--quiet", "origin", "feature/gate")
        original = self.remote_tip()
        for name in ("semgrep", "trivy"):
            with self.subTest(scanner=name):
                (self.repo / (name + "-fail")).write_text("failure canary\n")
                self.commit("scanner failure fixture")
                result = self.command(
                    "git", "push", "--quiet", "origin", "feature/gate", success=False
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.remote_tip(), original)
                (self.repo / (name + "-fail")).unlink()
        (self.repo / "implementation.py").write_text("VALUE = 2\n")
        (self.repo / "tests/test_changed.py").write_text(
            "def test_changed():\n assert 2 == 2\n"
        )
        self.commit("canonical check failure fixture")
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_tip(), original)

    def test_reserved_ignore_case_aliases_prevent_remote_update(self):
        """Mixed-case file and directory aliases must preserve the remote tip."""
        self.command("git", "push", "--quiet", "origin", "feature/gate")
        original = self.remote_tip()
        for name in (
            ".PARK-SEMGREP-IGNORE",
            "sub/.Park-Semgrep-Ignore",
            "a/b/.pArK-sEmGrEp-IgNoRe/hidden.txt",
        ):
            with self.subTest(name=name):
                path = self.repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("*\n")
                self.commit("reserved ignore case alias fixture")
                result = self.command(
                    "git", "push", "--quiet", "origin", "feature/gate", success=False
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"Reserved Semgrep ignore", result.stderr)
                self.assertEqual(self.remote_tip(), original)
                path.unlink()

    def test_missing_tool_prevents_remote_update(self):
        """A failed raw engine probe must block the initial branch publication."""
        self.commit("missing tool fixture")
        (self.bin / "semgrep-core").unlink()
        # A failing executable is used because another installation may be on PATH.
        (self.bin / "semgrep-core").write_text("#!/bin/sh\nexit 127\n")
        (self.bin / "semgrep-core").chmod(0o755)
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_tip(), b"")

    def test_branch_wide_requirement_survives_previous_push(self):
        """A prior push must not erase the branch's meaningful-test requirement."""
        self.command("git", "push", "--quiet", "origin", "feature/gate")
        original = self.remote_tip()
        (self.repo / "implementation.py").write_text(
            "VALUE = 1  # implementation edit\n"
        )
        self.commit("implementation without assertions")
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Meaningful test update", result.stderr)
        self.assertEqual(self.remote_tip(), original)

    def test_changed_policy_is_blocked(self):
        """Reject outgoing scanner rules that differ from the installed policy."""
        (self.repo / "tools/push_gate/semgrep.yml").write_text("rules: []\n")
        self.commit("unreviewed policy change")
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"differs from installed", result.stderr)
        self.assertEqual(self.remote_tip(), b"")

    def test_symlink_prevents_remote_update(self):
        """Reject committed symlinks rather than scanning their external targets."""
        (self.repo / "linked-private.txt").symlink_to(self.root / "outside.txt")
        self.commit("symlink fixture")
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Unsupported symlink", result.stderr)
        self.assertEqual(self.remote_tip(), b"")

    def test_install_preserves_hooks_and_restores_configuration(self):
        """Require hook replacement consent and restore the original hook routing."""
        self.command(sys.executable, "tools/push_gate/gate.py", "uninstall")
        hooks = self.repo / ".githooks"
        hooks.mkdir()
        original = hooks / "pre-push"
        original.write_text("#!/bin/sh\nexit 8\n")
        original.chmod(0o755)
        before_commit = hooks / "pre-commit"
        before_commit.write_text("#!/bin/sh\ntouch hook-executed\n")
        before_commit.chmod(0o755)
        self.command("git", "config", "core.hooksPath", ".githooks")
        revision = self.command("git", "rev-parse", "HEAD").stdout.decode().strip()
        rejected = self.command(
            sys.executable, "tools/push_gate/gate.py", "install", success=False
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.command(
            sys.executable,
            "tools/push_gate/gate.py",
            "install",
            "--replace",
            "--revision",
            revision,
        )
        self.assertEqual(original.read_text(), "#!/bin/sh\nexit 8\n")
        self.command(
            "git", "commit", "--quiet", "--allow-empty", "-m", "forward other hook"
        )
        self.assertTrue((self.repo / "hook-executed").exists())
        self.command(sys.executable, "tools/push_gate/gate.py", "uninstall")
        self.assertEqual(
            self.command("git", "config", "--get", "core.hooksPath").stdout.strip(),
            b".githooks",
        )

    def test_hook_uses_actual_push_destination(self):
        """Fetch the selected push URL rather than assuming the fetch remote."""
        alternate = self.root / "alternate.git"
        self.command("git", "init", "--quiet", "--bare", str(alternate), cwd=self.root)
        self.command("git", "config", "remote.origin.pushurl", str(alternate))
        result = self.command(
            "git", "push", "--quiet", "origin", "feature/gate", success=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Remote default branch is absent", result.stderr)
        self.assertEqual(self.command("git", "ls-remote", str(alternate)).stdout, b"")


if __name__ == "__main__":
    unittest.main()

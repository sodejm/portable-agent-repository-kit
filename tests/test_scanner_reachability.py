"""Guard native scanner boundaries; optionally exercise the installed engine.

The historical Python-fallback assessment is retained in SCANNER_REACHABILITY.md.
Supported setup no longer imports those packages or needs that fallback probe.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "reachability_gate", ROOT / "tools/push_gate/gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ScannerReachabilityTests(unittest.TestCase):
    """Preserve complete command coverage and the sanitized environment boundary."""

    def scanner_commands(self, directory: Path, files=None) -> list[list[str]]:
        """Capture the actual argv builder without launching scanners or version probes."""
        policy = json.loads((ROOT / "tools/push_gate/policy.json").read_text())
        commands = []

        def capture(argv, *args):
            """Return empty scanner reports and retain the declared argv."""
            commands.append(argv)
            return (
                {"results": [], "errors": []}
                if argv[0] == "osemgrep"
                else {"Results": []}
            )

        def version_command(argv, *args, **kwargs):
            """Capture version probes so added invocations cannot hide there."""
            commands.append(argv)
            if argv[0] == "semgrep-core":
                return f"semgrep-core version: {policy['tools']['semgrep']} (a5341ae595)".encode()
            return policy["tools"]["trivy"].encode()

        (directory / "sample.py").write_text(
            'raise RuntimeError("Scan targets must not execute")\n'
        )
        rules = directory / "tools/push_gate/semgrep.yml"
        rules.parent.mkdir(parents=True)
        rules.write_bytes((ROOT / "tools/push_gate/semgrep.yml").read_bytes())
        with (
            patch.object(GATE, "run", side_effect=version_command),
            patch.object(GATE, "native_scanner", return_value="osemgrep"),
            patch.object(GATE, "scanner_run", side_effect=capture),
        ):
            GATE.scanners(
                directory,
                files or ["sample.py"],
                policy,
                GATE.clean_environment(),
                directory,
            )
        return commands

    def test_gate_uses_native_local_scan_without_fallback(self) -> None:
        """Guard all scanner/version invocations and every existing scan protection."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            commands = self.scanner_commands(directory)
            self.assertEqual(len(commands), 4)
            self.assertEqual(
                commands[:2], [["semgrep-core", "-version"], ["trivy", "--version"]]
            )
            self.assertEqual(
                commands[2],
                [
                    "osemgrep",
                    "scan",
                    "--experimental",
                    "--config",
                    str(directory / "tools/push_gate/semgrep.yml"),
                    "--strict",
                    "--error",
                    "--metrics=off",
                    "--disable-version-check",
                    "--disable-nosem",
                    "--no-git-ignore",
                    "--max-target-bytes=0",
                    "--x-semgrepignore-filename",
                    GATE.SEMGREP_IGNORE,
                    "--json",
                    "./sample.py",
                ],
            )
            self.assertEqual(
                commands[3],
                [
                    "trivy",
                    "fs",
                    "--config",
                    "",
                    "--ignorefile",
                    "",
                    "--secret-config",
                    "",
                    "--scanners",
                    "vuln,secret,misconfig",
                    "--severity",
                    "HIGH,CRITICAL",
                    "--include-dev-deps",
                    "--show-suppressed",
                    "--exit-code",
                    "1",
                    "--format",
                    "json",
                    "--disable-telemetry",
                    "--skip-version-check",
                    "--timeout",
                    "15m",
                    "--skip-dirs",
                    ".git",
                    "--output",
                    str(directory / "trivy.json"),
                    ".",
                ],
            )
            self.assertFalse((directory / GATE.SEMGREP_IGNORE).exists())

    def test_gate_removes_mcp_trace_and_python_injection_environment(self) -> None:
        """Seed activation and propagation settings, then verify the allowlist boundary."""
        poison = dict.fromkeys(
            (
                "MCP_TRANSPORT",
                "SEMGREP_MCP",
                "SEMGREP_MCP_PORT",
                "SEMGREP_RULES",
                "SEMGREP_OTEL_ENDPOINT",
                "SEMGREP_TRACE_PARENT_TRACE_ID",
                "SEMGREP_TRACE_PARENT_SPAN_ID",
                "OTEL_PROPAGATORS",
                "TRACEPARENT",
                "TRACESTATE",
                "PYTHONPATH",
                "PYTHONSTARTUP",
                "SEMGREP_APP_TOKEN",
                "LD_PRELOAD",
                "LD_LIBRARY_PATH",
                "DYLD_INSERT_LIBRARIES",
                "DYLD_LIBRARY_PATH",
            ),
            "synthetic-untrusted-value",
        )
        with patch.dict(os.environ, poison):
            environment = GATE.clean_environment()
        self.assertFalse(set(poison) & set(environment))
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
        self.assertLessEqual(
            set(environment),
            {
                "PATH",
                "HOME",
                "TMPDIR",
                "LANG",
                "LC_ALL",
                "TERM",
                "SSH_AUTH_SOCK",
                "GIT_CONFIG_NOSYSTEM",
                "GIT_CONFIG_GLOBAL",
                "GIT_TERMINAL_PROMPT",
                "PYTHONNOUSERSITE",
                "CI",
                "NO_COLOR",
            },
        )

    @unittest.skipUnless(
        os.environ.get("PARK_NATIVE_SEMGREP") == "1", "opt-in installed native scanner"
    )
    def test_real_native_rule_and_suppression_controls(self) -> None:
        """Scan synthetic language controls with Python launchers replaced by traps.

        This tests local rules and ignore/suppression handling on the operator's
        engine, not native vulnerability absence or a successful real push hook.
        """
        environment = GATE.clean_environment()
        scanner = GATE.native_scanner(environment)
        core = str(Path(scanner).with_name("semgrep-core"))
        version = subprocess.run(
            [core, "-version"], env=environment, capture_output=True, timeout=30
        )
        self.assertEqual(
            (version.returncode, version.stdout.strip()),
            (0, b"semgrep-core version: 1.187.0 (a5341ae595)"),
        )
        with tempfile.TemporaryDirectory(prefix="park-native-scan-") as temporary:
            directory = Path(temporary)
            controls = {
                "sample.py": 'eval("1")  # nosemgrep\n',
                "nested/input.js": 'eval("1"); // nosemgrep\n',
                "nested/input.mjs": 'eval("1");\n',
                "nested/input.ts": 'eval("1");\n',
                "nested/input.tsx": 'eval("1");\n',
                "nested/input.go": 'package input\nimport "os/exec"\nfunc f() { exec.Command("sh", "-c", "true") }\n',
                "nested/input.sh": "curl -k https://example.invalid\n",
                "nested/input.yaml": "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION: true\n",
                "nested/input.yml": "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION: true\n",
                "nested/input.tf": "insecure = true\n",
                "nested/input.hcl": "skip_tls_verify = true\n",
            }
            for name, content in controls.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            command = self.scanner_commands(directory, list(controls))[2]
            (directory / "sample.py").write_text(controls["sample.py"])
            command[0] = scanner
            for name in (".gitignore", ".semgrepignore", "nested/.semgrepignore"):
                (directory / name).write_text("*\n")
            (directory / GATE.SEMGREP_IGNORE).write_text("")
            home = directory / "home"
            home.mkdir()
            traps = directory / "traps"
            traps.mkdir()
            for name in ("python", "python3", "pysemgrep", "semgrep"):
                executable = traps / name
                executable.write_text(
                    "#!/bin/sh\n/usr/bin/touch fallback-observed\nexit 99\n"
                )
                executable.chmod(0o755)
            environment.update(
                HOME=str(home), PATH=str(traps) + os.pathsep + environment["PATH"]
            )
            result = subprocess.run(
                command, cwd=directory, env=environment, capture_output=True, timeout=90
            )
            self.assertFalse((directory / "fallback-observed").exists())
            self.assertEqual(
                result.returncode,
                1,
                "Expected rule findings; inspect raw output privately",
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["errors"])
            self.assertEqual(
                {item["path"].removeprefix("./") for item in report["results"]},
                set(controls),
            )


if __name__ == "__main__":
    unittest.main()

"""Guard the scoped scanner CVE assessment; opt in to real-library profiling.

The ordinary suite checks PARK's command and environment boundaries without
third-party packages. Run this file with PARK_SCANNER_REACHABILITY=1 using the
reviewed Semgrep environment's Python for the synthetic, instrumented scan.
Profiling is corroborating evidence, not an exhaustive non-reachability proof.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reachability_gate", ROOT / "tools/push_gate/gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
SINKS = {
    ("mcp/server/streamable_http_manager.py", "StreamableHTTPSessionManager.__init__"): "session-manager",
    ("mcp/server/auth/middleware/bearer_auth.py", "BearerAuthBackend.authenticate"): "bearer-auth",
    ("mcp/shared/_httpx_utils.py", "create_mcp_http_client"): "http-client",
    ("mcp/client/sse.py", "sse_client"): "sse-transport",
    ("mcp/client/streamable_http.py", "streamablehttp_client"): "legacy-http-transport",
    ("mcp/client/streamable_http.py", "streamable_http_client"): "http-transport",
    ("mcp/client/auth/oauth2.py", "OAuthClientProvider.async_auth_flow"): "oauth-flow",
    ("mcp/client/session.py", "ClientSession.call_tool"): "tool-call",
    ("mcp/client/session.py", "ClientSession._validate_tool_result"): "tool-schema",
    ("opentelemetry/trace/span.py", "TraceState.from_header"): "tracestate",
}


def probe_worker(report: Path, arguments: list[str], controls_only: bool = False) -> None:
    """Profile either positive controls or a real Python CLI fallback, separately.

Controls use empty/local inputs and never listen, send requests or fetch schemas.
The profiler does not replace dependency functions. It records selected Python
calls in this process and newly created Python threads, not native subprocesses.
"""
    from importlib.metadata import version

    expected = {"semgrep": "1.183.0", "mcp": "1.29.0", "opentelemetry-api": "1.37.0"}
    if {name: version(name) for name in expected} != expected:
        raise RuntimeError("Scanner dependency versions changed; reassess before profiling")
    counts = dict.fromkeys(SINKS.values(), 0)
    scan_calls = 0
    tracing_enabled = []
    stop_before_body = {"sse-transport", "legacy-http-transport", "http-transport", "oauth-flow", "tool-call"}

    class ControlObserved(Exception):
        """Stop selected positive controls at entry, before they can perform I/O."""

    def profile(frame, event, arg):
        """Count selected library entries without recording arguments or private data."""
        nonlocal scan_calls
        if event != "call":
            return
        filename = frame.f_code.co_filename.replace("\\", "/")
        qualified = frame.f_code.co_qualname
        for (suffix, function), label in SINKS.items():
            if filename.endswith("/" + suffix) and qualified == function:
                counts[label] += 1
                if controls_only and label in stop_before_body:
                    raise ControlObserved(label)
        if filename.endswith("/semgrep/commands/scan.py") and qualified == "scan":
            scan_calls += 1
        if filename.endswith("/semgrep/telemetry.py") and qualified == "Telemetry.configure":
            tracing_enabled.append(bool(frame.f_locals["enabled"]))

    async def controls():
        """Exercise every observed entry with bounded inputs and no network traffic."""
        from types import SimpleNamespace
        from mcp.client.session import ClientSession
        from mcp.client.sse import sse_client
        from mcp.client.streamable_http import streamable_http_client, streamablehttp_client
        from mcp.client.auth.oauth2 import OAuthClientProvider
        from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
        from mcp.server.lowlevel import Server
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp.shared._httpx_utils import create_mcp_http_client
        from mcp.types import CallToolResult
        from opentelemetry.trace import TraceState

        StreamableHTTPSessionManager(Server("synthetic-audit"))
        await BearerAuthBackend(None).authenticate(SimpleNamespace(headers={}))
        client = create_mcp_http_client()
        await client.aclose()
        session = SimpleNamespace(_tool_output_schemas={"synthetic": {"type": "object"}})
        await ClientSession._validate_tool_result(
            session, "synthetic", CallToolResult(content=[], structuredContent={})
        )
        TraceState.from_header(["synthetic=value"])

        async def observe_entry(awaitable):
            """Resume a coroutine/generator only as far as its profiled entry."""
            try:
                await awaitable
            except ControlObserved:
                pass
            else:
                raise RuntimeError("Expected entry was not intercepted")
            finally:
                # Python disables a profile function that raises an exception.
                sys.setprofile(profile)

        await observe_entry(sse_client("https://example.invalid").__aenter__())
        await observe_entry(streamablehttp_client("https://example.invalid").__aenter__())
        await observe_entry(streamable_http_client("https://example.invalid").__aenter__())
        await observe_entry(OAuthClientProvider.async_auth_flow(None, None).__anext__())
        await observe_entry(ClientSession.call_tool(None, "synthetic"))

    import asyncio

    sys.setprofile(profile)
    threading.setprofile(profile)
    try:
        if controls_only:
            def deny_control_network(event, args):
                """Fail closed if a positive control unexpectedly attempts network I/O."""
                if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto"}:
                    raise RuntimeError("Positive controls must not access the network")

            sys.addaudithook(deny_control_network)
            asyncio.run(controls())
            if not all(counts.values()):
                raise RuntimeError("A positive control was not observed")
        else:
            from semgrep.main import main

            sys.argv = ["pysemgrep", *arguments]
            main()
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=report.parent,
            prefix=report.stem + "-", suffix=".json", delete=False,
        ) as output:
            json.dump({
                "versions": expected, "sink_calls": counts, "scan_calls": scan_calls,
                "tracing_enabled": tracing_enabled,
            }, output)


class ScannerReachabilityTests(unittest.TestCase):
    """Preserve the command and environment assumptions of the scoped acceptance."""

    def scanner_commands(self, directory: Path) -> list[list[str]]:
        """Capture every declared scanner/version command without launching tools."""
        policy = json.loads((ROOT / "tools/push_gate/policy.json").read_text())
        commands = []

        def capture(argv, *args):
            """Return empty synthetic scanner reports and retain only their argv."""
            commands.append(argv)
            return {"results": [], "errors": []} if argv[0] == "semgrep" else {"Results": []}

        def version_command(argv, *args, **kwargs):
            """Capture version probes too, so an added invocation cannot hide there."""
            commands.append(argv)
            return policy["tools"][argv[0]].encode()

        (directory / "sample.py").write_text(
            '"""Synthetic scan input, not executable telemetry."""\n'
            'raise RuntimeError("Scan targets must not execute")\n'
        )
        rules = directory / "tools/push_gate/semgrep.yml"
        rules.parent.mkdir(parents=True)
        rules.write_bytes((ROOT / "tools/push_gate/semgrep.yml").read_bytes())
        with patch.object(GATE, "run", side_effect=version_command), \
                patch.object(GATE, "scanner_run", side_effect=capture):
            GATE.scanners(directory, ["sample.py"], policy, GATE.clean_environment(), directory)
        return commands

    def test_gate_uses_local_scan_without_mcp_or_trace(self) -> None:
        """Guard the complete declared call list and the accepted Semgrep argv."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            commands = self.scanner_commands(directory)
            self.assertEqual(len(commands), 4)
            self.assertEqual(commands[:2], [["semgrep", "--version"], ["trivy", "--version"]])
            self.assertEqual(commands[3][:2], ["trivy", "fs"])
            self.assertEqual(commands[2], [
                "semgrep", "scan", "--config", str(directory / "tools/push_gate/semgrep.yml"),
                "--strict", "--error", "--metrics=off", "--disable-version-check",
                "--disable-nosem", "--no-git-ignore", "--max-target-bytes=0",
                "--x-semgrepignore-filename", str(directory / "empty-semgrep-ignore"),
                "--json", "--output", str(directory / "semgrep.json"), "./sample.py",
            ])

    def test_gate_removes_mcp_trace_and_python_injection_environment(self) -> None:
        """Seed activation and propagation settings, then verify the allowlist boundary."""
        poison = dict.fromkeys((
            "MCP_TRANSPORT", "SEMGREP_MCP", "SEMGREP_MCP_PORT", "SEMGREP_RULES",
            "SEMGREP_OTEL_ENDPOINT", "SEMGREP_TRACE_PARENT_TRACE_ID",
            "SEMGREP_TRACE_PARENT_SPAN_ID", "OTEL_PROPAGATORS", "TRACEPARENT",
            "TRACESTATE", "PYTHONPATH", "PYTHONSTARTUP", "SEMGREP_APP_TOKEN",
        ), "synthetic-untrusted-value")
        with patch.dict(os.environ, poison):
            environment = GATE.clean_environment()
        self.assertFalse(set(poison) & set(environment))
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
        self.assertLessEqual(set(environment), {
            "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "TERM", "SSH_AUTH_SOCK",
            "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT",
            "PYTHONNOUSERSITE", "CI", "NO_COLOR",
        })

    @unittest.skipUnless(os.environ.get("PARK_SCANNER_REACHABILITY") == "1", "opt-in real scanner profiling")
    def test_real_native_dispatch_and_python_fallback(self) -> None:
        """Run native dispatch with an instrumented fallback and a temporary empty HOME."""
        with tempfile.TemporaryDirectory(prefix="park-scanner-reachability-") as temporary:
            directory = Path(temporary)
            command = self.scanner_commands(directory)[2]
            report = directory / "profile.json"
            wrapper = directory / "pysemgrep"
            wrapper.write_text(
                f"#!{sys.executable}\nimport runpy, sys\n"
                f"sys.argv = [sys.argv[0], '--probe', {str(report)!r}, *sys.argv[1:]]\n"
                f"runpy.run_path({str(Path(__file__).resolve())!r}, run_name='__main__')\n"
            )
            wrapper.chmod(0o700)
            environment = GATE.clean_environment()
            environment["PATH"] = os.pathsep.join((str(directory), str(Path(sys.executable).parent), environment["PATH"]))
            home = directory / "home"
            home.mkdir()
            environment["HOME"] = str(home)
            positive_report = directory / "positive.json"
            positive = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--controls", str(positive_report)],
                cwd=directory, env=environment, capture_output=True, timeout=30,
            )
            self.assertEqual(positive.returncode, 0, "Positive controls failed; inspect privately")
            control_reports = list(directory.glob("positive-*.json"))
            self.assertEqual(len(control_reports), 1)
            controls = json.loads(control_reports[0].read_text())
            self.assertTrue(all(controls["sink_calls"].values()))
            result = subprocess.run(command, cwd=directory, env=environment, capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, "Instrumented native scan failed; inspect privately")
            scan_report = json.loads((directory / "semgrep.json").read_text())
            self.assertEqual(scan_report["paths"]["scanned"], ["sample.py"])
            self.assertFalse(scan_report["results"])
            self.assertFalse(scan_report["errors"])
            reports = list(directory.glob("profile-*.json"))
            self.assertEqual(len(reports), 1, "Expected exactly one profiled fallback; reassess native dispatch")
            evidence = json.loads(reports[0].read_text())
            self.assertGreater(evidence["scan_calls"], 0)
            self.assertEqual(evidence["tracing_enabled"], [False])
            self.assertEqual(evidence["sink_calls"], dict.fromkeys(SINKS.values(), 0))
            print(json.dumps({"positive_controls": controls, "scan": evidence}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"--probe", "--controls"}:
        probe_worker(Path(sys.argv[2]), sys.argv[3:], controls_only=sys.argv[1] == "--controls")
    else:
        unittest.main()

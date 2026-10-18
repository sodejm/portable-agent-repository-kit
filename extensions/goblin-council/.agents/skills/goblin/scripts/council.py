#!/usr/bin/env python3
"""Goblin Council: bounded routing and native Codex session coordination."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
from worktree import CouncilError, Transaction, fingerprint, git, init, lock, paths, raw_manifest, tree, write_json

PACKAGE = Path(__file__).resolve().parents[4]
ROLES = PACKAGE / ".codex" / "agents"
SCHEMA = Path(__file__).resolve().parents[1] / "references" / "review.schema.json"
CATALOG = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"


def route(depth, blast, ambiguity, risk, mode="standard"):
    scores = [depth, blast, ambiguity, risk]
    if mode not in {"standard", "max"} or any(type(v) is not int or v not in range(4) for v in scores):
        raise CouncilError("Mode must be standard/max and scores must be integers from 0 to 3")
    if ambiguity == 3:
        return "BLOCKED"
    if mode == "max":
        return "CRITIQUE" if max(scores) >= 2 else "CASCADE"
    if risk >= 2 or depth == 3 or blast == 3 or sum(v >= 2 for v in scores) >= 2:
        return "CRITIQUE"
    return "SINGLE" if max(scores) <= 1 and sum(scores) <= 3 else "CASCADE"


def selection(role, task, repair=False):
    high_risk = task["risk"] >= 2 or task["depth"] == 3 or task["blast"] == 3
    if role.startswith("goblin-critic") or repair or high_risk:
        return "gpt-5.6-sol", "high"
    effort = "high" if task["mode"] == "max" else "medium"
    simple = max(task[k] for k in ("depth", "blast", "ambiguity", "risk")) <= 1
    model = "gpt-5.6-luna" if role == "goblin-drafter" and simple and task["mode"] == "standard" else "gpt-5.6-terra"
    return model, effort


def check_model(model, effort, catalog=CATALOG):
    try:
        data = json.loads(catalog.read_text())
        entries = data["models"]
        for m in entries:
            if m.get("slug") == model:
                levels = m.get("supported_reasoning_levels", [])
                allowed = [x.get("effort") if isinstance(x, dict) else x for x in levels]
                if effort in allowed:
                    return
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise CouncilError(f"Live catalog does not confirm {model}/{effort}; refresh catalog or revise the route; no fallback")


def codex_path(explicit=None):
    value = explicit or shutil.which("codex")
    bundled = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")
    if not value and bundled.is_file():
        value = str(bundled)
    if not value:
        raise CouncilError("Native Codex CLI is required")
    return str(Path(value).resolve())


def sandbox_flags(writable):
    settings = {
        "sandbox_mode": "workspace-write" if writable else "read-only",
        "approval_policy": "never",
        "sandbox_workspace_write.writable_roots": [],
        "sandbox_workspace_write.network_access": False,
        "sandbox_workspace_write.exclude_tmpdir_env_var": True,
        "sandbox_workspace_write.exclude_slash_tmp": True,
    }
    flags = []
    for key, value in settings.items():
        flags += ["-c", key + "=" + json.dumps(value)]
    return flags


def command_sandbox_flags(writable):
    # `codex sandbox` requires a permission profile; `exec` still supports legacy
    # sandbox settings. Render the same no-temp-write policy for both entrypoints.
    profile = "goblin-check-write" if writable else "goblin-check-read"
    settings = {
        f"permissions.{profile}.extends": ":workspace" if writable else ":read-only",
        f"permissions.{profile}.filesystem.:tmpdir": "read",
        f"permissions.{profile}.filesystem.:slash_tmp": "read",
        f"permissions.{profile}.network.enabled": False,
    }
    flags = ["-P", profile]
    for key, value in settings.items():
        flags += ["-c", key + "=" + json.dumps(value)]
    return flags


class Native:
    def __init__(self, cli=None, timeout=900):
        self.cli = codex_path(cli)
        self.timeout = timeout
        self.children = set()
        self.mutex = threading.Lock()
        self.probe_mutex = threading.Lock()
        self.cancelled = False
        self.lease_fd = None

    def stop(self):
        with self.mutex:
            self.cancelled = True
            children = list(self.children)
        for p in children:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
        for p in children:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()

    def command(self, argv, cwd, input=None, env=None):
        with self.mutex:
            if self.cancelled:
                raise CouncilError("Run interrupted")
            p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                                 pass_fds=(() if self.lease_fd is None else (self.lease_fd,)))
            self.children.add(p)
        try:
            stdout, stderr = p.communicate(input=input, timeout=self.timeout)
            return p.returncode, stdout, stderr
        except BaseException:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            raise
        finally:
            with self.mutex:
                self.children.discard(p)

    def probe(self, tx, cwd, writable):
        """Run actual OS sandbox checks before allowing any model execution."""
        # Critics share a frozen checkout. Serialize temporary probe-directory
        # setup/cleanup, while leaving the model sessions independent and parallel.
        with self.probe_mutex:
            self._probe(tx, cwd, writable)

    def _probe(self, tx, cwd, writable):
        import uuid
        token = ".goblin-probe-" + uuid.uuid4().hex
        controls = cwd / ".codex"
        made_control = not controls.exists()
        controls.mkdir(exist_ok=True)
        targets = [cwd / token, tx.root / token, tx.container / token,
                   controls / token, tx.state / token]
        # Probe git administrative file write access without modifying its contents.
        code = '''import os,json,sys
results=[]
for path in sys.argv[1:-1]:
    try:
        fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        os.close(fd); os.unlink(path); results.append(True)
    except PermissionError: results.append(False)
try:
    fd=os.open(sys.argv[-1],os.O_WRONLY|os.O_APPEND); os.close(fd); results.append(True)
except PermissionError: results.append(False)
print(json.dumps(results))
'''
        argv = [self.cli, "sandbox", *command_sandbox_flags(writable),
                "-C", str(cwd), sys.executable, "-c", code,
                *map(str, targets), str(cwd / ".git")]
        try:
            rc, out, err = self.command(argv, cwd)
            expected = [writable, False, False, False, False, False]
            if rc or json.loads(out) != expected:
                raise CouncilError(f"Sandbox probe failed (exit={rc}, result={out.decode(errors='replace').strip()}, "
                                   f"error={err.decode(errors='replace').strip()[:1500]}): "
                                   "primary, sibling, control paths and Git metadata must deny writes")
        finally:
            if made_control:
                controls.rmdir()
        tx.trace("SANDBOX_VERIFIED", writable=writable, cwd=str(cwd))

    def server_disables(self, cwd):
        # Ask Codex for merged server names; never print connector config or credentials.
        # Match stage feature selection: overriding a removed plugin's server
        # would create a transport-less config entry and prevent startup.
        rc, out, _ = self.command([self.cli, "mcp", "list", "--json",
                                  "-c", "features.plugins=false", "-c", "features.apps=false"], cwd)
        if rc:
            raise CouncilError("Cannot inspect merged MCP configuration; stage launch blocked")
        try:
            rows = json.loads(out)
            if not isinstance(rows, list):
                raise ValueError()
            flags = []
            for row in rows:
                name = row["name"]
                if "." in name:
                    raise CouncilError("Cannot safely override a dotted MCP server name; stage launch blocked")
                flags += ["-c", "mcp_servers." + name + ".enabled=false"]
            return flags
        except (ValueError, KeyError, TypeError):
            raise CouncilError("Unexpected MCP inventory format; stage launch blocked")

    def stage(self, tx, role, task, context, writable=False, repair=False):
        model, effort = selection(role, task, repair)
        check_model(model, effort)
        role_data = tomllib.loads((ROLES / (role + ".toml")).read_text())
        cwd = tx.candidate if writable else Path(tx.m["review"])
        self.probe(tx, cwd, writable)
        number = len(list(tx.directory.glob("stage-*.json")))
        output = tx.directory / f"stage-{number}-{role}.json"
        settings = {
            "model_reasoning_effort": effort,
            "developer_instructions": role_data["developer_instructions"],
            "agents.enabled": False,
            "features.apps": False, "features.plugins": False,
            "features.memories": False, "features.request_permissions_tool": False,
            "web_search": "disabled",
            "model_provider": "openai",
        }
        flags = sandbox_flags(writable)
        for k, v in settings.items():
            flags += ["-c", k + "=" + json.dumps(v)]
        flags += self.server_disables(cwd)
        argv = [self.cli, "exec", *flags, "-C", str(cwd), "-m", model,
                "--ephemeral", "--json", "-o", str(output)]
        if not writable:
            argv += ["--output-schema", str(SCHEMA)]
        prompt = {
            "task": task, "role": role, "workspace": str(cwd),
            "candidate_id": tx.m.get("candidate_id", tx.m["baseline"]["tree"]),
            "baseline_commit": tx.m["base_commit"],
            "candidate_commit": tx.m.get("candidate_commit"),
            "patch_path": tx.m.get("patch"),
            "context": context,
            "constraints": ["Honor applicable AGENTS.md and user policies.", "No delegation or external services.",
                            "Do not alter Git state, .codex, .agents, or any path outside workspace.",
                            "Return your report as the final message; the host writes the output file."],
        }
        tx.trace("STAGE_START", role=role, model=model, effort=effort, writable=writable,
                 rationale=task["routing_basis"], candidate_id=prompt["candidate_id"])
        started = time.monotonic()
        rc, out, err = self.command(argv + ["-"], cwd, json.dumps(prompt).encode())
        output.with_suffix(".events.jsonl").write_bytes(out)
        output.with_suffix(".stderr.log").write_bytes(err)
        if rc or not output.is_file():
            raise CouncilError(f"{role} failed; inspect private stage logs in {tx.directory}")
        if writable:
            report = output.read_text()
        else:
            try:
                report = json.loads(output.read_text())
            except ValueError:
                raise CouncilError("Reviewer returned invalid JSON; no promotion")
        tx.trace("STAGE_END", role=role, model=model, effort=effort,
                 duration_seconds=round(time.monotonic() - started, 3))
        return report

    def validate(self, tx, task):
        tx.integrity()
        if not task["validation"]:
            result = {"candidate_id": tx.m["candidate_id"], "passed": True,
                      "checks": [], "no_tests_reason": task["no_tests_reason"]}
        else:
            checkout = tx.container / f"validation-{tx.m['generation']}"
            git(tx.root, "worktree", "add", "--detach", checkout, tx.m["candidate_commit"])
            self.probe(tx, checkout, True)
            checks = []
            try:
                for i, command in enumerate(task["validation"]):
                    argv = [self.cli, "sandbox", *command_sandbox_flags(True),
                            "-C", str(checkout), *command]
                    rc, out, err = self.command(argv, checkout)
                    (tx.directory / f"validation-{tx.m['generation']}-{i}.log").write_bytes(out + err)
                    checks.append({"argv": command, "exit_code": rc})
                unchanged = (tree(checkout, tx.state) == tx.m["candidate_id"]
                             and raw_manifest(checkout) == tx.m["candidate_raw"])
                result = {"candidate_id": tx.m["candidate_id"], "passed": all(c["exit_code"] == 0 for c in checks) and unchanged,
                          "checks": checks, "source_unchanged": unchanged}
            finally:
                tx.remove_checkout(checkout)
        tx.m["validation"] = result
        tx.save()
        tx.trace("VALIDATION", **result)
        return result


def validate_task(task):
    required = {"objective", "scope", "acceptance", "depth", "blast", "ambiguity", "risk", "routing_basis", "validation"}
    if not required <= set(task):
        raise CouncilError("Task is missing: " + ", ".join(sorted(required - set(task))))
    for k in ("objective", "routing_basis"):
        if not isinstance(task[k], str) or not task[k].strip():
            raise CouncilError(f"Task {k} must be nonempty text")
    for k in ("scope", "acceptance"):
        if not isinstance(task[k], list) or not task[k] or not all(isinstance(s, str) and s for s in task[k]):
            raise CouncilError(f"Task {k} must contain nonempty strings")
    if not isinstance(task["validation"], list):
        raise CouncilError("Validation must be a list of argv arrays")
    for argv in task["validation"]:
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise CouncilError("Each validation must be a nonempty argv array, without shell interpolation")
    if not task["validation"] and not task.get("no_tests_reason"):
        raise CouncilError("Supply validation commands or an explicit no_tests_reason")
    return route(*(task[k] for k in ("depth", "blast", "ambiguity", "risk")), task["mode"])


def pipeline(tx, task, native):
    topology = validate_task(task)
    if topology not in {"CASCADE", "CRITIQUE"}:
        raise CouncilError("Only Cascade/Critique have transaction pipelines")
    tx.trace("ROUTED", topology=topology, mode=task["mode"])
    native.stage(tx, "goblin-drafter", task, {"phase": "draft"}, writable=True)
    tx.freeze()
    validation = native.validate(tx, task)
    if topology == "CASCADE":
        review = native.stage(tx, "goblin-judge", task, {"validation": validation})
        tx.record_review("goblin-judge", review)
        if review["verdict"] != "PASS" or not validation["passed"]:
            if review["restart_required"]:
                tx.reset()
            tx.trace("REPAIR", reason="judge or validation rejection")
            native.stage(tx, "goblin-drafter", task,
                         {"phase": "repair", "review": review, "validation": validation}, writable=True, repair=True)
            tx.freeze()
            validation = native.validate(tx, task)
            review = native.stage(tx, "goblin-judge", task, {"validation": validation, "phase": "final"}, repair=True)
            tx.record_review("goblin-judge", review)
    elif topology == "CRITIQUE":
        roles = ["goblin-critic-arch", "goblin-critic-sec"]
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            futures = [pool.submit(native.stage, tx, role, task, {"validation": validation}) for role in roles]
            reports = [f.result() for f in futures]
        except BaseException:
            native.stop()
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        for role, report in zip(roles, reports):
            tx.record_review(role, report)
        if any(r["restart_required"] for r in reports):
            tx.reset()
        tx.trace("SYNTHESIZED_REVISION", critics=roles)
        native.stage(tx, "goblin-drafter", task,
                     {"phase": "synthesize-and-revise", "independent_reviews": reports, "validation": validation,
                      "instruction": "Synthesize both reports, resolve disagreements with evidence, and make one coherent revision."},
                     writable=True, repair=True)
        tx.freeze()
        validation = native.validate(tx, task)
        review = native.stage(tx, "goblin-judge", task, {"validation": validation, "independent_reviews": reports, "phase": "final"}, repair=True)
        tx.record_review("goblin-judge", review)
    else:
        raise CouncilError("Only Cascade/Critique have transaction pipelines")
    if review["verdict"] != "PASS" or not validation["passed"]:
        tx.m["status"] = "REJECTED"
        tx.save()
        tx.trace("REJECTED")
        raise CouncilError("Repair budget exhausted; candidate retained without primary mutations")
    tx.promote()
    return {"run_id": tx.m["id"], "status": tx.m["status"], "trace": str(tx.directory / "trace.jsonl")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".")
    sub = p.add_subparsers(dest="command", required=True)
    routing = sub.add_parser("route")
    for k in ("depth", "blast", "ambiguity", "risk"):
        routing.add_argument("--" + k, type=int, required=True)
    routing.add_argument("--mode", choices=["standard", "max"], default="standard")
    execution = sub.add_parser("run")
    execution.add_argument("--task", required=True)
    execution.add_argument("--mode", choices=["standard", "max"], default="standard")
    execution.add_argument("--codex")
    execution.add_argument("--timeout", type=int, default=900)
    sub.add_parser("init")
    sub.add_parser("recover")
    for cmd in ("status", "freeze", "reset", "abandon"):
        sub.add_parser(cmd).add_argument("run_id")
    args = p.parse_args()
    if args.command == "route":
        print(json.dumps({"topology": route(args.depth, args.blast, args.ambiguity, args.risk, args.mode)}))
    elif args.command == "init":
        print(json.dumps(init(args.repo), indent=2))
    elif args.command == "recover":
        _, state = paths(args.repo)
        for entry in sorted(state.glob("*/state.json")):
            m = json.loads(entry.read_text())
            print(json.dumps({k: m[k] for k in ("id", "status", "candidate")}))
    elif args.command == "run":
        task = json.loads(Path(args.task).read_text())
        task["mode"] = args.mode
        topology = validate_task(task)
        if topology == "BLOCKED":
            raise CouncilError("Acceptance-blocking ambiguity: clarify before execution")
        if topology == "SINGLE":
            print(json.dumps({"topology": "SINGLE", "action": "Execute in the primary Codex thread; no child sessions launched",
                              "effort": "low" if not any(task[k] for k in ("depth", "blast", "ambiguity", "risk")) else "medium"}))
            return
        native = Native(args.codex, args.timeout)
        # Validate availability before creating the transaction.
        for role in ("goblin-drafter", "goblin-judge", "goblin-critic-arch", "goblin-critic-sec"):
            check_model(*selection(role, task))
        m = init(args.repo)
        tx = Transaction(args.repo, m["id"])
        print(json.dumps({"run_id": m["id"], "topology": topology, "candidate": m["candidate"]}), flush=True)
        def interrupt(signum, frame):
            native.stop()
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGINT, interrupt)
        with tx.lease() as lease:
            native.lease_fd = lease.fileno()
            try:
                result = pipeline(tx, task, native)
            except BaseException:
                native.stop()
                if tx.m["status"] not in {"REJECTED", "PROMOTING", "PROMOTED", "PROMOTION_BLOCKED", "PROMOTION_NEEDS_INSPECTION"}:
                    tx.m["status"] = "INTERRUPTED"
                    tx.save()
                raise
        print(json.dumps(result))
    else:
        tx = Transaction(args.repo, args.run_id)
        with tx.lease():
            if args.command == "status":
                print(json.dumps(tx.m, indent=2))
            else:
                getattr(tx, args.command)()
                print(json.dumps(tx.m, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (CouncilError, OSError, ValueError) as e:
        print(f"Goblin Council: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Goblin Council interrupted; run retained. Use recover/status before abandon.", file=sys.stderr)
        sys.exit(130)

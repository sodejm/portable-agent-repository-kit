#!/usr/bin/env python3
"""Acceptance tests for the dependency-free agent workboard."""

from __future__ import annotations

import concurrent.futures
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "agent-workboard"
    / "scripts"
    / "workboard.py"
)


def run_cli(
    *arguments: str,
    cwd: Path,
    home: Path,
    input_data: str = "",
    check: bool = True,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *(str(argument) for argument in arguments)],
        cwd=str(cwd),
        env=env,
        input=input_data,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            "command failed ({}):\nstdout={}\nstderr={}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    return result


class WorkboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.database = self.root / "state" / "workboard.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        return run_cli(
            "--db",
            str(self.database),
            "--json",
            *arguments,
            cwd=self.project,
            home=self.home,
            check=check,
        )

    def result(self, *arguments: str) -> dict:
        return json.loads(self.cli(*arguments).stdout)

    def start_run(self, session: str = "session-parent") -> str:
        return self.result(
            "run", "start", "--title", "Acceptance run", "--session-id", session
        )["run_id"]

    def add_task(
        self,
        run_id: str,
        title: str = "Bounded task",
        dependencies: tuple = (),
    ) -> str:
        arguments = [
            "task",
            "add",
            "--run-id",
            run_id,
            "--title",
            title,
            "--goal",
            "Inspect a bounded target",
            "--scope",
            "Read only",
            "--inputs-json",
            '["src"]',
            "--expected-output",
            "A concise finding",
            "--acceptance-json",
            '["Finding is evidence-backed"]',
            "--model",
            "gpt-5.6-terra",
            "--effort",
            "medium",
        ]
        for dependency in dependencies:
            arguments.extend(["--depends-on", dependency])
        return self.result(*arguments)["task_id"]

    def fetch_task(self, task_id: str) -> dict:
        data = self.result("status", "--task-id", task_id)
        return data["tasks"][0]

    def test_init_and_migration_are_idempotent_and_secure(self) -> None:
        first = self.result("init")
        second = self.result("init")
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first, second)
        self.assertEqual(stat.S_IMODE(self.database.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.database.parent.stat().st_mode), 0o700)
        with sqlite3.connect(str(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 0)
        # foreign_keys is connection-local; verify the CLI applies it through behavior.
        run_id = self.start_run()
        bad = self.cli(
            "task",
            "add",
            "--run-id",
            run_id,
            "--title",
            "Bad dependency",
            "--goal",
            "x",
            "--scope",
            "x",
            "--expected-output",
            "x",
            "--model",
            "gpt-5.6-terra",
            "--effort",
            "low",
            "--depends-on",
            "missing",
            check=False,
        )
        self.assertEqual(bad.returncode, 2)

    def test_non_git_hash_is_stable_and_isolates_projects(self) -> None:
        other = self.root / "other"
        other.mkdir()
        first = json.loads(
            run_cli(
                "--cwd",
                str(self.project),
                "--json",
                "init",
                cwd=self.project,
                home=self.home,
            ).stdout
        )
        repeat = json.loads(
            run_cli(
                "--cwd",
                str(self.project / "."),
                "--json",
                "init",
                cwd=self.project,
                home=self.home,
            ).stdout
        )
        isolated = json.loads(
            run_cli(
                "--cwd",
                str(other),
                "--json",
                "init",
                cwd=other,
                home=self.home,
            ).stdout
        )
        self.assertEqual(first["database"], repeat["database"])
        self.assertNotEqual(first["database"], isolated["database"])
        self.assertIn(".codex/orchestration/projects", first["database"])

    def test_linked_worktrees_share_git_common_database_and_remain_untracked(self) -> None:
        repository = self.root / "repository"
        worktree_one = self.root / "worktree-one"
        worktree_two = self.root / "worktree-two"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--allow-empty",
                "-q",
                "-m",
                "initial",
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "worktree", "add", "-q", str(worktree_one)],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "worktree",
                "add",
                "-q",
                "-b",
                "second-worktree",
                str(worktree_two),
            ],
            check=True,
        )
        paths = []
        for checkout in (repository, worktree_one, worktree_two):
            result = json.loads(
                run_cli(
                    "--cwd",
                    str(checkout),
                    "--json",
                    "init",
                    cwd=checkout,
                    home=self.home,
                ).stdout
            )
            paths.append(result["database"])
        self.assertEqual(len(set(paths)), 1)
        self.assertEqual(
            subprocess.run(
                ["git", "-C", str(repository), "status", "--porcelain"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout,
            "",
        )

    def test_exactly_one_concurrent_claim_wins(self) -> None:
        run_id = self.start_run()
        task_id = self.add_task(run_id)

        def claim(agent: str) -> subprocess.CompletedProcess:
            return self.cli(
                "task",
                "claim",
                "--task-id",
                task_id,
                "--agent-id",
                agent,
                check=False,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, ("agent-a", "agent-b")))
        self.assertEqual(sorted(result.returncode for result in results), [0, 2])
        task = self.fetch_task(task_id)
        self.assertEqual(task["status"], "running")
        self.assertIn(task["assigned_agent_id"], ("agent-a", "agent-b"))

    def test_dependencies_heartbeat_completion_block_and_cancel(self) -> None:
        run_id = self.start_run()
        first = self.add_task(run_id, "First")
        second = self.add_task(run_id, "Second", dependencies=(first,))
        self.assertEqual(self.fetch_task(second)["status"], "pending")
        self.result(
            "task", "claim", "--task-id", first, "--agent-id", "agent-first"
        )
        heartbeat = self.result(
            "task",
            "heartbeat",
            "--task-id",
            first,
            "--agent-id",
            "agent-first",
            "--progress",
            "read source",
        )
        self.assertIsNotNone(heartbeat["lease_expires_at"])
        completion = self.result(
            "task",
            "complete",
            "--task-id",
            first,
            "--agent-id",
            "agent-first",
            "--summary",
            "Inspection complete",
            "--validation",
            "Read-only check passed",
            "--changed-file",
            "src/example.py",
            "--validation-file",
            "reports/check.txt",
        )
        self.assertIn(second, completion["made_ready"])
        self.assertEqual(self.fetch_task(second)["status"], "ready")
        self.result(
            "task", "claim", "--task-id", second, "--agent-id", "agent-second"
        )
        blocked = self.result(
            "task",
            "block",
            "--task-id",
            second,
            "--agent-id",
            "agent-second",
            "--reason",
            "Missing fixture",
            "--next-action",
            "Provide fixture",
        )
        self.assertTrue(Path(blocked["handoff"]).is_file())
        handoff_text = Path(completion["handoff"]).read_text()
        self.assertIn("changed_file: src/example.py", handoff_text)
        self.assertIn("validation: reports/check.txt", handoff_text)
        third = self.add_task(run_id, "Third")
        cancelled = self.result(
            "task", "cancel", "--task-id", third, "--reason", "No longer needed"
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(Path(cancelled["handoff"]).is_file())

    def test_expired_leases_stale_only_on_reconcile(self) -> None:
        run_id = self.start_run()
        task_id = self.add_task(run_id)
        self.result(
            "task", "claim", "--task-id", task_id, "--agent-id", "agent-stale"
        )
        with sqlite3.connect(str(self.database)) as connection:
            connection.execute(
                """
                UPDATE tasks SET lease_expires_at = '2000-01-01T00:00:00+00:00'
                WHERE task_id = ?
                """,
                (task_id,),
            )
            connection.commit()
        self.assertEqual(self.fetch_task(task_id)["status"], "running")
        reconciled = self.result("reconcile")
        self.assertEqual(reconciled["stale"], [task_id])
        self.assertEqual(self.fetch_task(task_id)["status"], "stale")

    def test_handoff_export_is_explicit(self) -> None:
        run_id = self.start_run()
        task_id = self.add_task(run_id)
        self.result(
            "task", "claim", "--task-id", task_id, "--agent-id", "agent-export"
        )
        completed = self.result(
            "task",
            "complete",
            "--task-id",
            task_id,
            "--agent-id",
            "agent-export",
            "--summary",
            "Done",
            "--validation",
            "Checked",
        )
        handoff = Path(completed["handoff"])
        self.assertTrue(handoff.is_file())
        destination = self.project / "docs" / "handoff.md"
        exported = self.result(
            "export", "--task-id", task_id, "--to", str(destination)
        )
        self.assertEqual(Path(exported["exported"]), destination.resolve())
        self.assertEqual(destination.read_text(), handoff.read_text())

    def test_explicit_gc_removes_only_eligible_terminal_tasks(self) -> None:
        run_id = self.start_run()
        completed_id = self.add_task(run_id, "Completed")
        blocked_id = self.add_task(run_id, "Blocked")
        self.result(
            "task", "complete", "--task-id", completed_id, "--summary", "Done"
        )
        self.result(
            "task",
            "block",
            "--task-id",
            blocked_id,
            "--reason",
            "Waiting",
            "--next-action",
            "Resume later",
        )
        with sqlite3.connect(str(self.database)) as connection:
            connection.execute(
                "UPDATE tasks SET updated_at = '2000-01-01T00:00:00+00:00'"
            )
            connection.commit()
        collected = self.result("gc", "--older-than", "1")
        self.assertEqual(collected["deleted_tasks"], [completed_id])
        self.assertEqual(self.fetch_task(blocked_id)["status"], "blocked")
        missing = self.cli("status", "--task-id", completed_id)
        self.assertEqual(json.loads(missing.stdout)["count"], 0)

    def test_hook_fixtures_and_subagent_stop_loop_guard(self) -> None:
        run_id = self.start_run(session="parent-hook")
        task_id = self.add_task(run_id)
        for index in range(10):
            self.add_task(run_id, "Summary task {}".format(index))
        self.result(
            "task",
            "bind",
            "--task-id",
            task_id,
            "--agent-id",
            "agent-hook",
            "--agent-type",
            "worker",
        )

        def hook(payload: dict) -> dict:
            result = run_cli(
                "--db",
                str(self.database),
                "hook",
                cwd=self.project,
                home=self.home,
                input_data=json.dumps(payload),
            )
            return json.loads(result.stdout) if result.stdout.strip() else {}

        common = {
            "session_id": "parent-hook",
            "transcript_path": None,
            "cwd": str(self.project),
            "model": "gpt-5.6-terra",
            "permission_mode": "default",
        }
        started = hook(
            dict(common, hook_event_name="SessionStart", source="startup")
        )
        context = started["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(len(context), 1200)
        self.assertIn(str(self.database), context)
        self.assertLessEqual(
            len([line for line in context.splitlines() if line.startswith("- task_")]),
            8,
        )
        subagent = hook(
            dict(
                common,
                hook_event_name="SubagentStart",
                turn_id="turn-1",
                agent_id="agent-hook",
                agent_type="worker",
            )
        )
        self.assertIn(
            "WORKBOARD_TASK_ID",
            subagent["hookSpecificOutput"]["additionalContext"],
        )
        correction = hook(
            dict(
                common,
                hook_event_name="SubagentStop",
                turn_id="turn-1",
                agent_id="agent-hook",
                agent_type="worker",
                agent_transcript_path=None,
                stop_hook_active=False,
                last_assistant_message="Done",
            )
        )
        self.assertEqual(correction["decision"], "block")
        allowed = hook(
            dict(
                common,
                hook_event_name="SubagentStop",
                turn_id="turn-1",
                agent_id="agent-hook",
                agent_type="worker",
                agent_transcript_path=None,
                stop_hook_active=True,
                last_assistant_message="Still done",
            )
        )
        self.assertEqual(allowed, {})
        self.assertEqual(self.fetch_task(task_id)["status"], "stale")
        ended = hook(
            dict(common, hook_event_name="SessionEnd", reason="other")
        )
        self.assertEqual(ended, {})
        with sqlite3.connect(str(self.database)) as connection:
            statuses = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            self.assertEqual(statuses[0], "closed")


if __name__ == "__main__":
    unittest.main(verbosity=2)

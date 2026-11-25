from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ci" / "review_gate.py"
SPEC = importlib.util.spec_from_file_location("review_gate", MODULE_PATH)
assert SPEC and SPEC.loader
review_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review_gate
SPEC.loader.exec_module(review_gate)

HEAD = "a" * 40
OLD_HEAD = "b" * 40


class FakeGitHub:
    def __init__(
        self,
        *,
        author: str = "contributor",
        author_type: str = "User",
        reviewer_type: str = "User",
        permission: str = "write",
        reviews: list[dict[str, Any]] | None = None,
        final_head: str = HEAD,
    ) -> None:
        self.author = author
        self.author_type = author_type
        self.reviewer_type = reviewer_type
        self.permission = permission
        self.reviews = reviews or []
        self.final_head = final_head

    def get(self, path: str) -> Any:
        if path.endswith("/pulls/7"):
            return {
                "number": 7,
                "head": {"sha": self.final_head},
                "user": {"login": self.author},
                "state": "open",
                "base": {"repo": {"full_name": "sodejm/portable-agent-repository-kit"}},
            }
        if path == f"/users/{self.author}":
            return {"login": self.author, "type": self.author_type}
        if path == "/users/sodejm":
            return {"login": "sodejm", "type": self.reviewer_type}
        if path.endswith("/collaborators/sodejm/permission"):
            return {"permission": self.permission, "role_name": self.permission}
        raise AssertionError(f"unexpected GET {path}")

    def pages(self, path: str) -> list[dict[str, Any]]:
        self.assert_review_path = path
        return self.reviews


class FailingGitHub(FakeGitHub):
    def pages(self, path: str) -> list[dict[str, Any]]:
        raise review_gate.GateError("synthetic API failure")


class TriggerGitHub:
    def __init__(self, run: dict[str, Any]) -> None:
        self.run = run

    def get(self, path: str) -> Any:
        self.path = path
        return self.run


class MainGitHub:
    def __init__(self, *, fail_at: str) -> None:
        self.fail_at = fail_at
        self.calls: list[tuple[str, str, Any]] = []

    def post(self, path: str, body: Any) -> Any:
        self.calls.append(("POST", path, body))
        return {"id": 101}

    def patch(self, path: str, body: Any) -> Any:
        self.calls.append(("PATCH", path, body))
        return {}

    def get(self, path: str) -> Any:
        self.calls.append(("GET", path, None))
        if "/actions/runs/" in path:
            if self.fail_at == "workflow":
                raise review_gate.GateError("synthetic workflow lookup failure")
            return workflow_run("Review event notification", "pull_request_review")
        if path.endswith("/pulls/7"):
            if self.fail_at == "pull":
                raise review_gate.GateError("synthetic pull lookup failure")
            raise AssertionError("evaluation should not reach a successful pull lookup")
        raise AssertionError(f"unexpected GET {path}")


def review(review_id: int, state: str, sha: str | None = HEAD, login: str = "sodejm") -> dict[str, Any]:
    return {"id": review_id, "state": state, "commit_id": sha, "user": {"login": login}}


def workflow_run(
    name: str = "Repository contract",
    event: str = "pull_request",
    **updates: Any,
) -> dict[str, Any]:
    paths = {
        "Repository contract": ".github/workflows/repository-contract.yml",
        "Review event notification": ".github/workflows/review-event-notification.yml",
    }
    run = {
        "name": name,
        "event": event,
        "path": paths.get(name, ".github/workflows/untrusted.yml"),
        "status": "completed",
        "pull_requests": [{"number": 7}],
        "head_sha": HEAD,
    }
    run.update(updates)
    return run


def workflow_event(event: str = "pull_request_review") -> dict[str, Any]:
    return {
        "workflow_run": {
            "id": 55,
            "event": event,
            "pull_requests": [{"number": 7, "head": {"sha": HEAD}}],
        }
    }


class ReviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = review_gate.Policy(
            "sodejm/portable-agent-repository-kit",
            review_gate.Identity("sodejm", "User"),
            review_gate.Reviewer("sodejm", "User", "write", True),
        )
        self.pull = review_gate.Pull(7, HEAD, "contributor", "open")

    def evaluate(self, client: FakeGitHub, pull: Any = None) -> Any:
        return review_gate.evaluate_pull(client, self.policy, pull or self.pull)

    def test_owner_user_is_owner_reviewed_without_approval(self) -> None:
        pull = review_gate.Pull(7, HEAD, "sodejm", "open")
        decision = self.evaluate(FakeGitHub(author="sodejm"), pull)
        self.assertTrue(decision.allowed)
        self.assertIn("Owner-reviewed", decision.title)
        self.assertIn("does not prove manual inspection", decision.summary)

    def test_owner_exception_rejects_bot_account(self) -> None:
        pull = review_gate.Pull(7, HEAD, "sodejm", "open")
        with self.assertRaisesRegex(review_gate.GateError, "requires the configured User"):
            self.evaluate(FakeGitHub(author="sodejm", author_type="Bot"), pull)

    def test_external_author_needs_current_exact_head_approval(self) -> None:
        decision = self.evaluate(FakeGitHub(reviews=[review(1, "APPROVED")]))
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.title, "Exact-head approval verified")

    def test_stale_approval_fails(self) -> None:
        decision = self.evaluate(FakeGitHub(reviews=[review(1, "APPROVED", OLD_HEAD)]))
        self.assertFalse(decision.allowed)
        self.assertIn("stale", decision.title.lower())

    def test_comment_does_not_erase_approval(self) -> None:
        client = FakeGitHub(reviews=[review(1, "APPROVED"), review(2, "COMMENTED")])
        self.assertTrue(self.evaluate(client).allowed)

    def test_later_changes_requested_or_dismissal_fails(self) -> None:
        for state in ("CHANGES_REQUESTED", "DISMISSED"):
            with self.subTest(state=state):
                client = FakeGitHub(reviews=[review(1, "APPROVED"), review(2, state)])
                self.assertFalse(self.evaluate(client).allowed)

    def test_unauthorized_approval_is_ignored(self) -> None:
        decision = self.evaluate(FakeGitHub(reviews=[review(1, "APPROVED", login="other-user")]))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.title, "Required approval missing")

    def test_reviewer_must_be_user_with_write_permission(self) -> None:
        with self.assertRaisesRegex(review_gate.GateError, "configured User"):
            self.evaluate(FakeGitHub(reviewer_type="Bot", reviews=[review(1, "APPROVED")]))
        with self.assertRaisesRegex(review_gate.GateError, "lacks"):
            self.evaluate(FakeGitHub(permission="read", reviews=[review(1, "APPROVED")]))

    def test_same_author_cannot_self_approve_without_owner_exception(self) -> None:
        policy = review_gate.Policy(
            self.policy.repository,
            review_gate.Identity("different-owner", "User"),
            self.policy.required_reviewer,
        )
        pull = review_gate.Pull(7, HEAD, "sodejm", "open")
        with self.assertRaisesRegex(review_gate.GateError, "same account"):
            review_gate.evaluate_pull(FakeGitHub(author="sodejm", reviews=[review(1, "APPROVED")]), policy, pull)

    def test_head_race_fails_closed(self) -> None:
        with self.assertRaisesRegex(review_gate.GateError, "changed during evaluation"):
            self.evaluate(FakeGitHub(reviews=[review(1, "APPROVED")], final_head=OLD_HEAD))

    def test_expected_contract_head_must_match(self) -> None:
        with self.assertRaisesRegex(review_gate.GateError, "not for the live PR head"):
            review_gate.evaluate_pull(
                FakeGitHub(reviews=[review(1, "APPROVED")]),
                self.policy,
                self.pull,
                expected_head=OLD_HEAD,
            )

    def test_api_failure_fails_closed(self) -> None:
        with self.assertRaisesRegex(review_gate.GateError, "synthetic API failure"):
            self.evaluate(FailingGitHub())

    def test_pagination_parser_selects_only_next_link(self) -> None:
        header = (
            '<https://api.github.com/repositories/1/pulls/7/reviews?page=1>; rel="prev", '
            '<https://api.github.com/repositories/1/pulls/7/reviews?page=3>; rel="next"'
        )
        self.assertEqual(
            review_gate._next_link(header),
            "https://api.github.com/repositories/1/pulls/7/reviews?page=3",
        )

    def test_unconfigured_and_unknown_config_fields_fail_closed(self) -> None:
        unconfigured = review_gate.Policy(self.policy.repository, None, None)
        with self.assertRaisesRegex(review_gate.GateError, "unconfigured"):
            review_gate.evaluate_pull(FakeGitHub(), unconfigured, self.pull)
        with tempfile.TemporaryDirectory(prefix="park-review-policy-") as temp:
            path = Path(temp) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repository": self.policy.repository,
                        "owner_review": None,
                        "required_reviewer": None,
                        "bypass": ["anyone"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(review_gate.GateError, "extra"):
                review_gate.load_policy(path)

            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "repository": self.policy.repository,
                        "owner_review": {"login": "sodejm", "account_type": "User"},
                        "required_reviewer": {
                            "login": "sodejm",
                            "account_type": "User",
                            "minimum_permission": "write",
                            "security_qualified": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(review_gate.GateError, "must be true"):
                review_gate.load_policy(path)

            path.write_text(
                '{"version": 1, "version": 1, "repository": "owner/repo", '
                '"owner_review": null, "required_reviewer": null}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(review_gate.GateError, "duplicate key"):
                review_gate.load_policy(path)

    def test_live_workflow_trigger_accepts_allowlisted_exact_identity(self) -> None:
        client = TriggerGitHub(workflow_run())
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run"}):
            self.assertEqual(
                review_gate._workflow_trigger(client, workflow_event(), self.policy.repository),
                (7, HEAD),
            )
        self.assertEqual(
            client.path,
            f"/repos/{self.policy.repository}/actions/runs/55",
        )

    def test_live_workflow_trigger_rejects_spoofed_identity(self) -> None:
        cases = {
            "name": workflow_run(name="Untrusted workflow"),
            "path suffix": workflow_run(
                path="untrusted/.github/workflows/repository-contract.yml"
            ),
            "event": workflow_run(event="workflow_dispatch"),
            "incomplete": workflow_run(status="in_progress"),
        }
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run"}):
            for label, run in cases.items():
                with self.subTest(label=label):
                    with self.assertRaisesRegex(
                        review_gate.GateError, "allowlisted|identity"
                    ):
                        review_gate._workflow_trigger(
                            TriggerGitHub(run), workflow_event(), self.policy.repository
                        )

    def test_live_workflow_trigger_rejects_bad_pr_association_and_head(self) -> None:
        cases = {
            "missing": workflow_run(pull_requests=[]),
            "ambiguous": workflow_run(
                pull_requests=[{"number": 7}, {"number": 8}]
            ),
            "zero": workflow_run(pull_requests=[{"number": 0}]),
        }
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run"}):
            for label, run in cases.items():
                with self.subTest(label=label):
                    with self.assertRaisesRegex(review_gate.GateError, "exactly one PR"):
                        review_gate._workflow_trigger(
                            TriggerGitHub(run), workflow_event(), self.policy.repository
                        )
            with self.assertRaisesRegex(review_gate.GateError, "head SHA"):
                review_gate._workflow_trigger(
                    TriggerGitHub(workflow_run(head_sha="not-a-sha")),
                    workflow_event(),
                    self.policy.repository,
                )

    def test_live_workflow_trigger_handles_push_and_dispatch(self) -> None:
        push = workflow_run(event="push", pull_requests=[])
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run"}):
            self.assertEqual(
                review_gate._workflow_trigger(
                    TriggerGitHub(push), workflow_event("push"), self.policy.repository
                ),
                (None, None),
            )
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            self.assertEqual(
                review_gate._workflow_trigger(
                    TriggerGitHub({}), {"inputs": {"pr_number": "7"}}, self.policy.repository
                ),
                (7, None),
            )
            for invalid in (True, 1.5, "7.0", "0"):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(review_gate.GateError, "positive integer"):
                        review_gate._workflow_trigger(
                            TriggerGitHub({}),
                            {"inputs": {"pr_number": invalid}},
                            self.policy.repository,
                        )

    def test_review_retrigger_supersedes_success_before_fallible_live_reads(self) -> None:
        for failure in ("workflow", "pull"):
            with self.subTest(failure=failure):
                client = MainGitHub(fail_at=failure)
                with tempfile.TemporaryDirectory(prefix="park-review-event-") as temp:
                    event_path = Path(temp) / "event.json"
                    event_path.write_text(json.dumps(workflow_event()), encoding="utf-8")
                    environment = {
                        "GITHUB_EVENT_NAME": "workflow_run",
                        "GITHUB_EVENT_PATH": str(event_path),
                        "GITHUB_REPOSITORY": self.policy.repository,
                        "REVIEW_GATE_TOKEN": "test-token",
                    }
                    with (
                        mock.patch.dict(os.environ, environment),
                        mock.patch.object(review_gate, "GitHub", return_value=client),
                        redirect_stderr(io.StringIO()),
                    ):
                        self.assertEqual(review_gate.main(), 1)
                self.assertEqual(client.calls[0][0], "POST")
                self.assertEqual(client.calls[0][2]["head_sha"], HEAD)
                self.assertEqual(client.calls[0][2]["status"], "in_progress")
                conclusion = client.calls[-1][2]
                self.assertEqual(client.calls[-1][0], "PATCH")
                self.assertEqual(conclusion["conclusion"], "failure")

    def test_workflows_do_not_execute_or_import_pr_content(self) -> None:
        gate = (ROOT / ".github/workflows/owner-review-gate.yml").read_text(encoding="utf-8")
        notice = (ROOT / ".github/workflows/review-event-notification.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.repository.default_branch", gate)
        self.assertIn("persist-credentials: false", gate)
        self.assertNotIn("github.event.pull_request.head", gate)
        self.assertNotIn("artifact", gate.lower())
        self.assertNotIn("cache", gate.lower())
        self.assertIn("permissions: {}", notice)
        self.assertNotIn("actions/checkout", notice)

    def test_documented_required_context_is_repository_contract_job(self) -> None:
        workflow = (ROOT / ".github/workflows/repository-contract.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(workflow, r"(?m)^name: Repository contract$")
        jobs = workflow.partition("\njobs:\n")[2]
        self.assertTrue(jobs, "repository contract workflow must define jobs")
        job_contexts = re.findall(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", jobs)

        for relative_path in (
            "docs/OWNER_REVIEW_POLICY.md",
            "templates/project/OWNER_REVIEW_POLICY.md",
        ):
            policy = (ROOT / relative_path).read_text(encoding="utf-8")
            documented = re.search(
                r"emitted\s+required\s+status\s+check context is `([^`]+)`", policy
            )
            self.assertIsNotNone(documented, relative_path)
            assert documented is not None
            self.assertEqual(documented.group(1), "validate", relative_path)
            self.assertIn(documented.group(1), job_contexts)
            self.assertIn("`validate` and `Owner review gate`", policy)


if __name__ == "__main__":
    unittest.main()

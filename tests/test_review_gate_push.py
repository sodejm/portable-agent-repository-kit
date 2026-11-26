"""Verify owner-review decisions for pushes that GitHub associates with a PR."""

import os
import unittest
from unittest import mock

import test_review_gate as fixtures


class PushReviewTests(unittest.TestCase):
    """Check branch-push associations against the live PR head and owner policy."""

    def test_associated_push_requires_live_pr_and_matching_head(self) -> None:
        """Resolve a single PR and reject missing approval, stale heads and ambiguous runs."""
        gate = fixtures.review_gate
        policy = gate.Policy(
            "sodejm/portable-agent-repository-kit",
            gate.Identity("sodejm", "User"),
            gate.Reviewer("sodejm", "User", "write", True),
        )
        event = fixtures.workflow_event("push")
        client = fixtures.FakeGitHub()
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_run"}):
            number, head = gate._workflow_trigger(
                fixtures.TriggerGitHub(fixtures.workflow_run(event="push")), event, policy.repository
            )
            self.assertEqual((number, head), (7, fixtures.HEAD))
            pull = gate.fetch_pull(client, policy.repository, number)
            self.assertFalse(gate.evaluate_pull(client, policy, pull, expected_head=head).allowed)
            with self.assertRaisesRegex(gate.GateError, "live PR head"):
                gate.evaluate_pull(client, policy, pull, expected_head=fixtures.OLD_HEAD)
            invalid_associations = (
                {"head_sha": None},
                {"pull_requests": [{"number": 7}, {"number": 8}]},
            )
            for changes in invalid_associations:
                with self.subTest(changes=changes), self.assertRaises(gate.GateError):
                    gate._workflow_trigger(
                        fixtures.TriggerGitHub(fixtures.workflow_run(event="push", **changes)),
                        event,
                        policy.repository,
                    )

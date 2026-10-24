#!/usr/bin/env python3
"""Evaluate PARK's owner-review policy from a trusted default-branch checkout."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA = re.compile(r"[0-9a-f]{40}")
PERMISSION_RANK = {"none": 0, "read": 1, "triage": 2, "write": 3, "maintain": 4, "admin": 5}
DECISIVE_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


class GateError(RuntimeError):
    """Raised when the gate cannot safely make an allow decision."""


@dataclasses.dataclass(frozen=True)
class Identity:
    login: str
    account_type: str


@dataclasses.dataclass(frozen=True)
class Reviewer(Identity):
    minimum_permission: str
    security_qualified: bool


@dataclasses.dataclass(frozen=True)
class Policy:
    repository: str
    owner_review: Identity | None
    required_reviewer: Reviewer | None


@dataclasses.dataclass(frozen=True)
class Pull:
    number: int
    head_sha: str
    author: str
    state: str


@dataclasses.dataclass(frozen=True)
class Target:
    number: int
    head_sha: str | None


@dataclasses.dataclass(frozen=True)
class Decision:
    allowed: bool
    title: str
    summary: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"review policy contains duplicate key {key!r}")
        result[key] = value
    return result


def _object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{label} must be an object")
    extras = set(value) - keys
    missing = keys - set(value)
    if extras or missing:
        raise GateError(
            f"{label} has invalid keys (missing={sorted(missing)}, extra={sorted(extras)})"
        )
    return value


def _identity(value: Any, label: str) -> Identity | None:
    if value is None:
        return None
    item = _object(value, label, {"login", "account_type"})
    login, account_type = item["login"], item["account_type"]
    if not isinstance(login, str) or not LOGIN.fullmatch(login):
        raise GateError(f"{label}.login is invalid")
    if account_type != "User":
        raise GateError(f"{label}.account_type must be User")
    return Identity(login, account_type)


def load_policy(path: Path) -> Policy:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateError(f"cannot read strict review policy: {error}") from error
    data = _object(
        raw,
        "policy",
        {"version", "repository", "owner_review", "required_reviewer"},
    )
    if type(data["version"]) is not int or data["version"] != 1:
        raise GateError("policy.version must be integer 1")
    repository = data["repository"]
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise GateError("policy.repository is invalid")
    owner = _identity(data["owner_review"], "policy.owner_review")
    reviewer_raw = data["required_reviewer"]
    reviewer: Reviewer | None = None
    if reviewer_raw is not None:
        item = _object(
            reviewer_raw,
            "policy.required_reviewer",
            {"login", "account_type", "minimum_permission", "security_qualified"},
        )
        identity = _identity(
            {"login": item["login"], "account_type": item["account_type"]},
            "policy.required_reviewer",
        )
        permission = item["minimum_permission"]
        if not isinstance(permission, str) or permission not in {
            "write",
            "maintain",
            "admin",
        }:
            raise GateError("required reviewer permission must be write, maintain, or admin")
        if item["security_qualified"] is not True:
            raise GateError("required_reviewer.security_qualified must be true")
        assert identity is not None
        reviewer = Reviewer(
            identity.login,
            identity.account_type,
            permission,
            item["security_qualified"],
        )
    return Policy(repository, owner, reviewer)


class GitHub:
    """Small fail-closed GitHub REST client with bounded pagination."""

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise GateError("REVIEW_GATE_TOKEN is required")
        parsed = urllib.parse.urlsplit(api_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise GateError("GITHUB_API_URL must be an HTTPS origin")
        self.token = token
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.base = api_url.rstrip("/")

    def request(self, path: str, *, method: str = "GET", body: Any = None) -> tuple[Any, dict[str, str]]:
        url = path if path.startswith("https://") else self.base + path
        parsed = urllib.parse.urlsplit(url)
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin:
            raise GateError("GitHub pagination attempted to leave the configured API origin")
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "park-owner-review-gate/1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, {key.lower(): value for key, value in response.headers.items()}
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GateError(f"GitHub API request failed for {parsed.path}: {error}") from error

    def get(self, path: str) -> Any:
        return self.request(path)[0]

    def pages(self, path: str) -> list[Any]:
        results: list[Any] = []
        next_url: str | None = path
        seen: set[str] = set()
        for _ in range(100):
            if next_url is None or next_url in seen:
                if next_url in seen:
                    raise GateError("GitHub pagination loop detected")
                return results
            seen.add(next_url)
            payload, headers = self.request(next_url)
            if not isinstance(payload, list):
                raise GateError("paginated GitHub response was not a list")
            results.extend(payload)
            next_url = _next_link(headers.get("link", ""))
        raise GateError("GitHub pagination exceeded 100 pages")

    def post(self, path: str, body: Any) -> Any:
        return self.request(path, method="POST", body=body)[0]

    def patch(self, path: str, body: Any) -> Any:
        return self.request(path, method="PATCH", body=body)[0]


def _next_link(header: str) -> str | None:
    for item in header.split(","):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="([^"]+)"\s*', item)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"live {label} response is malformed")
    return value


def _positive_number(value: Any, label: str, *, allow_string: bool = False) -> int:
    if type(value) is int and value > 0:
        return value
    if allow_string and isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    raise GateError(f"{label} must be a positive integer")


def _dispatch_number(event: dict[str, Any]) -> int:
    inputs = event.get("inputs")
    if not isinstance(inputs, dict):
        raise GateError("workflow_dispatch inputs are malformed")
    return _positive_number(
        inputs.get("pr_number"),
        "workflow_dispatch pr_number",
        allow_string=True,
    )


def _event_target(event: dict[str, Any]) -> Target | None:
    """Locate a PR for an early pessimistic check without authorizing it."""
    name = os.environ.get("GITHUB_EVENT_NAME")
    if name == "workflow_dispatch":
        return Target(_dispatch_number(event), None)
    if name != "workflow_run":
        raise GateError("unsupported workflow event")
    run = event.get("workflow_run")
    if not isinstance(run, dict) or type(run.get("id")) is not int:
        raise GateError("workflow_run id is missing or invalid")
    pulls = run.get("pull_requests")
    if not isinstance(pulls, list):
        raise GateError("workflow event PR association is malformed")
    if not pulls and run.get("event") == "push":
        return None
    if len(pulls) != 1 or not isinstance(pulls[0], dict):
        raise GateError("workflow event does not identify exactly one PR")
    number = _positive_number(pulls[0].get("number"), "workflow event PR number")
    try:
        head_sha = pulls[0]["head"]["sha"]
    except (KeyError, TypeError) as error:
        raise GateError("workflow event PR head SHA is missing") from error
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise GateError("workflow event PR head SHA is invalid")
    return Target(number, head_sha)


def fetch_pull(client: Any, repository: str, number: int) -> Pull:
    data = _dict(client.get(f"/repos/{repository}/pulls/{number}"), "pull request")
    try:
        actual_number = data["number"]
        head_sha = data["head"]["sha"]
        author = data["user"]["login"]
        state = data["state"]
        base_repository = data["base"]["repo"]["full_name"]
    except (KeyError, TypeError) as error:
        raise GateError("live pull request response is incomplete") from error
    if type(actual_number) is not int or actual_number != number:
        raise GateError("live pull request number does not match the requested PR")
    if (
        not isinstance(base_repository, str)
        or base_repository.casefold() != repository.casefold()
    ):
        raise GateError("pull request belongs to a different base repository")
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise GateError("pull request head SHA is invalid")
    if not isinstance(author, str) or not LOGIN.fullmatch(author):
        raise GateError("pull request author is invalid")
    if state != "open":
        raise GateError("pull request is not open")
    return Pull(number, head_sha, author, state)


def _account_type(client: Any, login: str) -> str:
    data = _dict(client.get(f"/users/{urllib.parse.quote(login)}"), "account")
    if not isinstance(data.get("login"), str) or data["login"].casefold() != login.casefold():
        raise GateError(f"account lookup did not resolve {login}")
    account_type = data.get("type")
    if not isinstance(account_type, str):
        raise GateError(f"account type for {login} is missing")
    return account_type


def _permission(client: Any, repository: str, login: str) -> str:
    quoted = urllib.parse.quote(login)
    data = _dict(
        client.get(f"/repos/{repository}/collaborators/{quoted}/permission"),
        "collaborator permission",
    )
    candidates = [data.get("permission"), data.get("role_name")]
    valid = [
        value
        for value in candidates
        if isinstance(value, str) and value in PERMISSION_RANK
    ]
    if not valid:
        raise GateError(f"collaborator permission for {login} is invalid")
    return max(valid, key=PERMISSION_RANK.__getitem__)


def evaluate_pull(
    client: Any,
    policy: Policy,
    pull: Pull,
    *,
    expected_head: str | None = None,
) -> Decision:
    owner, reviewer = policy.owner_review, policy.required_reviewer
    if owner is None or reviewer is None:
        raise GateError("review policy is unconfigured; set owner and reviewer explicitly")
    if expected_head is not None and expected_head != pull.head_sha:
        raise GateError("triggering Repository contract run is not for the live PR head")

    owner_authored = pull.author.casefold() == owner.login.casefold()
    if owner_authored:
        author_type = _account_type(client, pull.author)
        if author_type != owner.account_type:
            raise GateError("owner exception requires the configured User account type")
        decision = Decision(
            True,
            "Owner-reviewed policy satisfied",
            "The live author is the configured User owner. This is owner-reviewed, not "
            "independent human review; account authorship does not prove manual inspection.",
        )
    else:
        reviewer_type = _account_type(client, reviewer.login)
        if reviewer_type != reviewer.account_type:
            raise GateError("designated reviewer is not the configured User account type")
        permission = _permission(client, policy.repository, reviewer.login)
        if PERMISSION_RANK[permission] < PERMISSION_RANK[reviewer.minimum_permission]:
            raise GateError("designated reviewer lacks the configured repository permission")
        if reviewer.login.casefold() == pull.author.casefold():
            raise GateError("a PR author cannot satisfy the required approval with the same account")
        reviews = client.pages(
            f"/repos/{policy.repository}/pulls/{pull.number}/reviews?per_page=100"
        )
        latest: tuple[int, str, str | None] | None = None
        for review in reviews:
            item = _dict(review, "review")
            try:
                review_id = item["id"]
                login = item["user"]["login"]
                state = item["state"]
            except (KeyError, TypeError) as error:
                raise GateError("live review response is incomplete") from error
            if (
                type(review_id) is not int
                or not isinstance(login, str)
                or not LOGIN.fullmatch(login)
                or not isinstance(state, str)
            ):
                raise GateError("live review response has invalid field types")
            state = state.upper()
            if state not in DECISIVE_STATES | {"COMMENTED", "PENDING"}:
                raise GateError(f"live review has unsupported state {state!r}")
            if (
                login.casefold() != reviewer.login.casefold()
                or state in {"COMMENTED", "PENDING"}
            ):
                continue
            commit_id = item.get("commit_id")
            if commit_id is not None and (
                not isinstance(commit_id, str) or not SHA.fullmatch(commit_id)
            ):
                raise GateError("live review commit_id is invalid")
            candidate = (review_id, state, commit_id)
            if latest is None or candidate[0] > latest[0]:
                latest = candidate
        if latest is None:
            decision = Decision(
                False,
                "Required approval missing",
                "No decisive review from the designated reviewer is active.",
            )
        elif latest[1] == "CHANGES_REQUESTED":
            decision = Decision(
                False,
                "Changes requested",
                "The designated reviewer's latest decisive review requests changes.",
            )
        elif latest[1] == "DISMISSED":
            decision = Decision(
                False,
                "Approval dismissed",
                "The designated reviewer's latest decisive review was dismissed.",
            )
        elif latest[2] != pull.head_sha:
            decision = Decision(
                False,
                "Approval is stale",
                "The designated approval is not bound to the live PR head SHA.",
            )
        else:
            decision = Decision(
                True,
                "Exact-head approval verified",
                "The designated User reviewer has sufficient live permission and approved "
                "the current head SHA.",
            )

    final_pull = fetch_pull(client, policy.repository, pull.number)
    if final_pull.head_sha != pull.head_sha or final_pull.author.casefold() != pull.author.casefold():
        raise GateError("pull request head or author changed during evaluation")
    return decision


def _workflow_trigger(client: GitHub, event: dict[str, Any], repository: str) -> tuple[int | None, str | None]:
    name = os.environ.get("GITHUB_EVENT_NAME")
    if name == "workflow_dispatch":
        return _dispatch_number(event), None
    if name != "workflow_run":
        raise GateError("unsupported workflow event")
    try:
        run_id = event["workflow_run"]["id"]
    except (KeyError, TypeError) as error:
        raise GateError("workflow_run id is missing") from error
    if type(run_id) is not int:
        raise GateError("workflow_run id is invalid")
    run = _dict(client.get(f"/repos/{repository}/actions/runs/{run_id}"), "workflow run")
    allowed = {
        "Repository contract": (
            {"pull_request", "push"},
            ".github/workflows/repository-contract.yml",
        ),
        "Review event notification": (
            {"pull_request_review"},
            ".github/workflows/review-event-notification.yml",
        ),
    }
    run_name = run.get("name")
    if run_name not in allowed:
        raise GateError("live triggering workflow is not allowlisted")
    expected_events, expected_path = allowed[run_name]
    path = run.get("path")
    if not isinstance(path, str):
        raise GateError("live triggering workflow path is invalid")
    path = path.split("@", 1)[0]
    if (
        run.get("status") != "completed"
        or run.get("event") not in expected_events
        or path != expected_path
    ):
        raise GateError("live triggering workflow identity is invalid")
    if run_name == "Repository contract" and run.get("event") == "push":
        return None, None
    pulls = run.get("pull_requests")
    if (
        not isinstance(pulls, list)
        or len(pulls) != 1
        or not isinstance(pulls[0], dict)
        or type(pulls[0].get("number")) is not int
        or pulls[0]["number"] < 1
    ):
        raise GateError("live triggering workflow does not identify exactly one PR")
    expected_head = run.get("head_sha") if run_name == "Repository contract" else None
    if expected_head is not None and (not isinstance(expected_head, str) or not SHA.fullmatch(expected_head)):
        raise GateError("live triggering workflow head SHA is invalid")
    return pulls[0]["number"], expected_head


def _check(client: GitHub, repository: str, head_sha: str) -> int:
    data = _dict(
        client.post(
            f"/repos/{repository}/check-runs",
            {"name": "Owner review gate", "head_sha": head_sha, "status": "in_progress"},
        ),
        "check run",
    )
    if type(data.get("id")) is not int:
        raise GateError("created check run has no valid id")
    return data["id"]


def _finish(client: GitHub, repository: str, check_id: int, conclusion: str, decision: Decision) -> None:
    client.patch(
        f"/repos/{repository}/check-runs/{check_id}",
        {
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": decision.title, "summary": decision.summary},
        },
    )


def main() -> int:
    checks: dict[str, int] = {}
    client: GitHub | None = None
    repository = ""
    try:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not REPOSITORY.fullmatch(repository):
            raise GateError("GITHUB_REPOSITORY is invalid")
        event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
        event = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise GateError("workflow event is malformed")
        client = GitHub(
            os.environ.get("REVIEW_GATE_TOKEN", ""),
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        )
        target = _event_target(event)
        if target is not None and target.head_sha is not None:
            checks[target.head_sha] = _check(client, repository, target.head_sha)

        policy = load_policy(ROOT / ".github" / "review-policy.json")
        if repository.casefold() != policy.repository.casefold():
            raise GateError("GITHUB_REPOSITORY does not match the trusted policy")
        number, expected_head = _workflow_trigger(client, event, repository)
        if number is None:
            if target is not None:
                raise GateError("live workflow has no PR but the event identified one")
            print("No pull request is associated with this default-branch run.")
            return 0
        pull = fetch_pull(client, repository, number)
        if pull.head_sha not in checks:
            checks[pull.head_sha] = _check(client, repository, pull.head_sha)
        if target is None or target.number != number:
            raise GateError("event and live workflow identify different pull requests")
        if target.head_sha is not None and target.head_sha != pull.head_sha:
            raise GateError("event locator is not for the live PR head")
        decision = evaluate_pull(client, policy, pull, expected_head=expected_head)
        _finish(
            client,
            repository,
            checks[pull.head_sha],
            "success" if decision.allowed else "failure",
            decision,
        )
        print(f"PR #{number} at {pull.head_sha}: {decision.title}")
        return 0 if decision.allowed else 1
    except (GateError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        failure = Decision(False, "Review gate failed closed", str(error))
        if client is not None and REPOSITORY.fullmatch(repository):
            for check_id in checks.values():
                try:
                    _finish(client, repository, check_id, "failure", failure)
                except GateError as finish_error:
                    print(
                        f"error: could not conclude exact-head check: {finish_error}",
                        file=sys.stderr,
                    )
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# Owner-review policy and GitHub activation

PARK uses a repository-specific owner-review policy. The trusted configuration is
`.github/review-policy.json`; the executable gate is
`scripts/ci/review_gate.py` from the default branch.

## PARK policy

For `sodejm/portable-agent-repository-kit`:

- a pull request whose live author is the `sodejm` account of GitHub type `User`
  is **owner-reviewed**, including when an agent uses that account;
- owner-reviewed does not mean independent human review, and account authorship
  cannot prove that a person manually inspected the change;
- a pull request by any other author requires the latest decisive review from
  `sodejm` to be `APPROVED` on the current head commit;
- for that other-author path, `sodejm` must resolve live as a `User` collaborator
  with `write`, `maintain`, or `admin` permission. Comments do not replace an
  approval, while a later changes-requested or dismissed review invalidates it;
- `sodejm` is the owner-designated qualified human reviewer for security-sensitive
  changes. That designation is a governance decision, not evidence that a review
  happened.

Keep every PR in draft until `sodejm` chooses to mark it ready, review it, or merge
it. Agents do not infer those choices from a passing check. The policy has no
bypass actors and grants no permission to push, publish, merge, or release.

## Trusted check design

`Repository contract` is the workflow display name. Its emitted required status
check context is `validate`, and that job validates PR code with a read-only token.
A minimal `Review event notification` workflow runs for submitted, edited, and
dismissed reviews with no repository permissions. Completion of either workflow
triggers `Owner review gate`, whose definition and Python evaluator are checked
out only from the repository's default branch. A maintainer can also recover a
missed or failed notification with its `workflow_dispatch` PR-number input.

The gate does not run PR code and does not download artifacts or caches. With the
least privileges needed to read Actions, repository contents, pull requests, and
write a check, it fetches the live workflow run, PR, head SHA, account types,
collaborator permission, and all review pages. It rejects malformed configuration,
API failures, ambiguous workflow-to-PR association, stale or dismissed approvals,
unauthorized or bot approvals, same-author approval outside the owner exception,
and a head or author change observed during evaluation. It writes `Owner review
gate` directly to the evaluated head SHA. For an associated workflow-run event, it
first writes a fresh in-progress check to the event-located head, then uses only
independent live API reads to authorize success. A failure while reading the live
workflow or PR therefore concludes that fresh check as failed instead of leaving a
previous success as the newest result.

The configuration deliberately has no bypass list. Generated projects receive a
repository-specific copy with both identities set to `null`; their gate therefore
fails closed until that project's owner explicitly chooses and records a policy.
Generated projects do not inherit `sodejm` as owner or reviewer.

## Bootstrap and required GitHub settings

The custom check cannot safely be required before its workflow and evaluator are
present on the protected default branch. Until then, require `validate` and keep
this change's PR in draft. Merge the trusted implementation only through the
repository's existing authorized bootstrap process; do not add a temporary bypass.

After that merge, open a disposable draft PR and let `Repository contract`
complete. Its completion should trigger `Owner review gate`. If recovery is
needed, trigger `Owner review gate` manually with that open PR's number. Do not use
a closed or merged PR: the gate intentionally requires live PR state to be open.
Confirm that the open PR emits both required contexts, `validate` and `Owner review
gate`, before configuring them as required.

An administrator should then configure the default branch or its ruleset as
follows, preserving every stricter existing protection:

1. Require a pull request before merging, require conversation resolution, and set
   the native required-approval count to **zero**. GitHub cannot express this
   conditional author policy with its native approval count; a nonzero count would
   contradict the owner exception.
2. Require `validate` and `Owner review gate` to pass before merging.
   When GitHub offers a source-app binding, bind both checks to GitHub Actions.
3. Apply the rules to administrators, leave the bypass list empty, block direct
   pushes to the default branch, and disallow force pushes and branch deletion.
4. Do not enable merge until required checks and conversation resolution are
   satisfied. Keep the PR draft until the owner makes the review/merge decision.

Read the settings back in GitHub and verify all of the following: the exact check
names `validate` and `Owner review gate` are required; the required approval count
is zero; conversation resolution and pull requests are required; administrators
are covered; bypass actors are empty; force pushes and deletion are disabled. On
open draft PRs, also verify that an owner-authored draft reports owner-reviewed,
an external-author draft without a current `sodejm` approval fails, and a review
edit or dismissal starts a fresh notification and gate run. Record screenshots or
API responses in private administrative evidence without tokens. Source files
alone do not prove that these hosted settings are active.

## Limits and recovery

GitHub may briefly change review state after the gate's last live read but before
a merge. A head change is safer because the success check remains attached to the
old SHA. A review edit or dismissal retriggers evaluation, which pessimistically
refreshes the event-located exact-head check before its live authorization reads.
There is still a delivery window before that event starts, and a malformed event
that cannot identify exactly one PR and head cannot be refreshed automatically.
Workflow dispatch is the recovery path if association or delivery fails.
Conversation resolution is enforced by the native rule, not by this evaluator.

A required check name can be imitated if its source app is not bound, or by another
trusted workflow with equivalent `checks: write` authority. Protect the default
branch, restrict workflow changes, bind the required check source where supported,
and review every workflow with write authority. A compromised maintainer account
or default-branch workflow remains inside this repository's ultimate authority
boundary.

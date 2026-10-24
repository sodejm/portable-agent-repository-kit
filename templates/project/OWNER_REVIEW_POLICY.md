# Project review policy setup

This generated repository has no configured owner exception or designated
reviewer. `.github/review-policy.json` intentionally contains `null` identities,
so `Owner review gate` fails closed. No PARK account identity or review decision is
inherited.

Before relying on the gate, the new project owner must explicitly choose its own
policy. Set `repository` to the exact `owner/name`, and set both identity objects
only after recording the governance decision. The owner and reviewer must be
GitHub accounts of type `User`; the reviewer needs `write`, `maintain`, or `admin`
permission. Set `security_qualified` to `true` only after the owner designates that
person as qualified for security-sensitive changes. Do not add bypass actors.

Use a draft PR for setup. Merge the trusted workflow, evaluator, and configuration
to the default branch through an authorized bootstrap process before requiring the
custom check. `Repository contract` is the workflow display name; its emitted
required status check context is `validate`. After bootstrap, use an open
disposable draft PR to emit and verify `validate` and `Owner review gate`; do not
test the gate with a closed or merged PR. Then configure GitHub to require pull
requests, conversation resolution, `validate`, and `Owner review gate`; use a
native required approval count of zero only if the project explicitly adopts the
conditional owner exception. Cover administrators, keep bypass actors empty,
block direct default-branch pushes, and disallow force pushes and branch deletion.
Read every setting back after activation. Source files do not prove hosted
enforcement.

The gate evaluates live exact-head state but cannot eliminate the short race after
its final read, and an unbound check name can be imitated by another check writer.
Bind required checks to GitHub Actions where supported and restrict workflow
changes. Adapt and expand this document to the project's actual governance before
changing the fail-closed configuration.

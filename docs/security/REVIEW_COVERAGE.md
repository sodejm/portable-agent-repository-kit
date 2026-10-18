# Existing-code human review coverage

Baseline commit: `bfc41923fb497b495e95dc7dee644313b51b368b`. Status: initial inventory; no completed human
review is asserted. Scope includes all tracked first-party code, infrastructure,
CI, agent instructions and build/release tooling, including paths outside the
subsystem rows below. The maintainer must expand rows to exact file inventories;
these subsystem entries are prioritization, not proof of exhaustive review.

| ID | Scope | Status | Human owner | Deadline |
| --- | --- | --- | --- | --- |
| R1 | Source template → copy → destination and all implementing code/configuration/tests | Pending independent human review | Maintainer assignment pending | Before affected release; triage within 30 days, first pass within 90 days |
| R2 | Project parameters → token rendering / license → generated repository and all implementing code/configuration/tests | Pending independent human review | Maintainer assignment pending | Before affected release; triage within 30 days, first pass within 90 days |
| R3 | Canonical skills → Claude/other adapters → agent runtime and all implementing code/configuration/tests | Pending independent human review | Maintainer assignment pending | Before affected release; triage within 30 days, first pass within 90 days |
| R4 | Generated repo → future project code / deployment and all implementing code/configuration/tests | Pending independent human review | Maintainer assignment pending | Before affected release; triage within 30 days, first pass within 90 days |
| R-CI | All CI, dependencies, packaging, release, scripts and agent/tool authority | Pending independent human review | Maintainer assignment pending | Before affected release; triage within 30 days, first pass within 90 days |
| R-REST | All remaining tracked first-party files; enumerate and reconcile against Git inventory | Pending independent human review | Maintainer assignment pending | First pass within 90 days |

For each reviewed row add exact paths, reviewed SHA, reviewer identity/date,
checks/evidence, findings, disposition, residual risk acceptance/expiry and next
review trigger. Record third-party provenance and review separately. Changed
behavior invalidates prior scope approval. Follow the
[engineering review policy](../ENGINEERING_REVIEW.md). No automated result or
threat-model entry closes this human-review backlog.

## Goblin Council contribution

Pending independent human review: `extensions/goblin-council/**`,
`scripts/agent/check.py`, `tests/test_template.py`, and related documentation.
Review installer ownership checks, model routes, sandbox probes, snapshot and
promotion logic, recovery, and generated-project isolation at the exact proposed
commit. Owner: maintainer assignment pending; deadline: before affected release.
Local automated checks do not close this review.

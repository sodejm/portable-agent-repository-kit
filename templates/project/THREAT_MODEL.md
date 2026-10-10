# {{PROJECT_NAME}} threat model

## Status and scope

Architecture inventory pending. Independent human security review pending.
This generated scaffold is not a completed threat model or evidence of inherited
controls. Before the first substantial behavior change or release, replace every
pending section with project-specific source evidence and human owners.

## System decomposition

Document supported and unsupported operating modes, actors and attacker goals,
sensitive assets and retention/deletion, components, entry points, data-flow diagram,
trust boundaries, privileges and external recipients. Identify effective filesystem
paths, execution arguments, network endpoints and credential recipients.

## Threat register

| ID | Asset and abuse path / prerequisite | STRIDE category | Impact / likelihood / priority | Existing control and source evidence | Proposed mitigation and validation | Residual risk | Human owner / due date / status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | Architecture inventory pending | Pending decomposition | Pending assessment | No project-specific control established | Complete source-based architecture and negative-test plan | Unknown | Maintainer assignment pending; before first behavior change/release |

Analyze spoofing, tampering, repudiation, information disclosure, denial of service,
elevation of privilege, privacy, dependencies and build/distribution threats. State
impact/likelihood criteria. Separate implemented controls from proposals. Record
inapplicable surfaces with reasons, and never mark an untested control effective.

## Operations and validation

Inventory authorization, secret rotation, input/resource limits, isolation, logging
and monitoring, incident response, backup/restore and deployment assumptions.
Map each applicable high-risk control to reproducible synthetic tests and human
review; record live evidence separately. No risk is accepted by this scaffold.

## Maintenance and approval

Update in the same change as security-relevant code/config/dependency changes;
otherwise record a specific no-impact rationale. Reconcile each release and
quarterly. Record baseline SHA, human reviewer/date, reviewed SHA, outcomes,
remaining risks and next review date. Follow `docs/ENGINEERING_REVIEW.md`
and `docs/security/REVIEW_COVERAGE.md`.

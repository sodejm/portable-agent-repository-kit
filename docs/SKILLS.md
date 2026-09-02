# Skills

## Canonical location and format

Author reusable project workflows under `.agents/skills/<skill-name>/SKILL.md`.
Each file begins with:

```yaml
---
name: skill-name
description: A precise statement of when the skill should be used.
---
```

Keep the entrypoint focused. Put large examples, reference material, or helper
scripts beside it and load them only when needed. A skill should describe a bounded
workflow, evidence expectations, and safety boundaries—not repeat `AGENTS.md`.

Run `make sync-agent-adapters` after a skill change. PARK copies canonical skill
entrypoints to `.claude/skills/` for environments that do not discover the open
location. Do not edit generated copies.

## Included baseline

- `repository-orientation`: safe startup in an unfamiliar checkout.
- `repository-check`: deterministic validation and evidence reporting.
- `github-state-audit`: focused, read-only hosted-state inspection.
- `repository-delivery-gate`: readiness without conflating delivery states.
- `resumable-worktree-run`: isolated, recoverable issue-sized work.
- `gitignore-audit`: narrow evidence-based ignore recommendations.
- `security-review`: generic defensive change review.
- `documentation-impact`: documentation mapping and validation.

## PARK-source workflow

- `template-project-creator`: creates a new state-0 project from an
  unconfigured PARK checkout with `scripts/create_project.py`. It is intentionally
  removed during generation: a generated project has no project-generator script,
  so retaining the skill there would advertise an unavailable workflow.

## Global-skill selection rationale

PARK carries reusable ideas from a broader personal skill set but intentionally
does not copy machine- or account-level automation.

| Global pattern | PARK treatment | Reason |
| --- | --- | --- |
| GitHub state audit | included, rewritten | Generic, read-only, and portable |
| Delivery gate | included, rewritten | Durable evidence and lifecycle discipline |
| Resumable worktrees | included, simplified | Useful Git primitive; proprietary coordination removed |
| `.gitignore` audit | included, simplified | Generic and safe |
| GitHub workflow guard | principles in `AGENTS.md` and skills | Avoid standing remote-write authority in a public template |
| GitHub authentication guard | excluded | Machine/account hook, not repository policy |
| Model router and issue model recommender | excluded | Vendor catalog and account specific |
| Agent workboard | excluded from baseline | Runtime-specific coordination and local database state |
| Issue prioritizer | excluded | Optional live-service workflow, not every project's baseline |
| Product/repository-specific skills | excluded | Not generic |
| Installed plugin skills | excluded | Plugin licensing, versioning, and runtime remain external |

Projects may add optional skills after reviewing their license, provenance,
permissions, maintenance model, and whether repository-level sharing is appropriate.

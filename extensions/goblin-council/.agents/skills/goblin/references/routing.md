# Routing and contracts

Score each dimension 0–3 from inspected code and the acceptance contract.
Use the highest matching level, counting planned implementation and test files.
A module means a separately owned package or component; public API/schema changes
receive blast 3 even when confined to one file.

| Score | Reasoning depth | Blast radius | Ambiguity | Security/concurrency risk |
|---|---|---|---|---|
| 0 | Mechanical substitution | 1 file | Exact acceptance criteria | No behavior or trust boundary change |
| 1 | Local logic with established pattern | 2–3 files in 1 module | Resolved by existing conventions | Ordinary validation/error handling |
| 2 | Cross-component invariants or multi-step reasoning | 4–10 files or 2 modules | Consequential alternatives with sufficient acceptance criteria | Auth, untrusted inputs, shared state, shared-state retry/transaction logic |
| 3 | Architecture change or difficult correctness argument | More than 10 files, more than 2 modules, or public API/schema | Missing acceptance criteria that prevent safe implementation | Privilege/secrets, destructive data changes, or critical concurrency |

Apply these rules in order:

1. Ambiguity 3: BLOCKED pending clarification, in either mode.
2. Explicit max: CRITIQUE if any score is at least 2, otherwise CASCADE.
3. Standard: CRITIQUE if risk >= 2, depth == 3, blast == 3, or at least two scores >= 2.
4. Standard: SINGLE if all scores <= 1 and their sum <= 3.
5. Otherwise CASCADE.

These thresholds are initial policy, not a measured cost/latency optimum. Use
recorded stage durations and defects to tune them after representative runs.

| Role | Standard default | Max | Escalation |
|---|---|---|---|
| Primary Single | Current session, low/medium | Prohibited | Reclassify if scope changes |
| goblin-drafter | gpt-5.6-luna/medium for all scores <=1, otherwise gpt-5.6-terra/medium | gpt-5.6-terra/high | gpt-5.6-sol/high |
| goblin-judge | gpt-5.6-terra/medium | gpt-5.6-terra/high | Final repair gate: gpt-5.6-sol/high |
| goblin-critic-arch | gpt-5.6-sol/high | gpt-5.6-sol/high | No nested escalation |
| goblin-critic-sec | gpt-5.6-sol/high | gpt-5.6-sol/high | No nested escalation |

Risk >=2, depth 3, or blast 3 selects sol/high for every stage. Model IDs must be
confirmed in the native cache at launch. These are the currently implemented GPT-5.6 routes, not claims about the
newest available model. Other models require explicit routing and validation changes.

## Bounded workflows

- Single: classify → primary edit → appropriate verification → report.
- Cascade: snapshot → draft → freeze → validate → judge. PASS plus validation
  permits promotion. ESCALATE or validation failure permits one sol/high repair,
  then a new freeze, validation, and sol/high judge. Further failure is REJECTED.
- Critique: snapshot → draft → freeze → validate → architecture and security
  critics in parallel on the same immutable candidate → one sol/high synthesized
  revision → new freeze → validate → sol/high final judge → promote or REJECTED.
  Critics never see each other's initial report. A no-defect revision may be a
  documented no-op. A required restart uses the original snapshot, not a fresh
  snapshot of a potentially changed primary checkout.

## Handoff

Task input: objective, scope, acceptance, four scores, routing_basis, validation,
and an explicit no_tests_reason only when validation is empty. The coordinator
adds mode, workspace, baseline/candidate commits, candidate_id, patch path, phase,
and only the reports needed for that phase.

Writer output: short CHANGES, CHECKS, UNRESOLVED, RESTART_REQUIRED report.
Reviewer output: strict [JSON schema](review.schema.json), including exact
candidate_id, verdict PASS/ESCALATE, defects, repair_plan, restart_required.
A PASS containing a blocking finding or restart request is invalid. Stale reports
cannot promote a later candidate. The actual diff and check results take
precedence over summaries.

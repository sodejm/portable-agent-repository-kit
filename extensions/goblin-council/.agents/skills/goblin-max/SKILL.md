---
name: goblin-max
description: Use only when the user explicitly requests goblin-max or Goblin Council max mode. Requires Cascade or parallel Critique and high reasoning effort throughout.
---

# Goblin Council Max

Read and follow [the Goblin Council skill](../goblin/SKILL.md), including local
policies, task classification, isolation, verification, and recovery.

Set `--mode max`. Never select Single. Route any dimension scored 2 or higher to
Critique; otherwise use Cascade. Acceptance-blocking ambiguity still requires
clarification. Every model stage uses high reasoning effort. The repair budget
remains one pass; max does not permit unbounded retries or automatic permission
escalation. Never activate this mode merely because standard mode failed.

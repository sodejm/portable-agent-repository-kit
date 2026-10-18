---
name: goblin
description: Use Goblin Council when the user requests goblin, goblin council, or bounded multi-model drafting and review. Routes to Single, Cascade, or independent parallel Critique while preserving the primary Git workspace.
---

# Goblin Council

Tell the user you are using this skill. Default to standard mode. Use max only
when explicitly requested through `$goblin-max` or equivalent language.

1. Read applicable AGENTS.md and workflow policies. This skill does not override
   them. Read [routing.md](references/routing.md), inspect the task, and assign
   the four scores with a short evidence-based rationale. Resolve acceptance-
   blocking ambiguity before drafting. Reclassify if scope grows.
2. Locate Python 3.11+ and the native Codex CLI. Resolve `scripts/council.py`
   relative to this skill file, not the shell working directory. Keep the whole
   package layout intact: the helper loads roles from `.codex/agents` beside
   `.agents`. Review the repository's existing config before installation.
3. Write a task JSON outside the target checkout (a private temporary file is
   suitable). Include objective, scope (paths), acceptance (criteria), depth,
   blast, ambiguity, risk, routing_basis, and validation (arrays of executable
   plus arguments). Use absolute executable paths when environment setup needs
   them. For a documentation-only change, validation may be empty with a concrete
   no_tests_reason. Never use that exception to bypass required checks.
4. Run `python3 /absolute/package/.agents/skills/goblin/scripts/council.py
   --repo /absolute/target run --task /absolute/task.json --mode standard`.
   Use `--mode max` only for explicit max requests. The helper fails if its
   selected model/effort is absent from the local native model catalog. Refresh
   the catalog or propose a route change; do not silently substitute.
5. If the result is SINGLE, perform the task directly in the primary thread at
   low effort for a mechanical change, medium otherwise, then verify it. The
   helper intentionally does not edit anything on the Single route. A skill
   cannot force a current session's model/effort setting: report a mismatch and
   use an available supported session control, never claim to have changed it.
6. For Cascade/Critique, let the helper own the transaction and promotion. Do not
   launch overlapping writers, edit the primary checkout, manually apply an
   unreviewed patch, or substitute a prompt-only read-only instruction. These
   stages are separate native `codex exec` sessions with enforced permissions;
   native spawned agents inherit their parent's sandbox and cannot provide this
   per-role separation. The supplied TOMLs also document the roles, but do not
   make ordinary spawned critics read-only. Stage sessions cannot delegate.
7. Respect any policy covering model launches. This helper does not call
   `spawn_agent`; if you separately use that tool, complete its required router,
   workboard, and launch evidence first. Never use this helper to bypass a policy
   that applies to all delegation or model execution.
8. Report topology, models/efforts, checks, promotion status, and trace path.
   A rejected/interrupted run remains isolated for inspection. Use `recover`,
   `status RUN_ID`, and then `abandon RUN_ID` only for that inactive run. Do not
   run global garbage collection or install an unconditional Stop cleanup hook.

The helper limits repair to one high-effort pass. Critique uses two independent
read-only critics, one synthesized revision, and a final read-only judge. Review
and validation must refer to the exact frozen candidate before promotion.

Read the package README for setup, known limits, and crash recovery. A model
verdict is evidence, not proof; the coordinator enforces state and test gates.

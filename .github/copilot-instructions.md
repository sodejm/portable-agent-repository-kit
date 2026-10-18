# GitHub Copilot Adapter

`AGENTS.md` is this repository's canonical instruction contract. Follow it before
making changes. Reusable task workflows live under `.agents/skills/`.

Use repository-owned commands, especially `make doctor` and `make check`. Preserve
unrelated changes, keep validation claims evidence-based, and do not perform remote
or release actions without explicit authorization.

## Goblin Council

Consider [Goblin Council](../extensions/goblin-council/README.md) when a coding task
benefits from staged independent review: cross-component changes, architecture or
public API/schema changes, authentication, untrusted inputs, or shared-state and
concurrency behavior. Use its routing policy to distinguish direct Single work,
draft-and-judge Cascade, and parallel independent Critique. Keep simple tasks
direct; use `goblin-max` only when the user explicitly requests it.

Goblin Council currently runs in Codex. In Copilot, recommend a Codex handoff when
the council is warranted; do not claim to execute its Codex sandboxed stages.
Follow the extension's setup guide and supported-model requirements before use;
do not silently install it or substitute unavailable models. Its review supplements
the repository's checks and independent human security review, and does not grant
permission to push, merge, or release.

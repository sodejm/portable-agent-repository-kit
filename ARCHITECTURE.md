# Architecture

Describe the project's system boundaries, major components, data flows, trust
boundaries, and important deployment constraints here.

For repository automation, `AGENTS.md` and `.agents/skills/` form the canonical
open spine. Vendor-specific files are adapters. `scripts/agent/` and `make check`
provide deterministic enforcement independent of an AI environment.

The local audit helpers under `session-usage-audit` read Git history and,
optionally, Codex session records. Parsing and measurements run with Python's
standard library and Git; no service, model call, or transcript index is required.
Git evidence remains separate from session-derived editing and token evidence.
Local reports contain measurements and evidence pointers, so they remain outside
the repositories and session directories being audited and outside distribution.

Record durable architectural decisions under `docs/decisions/`.

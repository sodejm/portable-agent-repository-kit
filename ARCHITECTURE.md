# Architecture

Describe the project's system boundaries, major components, data flows, trust
boundaries, and important deployment constraints here.

For repository automation, `AGENTS.md` and `.agents/skills/` form the canonical
open spine. Vendor-specific files are adapters. `scripts/agent/` and `make check`
provide deterministic enforcement independent of an AI environment.

Record durable architectural decisions under `docs/decisions/`.

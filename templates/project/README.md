# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Repository contract

This repository was initialized with [PARK — Portable Agent Repository Kit](https://github.com/sodejm/portable-agent-repository-kit).
Its portable agent contract is rooted in `AGENTS.md`, its canonical reusable skills
live under `.agents/skills/`, and environment-specific files are intentionally thin
adapters.

Start with [AGENTS.md](AGENTS.md) and the [documentation index](docs/INDEX.md).

## Local validation

```bash
make doctor
make check
```

The baseline checks use Python's standard library and Git. Add project-specific
commands to the root `AGENTS.md`, `Makefile`, and CI workflow as the implementation
evolves.

## Development

1. Read the repository contract and relevant documentation.
2. Work in a focused branch or isolated worktree.
3. Keep canonical skills in `.agents/skills/` and run
   `make sync-agent-adapters` after changing them.
4. Run `make check` before delivery.
5. Record validation evidence and any residual risk in the pull request.

## Security

See [SECURITY.md](SECURITY.md) for reporting guidance and
[docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for the baseline agent threat model.

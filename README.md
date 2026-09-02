# PARK — Portable Agent Repository Kit

[![Repository contract](https://github.com/sodejm/portable-agent-repository-kit/actions/workflows/repository-contract.yml/badge.svg?branch=main)](https://github.com/sodejm/portable-agent-repository-kit/actions/workflows/repository-contract.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Use this template](https://img.shields.io/badge/use_this-template-2ea44f)](https://github.com/new?template_name=portable-agent-repository-kit&template_owner=sodejm)

**Start every repository with one portable contract for AI coding agents.**

PARK is an open, vendor-neutral GitHub repository template for agentic development.
It gives Codex, Claude Code, GitHub Copilot, ChatGPT, Google Antigravity, and other
AI coding assistants the same shared instructions, Agent Skills, MCP guidance,
checks, hooks, and delivery workflows—without locking the project to one vendor.

The goal is not to make every agent behave identically. The goal is to give every
agent the same trustworthy repository contract, the same reusable workflows, and
the same evidence gates without locking a project to one vendor.

## Supported environments

| Environment | Repository contract | Skills | Tool integration |
| --- | --- | --- | --- |
| Codex | `AGENTS.md` | `.agents/skills/` | MCP; optional local config |
| GitHub Copilot | `.github/copilot-instructions.md` | `.agents/skills/` where supported | GitHub and MCP capabilities vary by surface |
| Claude Code | `CLAUDE.md` | generated `.claude/skills/` copies | `.mcp.json` and optional hooks |
| Google Antigravity | `AGENTS.md` plus `.agents/rules/` | `.agents/skills/` | workspace workflows and MCP support vary |
| ChatGPT | linked repository context or a custom MCP/App integration | not guaranteed in ordinary chat | MCP or a ChatGPT App |
| Other agents | `AGENTS.md` | Agent Skills-compatible clients | MCP-compatible clients |

Compatibility means the checked-in contract is available to the environment. It
does not imply identical permissions, hook semantics, context discovery, or tool
availability. See [Compatibility](docs/COMPATIBILITY.md).

## Start a project

### Create at any local path

```bash
python3 scripts/create_project.py /absolute/path/to/my-project \
  --name "My Project" \
  --description "What the project does" \
  --github-owner my-account \
  --license mit
```

The destination must not exist or must be empty. PARK never merges into or
overwrites a populated directory.

### Use GitHub's template button

1. Mark this repository as a **Template repository** in GitHub settings.
2. Select **Use this template** and clone the new repository.
3. From the new clone, run:

```bash
python3 scripts/configure_project.py \
  --name "My Project" \
  --description "What the project does" \
  --github-owner my-account \
  --license mit
```

The in-place configurator requires `.portable-agent-template`, renders project
metadata, writes the selected license, and removes the marker and generator-only
assets. Commit the result.

License choices are `mit`, `apache-2.0`, or `none`. PARK does not silently choose a
project license.

## The open spine

- `AGENTS.md` is the canonical agent contract.
- `.agents/skills/*/SKILL.md` uses the open Agent Skills shape.
- MCP is the preferred protocol for portable external tools and data.
- `Makefile` and `scripts/agent/` expose deterministic, agent-independent checks.
- CI repeats repository invariants; local hooks are optional convenience only.
- Vendor files remain small adapters and must not redefine the contract.

## Included workflows

PARK includes focused skills for repository orientation, checks, GitHub state
auditing, resumable worktrees, delivery readiness, security review,
documentation impact, `.gitignore` auditing, and creating a new state-0 project
from the source template. The project-creator skill is source-only; it is removed
when a project is generated along with the generator itself. The reusable skills
are generic rewrites of durable practices—not copies of account-level plugins or
project-specific rules.

## Documentation

Start with [Getting Started](docs/GETTING_STARTED.md), then use the
[Repository Layout](docs/REPOSITORY_LAYOUT.md) to understand what each directory
owns and how generation works. The [Documentation Index](docs/INDEX.md) links the
full guide set. Maintainers should also read
[Portability Architecture](docs/PORTABILITY.md), [Skills](docs/SKILLS.md), and
[Security Model](docs/SECURITY_MODEL.md).

## Validate PARK

```bash
make doctor
make check
```

The implementation uses Python's standard library and Git. No package installation
is required for the repository contract checks.

## Community

Use the [issue chooser](https://github.com/sodejm/portable-agent-repository-kit/issues/new/choose)
to report a bug or propose a change. GitHub's `blob` pages show a read-only preview
of each issue form; the issue chooser opens the interactive form. Please review
[Contributing](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and the
[Security Policy](SECURITY.md) before participating.

## License

PARK is released under the [Apache License 2.0](LICENSE). Projects generated from
PARK choose their own license explicitly.

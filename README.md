# PARK — an AGENTS.md template for AI coding agents

[![Repository contract](https://github.com/sodejm/portable-agent-repository-kit/actions/workflows/repository-contract.yml/badge.svg?branch=main)](https://github.com/sodejm/portable-agent-repository-kit/actions/workflows/repository-contract.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Use this template](https://img.shields.io/badge/use_this-template-2ea44f)](https://github.com/new?template_name=portable-agent-repository-kit&template_owner=sodejm)

Portable Agent Repository Kit (PARK) is a GitHub template for teams using Codex,
Claude Code, and GitHub Copilot. Write repository instructions once in
`AGENTS.md`, keep reusable Agent Skills in `.agents/skills/`, and use GitHub
Actions to catch changes that leave Claude Code’s skill copies out of sync.

## Quick start

1. [Create a repository from PARK](https://github.com/new?template_name=portable-agent-repository-kit&template_owner=sodejm).
2. Clone **your new repository** and open its root directory. You’ll need Git,
   Python 3.9 or later, and Make.
3. Initialize the project and check the generated files.

```bash
make init
make check
```

Choose the project name, description, repository details, and license at the
prompts. Review the diff and commit it when the checks pass. To start from a
local PARK checkout, [generate a project in an empty directory](docs/GETTING_STARTED.md#create-into-a-local-directory).

## Supported environments

| Environment | Repository contract | Skills | Tool integration |
| --- | --- | --- | --- |
| Codex | `AGENTS.md` | `.agents/skills/` | MCP; optional local config |
| GitHub Copilot | `.github/copilot-instructions.md` | `.agents/skills/` where supported | GitHub and MCP capabilities vary by surface |
| Claude Code | `CLAUDE.md` | generated `.claude/skills/` copies | `.mcp.json` and optional hooks |
| Google Antigravity | `AGENTS.md` plus `.agents/rules/` | `.agents/skills/` | workspace workflows and MCP support vary |
| ChatGPT | linked repository context or a custom MCP/App integration | not guaranteed in ordinary chat | MCP or a ChatGPT App |
| Other agents | `AGENTS.md` | Agent Skills-compatible clients | MCP-compatible clients |

See [how coding agents read PARK’s instructions](docs/COMPATIBILITY.md) for
each client’s discovery paths and integration requirements.

## What your generated repository contains

- `AGENTS.md` is the canonical agent contract.
- `.agents/skills/*/SKILL.md` uses the open Agent Skills shape.
- MCP is the preferred protocol for portable external tools and data.
- `Makefile` and `scripts/agent/` expose deterministic, agent-independent checks.
- CI repeats repository invariants; local hooks are optional convenience only.
- Vendor files remain small adapters and must not redefine the contract.

The [AAIF project catalog](https://aaif.io/projects) lists `AGENTS.md`, Agent
Skills, and MCP as separate open projects. PARK uses each for its corresponding
repository concern; checked-in compatibility does not imply universal client
support or AAIF conformance.

## Included workflows

PARK includes focused skills for repository orientation, checks, GitHub state
auditing, resumable worktrees, durable parent/subagent workboards, delivery
readiness, security review, documentation impact, `.gitignore` auditing, local
code-churn analysis, and creating a new state-0 project from the source template.
Churn audits work from Git in any agent environment, with optional local Codex
session evidence for recorded edits and tokens. They suggest improvements to
existing contracts and planning using explicit repository inputs and local
reports. The project-creator skill
is source-only; it is removed when a project is generated along with the generator
itself. The reusable skills are generic rewrites of durable practices—not copies of
account-level plugins or project-specific rules.

The portable [clear-writing skill](.agents/skills/clear-writing/SKILL.md) combines
reader-focused prose with native language documentation conventions. See the
[source documentation policy](docs/CODE_DOCUMENTATION.md) for requirements and
the distinction between automated checks and review of meaning.

## Documentation

- [Create or configure a repository from the PARK template](docs/GETTING_STARTED.md)
- [Find the files to customize in a generated repository](docs/REPOSITORY_LAYOUT.md)
- [Update an Agent Skill and synchronize the Claude Code copy](docs/COMPATIBILITY.md#update-an-agent-skill-for-claude-code)
- [Browse all PARK guides](docs/INDEX.md), including [portability architecture](docs/PORTABILITY.md), [skill authoring](docs/SKILLS.md), and the [security model](docs/SECURITY_MODEL.md).

PARK maintainers must also follow the
[owner-review policy and activation runbook](docs/OWNER_REVIEW_POLICY.md).

## Validate PARK

```bash
make doctor
make check
```

The implementation uses Python's standard library and Git. No package installation
is required for the repository contract checks.

## Community

If PARK helped you set up a project, consider starring the repository.

Use the [issue chooser](https://github.com/sodejm/portable-agent-repository-kit/issues/new/choose)
to report a bug or propose a change. GitHub's `blob` pages show a read-only preview
of each issue form; the issue chooser opens the interactive form. Please review
[Contributing](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and the
[Security Policy](SECURITY.md) before participating.

## License

PARK is released under the [Apache License 2.0](LICENSE). Projects generated from
PARK choose their own license explicitly.

## Milestone development workflow

Use the [reusable goal prompt](prompts/next-milestone.md) to run a bounded
milestone with an orchestrating agent. The [usage guide](prompts/README.md) covers
the shared skill, task-specific model routing, decision summaries, and safe storage.

## Optional Codex extension

[Goblin Council](extensions/goblin-council/README.md) adds Single, Cascade, and
parallel Critique workflows for Codex. Its current routes use GPT-5.6 Luna, Terra,
and Sol; availability is checked locally before launch. It is inactive by default
and does not change PARK’s vendor-neutral contract. Follow the
[setup guide](extensions/goblin-council/docs/setup.md) to install it.

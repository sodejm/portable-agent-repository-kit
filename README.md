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

In a fresh project clone, run `make init` for guided setup. See [Project assurance](docs/PROJECT_ASSURANCE.md) for profiles, Spec Kit, Squad and CI.

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

Select **Use this template**, clone the new repository and run the setup interview in the clean clone.

```bash
make init
make check
```

Choose a project name, description, languages, workload contexts, assurance level and license. Setup recommends a level based on the workload and writes the security constitution, Spec Kit templates and Squad configuration. Review the generated files and commit them.

To create a separate project directory from a PARK Git checkout, run the same interview with the generator.

```bash
python3 scripts/create_project.py ../my-project --interactive
```

Choose a new or empty destination outside PARK. For scripted setup and hosted enforcement, see [Getting started](docs/GETTING_STARTED.md) and [Project assurance](docs/PROJECT_ASSURANCE.md).

## The open spine

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

Start with [Getting Started](docs/GETTING_STARTED.md), then use the
[Repository Layout](docs/REPOSITORY_LAYOUT.md) to understand what each directory
owns and how generation works. The [Documentation Index](docs/INDEX.md) links the
full guide set. Maintainers should also read
[Portability Architecture](docs/PORTABILITY.md), [Skills](docs/SKILLS.md), and
[Security Model](docs/SECURITY_MODEL.md). PARK maintainers must also follow the
[owner-review policy and activation runbook](docs/OWNER_REVIEW_POLICY.md).

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

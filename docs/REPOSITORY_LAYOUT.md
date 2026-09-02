# Repository layout

PARK separates portable policy, reusable workflows, deterministic enforcement,
environment adapters, and template-only setup tools. This guide explains what each
area owns and what happens when PARK creates a project.

## Layout at a glance

```text
.
├── AGENTS.md                         canonical repository instructions
├── .agents/
│   ├── skills/*/SKILL.md             canonical reusable Agent Skills
│   ├── rules/                        Antigravity-compatible repository rules
│   └── workflows/                    portable workflow entry points
├── .claude/skills/                   generated Claude discovery copies
├── .github/
│   ├── copilot-instructions.md       GitHub Copilot adapter
│   ├── workflows/                    CI enforcement
│   ├── ISSUE_TEMPLATE/               contribution intake
│   └── dependabot.yml, CODEOWNERS    repository maintenance
├── .codex/config.toml.example        optional Codex-local configuration example
├── CLAUDE.md                         Claude Code adapter
├── .mcp.json.example                 safe MCP configuration example
├── scripts/
│   ├── agent/                        environment-independent checks and sync
│   ├── create_project.py             create a project at a chosen path
│   ├── configure_project.py          configure a GitHub template clone once
│   └── _template_common.py           shared rendering and safety logic
├── templates/
│   ├── licenses/                     explicit license choices
│   └── project/README.md             generated-project README source
├── tests/                             generator and safety tests
├── docs/                              durable guidance and decision records
├── Makefile                           stable human-and-agent command surface
└── .portable-agent-template           one-time configuration guard
```

## Sources of truth

PARK uses a one-way ownership model to prevent instructions from drifting:

1. `AGENTS.md` owns repository-wide agent policy.
2. `.agents/skills/` owns reusable workflow instructions.
3. `scripts/agent/` and the `Makefile` own executable repository checks.
4. `docs/` owns longer-lived explanation, security boundaries, and decisions.
5. Vendor-specific files point to or mirror those sources; they do not redefine
   them.

The files under `.claude/skills/` are generated from `.agents/skills/` because
Claude Code uses a different discovery location. Do not edit those copies directly.
Run `make sync-adapters` after changing a canonical skill. `make check` fails if the
copies drift.

## How project creation works

There are two supported entry paths:

```text
PARK checkout -- create_project.py --> new local directory
GitHub template clone -- configure_project.py --> configured current directory
```

Both paths use the same rendering and validation logic:

1. Validate the destination and refuse unsafe or repeated configuration.
2. Render project name, description, owner, and default branch.
3. Require an explicit `mit`, `apache-2.0`, or `none` license choice.
4. Replace PARK's README with the generated project's README.
5. Synchronize environment adapters from canonical skills.
6. Remove `.portable-agent-template` and generator-only assets.
7. Run the repository contract validation.

The resulting repository keeps the portable agent contract, skills, adapters,
documentation, CI, and checks. It does not keep PARK's project generator, generator
tests, license templates, template-only project-creator skill, or template marker.

The included `agent-workboard` skill writes coordination state beside Git's common
directory (or in a local agent-state directory outside Git for non-Git projects).
It therefore shares state across linked worktrees without adding database files,
handoffs, or agent progress to a project's history.

## Runtime model

PARK does not run a resident service. An AI environment reads the instruction and
skill files it supports, while humans, agents, hooks, and CI invoke the same stable
commands:

```text
human or agent
      |
      +-- reads AGENTS.md and a relevant SKILL.md
      |
      +-- runs make doctor / make check
                         |
                         +-- syntax checks
                         +-- contract validation
                         +-- adapter drift check
                         +-- template safety tests
```

MCP connections and credentials remain client-local unless a project deliberately
adds a safe shared configuration. The checked-in `.mcp.json.example` contains no
secrets and is documentation, not an active connection.

## Files intended for project customization

After generation, maintainers normally update:

- `AGENTS.md` with project commands and non-negotiable constraints;
- `ARCHITECTURE.md` and `docs/decisions/` with actual system design;
- `Makefile` and `scripts/agent/` with build, test, lint, docs, and security gates;
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `GOVERNANCE.md` with real contacts and
  governance details;
- environment adapters only when an environment needs additional discovery
  metadata that cannot live in the open spine.

See [Customization](CUSTOMIZATION.md) for the safe extension rules and
[Portability Architecture](PORTABILITY.md) for the standards rationale.

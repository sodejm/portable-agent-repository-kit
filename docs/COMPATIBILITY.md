# How Codex, Claude Code, and GitHub Copilot read PARK’s instructions

Codex reads the root `AGENTS.md`. PARK’s `CLAUDE.md` and
`.github/copilot-instructions.md` direct Claude Code and GitHub Copilot to that
same file. Skill discovery and tool access depend on the client.

| Capability | Codex | Copilot | Claude Code | Antigravity | ChatGPT |
| --- | --- | --- | --- | --- | --- |
| Root contract | Native `AGENTS.md` | Adapter points to `AGENTS.md` | `CLAUDE.md` points to `AGENTS.md` | `AGENTS.md` plus rule adapter | Provide through linked project/context |
| Agent Skills | `.agents/skills/` | Supported surfaces may discover `.agents/skills/` | generated `.claude/skills/` | `.agents/skills/` | Requires a custom integration |
| MCP | Client config | Surface-dependent | `.mcp.json` or user config | Surface-dependent | Custom MCP/App integration |
| Hooks | Product/global mechanisms | GitHub workflows and product controls | `.claude/settings*.json` | workspace workflows/rules | Automation outside ordinary chat |
| CI evidence | GitHub Actions | GitHub Actions | GitHub Actions | GitHub Actions | Linked GitHub context |

Support changes over time. Verify current product documentation before relying on
a particular discovery path, permission, or hook. The portable fallback is always
to tell the environment to read `AGENTS.md`, select a relevant canonical skill,
and run the repository-owned command.

## Update an Agent Skill for Claude Code

Suppose your team wants its validation report to name the failing Make target.
Add that instruction to `.agents/skills/repository-check/SKILL.md` in your
generated project. Run the following commands from the repository root to update
the Claude Code copy and check the result.

```bash
make sync-agent-adapters
git diff -- .claude/skills/repository-check/SKILL.md
make check
```

The diff should show the same instruction in Claude Code’s discovery copy.
Commit the canonical skill and its copy together. If you skip synchronization,
`make check` reports the drift locally and the repository contract workflow
checks it again on a pull request.

## Compatibility test

For each supported environment, verify that a fresh session can:

1. identify `AGENTS.md` as authoritative;
2. discover or be directed to one relevant skill;
3. run `make doctor` and `make check` with normal approvals;
4. explain that remote writes need explicit authorization;
5. report local and hosted evidence as distinct states.

Record version-specific exceptions in the project, not in global machine policy.

## Goblin Council exception

The optional [Goblin Council extension](../extensions/goblin-council/README.md)
is designed for Codex only. It requires Python 3.11+, Git, and supported Unix
Codex sandbox controls; Windows and other agent runtimes are unsupported. Its
model table describes implemented routes, not universal account availability.

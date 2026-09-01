# Maintenance

Review the repository foundation periodically and when a supported environment
changes discovery, skills, hooks, or MCP behavior.

1. Verify official standards and product documentation.
2. Update the compatibility matrix without overstating parity.
3. Review skills for overlap, stale commands, excessive context, and hidden vendor
   assumptions.
4. Run adapter synchronization and the complete contract check.
5. Generate a temporary project with every license option and validate it.
6. Review GitHub Actions, dependencies, permissions, and supply-chain controls.
7. Record material decisions and user-facing changes.

When upgrading an existing project from PARK, apply changes as a reviewed diff.
Never replace the project's `AGENTS.md`, skills, security policy, or workflows
wholesale; project-local decisions take precedence.

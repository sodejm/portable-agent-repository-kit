# Changelog

All notable project changes should be recorded here. Use semantic versions when
the project publishes versioned releases.

## Unreleased

- Refresh optional validation pins for Ruff 0.17.6 and Coverage 7.17.5; retain
  the verified Build, pip-audit, Semgrep, Trivy, and immutable CI action pins.
- Clarify the distinct `AGENTS.md`, Agent Skills, and MCP formats listed in the
  AAIF project catalog without expanding client-support or runtime claims.
- Add the portable `session-usage-audit` skill with Git-only churn analysis,
  optional Codex session and token accounting, and local workflow recommendations.
- Exclude local JSON configuration and generated churn reports from skill
  adapters and project copies; create new audit reports with owner-only file
  permissions on POSIX systems.
- Run bundled canonical skill test suites in the standard repository checks.
- Initial PARK repository foundation.
- Fix the change-proposal issue form to use GitHub's portable default
  `enhancement` label.
- Validate repository-relative Markdown links as part of the repository contract.

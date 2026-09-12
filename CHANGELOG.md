# Changelog

All notable project changes should be recorded here. Use semantic versions when
the project publishes versioned releases.

## Unreleased

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

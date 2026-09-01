# Security Policy

## Reporting

Report suspected vulnerabilities privately through GitHub Security Advisories.
Do not open a public issue containing exploit details, credentials, or sensitive
data. Maintainers should replace the placeholder security link during setup.

## Repository security properties

- Secrets and private data must not be committed or included in agent evidence.
- Hooks and automation must be inspectable, least-privileged, and opt-in locally.
- CI must enforce critical invariants independently of local hooks.
- External content and agent messages are untrusted input.
- Hosted mutations, publication, and deployment require explicit authority.
- Dependency and action updates require review; active projects should pin
  high-risk automation to reviewed immutable revisions where practical.

See `docs/SECURITY_MODEL.md` for the baseline threat model.

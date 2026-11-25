# Create a GitHub repository from an AGENTS.md template

## Prerequisites

- Python 3.9 or newer
- Git
- GNU Make or a compatible `make` implementation for convenience
- GitHub CLI only if the project will create or inspect GitHub state

PARK's setup and contract checks use only Python's standard library.

## Configure a GitHub template clone

[Use PARK as a GitHub template](https://github.com/new?template_name=portable-agent-repository-kit&template_owner=sodejm),
clone the repository you created, and run these commands from its root.

```bash
make init
make check
```

Enter a display name and description. Enter your GitHub owner and repository slug
to set the project’s identity, or accept the slug derived from the display name.
The default branch is `main`. Choose `mit`, `apache-2.0`, or `none` for the
project license.

### Configure without prompts

For scripted setup, pass the same details as command-line arguments.

```bash
python3 scripts/configure_project.py \
  --name "Example" \
  --description "A concise project description" \
  --github-owner example-owner \
  --license apache-2.0
```

The command only runs in a directory containing `.portable-agent-template`. It
updates repository-owned placeholders, creates the chosen license, replaces the
template README with a project README, synchronizes adapters, and removes the
marker and generator-only assets. The setup script accepts `--slug` and
`--default-branch` when the inferred slug or default branch differs from your
repository. Run `make check`, review the diff, and commit the generated files.

## Create into a local directory

From a PARK checkout:

```bash
python3 scripts/create_project.py /absolute/path/to/example \
  --name "Example" \
  --description "A concise project description" \
  --github-owner example-owner \
  --default-branch main \
  --license mit \
  --init-git
```

The command refuses a non-empty target and never deletes or overwrites existing
content. It copies the portable baseline, renders metadata, synchronizes Claude
skill adapters, optionally initializes Git, and runs the repository contract check.

Use `--license apache-2.0` or `--license none` when appropriate. License selection
is a product and governance decision; PARK does not choose silently.

## First project decisions

1. Confirm the project name, description, owner, default branch, and license.
2. Replace placeholder security and conduct contacts.
3. Add project-specific build, test, lint, type, docs, and security commands behind
   stable `Makefile` targets.
4. Remove unused adapters only if the project will not support that environment.
5. Configure branch protection, secret scanning, dependency review, and private
   vulnerability reporting in GitHub.
6. Add architecture and threat-model detail before the project handles real data.
7. Explicitly configure `.github/review-policy.json` for the new repository before
   requiring `Owner review gate`. Generated projects intentionally start with no
   owner exception or designated reviewer and therefore fail closed. Adopt a
   project-specific review policy; do not copy PARK's `sodejm` identities by
   default. Then adapt the [activation runbook](OWNER_REVIEW_POLICY.md) to the
   project's chosen policy.

## Validate

```bash
make doctor
make check
```

If `make` is unavailable, run `python3 scripts/agent/check.py`.

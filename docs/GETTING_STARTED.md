# Getting started

## Prerequisites

- Python 3.9 or newer
- Git
- GNU Make or a compatible `make` implementation for convenience
- GitHub CLI only if the project will create or inspect GitHub state

PARK's setup and contract checks use only Python's standard library.

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

## Configure a GitHub template clone

After creating a repository with GitHub's **Use this template** button:

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
marker and generator-only assets. The portable contract and its checks remain. Run
it once, review the diff, then commit.

## First project decisions

1. Confirm the project name, description, owner, default branch, and license.
2. Replace placeholder security and conduct contacts.
3. Add project-specific build, test, lint, type, docs, and security commands behind
   stable `Makefile` targets.
4. Remove unused adapters only if the project will not support that environment.
5. Configure branch protection, secret scanning, dependency review, and private
   vulnerability reporting in GitHub.
6. Add architecture and threat-model detail before the project handles real data.

## Validate

```bash
make doctor
make check
```

If `make` is unavailable, run `python3 scripts/agent/check.py`.

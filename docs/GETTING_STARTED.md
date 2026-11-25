# Getting started

## Prerequisites

- Python 3.10 or newer
- Git
- GNU Make or a compatible `make` implementation for convenience
- GitHub CLI only if the project will create or inspect GitHub state

Setup uses Python's standard library and Git. The portable checks run locally. Security scans require the tools listed in [Project assurance](PROJECT_ASSURANCE.md).

## Configure a GitHub template clone

Select **Use this template**, clone the new repository and run the interview in the clean clone.

```bash
make init
```

Enter a name, description, languages and workload contexts. Choose the suggested assurance level or select another, then choose a license. Setup creates a project README, a security constitution, Spec Kit templates and Squad coordination files. Review the generated files, run `make check` and commit the result. Running `make init` again preserves the configuration.

## Create into a local directory

From a PARK Git checkout, choose a new or empty destination outside the checkout.

```bash
python3 scripts/create_project.py ../example --interactive
```

The generator copies tracked files and stages setup before publishing the directory. Supply explicit options for unattended setup. This example creates a Python API at medium assurance and initializes a local Git repository.

```bash
python3 scripts/create_project.py ../example \
  --name "Example" \
  --description "A small internal API" \
  --languages python --context api --assurance medium \
  --license mit --init-git
```

Run `make check` in the generated directory. License choices are `mit`, `apache-2.0` and `none`.

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

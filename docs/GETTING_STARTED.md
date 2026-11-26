# Create a GitHub repository from an AGENTS.md template

## Prerequisites

- Python 3.10 or newer
- Git
- GNU Make or a compatible `make` implementation for convenience
- GitHub CLI only if the project will create or inspect GitHub state

Setup uses Git and Python's standard library. Security scanning also requires the
tools listed in [Project assurance](PROJECT_ASSURANCE.md).

## Configure a GitHub template clone

[Use PARK as a GitHub template](https://github.com/new?template_name=portable-agent-repository-kit&template_owner=sodejm),
clone the repository you created, and run these commands from its root before editing any files.

```bash
make init
make check
```

Enter the project name and description, then give the languages and workload
contexts as comma-separated values. For example, enter `python,go` for languages
and `cli,api` for contexts. Press Enter to accept the suggested `medium` assurance
level for that combination. Choose `mit`, `apache-2.0`, or `none` for the license.

Review `.park/profile.json` for your selections and `.specify/memory/constitution.md`
for the controls they generated. Setup also creates Spec Kit templates and a local
Squad coordinator. Once the checks pass, commit the generated files and run
`make assurance` to scan the commit. Running
`make init` again shows where to find the constitution. See the
[project assurance guide](PROJECT_ASSURANCE.md) for context and language guidance.

### Configure without prompts

For scripted setup, pass the same details as command-line arguments.

```bash
python3 scripts/configure_project.py \
  --name "Example" \
  --description "A concise project description" \
  --languages python \
  --context api \
  --assurance medium \
  --github-owner example-owner \
  --license apache-2.0
```

The command only runs in a directory containing `.portable-agent-template`. It
updates repository-owned placeholders, creates the chosen license, replaces the
template README with a project README, synchronizes adapters, and removes the
marker and generator-only assets. Use `--github-owner` to set the GitHub owner. You can
override the inferred slug with `--slug` and the default branch (`main`) with
`--default-branch`. Run `make check`, review the diff, and commit the generated
files.

## Create into a local directory

From a PARK Git checkout, choose a new or empty directory outside the checkout.

```bash
python3 scripts/create_project.py ../example --interactive --init-git
cd ../example
make check
```

The local generator uses the same interview and accepts the same flags for
scripted setup. The `--init-git` flag initializes Git in the new directory.

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

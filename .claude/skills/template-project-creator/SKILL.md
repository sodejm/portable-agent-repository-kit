---
name: template-project-creator
description: Create a fresh state-0 repository from this PARK checkout with the Python project generator. Use only from an unconfigured PARK template checkout, not inside a generated project.
---

# Template project creator

Create a new, configured PARK project by running the repository's Python
generator. A state-0 project is the generated baseline: it has its selected
identity and license rendered, but no product-specific implementation or
history unless the user asks to initialize Git.

## Required decisions

Before running the generator, obtain or infer only these values:

- destination: an absolute path that does not exist or is an empty directory;
- name and concise description;
- license: `mit`, `apache-2.0`, or `none`.

Accept an optional GitHub owner, project slug, copyright holder, and default
branch. Do not invent an owner or license. Default the branch to `main` only
when the user has not selected another branch.

## Create the project

Confirm this checkout contains `scripts/create_project.py` and
`.portable-agent-template`; otherwise, explain that this is already a generated
project and cannot generate another project through this skill.

Run the generator from the PARK checkout with `python3` and explicit arguments:

```bash
python3 scripts/create_project.py /absolute/path/to/project \
  --name "Project Name" \
  --description "What the project does" \
  --license mit
```

Add `--github-owner`, `--slug`, `--copyright-holder`, or `--default-branch`
only when selected. Add `--init-git` only when the user requests a newly
initialized local Git repository. Never work around the generator's empty-target
check, merge into an existing project, or delete destination contents.

## Verify and hand off

Run `make check` in the generated directory. Report the destination, chosen
configuration, whether Git was initialized, and the validation result. The new
project should have no `.portable-agent-template`, no generator-only assets, and
no product-specific code until its owner adds them.

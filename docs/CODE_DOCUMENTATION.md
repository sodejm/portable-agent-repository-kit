# Source-code documentation

## Writing contract

Use the repository-local
[clear-writing skill](../.agents/skills/clear-writing/SKILL.md) with the language's
native documentation convention for every source documentation change. Agents
without skill discovery must read that file directly. Missing skill resources are
a prerequisite failure, not permission to claim that the skill was used.

Document public APIs, modules/packages, and major internal functions and types.
Internal code needs explanation when it implements domain rules, coordinates
operations, changes persistent state, or has non-obvious constraints or failures.
Explain complex algorithms, their invariants and relevant trade-offs beside the
implementation. Include inputs, outputs, side effects, error conditions and
troubleshooting context where relevant; do not invent unsupported guarantees.

This applies across application code, scripts, tests, build tooling and
infrastructure. Use native docstrings/comments or adjacent documentation for
formats without comments. Keep existing stricter conventions. Trivial private
helpers need no standalone prose unless their behavior is surprising. Comments
that merely narrate statements and empty boilerplate do not satisfy this policy.

Update documentation with the behavior it describes. Bring new and materially
changed code into compliance; track unrelated legacy gaps rather than expanding
every change into a full rewrite. Change generators and canonical sources, not
generated or vendored copies. Review meaning against implementation and tests.

## Automation boundary

The portable contract validates that the writing skill and this policy are
present, and adapter checks detect drift. Neither check proves that an agent
invoked the skill or that documentation is accurate.

Run `make check-code-documentation` for the source gate, or `make check` for all
repository checks. The existing `Repository contract` CI workflow runs the same
gate through `make check`. Python's standard-library AST parser reads source
without importing it or running decorators. No package or network is needed.

The gate checks all `.py` files under the repository, including untracked files,
except explicitly excluded directories in `.agents/code-documentation.json`.
Single-component exclusions match directory names anywhere; multi-component
exclusions match a root-relative prefix. `.claude/skills` is generated; its
canonical `.agents/skills` source remains checked. Standard dependency/cache
directories are excluded, not arbitrary application directories.

Required documentation covers:

- Every Python module, including test modules and package initializers.
- Public-named module-level functions/classes and methods of public classes.
  Protocol dunders count as public. Dynamic exports are not inferred.
- Private or nested declarations with at least 10 executable statements,
  including nested control flow but excluding nested declaration bodies and
  standalone string expressions. This threshold is only a mechanical minimum;
  smaller functions with subtle behavior still need documentation under the policy.

Checks reject missing/empty docstrings, exact placeholder summaries such as
`TODO`, `TBD` or `...`, and extended docstrings without a blank line after the
summary. This is a structural subset of PEP 257, not a complete style checker.
Use the existing section format; type and parameter-section consistency still
need review or additional native lint.

Diagnostics are sorted and contain relative path, line, symbol and rule. Exit 0
means the configured scope passes, 1 means documentation violations, and 2 means
input/configuration errors prevented a complete check. Source/configuration files
are limited to 8 MiB. Relevant symlinks, malformed configuration, unreadable input
and invalid Python fail closed; no source body is printed in error messages.

## Legacy coverage and migration

`.agents/code-documentation-baseline.json` records existing violations, the exact
file SHA-256 and relative path. It is a backlog, not evidence that those files are
documented or reviewed. Only identical file contents and recorded rules are
exempt. A changed file must satisfy the rules throughout that file; new files have
no exemption. Missing/deleted files are harmless, including source-only assets
removed by project generation. A fully compliant file passes even with a stale
baseline entry; remove stale entries during a reviewed baseline cleanup.

To inspect current gaps without changing anything:

```sh
python3 scripts/agent/check_code_documentation.py --inventory-json
```

The command prints candidate baseline JSON, not an updated approval. Review every
entry before adopting an initial inventory in another project. Do not refresh a
baseline to hide new violations; additions, exclusions and threshold changes
require the same review as the check itself. Routine checks never write policy,
baseline or source. To diagnose a failure, find the relative location, add accurate
documentation, and rerun the gate. Do not suppress a parse error as documentation
debt.

Generated projects retain the skill, policy, baseline and gate. The check works
before Git initialization and checks new consumer code without staging it.

## Additional languages and human review

Other languages require project-specific native checks. A table of language
conventions is not an implementation of their parsers. Record which checks run,
which files they cover, and which obligations remain manual. No linter establishes
the correctness of an algorithm explanation or the safety of recovery advice.

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

The planned source gate uses Python's standard-library AST for PARK's Python
code. It will enforce structural coverage with a reviewed legacy baseline. The
implementation plan describes acceptance tests; until that gate is implemented,
do not claim automated declaration-level enforcement.

Other languages require project-specific native checks. A table of language
conventions is not an implementation of their parsers. Record which checks run,
which files they cover, and which obligations remain manual. No linter establishes
the correctness of an algorithm explanation or the safety of recovery advice.

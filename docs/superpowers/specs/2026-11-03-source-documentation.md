# Portable source documentation specification

Status: user-approved; PARK implementation is undergoing validation and review.

## Outcome

Require clear, language-appropriate source documentation for new and materially
changed code. Package `clear-writing` in PARK so generated projects and supported
agent adapters do not depend on a contributor's personal skill installation.
Add offline, deterministic checks without claiming that automation can establish
prose accuracy, troubleshooting value, or actual agent skill invocation.

## Requirements

- Keep the skill vendor-neutral, repository-local, and usable without network
  access. Preserve meaning, conditions, technical terminology, and uncertainty.
  Include provenance and links to the Google and Orwell guidance; use original
  summaries and examples rather than reproducing their published prose.
- Require native docstrings or documentation comments for public interfaces and
  major internal functions, types, and algorithms. Explain purpose, constraints,
  side effects, failure behavior, invariants, and troubleshooting context where
  relevant. Do not require comments that merely repeat statements or signatures.
- Select conventions per language. Python uses PEP 257 with the repository's
  section style; other languages use their established native tooling. Formats
  without comments use adjacent documentation. Preserve stronger existing gates.
- PARK's first implementation checks Python with its standard-library AST.
  Public modules, classes, functions, and methods require nonempty docstrings.
  Private functions also require them when they contain at least 10 executable
  statements, counting nested control flow but not nested function/class bodies.
  This threshold is a mechanical minimum, not the definition of human complexity.
- Do not parse arbitrary languages with regular expressions and call the result
  semantic validation. Report the exact automated coverage and manual obligations.
  Rollout to another language requires its own tested, native integration before
  claiming that language's declaration documentation is enforced.
- Use a reviewed, exact-file-content legacy baseline to avoid an unrelated
  repository-wide documentation rewrite. Only identical legacy files may retain
  recorded violations. New or changed files must pass. No automatic baseline
  refresh is part of `make check`; additions to the baseline require review.
- Generated/vendor copies are excluded explicitly; canonical sources remain in
  scope. Generated projects retain a working gate before and after Git init.
- Diagnostics contain repository-relative locations and rule identifiers, not
  source bodies, credentials, or machine paths. Checks do not execute source code,
  invoke model providers, or access the network.
- Registered in-root directory aliases may refer to canonical source that is
  checked once at its real path. Reject retargeted, excluded or chained aliases;
  this exception preserves the supported project-local Goblin installation.
- Test missing, empty, and placeholder docstrings; nested and async declarations;
  syntax errors; baseline drift; path safety; adapters; and generated projects.

## Delivery boundaries

Implement and validate PARK first on a standalone branch from its remote default
branch. Push and merge only through normal review and required checks. Roll out
the accepted capability to explicitly selected projects on independent branches,
adapting their existing validation instead of replacing it. Do not publish other
project history, bypass review requirements, change branch protections, deploy,
or merge unrelated work. Record blocked repositories separately.

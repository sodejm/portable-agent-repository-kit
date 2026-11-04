# Portable source documentation implementation plan

> **For agentic workers:** Execute the checked tasks with the user's chosen native
> or bounded-subagent workflow. The upstream planning template's Superpowers
> execution subskills are not available here; use repository-owned commands and
> the installed review workflow instead. This plan grants no additional authority.

**Goal:** Ship portable clear-writing guidance and deterministic documentation
checks in PARK, then integrate the accepted capability into selected projects.

**Architecture:** Store the portable skill under `.agents/skills/clear-writing/`
and synchronize its Claude adapter through the existing generator. Keep policy,
the Python AST checker, and a reviewable legacy baseline separate. Extend the
existing `make check` path; no external service or new Python package is needed.

**Tech stack:** Python standard library, unittest, Markdown, Make, existing GitHub
Actions contract workflow.

**Spec:** [Source documentation specification](../specs/2026-11-03-source-documentation.md).

## Global constraints

- Preserve unrelated work, signing requirements, existing validation and reviews.
- Use canonical `.agents/skills/`; do not edit generated `.claude/skills/` copies.
- No dependency installation is required for PARK's baseline checks.
- Run focused tests during development and `make check` before handoff.
- Create validated local checkpoints with actual evidence and recovery notes.
- Do not claim manual review, prose quality, or skill invocation from a lint pass.
- Existing project history and data are outside the standalone publication scope.

## Review focus

1. Unchanged legacy violations must not hide new violations in a changed file.
2. AST traversal must distinguish private, public, nested, async and test code;
   decorated definitions and strings containing fake declarations remain safe.
3. Symlinks, malformed configuration and unreadable files must not bypass checks
   or expose files outside the repository.
4. Generation removes source-only assets and starts without Git metadata; copied
   baseline entries must not disable checks on new consumer code.
5. A green structural check must not imply that other languages or prose meaning
   were validated, or that an agent actually invoked the skill.

---

### Task 1: Portable skill and source documentation contract

**Files:**
- Create `.agents/skills/clear-writing/SKILL.md`.
- Create `.agents/skills/clear-writing/references/source-documentation.md`.
- Create `.agents/skills/clear-writing/references/provenance.md`.
- Create `docs/CODE_DOCUMENTATION.md`.
- Modify `AGENTS.md`, `docs/SKILLS.md`, `docs/INDEX.md`, `README.md`.
- Modify `scripts/agent/validate_contract.py`, `tests/test_template.py`.
- Generate `.claude/skills/clear-writing/` through the existing sync command.

**Interfaces:** The root contract links the canonical skill and policy. The skill
explains writing and review; the policy defines enforced rules and limitations.

- [x] Add tests requiring the canonical skill, references, generated adapter and
  generated-project copies. Verify that a missing required skill fails validation.
- [x] Run the focused unittest cases and record the expected failures (two failures).
- [x] Write a portable synthesis preserving the installed skill's meaning-first
  guidance, with language-specific examples and provenance. Add the source
  documentation policy without changing unrelated review or authority rules.
- [x] Require the skill and policy in contract validation, synchronize adapters,
  and rerun the focused tests plus contract validation.
- [x] Checkpoint with exact validation and a Git-revert recovery note (`98042ad`).

### Task 2: Python AST gate and reviewed legacy baseline

**Files:**
- Create `scripts/agent/check_code_documentation.py`.
- Create `tests/test_code_documentation.py`.
- Create `.agents/code-documentation.json`.
- Create `.agents/code-documentation-baseline.json`.
- Modify `Makefile`, `scripts/agent/check.py`, `docs/CODE_DOCUMENTATION.md`.
- Update documentation for materially changed checker integration functions.

**Interfaces:**
- `check_code_documentation.py --root PATH` reads policy and baseline below PATH;
  defaults to the repository containing the script.
- Exit 0: checked scope passes; 1: documentation violations; 2: invalid policy,
  unreadable source, unsafe path or parse failure. Sort diagnostics by relative
  path, line and rule. Do not print source bodies or raw filesystem exceptions.
- Policy version 1 selects Python sources and explicit generated/vendor excludes.
  Document the exact scope; do not provide arbitrary shell-command hooks.
- Baseline entries contain relative path, SHA-256 of exact bytes and recorded
  violation identifiers. An entry never excuses a different content hash or a
  violation not recorded in that entry. Deleted files do not fail the check.

- [x] Add failing fixture tests for missing/empty/placeholder module and public
  declaration docstrings; valid one-line and multiline docstrings; decorators;
  async functions; public methods; private functions below/at the 10-statement
  threshold; nested definitions; strings containing fake code; and syntax errors.
- [x] Add failing tests for unmodified legacy files, changed legacy files, new
  files, removed files, malformed/duplicate baseline entries, traversal paths,
  symlink escapes and stable diagnostics. Test that checks never update baselines.
- [x] Implement deterministic discovery, AST traversal and baseline comparison.
  Read Python encodings correctly. Ignore generated directories explicitly;
  do not depend on Git tracking so new files and generated projects are checked.
- [x] Run tests; generate and review the initial PARK-only legacy inventory.
  Document all new checker functions and keep their files out of the baseline.
- [x] Add `make check-code-documentation` and invoke the same checker from
  `scripts/agent/check.py`. Document covered syntax versus manual obligations.
- [ ] Run the focused suite, documentation gate and `make check`; checkpoint.

### Task 3: Generation, security evidence and PARK delivery

**Files:**
- Modify `tests/test_template.py`, `scripts/_template_common.py` only as needed.
- Modify `docs/THREAT_MODEL.md`, `docs/security/REVIEW_COVERAGE.md`.
- Keep `.github/workflows/repository-contract.yml` unchanged if `make check`
  already exercises the gate on the exact PR head.

**Interfaces:** A generated project retains canonical skill, synchronized adapter,
policy and checker. It enforces new code without requiring Git initialization.

- [x] Test generation before Git init, after empty Git init and after adding a new
  undocumented Python file. Assert the first two pass and the last fails; a
  documented replacement passes. Verify source-only removals do not break checks.
- [x] Make only the generator adjustments required by those regression tests.
  Token rendering changed the generator helper's hash in consumer projects;
  documented that helper and removed its legacy exception rather than regenerating
  an exemption for changed code. No generator behavior was changed.
- [x] Record the checker input boundary, read-only behavior, baseline-tampering
  limitation and diagnostics privacy in the threat model. Keep human review pending.
- [ ] Run `make check`, inspect the complete diff and obtain the chosen automated
  review. Correct supported findings and rerun affected checks.
- [ ] Create the final signed checkpoint, push only this branch and open a PR.
  Confirm the exact head, required checks and applicable review state before merge;
  do not bypass protection or rewrite checkpoints to force delivery.
- [ ] Verify the merged remote revision and retain an evidence-bearing checkpoint.

### Task 4: Bounded project integrations

This is a sequence of independent integrations, not a bulk copy operation. Keep
the selected repository inventory and local paths in private rollout evidence,
not in the public template. Prepare a short per-project file/test map after PARK
has passed and before that project's first edit.

**Shared inputs:** The merged PARK skill, policy, checker, tests and provenance.
**Outputs per project:** One standalone branch/PR, native check integration,
project-specific legacy inventory where needed, exact validation and merge state.

- [ ] Refresh each selected repository's remote default branch and contracts;
  create an isolated worktree without touching the original checkout's edits.
- [ ] Inspect existing language coverage, baseline and native doc tools. Reuse
  existing stricter documentation gates instead of introducing a competing checker.
- [ ] Add failing tests for missing documentation in each first-party language in
  that project's enforced scope. Use native parsers/tools for declaration checks.
  Mark remaining manual-only coverage explicitly; do not report it as enforced.
- [ ] Add the portable skill and concise agent policy; adapt existing commands,
  workflow entrypoints, documentation, notices and threat-model evidence.
- [ ] Run the repository's required checks, review and signing gates. Commit and
  push only the addition. Merge only when all required evidence is satisfied.
- [ ] Record URL, exact head, checks, review and merged revision; otherwise record
  a specific blocker. Do not bootstrap an empty remote or weaken human-review
  rules as part of this addition.

## Execution checkpoint

- PARK base: `71b8c29`; branch: `feature/source-code-documentation`.
- The user approved native execution. The skill is checkpointed; the AST gate,
  baseline and generated-project tests are implemented. `make check` passed
  (68 root tests, 48 skill tests, 26 extension tests; one opt-in sandbox skip).
- Next: validate the final input-bound tests, checkpoint and obtain independent
  automated review. No remote writes yet.

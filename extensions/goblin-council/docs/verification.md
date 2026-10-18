# Verify the optional extension

From the PARK repository root:

Use a Python 3.11+ interpreter for these commands. Ensure `python3` on `PATH`
selects that interpreter when running `make check`.

```sh
python3 -m unittest discover -s extensions/goblin-council/tests -v
make check
```

The extension suite exercises real Git repositories with deterministic fake model
stages. It checks Single routing, Cascade rejection/repair, parallel independent
Critique, bounded retries, dirty-index/untracked preservation, tampered/stale
review rejection, concurrency, linked worktrees, and installer ownership and
rollback. PARK's generator test also verifies that generated projects carry the
package without activating the Codex skills or creating Claude mirrors.

For a native sandbox and MCP-disable probe on the intended host:

```sh
GOBLIN_NATIVE_TESTS=1 python3 -m unittest discover -s extensions/goblin-council/tests -v
```

This optional test needs the native Codex CLI and host sandbox access. Running
inside another sandbox may prevent it. Report a skip or failure separately; do
not count deterministic fake-stage results as live permission verification.
The coordinator repeats permission probes before real stages.

The three [acceptance prompts](../README.md#verification) describe expected
Single, Cascade escalation, and max Critique traces. For real model validation,
use disposable repositories, inspect `trace.jsonl`, verify selected model/effort
and exact candidate IDs, and compare primary files/index before and after.
A real model need not intentionally produce the flawed Cascade candidate; use
the deterministic fixture to reproduce that rejection path reliably.

Model availability, effective OS sandbox isolation, and output quality are
separate claims. Neither TOML parsing nor an available catalog entry proves all
three. Human exact-revision review remains required by PARK's engineering policy.

## Import verification (2026-10-18)

On macOS with Python 3.14, the extension suite passed 25 deterministic tests
(the native test is opt-in). The native sandbox/MCP inventory test separately
passed outside the enclosing agent sandbox; inside it, macOS denied creation of
the nested sandbox. No paid model stages were exercised for this import.
These results do not establish Linux compatibility or real-model task quality.

## Live validation follow-up (2026-10-18)

Implementation revision: `a53ffdcb7745b14e015b4cec95356f13de38f19b`.
Host: macOS, Python 3.14, native Codex CLI `0.163.0-alpha.10.2`.
`make check` passed, and the opt-in native command above passed all 26 tests
without skips when run outside the enclosing agent sandbox. PR #11's Repository
contract CI also passed at this revision.

The smoke fixture used disposable repositories containing `attempts(retries)`.
Acceptance required `0 -> 1`, `3 -> 4`, and `ValueError` for negative retries.
Each repository also contained distinct staged and unstaged versions of a notes
file and an untracked file. The harness compared real index bytes and those file
contents after execution, and reran the acceptance command in the primary tree.
Scores were deliberately selected to exercise routes; this arithmetic fixture
does not represent a complex architecture or security workload.

| Route | Scores (depth, blast, ambiguity, risk) | Native stages | Result |
| --- | --- | --- | --- |
| Standard Single | 0, 0, 0, 0 | None; direct primary-thread edit | Acceptance passed; user edits preserved |
| Standard Cascade | 1, 1, 1, 1 | Luna medium draft, Terra medium judge | PASS; validated candidate promoted; user edits preserved |
| Standard Cascade | 2, 1, 0, 1 | Terra medium draft, Terra medium judge | PASS; validated candidate promoted; user edits preserved |
| Standard Cascade with injected defect | 1, 1, 1, 1 | Luna medium draft, Terra medium judge, Sol high repair and final judge | ESCALATE, one repair, PASS, promotion; user edits preserved |
| Max Critique | 2, 1, 0, 1 | Terra high draft, parallel Sol high architecture/security critics, Sol high synthesis and final judge | Both critics PASS, one synthesis, final PASS, promotion; user edits preserved |

Model names in this table abbreviate `gpt-5.6-luna`, `gpt-5.6-terra`, and
`gpt-5.6-sol`. No model substitution was used. The harness called the coordinator's
native pipeline directly; deterministic tests separately exercise CLI dispatch.
Single used the current primary thread, so it is not an additional model-access
test. Native stage traces recorded effective sandbox probes, model/effort,
candidate-bound validation and review, and promotion.

The rejection test deliberately restored the original defective function after a
real Luna draft. Validation failed and the real Terra judge returned `ESCALATE`;
Sol repaired the candidate, validation passed, and the final Sol judge returned
`PASS`. This demonstrates fault-injected recovery, not a spontaneous drafting
failure. The max-mode critic intervals overlapped (approximately 35 and 24
seconds); both reviewed the same frozen candidate before one synthesized revision
and final candidate-bound validation/judging.

These are bounded integration smoke results, not a broad model-quality benchmark
or independent security approval. Linux native validation remains outstanding.
The PR must remain draft pending independent human security review of the exact
revision. This evidence-only follow-up changes no code, dependencies, data flows,
or trust boundaries; the existing threat model remains applicable.

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

# Goblin Council

Goblin Council routes a coding task through **Single**, **Cascade**, or **Critique** using native Codex sessions and Git worktrees. Standard mode selects the smallest sufficient workflow; max mode always adds review and uses high reasoning effort. Max is selected explicitly.

The package contains two skills, four agent role definitions, a local Python standard-library coordinator, and transaction tests. It needs no external MCP server, model proxy, or agent SDK. The Python helper coordinates the native Codex CLI; it does not implement a model API client.

## PARK installation and support

This is an optional **Codex-only** extension. It is not a Claude Code, Copilot,
ChatGPT chat, or vendor-neutral orchestration implementation. PARK carries the
package into generated projects without activating it or mirroring these skills
into Claude adapters. See the [setup guide](docs/setup.md).

| Implemented model | Reasoning effort | Use |
| --- | --- | --- |
| `gpt-5.6-luna` | medium | Small standard Cascade drafts |
| `gpt-5.6-terra` | medium / high | Standard draft/judge; max draft/initial judge |
| `gpt-5.6-sol` | high | Critics, repair, final judge, high-risk stages |

Single uses the current primary session. These are configured routes, not a
guarantee of account access or claims about the newest models. Every launch
checks the local Codex catalog and stops if a selected pair is unavailable.
Other model families/providers are not implemented.

## Important implementation choice

The source implementation targets a Codex build that supports native agent roles, but those roles inherit their parent's sandbox. A `sandbox_mode` field in a role file does not establish a separate enforced permission boundary. Goblin Council therefore executes each draft/review stage as a separate native `codex exec` session. Drafts use `workspace-write`; judges and critics use `read-only`. These are CLI sessions, not children shown in the app's native subagent tree.

The four TOMLs supply role instructions and document default model choices. The coordinator applies the actual model, effort, and sandbox for each stage. It disables nested delegation, plugins, MCP servers, web search, and network access in stage tools. Existing applicable instructions and host policies still apply. Trusted host hooks remain outside the model tool sandbox.

## Requirements and setup

- Python 3.11 or later, Git, and an authenticated native Codex CLI.
- macOS or a Unix host with `fcntl` and working Codex sandbox support. macOS is tested; Linux must pass the same probes. Windows is not supported by this helper.
- A non-bare repository with an existing commit. Unmerged files, submodules, sparse checkouts, skip-worktree, and assume-unchanged entries are rejected.
- The selected model/effort pairs must appear in the live `$CODEX_HOME/models_cache.json` catalog. Missing routes fail; models are never silently substituted.

Keep this package together: the helper resolves `.codex/agents` relative to its own package root. To use it in another repository, pass that repository with `--repo`; you do not need to copy the package into the target checkout. Register the two skill directories in your normal Codex skill location, or open this package in Codex for project-scoped skill discovery. Restart or refresh skill discovery if necessary.

The installer and coordinator do not require changing global or repository configuration. For optional native role registration, merge `.codex/config.toml` with the existing file and place the roles under `.codex/agents`. Do not replace existing config. The example concurrency setting is `agents.max_concurrent_threads_per_session = 4`; the coordinator itself runs at most two independent critics. Stage sessions have delegation disabled, giving a logical depth of one. This build does not expose a supported `max_depth` setting; `max_threads` is a legacy alias.

The inactive provider example uses `wire_api = "responses"`. Another provider must implement the required Responses behavior and have an explicitly verified route and authentication configuration. The coordinator currently pins OpenAI and does not automatically route to that example provider.

## Use

In Codex, invoke `$goblin` or `$goblin-max`, followed by the task and acceptance criteria. The skill inspects the task, scores it, and writes a task contract outside the target checkout. See [the example contract](docs/example-task.json) and [routing policy](.agents/skills/goblin/references/routing.md).

For direct CLI use, set these to your package, Python, target repository, and task file:

```sh
COUNCIL_PACKAGE="/absolute/path/to/this/package"
COUNCIL_PYTHON="/absolute/path/to/python3.11-or-later"
COUNCIL_REPO="/absolute/path/to/target/repository"
COUNCIL_TASK="/absolute/path/outside/target/task.json"

"$COUNCIL_PYTHON" "$COUNCIL_PACKAGE/.agents/skills/goblin/scripts/council.py" \
  --repo "$COUNCIL_REPO" run --task "$COUNCIL_TASK" --mode standard
```

Use `--mode max` for explicit max mode. `run --codex /absolute/path/to/codex` selects a CLI; `--timeout 900` is the per-command timeout in seconds. Validation commands are argument arrays, not shell strings. Use the repository's required environment and executable paths. Dependency downloads are not enabled by the coordinator.

A Single result asks the calling Codex thread to implement directly. The CLI helper intentionally launches no model and edits nothing for Single. Skills cannot change the current thread's model or reasoning setting by themselves.

## Routing and execution

Scores range from 0 through 3 in reasoning depth, blast radius, ambiguity, and security/concurrency risk. File counts include tests. See the policy for exact boundaries and model selection.

| Rule, in order | Workflow |
|---|---|
| Ambiguity 3 | Clarification required |
| Max and any score at least 2 | Critique |
| Other max tasks | Cascade |
| Standard: risk at least 2, depth 3, blast 3, or two scores at least 2 | Critique |
| Standard: all scores at most 1 and sum at most 3 | Single |
| Remaining standard tasks | Cascade |

```text
Single:   classify → primary implementation → verification
Cascade:  isolated draft → freeze/test → judge
          PASS → promote
          ESCALATE or failed tests → one high-effort repair → freeze/test → final judge
Critique: isolated draft → freeze/test → architecture critic ─┐
                                       security critic ────┴→ one synthesized revision
          → freeze/test → final judge → promote or retain rejected candidate
```

Critics run in parallel against the same frozen candidate and do not receive one another's initial reports. The final judge receives both reports. A restart uses the original dirty-workspace snapshot, not a new snapshot of an edited primary directory. Repairs are bounded to one pass; further failure retains the run for inspection.

Standard drafting uses `gpt-5.6-luna/medium` for the smallest Cascade tasks and `gpt-5.6-terra/medium` otherwise. Critics, repair, and the final post-repair judge use `gpt-5.6-sol/high`. Risk 2+, depth 3, or blast 3 selects sol/high throughout. Max uses high effort in every stage. These configured GPT-5.6 routes are not claims that these models are the newest available. Initial thresholds are not a measured Pareto optimum.

Reviewer JSON contains exactly `candidate_id`, `verdict`, `defects`, `repair_plan`, and `restart_required`. The [schema](.agents/skills/goblin/references/review.schema.json) rejects extra fields. A PASS with a blocking defect or restart request cannot promote. Reports must refer to the exact candidate Git tree. Writers return short changes/checks/unresolved reports.

## Transaction guarantees and limits

The coordinator captures the primary HEAD, index bytes, and tracked plus non-ignored untracked file contents. It constructs a snapshot with a **private temporary Git index**. It never runs `git add -N` against the primary index and does not create, pop, or modify a user stash.

A detached candidate worktree starts from that snapshot. A separate frozen review worktree provides a stable candidate to critics. Validation runs in another disposable checkout, allowing build caches without letting tests mutate the reviewed candidate. Source changes during validation fail the gate.

Before promotion, the coordinator requires current candidate/review/patch integrity, passing validation, a matching PASS from the final judge, and an unchanged primary fingerprint. Promotion uses `git apply --check --binary` followed by plain `git apply --binary`; it does not use `--3way` or `--index`. The original staging state stays intact; accepted changes become working-directory edits. Postchecks verify primary HEAD/index and candidate contents.

Git worktrees share the repository's object database. This is isolation of candidate file mutations, not literal zero shared state. Synthetic snapshot refs and journals live in the common Git directory under `goblin-council`. The `.git` path may be a file; linked worktrees are supported.

Other limits:

- Ignored files, caches, and secrets are not copied. Required dependencies must be available through the repository's normal setup without enabling broad write access.
- Checkout filters or EOL conversion that change snapshot bytes fail closed. Filesystem metadata beyond ordinary file bytes, executable bits, and symlink targets is not preserved as a Git snapshot.
- A cooperative promotion lock excludes another Council promotion, not a human editor. Pre/post fingerprints detect concurrent changes, but applying multiple files is not an OS-atomic transaction. Keep the primary checkout quiescent during promotion; a mismatch retains inspection state and does not perform an automatic destructive rollback.
- Each stage first runs real native sandbox probes. Candidate writes must succeed; primary, sibling worktree, control directory, journal, and Git metadata writes must fail. Unsupported policy/config combinations stop the run. `codex sandbox` and `codex exec` use their respective supported permission configuration interfaces.
- Read-only critics can read code and produce output; they are not a confidentiality boundary. Host-managed policies and trusted hooks still matter.
- No grep-based write guard or unconditional Stop cleanup hook is installed. Such hooks are not a substitute for sandbox enforcement and could delete another active run.

## Recovery and trace

Runs print their UUID and candidate path at startup. State, the binary patch, validation logs, model output, and timestamped `trace.jsonl` are retained in the common Git directory's `goblin-council/<run-id>` directory. Stage durations are recorded. Treat those files as private repository data.

```sh
"$COUNCIL_PYTHON" "$COUNCIL_PACKAGE/.agents/skills/goblin/scripts/council.py" --repo "$COUNCIL_REPO" recover
"$COUNCIL_PYTHON" "$COUNCIL_PACKAGE/.agents/skills/goblin/scripts/council.py" --repo "$COUNCIL_REPO" status RUN_ID
# After verifying that the run and its child processes are inactive:
"$COUNCIL_PYTHON" "$COUNCIL_PACKAGE/.agents/skills/goblin/scripts/council.py" --repo "$COUNCIL_REPO" abandon RUN_ID
```

Successful promotion removes only that run's worktrees and synthetic refs, retaining its journal. Rejected or interrupted runs remain isolated. SIGINT/SIGTERM terminate child process groups; a lease prevents normal simultaneous ownership. After a host crash or SIGKILL, inspect remaining processes before abandonment. There is no background global garbage collector. `PROMOTING` or `PROMOTION_NEEDS_INSPECTION` requires manual state inspection; abandonment refuses those states. Resume by creating a new run after resolving the interrupted one.

## Verification

See [verification guidance](docs/verification.md) for reproducible checks and evidence limits.

```sh
"$COUNCIL_PYTHON" -m unittest discover -s tests -v
GOBLIN_NATIVE_TESTS=1 "$COUNCIL_PYTHON" -m unittest discover -s tests -v
```

The default suite uses deterministic fake stage outputs for routing and handoff behavior. The opt-in native test executes the real Codex OS sandbox and inspects MCP configuration; it does not consume a model request. Tests cover dirty indexes, binary files, renames/deletions, concurrent primary changes, stale/tampered reports and patches, linked worktrees, EOL mismatch, leases, bounded escalation, and parallel independent critics.

Three acceptance prompts:

1. **Single:** “Use `$goblin` to correct one spelling error in README.md. Preserve all other text.” Scores 0/0/0/0. Expected: SINGLE → primary edit → verification; no child session or transaction.
2. **Cascade escalation fixture:** “Use `$goblin` to repair a local retry-count calculation; zero is valid and negatives must be rejected. In the disposable test harness, supply a first candidate that incorrectly rejects zero.” Scores 2/1/0/1. Expected: draft → frozen candidate → failed test and ESCALATE → sol/high repair → new candidate → passing test and final PASS → promotion. The deterministic harness supplies the flawed candidate; production prompts cannot guarantee a model makes a particular mistake.
3. **Max parallel Critique:** “Use `$goblin-max` to add idempotent processing of concurrent payment callbacks, including duplicate delivery, invalid signatures, and transaction rollback tests.” Scores 3/2/1/3. Expected: high-effort draft → freeze/test → overlapping independent arch/sec reviews → one high-effort synthesized revision → freeze/test → final high-effort judge → promotion only on PASS and passing tests.

## Compatibility references

The source implementation was developed against native Codex CLI `0.163.0-alpha.10.2` and the following documentation (recheck for your installed version):

- [Subagents and custom role configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Permissions and sandbox profiles](https://learn.chatgpt.com/docs/permissions)

Revalidate schema and sandbox behavior after a Codex upgrade. A successful model verdict alone never satisfies the transaction gate.

# Local pre-push gate

This optional installation blocks a push when a prerequisite, policy check, scanner or canonical validation command fails. CI remains required: Git hooks are local, can be removed or bypassed with `--no-verify`, and are not a server-side security boundary.

## Install and update

Review the committed `tools/push_gate/` code and rules first. On a feature branch containing the reviewed commit:

```sh
python3 tools/push_gate/gate.py install
python3 .git/push-gate/gate.py check HEAD
```

If an existing pre-push hook is present, inspect it first, then explicitly use `install --replace`. The installer backs it up in Git metadata, records the old local `core.hooksPath`, and forwards other executable hooks at their original paths. It never edits tracked hook files. The replaced pre-push hook is not chained because it may validate dirty files or invoke unrelated scanners. Its required checks must be represented by the reviewed profile.

To install from another reviewed local commit while preserving a dirty checkout, run that commit's installer with `install --revision <full-commit-id> [--replace]`. It extracts only committed policy. Run the installed copy for checks. In a linked worktree, find its metadata with `git rev-parse --git-path push-gate` rather than assuming `.git` is a directory. Each clone/worktree needs installation. The recorded Python executable must remain installed.

Policy is pinned to committed Git blob IDs. Any change under `tools/push_gate/` requires reviewing and reinstalling the new committed revision before pushing. No environment variable disables checks. Direct pushes to the configured default branch, tags and deletions are blocked. Publish feature branches through the normal reviewed GitHub workflow; do not force-push.

## Prerequisites and checks

Install native Semgrep **1.186.0** as described below and Trivy **0.76.2** from its official distribution; the gate rejects other versions. Also install Git, Python >=3.11 and uv. `tools/push_gate/requirements.txt` pins direct Python validation dependencies; project dependency locks and canonical manifests govern project installs. Transitive validation dependencies are resolved by uv and are not a fully frozen toolchain. Network/package/provider access and sufficient temporary disk space are required for full gate validation. When relevant files exist, install actionlint, ShellCheck, bash and hadolint: all workflows, tracked shell scripts and Dockerfiles are checked. Missing tools fail closed. Scanner overrides inherited from the caller are removed.

Scanner pins refreshed on 2026-11-20 against the latest stable official [Semgrep release](https://github.com/semgrep/semgrep/releases/tag/v1.186.0) and [Trivy release](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2). Python validation dependencies were checked against PyPI on 2026-11-23: Ruff 0.17.6, Coverage 7.17.5, Build 1.6.1, and pip-audit 2.10.1. Coverage 7.17 requires Python 3.11 or newer, raising the optional gate's prerequisite without changing the portable standard-library checks. Refreshing pins requires rerunning validation and reinstalling the committed policy; it does not change scanner rules or severity thresholds. Scanner doubles in the gate regression suite use synthetic version fixtures; `tests/test_scanner_pins.py` checks the real reviewed pins and this guide.

The gate runs `make check` (contracts, adapters, template/workboard and skill
tests), unittest branch coverage and pip-audit. Existing portable checks remain
standard-library-only; the optional push gate adds development tools.

Every profile also validates the gate with Ruff lint/format and its disposable Git regression tests, checks whitespace, and runs the scanners before dependency installation or generated build artifacts. Checks never apply automatic fixes, stage, commit or push. Builds, dependency downloads and generated files stay in disposable snapshots or tool caches. Canonical tools may use caches outside the snapshot.

### Native Semgrep installation

Obtain the official 1.186.0 wheel separately, without installing it or resolving
Python dependencies. The offline, standard-library installer accepts only these
SHA256 identities, supplied for the reviewed release:

| Host / supplied wheel platform | SHA256 |
| --- | --- |
| Native macOS ARM64 | `94b473227b1abe89d104bf87a50e257b3c47f0e09483e4290babc99c01e3aea8` |
| Linux ARM64 / `manylinux_2_34_aarch64` | `bde206edcfa9ac2f5ed5e3fc58d1c675b4e9979a716ecb46b4e60e6bb6a035a4` |
| Linux x86_64 / `manylinux_2_34_x86_64` | `54ebaf79adf4e5855c54d5e4457d8d03f27cc6bf73d79642281790b833d92e4f` |

Linux requires glibc >=2.34. Intel macOS, Rosetta/x86_64 macOS processes,
Windows, musl Linux and other architectures are unsupported by this installer.
The portable `make check` does not require a supported scanner host. Do not use
an older scanner pin or a Python fallback to work around this boundary.

Choose a **new directory** in a trusted, existing parent. For example:

```sh
python3 -I -S tools/push_gate/install_native_semgrep.py /path/to/official-semgrep.whl "$HOME/.local/park-semgrep-native-1.186.0"
export PATH="$HOME/.local/park-semgrep-native-1.186.0/semgrep/bin:$PATH"
semgrep-core -version
PARK_NATIVE_SEMGREP=1 python3 tests/test_scanner_reachability.py -v
```

The installer hashes the complete wheel before ZIP parsing, rejects unsafe or
duplicate member paths and nonregular entries, and bounds archive/payload sizes.
It extracts `semgrep/bin/semgrep-core` plus the recursively linked bundled
libraries only, preserving their wheel paths. It parses ELF64 or ARM64 Mach-O
dependency tables without executing library inspection tools. Unknown or
ambiguous non-system dependencies fail closed. It creates `osemgrep` as a hard
link to that engine, verifies exact raw `semgrep-core -version` output in a clean
environment, and publishes the staged directory only on success. The sorted
`native-install.json` records the source digest and installed file hashes.
An existing destination, including a dangling symlink, is never replaced.

No pip/uv install, dependency resolution or wheel Python imports occur. MCP,
OpenTelemetry API and wcmatch Python packages are absent from this installation.
The old Semgrep venv is **not changed or repaired**: inventory other consumers
before separately retiring it. Keep the native directory first on the actual
push PATH; verify `command -v semgrep-core` and `command -v osemgrep`. The gate
requires both names to resolve to the same file and checks the raw exact version.
It calls `osemgrep scan --experimental`, takes JSON from stdout, and never invokes
`semgrep`, `pysemgrep` or the Python console-script launcher.

The pinned wheels supplied the native engine and its bundled library dependencies on macOS ARM64, Linux x86_64 and Linux ARM64. The engine executed a local scan on macOS ARM64 and emulated Linux x86_64. Linux ARM64 has extraction coverage only. The opt-in macOS run detected matches in all eleven target extensions.
On macOS, verify that mixed-case aliases of `.park-semgrep-ignore` at the root,
as nested files and as directory components block pushes before scanning.
The opt-in test above exercises matching in each declared target extension,
inline Semgrep suppression and nested ignore handling, with Python launchers
replaced by traps. It does not exercise a real push or Trivy's live database.

### Required pre-push pin preflight

Before any push attempt, verify the latest stable releases of pinned security
tools against their official upstream release sources. Update stale pins and
their installation guidance and tests, review compatibility and security impact,
then run the affected checks. Commit the reviewed update and refresh the installed
trusted gate before attempting the push. Verify the executables selected by the
actual push environment match the committed pins. A package-manager version alone
is insufficient when a CLI delegates to another executable on PATH.

Do not downgrade tools to satisfy stale pins, bypass hooks, or weaken scanner
rules/severity thresholds. If release verification, a safe upgrade or required
validation is unavailable, report the blocker before pushing. This preflight is
an agent workflow requirement, not a claim that the hook queries upstream releases.

## Security rules and reproducibility

### Scanner dependency remediation (2026-11-20)

[PARK issue #16](https://github.com/sodejm/portable-agent-repository-kit/issues/16)
tracks eight advisories in the old Python scanner environment: five in
`mcp==1.29.0`, two in `opentelemetry-api==1.37.0`, and one in `wcmatch==8.5.2`.
Native-only installation removes those packages from the supported scanner
setup. It does not patch or erase a previously installed venv, establish the
absence of native engine/library vulnerabilities, or audit unrelated tools.

The earlier five-advisory acceptance, its evidence and its November 20 invalidation
are retained in the [historical assessment](security/SCANNER_REACHABILITY.md).
It does not authorize continued use of the eight-advisory venv or transfer to
generated projects. There are no incompatible dependency overrides, CVE
suppressions, reduced severities or audit exclusions. The validation-environment
pip-audit remains separate from scanner provenance and native dependency review.

### Snapshot scan coverage

`semgrep.yml` is a committed, reviewed small ruleset covering high-confidence Python command/deserialization hazards, JavaScript/TypeScript dynamic execution and TLS verification, Go shell/TLS hazards, shell TLS bypasses, workflow insecure Node overrides and Terraform TLS bypasses. Language-specific AST rules are used where supported; generic shell/workflow/HCL rules deliberately have narrower coverage. Rules are local; no mutable registry rules are downloaded. Inline Semgrep suppression and repository ignore files cannot hide findings. The native ignore option takes a basename: the gate reserves `.park-semgrep-ignore` as every path component at every depth, rejects committed collisions (including case-folded aliases) before scanning, and creates its own empty root file. Targets retain their `./` prefix. Missing/malformed JSON and any reported parser/analysis error fail the gate. This ruleset is not an exhaustive vulnerability audit.

Trivy scans the complete committed filesystem for vulnerabilities, secrets and misconfiguration, including development dependencies. HIGH and CRITICAL findings block, including suppressed findings returned by Trivy. The runner supplies empty config/ignore paths, rejects inline Trivy suppression and does not use `--ignore-unfixed`. Secret matches are never printed by the scanner wrapper; only finding IDs and paths appear. Raw reports are temporary and removed after execution. Trivy's vulnerability database and official misconfiguration checks update independently of the pinned executable. Results are reproducible for the same rules, tool versions and feed/cache state, not forever across changing advisories. An unavailable feed or scanner error blocks; do not suppress findings to publish.

## Branch-wide test development

The actual push URL's configured default branch is fetched into the disposable clone. The full branch is compared with its merge base, including changes already pushed earlier. Each affected policy area needs a changed executable assertion in its recognized test paths. Python assertions are compared as AST nodes; JavaScript/TypeScript/Go/BDD and Terraform assertions use limited syntax heuristics. Comments, deleted assertions and unchanged tests do not satisfy this check.

Reviewers must establish that assertions exercise the changed behavior and are meaningful: the heuristic can accept irrelevant assertions and can reject valid unconventional tests. This is evidence of test updates alongside implementation, **not proof of test-driven development**, chronological test-first work or complete coverage.

For a genuinely non-behavioral implementation change, commit `push-gate-nonbehavioral.json`, mapping the exact path to `before_sha256`, `after_sha256` and a concrete reason of at least 40 characters. Hash the UTF-8 decoded base and pushed file contents as used by the runner (an absent file is the empty string). Use only for formatting, comments or equivalent mechanical changes after review. Any content change invalidates the hashes; refresh or remove stale entries when rebasing. Behavioral changes must have tests; there is no blanket skip flag. The authoritative patterns are in `policy.json`.

## Exact commit and trust boundary

Git supplies each pushed object ID on pre-push stdin. The gate validates that commit, not HEAD, the index or dirty files. It clones without hardlinks, checks out the exact SHA with hooks disabled and enumerates every Git tree blob, including export-ignored files. Scanners run before generated files are created. Private untracked files are not copied or scanned. Symlinks, submodules, non-UTF-8/newline filenames and unsupported refs fail closed rather than silently omitting content. Every pushed branch tip is checked; intermediate historical commits are not individually scanned. Review outgoing history before first publication or when secrets were previously committed.

Repository validation executes committed code with the user's permissions. The disposable directory is **not an OS sandbox**: HOME, PATH, SSH agent and tool caches remain available for dependency access. Review untrusted commits before installing or running; use a separate restricted machine/container for hostile code. The local trusted policy copy prevents a proposed commit from silently weakening its installed checks, but a user controlling the local machine can bypass it. No production cloud credentials are needed by the profiles. CI and review remain the authority for merge/release.

## Recovery and limitations

A failure leaves remote refs unchanged. Resolve the named finding/check or install its prerequisite, commit the fix with relevant tests, then retry. For detailed canonical output, rerun the named command in a separate clean clone of the failed SHA. Do not run automatic fixes from the hook or print raw secret reports. Most subprocesses have no global timeout; network-dependent checks can be slow or interrupted, and interruption fails the push. Trivy has a 15-minute scan timeout. Remote default-branch movement after it is fetched requires CI to reconcile; validation is of the exact tip against the observed baseline.

To restore the prior hooks configuration:

```sh
python3 .git/push-gate/gate.py uninstall
```

Use `git rev-parse --git-path push-gate` in worktrees. Recovery refuses if another tool changed hooksPath after installation; reconcile the recorded installation JSON and backup manually. Backups remain for review. An emergency bypass requires a separately reviewed decision and equivalent CI evidence; it does not constitute a passing local gate. Do not remove rules, lower severities or ignore findings to make a baseline green.

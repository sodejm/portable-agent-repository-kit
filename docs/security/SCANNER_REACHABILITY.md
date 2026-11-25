# Native scanner remediation and historical assessment

## Current installation boundary (2026-11-24)

The supported scanner setup now extracts the pinned official Semgrep 1.187.0
native engine and its linked bundled libraries without installing wheel Python
code or resolving Python dependency packages. The offline installer verifies the
complete wheel SHA256 before parsing and fails closed on unsafe entries, unknown
dependencies, unsupported hosts or an inexact raw engine version. See the
[installation guide](../LOCAL_PUSH_GATE.md#native-semgrep-installation) for the
three artifact digests, platform requirements and migration procedure.

The gate probes `semgrep-core -version` directly, requires `osemgrep` to be the
same file, and uses `osemgrep scan --experimental` with stdout JSON. There is no
Python launcher/fallback in this supported path. Local rules, strict analysis,
inline suppression protection, environment sanitization, Trivy's full scan,
HIGH/CRITICAL threshold and validation audits remain enabled. The native ignore
basename `.park-semgrep-ignore`, including case-folded aliases, is reserved in
every path component at every tree depth; only the gate's empty root file may
supply that policy. Missing or malformed reports fail closed.

This addresses all eight Python scanner-environment advisories at their source:
the affected packages are neither installed nor loaded by the new scanner.

| Old Python package | Advisories removed from the new installation |
| --- | --- |
| `mcp==1.29.0` | CVE-2026-59951, CVE-2026-116684, CVE-2026-116685, CVE-2026-116686, CVE-2026-115563 |
| `opentelemetry-api==1.37.0` | CVE-2026-114603, CVE-2026-126360 |
| `wcmatch==8.5.2` | CVE-2026-132276 |

This is a **new installation**, not a patch to an old venv. The old environment
retains its findings until separately retired; no CVE is suppressed or audit
result reclassified. Neither Python package audits nor this extraction establish
the safety of native binaries, bundled/system libraries, parser inputs, other
tools or a compromised local account. The supplied digests pin source bytes;
they are not an independent provenance proof. PATH, tools and installation parent
directories must remain trusted. Review new releases and artifacts again on update.

Ordinary regressions use synthetic ELF/Mach-O wheels and scanner doubles. They
cover selected dependency closure, rejected ZIP paths/types/digests/platforms,
atomic failure cleanup, same-file dispatch, exact version checks, stdout JSON,
malformed/missing reports, findings/errors, reserved names and mixed-case aliases
at the root, in nested files and in directory components, and remote update
prevention. They do not execute official wheel payloads or query feeds.
`PARK_NATIVE_SEMGREP=1 python3 tests/test_scanner_reachability.py -v` additionally
checks an installed native engine against synthetic matching controls for all
declared target extensions, inline suppression and nested ignores, with Python
launchers trapped. It is opt-in and does not validate a real push or Trivy feed.

On macOS ARM64 the 1.187.0 engine detected the expected findings in all eleven test files with Python fallback traps active. For release 1.186.0, the wheels supplied the native engine and its bundled library dependencies on macOS ARM64, Linux x86_64 and Linux ARM64. The engine executed a local scan on macOS ARM64 and emulated Linux x86_64. Linux ARM64 has extraction coverage only. The macOS test detected matches across the declared extensions with Python launchers replaced by traps. [Issue #16](https://github.com/sodejm/portable-agent-repository-kit/issues/16) tracks remediation and gate validation.

## Historical Python-environment assessment (superseded)

The remainder preserves the earlier decision and its finite observations. Its
commands and fallback profile describe the historical revisions, not the current
supported setup. The old profiler has been replaced by native-only regressions;
reproducing its observations requires the historical test source and venv.

The 2026-11-20 update to Semgrep 1.186.0 triggered the expiry condition below. Its isolated installation resolves the same MCP and OpenTelemetry API versions. The November 20 audit found eight advisories in three packages. The additional findings were CVE-2026-115563 in MCP, CVE-2026-126360 in OpenTelemetry API and CVE-2026-132276 in wcmatch 8.5.2. The existing opt-in profile passed on the refreshed scanner, with ten positive controls and zero observed calls to those instrumented paths during the synthetic scan. Its coverage excludes any additional paths implicated by the new findings. The repository maintainer is tracking reassessment and the decision for this installation in [PARK issue #16](https://github.com/sodejm/portable-agent-repository-kit/issues/16).

## Decision and expiry

**Accepted on 2026-11-04 for PARK's optional local push gate only.** The owner
explicitly selected **“Accept scoped exception”** after receiving the five-CVE
reachability result, operating limits, expiry and remediation triggers in the
active task. This records that human risk decision, not independent human code
review, manual inspection of every dependency, or a vulnerability-free toolchain.

Acceptance expires **2026-12-04**, or on a relevant tool/configuration change,
whichever comes first. The repository maintainer owns remediation and must
reassess before the next push after expiry or a trigger below. There is no
automatic renewal. Other approval and merge requirements remain unchanged.
This is PARK-source evidence: copying this file into a generated project does not
transfer the owner's acceptance. Each consumer needs its own assessment and decision.

The reviewed gate implementation is commit
`791bd551692122e7560610dc7025b5bd397b03b3`, file `tools/push_gate/gate.py`
(Git blob `473a8239c8808413bfe0e06ceb43e1490d51fe72`). The acceptance adds evidence
and regression tests; it does not change that gate implementation.

## Scope and threat boundary

The finding is **not reachable in the reviewed configuration**, not “the packages
are unaffected.” The separately installed Semgrep 1.183.0 environment contains
`mcp==1.29.0` and `opentelemetry-api==1.37.0`. Their five medium-severity advisories
remain visible in complete dependency audits. Semgrep's constraints currently
exclude the patched versions; no incompatible override or CVE suppression is used.

Acceptance requires all of these conditions:

- Run only the gate's fixed `semgrep --version` and local `semgrep scan` argv,
  with committed local rules, `--metrics=off`, no tracing and no MCP options.
- Preserve `clean_environment()` in `tools/push_gate/gate.py`. It removes inherited
  MCP, Semgrep, OpenTelemetry and Python injection settings. `PATH` and `HOME`
  remain trusted operator inputs; this is not a sandbox or a defense against a
  compromised local interpreter, executable, package, home directory or account.
- Put the reviewed scanner environment's `bin` directory first on the push PATH.
  Verify **both** `semgrep` and `pysemgrep` resolve there and report 1.183.0. The
  native launcher can find `pysemgrep` by PATH; the gate's version check alone
  does not establish the fallback's identity. Review the packaged `semgrep-core`
  installation too; no unreviewed wrapper or replacement binary is covered.
- Treat scanned files as parser inputs, not executable Python. The gate prefixes
  every target with `./`, so filenames cannot become command options.
- Do not reuse this exception for an MCP client/server, `semgrep mcp`, `semgrep ci`,
  tracing-enabled scanning, another project, or another scanner installation.

## Source-to-sink assessment

Installed-package paths below are relative to `site-packages`, not repository
files. Analysis traced the affected paths and relevant top-level imports in the
Python sources of the exact versions above; it was not an audit of every imported
module. Import-time activation of the monitored entries was not observed in the
probe. Independent automated Opus 5.5/high review agreed with all
five scoped conclusions; neither automated review constitutes human inspection.

| Advisory | Required entry point and sink | Why PARK does not reach it |
| --- | --- | --- |
| [CVE-2026-59951](https://github.com/advisories/GHSA-84m7-p3x7-pcfv) | Stateful MCP StreamableHTTP server retaining sessions in `mcp/server/streamable_http_manager.py` | `semgrep/commands/mcp.py` builds and runs this server only through the MCP command. `scan` never constructs its session manager or accepts MCP requests. |
| [CVE-2026-116684](https://github.com/advisories/GHSA-w4fh-qvv9-3v23) | Server bearer authentication accepting the wrong token audience in `mcp/server/auth/middleware/bearer_auth.py:54–73` | No MCP HTTP server, authentication middleware invocation or inbound bearer-token path exists in this scan mode. |
| [CVE-2026-116685](https://github.com/advisories/GHSA-5h93-6whr-6q8j) | MCP HTTP/SSE/OAuth clients following cross-origin redirects; `mcp/shared/_httpx_utils.py` creates a redirect-following client | The Semgrep scan path does not instantiate or invoke the SDK's clients, transports or OAuth provider. Loading their definitions is not a client connection. |
| [CVE-2026-116686](https://github.com/advisories/GHSA-rwrf-2pqf-9j8j) | `mcp/client/session.py:417–437`, validating server-supplied tool output schemas with remote `$ref` resolution | No `ClientSession.call_tool` or tool-result validation occurs. Repository source/rules are not MCP tool results or server-provided schemas. |
| [CVE-2026-114603](https://github.com/advisories/GHSA-xcq7-p3pf-p88h) | Untrusted `tracestate` passed through `TraceContextTextMapPropagator.extract` to `opentelemetry/trace/span.py`, `TraceState.from_header` | Scan's `--trace` default is false. `Telemetry.configure` returns before instrumentation/extraction. Additionally, Semgrep's own `telemetry.py:397–405` carrier contains only `traceparent`, not `tracestate`; inherited trace/propagator settings are removed. No inbound server-header path exists. |

The native launcher in `semgrep/console_scripts/entrypoint.py` executes
`semgrep-core` and can fall back to `pysemgrep`. Python CLI startup imports the
MCP command and dependency definitions even for `scan`; this analysis does **not**
rely on claiming MCP is never imported. The imported modules do not activate the
affected server/client paths. `semgrep/commands/scan.py:295–299,904–906` controls
tracing; `semgrep/telemetry.py:349–350` returns early when it is disabled.

## Behavioral evidence and reproduction

`tests/test_scanner_reachability.py` adds two dependency-free regressions to the
ordinary suite: the complete declared scanner/version call list with exact Semgrep
argv, and the environment allowlist, including seeded
MCP, tracing and Python-injection settings. Any change to these boundaries requires
review of this acceptance, not merely updating the expected values.

At the historical revision, the optional real-library probe used the reviewed
scanner environment's Python (`SCANNER_ENV` denotes that old local directory):

```sh
PARK_SCANNER_REACHABILITY=1 "$SCANNER_ENV/bin/python" tests/test_scanner_reachability.py -v
```

On native arm64 macOS with Python 3.14.9, all three tests passed. The probe:

1. Uses the gate's actual argv builder and environment sanitizer, committed local
   rules, an empty temporary HOME and synthetic Python input that raises if run.
2. Invokes the native `semgrep` launcher. A temporary `pysemgrep` wrapper profiles
   its real Python fallback; it does not change installed dependency files or
   replace the observed functions. The test fails if fallback is not observed.
3. Confirms the synthetic file was scanned without findings/errors, the scan
   callback ran once and `Telemetry.configure` received `False`.
4. Observes zero calls to ten selected entries: the session-manager constructor,
   bearer authentication, MCP HTTP-client helper, SSE and both StreamableHTTP
   transports, OAuth flow, tool call, tool-result schema validator and
   `TraceState.from_header`.
5. In a **separate process**, invokes each monitored entry once with bounded,
   local positive controls. All ten were observed, without listening, sending
   requests, fetching external schemas or using denial-of-service payloads.

Five positive controls execute with harmless local inputs; the transport, OAuth
and tool-call controls stop at their profiled entry before their bodies perform
I/O. A control-process network audit hook also fails on connection, bind, DNS or
datagram attempts. The scan profiler is passive. Each fallback writes a unique
report, and the test rejects zero or multiple fallback reports rather than letting
a later process overwrite earlier evidence.

The positive-control process is separate so its imports cannot hide scan-startup
side effects. Actual `semgrep` and `pysemgrep` version checks also returned 1.183.0
using the sanitized environment with the reviewed bin directory first. Those
`--version` executions were not profiled; their non-reachability conclusion rests
on source tracing, not the scan's runtime observations.

These are finite observations, not exhaustive proof. The probe profiles Python
calls in its process and new Python threads, not native subprocess internals;
it uses a synthetic target and empty HOME. Source tracing supplies the argument
for other source files being data rather than MCP/telemetry inputs. No conclusion
about unrelated native-engine vulnerabilities, all Semgrep modes, arbitrary local
plugins, hostile local state or other platforms is implied.

## Remediation and invalidation

Keep this acceptance visible alongside the raw audit findings. Do not add
`pip-audit --ignore-vuln`, lower scanner severities, disable dependency audits or
describe the environment as having zero CVEs. A complete scanner-environment
audit can still exit nonzero for these accepted findings.

Reassess immediately when any of the following changes:

- Semgrep, its dependencies, native binary, installation provenance or executable
  selection; review a new stable Semgrep release before the next push.
- Scanner argv, subcommand, rules source, environment allowlist or fallback
  dispatch; enabling tracing, MCP, CI mode or remote tool/schema input.
- Repository/check/hook code starts using these packages, or the scanner
  environment is reused outside the accepted local-scan path.
- An advisory gains an import-time path or other reachable trigger, or new
  evidence contradicts the source trace or behavioral tests.

Preferred remediation: use a compatible upstream Semgrep release that permits
MCP >=1.30.0 and OpenTelemetry API >=1.45.1, then audit the **scanner environment**
as well as PARK's validation environment. If future work adds an MCP server,
upgrading alone does not resolve CVE-2026-116684: configure resource/audience
validation as required by that advisory. Do not force unsupported transitive
versions merely to obtain a clean audit.

After remediation, rerun the reachability regressions, canonical checks and exact
committed gate validation, update this record and the threat model, and retire
the acceptance only when its findings are actually resolved. Remediation owner:
repository maintainer; reassessment deadline: **2026-12-04 at the latest**.

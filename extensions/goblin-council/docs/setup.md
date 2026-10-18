# Set up Goblin Council for Codex

This optional package currently targets Codex on Unix, with Python 3.11+ and Git.
Keep the entire package at a stable path. It uses only Python's standard library
and the authenticated native Codex CLI. No pip install, MCP server or proxy is
required. Review the [model and platform support](../README.md) first.

## Install

From the PARK repository root, inspect and then run:

```sh
python3 extensions/goblin-council/install.py --dry-run
python3 extensions/goblin-council/install.py
```

This registers `goblin` and `goblin-max` symlinks under `~/.agents/skills`.
It does not overwrite an existing skill, change config, install hooks, or move
credentials. Existing installations from another checkout are refused. Remove
those through their original installer after inspecting ownership, or use a
separate destination. For project-only discovery:

```sh
python3 extensions/goblin-council/install.py --skills-dir /path/to/project/.agents/skills
```

Refresh Codex skill discovery or start a new session. Invoke `$goblin` with a
bounded task and acceptance criteria; use `$goblin-max` explicitly for max mode.
Moving/deleting the package breaks the links. Keep the checkout trusted and
review package updates because installed skills follow its files.

The bundled `.codex/config.toml` is an optional example, not an installation
requirement. The helper reads bundled role files directly and sets session
permissions itself. Do not replace an existing global config. Native role TOMLs
alone do not establish read-only reviewer isolation.

## Preflight and first run

1. Confirm `python3 --version`, `git --version`, and `codex --version`. Authenticate
   through Codex's normal flow. The source targets CLI `0.163.0-alpha.10.2`;
   newer or older versions require compatibility verification.
2. Check that the local `$CODEX_HOME/models_cache.json` (normally under `~/.codex`)
   includes the configured model/effort pairs. The helper checks them before
   launches and fails closed. Refresh via your normal Codex startup/catalog flow
   if stale. There is no silent model substitution or alternate-provider support.
3. Run the deterministic checks described in [verification](verification.md).
   Then run the opt-in native sandbox test on the intended host.
4. Start with a disposable committed Git repository. Supply a contract based on
   [example-task.json](example-task.json), stored outside the target checkout.
   Follow the [CLI examples](../README.md). Real Cascade/Critique runs consume
   model usage; deterministic tests and native probes do not call a model.

Use the repository's required validation runtime. Offline dependencies must
already be available; the helper does not enable dependency downloads. A target
needs an initial commit. Unsupported Git layouts and filters fail closed.
Single delegates execution to the current primary thread and cannot change that
thread's selected model or effort automatically.

## Remove or troubleshoot

```sh
python3 extensions/goblin-council/install.py --uninstall --dry-run
python3 extensions/goblin-council/install.py --uninstall
```

Use the same `--skills-dir` as installation. Removal only deletes links pointing
to this package. It leaves user config, package files, and run journals intact.

A model/catalog error requires an available configured route or a reviewed route
change. A sandbox probe failure means the host is unsupported until the native
permissions/configuration issue is resolved; do not disable the probe. Linux
needs the same native checks; Windows is unsupported. PARK's baseline skips this
optional suite on Windows or Python below 3.11 and reports the skip.

For failed or interrupted runs, use `recover` and `status` before `abandon`, as
shown in the [recovery guide](../README.md#recovery-and-trace). Keep the primary
checkout quiescent during promotion. Inspect processes before cleanup; do not
install a global Stop-hook garbage collector. Treat journals as private data.

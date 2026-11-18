# GreenDevelopment validation — 0.3.4

Executed on 2026-11-18. Version 0.3.4 fixes false blocks of file reading/search commands. It has not been published. Native host evidence from 0.3.3 remains recorded below; the new executable package requires a fresh hook trust review. Final local installation receipts are kept outside the installed package to preserve its fingerprint.

## Read-only guard fix

The previous guard searched the entire command text, so data such as a filename or search pattern could look like a native build. Version 0.3.4 first recognizes a limited read-only shell subset. Quoted/escaped data and reader chains are handled without executing shell text. Every segment must qualify. Unknown syntax/options, executable modes and expansions receive no exemption and continue through the existing native-build/cleanup guard.

New decision tests reproduced the false positives before the fix. They cover readers, quoted data, pipes/chains, direct native builds, global cleanup, managed platform profiles, command substitutions and executable reader options. Independent review found argument-consumption and shell-expansion bypasses in the initial exemption; failing regressions reproduced them and the final implementation closes them. Unknown `rg` options prevent exemption rather than guessing their argument grammar. The reviewer approved the fixes.

## Plugin immutability fix

The 0.3.2 host run created Python bytecode in the cached plugin when the runner was invoked without `-B`. A fresh native hook inventory then reported modified trust. A failing integration regression reproduced the new files in a temporary installed copy. Version 0.3.3 disables bytecode before importing local modules and includes `-B` in startup guidance. The regression now compares all installed file names and contents before/after an ordinary invocation without `-B`.

Package updates, including documentation, may require renewed hook trust. Keep final host receipts outside the installed package; never edit trust records or bypass the host check.

## Repository preparation

GreenDevelopment 0.3.2 fixes two issues found during real local installation:

- The tested Codex client ignored hooks when the root portable `plugin.json` existed. Minimal host probes loaded them only with `.codex-plugin/plugin.json` as the sole manifest. Native `plugin/read`, `skills/list` and `hooks/list` now discover the installed package: all three skills enabled, all seven hooks enabled, no loading errors.
- Startup guidance omitted the hook's state directory. A failing native regression reproduced normal tool execution writing to the standalone store instead. Startup now supplies `run --state-dir ... --session ...`; the regression passes with `PLUGIN_DATA` deliberately absent from the tool environment.

The local marketplace and plugin were registered with the supported `codex plugin` commands. After the user reviewed the hooks, native `hooks/list` confirmed all seven as **trusted** and enabled. An ephemeral Codex app-server session then exercised the installed plugin without trust or sandbox bypass flags.

LICENSE is the unmodified official Apache License 2.0 text, SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`. The canonical manifest and all three skills declare `Apache-2.0`; source headers and NOTICE identify the copyright holder. The Git repository has no configured remote at handoff. GitHub Actions configuration was parsed locally; hosted CI has not run.

## Executed checks

- **74/74 tests passed**, including ten guard tests with parameterized decisions, seven native subprocess integration cases and 16 device reuse/app-preservation cases. Command: `DEV_WORKFLOW_NATIVE_SMOKE=1 python3 -B -m unittest discover -s tests -v`. The suite ran through the resource runner; its receipt reported successful cleanup and zero remaining work bytes.
- Native cases covered successful artifact retention, failure exit status, timeout, SIGTERM, and a background worker left by the main command. Task work was removed, retained evidence remained, and the unrelated control process survived.
- The 0.1.0 live Docker check passed **three runs**: a container command, a small `FROM scratch` image build, and Compose with a named volume/network. Each run's resources were removed. A separate control container, network and volume remained intact, as did the pre-existing base image. The test then removed its own control fixtures. An explicitly selected local image ID was used; no base image was pulled. Docker adapter behavior is unchanged through 0.3.2; its unit regressions passed again. Command: `DEV_WORKFLOW_DOCKER_SMOKE=1 DEV_WORKFLOW_SMOKE_IMAGE=LOCAL_IMAGE_ID python3 -B tests/docker_smoke.py`.
- New selectors read the actual installed Android/iOS inventories and selected existing devices, both without filters and with exact image/profile or runtime/type filters. The check explicitly prohibited native creation, boot and shutdown. It created no extra devices and removed its temporary state.
- Isolated creation tests proved one missing definition is created and the next call reuses it. Existing names/creators do not affect reuse. Busy/leased devices, uncertain Android metadata and numeric hardware indexes cannot trigger duplicates. Existing apps remain installed and package-ID collisions block test execution. A focused independent review identified the numeric-index issue; the fix passed its regression test.
- All **seven hook events** were invoked through the script's JSON stdin/stdout interface. Startup context, direct Gradle-command denial, completion and interrupt payloads matched their contracts.
- The official local skill validator accepted all **three skills**. Metadata, the canonical manifest, hook paths/timeouts, Python syntax, internal documentation links and absence of project-specific/local installation paths were checked.
- Source/plugin ZIPs were checked for expected contents, unsafe paths, CRC integrity and byte-for-byte agreement with committed source. Only the source archive includes the repository marketplace and CI configuration; neither contains `.git` or runtime state. The extracted runner's CLI loaded successfully.

## Installed-host verification on 0.3.3

An ephemeral Codex session (CLI 0.169.0-alpha.11.1) explicitly loaded all three installed skills and exercised normal tool execution. The host emitted successful `SessionStart`, `PreToolUse` and `Stop` dispatch events. The verification harness observed the following independently of the agent's final message:

- `PreToolUse` denied one direct `./gradlew test` attempt against a harmless fake executable; its execution marker was absent.
- The generic runner preserved the state directory/session from startup, exited successfully, removed its work directory, reported zero remaining bytes and retained the requested artifact. Its content was checked.
- The last tool command created two signed inactive test records. The agent did not invoke recovery. The real `Stop` hook automatically cleaned only the record for that session; the other session's work still existed. The harness then cleaned its own control fixture.
- Session shutdown produced the expected `SessionEnd` marker in the same plugin state store.
- All installed file names and contents were identical before and after the host test. A fresh app-server process still reported all seven hooks as trusted and all three skills enabled. An additional ordinary invocation without `-B` also preserved every installed file and all seven native hook fingerprints.
- The short-lived app-server exited. No Android/iOS devices or Docker workloads were launched for this host check; shared caches and unrelated resources were untouched.

The seven JSON contracts also passed against the installed scripts. `Interrupt`, `SubagentStart` and `SubagentStop` have contract coverage here, but their native host event dispatch was not separately exercised. No redundant agents were spawned to claim broader coverage.

## Safety coverage

Tests reject adopting unowned directories, tampered records, symlinks, replaced work directories, missing required retained outputs, uncertain process activity, active-run recovery, changed device leases, Android process reuse, iOS boot reuse, wrong AVDs, foreign Docker labels, daemon changes, external volumes/binds, Compose option overrides and shared Gradle daemon shutdown. A fresh independent review found five issues in those areas; the fixes have regression coverage.

The cleaner operates on registered resources and preserves shared caches, source repositories, device definitions/runtimes and base images. Uncertain ownership or activity blocks cleanup and is reported; it never becomes a successful cleanup receipt.

## Limits of this evidence

Android/iOS creation, boot and app cleanup were tested with controlled command responses. Actual inventory parsing and compatibility selection were checked read-only against the installed native tools. No real device was created/booted and no Gradle application build or Xcode application build was run for this package. Installed `simctl listapps`, `simctl create` and catalog interfaces were inspected. A project's first native use still needs its normal platform verification.

Actual Codex discovery, installation, persisted trust and the host paths described above were exercised. Direct JSON invocation of the other events validates their scripts, not native dispatch. Hook trust may need review again after future executable changes. Disabled hooks, tools outside their coverage, deliberately detached workers and arbitrary scripts that bypass the runner are outside the enforcement guarantee.

The guard recognizes a limited read-only subset rather than the complete shell language. Recognized file searches/readers no longer trigger on native-tool names used as data. Unsupported syntax, unknown reader options, heredocs and executable scripts can still produce conservative blocks. Use normal supported file readers or dedicated editing tools for those tasks; do not bypass a denied build or cleanup action.

SIGKILL or host failure can interrupt cleanup; signed records support later scoped recovery. A live orphan or lost device-instance proof remains blocked to protect other work. No machine-wide cleanup was performed.

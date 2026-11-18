# GreenDevelopment validation — 0.3.2

Executed on 2026-11-18. GreenDevelopment 0.3.2 is installed and enabled in the local Codex profile. It has not been published. Automatic host dispatch is pending explicit hook trust; see the limitations below.

## Repository preparation

GreenDevelopment 0.3.2 fixes two issues found during real local installation:

- The tested Codex client ignored hooks when the root portable `plugin.json` existed. Minimal host probes loaded them only with `.codex-plugin/plugin.json` as the sole manifest. Native `plugin/read`, `skills/list` and `hooks/list` now discover the installed package: all three skills enabled, all seven hooks enabled, no loading errors.
- Startup guidance omitted the hook's state directory. A failing native regression reproduced normal tool execution writing to the standalone store instead. Startup now supplies `run --state-dir ... --session ...`; the regression passes with `PLUGIN_DATA` deliberately absent from the tool environment.

The local marketplace and plugin were registered with the supported `codex plugin` commands. The latest observed hook trust status is **untrusted**. Registration and enabled state do not prove execution. No trust bypass was used.

LICENSE is the unmodified official Apache License 2.0 text, SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`. The canonical manifest and all three skills declare `Apache-2.0`; source headers and NOTICE identify the copyright holder. The Git repository has no configured remote at handoff. GitHub Actions configuration was parsed locally; hosted CI has not run.

## Executed checks

- **63/63 tests passed**, including six native subprocess integration cases and 16 new device reuse/app-preservation cases. Command: `DEV_WORKFLOW_NATIVE_SMOKE=1 python3 -B -m unittest discover -s tests -v`.
- Native cases covered successful artifact retention, failure exit status, timeout, SIGTERM, and a background worker left by the main command. Task work was removed, retained evidence remained, and the unrelated control process survived.
- The 0.1.0 live Docker check passed **three runs**: a container command, a small `FROM scratch` image build, and Compose with a named volume/network. Each run's resources were removed. A separate control container, network and volume remained intact, as did the pre-existing base image. The test then removed its own control fixtures. An explicitly selected local image ID was used; no base image was pulled. Docker adapter behavior is unchanged through 0.3.2; its unit regressions passed again. Command: `DEV_WORKFLOW_DOCKER_SMOKE=1 DEV_WORKFLOW_SMOKE_IMAGE=LOCAL_IMAGE_ID python3 -B tests/docker_smoke.py`.
- New selectors read the actual installed Android/iOS inventories and selected existing devices, both without filters and with exact image/profile or runtime/type filters. The check explicitly prohibited native creation, boot and shutdown. It created no extra devices and removed its temporary state.
- Isolated creation tests proved one missing definition is created and the next call reuses it. Existing names/creators do not affect reuse. Busy/leased devices, uncertain Android metadata and numeric hardware indexes cannot trigger duplicates. Existing apps remain installed and package-ID collisions block test execution. A focused independent review identified the numeric-index issue; the fix passed its regression test.
- All **seven hook events** were invoked through the script's JSON stdin/stdout interface. Startup context, direct Gradle-command denial, completion and interrupt payloads matched their contracts.
- The official local skill validator accepted all **three skills**. Metadata, the canonical manifest, hook paths/timeouts, Python syntax, internal documentation links and absence of project-specific/local installation paths were checked.
- Source/plugin ZIPs were checked for expected contents, unsafe paths, CRC integrity and byte-for-byte agreement with committed source. Only the source archive includes the repository marketplace and CI configuration; neither contains `.git` or runtime state. The extracted runner's CLI loaded successfully.

## Safety coverage

Tests reject adopting unowned directories, tampered records, symlinks, replaced work directories, missing required retained outputs, uncertain process activity, active-run recovery, changed device leases, Android process reuse, iOS boot reuse, wrong AVDs, foreign Docker labels, daemon changes, external volumes/binds, Compose option overrides and shared Gradle daemon shutdown. A fresh independent review found five issues in those areas; the fixes have regression coverage.

The cleaner operates on registered resources and preserves shared caches, source repositories, device definitions/runtimes and base images. Uncertain ownership or activity blocks cleanup and is reported; it never becomes a successful cleanup receipt.

## Limits of this evidence

Android/iOS creation, boot and app cleanup were tested with controlled command responses. Actual inventory parsing and compatibility selection were checked read-only against the installed native tools. No real device was created/booted and no Gradle application build or Xcode application build was run for this package. Installed `simctl listapps`, `simctl create` and catalog interfaces were inspected. A project's first native use still needs its normal platform verification.

Actual Codex discovery and local installation were exercised. Automatic hook dispatch is still unverified because the seven hooks need explicit trust. The computer-use tool denied access to Codex settings; trust confirmation was requested from the user. A prepared ephemeral host smoke test requires persisted trust and checks PreToolUse denial plus automatic Stop cleanup while preserving another session. Direct JSON invocation validates the scripts, not automatic host dispatch. Disabled hooks, tools outside their coverage, deliberately detached workers and arbitrary scripts that bypass the runner are outside the enforcement guarantee.

SIGKILL or host failure can interrupt cleanup; signed records support later scoped recovery. A live orphan or lost device-instance proof remains blocked to protect other work. No machine-wide cleanup was performed.

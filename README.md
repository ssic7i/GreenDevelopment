# GreenDevelopment

Reusable development rules and resource cleanup for Codex: focused changes, fewer repeated reads, conditional delegation, required quality checks, and Android/iOS/Docker cleanup without repeated project instructions.

**Version:** 0.3.3 · **License:** [Apache 2.0](LICENSE) · **Platforms:** macOS/Linux; iOS needs macOS/Xcode.

## Included

| Skill | Responsibility |
| --- | --- |
| `development-workflow` | Planning, implementation, dependencies, Git and token/resource economy. |
| `verification` | TDD, risk-based coverage, reusable evidence and delivery gates. |
| `resource-lifecycle` | Managed builds/tests, device reuse, retained artifacts and verified cleanup. |

Shared Python scripts do the work; seven hooks provide startup guidance, guard common unmanaged commands and recover interrupted runs. No MCP server or third-party Python packages are required.

## Install

Requirements: Python 3.11+, Git, `ps`, `lsof`, and Codex with local plugins/hooks. Android SDK, Xcode and Docker are needed only for their respective workloads.

From this repository's root:

```sh
codex plugin marketplace add .
codex plugin add green-development@green-development
```

Restart the desktop app or start a fresh CLI session. Review and trust the hooks in Settings → Hooks or `/hooks`. Confirm all three skills appear and startup guidance identifies GreenDevelopment.

[Installation, GitHub sources, updates and removal](docs/INSTALL.md)

## Use

Give Codex an ordinary development task, for example:

> Fix the failing tests. Use GreenDevelopment and finish with verification evidence and a cleanup receipt.

Or select a skill explicitly:

> Use `$resource-lifecycle` to run the Android tests. Reuse an existing compatible emulator; create one only if the required configuration is missing.

The agent chooses applicable skills, reads relevant references, groups dependent build/test steps, retains required outputs and checks the cleanup result. Resource limits change scheduling, not required quality coverage.

[Commands, platform examples, artifacts and recovery](docs/USAGE.md)

## Resource policy

- Inspect all existing compatible devices, regardless of creator/name; reuse an idle one first.
- Create one missing configuration from an installed image/runtime and keep it for subsequent runs.
- Busy/leased devices block execution instead of causing duplicates. Android currently blocks while any emulator is active; booted iOS simulators are treated as busy.
- Preserve existing applications/data; a test package ID that would overwrite an existing app blocks execution.
- Shut down only the device boot instance started by the runner. Preserve definitions, SDKs, runtimes, shared caches and base images.
- Remove only verified task resources. Uncertain ownership or activity becomes a reported blocker.

## Limits and verification

Commands use disposable source snapshots. Symlinks/submodules need explicit source preparation; edits inside snapshots do not copy back. Hooks must be enabled and trusted. This is not a sandbox for arbitrary build scripts or deliberately detached processes. A crash/SIGKILL can defer cleanup until scoped recovery.

Native Android/iOS inventory and selection have been checked. Device creation/boot/app cleanup use controlled test responses; complete native application builds remain project-specific verification. See [VALIDATION.md](VALIDATION.md) for executed checks and limits.

```sh
python3 -B -m unittest discover -s tests -v
DEV_WORKFLOW_NATIVE_SMOKE=1 python3 -B -m unittest discover -s tests -v
```

The second command also tests real process groups, timeout and SIGTERM. Neither starts Android/iOS/Docker workloads.

[Development and release checks](docs/DEVELOPMENT.md) · [Publish on GitHub](docs/PUBLISHING.md)

Copyright 2026 Serhii Sheiko. Licensed under the [Apache License 2.0](LICENSE); see [NOTICE](NOTICE).

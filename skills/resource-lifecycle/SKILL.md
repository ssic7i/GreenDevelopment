---
name: resource-lifecycle
description: Use before local builds, tests, emulators, simulators, Docker workloads or other temporary processes, and when inspecting, recovering or cleaning their resources.
license: Apache-2.0
---

# Resource Lifecycle

Use the bundled runner for resource-producing work. Resolve `../../scripts/dev_resources.py` from this skill directory; SessionStart also supplies its absolute path. Read the [runner contract](references/runner.md), then only the applicable [Android](references/android.md), [iOS](references/ios.md) or [Docker](references/docker.md) reference.

The owner authorizes automatic disposal of resources created and recorded by this plugin, including recovery of inactive records from interrupted runs. No repeated cleanup approval is needed. Unknown/pre-existing resources remain protected. Never adopt an old directory or Docker object merely because it has a familiar name, is ignored or looks unused.

The runner creates a private signed record, a source snapshot and task work directory before execution. Group the build and all consumers in one run or `--steps`; retain required outputs with `--retain` relative patterns. Cleanup follows success, failure, timeout and handled signals. Inspect the JSON receipt: a successful command with failed cleanup is a failed run. Evidence remains outside disposable work.

Use one resource-heavy run at a time. The runner serializes its runs and limits native workers. Check available memory/load/disk before launch and set an appropriate disk reserve. Keep shared Gradle/Xcode caches, SDKs, runtimes and base images. Do not issue global Docker prune, device erase/delete, adb kill-server or Gradle --stop as task cleanup.

Inspect all existing compatible devices, regardless of creator/name, and lease an idle one. Create only a missing configuration, using installed images/runtimes; keep it for subsequent runs. Busy devices are a reason to wait, never to duplicate. Select versions/hardware from the verification requirements and minimize the device count by running cases sequentially. Infer test package/bundle IDs from the project and pass `--test-app` for each, including test runners. Preserve pre-existing apps/data; a package-ID collision blocks execution. Never erase/delete devices or shared runtimes.

Hooks recover scoped inactive records and request a final cleanup pass. They never kill a live foreign task or bypass sandbox permissions. SIGKILL/host crashes may leave a record; the next startup/recover checks it. Inspect blockers rather than weakening ownership, process, label or symlink checks.

Use `preview`/`status` for an inventory and scoped `recover` to execute eligible cleanup. Report retained artifacts and blocked paths, sizes and reasons. This runner never removes Git worktrees or branches; their separate project-approved retirement requires integration proof, a clean inventory including ignored files, idle workers/processes and verified retained evidence.

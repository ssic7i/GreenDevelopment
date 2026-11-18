# Runner contract

Python 3.11+ on macOS/Linux; no third-party Python dependencies. Resolve the runner from the plugin. Use the `--session` value supplied by the startup hook so stop/recovery is correctly scoped.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" run \
  --session SESSION --task TASK --repo /path/to/project --platform generic \
  --retain 'source/reports/**' -- python3 -m unittest
```

`--repo` is a runtime project path, not an installation setting. Commands run in an isolated snapshot. Git roots copy tracked and non-ignored untracked files, including edits; ignored `local.properties` is included for Android SDK setup. Non-Git roots omit conventional build/cache directories. Symlinks and submodules require preparing a self-contained source tree. No changes to source snapshots are copied back.

`--steps` accepts a JSON array of argument arrays instead of the command after `--`. All steps share the same work directory and cleanup runs after the final consumer. Execution stops on the first failed step. No implicit shell expansion; pass an explicit shell only for a generic task whose resource effects are understood.

Connected Gradle tests and Xcode `test`/`test-without-building` automatically select a device. The platform references describe compatibility filters and creation only when no matching device exists. Receipts include `device_selection` with the selected identifier and whether it was created or reused. Ordinary build/unit-test commands create no devices. Required OS/hardware coverage still controls selection; sequential runs reuse the smallest sufficient set.

Children receive `DEV_WORKFLOW_WORK`, `DEV_WORKFLOW_BUILD_ROOT`, `DEV_WORKFLOW_EVIDENCE` and a task-local temporary directory. The record, logs, receipts and retained artifacts live under the plugin's writable `PLUGIN_DATA/resources`, or the user's local data directory when used standalone. `--state-dir` before the subcommand selects a new private root for testing. An existing unmarked directory is refused.

`--retain` is repeatable. Patterns are relative to work. Missing requested artifacts fail an otherwise successful run; missing outputs after a failed command do not prevent cleanup of disposable files. Existing outputs must copy and hash-verify successfully. Keep only needed reports/artifacts; evidence is durable and never automatically pruned.

The original nonzero command exit status survives cleanup failure. Cleanup failure after command success returns nonzero. Inspect `summary.json` and `command.log` in the reported evidence directory.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" preview --session SESSION
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" recover --session SESSION
```

Recovery can instead use `--repo /path/to/project`. It obtains the run lock, checks process liveness and exact resource identity, then retains artifacts and removes eligible work. It never signals processes from a previous run. A still-live orphan blocks removal until it exits or is separately resolved. Interrupted device/container cleanup may therefore remain blocked rather than risk another task.

The cleaner protects against accidental ownership/path changes. It is not a security sandbox for arbitrary build scripts running as the same OS user. Commands must not deliberately escape their snapshot, alter ownership records or launch unmanaged resources. Hooks recognize common direct commands; obfuscated scripts and tools outside hook coverage require the agent to follow this contract.

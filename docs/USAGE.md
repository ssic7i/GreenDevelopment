# Usage and recovery

## In Codex

Give the agent the task and existing project constraints. The plugin should select applicable skills automatically. The host exposes `green-development:development-workflow`, `green-development:verification` and `green-development:resource-lifecycle`; select them from the skills picker when explicitly invoking one.

Startup guidance supplies the exact runner path, `--state-dir` and `--session`. Preserve both options: ordinary tool calls do not inherit the hook's `PLUGIN_DATA` environment, and completion hooks must see the same store and session. The agent derives required OS/hardware coverage and package/bundle IDs from the project, including test runner IDs.

## Direct runner

The command guard permits recognized file readers even when their patterns or paths mention native tools: for example `rg -n gradlew .`, `rg --files | rg gradlew`, `cat gradlew`, `sed -n '1,40p' gradlew` and `git diff -- gradlew`. Quoted patterns are data. Every command in a reader chain must qualify; adding a build or unsafe cleanup command removes the exemption.

The exemption excludes executable preprocessors/pagers, `find -exec`, executing `sed` scripts, unknown options and shell syntax whose effects cannot be established. Unquoted expansions, command substitutions, redirects, heredocs and shell wrappers retain the conservative guard. Quote search globs, for example `rg -g '*.md' gradlew .`. This guard checks common command forms; it does not sandbox configured Git helpers, aliases or arbitrary scripts.

From this repository root:

```sh
GREEN_DEVELOPMENT_ROOT="$(pwd)"
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" run --help
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" run \
  --repo /path/to/project --session terminal-check --task unit-tests \
  --platform generic -- python3 -m unittest
```

`PLUGIN_ROOT` in skill examples is supplied by the host to hooks; a normal terminal does not automatically have it. For standalone use choose a distinct session label; in Codex use the session ID from startup guidance.

Commands run in a disposable source snapshot. Group dependent commands using `--steps`, a JSON array of argument arrays. Cleanup follows the final consumer. Shell expansion is not implicit.

## Android

Connected tests automatically inventory existing AVDs. Replace the example image and package IDs with actual project values:

```sh
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" run \
  --repo /path/to/android --session terminal-check --task android-tests --platform android \
  --android-image 'system-images;android-35;google_apis;arm64-v8a' \
  --test-app com.example.app.debug --test-app com.example.app.debug.test \
  --retain 'gradle-build/**/reports/**' -- ./gradlew connectedDebugAndroidTest
```

Use `--android-profile` only when hardware matters, with a stable string ID such as `pixel_8`. `--android-avd NAME` explicitly selects an existing device. See the [Android reference](../skills/resource-lifecycle/references/android.md).

## iOS

Choose actual runtime/type identifiers from `xcrun simctl list --json`:

```sh
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" run \
  --repo /path/to/ios --session terminal-check --task ios-tests --platform ios \
  --ios-runtime INSTALLED_RUNTIME_ID --ios-type REQUIRED_DEVICE_TYPE_ID \
  --test-app com.example.app --test-app com.example.app.UITests.xctrunner \
  --retain 'result-*.xcresult' -- xcodebuild test -scheme App
```

`--ios-device UDID` explicitly selects an existing simulator. Reuse existing compatible devices; create only missing configurations from installed runtimes/images. Busy devices are blockers. If a test package already exists, use distinct test IDs or another existing suitable device; do not erase its data or create an unnecessary duplicate. See the [iOS reference](../skills/resource-lifecycle/references/ios.md).

## Docker

```sh
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" run \
  --repo /path/to/backend --session terminal-check --task docker-tests --platform docker \
  --steps '[["docker","build","-t","test-app","."],["docker","run","test-app","python","-m","unittest"]]'
```

The runner assigns names/tags/ownership labels and verifies them before cleanup. Base images and shared build caches remain. See supported commands and Compose constraints in the [Docker reference](../skills/resource-lifecycle/references/docker.md).

## Outputs and recovery

Repeat `--retain` for required patterns relative to task work. Receipts include command exit status, cleanup status, evidence paths, artifact hashes, blockers and device selection. Missing required artifacts fail an otherwise successful run.

Logs, signed records and retained outputs live under the host's `PLUGIN_DATA/resources`, or the standalone default `~/.local/share/dev-workflow-resources`. Evidence is durable and is not automatically pruned. Inspect the reported `summary.json` and `command.log`.

```sh
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" status --session terminal-check
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" preview --session terminal-check
python3 -B "$GREEN_DEVELOPMENT_ROOT/scripts/dev_resources.py" recover --session terminal-check
```

To inspect a host-managed store from a terminal, use that same `--state-dir` **before** the subcommand. Recovery can instead scope by `--repo /path/to/project`.

`preview` shows saved inventory; recovery rechecks current ownership/activity. Recovery never signals live processes from previous runs. Keep and resolve blockers; do not bypass checks with prune, device erase, `adb kill-server` or shared-daemon shutdown. See the [runner contract](../skills/resource-lifecycle/references/runner.md) for snapshots, retention and interruption behavior.

# Android

Use `--platform android` with Gradle commands. The runner uses a source snapshot, task-local Gradle project cache and an init script that redirects each project's build directory, including included builds. Shared Gradle user cache and Android SDK remain untouched. Native `.cxx` and other project-local outputs stay inside the snapshot. It disables persistent Gradle daemons/file watching and uses one worker.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" run \
  --session SESSION --task android-check --repo /path/to/android --platform android \
  --retain 'gradle-build/**/outputs/**/*.apk' \
  --retain 'gradle-build/**/reports/**' -- ./gradlew test assembleDebug
```

Connected tests default to `--android-avd auto`. Inventory all AVDs using `avdmanager` and `emulator`, then reuse a compatible idle one, regardless of who created it or its name. `--android-image` selects the exact installed system-image package; optional `--android-profile` restricts hardware only when verification requires it. Use a stable string profile ID such as `pixel_8`, never a numeric list index. An explicit `--android-avd NAME` selects that existing device directly. Resolve requirements from the project before choosing a device; do not substitute a different API/ABI to reduce test coverage.

When no compatible definition exists, create exactly one with the selected installed image and optional hardware profile. No `--force`, SDK download, wipe or device deletion is used. The created AVD is persistent and the next inventory reuses it. If a compatible device is leased, inspection is incomplete, or any emulator is running, wait/report the blocker instead of allocating extras. Gradle-managed device provisioning remains unsupported because it bypasses this inventory.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" run \
  --session SESSION --task connected-tests --repo /path/to/android --platform android \
  --android-image 'system-images;android-35;google_apis;arm64-v8a' \
  --test-app com.example.app.debug --test-app com.example.app.debug.test \
  -- ./gradlew connectedDebugAndroidTest
```

The image and package IDs above are examples; derive real values from installed SDK/project configuration. Include every package installed by the test. Existing third-party apps are allowed with this package list, but a collision with an existing app blocks execution before tests can overwrite its data. Cleanup removes declared apps newly installed by the run, verifies baseline apps remain, shuts down the same emulator boot instance and releases its lease. Definitions, existing apps/data, system images, shared caches and physical devices remain. On a device without third-party apps, omitting package IDs retains the original exclusive-lease behavior of cleaning all newly added apps.

Reference: [Android avdmanager](https://developer.android.com/tools/avdmanager).

Keep dependent Gradle tasks in the same run. For native projects whose build scripts override the init-script output path, outputs still stay inside the source snapshot; inspect artifact locations and adjust retain patterns. Build scripts that write absolute paths outside the snapshot require explicit adaptation before use.

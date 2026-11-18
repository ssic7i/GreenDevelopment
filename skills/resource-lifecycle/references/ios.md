# iOS

Use `--platform ios` with `xcodebuild`. The source snapshot contains project-local outputs; explicit paths keep DerivedData, result bundles and cloned source packages inside task work. Xcode shared caches/runtimes stay untouched. Worker count is one and UI-test parallelization is disabled.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" run \
  --session SESSION --task ios-check --repo /path/to/ios --platform ios \
  --ios-runtime INSTALLED_RUNTIME_ID --ios-type REQUIRED_DEVICE_TYPE_ID \
  --test-app com.example.app --test-app com.example.app.UITests.xctrunner \
  --retain 'result-*.xcresult' -- xcodebuild test -scheme App
```

Tests default to `--ios-device auto`. Read `xcrun simctl list --json` and reuse an available, shut-down matching simulator regardless of its creator or name. The optional `--ios-runtime` and `--ios-type` constrain OS and hardware; derive them from verification requirements. An explicit `--ios-device UDID` uses that existing device directly. If no compatible device exists, both an installed runtime ID and a device type ID are required to create one. Keep the new simulator for later runs. Busy/leased matches block execution instead of creating duplicates. Build-only commands allocate none.

Derive every installed bundle ID from the project, including the UI test runner, and repeat `--test-app`. Existing apps are preserved. A test bundle ID already installed on the selected simulator blocks execution before it can overwrite existing app data. A simulator with non-Apple apps requires the explicit bundle list. Cleanup removes only declared apps newly added during this run, verifies baseline apps remain, and shuts down its boot instance. For a simulator without non-Apple apps, omitting the list retains the original exclusive-lease behavior of cleaning all newly added apps. Never erase/delete simulator definitions or runtimes, and never download a runtime implicitly. Destination/output/parallelism flags remain managed by the runner.

Interfaces verified with installed `simctl help create` and `simctl list --json`. [Apple's simulator overview](https://developer.apple.com/documentation/safari-developer-tools/adding-additional-simulators) distinguishes reusable devices from installed runtimes.

The first version targets simulator verification. Device signing, store upload, provisioning and release archive export need their separately approved project workflow; they are not implicitly performed by this plugin.

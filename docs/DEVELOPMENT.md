# Development

Python 3.11+ and its standard library are sufficient. Native process checks also need `ps` and `lsof`.

```sh
python3 -B -m unittest discover -s tests -v
DEV_WORKFLOW_NATIVE_SMOKE=1 python3 -B -m unittest discover -s tests -v
```

The ordinary suite skips five native subprocess cases. The opt-in suite exercises those too, without starting Docker/mobile devices. Native platform creation and app cleanup are represented by controlled command responses; do not report them as real application build evidence.

An optional live Docker smoke test needs an already-local image ID containing `/bin/sh`:

```sh
DEV_WORKFLOW_DOCKER_SMOKE=1 DEV_WORKFLOW_SMOKE_IMAGE=LOCAL_IMAGE_ID \
  python3 -B tests/docker_smoke.py
```

It creates unique fixtures, checks unrelated controls survive, then removes its own fixtures. No image is pulled automatically. CI runs one Linux job for the regular/native-process suite; it does not allocate mobile devices or Docker workloads.

## Layout

- `.codex-plugin/plugin.json`: canonical local Codex manifest.
- No root `plugin.json`: the currently tested host skips bundled hooks when a portable manifest is present.
- `.agents/plugins/marketplace.json`: repository installation catalog.
- `skills/`: the three skills and their platform/policy references.
- `scripts/`: shared runner, resource tracking and native adapters.
- `hooks/hooks.json`: lifecycle integration.
- `tests/`: regression and opt-in integration checks.

## Compatibility

GreenDevelopment is the public name; `green-development` is the plugin ID. The earlier development name was `dev-workflow`. Internal `DEV_WORKFLOW_*` environment variables, `io.dev-workflow.*` labels, `dw-` device names and the standalone state-directory name remain stable. Changing ownership/state identifiers casually can strand interrupted-run records. Skills and `dev_resources.py` retain their existing names.

## Release checks

Update the canonical manifest version, run the affected tests and required native process checks, validate skill metadata and local links, and update `VALIDATION.md` with actual evidence. Check archives for secrets, local paths, runtime data and Git metadata. Preserve LICENSE/NOTICE. Never describe a local check as a GitHub Actions run or installed-host verification.

The source ZIP includes the repository marketplace so it can be installed after extraction. The plugin ZIP contains one plugin with its manifest, skills, scripts, hooks, tests, docs and license files; it excludes `.git`, `.agents` and `.github`. See [publishing](PUBLISHING.md).

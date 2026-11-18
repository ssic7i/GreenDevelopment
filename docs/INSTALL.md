# Installation and updates

## Requirements

Use Python 3.11+, Git, `ps` and `lsof` on macOS/Linux. Check `codex plugin --help` for local plugin support. No `pip install` or MCP setup is needed.

Android needs installed SDK system images, `adb`, `emulator`, `avdmanager` and the project's Java/Gradle environment. Set `ANDROID_HOME` or `ANDROID_SDK_ROOT` and expose the tools on `PATH`. iOS needs Xcode and an installed simulator runtime. Docker needs its CLI/Compose and daemon. Windows-native execution is not supported.

## Local repository or source archive

From the root containing `.agents/plugins/marketplace.json`:

```sh
codex plugin marketplace add .
codex plugin add green-development@green-development
codex plugin list --marketplace green-development --json
```

The first name in the selector is the plugin; the second is its one-plugin marketplace. Restart the desktop app or start a fresh CLI session. Review and trust hooks in Settings → Hooks or `/hooks`. Check that all three skills appear and startup guidance supplies the GreenDevelopment runner path/session ID.

## GitHub after publication

Replace `OWNER` with the actual account or organization:

```sh
codex plugin marketplace add OWNER/GreenDevelopment --ref main
codex plugin add green-development@green-development
```

Use a published version tag instead of `main` when pinning a release. The repository supplies its own marketplace catalog.

## Standalone plugin ZIP

`GreenDevelopment-plugin.zip` excludes marketplace and Git/CI metadata. Prefer a clone or `GreenDevelopment-source.zip` for the commands above. To install using only the plugin ZIP, extract it to a durable location and create `.agents/plugins/marketplace.json` inside that plugin root with the following catalog, then run the local commands:

```json
{
  "name": "green-development",
  "interface": {"displayName": "GreenDevelopment"},
  "plugins": [{
    "name": "green-development",
    "source": {"source": "local", "path": "./"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity"
  }]
}
```

## Update

For a registered Git marketplace:

```sh
codex plugin marketplace upgrade green-development
codex plugin add green-development@green-development
```

For a local clone, use `git pull --ff-only`, then repeat the install command. Refresh the client and review trust after hook scripts change. Verify the installed version with `codex plugin list`; source edits alone do not prove the cached installation changed.

If upgrading an installed `dev-workflow` development build, first finish/recover its outstanding runs and disable/remove that old plugin. Then enable GreenDevelopment. Inspect the old plugin's actual marketplace name instead of guessing it; avoid running both hook sets together.

## Remove

First complete outstanding runs and inspect cleanup receipts, then:

```sh
codex plugin remove green-development@green-development
codex plugin marketplace remove green-development
```

Keep retained evidence and resource records while recovery is pending. Uninstallation is not authorization to delete reusable devices or shared caches.

If discovery fails, check CLI support, the catalog path, installed version, enabled state, hook trust and workspace policy. Commands were checked against local CLI help, and the installed CLI discovered this repository's available plugin through read-only configuration overrides. Installation in an active user profile still needs verification.

References: [plugin marketplaces](https://developers.openai.com/plugins/build/plugins), [hooks and trust](https://learn.chatgpt.com/docs/hooks).

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Guard decisions only: no native build or cleanup commands are executed."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dev_resources import hook_result


class CommandGuardTests(unittest.TestCase):
    def check_commands(self, commands, denied):
        for command in commands:
            with self.subTest(command=command):
                result = hook_result(None, {'hook_event_name': 'PreToolUse',
                                           'tool_input': {'command': command}})
                decision = result.get('hookSpecificOutput', {}).get('permissionDecision')
                self.assertEqual(decision == 'deny', denied, result)

    def test_reading_native_tool_names_is_allowed(self):
        self.check_commands([
            'rg -n gradlew .', 'grep -n "gradlew test" README.md',
            'rg -n -- gradlew .', 'rg -ni -- gradlew .',
            'cat ./gradlew', 'head -n 20 ./gradlew', 'tail -n 20 ./gradlew',
            'wc -l ./gradlew', 'ls -l ./gradlew', 'stat ./gradlew',
            "sed -n '1,40p' ./gradlew", 'git diff -- gradlew',
            'git --no-pager show HEAD:gradlew', 'find . -name gradlew -print',
        ], False)

    def test_reader_chains_and_pipelines_are_allowed(self):
        self.check_commands([
            'rg --files | rg "gradlew"', 'cat gradlew && head -n 3 gradlew',
            'rg gradlew . || grep gradlew README.md', 'cat gradlew; wc -l gradlew',
            'cat gradlew\nhead -n 2 gradlew\n',
        ], False)

    def test_quoted_data_is_not_shell_execution(self):
        self.check_commands([
            "rg 'docker system prune' docs", "rg 'adb kill-server' docs",
            "rg 'simctl delete all' docs", "rg 'gradlew --stop' docs",
            "rg '$(./gradlew test)' docs", "rg '`./gradlew test`' docs",
            "rg ';' gradlew", "rg '&&' gradlew", 'rg "a | b" gradlew',
            'cat "folder with spaces/gradlew"', "cat folder\\ with\\ spaces/gradlew",
            'rg -- "--pre=./gradlew" README.md',
            'rg -e "--pre=./gradlew" README.md',
            "rg 'gradle'\"w\" README.md",
            "rg '{gradlew,test}' README.md", "rg -g '*.md' gradlew .",
        ], False)

    def test_command_substitutions_are_not_exempt(self):
        self.check_commands([
            'rg "$(./gradlew test)" .', 'cat `./gradlew test`',
            'cat <(./gradlew test)', 'rg gradlew . > >(docker system prune)',
            'cat gradlew; $(docker system prune)',
        ], True)

    def test_reader_execution_options_are_not_exempt(self):
        self.check_commands([
            'rg --pre "./gradlew test" .', 'rg --pre=./gradlew .',
            "rg '--pr'e=./gradlew .", 'rg --hostname-bin ./gradlew .',
            'find . -exec ./gradlew test \\;', 'find . -execdir ./gradlew test +',
            "sed -n 'e ./gradlew test' README.md",
            "sed -n '1p;e ./gradlew test' README.md",
            "sed -n '1p' --expression='e ./gradlew test' README.md",
            'git -c diff.external=./gradlew diff',
            'git diff --ext-diff -- gradlew',
            'git grep -O./gradlew pattern',
            'git grep --open-files-in-pager="./gradlew test" pattern',
            'git diff --output=gradlew', 'find . -fprint gradlew',
            'rg -e -- --pre=./gradlew README.md',
            'rg --regexp -- --hostname-bin=./gradlew README.md',
            'rg -ne -- --pre=./gradlew README.md',
            'rg --replace -- --pre=./gradlew README.md',
            'rg --replace -e --pre=./gradlew pattern README.md',
            'rg -ne -e --pre=./gradlew pattern README.md',
            'git grep -e -- --open-files-in-pager=./gradlew',
        ], True)

    def test_reader_does_not_exempt_a_following_build(self):
        self.check_commands([
            'cat gradlew && ./gradlew test', 'rg gradlew .; ./gradlew test',
            'cat gradlew || xcodebuild test', 'rg gradlew . | docker build .',
            'cat gradlew & ./gradlew test', 'cat gradlew\n./gradlew test',
        ], True)

    def test_direct_builds_and_global_cleanup_remain_denied(self):
        self.check_commands([
            './gradlew test', 'gradle build', 'xcodebuild test',
            'docker build .', 'docker run image', 'docker compose up',
            'xcrun simctl boot DEVICE', 'emulator -avd device',
            'docker system prune -af', 'docker volume prune',
            'adb kill-server', 'xcrun simctl erase all', 'xcrun simctl delete all',
            './gradlew --stop', 'cat gradlew; docker system prune',
        ], True)

    def test_managed_profiles_keep_their_existing_contract(self):
        base = 'python3 -B /plugin/scripts/dev_resources.py run --session s --task test '
        self.check_commands([
            base + '--platform android -- ./gradlew test',
            base + '--platform ios -- xcodebuild test',
            base + '--platform docker -- docker build .',
        ], False)
        self.check_commands([
            base + '--platform generic -- ./gradlew test',
            base + '--platform docker -- docker system prune',
        ], True)

    def test_unknown_or_malformed_shell_keeps_conservative_guard(self):
        self.check_commands([
            'rg "gradlew', 'bash -c "./gradlew test"',
            'PATTERN=gradlew rg "$PATTERN" .', 'cat <<EOF\n./gradlew test\nEOF',
            'rg --{pre,pre}=./gradlew pattern README.md',
            'rg --pr* ./gradlew README.md', 'rg --p[r]e=./gradlew README.md',
        ], True)

    def test_cmd_input_alias_is_supported(self):
        result = hook_result(None, {'hook_event_name': 'PreToolUse',
                                   'tool_input': {'cmd': 'rg gradlew .'}})
        self.assertEqual(result, {})

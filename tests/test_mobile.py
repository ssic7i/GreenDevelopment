# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from resource_core import Store, Unsafe, write_json
from mobile_resources import prepare_mobile, cleanup_devices, acquire_lease


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve(); self.repo = base/'repo'; self.repo.mkdir()
        self.store = Store(base/'state')
        self.rec = self.store.create(self.repo, 'mobile', 's', 'android', [])

    def test_android_outputs_and_project_cache_are_task_local(self):
        cmd = prepare_mobile(self.store, self.rec, ['./gradlew','test'])
        self.assertIn('--no-daemon', cmd)
        self.assertIn('--project-cache-dir', cmd)
        self.assertTrue(Path(cmd[cmd.index('--project-cache-dir')+1]).is_relative_to(self.store.work(self.rec)))
        self.assertNotIn('--stop', cmd)

    def test_ios_derived_data_and_results_are_task_local(self):
        self.rec['platform'] = 'ios'
        cmd = prepare_mobile(self.store, self.rec, ['xcodebuild','build','-scheme','App'])
        for flag in ('-derivedDataPath', '-resultBundlePath', '-clonedSourcePackagesDirPath'):
            self.assertTrue(Path(cmd[cmd.index(flag)+1]).is_relative_to(self.store.work(self.rec)))
        self.assertEqual(cmd[cmd.index('-parallel-testing-enabled')+1], 'NO')

    def test_output_override_is_refused(self):
        for platform, args in [('android',['./gradlew','--project-cache-dir','/shared']), ('ios',['xcodebuild','-derivedDataPath','/shared'])]:
            self.rec['platform'] = platform
            with self.assertRaises(Unsafe): prepare_mobile(self.store, self.rec, args)

    def test_device_lease_is_exclusive(self):
        acquire_lease(self.store, self.rec, 'ios', 'UDID')
        other = self.store.create(self.repo, 'other', 'other', 'ios', [])
        with self.assertRaises(Unsafe): acquire_lease(self.store, other, 'ios', 'UDID')

    def test_changed_lease_never_touches_device(self):
        device = acquire_lease(self.store, self.rec, 'ios', 'UDID')
        write_json(Path(device['lease']), {'run':'foreign','token':'foreign'})
        with patch('mobile_resources.command') as cmd, self.assertRaises(Unsafe):
            cleanup_devices(self.store, self.rec)
        cmd.assert_not_called()

    def test_android_wrong_avd_never_uninstalls_or_stops(self):
        device = acquire_lease(self.store, self.rec, 'android', 'mine')
        device.update(started=True, serial='emulator-5554', baseline=[], ready=True)
        calls=[]
        def fake(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout='someone-else\nOK\n', stderr='')
        with patch('mobile_resources.command',side_effect=fake), self.assertRaises(Unsafe):
            cleanup_devices(self.store, self.rec)
        self.assertEqual(len(calls),1)

    def test_ios_only_new_apps_uninstalled(self):
        device=acquire_lease(self.store,self.rec,'ios','UDID')
        device.update(started=True, ready=True, baseline=['com.apple.Settings'], boot_marker=True)
        calls=[]
        def fake(argv,**kwargs):
            calls.append(argv)
            if 'getenv' in argv: output=self.rec['token']
            elif 'listapps' in argv: output=json.dumps({'com.apple.Settings':{}} if any('uninstall' in c for c in calls) else {'com.apple.Settings':{},'com.example.test':{}})
            elif 'list' in argv: output=json.dumps({'devices':{'runtime':[{'udid':'UDID','state':'Shutdown' if any('shutdown' in c for c in calls) else 'Booted'}]}})
            else: output=''
            return SimpleNamespace(returncode=0,stdout=output,stderr='')
        with patch('mobile_resources.command',side_effect=fake): cleanup_devices(self.store,self.rec)
        uninstall=[c for c in calls if 'uninstall' in c]
        self.assertEqual(uninstall,[['xcrun','simctl','uninstall','UDID','com.example.test']])
        self.assertFalse(Path(device['lease']).exists())


if __name__ == '__main__': unittest.main()

class MobileInstanceTests(unittest.TestCase):
    setUp=MobileTests.setUp

    def test_shared_gradle_daemon_stop_is_refused(self):
        with self.assertRaises(Unsafe):
            prepare_mobile(self.store,self.rec,['./gradlew','-q','--stop'])

    def test_android_reused_pid_is_never_stopped(self):
        device=acquire_lease(self.store,self.rec,'android','mine')
        device.update(started=True,ready=True,serial='emulator-5554',pid=123,process_identity='original',baseline=[],boot_id='original-boot')
        calls=[]
        def fake(argv,**kwargs):
            calls.append(argv)
            text = 'mine\nOK\n' if 'avd' in argv else ('package:com.foreign\n' if 'packages' in argv else '')
            return SimpleNamespace(returncode=0,stdout=text,stderr='')
        with patch('mobile_resources.command',side_effect=fake),patch('mobile_resources.process_identity',return_value='different'),self.assertRaises(Unsafe):
            cleanup_devices(self.store,self.rec)
        self.assertFalse(any('uninstall' in c or 'kill' in c for c in calls))

    def test_ios_shutdown_with_test_apps_keeps_lease(self):
        device=acquire_lease(self.store,self.rec,'ios','UDID')
        device.update(started=True,ready=True,baseline=[],boot_marker=True)
        response=SimpleNamespace(returncode=0,stdout=json.dumps({'devices':{'r':[{'udid':'UDID','state':'Shutdown'}]}}),stderr='')
        with patch('mobile_resources.command',return_value=response),self.assertRaises(Unsafe):
            cleanup_devices(self.store,self.rec)
        self.assertTrue(Path(device['lease']).exists())

    def test_ios_new_boot_is_never_modified(self):
        device=acquire_lease(self.store,self.rec,'ios','UDID')
        device.update(started=True,ready=True,baseline=[],boot_marker=True)
        calls=[]
        def fake(argv,**kwargs):
            calls.append(argv)
            text=json.dumps({'devices':{'r':[{'udid':'UDID','state':'Booted'}]}}) if 'list' in argv else (json.dumps({'com.foreign':{}}) if 'listapps' in argv else 'foreign-token')
            return SimpleNamespace(returncode=0,stdout=text,stderr='')
        with patch('mobile_resources.command',side_effect=fake),self.assertRaises(Unsafe):
            cleanup_devices(self.store,self.rec)
        self.assertFalse(any('uninstall' in c or 'shutdown' in c for c in calls))

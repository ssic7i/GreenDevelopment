# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mobile_resources as mobile
from resource_core import Store, Unsafe


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); repo=self.root/'repo'; repo.mkdir()
        self.store=Store(self.root/'state'); self.rec=self.store.create(repo,'reuse','s','ios',[])
        self.runtime='com.apple.CoreSimulator.SimRuntime.iOS-18-0'
        self.kind='com.apple.CoreSimulator.SimDeviceType.iPhone-16'
        self.catalog={'runtimes':[{'identifier':self.runtime,'isAvailable':True}], 'devicetypes':[{'identifier':self.kind}], 'devices':{self.runtime:[]}}
        self.created=[]

    def select_ios(self, **kwargs):
        self.assertTrue(hasattr(mobile,'select_device'), 'Automatic discovery/reuse is missing')
        return mobile.select_device(self.store,self.rec,'ios',**kwargs)

    def ios_fake(self,argv,**kwargs):
        if argv==['xcrun','simctl','list','--json']:
            return SimpleNamespace(stdout=json.dumps(self.catalog),returncode=0,stderr='')
        if argv[:3]==['xcrun','simctl','create']:
            self.created.append(argv)
            self.catalog['devices'][self.runtime].append(self.device('NEW',name=argv[3]))
            return SimpleNamespace(stdout='NEW\n',returncode=0,stderr='')
        self.fail(str(argv))

    def device(self,udid,state='Shutdown',**kw):
        return {'udid':udid,'state':state,'isAvailable':True,'name':'My existing phone','deviceTypeIdentifier':self.kind,**kw}

    def test_reuses_existing_device_regardless_of_creator_or_name(self):
        self.catalog['devices'][self.runtime]=[self.device('EXISTING')]
        with patch('mobile_resources.command',side_effect=self.ios_fake):
            result=self.select_ios(runtime=self.runtime,device_type=self.kind)
        self.assertEqual(result,'EXISTING'); self.assertEqual(self.created,[])

    def test_creates_one_missing_device_and_reuses_on_next_run(self):
        with patch('mobile_resources.command',side_effect=self.ios_fake):
            first=self.select_ios(runtime=self.runtime,device_type=self.kind)
            second=self.select_ios(runtime=self.runtime,device_type=self.kind)
        self.assertEqual((first,second),('NEW','NEW')); self.assertEqual(len(self.created),1)

    def test_busy_matching_device_does_not_cause_duplicate(self):
        self.catalog['devices'][self.runtime]=[self.device('BUSY',state='Booted')]
        with patch('mobile_resources.command',side_effect=self.ios_fake),self.assertRaises(Unsafe):
            self.select_ios(runtime=self.runtime,device_type=self.kind)
        self.assertEqual(self.created,[])

    def test_leased_device_does_not_cause_duplicate(self):
        self.catalog['devices'][self.runtime]=[self.device('LEASED')]
        mobile.acquire_lease(self.store,self.rec,'ios','LEASED')
        with patch('mobile_resources.command',side_effect=self.ios_fake),self.assertRaises(Unsafe):
            self.select_ios(runtime=self.runtime,device_type=self.kind)
        self.assertEqual(self.created,[])

    def test_prefers_idle_matching_device_when_another_is_busy(self):
        self.catalog['devices'][self.runtime]=[self.device('BUSY','Booted'),self.device('IDLE')]
        with patch('mobile_resources.command',side_effect=self.ios_fake):
            self.assertEqual(self.select_ios(runtime=self.runtime,device_type=self.kind),'IDLE')
        self.assertEqual(self.created,[])

    def test_missing_runtime_never_downloads_or_substitutes(self):
        with patch('mobile_resources.command',side_effect=self.ios_fake),self.assertRaises(Unsafe):
            self.select_ios(runtime='missing',device_type=self.kind)
        self.assertEqual(self.created,[])

    def test_creation_requires_explicit_configuration_if_inventory_empty(self):
        with patch('mobile_resources.command',side_effect=self.ios_fake),self.assertRaises(Unsafe):
            self.select_ios()
        self.assertEqual(self.created,[])


class ExistingAppsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); repo=self.root/'repo'; repo.mkdir()
        self.store=Store(self.root/'state'); self.rec=self.store.create(repo,'reuse','s','ios',[])
        self.apps={'com.apple.Settings','com.personal.notes'}
        self.calls=[]; self.booted=False

    def fake(self,argv,**kwargs):
        self.calls.append(argv)
        if 'list' in argv:
            value=json.dumps({'devices':{'r':[{'udid':'EXISTING','state':'Booted' if self.booted else 'Shutdown','isAvailable':True}]}})
        elif 'listapps' in argv: value=json.dumps({app:{} for app in self.apps})
        elif 'getenv' in argv: value=self.rec['token']
        else:
            value=''
            if 'boot' in argv: self.booted=True
            if 'shutdown' in argv: self.booted=False
            if 'uninstall' in argv: self.apps.remove(argv[-1])
        return SimpleNamespace(returncode=0,stdout=value,stderr='')

    def setup_existing(self,test_apps):
        self.assertTrue(hasattr(mobile,'select_device'), 'Automatic discovery/reuse is missing')
        return mobile.setup_device(self.store,self.rec,ios_device='EXISTING',test_apps=test_apps)

    def test_reuse_preserves_existing_apps_and_removes_only_declared_test_apps(self):
        with patch('mobile_resources.command',side_effect=self.fake):
            self.setup_existing(['com.test.app'])
            self.apps.update({'com.test.app','com.unrelated.new'})
            mobile.cleanup_devices(self.store,self.rec)
        self.assertEqual(self.apps,{'com.apple.Settings','com.personal.notes','com.unrelated.new'})
        self.assertFalse(self.booted)
        self.assertFalse(any('erase' in c or 'delete' in c for c in self.calls))

    def test_existing_test_app_conflict_is_detected_before_test_execution(self):
        with patch('mobile_resources.command',side_effect=self.fake):
            with self.assertRaises(Unsafe): self.setup_existing(['com.personal.notes'])
            mobile.cleanup_devices(self.store,self.rec)
        self.assertIn('com.personal.notes',self.apps)
        self.assertFalse(any('uninstall' in c for c in self.calls))

    def test_existing_apps_need_declared_package_ids_before_testing(self):
        with patch('mobile_resources.command',side_effect=self.fake):
            with self.assertRaises(Unsafe): self.setup_existing([])
            mobile.cleanup_devices(self.store,self.rec)
        self.assertIn('com.personal.notes',self.apps)

class AndroidSelectionTests(unittest.TestCase):
    setUp=SelectionTests.setUp

    def prepare_android(self):
        self.sdk=self.root/'sdk'; self.sdk.mkdir()
        self.image='system-images;android-35;google_apis;arm64-v8a'
        image_dir=self.sdk/'system-images/android-35/google_apis/arm64-v8a'
        image_dir.mkdir(parents=True); (image_dir/'source.properties').write_text('Pkg.Revision=1')
        self.avds={}; self.running=False

    def avd(self,name):
        path=self.root/(name+'.avd'); path.mkdir()
        (path/'config.ini').write_text('image.sysdir.1=system-images/android-35/google_apis/arm64-v8a/\nhw.device.name=pixel\n')
        self.avds[name]=path

    def fake(self,argv,**kwargs):
        if argv==['avdmanager','list','avd']:
            text='Available Android Virtual Devices:\n'+''.join(f'    Name: {name}\n    Path: {path}\n---------\n' for name,path in self.avds.items())
        elif argv==['emulator','-list-avds']: text='\n'.join(self.avds)
        elif argv==['adb','devices']: text='List of devices attached\n'+('emulator-5554\tdevice\n' if self.running else '')
        elif argv[:3]==['avdmanager','create','avd']:
            self.assertNotIn('--force',argv); self.assertNotIn('-f',argv)
            self.assertEqual(kwargs.get('input_text'),'no\n')
            name=argv[argv.index('-n')+1]; self.avd(name); self.created.append(argv); text=''
        else: self.fail(str(argv))
        return SimpleNamespace(stdout=text,returncode=0,stderr='')

    def select(self):
        self.assertTrue(hasattr(mobile,'select_device'),'Automatic discovery/reuse is missing')
        with patch('mobile_resources.command',side_effect=self.fake),patch('mobile_resources.android_sdk',return_value=self.sdk),patch('mobile_resources.android_tool',side_effect=lambda tool:tool):
            return mobile.select_device(self.store,self.rec,'android',image=self.image,profile='pixel')

    def test_reuses_an_existing_unregistered_avd(self):
        self.prepare_android(); self.avd('PersonalPhone')
        self.assertEqual(self.select(),'PersonalPhone'); self.assertEqual(self.created,[])

    def test_create_once_then_reuse_without_force_or_download(self):
        self.prepare_android()
        first=self.select(); second=self.select()
        self.assertEqual(first,second); self.assertEqual(len(self.created),1)

    def test_running_emulator_does_not_trigger_extra_creation(self):
        self.prepare_android(); self.avd('PersonalPhone'); self.running=True
        with self.assertRaises(Unsafe): self.select()
        self.assertEqual(self.created,[])

    def test_uninspectable_existing_avd_blocks_creation(self):
        self.prepare_android(); self.avd('PersonalPhone')
        (self.avds['PersonalPhone']/'config.ini').unlink()
        with self.assertRaises(Unsafe): self.select()
        self.assertEqual(self.created,[])

    def test_numeric_hardware_index_cannot_duplicate_an_existing_profile(self):
        self.prepare_android(); self.avd('PersonalPhone')
        with patch('mobile_resources.command',side_effect=self.fake),patch('mobile_resources.android_sdk',return_value=self.sdk),patch('mobile_resources.android_tool',side_effect=lambda tool:tool):
            with self.assertRaisesRegex(Unsafe,'stable'):
                mobile.select_device(self.store,self.rec,'android',image=self.image,profile='35')
        self.assertEqual(self.created,[])

    def test_incomplete_existing_image_metadata_blocks_creation(self):
        self.prepare_android(); self.avd('PersonalPhone')
        (self.avds['PersonalPhone']/'config.ini').write_text('hw.device.name=pixel\n')
        with self.assertRaises(Unsafe): self.select()
        self.assertEqual(self.created,[])

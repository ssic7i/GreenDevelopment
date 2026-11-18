# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resource_core import Store, Unsafe
from dev_resources import run_task, recover, hook_result


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name).resolve(); self.repo=base/'repo'; self.repo.mkdir()
        self.store=Store(base/'state')
        self.args=argparse.Namespace(repo=str(self.repo),task='test',session='s',platform='generic',retain=[],android_avd=None,ios_device=None,timeout=10,steps=None,command=[],min_free_mb=0)

    def run_script(self,text,retain_paths=()):
        self.args.command=[sys.executable,'-c',text]; self.args.retain=list(retain_paths)
        def identity(pid):
            try: os.kill(pid,0); return 'test-'+str(pid)
            except ProcessLookupError: return None
        with contextlib.redirect_stdout(io.StringIO()), patch('resource_core.assert_idle'),patch('dev_resources.process_identity',side_effect=identity), patch('dev_resources.group_pids',return_value=[]):
            return run_task(self.store,self.args)

    def test_success_cleans_work_and_preserves_evidence(self):
        code=self.run_script("import os; from pathlib import Path; Path(os.environ['DEV_WORKFLOW_WORK'],'out.txt').write_text('final')", ['out.txt'])
        self.assertEqual(code,0)
        record=list(self.store.records())[0]
        self.assertEqual(record['status'],'cleaned')
        self.assertFalse(self.store.work(record).exists())
        self.assertEqual((self.store.evidence(record)/'artifacts/out.txt').read_text(),'final')

    def test_failure_exit_code_is_preserved_and_work_cleaned(self):
        self.assertEqual(self.run_script('raise SystemExit(7)'),7)
        record=list(self.store.records())[0]
        self.assertEqual(record['status'],'cleaned')
        self.assertEqual(record['command_exit'],7)

    def test_missing_artifact_fails_otherwise_successful_run(self):
        self.assertNotEqual(self.run_script('pass',['missing']),0)
        record=list(self.store.records())[0]
        self.assertEqual(record['status'],'blocked')
        self.assertTrue(self.store.work(record).exists())

    def test_recovery_does_not_touch_active_run(self):
        record=self.store.create(self.repo,'active','s','generic',[])
        record['runner_pid']=123; record['runner_identity']='same'; self.store.save(record)
        with patch('dev_resources.process_identity',return_value='same'):
            report=recover(self.store,session='s')
        self.assertTrue(self.store.work(record).exists())
        self.assertEqual(report[0]['status'],'active')

    def test_recovery_is_session_scoped(self):
        a=self.store.create(self.repo,'a','one','generic',[])
        b=self.store.create(self.repo,'b','two','generic',[])
        with patch('resource_core.assert_idle'):
            recover(self.store,session='one')
        self.assertFalse(self.store.work(a).exists())
        self.assertTrue(self.store.work(b).exists())

    def test_hook_blocks_unmanaged_gradle(self):
        result=hook_result(self.store,{'hook_event_name':'PreToolUse','session_id':'s','cwd':str(self.repo),'tool_input':{'command':'./gradlew test'}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'],'deny')

    def test_hook_allows_managed_runner(self):
        result=hook_result(self.store,{'hook_event_name':'PreToolUse','session_id':'s','cwd':str(self.repo),'tool_input':{'command':'python3 /plugin/scripts/dev_resources.py run --platform android --session s --task build -- ./gradlew test'}})
        self.assertEqual(result,{})

    def test_stop_hook_does_not_repeat_continuations(self):
        self.store.create(self.repo,'leftover','s','generic',[])
        with patch('dev_resources.recover',return_value=[{'id':'x','status':'blocked','blocked':['inspection failed']} ]):
            first=hook_result(self.store,{'hook_event_name':'Stop','session_id':'s'})
            second=hook_result(self.store,{'hook_event_name':'Stop','session_id':'s','stop_hook_active':True})
        self.assertEqual(first['decision'],'block')
        self.assertNotIn('decision',second)


if __name__=='__main__': unittest.main()

class AdditionalGuardTests(unittest.TestCase):
    setUp = RunnerTests.setUp
    def test_native_command_cannot_hide_in_generic_profile(self):
        result=hook_result(self.store,{'hook_event_name':'PreToolUse','session_id':'s','cwd':str(self.repo),'tool_input':{'command':'python3 /plugin/scripts/dev_resources.py run --platform generic --session s --task build -- ./gradlew test'}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'],'deny')

    def test_preparing_record_does_not_delete_without_retention_receipt(self):
        record=self.store.create(self.repo,'interrupted','s','generic',[])
        self.store.work(record).rmdir()
        with patch('resource_core.assert_idle'):
            report=recover(self.store,session='s')
        self.assertEqual(report[0]['status'],'blocked')

class ProcessGroupTests(unittest.TestCase):
    def test_exited_leader_with_live_group_cannot_claim_cleanup(self):
        from dev_resources import stop_processes
        with patch('dev_resources.process_identity',return_value=None),patch('dev_resources.group_pids',return_value=[222],create=True):
            with self.assertRaises(Unsafe):
                stop_processes({'processes':[{'pid':111,'identity':'original'}]})

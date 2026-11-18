# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Real processes/files only; never starts Docker, Android or iOS devices."""
import json
import os
from pathlib import Path
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

RUNNER=Path(__file__).resolve().parents[1]/'scripts/dev_resources.py'


@unittest.skipUnless(os.environ.get('DEV_WORKFLOW_NATIVE_SMOKE')=='1','set DEV_WORKFLOW_NATIVE_SMOKE=1 where ps/lsof inspection is permitted')
class NativeSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.repo=self.root/'repo'; self.repo.mkdir()
        (self.repo/'sentinel').write_text('keep')
        self.state=self.root/'state'

    def cli(self,code,*options):
        return [sys.executable,'-B',str(RUNNER),'--state-dir',str(self.state),'run','--repo',str(self.repo),'--session','smoke','--task','smoke','--min-free-mb','0',*options,'--',sys.executable,'-c',code]

    def test_real_success_retains_artifact_and_cleans(self):
        result=subprocess.run(self.cli("import os; from pathlib import Path; Path(os.environ['DEV_WORKFLOW_WORK'],'out.txt').write_text('artifact')",'--retain','out.txt'),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'cleaned')
        self.assertFalse(Path(report['work']).exists())
        self.assertEqual((Path(report['evidence'])/'artifacts/out.txt').read_text(),'artifact')
        self.assertEqual((self.repo/'sentinel').read_text(),'keep')

    def test_real_failed_command_cleans_and_preserves_status(self):
        result=subprocess.run(self.cli('raise SystemExit(9)'),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,9,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'cleaned',result.stdout)

    def test_startup_command_shares_hook_state_without_plugin_environment(self):
        hook_env={**os.environ,'PLUGIN_DATA':str(self.root/'plugin data')}
        startup=subprocess.run([sys.executable,'-B',str(RUNNER),'hook'],input=json.dumps({'hook_event_name':'SessionStart','session_id':'host-smoke','cwd':str(self.repo)}),env=hook_env,capture_output=True,text=True,timeout=20)
        self.assertEqual(startup.returncode,0,startup.stderr)
        context=json.loads(startup.stdout)['hookSpecificOutput']['additionalContext']
        prefix=shlex.split(context.split('Run builds/tests through ',1)[1].split(' --task ',1)[0])
        # Tools do not inherit the environment assigned exclusively to a hook.
        tool_env={k:v for k,v in os.environ.items() if k!='PLUGIN_DATA'}
        result=subprocess.run([*prefix,'--task','host-smoke','--platform','generic','--repo',str(self.repo),'--min-free-mb','0','--',sys.executable,'-c','pass'],env=tool_env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertTrue(Path(report['evidence']).is_relative_to(self.root/'plugin data/resources'),report)
        self.assertEqual(report['status'],'cleaned')

    def test_running_installed_copy_does_not_mutate_plugin_files(self):
        plugin=self.root/'installed-plugin'
        shutil.copytree(RUNNER.parent,plugin/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
        before={str(p.relative_to(plugin)):p.read_bytes() for p in plugin.rglob('*') if p.is_file()}
        # Ordinary invocation without -B must not invalidate the host's trust
        # fingerprint by creating bytecode inside its cached plugin package.
        result=subprocess.run([sys.executable,str(plugin/'scripts/dev_resources.py'),'--state-dir',str(self.state),'run','--repo',str(self.repo),'--session','immutable-plugin','--task','smoke','--min-free-mb','0','--',sys.executable,'-c','pass'],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        after={str(p.relative_to(plugin)):p.read_bytes() for p in plugin.rglob('*') if p.is_file()}
        self.assertEqual(set(after),set(before),'Execution added files to the installed plugin')
        self.assertEqual(after,before,'Execution changed installed plugin contents')

    def test_timeout_stops_child_and_cleans(self):
        result=subprocess.run(self.cli('import time; time.sleep(60)','--timeout','0.2'),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,124,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'cleaned',result.stdout)

    def test_sigterm_stops_child_and_cleans_without_touching_foreign_process(self):
        foreign=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
        process=subprocess.Popen(self.cli("import os,time; from pathlib import Path; Path(os.environ['DEV_WORKFLOW_WORK'],'started').write_text('yes'); time.sleep(60)"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+10
            while time.monotonic()<deadline and not list(self.state.glob('runs/*/work/started')):
                if process.poll() is not None: self.fail('Runner exited before signal: '+str(process.communicate()))
                time.sleep(.05)
            self.assertTrue(list(self.state.glob('runs/*/work/started')))
            process.send_signal(signal.SIGTERM)
            stdout,stderr=process.communicate(timeout=20)
            self.assertEqual(process.returncode,143,stdout+stderr)
            self.assertEqual(json.loads(stdout)['status'],'cleaned',stdout)
            self.assertIsNone(foreign.poll())
        finally:
            if process.poll() is None: process.kill(); process.wait()
            foreign.terminate(); foreign.wait()


if __name__=='__main__': unittest.main()

@unittest.skipUnless(os.environ.get('DEV_WORKFLOW_NATIVE_SMOKE')=='1','native process inspection required')
class BackgroundWorkerSmokeTests(unittest.TestCase):
    setUp=NativeSmokeTests.setUp
    cli=NativeSmokeTests.cli
    def test_background_worker_is_stopped_when_main_command_exits(self):
        code="import os,subprocess,sys; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import os,time; os.chdir(\"/\"); time.sleep(60)']); Path(os.environ['DEV_WORKFLOW_EVIDENCE'],'child.pid').write_text(str(p.pid))"
        result=subprocess.run(self.cli(code),capture_output=True,text=True,timeout=20)
        report=json.loads(result.stdout)
        pid=int((Path(report['evidence'])/'child.pid').read_text())
        try:
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(report['status'],'cleaned',result.stdout)
            info=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True)
            self.assertTrue(info.returncode!=0 or info.stdout.strip().startswith('Z'),info.stdout)
        finally:
            # This exact child was created by this test; never signal another PID.
            info=subprocess.run(['ps','-p',str(pid),'-o','args='],capture_output=True,text=True)
            if 'os.chdir("/"); time.sleep(60)' in info.stdout:
                os.kill(pid,signal.SIGTERM)

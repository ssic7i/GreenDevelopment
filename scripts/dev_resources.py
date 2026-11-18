#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Run isolated build/test steps and clean only their verified resources."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

# Cached plugin contents are part of host hook trust. Ordinary Python callers
# must not create bytecode beside these modules and invalidate that trust.
sys.dont_write_bytecode = True

from resource_core import command, Store, Unsafe, canonical, process_identity, remove_work, retain, snapshot, tree_size, write_json
from docker_resources import cleanup_docker, prepare_docker, setup_docker
from mobile_resources import cleanup_devices, prepare_mobile, setup_device
from command_guard import is_read_only_shell


class Interrupted(Exception):
    def __init__(self, signum): self.signum=signum


def default_state():
    base=os.environ.get('PLUGIN_DATA')
    return Path(base).expanduser().resolve()/'resources' if base else Path.home()/'.local/share/dev-workflow-resources'


def summarize(store,record):
    return {'id':record['id'],'task':record['task'],'status':record['status'],
            'command_exit':record.get('command_exit'),'work':str(store.work(record)),
            'remaining_bytes':tree_size(store.work(record)), 'evidence':str(store.evidence(record)),
            'blocked':record.get('blocked',[]),'artifacts':record['artifacts'],
            'device_selection':record.get('device_selection')}


def finalize(store,record):
    record['blocked']=[]
    # A failed retention must not leave a device/container running unnecessarily.
    for action in (lambda: cleanup_devices(store,record),lambda: cleanup_docker(store,record),
                   lambda: retain(store,record,record['retain'],record.get('command_exit')==0)):
        try:
            action()
        except (Unsafe,OSError,ValueError) as exc:
            record['blocked'].append(str(exc))
    if not record['blocked']:
        try: remove_work(store,record)
        except (Unsafe,OSError) as exc: record['blocked'].append(str(exc))
    record['status']='blocked' if record['blocked'] else 'cleaned'
    store.save(record)
    write_json(store.evidence(record)/'summary.json',summarize(store,record))
    return not record['blocked']


def group_pids(pgid):
    rows=command(['ps','-axo','pid=,pgid=,stat=']).stdout.splitlines()
    found=[]
    for row in rows:
        parts=row.split()
        if len(parts)!=3: raise Unsafe('Incomplete process-group inspection')
        if int(parts[1])==pgid and not parts[2].startswith('Z'):
            found.append(int(parts[0]))
    return found


def stop_processes(record, proc=None):
    for child in record['processes']:
        if proc is not None and proc.pid==child['pid']:
            proc.poll()  # Reap an exited child before inspecting or signalling it.
        current=process_identity(child['pid'])
        if current is not None:
            if not child.get('identity') or current!=child['identity']:
                raise Unsafe('Process identity changed; refusing to send a signal')
            os.killpg(child['pid'],signal.SIGTERM)
            if proc is not None and proc.pid==child['pid']:
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if process_identity(child['pid'])!=child['identity']: raise Unsafe('Process changed while stopping')
                    os.killpg(child['pid'],signal.SIGKILL)
                    proc.wait(timeout=5)
            else:
                raise Unsafe('Cannot reap this process; retaining resources')
        if group_pids(child['pid']):
            raise Unsafe('Owned process group still has workers; retaining resources for recovery')


def run_task(store,args):
    steps=json.loads(args.steps) if args.steps else [args.command[1:] if args.command and args.command[0]=='--' else args.command]
    if not isinstance(steps,list) or not steps or any(not isinstance(step,list) or not step or any(not isinstance(a,str) for a in step) for step in steps):
        raise Unsafe('Provide a command after --, or --steps as a JSON array of argument arrays')
    repo=canonical(args.repo)
    if shutil.disk_usage(store.root).free < args.min_free_mb*1024*1024:
        raise Unsafe('Insufficient free disk space for the configured reserve')
    runner_identity=process_identity(os.getpid())
    with store.lock('heavy'):
        record=store.create(repo,args.task,args.session,args.platform,args.retain)
        record.update(runner_pid=os.getpid(),runner_identity=runner_identity)
        store.save(record)
        previous={}
        def interrupt(signum,frame): raise Interrupted(signum)
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous[sig]=signal.signal(sig,interrupt)
        code,clean=1,False
        proc=None
        try:
            with store.lock('run-'+record['id']):
                try:
                    work=store.work(record)
                    source=work/'source'
                    snapshot(repo,source)
                    env=os.environ.copy()
                    env.update(DEV_WORKFLOW_WORK=str(work),DEV_WORKFLOW_EVIDENCE=str(store.evidence(record)),DEV_WORKFLOW_RUN=record['id'],DEV_WORKFLOW_BUILD_ROOT=str(work/'gradle-build'),TMPDIR=str(work/'tmp'),TMP=str(work/'tmp'),TEMP=str(work/'tmp'),PYTHONDONTWRITEBYTECODE='1')
                    (work/'tmp').mkdir()
                    # Shared Gradle/Xcode caches and SDK locations are never redirected or deleted.
                    if record['platform']=='docker': setup_docker(store,record)
                    android_avd,ios_device=args.android_avd,args.ios_device
                    if record['platform']=='android' and not android_avd and any('connected' in a.lower() for step in steps for a in step[1:]):
                        android_avd='auto'
                    if record['platform']=='ios' and not ios_device and any(a in ('test','test-without-building') for step in steps for a in step[1:]):
                        ios_device='auto'
                    setup_device(store,record,android_avd,ios_device,
                                 image=getattr(args,'android_image',None),profile=getattr(args,'android_profile',None),
                                 runtime=getattr(args,'ios_runtime',None),device_type=getattr(args,'ios_type',None),
                                 test_apps=getattr(args,'test_app',None))
                    android=next((d for d in record['devices'] if d['platform']=='android'),None)
                    if android: env['ANDROID_SERIAL']=android['serial']
                    record['status']='running'; store.save(record)
                    with (store.evidence(record)/'command.log').open('w') as log:
                        code=0
                        for index,step in enumerate(steps):
                            if record['platform']=='docker': argv=prepare_docker(store,record,step,source)
                            elif record['platform'] in ('android','ios'): argv=prepare_mobile(store,record,step)
                            else: argv=step
                            log.write(f'\nStep {index+1}: {Path(argv[0]).name}\n'); log.flush()
                            status=store.evidence(record)/f'step-{index+1}.json'
                            guard=[sys.executable,'-B',str(Path(__file__).with_name('process_guard.py')),str(status),*argv]
                            proc=subprocess.Popen(guard,cwd=source,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                            child={'pid':proc.pid,'identity':process_identity(proc.pid)}
                            record['processes'].append(child); store.save(record)
                            deadline=time.monotonic()+args.timeout
                            while not status.exists():
                                if proc.poll() is not None: raise Unsafe('Process supervisor exited without a command receipt')
                                if time.monotonic()>=deadline:
                                    code=124
                                    break
                                time.sleep(.05)
                            else:
                                code=json.loads(status.read_text())['exit_code']
                                if not isinstance(code,int) or not 0<=code<=255: raise Unsafe('Invalid command exit receipt')
                            stop_processes(record,proc)
                            proc.stdin.close()
                            if code: break
                except Interrupted as exc:
                    code=128+exc.signum
                except (Unsafe,OSError,ValueError) as exc:
                    code=1
                    record['execution_error']=str(exc)
                finally:
                    # A second signal must not abort the cleanup phase.
                    for sig in previous: signal.signal(sig,signal.SIG_IGN)
                    record['command_exit']=code
                    store.save(record)
                    try:
                        stop_processes(record,proc)
                        if proc is not None:
                            proc.wait(timeout=10)
                            if proc.stdin: proc.stdin.close()
                    except (Unsafe,OSError,subprocess.TimeoutExpired) as exc:
                        record['status']='blocked'; record['blocked']=[str(exc)]; store.save(record)
                    else:
                        clean=finalize(store,record)
        finally:
            for sig,handler in previous.items(): signal.signal(sig,handler)
        report=summarize(store,record)
        if record.get('execution_error'): report['execution_error']=record['execution_error']
        print(json.dumps(report,ensure_ascii=False))
        return code if code else (0 if clean else 1)


def recover(store,*,session=None,repo=None):
    reports=[]
    for record in store.records():
        if record['status']=='cleaned': continue
        if session is not None and record['session']!=session: continue
        if repo is not None and record['repo']!=str(Path(repo).resolve()): continue
        try:
            with store.lock('run-'+record['id']):
                pid=record.get('runner_pid')
                if pid:
                    current=process_identity(pid)
                    if current is not None:
                        reports.append({**summarize(store,record),'status':'active'})
                        continue  # Even PID reuse is not permission to signal another process.
                for child in record.get('processes',[]):
                    if process_identity(child['pid']) is not None or group_pids(child['pid']):
                        raise Unsafe('A recorded process still exists; recovery will not signal it')
                finalize(store,record)
                reports.append(summarize(store,record))
        except Unsafe as exc:
            reports.append({**summarize(store,record),'status':'blocked','blocked':[str(exc)]})
    return reports


def hook_result(store,event):
    kind=event.get('hook_event_name','')
    session=event.get('session_id')
    root=Path(__file__).resolve().parents[1]
    runner=root/'scripts/dev_resources.py'
    if kind in ('SessionStart','SubagentStart'):
        # Scope recovery to this source directory, not unrelated projects.
        reports=recover(store,repo=event.get('cwd')) if event.get('cwd') else []
        text=(f'GreenDevelopment: use the three bundled skills for applicable work. Run builds/tests through python3 -B {shlex.quote(str(runner))} run --state-dir {shlex.quote(str(store.root))} --session {shlex.quote(session or "unknown")} --task <slug> --platform <generic|android|ios|docker> --repo <source> -- <command>. '
              'The runner isolates outputs, retains requested artifacts, and cleans its own resources. Never prune shared caches, delete devices, or commandeer active devices. Read resource-lifecycle before a first run. ')
        if reports: text+='Recovery: '+json.dumps(reports)[:1800]
        return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':text}}
    if kind=='PreToolUse':
        data=event.get('tool_input',{})
        text=data.get('command',data.get('cmd','')) if isinstance(data,dict) else ''
        if not isinstance(text,str): return {}
        if is_read_only_shell(text): return {}
        managed=bool(re.search(r'dev_resources\.py[\s\"\']+run\b',text))
        dangerous=bool(re.search(r'\bdocker\s+(?:system|builder|buildx|image|volume|network|container)\s+prune\b|\badb\s+kill-server\b|\bsimctl\s+(?:erase|delete)\s+all\b|\bgradle(?:w)?\b[^;\n]*--stop\b',text))
        build=bool(re.search(r'(?<![\w-])(?:\./)?gradlew?\b|\bxcodebuild\b|\bdocker\s+(?:build|run|create|compose)\b|\bsimctl\s+boot\b|\bemulator\s+(?:-avd|@)',text))
        expected = 'android' if re.search(r'gradlew?\b|\bemulator\b', text) else ('ios' if re.search(r'\bxcodebuild\b|\bsimctl\b', text) else 'docker')
        correct_profile = bool(re.search(r'--platform(?:=|\s+)' + expected + r'\b', text))
        if dangerous or (build and (not managed or not correct_profile)):
            return {'hookSpecificOutput':{'hookEventName':kind,'permissionDecision':'deny','permissionDecisionReason':'Use the GreenDevelopment resource runner for build/test resources; global pruning/device wipes/shared-daemon shutdown are not task cleanup.'}}
        return {}
    if kind in ('Stop','SubagentStop') and session:
        reports=recover(store,session=session)
        unresolved=[r for r in reports if r['status']!='cleaned']
        if unresolved:
            reason='GreenDevelopment cleanup remains incomplete. Inspect these records; preserve active/foreign resources and report blockers: '+json.dumps(unresolved)[:2500]
            if not event.get('stop_hook_active'):
                return {'decision':'block','reason':reason}
            return {'systemMessage':reason}
        return {}
    if kind in ('Interrupt','SessionEnd') and session:
        # These events have a tiny runtime budget. Record intent; the runner's
        # signal handlers or the next startup perform verified cleanup.
        marker=store.root/('interrupted-'+__import__('hashlib').sha256(session.encode()).hexdigest()+'.json')
        write_json(marker,{'session':session,'event':kind,'at':time.time()})
        return {}
    return {}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,default=default_state())
    sub=parser.add_subparsers(dest='action',required=True)
    run=sub.add_parser('run',help='run all dependent build/test steps, then clean')
    # Hook-only PLUGIN_DATA is not inherited by agent tool calls. Carry the
    # resolved store explicitly; retain the global option for standalone use.
    run.add_argument('--state-dir',type=Path,default=argparse.SUPPRESS)
    run.add_argument('--repo',default=os.getcwd()); run.add_argument('--task',required=True)
    run.add_argument('--session',required=True); run.add_argument('--platform',choices=['generic','android','ios','docker'],default='generic')
    run.add_argument('--retain',action='append',default=[])
    run.add_argument('--android-avd',help='Existing AVD name or auto; connected tests default to auto')
    run.add_argument('--ios-device',help='Existing simulator UDID or auto; simulator tests default to auto')
    run.add_argument('--android-image',help='Exact installed system-image package for auto selection/creation')
    run.add_argument('--android-profile',help='Required hardware profile ID; omit when hardware does not matter')
    run.add_argument('--ios-runtime',help='Required installed runtime identifier')
    run.add_argument('--ios-type',help='Required device type identifier')
    run.add_argument('--test-app',action='append',default=[],help='Package/bundle ID installed by these tests; repeat for test runners')
    run.add_argument('--timeout',type=float,default=3600); run.add_argument('--min-free-mb',type=int,default=512)
    run.add_argument('--steps'); run.add_argument('command',nargs=argparse.REMAINDER)
    for name in ('status','recover','preview'):
        cmd=sub.add_parser(name); cmd.add_argument('--session'); cmd.add_argument('--repo')
    sub.add_parser('hook')
    args=parser.parse_args()
    try:
        store=Store(args.state_dir)
        if args.action=='run': return run_task(store,args)
        if args.action=='hook':
            result=hook_result(store,json.load(sys.stdin)); print(json.dumps(result)); return 0
        if args.action=='recover':
            if not args.session and not args.repo: raise Unsafe('Recovery needs --session or --repo scope')
            reports=recover(store,session=args.session,repo=args.repo)
        else:
            reports=[summarize(store,r) for r in store.records() if (not args.session or r['session']==args.session) and (not args.repo or r['repo']==str(Path(args.repo).resolve()))]
        print(json.dumps(reports,indent=2))
        return int(any(r['status']=='blocked' for r in reports))
    except (Unsafe,OSError,ValueError) as exc:
        if args.action=='hook':
            print(json.dumps({'systemMessage':'GreenDevelopment safety check could not complete: '+str(exc)}))
            return 0
        print(json.dumps({'error':str(exc)}),file=sys.stderr)
        return 1


if __name__=='__main__': sys.exit(main())

# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Explicit opt-in live Docker smoke; uses only unique task-created resources."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resource_core import command


def main():
    if os.environ.get('DEV_WORKFLOW_DOCKER_SMOKE')!='1':
        raise SystemExit('Set DEV_WORKFLOW_DOCKER_SMOKE=1 explicitly; requires an already-local base image')
    base_image=os.environ.get('DEV_WORKFLOW_SMOKE_IMAGE')
    if not base_image:
        raise SystemExit('Set DEV_WORKFLOW_SMOKE_IMAGE to an already-local image ID with /bin/sh; no image is selected or pulled automatically')
    base=json.loads(command(['docker','image','inspect',base_image]).stdout)[0]['Id']
    runner=Path(__file__).resolve().parents[1]/'scripts/dev_resources.py'
    root=Path(tempfile.mkdtemp(prefix='dev-workflow-docker-smoke-')).resolve()
    source=root/'source'; source.mkdir()
    state=root/'state'
    token=uuid.uuid4().hex
    marker='io.dev-workflow.smoke='+token
    sentinel='dw-sentinel-'+token
    made=[]
    clean=False
    try:
        for kind in ('network','volume'):
            value=command(['docker',kind,'create','--label',marker,sentinel]).stdout.strip()
            made.append((kind,value))
        value=command(['docker','container','create','--label',marker,'--name',sentinel,'--entrypoint','/bin/sh',base_image,'-c','true']).stdout.strip()
        made.append(('container',value))
        def run(args):
            result=command([sys.executable,'-B',str(runner),'--state-dir',str(state),'run','--repo',str(source),'--session','docker-smoke','--task','docker-smoke','--platform','docker','--min-free-mb','0','--',*args],timeout=120,check=False)
            if result.returncode: raise RuntimeError(result.stdout+result.stderr)
            report=json.loads(result.stdout)
            assert report['status']=='cleaned',report
            assert not Path(report['work']).exists(),report
            for kind in ('container','network','volume','image'):
                listed=command(['docker',kind,'ls','-q','--filter','label=io.dev-workflow.run='+report['id']]).stdout.strip()
                assert not listed,(kind,listed)
            return report['id']
        ids=[]
        ids.append(run(['docker','run','--entrypoint','/bin/sh',base_image,'-c','printf live-smoke']))
        (source/'Dockerfile').write_text('FROM scratch\nCOPY fixture /fixture\n')
        (source/'fixture').write_text('test-only')
        ids.append(run(['docker','build','-t','smoke-image','.']))
        config={'services':{'tests':{'image':base_image,'entrypoint':['/bin/sh','-c'],'command':['echo compose-smoke >/data/result'],'volumes':[{'type':'volume','source':'data','target':'/data'}]}},'volumes':{'data':{}}}
        (source/'compose.json').write_text(json.dumps(config))
        ids.append(run(['docker','compose','-f','compose.json','up','--abort-on-container-exit','--exit-code-from','tests']))
        for kind,resource in made:
            obj=json.loads(command(['docker',kind,'inspect',resource]).stdout)[0]
            label=(obj.get('Config',{}).get('Labels',{}) if kind=='container' else obj.get('Labels',{}))
            assert label.get('io.dev-workflow.smoke')==token
        assert json.loads(command(['docker','image','inspect',base_image]).stdout)[0]['Id']==base
        clean=True
        print(json.dumps({'live_docker':'passed','runs':len(ids),'foreign_sentinels_preserved':3,'base_image_preserved':True}))
    finally:
        for kind,resource in reversed(made):
            obj=json.loads(command(['docker',kind,'inspect',resource]).stdout)[0]
            label=(obj.get('Config',{}).get('Labels',{}) if kind=='container' else obj.get('Labels',{}))
            if label.get('io.dev-workflow.smoke')!=token: raise RuntimeError('Sentinel ownership changed; refusing deletion')
            command(['docker',kind,'rm',*(['--volumes'] if kind=='container' else []),resource])
        if clean: shutil.rmtree(root)
        else: print('Retained diagnostic state: '+str(root),file=sys.stderr)


if __name__=='__main__': main()

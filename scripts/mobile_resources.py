# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Native output isolation and exclusively leased, initially idle test devices."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import time
from resource_core import Unsafe, command, process_identity, read_json, write_json


def android_sdk():
    configured=os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if configured: return Path(configured).expanduser().resolve()
    emulator=shutil.which('emulator')
    if emulator: return Path(emulator).resolve().parents[1]
    raise Unsafe('Set ANDROID_HOME or put the SDK emulator on PATH')


def android_tool(name):
    found=shutil.which(name)
    if found: return found
    sdk=android_sdk()
    path=sdk/'emulator/emulator' if name=='emulator' else sdk/'cmdline-tools/latest/bin/avdmanager'
    if not path.is_file(): raise Unsafe(f'{name} unavailable; add the installed SDK tool to PATH')
    return str(path)


def leased(store,platform,identifier):
    key=hashlib.sha256((platform+':'+identifier).encode()).hexdigest()
    return (store.root/'leases'/(key+'.json')).exists()


def android_catalog(manager,emulator):
    text=command([manager,'list','avd']).stdout
    result=[]
    for block in re.split(r'(?m)^\s*Name:\s*',text)[1:]:
        name=block.splitlines()[0].strip()
        path=re.search(r'(?m)^\s*Path:\s*(.+)$',block)
        if not path: raise Unsafe(f'Cannot inspect existing AVD {name}; no extra device will be created')
        try:
            config={key.strip():value.strip() for line in (Path(path[1].strip())/'config.ini').read_text().splitlines()
                    if '=' in line for key,value in [line.split('=',1)]}
        except OSError as exc: raise Unsafe(f'Cannot inspect existing AVD {name}') from exc
        if not config.get('image.sysdir.1'):
            raise Unsafe(f'Existing AVD {name} has incomplete image metadata; refusing duplicate creation')
        result.append({'id':name,'image':config.get('image.sysdir.1',''),'profile':config.get('hw.device.name','')})
    names=set(command([emulator,'-list-avds']).stdout.splitlines())
    if names!={item['id'] for item in result}:
        raise Unsafe('Android inventories disagree; no extra device will be created')
    return result


def select_device(store,record,platform,*,image=None,profile=None,runtime=None,device_type=None):
    """Inspect all existing devices, regardless of creator; allocate only a missing configuration."""
    with store.lock('device-catalog'):
        created=False
        if platform=='ios':
            catalog=json.loads(command(['xcrun','simctl','list','--json']).stdout)
            runtimes={r['identifier'] for r in catalog['runtimes'] if r.get('isAvailable') and '.iOS-' in r['identifier']}
            if runtime and runtime not in runtimes: raise Unsafe('Requested iOS runtime is not installed/available')
            candidates=[d for rid,devices in catalog['devices'].items() if rid in runtimes and (not runtime or rid==runtime)
                        for d in devices if d.get('isAvailable') and (not device_type or d.get('deviceTypeIdentifier')==device_type)]
            idle=[d for d in candidates if d['state']=='Shutdown' and not leased(store,'ios',d['udid'])]
            if idle: selected=sorted(idle,key=lambda d:d['udid'])[0]['udid']
            elif candidates: raise Unsafe('Compatible simulators exist but are busy/leased; wait and reuse, do not create a duplicate')
            else:
                if not runtime or not device_type: raise Unsafe('No matching simulator: select an installed --ios-runtime and --ios-type to create one')
                if device_type not in {d['identifier'] for d in catalog['devicetypes']}: raise Unsafe('Unknown iOS device type')
                name='dw-ios-'+hashlib.sha256((runtime+device_type).encode()).hexdigest()[:12]
                record['device_selection']={'platform':'ios','created':True,'name':name,'runtime':runtime,'device_type':device_type,'status':'creating'}
                store.save(record)
                selected=command(['xcrun','simctl','create',name,device_type,runtime],timeout=120).stdout.strip()
                if not selected: raise Unsafe('Simulator creation returned no identifier; inspect inventory before retry')
                created=True
        else:
            if profile and (profile.isdecimal() or profile.startswith('-') or '\n' in profile):
                raise Unsafe('Use a stable Android hardware profile string ID, such as pixel_8, not a numeric index')
            manager,emulator=android_tool('avdmanager'),android_tool('emulator')
            sdk=android_sdk()
            existing=android_catalog(manager,emulator)
            if any(line.startswith('emulator-') for line in command(['adb','devices']).stdout.splitlines()):
                raise Unsafe('An emulator is active; wait for it to be idle, do not create a duplicate')
            desired=None
            if image:
                parts=image.split(';')
                if len(parts)!=4 or parts[0]!='system-images' or any(not re.fullmatch(r'[A-Za-z0-9_.-]+',p) or p in ('.','..') for p in parts):
                    raise Unsafe('Use an exact installed Android system-image package ID')
                desired=sdk.joinpath(*parts).resolve()
            def compatible(item):
                path=Path(item['image'])
                location=(path if path.is_absolute() else sdk/path).resolve()
                return (not desired or location==desired) and (not profile or item['profile']==profile)
            candidates=[d for d in existing if compatible(d)]
            idle=[d for d in candidates if not leased(store,'android',d['id'])]
            if idle: selected=sorted(idle,key=lambda d:d['id'])[0]['id']
            elif candidates: raise Unsafe('Compatible AVDs are leased; wait and reuse, do not create a duplicate')
            else:
                if not desired: raise Unsafe('No matching AVD: select an installed --android-image to create one')
                if not (desired/'source.properties').is_file(): raise Unsafe('Requested Android system image is not installed; no automatic download')
                selected='dw-android-'+hashlib.sha256((image+(profile or '')).encode()).hexdigest()[:12]
                if selected in {d['id'] for d in existing}: raise Unsafe('Creation name collides with an existing AVD; refusing overwrite')
                record['device_selection']={'platform':'android','created':True,'id':selected,'image':image,'profile':profile,'status':'creating'}
                store.save(record)
                argv=[manager,'create','avd','-n',selected,'-k',image]
                if profile: argv.extend(['-d',profile])
                command(argv,input_text='no\n',timeout=120)  # No --force, SDK install, wipe or deletion.
                created=True
        record['device_selection']={'platform':platform,'id':selected,'created':created,'status':'selected'}
        store.save(record)
        return selected


def prepare_app_inventory(store,record,device,apps,test_apps):
    device['baseline']=sorted(apps)
    device['test_apps']=sorted(set(test_apps or []))
    store.save(record)
    if set(test_apps or []) & apps:
        raise Unsafe('A test package is already installed; preserve its app/data and use distinct test package IDs')
    if any(not app.startswith('com.apple.') for app in apps) and not test_apps:
        raise Unsafe('Existing apps require --test-app IDs for every package the test will install')
    device['ready']=True
    store.save(record)


def added_test_apps(device,apps):
    added=apps-set(device['baseline'])
    return added & set(device['test_apps']) if device.get('test_apps') else added


def acquire_lease(store, record, platform, identifier):
    key = hashlib.sha256((platform + ':' + identifier).encode()).hexdigest()
    path = store.root / 'leases' / (key + '.json')
    device = {'platform':platform, 'id':identifier, 'lease':str(path), 'started':False, 'ready':False, 'baseline':[]}
    # The signed record precedes acquisition; recovery only removes a matching lease.
    record['devices'].append(device)
    store.save(record)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        record['devices'].remove(device); store.save(record)
        raise Unsafe(f'Device already leased: {identifier}') from exc
    with os.fdopen(fd,'w') as handle:
        json.dump({'run':record['id'], 'token':record['token']},handle)
        handle.flush(); os.fsync(handle.fileno())
    return device


def validate_lease(store, record, device):
    key=hashlib.sha256((device['platform']+':'+device['id']).encode()).hexdigest()
    path=store.root/'leases'/(key+'.json')
    if str(path)!=device['lease']:
        raise Unsafe('Device lease path mismatch')
    owner=read_json(path)
    if owner!={'run':record['id'],'token':record['token']}:
        raise Unsafe('Device lease owner mismatch')
    return path


def ios_devices():
    value=json.loads(command(['xcrun','simctl','list','devices','--json']).stdout)
    return {d['udid']:d for group in value['devices'].values() for d in group}


def ios_apps(udid):
    text=command(['xcrun','simctl','listapps',udid]).stdout
    try:
        return set(json.loads(text))
    except ValueError:
        try:
            return set(plistlib.loads(text.encode()))
        except (ValueError, plistlib.InvalidFileException):
            result=subprocess.run(['plutil','-convert','json','-o','-','-'],input=text,text=True,capture_output=True)
            if result.returncode:
                raise Unsafe('Cannot parse simulator application inventory')
            return set(json.loads(result.stdout))


def android_apps(serial):
    text=command(['adb','-s',serial,'shell','pm','list','packages','-3']).stdout
    if any(line and not line.startswith('package:') for line in text.splitlines()):
        raise Unsafe('Unexpected Android app inventory')
    return {line.split(':',1)[1].strip() for line in text.splitlines() if line}


def android_identity(device):
    actual=command(['adb','-s',device['serial'],'emu','avd','name']).stdout.splitlines()
    if not actual or actual[0].strip()!=device['id']:
        raise Unsafe('Android emulator identity changed; refusing cleanup')


def setup_device(store,record,android_avd=None,ios_device=None,*,image=None,profile=None,runtime=None,device_type=None,test_apps=None):
    if android_avd and ios_device: raise Unsafe('Select only the device for this run platform')
    if android_avd=='auto':
        if record['platform']!='android': raise Unsafe('Android device requires Android profile')
        android_avd=select_device(store,record,'android',image=image,profile=profile)
    if ios_device=='auto':
        if record['platform']!='ios': raise Unsafe('iOS device requires iOS profile')
        ios_device=select_device(store,record,'ios',runtime=runtime,device_type=device_type)
    if android_avd:
        if record['platform']!='android': raise Unsafe('Android device requires Android profile')
        device=acquire_lease(store,record,'android',android_avd)
        devices=command(['adb','devices']).stdout
        if any(line.startswith('emulator-') for line in devices.splitlines()):
            raise Unsafe('Another emulator is active; refusing to commandeer it')
        executable=android_tool('emulator')
        if android_avd not in command([executable,'-list-avds']).stdout.splitlines(): raise Unsafe('Unknown AVD')
        device.update(serial='emulator-5554', started=True)
        store.save(record)
        log=(store.evidence(record)/'emulator.log').open('w')
        try:
            proc=subprocess.Popen([executable,'-avd',android_avd,'-port','5554','-no-snapshot-save','-no-window'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        finally:
            log.close()
        device['pid']=proc.pid
        device['process_identity']=process_identity(proc.pid)
        store.save(record)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if proc.poll() is not None: raise Unsafe('Emulator exited before boot')
            result=command(['adb','-s',device['serial'],'shell','getprop','sys.boot_completed'],check=False,timeout=5)
            if result.returncode==0 and result.stdout.strip()=='1': break
            time.sleep(1)
        else: raise Unsafe('Emulator boot timeout')
        android_identity(device)
        device['boot_id']=command(['adb','-s',device['serial'],'shell','cat','/proc/sys/kernel/random/boot_id']).stdout.strip()
        if not device['boot_id']: raise Unsafe('Android boot identity unavailable')
        store.save(record)
        prepare_app_inventory(store,record,device,android_apps(device['serial']),test_apps)
    elif ios_device:
        if record['platform']!='ios': raise Unsafe('iOS device requires iOS profile')
        device=acquire_lease(store,record,'ios',ios_device)
        actual=ios_devices().get(ios_device)
        if not actual or actual.get('state')!='Shutdown' or not actual.get('isAvailable',True):
            raise Unsafe('Simulator must exist, be available and initially shut down')
        device['started']=True
        store.save(record)
        command(['xcrun','simctl','boot',ios_device])
        command(['xcrun','simctl','bootstatus',ios_device,'-b'],timeout=120)
        command(['xcrun','simctl','spawn',ios_device,'launchctl','setenv','DEV_WORKFLOW_LEASE',record['token']])
        device['boot_marker']=True
        store.save(record)
        prepare_app_inventory(store,record,device,ios_apps(ios_device),test_apps)


def prepare_mobile(store,record,argv):
    work=store.work(record)
    if record['platform']=='android':
        if Path(argv[0]).name not in ('gradlew','gradle'):
            raise Unsafe('Android profile runs Gradle; group tasks in one invocation or --steps')
        reserved=('--stop','--status','--project-cache-dir','--init-script','-I','--gradle-user-home','-g','--daemon','--max-workers','--parallel')
        if any(any(a==x or a.startswith(x+'=') for x in reserved) for a in argv[1:]):
            raise Unsafe('Android isolation/worker options are managed by the runner')
        if any('connected' in a.lower() for a in argv[1:]) and not any(d['ready'] for d in record['devices']):
            raise Unsafe('Connected Android tests require device selection before execution')
        if any('manageddevice' in a.lower() for a in argv[1:]):
            raise Unsafe('Managed-device creation is outside the reusable-device policy')
        return [*argv,'--no-daemon','--no-watch-fs','--max-workers=1','--project-cache-dir',str(work/'gradle-project-cache'),'--init-script',str(Path(__file__).with_name('android.init.gradle'))]
    if Path(argv[0]).name!='xcodebuild': raise Unsafe('iOS profile requires xcodebuild')
    reserved=('-derivedDataPath','-resultBundlePath','-clonedSourcePackagesDirPath','-parallel-testing-enabled','-maximum-concurrent-test-simulator-destinations','-jobs','-destination')
    if any(a in reserved or any(a.startswith(x+'=') for x in reserved) for a in argv[1:]):
        raise Unsafe('iOS output, destination and parallelism options are managed by the runner')
    needs_device=any(a in ('test','test-without-building') for a in argv)
    device=next((d for d in record['devices'] if d['ready']),None)
    if needs_device and not device: raise Unsafe('iOS device tests require device selection before execution')
    record['ios_step']=record.get('ios_step',0)+1
    store.save(record)
    extra=['-destination','id='+device['id']] if device else []
    return [*argv,*extra,'-derivedDataPath',str(work/'DerivedData'),'-resultBundlePath',str(work/('result-'+str(record['ios_step'])+'.xcresult')),'-clonedSourcePackagesDirPath',str(work/'SourcePackages'),'-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1','-jobs','1']


def cleanup_devices(store,record):
    for device in list(record['devices']):
        path=validate_lease(store,record,device)
        if device['started']:
            if device['platform']=='android':
                android_identity(device)
                if not device.get('pid') or not device.get('process_identity') or process_identity(device['pid']) != device['process_identity']:
                    raise Unsafe('Android process instance changed; retaining device and lease')
                boot=command(['adb','-s',device['serial'],'shell','cat','/proc/sys/kernel/random/boot_id']).stdout.strip()
                if not device.get('boot_id') or boot != device['boot_id']:
                    raise Unsafe('Android boot instance changed; retaining device and lease')
                if device['ready']:
                    for app in sorted(added_test_apps(device,android_apps(device['serial']))):
                        command(['adb','-s',device['serial'],'shell','am','force-stop',app])
                        command(['adb','-s',device['serial'],'uninstall',app])
                    apps=android_apps(device['serial'])
                    if not set(device['baseline']).issubset(apps) or added_test_apps(device,apps):
                        raise Unsafe('Android app cleanup/inventory restoration incomplete; retaining lease')
                command(['adb','-s',device['serial'],'emu','kill'])
                deadline=time.monotonic()+15
                while device['serial'] in command(['adb','devices']).stdout:
                    if time.monotonic() >= deadline: raise Unsafe('Emulator did not shut down; retaining lease')
                    time.sleep(.2)
            else:
                actual=ios_devices().get(device['id'])
                if not actual: raise Unsafe('Leased simulator disappeared; retaining lease')
                if actual['state']=='Shutdown':
                    raise Unsafe('Simulator shut down before app cleanup; boot ownership cannot be verified')
                if not device.get('boot_marker'):
                    raise Unsafe('Simulator boot marker unavailable; retaining lease')
                marker=command(['xcrun','simctl','spawn',device['id'],'launchctl','getenv','DEV_WORKFLOW_LEASE']).stdout.strip()
                if marker != record['token']:
                    raise Unsafe('Simulator boot instance changed; retaining device and lease')
                if device['ready']:
                    for app in sorted(added_test_apps(device,ios_apps(device['id']))):
                        command(['xcrun','simctl','terminate',device['id'],app],check=False)
                        command(['xcrun','simctl','uninstall',device['id'],app])
                    apps=ios_apps(device['id'])
                    if not set(device['baseline']).issubset(apps) or added_test_apps(device,apps):
                        raise Unsafe('Simulator app inventory not restored; retaining lease')
                command(['xcrun','simctl','shutdown',device['id']])
                deadline=time.monotonic()+15
                while ios_devices().get(device['id'],{}).get('state')!='Shutdown':
                    if time.monotonic()>=deadline: raise Unsafe('Simulator did not shut down; retaining lease')
                    time.sleep(.2)
        path.unlink()
        record['devices'].remove(device)
        store.save(record)

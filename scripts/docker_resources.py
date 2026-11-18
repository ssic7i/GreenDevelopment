# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Scoped Docker commands; never prune, force-remove images, or adopt resources."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
from resource_core import Unsafe, canonical, command

PREFIX = 'io.dev-workflow.'


def labels(record, kind):
    return {PREFIX + 'run': record['id'], PREFIX + 'token': record['token'], PREFIX + 'kind': kind}


def flags(record, kind):
    return [item for key, value in labels(record, kind).items() for item in ('--label', key + '=' + value)]


def name(record, kind, value):
    return 'dw-' + record['id'] + '-' + kind + '-' + hashlib.sha256(value.encode()).hexdigest()[:12]


def owned_path(path, work):
    path = canonical(path)
    if not path.is_relative_to(work):
        raise Unsafe(f'Docker writable/build path outside task workspace: {path}')
    return str(path)


def setup_docker(store, record):
    binary = shutil.which('docker')
    if not binary:
        raise Unsafe('Docker executable unavailable')
    server = command([binary, 'info', '--format', '{{.ID}}']).stdout.strip()
    if not server:
        raise Unsafe('Docker daemon identity unavailable')
    record['docker'] = {'bin': binary, 'server': server, 'images': {}, 'counter': 0}
    store.save(record)


def sanitize_compose(config, record, work):
    config = copy.deepcopy(config)
    config['name'] = 'dw-' + record['id']
    if config.get('include') or config.get('secrets') or config.get('configs'):
        raise Unsafe('Prepare Compose without external includes/secrets/configs for isolated testing')
    config.setdefault('networks', {}).setdefault('default', {})
    for group, kind in (('volumes', 'volume'), ('networks', 'network')):
        for key, obj in config.get(group, {}).items():
            obj = obj or {}
            config[group][key] = obj
            if obj.get('external') or obj.get('driver_opts') or obj.get('driver', 'local' if kind == 'volume' else 'bridge') not in ('local', 'bridge'):
                raise Unsafe(f'External/custom Docker {kind} is outside task ownership: {key}')
            obj['name'] = name(record, kind, key)
            obj['labels'] = {**obj.get('labels', {}), **labels(record, kind)}
    for key, service in config.get('services', {}).items():
        for option in ('privileged', 'pid', 'ipc', 'devices', 'volumes_from', 'network_mode', 'use_api_socket', 'develop'):
            if service.get(option):
                raise Unsafe(f'Unsafe shared-host Compose option: {option}')
        service['container_name'] = name(record, 'container', key)
        service['labels'] = {**service.get('labels', {}), **labels(record, 'container')}
        for volume in service.get('volumes', []):
            if not isinstance(volume, dict):
                raise Unsafe('Compose volumes must be normalized by docker compose config')
            if volume['type'] == 'bind':
                owned_path(volume['source'], work)
            elif volume['type'] == 'volume' and not volume.get('source'):
                # Docker removes anonymous volumes only with their owned container.
                pass
            elif volume['type'] not in ('volume', 'tmpfs'):
                raise Unsafe('Unsupported volume type')
        build = service.get('build')
        if build:
            if isinstance(build, str):
                build = {'context': build}
                service['build'] = build
            build['context'] = owned_path(build.get('context', '.'), work)
            if build.get('additional_contexts') or build.get('cache_to') or build.get('secrets'):
                raise Unsafe('External build contexts/cache export/secrets need explicit isolated preparation')
            build['labels'] = {**build.get('labels', {}), **labels(record, 'image')}
            tag = name(record, 'image', key) + ':task'
            build['tags'] = [tag]
            service['image'] = tag
    return config


def validate_compose_action(args, services):
    action = args[0]
    switches = {
        'up': {'--build', '--no-build', '--abort-on-container-exit', '--abort-on-container-failure', '--detach', '-d', '--wait', '--no-deps'},
        'run': {'--rm', '--no-deps', '--build', '-T'},
        'build': {'--no-cache', '--pull', '--quiet'},
        'exec': {'-T', '--no-TTY'},
        'logs': {'--no-color', '--timestamps'},
        'ps': {'-a', '--all', '-q', '--quiet'},
    }
    values = {'up': {'--exit-code-from', '--timeout', '--wait-timeout'},
              'run': {'--entrypoint', '-e', '--env'}, 'build': {'--build-arg'},
              'exec': {'-e', '--env', '-u', '--user', '-w', '--workdir'},
              'logs': {'--tail', '--since'}, 'ps': {'--format'}}
    index = 1
    while index < len(args):
        item = args[index]
        option, equal, value = item.partition('=')
        if item in switches[action]:
            index += 1
        elif option in values[action]:
            if not equal:
                if index + 1 == len(args): raise Unsafe('Missing Compose option value')
                index += 1
                value = args[index]
            if option == '--exit-code-from' and value not in services:
                raise Unsafe('Unknown exit-code service')
            index += 1
        elif item in services:
            if action in ('run', 'exec'):
                return  # Remaining tokens are the command inside this owned container.
            index += 1
        else:
            raise Unsafe(f'Unsupported or unsafe Compose action argument: {item}')
    if action in ('run', 'exec'):
        raise Unsafe('Compose run/exec requires a service')


def compose_command(store, record, args, source):
    binary = record['docker']['bin']
    index, files = 0, []
    while index < len(args) and args[index].startswith('-'):
        option = args[index]
        if option not in ('-f', '--file') or index + 1 == len(args):
            raise Unsafe('Compose accepts only explicit -f files before the action')
        path = Path(args[index + 1])
        path = source / path if not path.is_absolute() else path
        files.extend(['-f', owned_path(path, store.work(record))])
        index += 2
    if index == len(args) or args[index] not in ('up', 'run', 'build', 'exec', 'logs', 'ps'):
        raise Unsafe('Use Compose up/run/build/exec/logs/ps; cleanup is automatic')
    if not files:
        for candidate in ('compose.yaml', 'compose.yml', 'docker-compose.yml', 'docker-compose.yaml'):
            if (source / candidate).is_file():
                files = ['-f', str(source / candidate)]
                break
    if not files:
        raise Unsafe('Compose file not found')
    rendered = command([binary, 'compose', *files, 'config', '--format', 'json'], cwd=source).stdout
    config = sanitize_compose(json.loads(rendered), record, store.work(record))
    validate_compose_action(args[index:], config.get('services', {}))
    path = store.work(record) / 'compose.generated.json'
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return [binary, 'compose', '-p', 'dw-' + record['id'], '-f', str(path), *args[index:]]


def prepare_docker(store, record, argv, source):
    if Path(argv[0]).name != 'docker' or len(argv) < 2:
        raise Unsafe('Docker profile requires docker commands; use --steps to group dependent calls')
    args = list(argv[2:])
    action = argv[1]
    binary = record['docker']['bin']
    record['docker']['counter'] += 1
    counter = str(record['docker']['counter'])
    if action == 'compose':
        result = compose_command(store, record, args, source)
    elif action == 'build':
        clean, aliases, i = [], [], 0
        valued = {'-f', '--file', '--build-arg', '--target', '--platform', '--progress'}
        switches = {'--no-cache', '--pull'}
        while i < len(args) - 1:
            opt = args[i]
            if opt in ('-t', '--tag') and i + 1 < len(args) - 1:
                aliases.append(args[i+1]); i += 2
            elif opt in valued and i + 1 < len(args) - 1:
                clean.extend(args[i:i+2]); i += 2
            elif opt in switches:
                clean.append(opt); i += 1
            else:
                raise Unsafe(f'Unsupported Docker build option: {opt}')
        if not args or args[-1].startswith('-'):
            raise Unsafe('Docker build needs a local context')
        context = Path(args[-1]); context = source / context if not context.is_absolute() else context
        tag = name(record, 'image', counter) + ':task'
        for alias in aliases:
            record['docker']['images'][alias] = tag
        result = [binary, 'build', *clean, *flags(record, 'image'), '-t', tag, owned_path(context, store.work(record))]
    elif action in ('run', 'create'):
        clean, i = [], 0
        valued = {'-e', '--env', '-p', '--publish', '--entrypoint', '--workdir', '-w', '--user', '-u', '--cpus', '--memory'}
        switches = {'-i', '--interactive', '--init', '--read-only', '-d', '--detach'}
        while i < len(args) and args[i].startswith('-'):
            opt = args[i]
            if opt in valued and i + 1 < len(args):
                clean.extend(args[i:i+2]); i += 2
            elif opt in switches:
                clean.append(opt); i += 1
            elif opt == '--rm':
                i += 1  # Keep container until verified cleanup, including failure logs.
            elif opt in ('-v', '--volume') and i + 1 < len(args):
                parts = args[i+1].split(':')
                if len(parts) < 2:
                    raise Unsafe('Explicit task-local bind mounts are required')
                host = Path(parts[0]); host = source / host if not host.is_absolute() else host
                parts[0] = owned_path(host, store.work(record))
                clean.extend(['--volume', ':'.join(parts)]); i += 2
            else:
                raise Unsafe(f'Unsupported Docker run option: {opt}; use isolated Compose for named volumes/networks')
        if i == len(args):
            raise Unsafe('Docker run needs an image')
        image = record['docker']['images'].get(args[i], args[i])
        result = [binary, action, *clean, *flags(record, 'container'), '--name', name(record, 'container', counter), image, *args[i+1:]]
    else:
        raise Unsafe(f'Unmanaged Docker action refused: {action}; no prune or arbitrary removals')
    store.save(record)  # Persist labels/daemon identity before creating resources.
    return result


def cleanup_docker(store, record):
    state = record.get('docker')
    if not state:
        return
    binary = state['bin']
    if command([binary, 'info', '--format', '{{.ID}}']).stdout.strip() != state['server']:
        raise Unsafe('Docker daemon changed; refusing cleanup')
    for kind in ('container', 'network', 'volume', 'image'):
        wanted = labels(record, kind)
        filters = [item for k, v in wanted.items() for item in ('--filter', f'label={k}={v}')]
        listing = [binary, kind, 'ls', '-q', *filters]
        if kind == 'container':
            listing.insert(3, '-a')
        ids = sorted(set(command(listing).stdout.split()))
        for resource in ids:
            obj = json.loads(command([binary, kind, 'inspect', resource]).stdout)[0]
            actual = obj.get('Config', {}).get('Labels', {}) if kind in ('container', 'image') else obj.get('Labels', {})
            if any((actual or {}).get(k) != v for k, v in wanted.items()):
                raise Unsafe(f'Foreign/mismatched {kind}: {resource}')
            if kind == 'container':
                # --volumes removes anonymous container volumes; named volumes use separate label checks.
                command([binary, 'container', 'rm', '--force', '--volumes', resource])
            elif kind == 'image':
                tags = obj.get('RepoTags') or []
                if any(not tag.startswith('dw-' + record['id'] + '-') for tag in tags):
                    raise Unsafe(f'Image now has foreign tags; retained: {resource}')
                command([binary, 'image', 'rm', resource])  # Never force; shared references block removal.
            else:
                command([binary, kind, 'rm', resource])  # Busy networks/volumes fail closed.

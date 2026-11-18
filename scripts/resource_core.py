# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Private resource records and filesystem operations. No arbitrary delete API."""
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import time
import uuid


class Unsafe(RuntimeError):
    pass


def command(argv, *, cwd=None, env=None, timeout=30, check=True, input_text=None):
    try:
        result = subprocess.run([str(a) for a in argv], cwd=cwd, env=env,
                                text=True, capture_output=True, timeout=timeout, input=input_text)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unsafe(f'Cannot inspect/run {argv[0]}: {exc}') from exc
    if check and result.returncode:
        raise Unsafe(f'{argv[0]} exited {result.returncode}: {result.stderr.strip()[:1500]}')
    return result


def identity(path):
    info = Path(path).lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise Unsafe(f'Unexpected owner or symlink: {path}')
    return [info.st_dev, info.st_ino]


def canonical(path):
    path = Path(path).expanduser().absolute()
    if path != path.resolve():
        raise Unsafe(f'Symlink or noncanonical path: {path}')
    return path


def read_json(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd) as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise Unsafe(f'Unsafe record permissions: {path}')
            return json.load(handle)
    except (ValueError, OSError) as exc:
        raise Unsafe(f'Unreadable record {path}: {exc}') from exc


def write_json(path, value):
    temp = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Store:
    def __init__(self, root):
        self.root = canonical(root)
        try:
            self.root.mkdir(mode=0o700, parents=True)
            created = True
        except FileExistsError:
            created = False
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise Unsafe('State directory must be a private, owned directory')
        marker = self.root / 'owner.json'
        if created:
            write_json(marker, {'version': 1, 'key': secrets.token_hex(32), 'identity': identity(self.root)})
        self.owner = read_json(marker)
        if self.owner.get('version') != 1 or self.owner.get('identity') != identity(self.root):
            raise Unsafe('State directory identity mismatch')
        try:
            self.key = bytes.fromhex(self.owner['key'])
        except (KeyError, ValueError, TypeError) as exc:
            raise Unsafe('Invalid state owner key') from exc
        if len(self.key) != 32:
            raise Unsafe('Invalid state owner key length')
        for name in ('runs', 'leases'):
            child = self.root / name
            child.mkdir(mode=0o700, exist_ok=True)
            if canonical(child) != child or not child.is_dir():
                raise Unsafe(f'Unsafe state directory: {child}')
            identity(child)

    def record_path(self, run_id):
        if not re.fullmatch(r'[a-f0-9]{32}', run_id):
            raise Unsafe('Invalid run identifier')
        folder = self.root / 'runs' / run_id
        if folder.exists():
            canonical(folder)
            identity(folder)
        return folder / 'record.json'

    def sign(self, record):
        data = json.dumps(record, sort_keys=True, separators=(',', ':')).encode()
        return hmac.new(self.key, data, hashlib.sha256).hexdigest()

    def save(self, record):
        write_json(self.record_path(record['id']), {'record': record, 'signature': self.sign(record)})

    def load(self, run_id):
        data = read_json(self.record_path(run_id))
        record = data.get('record', {})
        if not hmac.compare_digest(data.get('signature', ''), self.sign(record)):
            raise Unsafe('Ownership record signature mismatch; retaining resources')
        if record.get('id') != run_id or record.get('uid') != os.getuid():
            raise Unsafe('Run owner mismatch')
        return record

    def create(self, repo, task, session, platform, patterns):
        repo = canonical(repo)
        if not repo.is_dir() or self.root.is_relative_to(repo) or repo.is_relative_to(self.root):
            raise Unsafe('Source and state directories must be separate')
        run_id = uuid.uuid4().hex
        folder = self.record_path(run_id).parent
        folder.mkdir(mode=0o700)
        (folder / 'work').mkdir(mode=0o700)
        (folder / 'evidence').mkdir(mode=0o700)
        record = dict(id=run_id, uid=os.getuid(), task=task, session=session,
                      repo=str(repo), platform=platform, created=time.time(), status='preparing',
                      token=secrets.token_hex(32), work_identity=identity(folder / 'work'),
                      evidence_identity=identity(folder / 'evidence'), retain=patterns,
                      artifacts=[], devices=[], docker=None, processes=[], blocked=[])
        self.save(record)
        return record

    def work(self, record):
        return self.record_path(record['id']).parent / 'work'

    def evidence(self, record):
        path = self.record_path(record['id']).parent / 'evidence'
        if identity(path) != record['evidence_identity']:
            raise Unsafe('Evidence directory replaced')
        return path

    @contextlib.contextmanager
    def lock(self, name):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
            raise Unsafe('Invalid lock name')
        path = self.root / (name + '.lock')
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            if os.fstat(fd).st_uid != os.getuid():
                raise Unsafe('Lock owner mismatch')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Unsafe(f'Resource busy: {name}') from exc
            yield
        finally:
            os.close(fd)

    def records(self):
        for folder in sorted((self.root / 'runs').iterdir()):
            if not re.fullmatch(r'[a-f0-9]{32}', folder.name):
                continue
            yield self.load(folder.name)


def process_identity(pid):
    result = command(['ps', '-p', str(pid), '-o', 'uid=', '-o', 'lstart='], check=False)
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return None
    if result.returncode or result.stderr.strip():
        raise Unsafe('Process inspection unavailable')
    fields = result.stdout.split()
    if not fields:
        return None
    return ' '.join(fields)


def assert_idle(path):
    # Permission/inspection failures are not evidence that a resource is idle.
    result = command(['lsof', '-n', '-P', '-t', '+D', str(path)], check=False, timeout=30)
    if result.stderr.strip() or result.returncode not in (0, 1):
        raise Unsafe('Open-file inspection unavailable or incomplete')
    if result.stdout.strip():
        raise Unsafe('Processes still use task files: ' + result.stdout.strip().replace('\n', ', '))


def check_tree(path):
    canonical(path)
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            child = Path(root) / name
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise Unsafe(f'Symlink requires inspection; retaining: {child}')
            if info.st_uid != os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise Unsafe(f'Unknown file type or owner: {child}')


def snapshot(repo, destination):
    repo, destination = Path(repo), Path(destination)
    result = command(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], check=False)
    is_root = result.returncode == 0 and Path(result.stdout.strip()).resolve() == repo
    if is_root:
        output = command(['git', '-C', str(repo), 'ls-files', '-c', '-o', '--exclude-standard', '-z']).stdout
        paths = [Path(p) for p in output.split('\0') if p]
        # SDK configuration is often ignored; it remains private and disposable.
        if (repo / 'local.properties').is_file():
            paths.append(Path('local.properties'))
    else:
        ignored = {'.git', '.gradle', '.build', 'build', 'DerivedData', 'node_modules', '.cxx'}
        paths = []
        for directory, dirs, files in os.walk(repo, followlinks=False):
            for name in dirs + files:
                if (Path(directory) / name).is_symlink():
                    raise Unsafe('Source contains symlink; provide a self-contained source tree')
            dirs[:] = [name for name in dirs if name not in ignored]
            paths.extend((Path(directory) / name).relative_to(repo) for name in files)
    destination.mkdir(mode=0o700)
    for relative in sorted(set(paths)):
        source = repo / relative
        if not source.exists() and not source.is_symlink():
            continue  # Deleted tracked file.
        if relative.is_absolute() or '..' in relative.parts or source.resolve() != source:
            raise Unsafe(f'Unsafe snapshot input: {relative}')
        if not source.is_file():
            raise Unsafe(f'Submodule or non-file requires explicit source preparation: {relative}')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def retain(store, record, patterns, success):
    work, evidence = store.work(record), store.evidence(record)
    if not work.exists():
        if not record.get('retention_complete'):
            raise Unsafe('Work disappeared without a verified retention receipt')
        for artifact in record['artifacts']:
            path = canonical(artifact['path'])
            if not path.is_relative_to(evidence) or digest(path) != artifact['sha256']:
                raise Unsafe('Retained artifact changed or disappeared')
        return
    check_tree(work)
    outputs = []
    for pattern in patterns:
        relative = Path(pattern)
        if relative.is_absolute() or '..' in relative.parts:
            raise Unsafe('Retain paths must be relative to task work, without traversal')
        matches = list(work.glob(pattern))
        if not matches and success:
            raise Unsafe(f'Required artifact missing: {pattern}')
        for match in matches:
            outputs.extend(p for p in match.rglob('*') if p.is_file()) if match.is_dir() else outputs.append(match)
    for source in sorted(set(outputs)):
        relative = source.relative_to(work)
        target = evidence / 'artifacts' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        canonical(target.parent)
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or digest(target) != digest(source):
                raise Unsafe(f'Retention destination conflict: {target}')
        else:
            shutil.copy2(source, target)
        checksum = digest(source)
        if digest(target) != checksum:
            raise Unsafe(f'Retention verification failed: {source}')
        entry = {'path': str(target), 'sha256': checksum, 'bytes': target.stat().st_size}
        if entry not in record['artifacts']:
            record['artifacts'].append(entry)
    record['retention_complete'] = True
    store.save(record)


def remove_work(store, record):
    work = store.work(record)
    if not work.exists() and not work.is_symlink():
        return
    if identity(work) != record['work_identity']:
        raise Unsafe('Task work directory replaced; refusing cleanup')
    check_tree(work)
    assert_idle(work)
    if not shutil.rmtree.avoids_symlink_attacks:
        raise Unsafe('This platform lacks symlink-safe directory removal')
    shutil.rmtree(work)


def tree_size(path):
    total = 0
    try:
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in files:
                total += (Path(root) / name).lstat().st_size
        return total
    except OSError:
        return None

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
from resource_core import Store, Unsafe
from docker_resources import labels, sanitize_compose, cleanup_docker, prepare_docker


class DockerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.repo = base / 'repo'
        self.repo.mkdir()
        self.store = Store(base / 'state')
        self.rec = self.store.create(self.repo, 'docker-test', 'session', 'docker', [])
        self.work = self.store.work(self.rec)
        self.source = self.work / 'source'
        self.source.mkdir()
        self.rec['docker'] = {'bin': '/docker', 'server': 'server-A', 'images': {}, 'counter': 0}
        self.store.save(self.rec)

    def test_compose_names_and_labels_all_owned_resources(self):
        config = {'services': {'test': {'image': 'python:3', 'container_name': 'user-name', 'volumes': [{'type':'volume','source':'db','target':'/db'}]}}, 'volumes': {'db': {'name':'production-db'}}, 'networks': {'default': {'name':'production-net'}}}
        result = sanitize_compose(config, self.rec, self.work)
        self.assertNotEqual(result['volumes']['db']['name'], 'production-db')
        self.assertNotEqual(result['services']['test']['container_name'], 'user-name')
        for obj, kind in ((result['services']['test'], 'container'), (result['volumes']['db'], 'volume'), (result['networks']['default'], 'network')):
            self.assertEqual(obj['labels'], labels(self.rec, kind))

    def test_compose_refuses_external_volume(self):
        with self.assertRaises(Unsafe):
            sanitize_compose({'services':{}, 'volumes':{'db':{'external':True}}}, self.rec, self.work)

    def test_compose_refuses_host_write_mount(self):
        config = {'services':{'test':{'image':'python:3','volumes':[{'type':'bind','source':str(self.repo),'target':'/data'}]}}}
        with self.assertRaises(Unsafe):
            sanitize_compose(config, self.rec, self.work)

    def test_daemon_change_prevents_every_delete(self):
        calls = []
        def fake(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout='server-B\n', stderr='')
        with patch('docker_resources.command', side_effect=fake), self.assertRaises(Unsafe):
            cleanup_docker(self.store, self.rec)
        self.assertEqual(len(calls), 1)

    def test_foreign_labels_are_never_deleted(self):
        calls = []
        def fake(argv, **kwargs):
            calls.append(argv)
            if 'info' in argv: text = 'server-A'
            elif 'ls' in argv: text = 'foreign-id'
            elif 'inspect' in argv: text = json.dumps([{'Id':'foreign-id','Config':{'Labels':{'other':'owner'}}}])
            else: self.fail(f'Destructive operation attempted: {argv}')
            return SimpleNamespace(returncode=0, stdout=text, stderr='')
        with patch('docker_resources.command', side_effect=fake), self.assertRaises(Unsafe):
            cleanup_docker(self.store, self.rec)
        self.assertFalse(any('rm' in x or 'rmi' in x for x in calls))

    def test_build_injects_unique_tag_and_labels(self):
        argv = prepare_docker(self.store, self.rec, ['docker','build','-t','app','.'], self.source)
        self.assertIn('--label', argv)
        self.assertIn('image', ' '.join(argv))
        self.assertNotIn('app', argv)
        self.assertIn('app', self.rec['docker']['images'])

    def test_prune_and_foreign_remove_are_rejected(self):
        for args in (['docker','system','prune','-af'], ['docker','rm','foreign'], ['docker','volume','rm','shared']):
            with self.assertRaises(Unsafe):
                prepare_docker(self.store, self.rec, args, self.source)


if __name__ == '__main__': unittest.main()

class ComposeOverrideTests(unittest.TestCase):
    setUp=DockerTests.setUp
    def test_action_overrides_cannot_escape_isolation(self):
        (self.source/'compose.yaml').write_text('services: {}')
        config={'services':{'tests':{'image':'python:3'}}}
        fake=SimpleNamespace(returncode=0,stdout=json.dumps(config),stderr='')
        for option in (['--volume','/foreign:/data'],['--privileged'],['--name','foreign'],['--env-from-file','/foreign/secret']):
            with patch('docker_resources.command',return_value=fake),self.assertRaises(Unsafe):
                prepare_docker(self.store,self.rec,['docker','compose','run',*option,'tests'],self.source)

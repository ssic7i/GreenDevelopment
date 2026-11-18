# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from resource_core import Store, Unsafe, snapshot, retain, remove_work


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'source.txt').write_text('original')
        self.store = Store(self.base / 'state')
        self.record = self.store.create(self.repo, 'task', 'session', 'generic', [])

    def test_refuses_adopting_existing_directory(self):
        other = self.base / 'unowned'
        other.mkdir()
        (other / 'cache').write_text('keep')
        with self.assertRaises(Unsafe):
            Store(other)
        self.assertEqual((other / 'cache').read_text(), 'keep')

    def test_tampered_record_rejected(self):
        path = self.store.record_path(self.record['id'])
        envelope = json.loads(path.read_text())
        envelope['record']['repo'] = '/'
        path.write_text(json.dumps(envelope))
        with self.assertRaises(Unsafe):
            self.store.load(self.record['id'])

    def test_foreign_files_and_shared_cache_survive_cleanup(self):
        foreign = self.base / 'shared-cache'
        foreign.mkdir()
        (foreign / 'important').write_text('keep')
        work = self.store.work(self.record)
        (work / 'output').write_text('temporary')
        with patch('resource_core.assert_idle'):
            remove_work(self.store, self.record)
        self.assertFalse(work.exists())
        self.assertEqual((foreign / 'important').read_text(), 'keep')
        self.assertEqual((self.repo / 'source.txt').read_text(), 'original')

    def test_external_symlink_blocks_cleanup_and_retention(self):
        target = self.base / 'foreign'
        target.write_text('keep')
        work = self.store.work(self.record)
        (work / 'escape').symlink_to(target)
        with self.assertRaises(Unsafe):
            retain(self.store, self.record, ['escape'], True)
        with patch('resource_core.assert_idle'), self.assertRaises(Unsafe):
            remove_work(self.store, self.record)
        self.assertEqual(target.read_text(), 'keep')

    def test_replaced_work_root_is_not_deleted(self):
        work = self.store.work(self.record)
        work.rename(work.with_name('saved'))
        work.mkdir()
        (work / 'not-ours').write_text('keep')
        with patch('resource_core.assert_idle'), self.assertRaises(Unsafe):
            remove_work(self.store, self.record)
        self.assertTrue((work / 'not-ours').exists())

    def test_retains_and_hashes_only_requested_outputs(self):
        work = self.store.work(self.record)
        (work / 'app.apk').write_bytes(b'final app')
        (work / 'scratch').write_bytes(b'tmp')
        retain(self.store, self.record, ['*.apk'], True)
        self.assertEqual((self.store.evidence(self.record) / 'artifacts/app.apk').read_bytes(), b'final app')
        self.assertFalse((self.store.evidence(self.record) / 'artifacts/scratch').exists())
        self.assertEqual(len(self.record['artifacts'][0]['sha256']), 64)

    def test_missing_success_artifact_blocks_cleanup(self):
        with self.assertRaises(Unsafe):
            retain(self.store, self.record, ['missing.apk'], True)
        self.assertTrue(self.store.work(self.record).exists())

    def test_snapshot_keeps_source_unmodified(self):
        dest = self.store.work(self.record) / 'source'
        snapshot(self.repo, dest)
        (dest / 'source.txt').write_text('modified')
        self.assertEqual((self.repo / 'source.txt').read_text(), 'original')

    def test_snapshot_rejects_external_symlink(self):
        (self.repo / 'escape').symlink_to(self.base / 'state')
        with self.assertRaises(Unsafe):
            snapshot(self.repo, self.store.work(self.record) / 'source')

    def test_traversal_run_id_rejected(self):
        with self.assertRaises(Unsafe):
            self.store.load('../repo')

    def test_unknown_process_activity_prevents_removal(self):
        with patch('resource_core.assert_idle', side_effect=Unsafe('inspection unavailable')):
            with self.assertRaises(Unsafe):
                remove_work(self.store, self.record)
        self.assertTrue(self.store.work(self.record).exists())


if __name__ == '__main__':
    unittest.main()

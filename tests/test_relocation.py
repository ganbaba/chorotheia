"""Relocation requires real, matching local receipt and committed provenance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from chorotheia import core
from chorotheia.guard import Tree, Transaction, SafetyError, digest, encode


class Relocation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chorotheia-relocation-')
        self.root = Path(self.temp.name).resolve()
        self.old = self.root / 'original'
        self.new = self.root / 'renamed'
        self.old.mkdir()
        (self.old / 'work.txt').write_text('unfinished user work')
        self.home = Tree(self.root / 'private', create=True, private=True)
        self.tree = Tree(self.old)
        core.initialize(self.tree, self.home)
        core.checkpoint(self.tree, self.home, 'Existing task', next_steps=['Keep original work'])
        self.tree.close()
        self.old.rename(self.new)
        self.tree = Tree(self.new)

    def tearDown(self):
        self.tree.close()
        self.home.close()
        self.temp.cleanup()

    def rebind(self, **kw):
        return core.repair(self.tree, self.home, rebind_from=self.old, **kw)

    def test_preview_has_zero_project_and_private_writes(self):
        project, private = self.tree.snapshot(), self.home.snapshot()
        self.assertTrue(self.rebind(dry_run=True)['would_rebind'])
        self.assertEqual(project, self.tree.snapshot())
        self.assertEqual(private, self.home.snapshot())

    def test_real_receipt_relocation_preserves_all_project_bytes(self):
        before = self.tree.snapshot()
        r = self.rebind()
        self.assertTrue(r['changed'])
        self.assertEqual(before, self.tree.snapshot())
        self.assertTrue(core.audit(self.tree, self.home)['ok'])
        old = json.loads(self.home.read(core.receipt_path(self.old)))
        self.assertEqual(old['state'], 'relocated')
        self.assertIsNone(old['manifest_sha256'])
        self.assertFalse(self.rebind()['changed'])
        self.assertFalse(self.rebind(dry_run=True)['changed'])

    def test_subsequent_checkpoint_does_not_break_repeat_relocation(self):
        self.rebind()
        core.checkpoint(self.tree, self.home, 'Later work')
        self.assertFalse(self.rebind()['changed'])

    def test_second_move_uses_committed_relocation_provenance(self):
        self.rebind()
        self.tree.close()
        third = self.root / 'renamed-again'
        self.new.rename(third)
        self.tree = Tree(third)
        r = core.repair(self.tree, self.home, rebind_from=self.new)
        self.assertTrue(r['changed'])
        self.assertTrue(core.audit(self.tree, self.home)['ok'])

    def test_import_without_real_private_receipt_is_refused(self):
        p = self.home.root / core.receipt_path(self.old)
        p.unlink()
        with self.assertRaises(SafetyError):
            self.rebind()
        self.assertFalse(self.home.exists(core.receipt_path(self.new)))

    def test_existing_previous_root_is_not_treated_as_move(self):
        self.old.mkdir()
        with self.assertRaises(SafetyError):
            self.rebind()
        self.assertFalse(self.home.exists(core.receipt_path(self.new)))

    def test_altered_manifest_or_memory_cannot_be_adopted(self):
        p = self.new / '.agent/STATE.md'
        p.write_text('external edit')
        with self.assertRaises(SafetyError):
            self.rebind()
        self.assertEqual(p.read_text(), 'external edit')
        self.assertFalse(self.home.exists(core.receipt_path(self.new)))

    def test_missing_or_uncommitted_journal_is_refused(self):
        rp = core.receipt_path(self.old)
        owner = json.loads(self.home.read(rp))
        p = self.home.root / ('backups/transactions/' + owner['transaction'] + '.json')
        d = json.loads(p.read_text())
        d['phase'] = 'rolled_back'
        p.write_text(json.dumps(d))
        with self.assertRaises(SafetyError):
            self.rebind()
        self.assertFalse(self.home.exists(core.receipt_path(self.new)))

    def test_occupied_destination_receipt_is_preserved(self):
        rp = core.receipt_path(self.new)
        self.home.write(rp, b'{"foreign":"keep"}')
        with self.assertRaises(SafetyError):
            self.rebind()
        self.assertEqual(self.home.read(rp), b'{"foreign":"keep"}')

    def test_failure_rolls_back_both_bindings(self):
        old = self.home.read(core.receipt_path(self.old))
        original = Transaction.put
        def injected(tx, rel, *args, **kw):
            if rel == core.receipt_path(self.old):
                raise SafetyError('Failure before source tombstone')
            return original(tx, rel, *args, **kw)
        with patch.object(Transaction, 'put', injected):
            with self.assertRaises(SafetyError):
                self.rebind()
        self.assertEqual(self.home.read(core.receipt_path(self.old)), old)
        self.assertFalse(self.home.exists(core.receipt_path(self.new)))
        self.assertTrue(self.rebind()['changed'])

    def test_source_receipt_requires_exact_committed_bytes(self):
        rp = core.receipt_path(self.old)
        d = json.loads(self.home.read(rp));d['unproven-extra'] = True
        p = self.home.root / rp;p.write_bytes(encode(d))
        with self.assertRaises(SafetyError):
            self.rebind()

    def test_pending_old_transaction_prevents_relocation(self):
        rel = 'backups/transactions/' + 'f' * 32 + '.json'
        self.home.write(rel, encode({'id': 'f' * 32, 'root': str(self.old), 'phase': 'pending'}))
        with self.assertRaises(SafetyError):
            self.rebind()

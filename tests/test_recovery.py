"""Interruption recovery uses evidence and explicit transactions, never a model."""
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
try:
    from . import test_monitor as fixtures
except ImportError:
    import test_monitor as fixtures
from chorotheia import core, monitor, recovery
from chorotheia.adapters import run_hook
from chorotheia.guard import SafetyError, Transaction


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.MonitorTests.setUp
    tearDown = fixtures.MonitorTests.tearDown
    write = fixtures.MonitorTests.write
    message = fixtures.MonitorTests.message
    enable = fixtures.MonitorTests.enable
    scan = fixtures.MonitorTests.scan
    report = fixtures.MonitorTests.report
    cp = fixtures.MonitorTests.cp
    token = fixtures.MonitorTests.token

    def fail_request(self):
        self.enable()
        return run_hook(self.home, 'codex', 'PostModelRequest', self.payload(status='failed', error='usage limit'))

    def payload(self, **extra):
        return dict(cwd=str(self.project), session_id=self.sid, transcript_path=str(self.path), **extra)

    def plan(self):
        return recovery.plan(self.tree, core.require(self.tree)[0], self.report())

    def complete(self, **extra):
        return self.cp(review_recovery=self.plan()['recovery_token'], recovery_result='Verified saved results; remaining QA is unknown',
                       tests=['Not rerun: read-only fixture recovery; pending QA retained'], **extra)

    def test_normal_open_phase_and_discussion_do_not_trigger_full_recovery(self):
        self.enable()
        self.cp(phase='Implementation')
        self.message()
        (self.project/'work.txt').write_text('unfinished work')
        out = run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        self.assertFalse(self.plan()['required'])
        self.assertNotIn('Chorotheia recovery:', json.dumps(out))
        self.assertNotIn('recovery_delivery', monitor.load(self.home, self.m))

    def test_recover_cli_is_read_only_and_bounded(self):
        self.fail_request()
        before, project = self.home.snapshot(), self.tree.snapshot()
        result = subprocess.run([sys.executable, '-B', '-m', 'chorotheia', 'recover', '--project', str(self.project),
                                 '--home', str(self.home.root), '--text'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('recover', result.stdout)
        self.assertLessEqual(len(result.stdout.encode()), 2401)
        self.assertEqual(before, self.home.snapshot())
        self.assertEqual(project, self.tree.snapshot())

    def test_next_prompt_delivers_plan_once_and_keeps_failure_pending(self):
        self.fail_request()
        before = self.tree.snapshot()
        first = run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        second = run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        a = first['hookSpecificOutput']['additionalContext']
        b = second['hookSpecificOutput']['additionalContext']
        self.assertIn('--review-recovery', a)
        self.assertLess(len(b), len(a))
        self.assertIn('remains pending', b)
        self.assertTrue(self.plan()['required'])
        self.assertEqual(before, self.tree.snapshot())

    def test_compaction_reloads_recovery_even_after_delivery(self):
        self.fail_request()
        run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        for event in ['PostCompact', 'SessionStart']:
            text = run_hook(self.home, 'codex', event, self.payload())['hookSpecificOutput']['additionalContext']
            self.assertIn('--review-recovery', text)
            self.assertIn('SOURCE .agent/CHECKPOINT.json', text)
            self.assertLessEqual(len(text.encode()), 2400)
        self.assertTrue(self.plan()['required'])

    def test_verified_recovery_checkpoint_acknowledges_failure_only(self):
        self.fail_request()
        self.message('决定尚未核对')
        self.scan()
        result = self.complete()['checkpoint']
        self.assertTrue(result['recovery']['incident_id'])
        self.assertIn('unknown', result['recovery']['result'])
        self.assertFalse(self.plan()['required'])
        self.assertEqual(self.report()['pending_messages'], 1)
        self.assertTrue(self.report()['unsummarized_progress'])
        self.assertNotIn('Chorotheia recovery:', json.dumps(run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())))

    def test_recovery_without_result_tests_or_current_token_refused(self):
        self.fail_request()
        before = self.home.snapshot(), self.tree.snapshot()
        token = self.plan()['recovery_token']
        for args in [dict(review_recovery=token), dict(recovery_result='Read results'),
                     dict(review_recovery=token, recovery_result='Read results'),
                     dict(review_recovery=token, recovery_result='Read results', tests=['']),
                     dict(review_recovery='stale', recovery_result='Read results', tests=['not run'])]:
            with self.assertRaises(SafetyError):
                self.cp(**args)
        self.assertEqual(before, (self.home.snapshot(), self.tree.snapshot()))

    def test_recovery_token_rejects_new_source_or_git_changes(self):
        self.fail_request()
        token = self.plan()['recovery_token']
        self.message('决定新范围')
        self.scan()
        with self.assertRaises(SafetyError):
            self.cp(review_recovery=token, recovery_result='stale', tests=['not run'])
        token = self.plan()['recovery_token']
        (self.project/'changed.txt').write_text('new work')
        with self.assertRaises(SafetyError):
            self.cp(review_recovery=token, recovery_result='stale', tests=['not run'])

    def test_tool_only_cursor_advances_do_not_invalidate_recovery_token(self):
        self.fail_request()
        token = self.plan()['recovery_token']
        self.write({'type': 'response_item', 'payload': {'type': 'custom_tool_call_output', 'output': 'ignored result'}})
        self.scan()
        self.assertEqual(token, self.plan()['recovery_token'])
        self.cp(review_recovery=token, recovery_result='Inspected saved results', tests=['Not run: fixture'])
        self.assertFalse(self.plan()['required'])

    def test_automatic_snapshot_cannot_acknowledge_recovery(self):
        self.fail_request()
        with self.assertRaises(SafetyError):
            self.cp(snapshot=True, review_recovery=self.plan()['recovery_token'], recovery_result='wrong', tests=['not run'])
        self.assertTrue(self.plan()['required'])

    def test_recovery_result_and_failure_ack_roll_back_together(self):
        self.fail_request()
        before = self.home.read(monitor.location(self.m)), self.tree.read('.agent/CHECKPOINT.json')
        original = Transaction.put
        def fail(tx, rel, *args, **kw):
            if rel == '.agent/CHECKPOINT.json':
                raise SafetyError('synthetic checkpoint failure')
            return original(tx, rel, *args, **kw)
        with patch.object(Transaction, 'put', fail):
            with self.assertRaises(SafetyError):
                self.complete()
        self.assertEqual(before, (self.home.read(monitor.location(self.m)), self.tree.read('.agent/CHECKPOINT.json')))
        self.assertTrue(self.plan()['required'])

    def test_new_failure_after_recovery_delivers_a_new_plan(self):
        self.fail_request()
        run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        self.complete()
        run_hook(self.home, 'codex', 'PostModelRequest', self.payload(status='failed', error='network failure'))
        out = run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        self.assertIn('--review-recovery', out['hookSpecificOutput']['additionalContext'])

    def test_monitor_disabled_does_not_start_recovery_or_any_model(self):
        before = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        native_popen = subprocess.Popen
        def only_git(args, *a, **kw):
            if args[0] != 'git':
                raise AssertionError('Recovery must not start a model or RPC')
            return native_popen(args, *a, **kw)
        with patch('subprocess.Popen', side_effect=only_git):
            run_hook(self.home, 'codex', 'PostModelRequest', self.payload(status='failed', error='usage limit'))
            self.assertFalse(self.plan()['required'])
        self.assertEqual(before['summary'], json.loads(self.tree.read('.agent/CHECKPOINT.json'))['summary'])
        self.assertNotIn('recovery_delivery', monitor.load(self.home, self.m))

    def test_recovery_marker_survives_small_restore_budget(self):
        from chorotheia.memory import restore
        self.fail_request()
        self.cp(summary='Lengthy prior history. ' * 100)
        out = restore(self.tree, core.require(self.tree)[0], 1500, self.report())
        self.assertIn('Recovery', out['loaded_fields'])
        self.assertLessEqual(out['utf8_bytes'], 1500)

    def test_edited_checkpoint_preserved_and_recovery_does_not_claim_completion(self):
        self.fail_request()
        path = self.project/'.agent/CHECKPOINT.json'
        edited = b'{"summary":"edited evidence"}'
        path.write_bytes(edited)
        with self.assertRaises(SafetyError):
            self.plan()
        out = run_hook(self.home, 'codex', 'UserPromptSubmit', self.payload())
        self.assertIn('Inspect audit', out['hookSpecificOutput']['additionalContext'])
        self.assertEqual(path.read_bytes(), edited)
        self.assertIsNotNone(self.report()['model_failure'])


if __name__ == '__main__':
    unittest.main()

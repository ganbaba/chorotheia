"""Synthetic visible transcripts and quotas; never consume real model quota."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from chorotheia import core, monitor
from chorotheia.adapters import run_hook, hook_configs
from chorotheia.guard import Tree, SafetyError, Transaction, lock
from chorotheia.memory import restore
from chorotheia.quota import normalize, evaluate, read_native
from chorotheia.installation import install, upgrade_global


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chorotheia-monitor-')
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.tree = Tree(self.project)
        self.home = Tree(self.root / 'private', create=True, private=True)
        self.codex = self.root / 'user/.codex'
        self.sessions = self.codex / 'sessions/2026/11/26'
        self.sessions.mkdir(parents=True)
        self.env = patch.dict(os.environ, CODEX_HOME=str(self.codex))
        self.env.start()
        core.initialize(self.tree, self.home)
        self.m = core.require(self.tree)[0]
        self.sid = '12345678-1234-1234-1234-123456789abc'
        self.path = self.sessions / ('rollout-test-' + self.sid + '.jsonl')
        self.write({'type': 'session_meta', 'payload': {'id': self.sid, 'cwd': str(self.project)}})

    def tearDown(self):
        self.env.stop()
        self.tree.close()
        self.home.close()
        self.temp.cleanup()

    def write(self, record):
        with self.path.open('a') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def message(self, text='决定先支持 Codex，Copilot 延后。', role='user', **extra):
        self.write({'type': 'response_item', 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'payload': {'type': 'message', 'id': 'message-' + str(self.path.stat().st_size), 'role': role,
                                'content': [{'type': 'input_text' if role == 'user' else 'output_text', 'text': text}], **extra}})

    def enable(self):
        monitor.configure(self.home, self.m, self.project, True)
        self.scan()

    def scan(self, **kw):
        return monitor.scan(self.home, self.m, self.project, self.sid, str(self.path), **kw)

    def report(self, details=False):
        return monitor.public(monitor.load(self.home, self.m), details)

    def cp(self, **kw):
        return core.checkpoint(self.tree, self.home, kw.pop('summary', 'Reviewed fixture progress'), **kw)

    def token(self):
        return self.report()['streams'][0]['review_token']

    def quota(self, used, reset=None):
        return normalize({'primary': {'used_percent': used, 'resets_at': reset or time.time() + 3600}}, source='synthetic fixture')

    def test_disabled_monitor_does_not_open_untrusted_transcript(self):
        before = self.home.snapshot()
        r = monitor.scan(self.home, self.m, self.project, self.sid, '/not/authorized')
        self.assertFalse(r['enabled'])
        self.assertEqual(before, self.home.snapshot())

    def test_prospective_binding_does_not_claim_old_history_reviewed(self):
        self.message('旧的决定')
        self.enable()
        r = self.report()
        self.assertEqual(r['pending_messages'], 0)
        self.assertIsNone(r['streams'][0]['reviewed_cursor'])
        self.message()
        self.scan()
        self.assertEqual(self.report()['pending_messages'], 1)

    def test_visible_only_candidates_have_source_offsets_and_redaction(self):
        self.enable()
        self.message('PRIVATE-REASONING', role='assistant', channel='analysis')
        self.message('PRIVATE-COMMENTARY', role='assistant', phase='commentary')
        self.write({'type': 'response_item', 'payload': {'type': 'function_call', 'arguments': 'PRIVATE-TOOL-INPUT'}})
        self.message('决定采用本地方案。password=do-not-store')
        self.message('已完成接口设计。', role='assistant', phase='final_answer')
        self.scan()
        r = self.report(True)
        self.assertEqual(r['pending_messages'], 2)
        text = json.dumps(r)
        for secret in ('PRIVATE-REASONING', 'PRIVATE-COMMENTARY', 'PRIVATE-TOOL-INPUT', 'do-not-store'):
            self.assertNotIn(secret, text)
        candidate = r['streams'][0]['candidates'][0]
        self.assertLess(candidate['byte_start'], candidate['byte_end'])
        self.assertEqual(candidate['classification'], 'inferred; requires review')
        self.assertTrue(r['streams'][0]['source'].endswith('.jsonl'))

    def test_duplicate_events_do_not_duplicate_messages(self):
        self.enable()
        self.message()
        first = self.scan()
        token = self.token()
        self.assertEqual(self.scan()['pending_messages'], first['pending_messages'])
        self.assertEqual(self.token(), token)

    def test_checkpoint_without_review_keeps_discussion_pending(self):
        self.enable()
        self.message()
        self.scan()
        cp = self.cp()
        self.assertTrue(cp['checkpoint']['reviewed_at'])
        self.assertTrue(cp['checkpoint']['unsummarized_progress']['pending'])
        self.assertEqual(cp['freshness']['state'], 'needs_review')
        self.assertEqual(self.report()['pending_messages'], 1)

    def test_exact_review_token_clears_only_acknowledged_discussion(self):
        self.enable()
        self.message()
        self.scan()
        token = self.token()
        cp = self.cp(review_discussion=[token], decisions=['Confirmed fixture decision'])
        self.assertEqual(self.report()['pending_messages'], 0)
        self.assertEqual(cp['checkpoint']['discussion_review_tokens'], [token])
        self.assertEqual(cp['freshness']['state'], 'reviewed')
        self.message('下一步验证')
        self.scan()
        self.assertEqual(self.report()['pending_messages'], 1)

    def test_stale_review_token_cannot_acknowledge_new_messages(self):
        self.enable()
        self.message()
        self.scan()
        stale = self.token()
        self.message('决定改变范围')
        self.scan()
        before = self.home.snapshot()
        with self.assertRaises(SafetyError):
            self.cp(review_discussion=[stale])
        self.assertEqual(before, self.home.snapshot())

    def test_failure_snapshot_preserves_notes_and_marks_unsummarized_without_model(self):
        self.enable()
        before = self.cp(summary='Known notes', tests=['Previously observed test'])['checkpoint']
        self.message()
        payload = {'cwd': str(self.project), 'session_id': self.sid, 'transcript_path': str(self.path),
                   'status': 'failed', 'error': 'usage limit reached password=never-store-error'}
        native_popen = subprocess.Popen
        def only_git(args, *a, **kw):
            if args[0] != 'git':
                raise AssertionError('No model or RPC process allowed')
            return native_popen(args, *a, **kw)
        with patch('chorotheia.quota.subprocess.Popen', side_effect=only_git):
            run_hook(self.home, 'codex', 'PostModelRequest', payload)
        cp = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        for key in ('summary', 'tests', 'reviewed_at', 'covered_git'):
            self.assertEqual(cp[key], before[key])
        self.assertEqual(cp['unsummarized_progress']['label'], '尚未总结的进展')
        self.assertEqual(self.report()['model_failure']['reason'], 'quota_or_rate_limit')
        self.assertNotIn('never-store-error', json.dumps(monitor.load(self.home, self.m)))

    def test_exhausted_quota_before_request_snapshots_known_notes(self):
        self.enable()
        known = self.cp(summary='Known notes')['checkpoint']
        self.write({'type': 'event_msg', 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'payload': {'type': 'token_count', 'rate_limits': {'primary': {'used_percent': 100}}}})
        out = run_hook(self.home, 'codex', 'PreModelRequest', {'cwd': str(self.project), 'session_id': self.sid,
                                                             'transcript_path': str(self.path)})
        self.assertEqual(out, {})
        cp = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        self.assertEqual(cp['summary'], known['summary'])
        self.assertEqual(cp['reviewed_at'], known['reviewed_at'])
        self.assertEqual(cp['unsummarized_progress']['label'], '尚未总结的进展')

    def test_failure_acknowledgement_requires_explicit_token(self):
        self.enable()
        monitor.model_outcome(self.home, self.m, self.project, {'status': 'failed', 'error': 'network failure'})
        monitor.model_outcome(self.home, self.m, self.project, {'status': 'completed'})
        self.assertTrue(self.report()['unsummarized_progress'])
        self.cp(review_discussion=[self.report()['failure_review_token']])
        self.assertFalse(self.report()['unsummarized_progress'])

    def test_failed_request_still_snapshots_when_transcript_is_unsafe(self):
        self.enable()
        old = self.cp(summary='Known notes')['checkpoint']
        run_hook(self.home, 'codex', 'PostModelRequest', {'cwd': str(self.project), 'session_id': self.sid,
                 'transcript_path': '/outside/forbidden.jsonl', 'status': 'failed', 'error': 'usage limit'})
        cp = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        self.assertEqual(cp['summary'], old['summary'])
        self.assertTrue(cp['unsummarized_progress']['pending'])
        self.assertTrue(self.report()['source_errors'])
        self.assertTrue(self.report()['model_failure'])

    def test_thresholds_both_windows_and_multiple_buckets(self):
        data = normalize({'rateLimitsByLimitId': {'a': {'primary': {'usedPercent': 20}, 'secondary': {'usedPercent': 81}},
                                               'b': {'primary': {'usedPercent': 96}}}})
        self.assertEqual(len(data['windows']), 3)
        self.assertEqual(evaluate(data)['state'], 'critical')
        self.assertEqual(evaluate(self.quota(80))['state'], 'warning')
        self.assertEqual(evaluate(self.quota(100))['state'], 'exhausted')
        self.assertEqual(evaluate(self.quota(95), warning=60, critical=98)['state'], 'warning')

    def test_stale_missing_reset_and_invalid_quota_are_unknown(self):
        data = self.quota(99)
        self.assertEqual(evaluate(data, clock=time.time() + 301)['state'], 'unknown')
        self.assertEqual(evaluate(self.quota(99, reset=time.time() - 1))['state'], 'unknown')
        self.assertEqual(evaluate(None)['state'], 'unknown')
        for percent in (-1, 101, True, float('nan')):
            with self.assertRaises(SafetyError):
                self.quota(percent)

    def test_quota_passive_observation_and_notice_deduplication(self):
        self.enable()
        self.write({'type': 'event_msg', 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'payload': {'type': 'token_count', 'rate_limits': {'primary': {'used_percent': 82}}}})
        r = self.scan()
        self.assertEqual(r['quota']['state'], 'warning')
        first = monitor.take_notice(self.home, self.m, self.project, 'PostToolUse', r)
        self.assertIn('整理检查点', first)
        self.assertEqual(monitor.take_notice(self.home, self.m, self.project, 'PostToolUse', r), '')
        self.assertEqual(self.report()['pending_messages'], 0)

    def test_hook_additional_context_is_advisory_and_not_a_block(self):
        self.enable()
        self.message()
        out = run_hook(self.home, 'codex', 'PostToolUse', {'cwd': str(self.project), 'session_id': self.sid,
                                                         'transcript_path': str(self.path)})
        self.assertIn('尚未总结', out['hookSpecificOutput']['additionalContext'])
        self.assertNotIn('decision', out)
        self.assertNotIn('continue', out)

    def test_partial_record_is_not_consumed_until_newline(self):
        self.enable()
        start = self.path.stat().st_size
        line = json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                           'content': [{'type': 'input_text', 'text': '下一步验证'}]}})
        with self.path.open('a') as f:
            f.write(line)
        self.scan()
        self.assertEqual(self.report()['streams'][0]['observed_cursor'], start)
        with self.path.open('a') as f:
            f.write('\n')
        self.scan()
        self.assertEqual(self.report()['pending_messages'], 1)

    def test_truncation_and_anchor_rewrite_preserve_cursor(self):
        self.enable()
        self.message()
        self.scan()
        before = self.home.snapshot()
        self.path.write_text('{}\n')
        with self.assertRaises(SafetyError):
            self.scan()
        self.assertEqual(before, self.home.snapshot())

    def test_path_identity_symlink_and_hardlink_refused(self):
        self.enable()
        outside = self.root / self.path.name
        outside.write_text(self.path.read_text())
        with self.assertRaises(SafetyError):
            monitor.scan(self.home, self.m, self.project, self.sid, str(outside))
        self.path.unlink()
        self.path.symlink_to(outside)
        with self.assertRaises((SafetyError, OSError)):
            self.scan()
        self.path.unlink()
        os.link(outside, self.path)
        with self.assertRaises(SafetyError):
            self.scan()

    def test_malformed_source_remains_pending_and_cannot_be_acknowledged(self):
        self.enable()
        with self.path.open('a') as f:
            f.write('{broken}\n')
        self.message()
        self.scan()
        self.assertTrue(self.report()['source_gap'])
        with self.assertRaises(SafetyError):
            self.cp(review_discussion=[self.token()])

    def test_other_project_context_is_not_imported(self):
        self.enable()
        self.write({'type': 'turn_context', 'payload': {'cwd': str(self.root / 'other')}})
        self.message('其他项目决定')
        self.scan()
        self.assertEqual(self.report()['pending_messages'], 0)

    def test_acknowledgement_rolls_back_if_checkpoint_transaction_fails(self):
        self.enable()
        self.message()
        self.scan()
        before = self.home.read(monitor.location(self.m))
        original = Transaction.put
        def fail(tx, rel, *args, **kw):
            if rel == '.agent/CHECKPOINT.json':
                raise SafetyError('synthetic failure')
            return original(tx, rel, *args, **kw)
        with patch.object(Transaction, 'put', fail):
            with self.assertRaises(SafetyError):
                self.cp(review_discussion=[self.token()])
        self.assertEqual(before, self.home.read(monitor.location(self.m)))
        self.assertEqual(self.report()['pending_messages'], 1)

    def test_stale_private_state_write_preserves_external_change(self):
        self.enable()
        stale = monitor.load(self.home, self.m)
        path = self.home.root / monitor.location(self.m)
        changed = json.loads(path.read_text())
        changed['external_note'] = 'preserve this change'
        path.write_text(json.dumps(changed))
        before = path.read_bytes()
        with self.assertRaises(SafetyError):
            monitor.save(self.home, self.m, stale, self.project)
        self.assertEqual(path.read_bytes(), before)

    def test_private_candidates_never_enter_project_checkpoint(self):
        self.enable()
        self.message('决定采用 PRIVATE-DISCUSSION-CONTENT')
        self.scan()
        cp = self.cp()
        self.assertNotIn('PRIVATE-DISCUSSION-CONTENT', json.dumps(cp))
        self.assertIn('PRIVATE-DISCUSSION-CONTENT', json.dumps(self.report(True)))

    def test_explicit_quota_refresh_does_not_start_a_model(self):
        with patch('chorotheia.monitor.read_native', return_value=self.quota(88)) as read:
            r = monitor.refresh(self.home, self.m, self.project, '/absolute/codex')
        read.assert_called_once_with('/absolute/codex')
        self.assertEqual(r['quota']['state'], 'warning')

    def test_warning_and_pending_discussion_survive_restore_budget(self):
        self.enable()
        self.message()
        self.scan()
        with patch('chorotheia.monitor.read_native', return_value=self.quota(98)):
            monitor.refresh(self.home, self.m, self.project, '/absolute/codex')
        self.cp(summary='长历史。' * 100)
        m = core.require(self.tree)[0]
        r = restore(self.tree, m, 1500, self.report())
        self.assertIn('Attention', r['loaded_fields'])
        self.assertIn('Quota', r['loaded_fields'])
        self.assertIn('尚未总结', r['text'])
        self.assertLessEqual(r['utf8_bytes'], 1500)

    def test_cli_configuration_and_preview_zero_writes(self):
        base = [sys.executable, '-B', '-m', 'chorotheia', 'monitor', '--project', str(self.project),
                '--home', str(self.home.root)]
        before = self.home.snapshot()
        r = subprocess.run(base + ['--enable', '--quota-warning', '70', '--dry-run'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(before, self.home.snapshot())
        r = subprocess.run(base + ['--enable', '--quota-warning', '70'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['settings']['warning_percent'], 70)
        with self.assertRaises(SafetyError):
            monitor.configure(self.home, self.m, self.project, warning=99, critical=90)
        invalid = subprocess.run(base + ['--quota-warning', '99', '--quota-critical', '90', '--dry-run'], capture_output=True)
        self.assertEqual(invalid.returncode, 2)

    def test_oversized_hook_event_is_diagnostic_not_blocking(self):
        self.enable()
        before, project = self.home.snapshot(), self.tree.snapshot()
        payload = {'cwd': str(self.project), 'session_id': self.sid, 'transcript_path': str(self.path),
                   'tool_input': {'content': 'unrelated tool payload ' * 10000}}
        result = subprocess.run([sys.executable, '-B', '-m', 'chorotheia', 'hook', '--agent', 'codex',
                                 '--event', 'PostToolUse', '--home', str(self.home.root)],
                                input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertIn('observation skipped', result.stderr)
        self.assertNotIn('unrelated tool payload', result.stderr)
        self.assertEqual(before, self.home.snapshot())
        self.assertEqual(project, self.tree.snapshot())

    def test_busy_observation_hook_does_not_block_tools_or_write_state(self):
        self.enable()
        before = self.home.read(monitor.location(self.m))
        payload = {'cwd': str(self.project), 'session_id': self.sid, 'transcript_path': str(self.path)}
        with lock(self.home, self.project):
            result = subprocess.run([sys.executable, '-B', '-m', 'chorotheia', 'hook', '--agent', 'codex',
                                     '--event', 'PostToolUse', '--home', str(self.home.root)],
                                    input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertIn('writer busy', result.stderr)
        self.assertEqual(before, self.home.read(monitor.location(self.m)))

    def old_install(self):
        target, user = self.root / 'installed', self.root / 'user'
        configs = hook_configs(target / 'bin/chorotheia')
        configs['codex']['hooks'] = {k: v for k, v in configs['codex']['hooks'].items()
                                    if k in {'SessionStart', 'PreCompact', 'PostCompact', 'Stop'}}
        with patch('chorotheia.installation.hook_configs', return_value=configs):
            install(Path(__file__).resolve().parents[1], target, user)
        return target, user, configs

    def test_maintenance_adds_events_without_touching_existing_definitions_or_trust(self):
        target, user, configs = self.old_install()
        trust = user / '.codex/config.toml'
        trust.write_text('# existing native trust must be preserved\n')
        r = upgrade_global(target, source=Path(__file__).resolve().parents[1])
        self.assertTrue(r['changed'])
        new = json.loads((user / '.codex/hooks.json').read_text())
        for event, definition in configs['codex']['hooks'].items():
            self.assertEqual(new['hooks'][event], definition)
        self.assertIn('PostModelRequest', new['hooks'])
        self.assertEqual(trust.read_text(), '# existing native trust must be preserved\n')
        self.assertFalse(upgrade_global(target, source=Path(__file__).resolve().parents[1])['changed'])

    def test_maintenance_preserves_modified_native_hooks(self):
        target, user, configs = self.old_install()
        path = user / '.codex/hooks.json'
        configs['custom-user-setting'] = 'keep'
        path.write_text(json.dumps(configs))
        before = path.read_bytes()
        r = upgrade_global(target, source=Path(__file__).resolve().parents[1])
        self.assertIn('.codex/hooks.json', r['preserved_modified_registrations'])
        self.assertEqual(before, path.read_bytes())

    def test_native_rpc_sends_only_initialize_and_rate_limit_read(self):
        binary = self.root / 'codex'
        log = self.root / 'rpc-methods.jsonl'
        script = ('#!' + sys.executable + '\nimport sys,json\n'
                  'for line in sys.stdin:\n'
                  ' r=json.loads(line)\n'
                  ' with open(' + repr(str(log)) + ',"a") as f:f.write(r["method"]+"\\n")\n'
                  ' if r.get("id")==1: print(json.dumps({"id":1,"result":{}}),flush=True)\n'
                  ' if r.get("id")==2: print(json.dumps({"id":2,"result":{"rateLimits":{"primary":{"usedPercent":83}}}}),flush=True)\n')
        binary.write_text(script)
        binary.chmod(0o700)
        r = read_native(binary)
        self.assertEqual(evaluate(r)['state'], 'warning')
        self.assertEqual(log.read_text().splitlines(), ['initialize', 'initialized', 'account/rateLimits/read'])

    def test_native_rpc_timeout_is_bounded_and_process_is_reaped(self):
        binary = self.root / 'codex'
        binary.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(30)\n')
        binary.chmod(0o700)
        start = time.monotonic()
        with self.assertRaises(SafetyError):
            read_native(binary, timeout=0.05)
        self.assertLess(time.monotonic() - start, 3)


if __name__ == '__main__':
    unittest.main()

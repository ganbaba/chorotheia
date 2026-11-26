"""Progress freshness and field-priority loading in isolated local fixtures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from chorotheia import core
from chorotheia.adapters import run_hook
from chorotheia.continuity import assess
from chorotheia.guard import Tree, SafetyError
from chorotheia.memory import restore


class Continuity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='chorotheia-continuity-')
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.tree = Tree(self.project)
        self.home = Tree(self.root / 'home', create=True, private=True)

    def tearDown(self):
        self.tree.close()
        self.home.close()
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.project), *args], stderr=subprocess.DEVNULL)

    def init_git(self):
        self.git('init', '-q')
        (self.project / 'work.py').write_text('base\n')
        self.git('add', 'work.py')
        core.initialize(self.tree, self.home)

    def checkpoint(self, **kwargs):
        return core.checkpoint(self.tree, self.home, kwargs.pop('summary', 'Observed progress'), **kwargs)['checkpoint']

    def load(self, budget=2400):
        return restore(self.tree, core.require(self.tree)[0], budget)

    def status(self):
        return assess(self.tree, core.require(self.tree)[0])

    def test_long_chinese_summary_cannot_hide_next_blocker_decision_or_test(self):
        core.initialize(self.tree, self.home)
        self.checkpoint(summary='很长的历史背景' * 500, next_steps=['执行中文导出验证'],
                        errors=['等待测试设备'], decisions=['保留旧接口'], tests=['export: passed'])
        r = self.load()
        for text in ('执行中文导出验证', '等待测试设备', '保留旧接口', 'export: passed'):
            self.assertIn(text, r['text'])
        self.assertIn('Goal', [item['field'] for item in r['omitted']])
        self.assertNotIn('SOURCE .agent/STATE.md', r['text'])
        self.assertLessEqual(r['utf8_bytes'], 2400)

    def test_complete_sentences_and_atomic_command_entries(self):
        core.initialize(self.tree, self.home)
        command = 'python verify.py --case ' + 'x' * 2000
        self.checkpoint(summary='完成第一阶段。' + '很长的第二句话' * 100 + '。',
                        next_steps=['读取测试结果'], tests=[command])
        r = self.load()
        self.assertEqual(r['loaded_fields']['Goal'], ['完成第一阶段。'])
        self.assertNotIn('python verify.py', r['text'])
        self.assertIn('Test', [x['field'] for x in r['omitted']])
        for line in r['text'].splitlines():
            if line.startswith(('Goal: ', 'Next: ')):
                self.assertIsInstance(json.loads(line.split(': ', 1)[1]), str)

    def test_first_items_reserved_before_extra_next_steps(self):
        core.initialize(self.tree, self.home)
        self.checkpoint(summary='目标', next_steps=['step ' + str(i) for i in range(100)],
                        errors=['阻塞项'], tests=['latest: passed'], decisions=['决策'])
        r = self.load(1500)
        self.assertIn('阻塞项', r['text'])
        self.assertIn('latest: passed', r['text'])
        self.assertIn('决策', r['text'])

    def test_tiny_budgets_keep_safety_source_and_omission_notice(self):
        core.initialize(self.tree, self.home)
        self.checkpoint(goal='修复中文导出', summary='进展', completed=['读取源码'],
                        next_steps=['运行验证'], errors=['阻塞'], decisions=['决定'], tests=['通过'], phase='实现')
        for budget in (256, 300, 512, 1500, 2400):
            r = self.load(budget)
            self.assertLessEqual(len(r['text'].encode()), budget)
            self.assertIn('untrusted', r['text'])
            self.assertIn('SOURCE .agent/CHECKPOINT.json', r['text'])
            self.assertIn('Omitted', r['text'])

    def test_legacy_and_initial_snapshots_never_become_reviewed(self):
        self.init_git()
        self.assertEqual(self.status()['state'], 'unknown')
        run_hook(self.home, 'codex', 'Stop', {'cwd': str(self.project)})
        cp = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        self.assertIsNone(cp['reviewed_at'])
        self.assertIsNone(cp['covered_git'])
        self.assertEqual(self.status()['state'], 'unknown')

    def test_memory_writes_do_not_invalidate_review(self):
        self.init_git()
        cp = self.checkpoint()
        for event in ('PreCompact', 'Stop', 'Stop'):
            run_hook(self.home, 'codex', event, {'cwd': str(self.project)})
        latest = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        self.assertEqual(latest['reviewed_at'], cp['reviewed_at'])
        self.assertEqual(latest['reviewed_checkpoint_id'], cp['id'])
        self.assertNotEqual(latest['snapshot_at'], cp['snapshot_at'])
        self.assertEqual(self.status()['state'], 'reviewed')

    def test_same_dirty_status_content_changes_require_review(self):
        self.init_git()
        p = self.project / 'work.py'
        p.write_text('version one\n')
        cp = self.checkpoint()
        before = self.git('status', '--porcelain=v1', '--', 'work.py')
        p.write_text('version two\n')
        run_hook(self.home, 'codex', 'Stop', {'cwd': str(self.project)})
        latest = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        self.assertEqual(self.git('status', '--porcelain=v1', '--', 'work.py'), before)
        self.assertEqual(latest['covered_git'], cp['covered_git'])
        self.assertNotEqual(latest['observed_git']['fingerprint'], cp['covered_git']['fingerprint'])
        self.assertEqual(self.status()['state'], 'needs_review')
        self.assertIn('needs_review', self.load()['text'])
        # Explicitly confirming unchanged notes can acknowledge the new baseline.
        self.checkpoint()
        self.assertEqual(self.status()['state'], 'reviewed')

    def test_untracked_content_and_staging_changes_detected(self):
        self.init_git()
        p = self.project / 'new.py'
        p.write_text('first')
        self.checkpoint()
        p.write_text('second')
        self.assertEqual(self.status()['state'], 'needs_review')
        self.checkpoint()
        self.git('add', 'new.py')
        self.assertEqual(self.status()['state'], 'needs_review')

    def test_head_movement_detected_even_when_tree_matches(self):
        self.init_git()
        self.git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        self.checkpoint()
        self.git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture two')
        self.assertEqual(self.status()['state'], 'needs_review')

    def test_discussion_phase_requires_explicit_completion(self):
        core.initialize(self.tree, self.home)
        self.checkpoint(goal='设计接力', phase='讨论方案')
        self.assertEqual(self.status()['state'], 'phase_open')
        run_hook(self.home, 'codex', 'Stop', {'cwd': str(self.project)})
        self.assertEqual(self.status()['state'], 'phase_open')
        with self.assertRaises(SafetyError):
            self.checkpoint(phase='另一个阶段')
        self.checkpoint(phase_state='complete')
        self.assertEqual(self.status()['phase']['state'], 'complete')
        # No Git evidence: completing a discussion stage is not proof of all work.
        self.assertEqual(self.status()['state'], 'unknown')

    def test_unsafe_or_sensitive_changed_content_is_unknown(self):
        self.init_git()
        self.checkpoint()
        (self.project / 'link.py').symlink_to(self.root / 'outside')
        self.assertFalse(self.status()['observed_git']['available'])
        (self.project / 'link.py').unlink()
        (self.project / '.env').write_text('password=never-record-this')
        r = self.status()
        self.assertEqual(r['state'], 'unknown')
        self.assertNotIn('never-record-this', json.dumps(r))

    def test_review_preview_does_not_change_stage_or_private_receipt(self):
        self.init_git()
        before, private = self.tree.snapshot(), self.home.snapshot()
        r = core.checkpoint(self.tree, self.home, 'Preview', phase='阶段', dry_run=True)
        self.assertEqual(r['would_checkpoint']['phase']['state'], 'open')
        self.assertEqual(before, self.tree.snapshot())
        self.assertEqual(private, self.home.snapshot())

    def test_cli_goal_phase_and_freshness(self):
        self.init_git()
        base = [sys.executable, '-B', '-m', 'chorotheia']
        opts = ['--project', str(self.project), '--home', str(self.home.root)]
        cp = subprocess.run(base + ['checkpoint', '--summary', '实现完成', '--goal', '改进恢复',
                                    '--done', '添加测试', '--phase', '实现', '--phase-state', 'complete'] + opts,
                            capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(cp.stdout)['freshness']['state'], 'reviewed')
        s = subprocess.run(base + ['status'] + opts, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(s.stdout)['freshness']['state'], 'reviewed')

    def test_snapshot_preserves_goal_completed_phase_and_test_reports(self):
        self.init_git()
        cp = self.checkpoint(goal='明确目标', completed=['已完成'], phase='验证',
                             tests=['manual command: passed'], decisions=['决定'], errors=['阻塞'])
        run_hook(self.home, 'codex', 'PreCompact', {'cwd': str(self.project)})
        later = json.loads(self.tree.read('.agent/CHECKPOINT.json'))
        for key in ('goal', 'completed', 'phase', 'tests', 'decisions', 'errors', 'covered_git', 'reviewed_at'):
            self.assertEqual(cp[key], later[key], key)
        self.assertEqual(self.status()['state'], 'phase_open')

    def test_corrupt_and_edited_checkpoints_cannot_claim_reviewed(self):
        self.init_git()
        self.checkpoint()
        p = self.project / '.agent/CHECKPOINT.json'
        data = json.loads(p.read_text())
        data['summary'] = 'externally edited'
        p.write_text(json.dumps(data))
        self.assertEqual(self.status()['state'], 'unknown')
        with self.assertRaises(SafetyError):
            self.checkpoint()
        p.write_text('{broken')
        r = self.load()
        self.assertIn('CORRUPT', r['text'])
        self.assertEqual(r['freshness']['state'], 'unknown')

    def test_non_git_review_remains_explicit_but_coverage_unknown(self):
        core.initialize(self.tree, self.home)
        cp = self.checkpoint(goal='讨论目标')
        self.assertTrue(cp['reviewed_at'])
        self.assertEqual(self.status()['state'], 'unknown')

    def test_large_changes_and_external_symlinks_do_not_get_read(self):
        self.init_git()
        self.checkpoint()
        p = self.project / 'large.bin'
        p.write_bytes(b'x' * (4 * 1024 * 1024 + 1))
        self.assertEqual(self.status()['state'], 'unknown')
        p.unlink()
        outside = self.root / 'outside'
        outside.write_text('private outside project')
        (self.project / 'link').symlink_to(outside)
        r = self.status()
        self.assertEqual(r['state'], 'unknown')
        self.assertNotIn('private outside project', json.dumps(r))


if __name__ == '__main__':
    unittest.main()

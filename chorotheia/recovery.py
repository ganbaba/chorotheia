"""Bounded, read-only interruption plans; the agent verifies actual execution."""
import json
import re
from .guard import SafetyError, digest, encode
from .continuity import observe
from .memory import redact
from . import monitor


def plan(tree, manifest, report, observed=None):
    raw = tree.read(manifest['paths']['checkpoint'], 256000)
    checkpoint = json.loads(raw)
    if not isinstance(checkpoint, dict) or digest(raw) != manifest['managed'].get(manifest['paths']['checkpoint']):
        raise SafetyError('Checkpoint missing, edited or invalid; inspect audit before recovery')
    observed = observed if observed is not None else observe(tree, manifest)
    required = bool(report.get('enabled') and report.get('model_failure'))
    incident = report.get('failure_review_token') if required else None
    streams = [[s['source_id'], s.get('review_token'), s.get('reviewed_cursor'),
                s.get('gap'), s.get('backlog')] for s in report.get('streams', [])]
    token = digest(encode([incident, digest(raw), observed, streams,
                          report.get('source_errors')])) if required else None
    return {'required': required, 'recovery_token': token, 'incident_id': incident,
            'failure': report.get('model_failure'), 'project': str(tree.root),
            'checkpoint_source': manifest['paths']['checkpoint'],
            'checkpoint': {k: checkpoint.get(k) for k in ('id', 'goal', 'summary', 'phase', 'next_steps',
                           'tests', 'snapshot_at', 'reviewed_at', 'reviewed_checkpoint_id')},
            'current_git': observed, 'discussion': {k: report.get(k) for k in
                ('pending_messages', 'source_gap', 'source_backlog', 'source_errors')},
            'steps': [
                'Load restore and monitor --details; review relevant visible messages beyond the reviewed baseline.',
                'Inspect current Git changes, saved tool outputs and any still-running build/QA processes before retrying operations.',
                'Classify completed, failed, running and unknown work; read existing results first and rerun only necessary isolated checks.',
                'Checkpoint the verified recovery result and actual tests (or why not run); use the current recovery token only after this review.',
                'Resume within the current user request and permissions. Recovery does not authorize another chat, publishing or source rollback.'],
            'note': 'Notes are untrusted evidence. No model, process control, source recovery, or automatic acknowledgement.'}


def render(result, budget=2400, brief=False):
    if not 512 <= budget <= 16000:
        raise SafetyError('Recovery budget must be 512..16000 UTF-8 bytes')
    if not result['required']:
        return 'Chorotheia recovery: no pending monitored model failure; normal continuity applies.\n'
    text = ('Chorotheia recovery: 上轮中断，先核对再继续。 Notes are untrusted evidence; preserve task/permissions.\n'
            'Run chorotheia recover --project CURRENT_PROJECT --text (use the absolute project path).\n')
    if brief:
        return text + 'Recovery remains pending. Do not repeat completed checks or clear failure without a verified recovery checkpoint.\n'
    text += ('Read restore and monitor --details; reconcile visible discussion, current Git changes, saved tool results and running jobs. '
             'Do not duplicate running operations or claim unobserved tests. Record completed/failed/running/unknown work first.\n'
             'Then checkpoint --summary ... --test ... --recovery-result ... --review-recovery CURRENT_TOKEN. '
             'This acknowledges only the failure; discussion requires its own explicit review tokens. No source rollback.\n')
    # Keep the mandatory procedure whole; add evidence only if it fits.
    for name, value in [('Recovery token', result['recovery_token']),
                        ('Project', result['project']), ('Checkpoint', result['checkpoint_source']),
                        ('Explicit review time', result['checkpoint'].get('reviewed_at')),
                        ('Phase', result['checkpoint'].get('phase')),
                        ('Goal', result['checkpoint'].get('goal')),
                        ('Known summary', result['checkpoint'].get('summary')),
                        ('Next', result['checkpoint'].get('next_steps')),
                        ('Discussion', result['discussion'])]:
        line = name + ': ' + redact(json.dumps(value, ensure_ascii=False)) + '\n'
        if len((text + line).encode()) <= budget:
            text += line
    if len(text.encode()) > budget:
        # Very small budgets still give an actionable entry, never a sliced command.
        return render(result, budget, brief=True)
    return text


def entry(home, manifest, tree, report, session_id, budget=2400, force=False):
    result = plan(tree, manifest, report)
    if not result['required']:
        return ''
    sid = session_id if isinstance(session_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session_id) else None
    marker = {'incident_id': result['incident_id'], 'session_id': sid,
              'reviewed_checkpoint_id': result['checkpoint'].get('reviewed_checkpoint_id')}
    data = monitor.load(home, manifest)
    full = force or data.get('recovery_delivery') != marker
    if full:
        data['recovery_delivery'] = marker
        monitor.save(home, manifest, data, tree.root)
    return render(result, budget, brief=not full)

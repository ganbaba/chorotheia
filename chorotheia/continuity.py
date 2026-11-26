"""Conservative freshness evidence; never infer semantic progress from snapshots."""
import json
import subprocess
from .guard import SafetyError, digest, encode
from .memory import git, SENSITIVE_PATH


def observe(tree, manifest):
    """Hash index entries and changed/untracked bytes without storing their content.

    Own memory is excluded to avoid making every checkpoint stale immediately.
    Unsafe, large or concurrently changing inputs produce unknown, never fresh.
    """
    def own(path):
        return (path == manifest['base'] or path.startswith(manifest['base'] + '/') or
                path in manifest['managed'])

    try:
        head = git(tree.root, 'rev-parse', '--verify', 'HEAD')
        index = git(tree.root, 'ls-files', '--stage', '-z')
        changes = git(tree.root, 'ls-files', '--modified', '--deleted', '--others',
                      '--exclude-standard', '-z')
        if index is None or changes is None:
            return {'available': False, 'reason': 'Git worktree unavailable'}
        entries = []
        for row in index.split(b'\0'):
            if row:
                metadata, path = row.split(b'\t', 1)
                if not own(path.decode('utf-8')):
                    entries.append(digest(metadata + b'\t' + path))
        names = sorted(set(p.decode('utf-8') for p in changes.split(b'\0') if p))
        names = [p for p in names if not own(p)]
        if len(names) > 1000:
            return {'available': False, 'reason': 'More than 1000 changed paths; review manually'}
        content, total = [], 0
        for path in names:
            if SENSITIVE_PATH.search(path):
                return {'available': False, 'reason': 'Sensitive changed path excluded from content inspection'}
            try:
                data = tree.read(path)
            except FileNotFoundError:
                data = None
            total += len(data) if data is not None else 0
            if total > 16 * 1024 * 1024:
                return {'available': False, 'reason': 'Changed content exceeds 16 MiB inspection budget'}
            content.append([digest(path.encode()), digest(data) if data is not None else None])
        # Catch common races; cooperative locks do not lock external editors.
        if (index != git(tree.root, 'ls-files', '--stage', '-z') or
                changes != git(tree.root, 'ls-files', '--modified', '--deleted', '--others',
                               '--exclude-standard', '-z') or
                head != git(tree.root, 'rev-parse', '--verify', 'HEAD')):
            return {'available': False, 'reason': 'Git changed during inspection'}
        return {'available': True, 'head': head.decode().strip() if head else None,
                'fingerprint': digest(encode([sorted(entries), content])),
                'method': 'index-and-changed-content-v1'}
    except (OSError, SafetyError, UnicodeError, ValueError, subprocess.SubprocessError):
        return {'available': False, 'reason': 'Cannot safely inspect changed content'}


def assess(tree, manifest, checkpoint=None, observed=None, monitoring=None):
    if checkpoint is None:
        try:
            checkpoint = json.loads(tree.read(manifest['paths']['checkpoint']))
            if not isinstance(checkpoint, dict):
                raise ValueError('Checkpoint must be an object')
        except (FileNotFoundError, ValueError):
            checkpoint = {}
    cp = checkpoint
    current = observed if observed is not None else observe(tree, manifest)
    covered = cp.get('covered_git') or {}
    phase = cp.get('phase') or {}
    if not isinstance(covered, dict):
        covered = {}
    if not isinstance(phase, dict):
        phase = {}
    phase_open = phase.get('state') == 'open'
    reasons = []
    reviewed = bool(cp.get('reviewed_at'))
    if not reviewed:
        reasons.append('No explicit progress review recorded (initial/legacy snapshot)')
    comparable = (current.get('available') and covered.get('available') and
                  covered.get('method') == current.get('method'))
    changed = comparable and any(current.get(k) != covered.get(k) for k in ('head', 'fingerprint'))
    if changed:
        reasons.append('Git content differs from the explicitly reviewed baseline; review needed, not proof of omission')
    if not comparable:
        reasons.append('Git coverage cannot be compared; discussion/external work cannot be inferred')
    if phase_open:
        reasons.append('Recorded phase has no explicit completion checkpoint')
    state = ('needs_review' if changed else 'phase_open' if phase_open else
             'reviewed' if reviewed and comparable else 'unknown')
    unreviewed = (monitoring.get('unsummarized_progress') if monitoring is not None else
                  (cp.get('unsummarized_progress') or {}).get('pending', False))
    if unreviewed:
        state = 'needs_review'
        reasons.append('尚未总结的进展：visible discussion, source gaps or model failure require explicit review')
    if tree.hash(manifest['paths']['checkpoint']) != manifest['managed'].get(manifest['paths']['checkpoint']):
        state = 'unknown'
        reasons.append('Checkpoint missing or edited; inspect audit before trusting coverage')
    return {'state': state, 'reasons': reasons, 'snapshot_at': cp.get('snapshot_at', cp.get('created_at')),
            'reviewed_at': cp.get('reviewed_at'), 'reviewed_checkpoint_id': cp.get('reviewed_checkpoint_id'),
            'phase': phase or None, 'observed_git': current, 'covered_git': covered or None,
            'note': 'Evidence only; reviewed does not prove note accuracy or detect all discussion-only work'}

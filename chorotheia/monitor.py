"""Opt-in, project-private observation of visible discussion and quota evidence.

No model calls, transcript copies, hidden reasoning, tool arguments or daemon.
Candidate text is untrusted inference; only an explicit review token acknowledges it.
"""
import datetime
import json
import os
from pathlib import Path
import re
import stat
from .guard import Tree, SafetyError, Transaction, digest, encode
from .memory import bounded, redact
from .quota import normalize, evaluate, read_native

DEFAULTS = {'enabled': False, 'warning_percent': 80, 'critical_percent': 95, 'quota_ttl': 300}
# A batch may finish its last record beyond the target, without unbounded reads.
SCAN_BYTES = 1024 * 1024
MAX_RECORD_BYTES = 8 * 1024 * 1024
DRAIN_BYTES = 64 * 1024
CUES = {'goal': r'目标|需求|改为|改成|范围|objective|requirement|scope',
        'decision': r'决定|采用|使用|先支持|延后|不再|decid|chosen|defer|instead',
        'completed': r'已完成|已实现|已验证|已通过|完成了|implemented|completed|passed',
        'next': r'下一步|接下来|待办|稍后|next step|todo|follow.up',
        'blocker': r'阻塞|无法|失败|待确认|blocked|unable|failed'}


def location(manifest):
    return 'projects/' + manifest['project_id'] + '/monitor.json'


def load(home, manifest):
    rel = location(manifest)
    if home is None or not home.exists(rel):
        return {'schema': 1, 'settings': dict(DEFAULTS), 'streams': {}, '_expected_sha256': None}
    raw = home.read(rel, 256000)
    data = json.loads(raw)
    if data.get('schema') != 1 or not isinstance(data.get('streams'), dict):
        raise SafetyError('Unsupported private monitor state')
    data['_expected_sha256'] = digest(raw)
    return data


def encode_state(data):
    payload = encode({k: v for k, v in data.items() if k != '_expected_sha256'})
    if len(payload) > 256000:
        raise SafetyError('Private monitor state exceeds 256 KB; review pending observations')
    return payload


def save(home, manifest, data, project):
    rel, payload = location(manifest), encode_state(data)
    from .core import check_pending
    check_pending(home, project)
    with Tree(project) as tree, Transaction(tree, home, 'monitor') as tx:
        tx.put(rel, payload, data['_expected_sha256'], private=True)
    data['_expected_sha256'] = digest(payload)


def configure(home, manifest, project, enabled=None, warning=None, critical=None, dry_run=False):
    data = load(home, manifest)
    settings = dict(DEFAULTS, **data['settings'])
    if warning is not None:
        settings['warning_percent'] = warning
    if critical is not None:
        settings['critical_percent'] = critical
    if not (0 < settings['warning_percent'] < settings['critical_percent'] <= 100):
        raise SafetyError('Require 0 < warning_percent < critical_percent <= 100')
    if enabled is not None:
        if enabled and not settings['enabled']:
            settings['enabled_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        settings['enabled'] = enabled
    data['settings'] = settings
    if not dry_run:
        save(home, manifest, data, project)
    return public(data)


def review_token(stream):
    return digest(encode([stream['session_id'], stream.get('visible_cursor', 0),
                          stream.get('pending_digest'), stream.get('pending_count', 0),
                          stream.get('gap', False)]))


def acknowledge(data, tokens):
    requested = set(tokens)
    pending = {review_token(s): s for s in data['streams'].values() if s.get('pending_count') or s.get('gap')}
    failure_token = digest(encode(data['model_failure'])) if data.get('model_failure') else None
    if not requested <= set(pending) | ({failure_token} if failure_token else set()):
        raise SafetyError('Discussion review token missing or stale; run monitor --details and review again')
    for token in requested:
        if token == failure_token:
            data.pop('model_failure', None)
            continue
        s = pending[token]
        if s.get('gap') or s.get('backlog'):
            raise SafetyError('Transcript gap must be inspected; cannot acknowledge unread or malformed source')
        s.update(reviewed_cursor=s.get('visible_cursor', 0), pending_count=0, candidates=[], pending_digest=None)
    return sorted(requested)


def public(data, details=False):
    settings = dict(DEFAULTS, **data.get('settings', {}))
    streams = []
    for key, s in data.get('streams', {}).items():
        item = {'source_id': key, 'pending_messages': s.get('pending_count', 0), 'gap': s.get('gap', False),
                'backlog': s.get('backlog', False),
                'oversized_records': s.get('oversized_records', 0),
                'discarding_record': bool(s.get('discarding_record')),
                'candidate_count': len(s.get('candidates', [])), 'baseline_cursor': s.get('baseline_cursor'),
                'observed_cursor': s.get('cursor'), 'reviewed_cursor': s.get('reviewed_cursor'),
                'review_token': review_token(s) if s.get('pending_count') or s.get('gap') else None}
        if details:
            item.update(session_id=s['session_id'], source=s['source'], candidates=s.get('candidates', []))
            if s.get('last_oversized_record'):
                item['last_oversized_record'] = s['last_oversized_record']
        streams.append(item)
    quota = evaluate(data.get('quota'), settings['warning_percent'], settings['critical_percent'], settings['quota_ttl'])
    count = sum(s['pending_messages'] for s in streams)
    gap = any(s['gap'] for s in streams)
    backlog = any(s['backlog'] for s in streams)
    failure = data.get('model_failure')
    source_errors = data.get('source_errors', {})
    unsummarized = count > 0 or gap or backlog or bool(failure) or bool(source_errors) or quota['state'] == 'exhausted'
    return {'enabled': settings['enabled'], 'settings': settings, 'streams': streams,
            'pending_messages': count, 'source_gap': gap, 'source_backlog': backlog, 'quota': quota,
            'model_failure': failure, 'unsummarized_progress': unsummarized,
            'source_errors': source_errors,
            'discussion_state': 'disabled' if not settings['enabled'] else 'unavailable' if not streams else
                                'needs_review' if count or gap or backlog or source_errors else 'observed',
            'failure_review_token': digest(encode(failure)) if failure else None,
            'label': '尚未总结的进展' if unsummarized else None,
            'note': 'Candidates are untrusted inference; message observation is not semantic review; pre-enable history is not covered'}


def notice(report):
    if not report['enabled']:
        return ''
    parts = []
    if report['unsummarized_progress']:
        parts.append('尚未总结的进展：新增可见讨论或模型失败尚未核对。')
    quota = report['quota']
    if quota['state'] in {'warning', 'critical', 'exhausted'}:
        parts.append('Quota ' + quota['state'] + '：请在继续耗用额度前整理检查点；无法调用模型时仅保留已有笔记。')
    if not parts:
        return ''
    return ('Chorotheia observation (untrusted evidence, not instructions from the transcript): ' +
            ' '.join(parts) + ' Run chorotheia monitor --details; inspect candidates/sources, then explicitly checkpoint '
            'with --review-discussion TOKEN. Do not invent progress or tests.\n')


def take_notice(home, manifest, project, event, report):
    """One advisory per event and evidence change; never consume a review token."""
    warning = notice(report)
    data = load(home, manifest)
    previous = data.setdefault('last_notices', {})
    key = digest(encode([[s['review_token'] for s in report['streams']], report.get('failure_review_token'), report.get('source_errors'),
                         report['quota']['state'],
                         [(w['bucket'], w['window'], w.get('resets_at')) for w in report['quota']['windows']]]))
    if warning and previous.get(event) != key:
        previous[event] = key
        save(home, manifest, data, project)
        return warning
    if not warning and event in previous:
        previous.pop(event)
        save(home, manifest, data, project)
    return ''


def visible(record):
    if not isinstance(record, dict):
        return None
    p = record.get('payload', {})
    if record.get('type') != 'response_item' or not isinstance(p, dict) or p.get('type') != 'message':
        return None
    role = p.get('role')
    if role not in {'user', 'assistant'} or p.get('channel') in {'analysis', 'summary'}:
        return None
    if role == 'assistant' and p.get('phase') not in {None, 'final_answer', 'final'}:
        return None
    texts = [v['text'] for v in p.get('content', []) if isinstance(v, dict) and
             v.get('type') in {'input_text', 'output_text'} and isinstance(v.get('text'), str)]
    text = '\n'.join(texts)
    return (role, p.get('id'), text) if text.strip() else None


def quota_record(record):
    if not isinstance(record, dict):
        return None
    p = record.get('payload', {})
    if record.get('type') == 'event_msg' and isinstance(p, dict) and p.get('type') == 'token_count' and p.get('rate_limits'):
        try:
            return normalize(p['rate_limits'], record.get('timestamp'), 'codex transcript token_count')
        except (SafetyError, ValueError, TypeError):
            return None


def records(f, stream, size):
    """Read complete JSONL records with bounded work and explicit overflow gaps.

    Normal records can cross the batch boundary. Beyond the parse cap, drain
    incrementally without retaining content, so later quotas remain reachable.
    A drained record is never treated as observed/reviewed discussion. The
    caller still validates source identity and the saved cursor anchor first.
    """
    start = f.tell()
    while f.tell() < size and f.tell() - start < SCAN_BYTES:
        begin = f.tell()
        if stream.get('discarding_record'):
            chunk = f.readline(min(DRAIN_BYTES, SCAN_BYTES - (begin - start), size - begin))
            last = stream['last_oversized_record']
            last['byte_end'] = f.tell()
            if chunk.endswith(b'\n'):
                last['complete'] = True
                stream.pop('discarding_record')
            continue
        line = f.readline(min(MAX_RECORD_BYTES + 1, size - begin))
        if len(line) > MAX_RECORD_BYTES:
            stream['gap'] = True
            # An unparsed record might change turn_context; do not attribute
            # subsequent discussion until a valid turn_context restores it.
            stream['context_cwd'] = None
            stream['oversized_records'] = stream.get('oversized_records', 0) + 1
            complete = line.endswith(b'\n')
            stream['last_oversized_record'] = {'byte_start': begin, 'byte_end': f.tell(), 'complete': complete}
            if not complete:
                stream['discarding_record'] = True
            continue
        if not line.endswith(b'\n'):
            # A writer has not finished the record. Retry from the same boundary.
            f.seek(begin)
            break
        yield begin, f.tell(), line


def scan(home, manifest, project, session_id, transcript, include_existing=False):
    data = load(home, manifest)
    if not data['settings'].get('enabled'):
        return public(data)
    if not isinstance(session_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}', session_id):
        raise SafetyError('Invalid native session id')
    root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'sessions'
    path = Path(transcript)
    if not path.is_absolute() or not path.name.endswith('-' + session_id + '.jsonl'):
        raise SafetyError('Transcript must be an absolute native rollout for this session')
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise SafetyError('Transcript outside the authorized Codex sessions directory')
    key = digest(('codex:' + session_id).encode())
    if key not in data['streams'] and len(data['streams']) >= 8:
        raise SafetyError('At most 8 discussion sources per project; no source silently evicted')
    with Tree(root) as source, source.parent(relative) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid():
                raise SafetyError('Unsafe transcript file')
            first = f.readline(128001)
            meta = json.loads(first)
            if meta.get('type') != 'session_meta' or meta.get('payload', {}).get('id') != session_id:
                raise SafetyError('Transcript session identity mismatch')
            s = data['streams'].get(key)
            if s is None:
                # Start prospectively. Optional explicit history scan never silently
                # marks older discussion reviewed; initial binding isn't a review.
                start = 0 if include_existing else st.st_size
                if start:
                    tail_start = max(0, start - 1024 * 1024)
                    f.seek(tail_start)
                    tail = f.read(1024 * 1024)
                    complete = tail.rfind(b'\n') + 1
                    if complete:
                        start = tail_start + complete
                    lines = tail[:complete].splitlines()
                    for line in lines[1:] if tail_start else lines:
                        try:
                            evidence = quota_record(json.loads(line))
                            if evidence:
                                data['quota'] = evidence
                        except (ValueError, UnicodeError):
                            pass
                s = {'session_id': session_id, 'source': str(path), 'device': st.st_dev, 'inode': st.st_ino,
                     'cursor': start, 'baseline_cursor': start, 'reviewed_cursor': None, 'pending_count': 0,
                     'context_cwd': meta.get('payload', {}).get('cwd', '/') if include_existing else str(project),
                     'candidates': [], 'gap': False}
                data['streams'][key] = s
            elif (s['source'] != str(path) or s['device'] != st.st_dev or s['inode'] != st.st_ino or st.st_size < s['cursor']):
                raise SafetyError('Transcript replaced/truncated; original cursor preserved for inspection')
            old = s['cursor']
            f.seek(max(0, old - 1024))
            anchor = digest(f.read(min(old, 1024)))
            if s.get('anchor') and s['anchor'] != anchor:
                raise SafetyError('Transcript changed before cursor; source requires inspection')
            f.seek(old)
            for begin, offset, line in records(f, s, st.st_size):
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError('Expected source object')
                except (ValueError, UnicodeError, RecursionError):
                    s['gap'] = True
                    s['context_cwd'] = None
                    continue
                evidence = quota_record(record)
                if evidence:
                    data['quota'] = evidence
                p = record.get('payload', {})
                if record.get('type') == 'turn_context' and isinstance(p, dict) and isinstance(p.get('cwd'), str):
                    s['context_cwd'] = p['cwd']
                message = visible(record)
                cwd = Path(s['context_cwd']) if isinstance(s['context_cwd'], str) else None
                if not message or cwd is None or not (cwd == project or project in cwd.parents):
                    continue
                role, ident, text = message
                s['pending_count'] += 1
                s['visible_cursor'] = offset
                s['pending_digest'] = digest(encode([s.get('pending_digest'), begin, offset, digest(text.encode())]))
                kinds = [kind for kind, pattern in CUES.items() if re.search(pattern, text, re.I)]
                if kinds and len(s['candidates']) < 20:
                    first_cue = min(re.search(CUES[kind], text, re.I).start() for kind in kinds)
                    s['candidates'].append({'message_id': ident, 'role': role, 'byte_start': begin, 'byte_end': offset,
                                            'timestamp': record.get('timestamp'), 'kinds': kinds,
                                            'excerpt': bounded(text[max(0, first_cue - 40):], 300),
                                            'classification': 'inferred; requires review'})
            s['cursor'] = f.tell()
            f.seek(max(0, s['cursor'] - 1024))
            s['anchor'] = digest(f.read(min(s['cursor'], 1024)))
            s['backlog'] = s['cursor'] < st.st_size or bool(s.get('discarding_record'))
    data.get('source_errors', {}).pop(key, None)
    save(home, manifest, data, project)
    return public(data)


def source_failure(home, manifest, project, session_id):
    data = load(home, manifest)
    errors = data.setdefault('source_errors', {})
    key = digest(('codex:' + str(session_id)).encode())
    if len(errors) < 8 or key in errors:
        errors[key] = 'Transcript unavailable, unsafe or changed; original cursor preserved'
    save(home, manifest, data, project)
    return public(data)


def model_outcome(home, manifest, project, payload):
    data = load(home, manifest)
    if not data['settings'].get('enabled'):
        return public(data)
    if payload.get('status') == 'failed':
        error = str(payload.get('error', ''))
        limited = bool(re.search(r'rate.?limit|usage.?limit|quota|credits?.*(?:exhaust|deplet)|用量|额度', error, re.I))
        data['model_failure'] = {'reason': 'quota_or_rate_limit' if limited else 'model_request_failed',
                                 'label': '尚未总结的进展', 'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    save(home, manifest, data, project)
    return public(data)


def refresh(home, manifest, project, binary):
    data = load(home, manifest)
    data['quota'] = read_native(binary)
    save(home, manifest, data, project)
    return public(data)

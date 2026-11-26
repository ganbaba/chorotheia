"""Quota evidence, not token-count guesses; optional short-lived native RPC."""
import datetime
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from .guard import SafetyError, absolute


def normalize(raw, timestamp=None, source='native'):
    if not isinstance(raw, dict):
        raise SafetyError('Quota data must be an object')
    # Preserve every metered bucket and both windows, not only the legacy bucket.
    buckets = raw.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        single = raw.get('rateLimits', raw)
        if not isinstance(single, dict):
            raise SafetyError('No usable native quota bucket')
        buckets = {single.get('limitId', single.get('limit_id', 'codex')): single}
    windows = []
    reached = False
    for bucket, data in buckets.items():
        if not isinstance(data, dict):
            continue
        reached |= bool(data.get('rateLimitReachedType') or data.get('rate_limit_reached_type') or
                        data.get('spend_control_reached'))
        for name in ('primary', 'secondary'):
            w = data.get(name)
            if not isinstance(w, dict):
                continue
            used = w.get('usedPercent', w.get('used_percent'))
            reset = w.get('resetsAt', w.get('resets_at'))
            if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100:
                raise SafetyError('Invalid quota percentage')
            if reset is not None and (isinstance(reset, bool) or not isinstance(reset, (int, float)) or not math.isfinite(reset)):
                raise SafetyError('Invalid quota reset time')
            windows.append({'bucket': str(bucket)[:80], 'window': name, 'used_percent': used,
                            'resets_at': reset, 'window_minutes': w.get('windowDurationMins', w.get('window_minutes'))})
    if not windows and not reached:
        raise SafetyError('No usable quota windows')
    stamp = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {'observed_at': stamp, 'source': source, 'windows': windows, 'limit_reached': reached}


def evaluate(evidence, warning=80, critical=95, ttl=300, clock=None):
    now = time.time() if clock is None else clock
    result = {'state': 'unknown', 'windows': [], 'reason': 'No recent quota evidence'}
    if not isinstance(evidence, dict):
        return result
    try:
        stamp = datetime.datetime.fromisoformat(evidence['observed_at'].replace('Z', '+00:00')).timestamp()
    except (KeyError, ValueError, TypeError):
        return result
    if now - stamp > ttl or stamp > now + 30:
        return dict(result, reason='Quota evidence expired or has a future timestamp')
    windows = evidence.get('windows', [])
    # A reset does not imply zero use; require a new observation instead.
    if any(w.get('resets_at') is not None and w['resets_at'] <= now for w in windows):
        return dict(result, reason='Quota window reset; refresh evidence')
    highest = max([w['used_percent'] for w in windows] or [0])
    state = ('exhausted' if evidence.get('limit_reached') or highest >= 100 else
             'critical' if highest >= critical else 'warning' if highest >= warning else 'normal')
    return {'state': state, 'windows': windows, 'observed_at': evidence['observed_at'],
            'source': evidence.get('source'), 'warning_percent': warning, 'critical_percent': critical}


def read_native(binary, timeout=8):
    """Initialize and read account limits only. No thread, model or login request.

    The native executable manages its own existing authentication. Raw RPC replies,
    stderr, and credentials are never persisted or returned on failure.
    """
    path = absolute(binary)
    if path.name != 'codex' or not path.is_file() or not os.access(path, os.X_OK):
        raise SafetyError('Supply an absolute native codex executable')
    proc = subprocess.Popen([str(path), 'app-server', '--listen', 'stdio://'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    buffer, total = b'', 0
    deadline = time.monotonic() + timeout

    def send(obj):
        proc.stdin.write((json.dumps(obj) + '\n').encode())
        proc.stdin.flush()

    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'chorotheia-quota', 'version': '1.0.0'},
                                                                      'capabilities': {'experimentalApi': True}}})
        while time.monotonic() < deadline:
            if not sel.select(max(0, deadline - time.monotonic())):
                break
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            total += len(chunk)
            if total > 1024 * 1024 or len(buffer) > 256000:
                raise SafetyError('Quota RPC response exceeds bounds')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                response = json.loads(line)
                if response.get('id') not in (1, 2):
                    continue
                if 'error' in response:
                    raise SafetyError('Native quota RPC unavailable; no credentials or raw error captured')
                if response['id'] == 1:
                    send({'method': 'initialized', 'params': {}})
                    send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
                else:
                    return normalize(response['result'], source='account/rateLimits/read')
        raise SafetyError('Native quota RPC timed out or disconnected')
    finally:
        sel.close()
        proc.stdin.close()
        # Own process group only; never stop the user's existing app-server.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)
        proc.stdout.close()

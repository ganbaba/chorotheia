import argparse
import json
import os
from pathlib import Path
import sys
from . import __version__
from .guard import Tree, SafetyError, lock
from . import core
from .memory import clean, restore, git_state


def parser():
    p = argparse.ArgumentParser(description="Chorotheia portable local agent memory (no source recovery)")
    p.add_argument("--version", action="version", version=__version__)
    subs = p.add_subparsers(dest="command", required=True)
    for cmd in ["init", "retrofit", "checkpoint", "restore", "handoff", "recall", "compact", "status", "audit", "repair", "doctor", "upgrade", "uninstall", "hook", "monitor"]:
        s = subs.add_parser(cmd)
        s.add_argument("--project", default=".")
        s.add_argument("--home", default=os.environ.get("CHOROTHEIA_HOME", str(Path.home() / ".chorotheia")))
        s.add_argument("--dry-run", action="store_true")
        if cmd in ["init", "retrofit"]:
            s.add_argument("--mode", choices=["auto", "new", "retrofit", "repair", "audit"], default="auto")
        if cmd in ["checkpoint", "handoff"]:
            s.add_argument("--summary", required=True)
            s.add_argument("--next", action="append", default=[], dest="next_steps")
            s.add_argument("--decision", action="append", default=[], dest="decisions")
            s.add_argument("--error", action="append", default=[], dest="errors")
            s.add_argument("--test", action="append", default=[], dest="tests")
            s.add_argument("--goal", help="Explicit current objective; inherited when omitted")
            s.add_argument("--done", action="append", default=[], dest="completed")
            s.add_argument("--phase", help="Name of the current stage (starts open unless completed)")
            s.add_argument("--phase-state", choices=["open", "complete"])
            s.add_argument("--review-discussion", action="append", default=[], help="Exact current monitor review token; repeatable")
        if cmd in ["checkpoint", "hook"]:
            s.add_argument("--agent", default="manual", choices=["manual", "codex", "antigravity", "copilot"])
        if cmd == "handoff":
            s.add_argument("--to", default="unspecified", dest="target")
            s.add_argument("--task-id")
            s.add_argument("--run-id")
            s.add_argument("--base-revision", type=int)
            s.add_argument("--outcome", choices=["continue", "done", "blocked"], default="continue")
        if cmd == "restore":
            s.add_argument("--budget", type=int, default=2400)
            s.add_argument("--text", action="store_true")
        if cmd == "recall":
            s.add_argument("query")
            s.add_argument("--limit", type=int, default=10)
        if cmd == "compact":
            s.add_argument("--keep", type=int, default=5)
        if cmd == "repair":
            s.add_argument("--adopt", action="store_true")
            s.add_argument("--rollback")
        if cmd == "hook":
            s.add_argument("--event", required=True)
        if cmd == 'monitor':
            mode = s.add_mutually_exclusive_group()
            mode.add_argument('--enable', action='store_true', dest='monitor_enabled', default=None)
            mode.add_argument('--disable', action='store_false', dest='monitor_enabled')
            s.add_argument('--quota-warning', type=float)
            s.add_argument('--quota-critical', type=float)
            s.add_argument('--session-id')
            s.add_argument('--transcript')
            s.add_argument('--include-existing', action='store_true', help='First binding only; bounded history scan, no automatic acknowledgement')
            s.add_argument('--details', action='store_true')
            s.add_argument('--refresh-quota', action='store_true')
            s.add_argument('--codex-binary', help='Absolute native codex executable for explicit read-only quota RPC')
        if cmd in ["uninstall", "upgrade"]:
            s.add_argument("--global-install", action="store_true")
        if cmd == "upgrade":
            s.add_argument("--source", help="Local v1.0.0 maintenance source directory; no network download")
    return p


def dispatch(args):
    cmd = args.command
    if cmd == "doctor":
        from .doctor import inspect
        return inspect()
    if cmd in ["uninstall", "upgrade"] and args.global_install:
        from .installation import uninstall_global, upgrade_global
        return uninstall_global(args.home, args.dry_run) if cmd == "uninstall" else upgrade_global(args.home, args.dry_run, args.source)
    if cmd == "hook":
        from .adapters import run_hook
        raw = sys.stdin.buffer.read(128001)
        if len(raw) > 128000:
            # Observation must not turn a large unrelated tool call into a
            # blocking failure. Drain without retaining the tool payload;
            # subsequent bounded events can catch up from the transcript.
            while sys.stdin.buffer.read(65536):
                pass
            print('Chorotheia observation skipped: oversized hook event; checkpoint at the next supported event.', file=sys.stderr)
            return {}
        payload = json.loads(raw or b"{}")
        if not isinstance(payload, dict):
            raise SafetyError("Hook payload must be an object")
        with Tree(args.home, create=True, private=True) as home:
            return run_hook(home, args.agent, args.event, payload)
    read_only = cmd in {"restore", "recall", "status", "audit"} or args.dry_run or getattr(args, "mode", None) == "audit"
    if cmd == 'monitor' and not (args.transcript or args.refresh_quota or args.monitor_enabled is not None or
                                  args.quota_warning is not None or args.quota_critical is not None):
        read_only = True
    home = None
    try:
        if not read_only or Path(args.home).exists():
            home = Tree(args.home, create=not read_only, private=True)
        with Tree(args.project) as tree:
            def action():
                if cmd in {"init", "retrofit"}:
                    if args.mode == "audit":
                        return core.audit(tree, home)
                    if args.mode == "repair":
                        return core.repair(tree, home, dry_run=args.dry_run)
                    from .adapters import CAPABILITIES
                    return core.initialize(tree, home, "retrofit" if cmd == "retrofit" else args.mode, args.dry_run, CAPABILITIES)
                if cmd == "checkpoint":
                    return core.checkpoint(tree, home, args.summary, args.next_steps, args.decisions, args.errors, args.tests,
                                           args.agent, args.dry_run, goal=args.goal, completed=args.completed,
                                           phase=args.phase, phase_state=args.phase_state, review_discussion=args.review_discussion)
                if cmd == "restore":
                    m, _, _ = core.require(tree)
                    from . import monitor
                    result = restore(tree, m, args.budget, monitor.public(monitor.load(home, m)))
                    result["current_git"] = git_state(tree.root)
                    if home:
                        result["pending_transactions"] = [j["id"] for j in core.pending(home, tree.root)]
                    return result["text"] if args.text else result
                if cmd == "handoff":
                    protocol = None
                    if args.task_id is not None or args.run_id is not None or args.base_revision is not None:
                        protocol = {"task_id": args.task_id, "run_id": args.run_id, "base_revision": args.base_revision, "outcome": args.outcome}
                        if args.base_revision is None:
                            raise SafetyError("Controller base revision required")
                    return core.handoff(tree, home, args.target, args.summary, args.dry_run, protocol,
                                        next_steps=args.next_steps, decisions=args.decisions, errors=args.errors,
                                        tests=args.tests, goal=args.goal, completed=args.completed,
                                        phase=args.phase, phase_state=args.phase_state, review_discussion=args.review_discussion)
                if cmd == 'monitor':
                    from . import monitor
                    m, _, _ = core.require(tree, home, writable=not read_only)
                    if args.dry_run:
                        monitor.configure(home, m, tree.root, args.monitor_enabled, args.quota_warning,
                                          args.quota_critical, dry_run=True)
                        return {'dry_run': True, 'would_configure': args.monitor_enabled is not None or args.quota_warning is not None or args.quota_critical is not None,
                                'would_scan': bool(args.transcript), 'would_refresh_quota': args.refresh_quota}
                    if args.monitor_enabled is not None or args.quota_warning is not None or args.quota_critical is not None:
                        monitor.configure(home, m, tree.root, args.monitor_enabled, args.quota_warning, args.quota_critical)
                    if args.transcript:
                        monitor.scan(home, m, tree.root, args.session_id, args.transcript, args.include_existing)
                    if args.refresh_quota:
                        if not args.codex_binary:
                            raise SafetyError('--codex-binary required for explicit native quota refresh')
                        monitor.refresh(home, m, tree.root, args.codex_binary)
                    return monitor.public(monitor.load(home, m), args.details)
                if cmd == "recall":
                    if not 1 <= args.limit <= 100:
                        raise SafetyError("limit must be 1..100")
                    return core.recall(tree, args.query, args.limit)
                if cmd == "compact":
                    return core.compact(tree, home, args.keep, args.dry_run)
                if cmd in {"status", "audit"}:
                    report = core.audit(tree, home)
                    if cmd == "status":
                        m, _, _ = core.require(tree)
                        report.update(paths=m["paths"], git=git_state(tree.root), conflicts_preserved=m.get("conflicts_preserved", []))
                        from . import monitor
                        report['monitor'] = monitor.public(monitor.load(home, m))
                        report['freshness'] = core.assess(tree, m, monitoring=report['monitor'])
                    return report
                if cmd == "repair":
                    return core.repair(tree, home, args.dry_run, args.adopt, args.rollback)
                if cmd == "upgrade":
                    return core.upgrade(tree, home, args.dry_run)
                if cmd == "uninstall":
                    return core.uninstall(tree, home, args.dry_run)
            if read_only:
                return action()
            with lock(home, tree.root):
                return action()
    finally:
        if home:
            home.close()


def main():
    args = parser().parse_args()
    try:
        result = dispatch(args)
        print(result if isinstance(result, str) else json.dumps(clean(result), ensure_ascii=False, indent=2))
        return 1 if isinstance(result, dict) and result.get("ok") is False else 0
    except (SafetyError, OSError, ValueError, KeyError, TypeError) as e:
        # Hook failures are visible, never fake success or block an agent by force.
        print(json.dumps({"error": str(e), "type": type(e).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

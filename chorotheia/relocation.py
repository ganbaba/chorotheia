"""Audited rebinding of a locally renamed project; never import ownership."""
import json
import os
from .guard import SafetyError, Transaction, absolute, digest, encode, lock


def rebind(tree, home, previous_root, dry_run=False):
    from .core import require, receipt_path, check_pending, audit
    old = absolute(previous_root)
    if old == tree.root:
        raise SafetyError('Previous and current project roots must differ')
    if os.path.lexists(old):
        raise SafetyError('Previous root still exists; copied/imported projects are not eligible')
    m, rel, mh = require(tree)
    source = receipt_path(old)
    target = receipt_path(tree.root)
    if home is None or not home.exists(source):
        raise SafetyError('No real private receipt at previous root; import is not supported')
    # Destination lock is held by the CLI on mutation; source lock prevents two
    # moves claiming the same original binding. Preview takes no write locks.
    import contextlib
    with contextlib.nullcontext() if dry_run else lock(home, old):
        check_pending(home, old)
        check_pending(home, tree.root)
        raw = home.read(source)
        owner = json.loads(raw)
        if owner.get('state') == 'relocated' and owner.get('relocated_to') == str(tree.root):
            from .core import receipt
            receipt(tree, home, m, mh)
            prior = owner.get('transaction', '')
            if not isinstance(prior, str) or len(prior) != 32 or any(c not in '0123456789abcdef' for c in prior):
                raise SafetyError('Invalid relocation provenance')
            proof = json.loads(home.read('backups/transactions/' + prior + '.json'))
            if (proof.get('root') != str(tree.root) or proof.get('phase') != 'committed' or
                not any(e.get('private') and e.get('path') == source and e.get('applied') and
                        e.get('after') == digest(raw) for e in proof.get('entries', []))):
                raise SafetyError('Relocation marker lacks committed local evidence')
            if not audit(tree)['ok']:
                raise SafetyError('Edited memory remains unadopted')
            return {'changed': False, 'dry_run': dry_run, 'ownership': 'verified'}
        if owner.get('project_id') != m['project_id'] or owner.get('manifest_sha256') != mh:
            raise SafetyError('Existing private receipt does not match the unchanged project manifest')
        transaction = owner.get('transaction', '')
        if not isinstance(transaction, str) or len(transaction) != 32 or any(c not in '0123456789abcdef' for c in transaction):
            raise SafetyError('Private receipt lacks verifiable local transaction provenance')
        journal = json.loads(home.read('backups/transactions/' + transaction + '.json'))
        if journal.get('id') != transaction or journal.get('root') != str(old) or journal.get('phase') != 'committed':
            raise SafetyError('Previous local transaction is not committed at the recorded root')
        if not any(e.get('private') and not e.get('external_root') and e.get('path') == source and
                   e.get('applied') and e.get('after') == digest(raw) for e in journal.get('entries', [])):
            raise SafetyError('Receipt bytes do not match committed local transaction evidence')
        report = audit(tree)
        if not report['ok']:
            raise SafetyError('Memory missing, modified or unsafe; relocation cannot adopt edits')
        if home.exists(target):
            destination = json.loads(home.read(target))
            if destination.get('project_id') == m['project_id'] and destination.get('manifest_sha256') == mh:
                return {'changed': False, 'dry_run': dry_run, 'ownership': 'verified'}
            raise SafetyError('Destination receipt occupied; preserving it')
        result = {'dry_run': dry_run, 'previous_root': str(old), 'project': str(tree.root),
                  'project_id': m['project_id'], 'manifest_sha256': mh,
                  'verified_memory_files': len(m['managed']), 'source_transaction': transaction,
                  'project_files_changed': False}
        if dry_run:
            return dict(result, would_rebind=True)
        # The real source receipt is retained verbatim in the transaction preimage.
        # Its old binding becomes a tombstone so old clients also reject it.
        with Transaction(tree, home, 'project-relocation') as tx:
            if os.path.lexists(old) or tree.hash(rel) != mh:
                raise SafetyError('Project changed during relocation preview')
            tx.put(target, encode({'project_id': m['project_id'], 'manifest_sha256': mh, 'transaction': tx.id,
                                   'relocated_from': str(old), 'source_transaction': transaction}), private=True)
            tx.put(source, encode({'project_id': m['project_id'], 'manifest_sha256': None,
                                   'state': 'relocated', 'relocated_to': str(tree.root), 'transaction': tx.id}),
                   digest(raw), private=True)
            if tree.hash(rel) != mh or not audit(tree)['ok']:
                raise SafetyError('Memory changed during relocation; bindings rolled back')
        return dict(result, changed=True, backup_transaction=tx.id, ownership='verified')

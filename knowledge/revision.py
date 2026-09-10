import hashlib
import json
import os
import threading

from config import store
from knowledge import architecture
from model_client import client
from snapshot.scanner import take_snapshot


_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def project_lock(project):
    project = os.path.realpath(project)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(project, threading.Lock())


def event_version(event):
    body = json.dumps(store.event_evidence(event), sort_keys=True, ensure_ascii=False)
    return hashlib.blake2b(body.encode(), digest_size=16).hexdigest()


def completed_events(project):
    return [event for event in store.read_events(project, limit=None)
            if event.get('source') != 'claude_hook' and event.get('is_completed') is not False]


def pending_events(arch, events):
    incorporated = arch.get('incorporated_events', {})
    return [event for event in events
            if incorporated.get(event['event_id']) != event_version(event)]


def status(project):
    arch = architecture.load_architecture(project)
    events = completed_events(project)
    return {'busy': project_lock(project).locked(),
            'pending': len(pending_events(arch, events)) if arch else 0}


def revise(project, model_cfg, lang='zh', full=False):
    lock = project_lock(project)
    if not lock.acquire(blocking=False):
        return 409, {'ok': False, 'error': 'Architecture update already running', 'busy': True}
    try:
        events = completed_events(project)
        arch = architecture.load_architecture(project)
        if not full and not arch:
            return 400, {'ok': False, 'error': 'Generate the architecture first'}
        pending = events if full else pending_events(arch, events)
        if not full and not pending:
            return 200, {'ok': True, 'unchanged': True, 'pending': 0}
        if full:
            from graph import builder
            snapshot = take_snapshot(project)
            struct = builder.structure(project, snapshot=snapshot, events=events)
            previous = arch
            arch = client.abstract_architecture_full(
                project, model_cfg, struct, builder.repo_info(project, snapshot=snapshot), lang=lang)
            if arch is None:
                return 502, {'ok': False, 'error': 'Architecture synthesis failed'}
            architecture.preserve_ids(previous, arch)
            architecture.normalize_architecture(arch)
            arch['base_revision'] = len(events)
            arch['incorporated_events'] = {}
        else:
            pending = pending[:20]
            changed = [event for event in pending if event.get('files')]
            if changed:
                files = {f['path']: f for event in changed for f in event['files']}
                meanings = [str((event.get('dialogue') or {}).get('technical_meaning')
                                or event.get('result_text') or event.get('request_text') or '')[:600]
                            for event in changed]
                target = {'files': list(files.values()),
                          'dialogue': {'technical_meaning': '\n'.join(meanings)}}
                patch = client.update_architecture_patch(arch, target, model_cfg, lang=lang, project=project)
                if patch is None:
                    return 502, {'ok': False, 'error': 'Architecture revision failed'}
                architecture.apply_update(arch, patch, set(take_snapshot(project)['files']), len(events))
        incorporated = arch.setdefault('incorporated_events', {})
        incorporated.update({event['event_id']: event_version(event) for event in pending})
        arch['analysis_revision'] = sum(incorporated.get(e['event_id']) == event_version(e) for e in events)
        architecture.save_architecture(project, arch)
        from graph import builder
        builder.MAP_CACHE.clear()
        return 200, {'ok': True, 'components': len(arch.get('components', [])),
                     'overview': arch.get('overview', {}), 'analysis_revision': arch['analysis_revision'],
                     'pending': len(pending_events(arch, completed_events(project)))}
    finally:
        lock.release()

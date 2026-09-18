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
    """Architecture revision entry point. Execution lives in the LangGraph
    state graph (agent/graphs/architecture.py); this wrapper keeps the
    historical (code, result) contract for server.py."""
    from agent.graphs.architecture import revise_graph
    return revise_graph(project, model_cfg, lang=lang, full=full)

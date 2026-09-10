"""Local config + event store. Both live under the data dir, never in a
watched project or an agent home directory.
"""

import fcntl
import json
import os
import time


def data_dir():
    return os.environ.get("VIBE_LEARNING_DATA",
                           os.path.expanduser("~/.vibe-learning"))


def _path(name):
    return os.path.join(data_dir(), name)


def ensure_dirs():
    os.makedirs(data_dir(), exist_ok=True)


def default_config():
    return {
        "projects": [],
        "ignored_projects": [],
        "ignored_sessions": [],
        "models": [],
        "active_model_id": "",
        "model": None,
        "poll_interval": 20,
        "port": 8765,
    }


def get_active_model(config):
    """Return the active model dictionary with full credentials."""
    models = config.get("models") or []
    active_id = config.get("active_model_id")
    if models:
        for m in models:
            if m.get("id") == active_id:
                return m
        return models[0]
    return config.get("model")


def upsert_model(config, model_dict):
    """Add or update a provider/model preset."""
    models = config.get("models") or []
    mid = model_dict.get("id") or ("model_" + str(int(time.time())))
    model_dict["id"] = mid

    found = False
    new_models = []
    for m in models:
        if m.get("id") == mid:
            # Preserve existing key if placeholder *** passed
            if model_dict.get("api_key") in (None, "", "***"):
                model_dict["api_key"] = m.get("api_key", "")
            new_models.append(model_dict)
            found = True
        else:
            new_models.append(m)
    if not found:
        new_models.append(model_dict)

    config["models"] = new_models
    if not config.get("active_model_id"):
        config["active_model_id"] = mid
    save_config(config)
    return model_dict


def delete_model(config, model_id):
    models = [m for m in (config.get("models") or []) if m.get("id") != model_id]
    config["models"] = models
    if config.get("active_model_id") == model_id:
        config["active_model_id"] = models[0]["id"] if models else ""
    save_config(config)
    return config


def set_active_model(config, model_id):
    config["active_model_id"] = model_id
    save_config(config)
    return config


def load_config():
    ensure_dirs()
    path = _path("config.json")
    config = default_config()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)
    except (OSError, ValueError):
        pass

    # Seamless migration: if legacy single model exists, ensure it is in models list
    if config.get("model") and isinstance(config["model"], dict):
        legacy = config["model"]
        if not config.get("models"):
            config["models"] = [{
                "id": "legacy_custom",
                "name": legacy.get("model") or "自定义模型",
                "base_url": legacy.get("base_url", ""),
                "api_key": legacy.get("api_key", ""),
                "model": legacy.get("model", "")
            }]
            config["active_model_id"] = "legacy_custom"

    return config


def save_config(config):
    ensure_dirs()
    path = _path("config.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return config


def _slug(project):
    import hashlib
    digest = hashlib.blake2b(os.path.abspath(project).encode("utf-8"),
                             digest_size=8).hexdigest()
    return digest


def events_path(project):
    ensure_dirs()
    return _path("events-%s.jsonl" % _slug(project))


def components_path(project):
    ensure_dirs()
    return _path("components-%s.json" % _slug(project))


def knowledge_path(project):
    d = os.path.join(data_dir(), "knowledge")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "arch-%s.json" % _slug(project))


def memory_path(project):
    d = os.path.join(data_dir(), "memory")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "user-%s.json" % _slug(project))


def load_user_memory(project):
    try:
        with open(memory_path(project), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def save_user_memory(project, state):
    ensure_dirs()
    path = memory_path(project)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return state


def load_architecture(project):
    try:
        with open(knowledge_path(project), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and str(data.get("schema_version", "")).startswith("architecture."):
            return data
    except (OSError, ValueError):
        pass
    return None


def save_architecture(project, arch):
    ensure_dirs()
    arch = dict(arch)
    arch["updated_at"] = now_iso()
    path = knowledge_path(project)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(path),
                                     prefix=os.path.basename(path) + '.', delete=False) as handle:
        tmp = handle.name
        try:
            json.dump(arch, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return arch


def load_components(project):
    path = components_path(project)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def save_components(project, data):
    ensure_dirs()
    path = components_path(project)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return data


def offsets_path():
    ensure_dirs()
    return _path("offsets.json")


def load_offsets():
    try:
        with open(offsets_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_offsets(offsets):
    with open(offsets_path(), "w", encoding="utf-8") as handle:
        json.dump(offsets, handle, ensure_ascii=False)


def known_event_ids(project):
    ids = set()
    try:
        with open(events_path(project), "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    ids.add(json.loads(line).get("event_id"))
                except ValueError:
                    continue
    except OSError:
        pass
    return ids


def session_history(project, session_id, exclude="", limit=8):
    """Past events of one session, oldest first, for the dialogue pass."""
    if not project or not session_id:
        return []
    out = []
    for event in read_events(project, limit=500):
        if event.get("session_id") != session_id:
            continue
        if event.get("event_id") == exclude:
            continue
        out.append(event)
    return out[-limit:]


def event_evidence(event):
    return {key: event.get(key) for key in (
        'request_text', 'result_text', 'files', 'status', 'is_completed', 'cwd')}


def same_event(old, new):
    if old.get('event_id') == new.get('event_id'):
        return True
    if not new.get('session_id') or old.get('session_id') != new['session_id'] or old.get('agent_id') != new.get('agent_id'):
        return False
    if new.get('turn_id') and old.get('turn_id') == new['turn_id']:
        return old.get('source') == new.get('source')
    return (old.get('agent_id') == 'codex' and 'is_completed' not in old
            and bool(new.get('occurred_at')) and old.get('occurred_at') == new['occurred_at']
            and old.get('request_text') == new.get('request_text'))


def event_needs_update(project, event):
    """Check for changed evidence, including completion and late results."""
    path = events_path(project)
    if not os.path.exists(path):
        return True
    target_ev_id = event.get("event_id")
    target_turn_id = event.get("turn_id")
    target_session_id = event.get("session_id")
    try:
        with open(path, "r", encoding="utf-8") as reader:
            for line in reader:
                try:
                    old_ev = json.loads(line)
                except ValueError:
                    continue
                old_ev_id = old_ev.get("event_id")
                old_turn_id = old_ev.get("turn_id")
                old_session_id = old_ev.get("session_id")
                is_match = same_event(old_ev, event)
                if is_match:
                    return event_evidence(old_ev) != event_evidence(event)
    except OSError:
        return True
    return True


def append_event(project, event):
    """Append or atomically update with an exclusive file lock.
    Returns True when newly stored or updated.
    """
    ensure_dirs()
    path = events_path(project)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            lines = handle.readlines()
            new_lines = []
            replaced = False
            target_ev_id = event.get("event_id")
            target_turn_id = event.get("turn_id")
            target_session_id = event.get("session_id")

            for line in lines:
                try:
                    old_ev = json.loads(line)
                except ValueError:
                    continue
                old_ev_id = old_ev.get("event_id")
                old_turn_id = old_ev.get("turn_id")
                old_session_id = old_ev.get("session_id")

                is_match = same_event(old_ev, event)
                if is_match:
                    if old_ev_id:
                        event["event_id"] = old_ev_id
                    if old_ev == event:
                        return False
                    new_lines.append(json.dumps(event, ensure_ascii=False) + "\n")
                    replaced = True
                else:
                    new_lines.append(line)

            if replaced:
                handle.seek(0)
                handle.truncate(0)
                handle.writelines(new_lines)
                handle.flush()
                return True
            else:
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                handle.flush()
                return True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_events(project, limit=500, include_ignored=False):
    events = []
    ignored = set()
    if not include_ignored:
        try:
            config = load_config()
            ignored = set(config.get("ignored_sessions") or [])
        except Exception:
            pass
    try:
        with open(events_path(project), "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    ev = json.loads(line)
                    if not include_ignored and ev.get("session_id") in ignored:
                        continue
                    events.append(ev)
                except ValueError:
                    continue
    except OSError:
        pass
    return events if limit is None else events[-limit:]


def ignore_session(session_id):
    if not session_id:
        return []
    config = load_config()
    ignored = list(config.get("ignored_sessions") or [])
    if session_id not in ignored:
        ignored.append(session_id)
        config["ignored_sessions"] = ignored
        save_config(config)
    return ignored


def unignore_session(session_id):
    if not session_id:
        return []
    config = load_config()
    ignored = list(config.get("ignored_sessions") or [])
    if session_id in ignored:
        ignored.remove(session_id)
        config["ignored_sessions"] = ignored
        save_config(config)
    return ignored


def analysis_scope(project, events, recent=None, historical=False):
    import tempfile
    from datetime import datetime

    def order(event):
        return (datetime.fromisoformat(event['occurred_at'].replace('Z', '+00:00')).timestamp(),
                event['event_id'])

    ensure_dirs()
    path = _path('analysis-scope-' + _slug(project) + '.json')
    with _ANALYSIS_SCOPE_LOCK, open(path + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try:
                with open(path, encoding='utf-8') as handle:
                    state = json.load(handle)
            except FileNotFoundError:
                state = {'initialized': False, 'known': [], 'eligible': []}
            known = set(state['known'])
            eligible = set(state['eligible'])
            completed = [e for e in events if e.get('is_completed') is not False]
            if not state['initialized']:
                eligible.update(e['event_id'] for e in sorted(completed, key=order)[-5:])
                eligible.update(e['event_id'] for e in events
                                if e.get('is_completed') is False or e.get('analysis_status') == 'analysis_done')
                state['initialized'] = True
            elif not historical:
                eligible.update(e['event_id'] for e in events if e['event_id'] not in known)
            if recent is not None:
                eligible.update(e['event_id'] for e in sorted(completed, key=order)[-recent:])
            known.update(e['event_id'] for e in events)
            updated = {**state, 'known': sorted(known), 'eligible': sorted(eligible)}
            if updated != state or not os.path.exists(path):
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=data_dir(), delete=False) as handle:
                    json.dump(updated, handle)
                    temporary = handle.name
                os.replace(temporary, path)
            return eligible
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


import threading
_ANALYSIS_SCOPE_LOCK = threading.Lock()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

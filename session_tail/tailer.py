"""Session tailer: poll implemented adapters, attribute rounds to exactly
one registered project, build change events, persist them.

Attribution rule (narrowed to the watched folder): a round belongs to a
project only when its evidence touches that project folder — an absolute
written-file path inside it, or a cwd equal to / under it. The project is
accepted only on a unique match; zero or multiple matches are dropped and
counted so /api/map can expose dropped_packets.
"""

import hashlib
import json
import os
import re
import time

from config.store import (append_event, event_needs_update, known_event_ids,
                          load_offsets, save_offsets)
from snapshot.languages import language_for, technologies_for
from snapshot.redact import evidence_summary, redact, truncate

# request/result 全文留存(脱敏后),供对话累积分析读历史;展示层只取首屏.
REQUEST_STORE_LIMIT = 12000
RESULT_STORE_LIMIT = 20000


def _norm(path):
    return os.path.abspath(os.path.expanduser(path))


def _under(path, project):
    path, project = _norm(path), _norm(project)
    return path == project or path.startswith(project + os.sep)


SESSION_AFFINITY = {}


def _init_affinity(projects):
    global SESSION_AFFINITY
    from config.store import read_events
    for p in projects:
        for ev in read_events(p, limit=300):
            sid = ev.get("session_id")
            if sid and sid not in SESSION_AFFINITY:
                SESSION_AFFINITY[sid] = p


def attribute(cwd, projects, files=(), session_id=""):
    """Return the unique project the round touches, else None.

    Cwd match wins when it is unique; otherwise absolute written-file paths
    vote and only a unanimous single-project vote is accepted.
    If round has no direct file/cwd hits (e.g. conversational turns, read-only),
    inherit from session affinity so ongoing conversations are not dropped.
    """
    projects = [_norm(p) for p in projects]
    votes = set()
    for path in files:
        if isinstance(path, str) and path:
            abs_path = path if os.path.isabs(path) else (
                os.path.normpath(os.path.join(cwd, path)) if cwd else "")
            if abs_path:
                matches = [project for project in projects if _under(abs_path, project)]
                if matches:
                    votes.add(max(matches, key=len))
    if votes:
        if len(votes) > 1:
            return None
        res = next(iter(votes))
        if session_id:
            SESSION_AFFINITY[session_id] = res
        return res

    hits = {p for p in projects if _under(cwd, p)} if cwd else set()
    if len(hits) == 1:
        res = next(iter(hits))
        if session_id:
            SESSION_AFFINITY[session_id] = res
        return res

    # Fallback to session affinity for pure dialogue or read-only turns
    if session_id and session_id in SESSION_AFFINITY:
        aff = SESSION_AFFINITY[session_id]
        if aff in projects:
            return aff

    return None


def _rel(path, project):
    if os.path.isabs(path):
        if path == project or path.startswith(project + os.sep):
            return os.path.relpath(path, project)
        return path
    return path


def _extract_meta(text):
    if not text or "META:" not in text:
        return {}
    res = {}
    try:
        m = re.search(r"META:\s*(\{.*?\})", text, re.DOTALL)
        if m:
            res = json.loads(m.group(1))
    except Exception:
        pass
    if not res.get("cwd"):
        m_cwd = re.search(r'"cwd"\s*:\s*"([^"]+)"', text)
        if m_cwd:
            res["cwd"] = m_cwd.group(1)
    if not res.get("timestamp"):
        m_time = re.search(r'"timestamp"\s*:\s*"([^"]+)"', text)
        if m_time:
            res["timestamp"] = m_time.group(1)
    return res


def _clean_req_text(text):
    if not text:
        return ""
    s = str(text).strip()
    # Strip leading request: tag
    s = re.sub(r"(?i)^request\s*:\s*", "", s).strip()
    # Split off leaked result or META inside request text
    for marker in ("\nresult: META:", "\nresult:", "\nResult:"):
        if marker in s:
            s = s.split(marker)[0].strip()
    s = re.sub(r"META:\s*\{.*?\}", "", s, flags=re.DOTALL).strip()
    return s


def build_event(adapter, raw, project):
    files = []
    for path, status in (raw.get("files") or {}).items():
        full_path = path if os.path.isabs(path) else os.path.join(raw.get('cwd') or project, path)
        if not _under(full_path, project):
            continue
        rel = _rel(path, project)
        files.append({
            "path": rel,
            "status": status,
            "additions": 0,
            "deletions": 0,
            "languages": [language_for(path)],
            "technologies": technologies_for(path),
        })
    seed = "%s|%s|%s" % (adapter.agent_id, raw.get("session_id"), raw.get("turn_id"))
    event_id = "evt_" + hashlib.blake2b(seed.encode("utf-8"),
                                        digest_size=8).hexdigest()

    meta_obj = _extract_meta(raw.get("result", "")) or _extract_meta(raw.get("request", ""))
    occurred = raw.get("occurred_at") or ""
    if not occurred and meta_obj.get("timestamp"):
        occurred = str(meta_obj.get("timestamp"))
    if not occurred:
        turn_id = str(raw.get("turn_id") or "")
        if turn_id.startswith("turn-") and turn_id[5:].isdigit():
            try:
                t_val = int(turn_id[5:])
                sec = t_val / 1000.0 if t_val > 1e11 else float(t_val)
                occurred = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sec))
            except Exception:
                pass
    if not occurred:
        from config.store import now_iso
        occurred = now_iso()

    detected_cwd = raw.get("cwd") or meta_obj.get("cwd") or project or ""
    cleaned_req = _clean_req_text(raw.get("request") or "")

    return {
        "event_id": event_id,
        "occurred_at": occurred,
        "cwd": detected_cwd,
        "agent_id": adapter.agent_id,
        "agent_label": adapter.agent_label,
        "session_id": raw.get("session_id") or "",
        "turn_id": raw.get("turn_id") or "",
        "status": (raw.get("status") if raw.get("status") == "error" else "completed") if raw.get("is_completed") else "running",
        "is_completed": bool(raw.get("is_completed")),
        "analysis_status": "evidence_only" if raw.get("is_completed") else "collecting",
        "_project": project,
        "evidence_summary": evidence_summary(raw.get("request"), raw.get("result")),
        "request_text": truncate(redact(cleaned_req), REQUEST_STORE_LIMIT),
        "result_text": truncate(redact((raw.get("result") or "").strip()),
                                RESULT_STORE_LIMIT),
        "files": files,
        "source": "session_tail",
    }


import threading

_INGEST_LOCK = threading.Lock()


def poll_once(registry, projects, analyze=None):
    """Poll every implemented adapter once. Returns (new_events, dropped)."""
    with _INGEST_LOCK:
        return _poll(registry, projects, analyze)


def backfill(registry, projects, analyze=None, limit_sessions=30):
    with _INGEST_LOCK:
        return _backfill(registry, projects, analyze, limit_sessions)


def _backfill(registry, projects, analyze=None, limit_sessions=30):
    """One-shot historical ingest: all sessions, oldest first, bounded.

    Uses discover_all_sessions when available, else discover_sessions.
    Offsets are left untouched so the realtime poll keeps its own cursor;
    event_id dedup keeps this idempotent.
    """
    ordered = []
    for name, entry in registry.items():
        if not entry.get("implemented"):
            continue
        adapter = entry["adapter"]
        discover = getattr(adapter, "discover_all_sessions",
                           adapter.discover_sessions)
        try:
            sessions = discover()
        except Exception:
            continue
        try:
            sessions = sorted(sessions, key=lambda p: os.path.getmtime(p))
        except OSError:
            pass
        for session in sessions[-limit_sessions:]:
            ordered.append((name, adapter, session))
    new_events, dropped = [], 0
    _init_affinity(projects)
    known = {p: known_event_ids(p) for p in projects}
    for name, adapter, session in ordered:
        try:
            rounds = adapter.read_session(session)
        except Exception:
            continue
        for raw in rounds:
            project = attribute(raw.get("cwd") or "", projects,
                                files=list((raw.get("files") or {}).keys()),
                                session_id=raw.get("session_id") or "")
            if project is None:
                dropped += 1
                continue
            event = build_event(adapter, raw, project)
            if not event_needs_update(project, event):
                continue
            if analyze is not None and event['is_completed']:
                try:
                    analyze(event)
                except Exception:
                    pass
            if append_event(project, event):
                known.setdefault(project, set()).add(event["event_id"])
                new_events.append((project, event))
    return new_events, dropped


def _poll(registry, projects, analyze=None):
    offsets = load_offsets()
    new_events, dropped = [], 0
    _init_affinity(projects)
    known = {p: known_event_ids(p) for p in projects}
    for name, entry in registry.items():
        if not entry.get("implemented"):
            continue
        adapter = entry["adapter"]
        for session in adapter.discover_sessions():
            key = "%s:%s" % (name, session)
            seen_offset = offsets.get(key, 0)
            try:
                rounds = adapter.read_session(session)
            except Exception:
                continue
            for raw in rounds:
                project = attribute(raw.get("cwd") or "", projects,
                                    files=list((raw.get("files") or {}).keys()),
                                    session_id=raw.get("session_id") or "")
                if project is None:
                    dropped += 1
                    continue
                event = build_event(adapter, raw, project)
                if not event_needs_update(project, event):
                    continue
                if analyze is not None and event['is_completed']:
                    try:
                        analyze(event)
                    except Exception:
                        pass
                if append_event(project, event):
                    known.setdefault(project, set()).add(event["event_id"])
                    new_events.append((project, event))
            if rounds:
                offsets[key] = max([r.get("offset") or 0 for r in rounds] + [seen_offset])
    save_offsets(offsets)
    return new_events, dropped

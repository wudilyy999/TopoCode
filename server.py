"""Single-process server: stdlib HTTP + background poll thread + SSE.

Endpoints:
  GET  /api/map?project=<abs path>[&top=N]
  GET  /api/events/stream?project=<abs path>   (SSE)
  GET  /api/config
  POST /api/config                             (projects list + model config)
  POST /api/components                         (LLM architecture synthesis → knowledge store)
  POST /api/components/update                  (incremental architecture revision)
  POST /api/file_deep_analysis                 (on-demand agent deep-dive of one file)
  POST /hooks/claude                           (observe-only hook receiver)
  GET  /                                       (web UI)
"""

import hashlib
import json
import os
import queue
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import platforms.claude  # noqa: F401
import platforms.codex  # noqa: F401
import platforms.kimi  # noqa: F401
import platforms.stubs  # noqa: F401
from config import store as store_mod
from discovery.engine import ProjectDiscoveryEngine
from graph import builder as graph_builder
from knowledge import architecture as arch_store
from knowledge import bank as knowledge_bank
from knowledge import rag as rag_mod
from model_client import client as model_client
from platforms.base import REGISTRY
from session_tail import tailer
from snapshot import file_analysis as file_analysis_mod
from snapshot.languages import language_for, technologies_for
from snapshot.redact import redact, truncate
from snapshot.scanner import take_snapshot

STATE = {"dropped": 0, "model": None, "projects": []}
SUBSCRIBERS = []
SUB_LOCK = threading.Lock()
DISCOVERY_ENGINE = ProjectDiscoveryEngine(REGISTRY)
NOTIFIED_PROJECTS = set()
LAST_DISCOVERY_SCAN = 0
ANALYSIS_QUEUE = queue.Queue(maxsize=128)
ARCHITECTURE_QUEUE = queue.Queue(maxsize=32)
WORK_QUEUE_LOCK = threading.Lock()
QUEUED_ANALYSIS = set()
QUEUED_ARCHITECTURE = set()
ANALYZED_ATTEMPTS = set()


def _event_fingerprint(event):
    body = json.dumps({key: event.get(key) for key in (
        'request_text', 'result_text', 'files', 'status', 'is_completed', 'cwd')},
        sort_keys=True, ensure_ascii=False)
    return hashlib.blake2b(body.encode('utf-8'), digest_size=12).hexdigest()


def _model_fingerprint(model_cfg):
    if not model_cfg:
        return ''
    return '%s|%s' % (model_cfg.get('base_url', ''), model_cfg.get('model', ''))


def _broadcast(project, event):
    event['_project'] = project
    with SUB_LOCK:
        for sub in SUBSCRIBERS:
            try:
                sub.put_nowait(event)
            except queue.Full:
                pass


def _analyze(event):
    history = store_mod.session_history(
        event.get('_project') or '', event.get('session_id') or '',
        exclude=event.get('event_id'), limit=5)
    cfg = store_mod.load_config()
    model_client.analyze_dialogue(
        event, history, STATE['model'],
        project_root=event.get('_project') or '', lang=cfg.get('language', 'zh'))
    event.setdefault('analysis_status', 'evidence_only')


def _queue_analysis(project, event):
    if (not model_client.configured(STATE.get('model'))
            or event.get('is_completed') is False
            or event.get('analysis_status') == 'analysis_done'):
        return False
    event_id = event.get('event_id')
    if not event_id:
        return False
    model_key = _model_fingerprint(STATE.get('model'))
    key = (project, event_id, _event_fingerprint(event), model_key)
    with WORK_QUEUE_LOCK:
        if key in QUEUED_ANALYSIS or key in ANALYZED_ATTEMPTS:
            return False
        try:
            ANALYSIS_QUEUE.put_nowait((project, dict(event), key))
        except queue.Full:
            return False
        QUEUED_ANALYSIS.add(key)
    return True


def _queue_architecture(project):
    with WORK_QUEUE_LOCK:
        if project in QUEUED_ARCHITECTURE:
            return False
        try:
            ARCHITECTURE_QUEUE.put_nowait(project)
        except queue.Full:
            return False
        QUEUED_ARCHITECTURE.add(project)
    return True


def _analysis_worker():
    while True:
        project, event, key = ANALYSIS_QUEUE.get()
        try:
            latest = [item for item in store_mod.read_events(project, limit=None)
                      if item.get('event_id') == event.get('event_id')]
            if latest:
                event = latest[-1]
            event['_project'] = project
            _analyze(event)
            if store_mod.append_event(project, event):
                _broadcast(project, event)
            with WORK_QUEUE_LOCK:
                ANALYZED_ATTEMPTS.add(key)
            _queue_architecture(project)
        except Exception:
            pass
        finally:
            with WORK_QUEUE_LOCK:
                QUEUED_ANALYSIS.discard(key)
            ANALYSIS_QUEUE.task_done()


def _architecture_worker():
    from knowledge import revision
    while True:
        project = ARCHITECTURE_QUEUE.get()
        try:
            model_cfg = STATE.get('model')
            if model_client.configured(model_cfg):
                config = store_mod.load_config()
                revision.revise(project, model_cfg, lang=config.get('language', 'zh'))
        except Exception:
            pass
        finally:
            with WORK_QUEUE_LOCK:
                QUEUED_ARCHITECTURE.discard(project)
            ARCHITECTURE_QUEUE.task_done()


ANALYSIS_INGEST_LOCK = threading.RLock()


def _ingest(projects, historical=False, limit_sessions=30, recent=None):
    with ANALYSIS_INGEST_LOCK:
        for project in projects:
            existing = store_mod.read_events(project, limit=None)
            if existing:
                store_mod.analysis_scope(project, existing)
        if historical:
            new_events, dropped = tailer.backfill(REGISTRY, projects, limit_sessions=limit_sessions)
        else:
            new_events, dropped = tailer.poll_once(REGISTRY, projects)
        queued = 0
        for project in projects:
            events = store_mod.read_events(project, limit=None)
            eligible = store_mod.analysis_scope(project, events, recent=recent, historical=historical)
            queued += sum(_queue_analysis(project, event) for event in events if event['event_id'] in eligible)
        for project, event in new_events:
            _broadcast(project, event)
        return new_events, dropped, queued


def _poll_loop():
    global LAST_DISCOVERY_SCAN
    while True:
        try:
            config = store_mod.load_config()
            STATE["model"] = store_mod.get_active_model(config)
            projects = [p for p in config.get("projects", []) if os.path.isdir(p)]
            STATE["projects"] = projects

            # Periodically (every 20s) check for newly active untracked projects and notify user
            now = time.time()
            if now - LAST_DISCOVERY_SCAN > 20:
                LAST_DISCOVERY_SCAN = now
                try:
                    ignored = set(os.path.abspath(p) for p in config.get("ignored_projects", []))
                    discovered = DISCOVERY_ENGINE.scan_discovered_projects(
                        tracked_projects=projects,
                        ignored_projects=list(ignored),
                        max_sessions_per_adapter=20
                    )
                    for item in discovered:
                        p_path = item["path"]
                        if not item["is_tracked"] and not item["is_ignored"] and p_path not in NOTIFIED_PROJECTS:
                            NOTIFIED_PROJECTS.add(p_path)
                            prompt_msg = {
                                "_type": "project_prompt",
                                "type": "project_prompt",
                                "project_path": p_path,
                                "project_name": item["name"],
                                "agent_labels": item.get("agent_labels", []),
                                "last_active": item.get("last_active", "")
                            }
                            with SUB_LOCK:
                                for sub in SUBSCRIBERS:
                                    try:
                                        sub.put_nowait(prompt_msg)
                                    except queue.Full:
                                        pass
                except Exception:
                    pass

            new_events, dropped, queued = _ingest(projects)
            STATE["dropped"] += dropped
            for project in projects:
                if model_client.configured(STATE['model']):
                    from knowledge import revision
                    if revision.status(project)['pending']:
                        _queue_architecture(project)
            interval = config.get("poll_interval", 20)
        except Exception:
            interval = 20
        time.sleep(max(1, interval))


def _looks_like_path(value):
    if not value or len(value) > 512 or "\n" in value:
        return False
    lowered = value.lower()
    if " " in value.strip() and "/" not in value and "\\" not in value:
        return False
    if lowered.startswith(("http://", "https://")):
        return False
    name = value.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "/" in value or "\\" in value or "." in name:
        return True
    return False


def _hook_event(payload):
    event_name = payload.get("hook_event_name", "")
    session_id = payload.get("session_id", "")
    cwd = payload.get("cwd", "")
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}
    tool_text = redact("%s %s" % (payload.get("tool_name") or "",
                                  json.dumps(tool_input, ensure_ascii=False)))
    files = []
    for key in ("file_path", "path", "filename", "file"):
        value = tool_input.get(key)
        if (event_name == 'PostToolUse' and payload.get('tool_name') in ('Write', 'Edit', 'NotebookEdit')
                and isinstance(value, str) and value and _looks_like_path(value)):
            files.append({"path": value, "status": "modified",
                          "additions": 0, "deletions": 0,
                          "languages": [language_for(value)],
                          "technologies": technologies_for(value)})
            break
    return {
        "event_id": "hook_%s_%s" % (session_id[:8], str(time.time_ns())),
        "occurred_at": store_mod.now_iso(),
        "agent_id": "claude-code",
        "agent_label": "Claude Code",
        "session_id": session_id,
        "turn_id": payload.get("prompt_id") or session_id,
        "status": "observed",
        "evidence_summary": truncate("hook %s [%s]: %s" % (event_name, cwd, tool_text), 1000),
        "files": files,
        "source": "claude_hook",
        "hook_event": event_name,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "vibe-learning/1.0"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            here = os.path.dirname(os.path.abspath(__file__))
            try:
                with open(os.path.join(here, "web", "index.html"), "rb") as handle:
                    self._send(200, handle.read(), "text/html")
            except OSError:
                self._send(404, "no ui")
        elif parsed.path == "/api/map":
            project = (params.get("project") or [""])[0]
            if not project or not os.path.isdir(project):
                self._send(400, json.dumps({"error": "unknown project"}))
                return
            try:
                top_n = max(10, min(500, int((params.get("top") or ["60"])[0])))
            except ValueError:
                top_n = 60
            map_data = graph_builder.build_map(project, STATE["dropped"], top_n=top_n)
            config = store_mod.load_config()
            map_data["ignored_sessions"] = config.get("ignored_sessions") or []
            from knowledge import revision
            map_data['architecture_job'] = revision.status(project)
            self._send(200, json.dumps(map_data, ensure_ascii=False))
        elif parsed.path == "/api/events/stream":
            project = (params.get("project") or [""])[0]
            sub = queue.Queue(maxsize=100)
            with SUB_LOCK:
                SUBSCRIBERS.append(sub)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        event = sub.get(timeout=15)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        continue
                    if event.get("_type") == "project_prompt":
                        # Broadcast project tracking prompt to all connected web clients
                        data = ("data: %s\n\n" % json.dumps(event, ensure_ascii=False)).encode()
                        self.wfile.write(data)
                        self.wfile.flush()
                        continue
                    if project and event.get("_project") != project:
                        continue
                    cfg = store_mod.load_config()
                    if event.get("session_id") in (cfg.get("ignored_sessions") or []):
                        continue
                    event = {k: v for k, v in event.items() if not k.startswith("_")}
                    data = ("data: %s\n\n" % json.dumps(event, ensure_ascii=False)).encode()
                    self.wfile.write(data)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with SUB_LOCK:
                    if sub in SUBSCRIBERS:
                        SUBSCRIBERS.remove(sub)
        elif parsed.path == "/api/config":
            config = store_mod.load_config()
            if config.get("model") and config["model"].get("api_key"):
                config = dict(config)
                config["model"] = dict(config["model"])
                config["model"]["api_key"] = "***"
            profiles = []
            for p in config.get("projects", []):
                profiles.append({
                    "path": p,
                    "name": os.path.basename(p),
                    "headline": graph_builder.extract_project_headline(p)
                })
            config["project_profiles"] = profiles
            self._send(200, json.dumps(config, ensure_ascii=False))
        elif parsed.path == '/api/folders':
            path = (params.get('path') or [os.getcwd()])[0]
            path = os.path.realpath(os.path.expanduser(path))
            try:
                offset = max(0, int((params.get('offset') or ['0'])[0]))
                if any(part.startswith('.') for part in path.split(os.sep) if part):
                    raise ValueError('Hidden directories are not browsable')
                with os.scandir(path) as entries:
                    names = sorted(entry.name for entry in entries if entry.is_dir(follow_symlinks=False)
                                   and not entry.name.startswith('.')
                                   and entry.name not in ('node_modules', '__pycache__'))
            except (OSError, ValueError) as exc:
                self._send(400, json.dumps({'ok': False, 'error': str(exc)}))
                return
            self._send(200, json.dumps({'ok': True, 'path': path, 'parent': os.path.dirname(path),
                                       'folders': [{'name': name, 'path': os.path.join(path, name)} for name in names[offset:offset+100]],
                                       'next_offset': offset+100 if offset+100 < len(names) else None}, ensure_ascii=False))
        elif parsed.path == "/api/projects/discovered":
            config = store_mod.load_config()
            tracked = config.get("projects", [])
            ignored = config.get("ignored_projects", [])
            items = DISCOVERY_ENGINE.scan_discovered_projects(
                tracked_projects=tracked,
                ignored_projects=ignored,
                max_sessions_per_adapter=40
            )
            untracked_count = len([x for x in items if not x["is_tracked"] and not x["is_ignored"]])
            self._send(200, json.dumps({
                "ok": True,
                "scope": config.get('discovery_scope') or '',
                "auto_track": bool(config.get("auto_track_discovered")),
                "untracked_count": untracked_count,
                "discovered": items
            }, ensure_ascii=False))
        elif parsed.path == "/api/projects/pending_prompt":
            config = store_mod.load_config()
            tracked = set(os.path.abspath(p) for p in config.get("projects", []))
            ignored = set(os.path.abspath(p) for p in config.get("ignored_projects", []))
            items = DISCOVERY_ENGINE.scan_discovered_projects(
                tracked_projects=list(tracked),
                ignored_projects=list(ignored),
                max_sessions_per_adapter=20
            )
            pending = [x for x in items if not x["is_tracked"] and not x["is_ignored"]]
            self._send(200, json.dumps({
                "ok": True,
                "pending": pending[:3]
            }, ensure_ascii=False))
        elif parsed.path == "/api/file_code":
            from snapshot.source import read_code_block
            project = (params.get('project') or [''])[0]
            tracked = store_mod.load_config().get('projects', [])
            if os.path.realpath(project) not in {os.path.realpath(p) for p in tracked}:
                self._send(403, json.dumps({'error': 'Project is not registered'}))
                return
            try:
                block = read_code_block(project, (params.get('file') or [''])[0],
                                        int((params.get('start') or ['0'])[0]),
                                        int((params.get('end') or ['0'])[0]))
            except (ValueError, OSError) as exc:
                self._send(400, json.dumps({'error': str(exc)}))
                return
            self._send(200, json.dumps({'ok': True, **block}, ensure_ascii=False))
        elif parsed.path == "/api/file_analysis":
            project = (params.get("project") or [""])[0]
            fpath = (params.get("file") or [""])[0]
            if not project or not fpath:
                self._send(400, json.dumps({"error": "missing project or file"}))
                return
            data = file_analysis_mod.analyze_source_file(project, fpath, ui_lang=(params.get('lang') or ['zh'])[0])
            if data is None:
                self._send(404, json.dumps({"error": "file not found or unreadable"}))
                return
            self._send(200, json.dumps({"ok": True, "analysis": data}, ensure_ascii=False))
        elif parsed.path == "/api/knowledge_dict":
            frontend_dict = knowledge_bank.get_frontend_dict()
            self._send(200, json.dumps({"ok": True, "dict": frontend_dict}, ensure_ascii=False))
        elif parsed.path == "/api/knowledge_detail":
            kid = (params.get("id") or [""])[0]
            term = (params.get("term") or [""])[0]
            entry = knowledge_bank.get_knowledge_by_id(kid) if kid else None
            if not entry and term:
                entry = knowledge_bank.find_knowledge_by_term(term)
            if entry:
                self._send(200, json.dumps({"ok": True, "entry": entry}, ensure_ascii=False))
            else:
                self._send(404, json.dumps({"error": "entry not found"}, ensure_ascii=False))
        elif parsed.path == "/api/knowledge":
            query = (params.get("query") or [""])[0]
            hits = rag_mod.retrieve_knowledge(query, top_k=5)
            self._send(200, json.dumps({"ok": True, "query": query, "hits": hits}, ensure_ascii=False))
        elif parsed.path == "/api/sessions/ignored":
            config = store_mod.load_config()
            self._send(200, json.dumps({
                "ok": True,
                "ignored_sessions": config.get("ignored_sessions", [])
            }, ensure_ascii=False))
        elif parsed.path == "/api/models":
            config = store_mod.load_config()
            models = config.get("models") or []
            safe_models = []
            for m in models:
                item = dict(m)
                if item.get("api_key"):
                    item["api_key"] = "***"
                    item["has_key"] = True
                else:
                    item["has_key"] = False
                safe_models.append(item)
            self._send(200, json.dumps({
                "ok": True,
                "active_model_id": config.get("active_model_id") or (models[0]["id"] if models else ""),
                "models": safe_models
            }, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            payload = {}
        if parsed.path == "/api/config":
            config = store_mod.load_config()
            if isinstance(payload.get("projects"), list):
                config["projects"] = [p for p in payload["projects"]
                                      if isinstance(p, str) and os.path.isdir(p)]
            if "model" in payload:
                model = payload["model"]
                if model is None:
                    config["model"] = None
                elif isinstance(model, dict):
                    prev = config.get("model") or {}
                    if model.get("api_key") in (None, "", "***"):
                        model["api_key"] = prev.get("api_key", "")
                    config["model"] = {
                        "base_url": model.get("base_url", ""),
                        "api_key": model.get("api_key", ""),
                        "model": model.get("model", ""),
                    }
            store_mod.save_config(config)
            STATE["model"] = config.get("model")
            STATE["projects"] = config.get("projects", [])
            self._send(200, json.dumps({"ok": True}))
        elif parsed.path == "/api/models/save":
            model_dict = payload.get("model") or {}
            if not model_dict.get("model"):
                self._send(400, json.dumps({"error": "model name required"}))
                return
            config = store_mod.load_config()
            saved = store_mod.upsert_model(config, model_dict)
            STATE["model"] = store_mod.get_active_model(config)
            self._send(200, json.dumps({"ok": True, "model": saved}, ensure_ascii=False))
        elif parsed.path == "/api/models/select":
            mid = payload.get("model_id", "")
            if not mid:
                self._send(400, json.dumps({"error": "model_id required"}))
                return
            config = store_mod.load_config()
            store_mod.set_active_model(config, mid)
            STATE["model"] = store_mod.get_active_model(config)
            self._send(200, json.dumps({"ok": True, "active_model_id": mid,
                                        "active_model": STATE["model"].get("name") if STATE["model"] else ""}, ensure_ascii=False))
        elif parsed.path == "/api/models/delete":
            mid = payload.get("model_id", "")
            if not mid:
                self._send(400, json.dumps({"error": "model_id required"}))
                return
            config = store_mod.load_config()
            store_mod.delete_model(config, mid)
            STATE["model"] = store_mod.get_active_model(config)
            self._send(200, json.dumps({"ok": True, "active_model_id": config.get("active_model_id")}, ensure_ascii=False))
        elif parsed.path == "/api/model/test":
            model_cfg = payload.get("model")
            if not model_cfg or not isinstance(model_cfg, dict):
                model_cfg = STATE.get("model") or store_mod.load_config().get("model")
            else:
                prev = (STATE.get("model") or store_mod.load_config().get("model") or {})
                if model_cfg.get("api_key") in (None, "", "***"):
                    model_cfg["api_key"] = prev.get("api_key", "")
            res = model_client.test_connection(model_cfg)
            self._send(200, json.dumps(res, ensure_ascii=False))
        elif parsed.path in ('/api/components', '/api/components/update'):
            from knowledge import revision
            project = payload.get('project', '')
            if not project or not os.path.isdir(project):
                self._send(400, json.dumps({'error': 'unknown project'}))
                return
            model_cfg = STATE.get('model') or store_mod.get_active_model(store_mod.load_config())
            if not model_client.configured(model_cfg):
                self._send(400, json.dumps({'error': 'model not configured'}))
                return
            try:
                code, result = revision.revise(os.path.abspath(project), model_cfg,
                    lang=str(payload.get('lang') or 'zh').lower(), full=parsed.path == '/api/components')
            except Exception as exc:
                self._send(502, json.dumps({'ok': False, 'error': str(exc)[:200]}))
                return
            self._send(code, json.dumps(result, ensure_ascii=False))
        elif parsed.path == "/api/file_deep_analysis":
            project = payload.get("project", "")
            fpath = payload.get("file", "")
            lang = str(payload.get("lang") or "zh").lower()
            if not project or not os.path.isdir(project) or not fpath:
                self._send(400, json.dumps({"error": "unknown project or file"}))
                return
            model_cfg = STATE.get("model") or store_mod.load_config().get("model")
            if not model_client.configured(model_cfg):
                self._send(400, json.dumps({"error": "model not configured"}))
                return
            context = file_analysis_mod.analyze_source_file(project, fpath)
            if context is None:
                self._send(404, json.dumps({"error": "file not found"}))
                return
            deep = model_client.analyze_file_deep(project, fpath, context, model_cfg, lang=lang)
            if deep is None:
                self._send(502, json.dumps({"error": "深度解析失败 (模型返回格式不符合规范或被拦截)"}))
                return
            self._send(200, json.dumps({"ok": True, "deep": deep}, ensure_ascii=False))
        elif parsed.path == "/api/backfill":
            project = payload.get("project", "")
            if not project or not os.path.isdir(project):
                self._send(400, json.dumps({"error": "unknown project"}))
                return
            try:
                limit = max(1, min(200, int(payload.get("limit_sessions", 30))))
            except (TypeError, ValueError):
                limit = 30
            recent = payload.get('recent_rounds', 5)
            if type(recent) is not int or recent < 1:
                self._send(400, json.dumps({'error': 'recent_rounds must be a positive integer'}))
                return
            project = os.path.abspath(project)
            if project not in STATE['projects']:
                self._send(403, json.dumps({'error': 'Project is not tracked'}))
                return
            new_events, dropped, queued = _ingest([project], historical=True, limit_sessions=limit, recent=recent)
            STATE["dropped"] += dropped
            self._send(200, json.dumps({"ok": True, "new_events": len(new_events),
                                        "queued": queued, "dropped": dropped}))
        elif parsed.path == "/api/projects/track":
            project = payload.get("project", "")
            if not project or not os.path.isdir(project):
                self._send(400, json.dumps({"error": "directory not found"}))
                return
            abs_proj = os.path.abspath(project)
            config = store_mod.load_config()
            projects = config.get("projects", [])
            if abs_proj not in projects:
                projects.append(abs_proj)
                config["projects"] = projects
            ignored = config.get("ignored_projects", [])
            if abs_proj in ignored:
                ignored.remove(abs_proj)
                config["ignored_projects"] = ignored
            store_mod.save_config(config)
            STATE["projects"] = config.get("projects", [])

            # Run backfill in background daemon thread to avoid blocking HTTP response
            def _async_backfill():
                try:
                    new_events, dropped, queued = _ingest([abs_proj], historical=True, limit_sessions=15)
                    STATE["dropped"] += dropped
                except Exception:
                    pass
            threading.Thread(target=_async_backfill, daemon=True).start()

            self._send(200, json.dumps({
                "ok": True,
                "project": abs_proj,
                "projects": config["projects"]
            }, ensure_ascii=False))
        elif parsed.path == "/api/projects/untrack":
            project = payload.get("project", "")
            if not project:
                self._send(400, json.dumps({"error": "empty project"}))
                return
            abs_proj = os.path.abspath(project)
            config = store_mod.load_config()
            projects = config.get("projects", [])
            if abs_proj in projects:
                projects.remove(abs_proj)
                config["projects"] = projects
            ignored = config.get("ignored_projects", [])
            if abs_proj not in ignored:
                ignored.append(abs_proj)
                config["ignored_projects"] = ignored
            store_mod.save_config(config)
            STATE["projects"] = config.get("projects", [])
            if hasattr(graph_builder, "MAP_CACHE"):
                graph_builder.MAP_CACHE.clear()
            self._send(200, json.dumps({
                "ok": True,
                "untracked": abs_proj,
                "projects": config["projects"]
            }, ensure_ascii=False))
        elif parsed.path == "/api/sessions/untrack":
            session_id = (payload.get("session_id") or "").strip()
            if not session_id:
                self._send(400, json.dumps({"error": "empty session_id"}))
                return
            ignored = store_mod.ignore_session(session_id)
            if hasattr(graph_builder, "MAP_CACHE"):
                graph_builder.MAP_CACHE.clear()
            self._send(200, json.dumps({
                "ok": True,
                "untracked_session": session_id,
                "ignored_sessions": ignored
            }, ensure_ascii=False))
        elif parsed.path == "/api/sessions/track":
            session_id = (payload.get("session_id") or "").strip()
            if not session_id:
                self._send(400, json.dumps({"error": "empty session_id"}))
                return
            ignored = store_mod.unignore_session(session_id)
            if hasattr(graph_builder, "MAP_CACHE"):
                graph_builder.MAP_CACHE.clear()
            self._send(200, json.dumps({
                "ok": True,
                "restored_session": session_id,
                "ignored_sessions": ignored
            }, ensure_ascii=False))
        elif parsed.path == "/api/projects/ignore":
            project = payload.get("project", "")
            if not project:
                self._send(400, json.dumps({"error": "empty project"}))
                return
            abs_proj = os.path.abspath(project)
            config = store_mod.load_config()
            ignored = config.get("ignored_projects", [])
            if abs_proj not in ignored:
                ignored.append(abs_proj)
                config["ignored_projects"] = ignored
            store_mod.save_config(config)
            self._send(200, json.dumps({"ok": True, "ignored": config["ignored_projects"]}))
        elif parsed.path == '/api/projects/discovery-scope':
            path = str(payload.get('path') or '').strip()
            path = os.path.realpath(os.path.expanduser(path)) if path else ''
            if not path or not os.path.isdir(path):
                self._send(400, json.dumps({'ok': False, 'error': 'Choose an existing folder'}))
                return
            config = store_mod.load_config()
            config['discovery_scope'] = path
            store_mod.save_config(config)
            NOTIFIED_PROJECTS.clear()
            self._send(200, json.dumps({'ok': True, 'scope': path}))
        elif parsed.path == "/api/projects/auto-track":
            enabled = bool(payload.get("enabled"))
            config = store_mod.load_config()
            config["auto_track_discovered"] = enabled
            store_mod.save_config(config)
            self._send(200, json.dumps({"ok": True, "auto_track_discovered": enabled}))
        elif parsed.path == '/api/knowledge/explain':
            from knowledge.explanations import explain
            project = str(payload.get('project') or '')
            term = str(payload.get('term') or '').strip()
            lang = str(payload.get('lang') or 'zh')
            scope = str(payload.get('scope') or 'architecture')
            question = str(payload.get('question') or '')
            if (not term or len(term) > 2000 or len(question) > 1000 or len(scope) > 500
                    or lang not in ('zh', 'en')):
                self._send(400, json.dumps({'ok': False, 'error': 'Invalid term, language or question'}))
                return
            if os.path.realpath(project) not in {os.path.realpath(p) for p in STATE['projects']}:
                self._send(403, json.dumps({'ok': False, 'error': 'Project is not registered'}))
                return
            try:
                result = explain(project, term, lang, STATE.get('model'), scope=scope,
                                 generate=not payload.get('cache_only'),
                                 project_only=bool(payload.get('project_only')), question=question,
                                 force=bool(payload.get('force')))
            except Exception as exc:
                self._send(502, json.dumps({'ok': False, 'error': str(exc)[:300]}))
                return
            self._send(200, json.dumps(result, ensure_ascii=False))
        elif parsed.path == "/api/knowledge/ask":
            kid = str(payload.get("id") or "")
            term = str(payload.get("term") or "")
            question = str(payload.get("question") or "").strip()
            lang = str(payload.get("lang") or "zh").lower()
            entry = knowledge_bank.get_knowledge_by_id(kid) if kid else None
            if not entry and term:
                entry = knowledge_bank.find_knowledge_by_term(term)
            if not entry and term and len(term) <= 160:
                entry = {'id': term, 'name': term, 'definition': '', 'detailed_explanation': ''}
            if not entry:
                self._send(400, json.dumps({'error': 'A term of up to 160 characters is required'}))
                return
            if not question:
                self._send(400, json.dumps({"error": "empty question"}, ensure_ascii=False))
                return
            model_cfg = STATE.get("model")
            related = [r for r in rag_mod.retrieve_knowledge(
                "%s %s" % (entry.get("name", ""), question), top_k=4)
                if r.get("id") != entry.get("id")][:2]
            answer = model_client.answer_knowledge(entry, related, question, model_cfg, lang=lang)
            if answer:
                self._send(200, json.dumps({"ok": True, "answer": answer}, ensure_ascii=False))
            else:
                configured = model_client.configured(model_cfg)
                self._send(200, json.dumps({
                    "ok": False,
                    "configured": configured,
                    "error": "模型调用失败，请检查配置或稍后重试" if configured
                             else "未配置分析模型：请在顶部模型栏配置 OpenAI-compatible 接口后重试",
                    "related": [{"id": r.get("id"), "name": r.get("name")} for r in related],
                }, ensure_ascii=False))
        elif parsed.path == "/hooks/claude":
            try:
                project = tailer.attribute(payload.get("cwd") or "", STATE["projects"])
                if project is None:
                    self._send(200, json.dumps({"ok": True, "attributed": False}))
                    return
                event = _hook_event(payload)
                event['analysis_status'] = 'evidence_only'
                event['_project'] = project
                stored = store_mod.append_event(project, event)
                if stored:
                    event["_project"] = project
                    with SUB_LOCK:
                        for sub in SUBSCRIBERS:
                            try:
                                sub.put_nowait(event)
                            except queue.Full:
                                pass
                self._send(200, json.dumps({"ok": True, "attributed": True,
                                            "event_id": event["event_id"]}))
            except Exception as exc:
                self._send(200, json.dumps({"ok": False, "error": str(exc)[:200]}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="vibe-learning observer")
    parser.add_argument("--project", default="")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    config = store_mod.load_config()
    if args.project:
        if not os.path.isdir(args.project):
            print("not a directory: %s" % args.project, file=sys.stderr)
            return 2
        abs_project = os.path.abspath(args.project)
        if abs_project not in config.get("projects", []):
            config["projects"] = config.get("projects", []) + [abs_project]
            store_mod.save_config(config)
    port = args.port or config.get("port") or 8765
    STATE["model"] = store_mod.get_active_model(config)
    STATE["projects"] = config.get("projects", [])
    threading.Thread(target=_analysis_worker, name="vibe-learning-analysis", daemon=True).start()
    threading.Thread(target=_architecture_worker, name="vibe-learning-architecture", daemon=True).start()
    thread = threading.Thread(target=_poll_loop, name="vibe-learning-listener", daemon=True)
    thread.start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("vibe-learning on http://127.0.0.1:%d  projects=%s"
          % (server.server_port, STATE["projects"]), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

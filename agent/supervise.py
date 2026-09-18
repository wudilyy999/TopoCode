"""Optional live supervision of a coding-agent session.

Claude Code: Stop hook may return decision=block so the agent keeps working.
Codex: `codex exec resume` launches a real continuation (not clipboard).
Off by default. Never writes agent home directories or watched projects.

Session records (enabled flag, goal, block counters) stay in this module;
stop judgement and escalation run in the LangGraph state graph
(agent/graphs/supervise.py) with checkpointed assessment history and a
human-gate interrupt once the auto-nudge budget is exhausted.
"""

import os
import shutil
import subprocess
import threading
import time

from config import store as store_mod

MAX_BLOCKS = 3
BLOCK_WINDOW_SEC = 600
STOP_QUESTION = (
    "The coding agent is about to stop. If the user goal is unfinished or the "
    "last round drifted, set status to incomplete or off_goal and put a short "
    "continuation instruction in nudge. If the work is done, status idle and empty nudge."
)


def session_key(agent_id, session_id):
    return "%s:%s" % (agent_id or "", session_id or "")


def _records(config=None):
    config = config if config is not None else store_mod.load_config()
    records = config.get("supervised_sessions")
    return records if isinstance(records, dict) else {}


def get(agent_id, session_id, config=None):
    return _records(config).get(session_key(agent_id, session_id)) or {}


def is_enabled(agent_id, session_id, config=None):
    rec = get(agent_id, session_id, config)
    return bool(rec.get("enabled"))


def list_enabled(config=None):
    return {key: rec for key, rec in _records(config).items() if rec.get("enabled")}


def set_enabled(agent_id, session_id, project, enabled, goal=""):
    config = store_mod.load_config()
    records = dict(_records(config))
    key = session_key(agent_id, session_id)
    rec = dict(records.get(key) or {})
    rec.update({
        "enabled": bool(enabled),
        "agent_id": agent_id,
        "session_id": session_id,
        "project": os.path.abspath(project) if project else rec.get("project") or "",
        "goal": (goal or rec.get("goal") or "")[:400],
        "blocks": 0 if enabled else rec.get("blocks") or 0,
    })
    records[key] = rec
    config["supervised_sessions"] = records
    store_mod.save_config(config)
    return rec


def _touch_block(agent_id, session_id):
    config = store_mod.load_config()
    records = dict(_records(config))
    key = session_key(agent_id, session_id)
    rec = dict(records.get(key) or {})
    now = time.time()
    last = float(rec.get("last_block_at") or 0)
    blocks = int(rec.get("blocks") or 0)
    if now - last > BLOCK_WINDOW_SEC:
        blocks = 0
    rec["blocks"] = blocks + 1
    rec["last_block_at"] = now
    records[key] = rec
    config["supervised_sessions"] = records
    store_mod.save_config(config)
    return rec["blocks"]


def _reset_blocks(agent_id, session_id):
    config = store_mod.load_config()
    records = dict(_records(config))
    key = session_key(agent_id, session_id)
    rec = dict(records.get(key) or {})
    rec["blocks"] = 0
    rec["last_block_at"] = 0
    records[key] = rec
    config["supervised_sessions"] = records
    store_mod.save_config(config)


def decide_stop(payload, model_cfg, lang="zh"):
    """Return JSON for Claude Stop hook stdout. Empty dict = allow stop.

    Runs the supervision LangGraph; on any internal failure the hook must
    never block the agent, so errors collapse to {}.
    """
    if payload.get("stop_hook_active") and int(get("claude-code", str(payload.get("session_id") or "")).get("blocks") or 0) >= MAX_BLOCKS:
        return {}
    if not is_enabled("claude-code", str(payload.get("session_id") or "")):
        return {}
    from agent.graphs.supervise import decide_stop as graph_decide_stop
    return graph_decide_stop(payload, model_cfg, lang=lang)


def pending_escalations():
    """Sessions whose supervision graph is waiting on a human decision."""
    from agent.graphs.supervise import pending_escalations as graph_pending
    return graph_pending()


def resume_escalation(agent_id, session_id, action):
    """Apply a human decision (disable | extend | continue) to an
    interrupted supervision run."""
    from agent.graphs.supervise import resume_escalation as graph_resume
    return graph_resume(agent_id, session_id, action)


def resume_codex(project, session_id, prompt):
    binary = shutil.which("codex")
    if not binary:
        return False, "codex CLI not found"
    if not session_id or not prompt.strip():
        return False, "session and prompt required"
    cwd = os.path.abspath(project) if project and os.path.isdir(project) else os.path.expanduser("~")

    def _run():
        try:
            subprocess.Popen(
                [binary, "exec", "resume", session_id, prompt.strip()[:800]],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    threading.Thread(target=_run, name="topocode-codex-resume", daemon=True).start()
    _touch_block("codex", session_id)
    return True, "launched"

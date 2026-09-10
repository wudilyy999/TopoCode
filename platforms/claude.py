"""Claude Code adapter: poll ~/.claude/projects/*/*.jsonl.

Entry shapes observed in the wild: user / assistant / queue-operation /
attachment / file-history-snapshot / summary / last-prompt. A round starts
at each user entry; following assistant entries contribute request/result
text and tool_use blocks contribute written-file paths. System injections
(thinking, system-reminder, apiErrorMessage) are skipped.
"""

import glob
import json
import os
import time

from platforms.base import BaseAdapter, register

ACTIVE_WINDOW_SEC = 600
TRUNC = 2000
REQUEST_KEEP = 4000
RESULT_KEEP = 8000
MAX_BACKFILL_BYTES = 64 * 1024 * 1024

_SYSTEM_MARKERS = ("<system-reminder>", "<thinking>", "<command-name>",
                   "<command-message>", "<local-command>")


def _fresh(path):
    try:
        return time.time() - os.path.getmtime(path) <= ACTIVE_WINDOW_SEC
    except OSError:
        return False


def _small_enough(path):
    try:
        return os.path.getsize(path) <= MAX_BACKFILL_BYTES
    except OSError:
        return False


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def _content_blocks(content):
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


@register("claude")
class ClaudeAdapter(BaseAdapter):
    agent_id = "claude-code"
    agent_label = "Claude Code"

    def discover_source_roots(self):
        return [os.path.expanduser("~/.claude/projects")]

    def discover_sessions(self):
        sessions = []
        for root in self.discover_source_roots():
            if not os.path.isdir(root):
                continue
            for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
                if _fresh(path):
                    sessions.append(path)
        return sessions

    def discover_all_sessions(self):
        sessions = []
        for root in self.discover_source_roots():
            if not os.path.isdir(root):
                continue
            for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
                if _small_enough(path):
                    sessions.append(path)
        return sessions

    def read_session(self, session_ref):
        rounds = []
        current = None
        try:
            with open(session_ref, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            return rounds
        offset = 0
        for line in lines:
            offset += len(line.encode("utf-8"))
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            kind = entry.get("type")
            if kind == "user":
                message = entry.get("message", {})
                results = [b for b in _content_blocks(message.get("content")) if b.get("type") == "tool_result"]
                if results:
                    if current:
                        for block in results:
                            target = pending.pop(block.get("tool_use_id"), None)
                            if target and not block.get("is_error"):
                                current["files"][target] = "modified"
                    continue
                text = _text_of(message.get("content", ""))
                if not text or any(m in text for m in _SYSTEM_MARKERS):
                    continue
                if current:
                    current["is_completed"] = True
                    rounds.append(current)
                pending = {}
                current = {
                    "session_id": entry.get("sessionId") or os.path.basename(session_ref)[:-6],
                    "turn_id": entry.get("uuid") or entry.get("promptId") or "t-%d" % offset,
                    "occurred_at": entry.get("timestamp") or "",
                    "cwd": entry.get("cwd") or "",
                    "request": text[:REQUEST_KEEP],
                    "result": "",
                    "files": {},
                    "status": "observed",
                    "is_completed": False,
                    "offset": offset,
                }
            elif kind == "assistant" and current is not None:
                if entry.get("isApiErrorMessage"):
                    current["status"] = "error"
                    continue
                message = entry.get("message", {})
                text = _text_of(message.get("content", ""))
                if text and not any(m in text for m in _SYSTEM_MARKERS):
                    current["result"] = (current["result"] + "\n" + text).strip()[-RESULT_KEEP:]
                if not current["cwd"]:
                    current["cwd"] = entry.get("cwd") or ""
                if not current["occurred_at"]:
                    current["occurred_at"] = entry.get("timestamp") or ""
                for block in _content_blocks(message.get("content")):
                    if block.get("type") == "tool_use":
                        current["is_completed"] = False
                        name = block.get("name", "")
                        if name in ("Edit", "Write", "NotebookEdit"):
                            target = (block.get("input") or {}).get("file_path") or (block.get("input") or {}).get("notebook_path")
                            if target:
                                pending[block.get("id")] = target
                if message.get("stop_reason") in ("end_turn", "stop_sequence"):
                    current["is_completed"] = True
        if current:
            rounds.append(current)
        return rounds

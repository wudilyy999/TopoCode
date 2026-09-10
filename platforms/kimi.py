"""Kimi Code adapter: poll ~/.kimi-code/sessions/*/session_*/agents/*/wire.jsonl.

Wire shapes (protocol 1.5): turn.prompt (user text in input[].text),
context.append_loop_event with event.type tool.call (name + args; Write/Edit
args carry path, Bash args carry command), tool.result (output/status),
turn.ended (reason). Round = one turn.prompt .. next turn.prompt (or EOF);
cwd comes from the sibling state.json of the session dir.
"""

import glob
import json
import os
import re
import time

from platforms.base import BaseAdapter, register

ACTIVE_WINDOW_SEC = 600
TRUNC = 2000
REQUEST_KEEP = 4000
RESULT_KEEP = 8000
MAX_BACKFILL_BYTES = 64 * 1024 * 1024

_WRITE_TOOLS = {"Write": "path", "Edit": "path", "NotebookEdit": "path"}

# Redirect targets that are sinks, not project files.
_SINK_PATHS = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"})

# Session cwd per wire file, so relative tool paths resolve against the
# project the agent actually ran in. Guarded by size: absurd session dirs
# are treated as unknown rather than trusted.
_CWD_CACHE = {}
_MAX_CWD_CACHE = 4096


def _wire_cwd(wire_path):
    if wire_path in _CWD_CACHE:
        return _CWD_CACHE[wire_path]
    cwd = ""
    parts = wire_path.split(os.sep)
    indices = [i for i, p in enumerate(parts) if p.startswith("session_")]
    if indices:
        state = os.path.join(os.sep.join(parts[:indices[-1] + 1]), "state.json")
        try:
            with open(state, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            value = data.get("cwd") or ""
            cwd = value if isinstance(value, str) else ""
        except (OSError, ValueError):
            cwd = ""
    if len(_CWD_CACHE) < _MAX_CWD_CACHE:
        _CWD_CACHE[wire_path] = cwd
    return cwd


def _clean_path(value, base=""):
    """Absolute paths pass; session-relative paths resolve against base."""
    if not isinstance(value, str):
        return None
    value = value.strip().strip("'\"").rstrip(";,)")
    if not value or "\n" in value or len(value) > 512:
        return None
    # 彻底过滤代码片段、变量插值与正则符号
    if any(c in value for c in ("%", "$", "*", "?", "<", ">", "|", ";", "\t", "{", "}", "(", ")", "[", "]", ":", "'", '"', ",")):
        return None
    if value.startswith("~") or value.startswith("=") or value.startswith("&"):
        return None
    if value in _SINK_PATHS:
        return None
    if re.search(r"(^|/)=[0-9]", value):
        return None
    if not value.startswith("/"):
        if not base or not base.startswith("/"):
            return None
        value = os.path.normpath(os.path.join(base, value))
        if not value.startswith("/"):
            return None
    name = value.rsplit("/", 1)[-1]
    if not name or name in (".", "..") or name.startswith("-"):
        return None
    # 严格排除单斜杠短标记如 /i, /gi, /a 等非正常工程文件
    parts = [p for p in value.strip("/").split("/") if p]
    if len(parts) <= 1 and len(parts[0] if parts else "") <= 3:
        return None
    return value


def _strip_fd_redirects(cmd):
    """Remove N> / N>&M / &> stream plumbing before hunting the file target."""
    out = []
    i, n = 0, len(cmd)
    while i < n:
        ch = cmd[i]
        if ch == "&" and i + 1 < n and cmd[i + 1] == ">":
            i += 2
            while i < n and cmd[i] in " \t":
                i += 1
            if i < n and cmd[i] == "-":
                i += 1
            else:
                while i < n and not cmd[i].isspace() and cmd[i] not in ";|":
                    i += 1
            out.append(" ")
            continue
        if ch.isdigit():
            j = i
            while j < n and cmd[j].isdigit():
                j += 1
            k = j
            while k < n and cmd[k] in " \t":
                k += 1
            if k < n and cmd[k] == ">":
                i = k + 1
                while i < n and cmd[i] in " \t":
                    i += 1
                if i < n and cmd[i] == "&":
                    i += 1
                    while i < n and not cmd[i].isspace() and cmd[i] not in ";|":
                        i += 1
                else:
                    while i < n and not cmd[i].isspace() and cmd[i] not in ";|":
                        i += 1
                out.append(" ")
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _bash_redirect_target(cmd, base=""):
    """Target of > / >> / tee writes only; reads never produce files."""
    if not isinstance(cmd, str):
        return None
    cmd = _strip_fd_redirects(cmd)
    if "| tee " in cmd:
        after = cmd.split("| tee ", 1)[1].strip()
        if after.startswith("-"):
            return None
        token = after.split()[0] if after.split() else ""
        return _clean_path(token, base)
    
    # 严格排除 Python 箭头 -> 或比较符 => 以及非重定向场景
    m = re.search(r"(?<![-=\w])(?:>>|>)\s*([a-zA-Z0-9_\-\./~]+)", cmd)
    if not m:
        return None
    token = m.group(1).strip()
    if token.startswith("-"):
        return None
    return _clean_path(token, base)


def _prompt_text(entry):
    parts = []
    for item in entry.get("input", []) or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    origin = entry.get("origin", {})
    if isinstance(origin, dict) and origin.get("kind") != "user":
        return ""
    return "\n".join(parts)


def _tool_file(name, args, base=""):
    if not isinstance(args, dict):
        return None
    if name in _WRITE_TOOLS:
        return _clean_path(args.get(_WRITE_TOOLS[name]), base)
    if name == "Bash":
        return _bash_redirect_target(args.get("command", ""), base)
    return None


def _result_text(result):
    if isinstance(result, dict):
        output = result.get("output", "")
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        status = result.get("status") or result.get("exitCode")
        if status not in (None, "", 0, "completed", "success"):
            return "%s (status=%s)" % (text, status)
        return text
    return "" if result is None else str(result)


@register("kimi-code")
class KimiAdapter(BaseAdapter):
    agent_id = "kimi-code"
    agent_label = "Kimi Code"

    def discover_source_roots(self):
        return [os.path.expanduser("~/.kimi-code/sessions")]

    def _session_cwd(self, wire_path):
        parts = wire_path.split(os.sep)
        try:
            idx = [i for i, p in enumerate(parts) if p.startswith("session_")][-1]
        except IndexError:
            return ""
        state = os.path.join(os.sep.join(parts[:idx + 1]), "state.json")
        try:
            with open(state, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            cwd = data.get("cwd") or ""
            return cwd if isinstance(cwd, str) else ""
        except (OSError, ValueError):
            return ""

    def _session_id(self, wire_path):
        parts = wire_path.split(os.sep)
        for part in reversed(parts):
            if part.startswith("session_"):
                return part
        return os.path.basename(wire_path)

    def _iter_wires(self):
        for root in self.discover_source_roots():
            if not os.path.isdir(root):
                continue
            # 严格锁定与用户直接交互的主会话(main)，避免子智能体(agent-xxx)的内部指令串入主时间线
            pattern = os.path.join(root, "*", "session_*", "agents", "main", "wire.jsonl")
            for path in glob.glob(pattern):
                yield path

    def discover_sessions(self):
        now = time.time()
        out = []
        for path in self._iter_wires():
            try:
                if now - os.path.getmtime(path) <= ACTIVE_WINDOW_SEC:
                    out.append(path)
            except OSError:
                continue
        return out

    def discover_all_sessions(self):
        out = []
        for path in self._iter_wires():
            try:
                if os.path.getsize(path) <= MAX_BACKFILL_BYTES:
                    out.append(path)
            except OSError:
                continue
        return out

    def read_session(self, session_ref):
        rounds = []
        current = None
        session_id = self._session_id(session_ref)
        cwd = self._session_cwd(session_ref)
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
            if kind == "turn.prompt":
                text = _prompt_text(entry)
                if not text:
                    continue
                if current:
                    current["is_completed"] = True
                    rounds.append(current)
                t_val = entry.get("time")
                occurred = ""
                if isinstance(t_val, (int, float)):
                    sec = t_val / 1000.0 if t_val > 1e11 else float(t_val)
                    try:
                        occurred = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sec))
                    except Exception:
                        occurred = ""
                elif isinstance(t_val, str):
                    occurred = t_val
                if not occurred:
                    try:
                        occurred = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(session_ref)))
                    except Exception:
                        occurred = ""
                current = {
                    "session_id": session_id,
                    "turn_id": "turn-%s" % entry.get("time", offset),
                    "occurred_at": occurred,
                    "cwd": cwd,
                    "request": text[:REQUEST_KEEP],
                    "result": "",
                    "files": {},
                    "status": "observed",
                    "offset": offset,
                    "is_completed": False,
                }
            elif kind == "context.append_loop_event" and current is not None:
                current["offset"] = offset
                event = entry.get("event", {})
                if not isinstance(event, dict):
                    continue
                subtype = event.get("type")
                if subtype == "tool.call":
                    current["is_completed"] = False
                    base = _wire_cwd(session_ref)
                    found = _tool_file(event.get("name", ""), event.get("args", {}), base)
                    call_id = event.get("tool_call_id") or event.get("call_id") or event.get("id") or ""
                    current.setdefault("pending_tools", {})[call_id] = found
                elif subtype == "tool.result":
                    result = event.get("result")
                    call_id = event.get("tool_call_id") or event.get("call_id") or event.get("id") or ""
                    found = current.get("pending_tools", {}).pop(call_id, None)
                    success = not isinstance(result, dict) or (
                        not result.get("is_error") and result.get("status") in (None, "", "completed", "success")
                        and result.get("exitCode", 0) == 0)
                    if found and success:
                        current["files"][found] = "modified"
                    text = _result_text(result)
                    if text:
                        current["result"] = (current["result"] + "\n" + text).strip()[-RESULT_KEEP:]
                elif subtype in ("message", "assistant.message"):
                    text = event.get("content") or event.get("text") or ""
                    if isinstance(text, str):
                        current["result"] = (current["result"] + "\n" + text).strip()[-RESULT_KEEP:]
            elif kind == "turn.ended" and current is not None:
                current["offset"] = offset
                current["is_completed"] = True
                if entry.get("reason") not in (None, "", "completed", "success"):
                    current["status"] = "error"
        if current:
            rounds.append(current)
        return rounds

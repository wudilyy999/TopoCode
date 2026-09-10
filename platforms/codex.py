"""Codex adapter: poll ~/.codex/sessions/**/**/rollout-*.jsonl.

Shapes: session_meta (id/cwd), turn_context (turn_id/cwd), response_item
(function_call exec_command/write_stdin, custom_tool_call apply_patch,
message, reasoning), event_msg (user_message/agent_message/task_*).
A round starts at each event_msg user_message; tool calls until the next
user message attach written-file paths; apply_patch input is scanned for
"Add File:"/"Update File:" headers.
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

_PATCH_FILE = re.compile(r"(?m)^\*\*\*\s+(?:Add File|Update File):\s*(\S+)")

# Redirect targets that are sinks, not project files.
_SINK_PATHS = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"})


def _clean_path(value):
    if not isinstance(value, str):
        return None
    value = value.strip().strip("'\"()").rstrip(";,)")
    if not value.startswith("/") or "\n" in value or len(value) > 512:
        return None
    if any(c in value for c in ("%", "$", "*", "?", "<", ">", "|", ";", "\t")):
        return None
    if value in _SINK_PATHS:
        return None
    if value.startswith("=") or value.startswith("&"):
        return None
    if re.search(r"(^|/)=[0-9]", value):
        return None
    name = value.rsplit("/", 1)[-1]
    if not name or name in (".", ".."):
        return None
    return value


def _patch_files(text):
    return [p for p in (_clean_path(m) for m in _PATCH_FILE.findall(text or "")) if p]


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


def _bash_redirect_target(cmd):
    if not isinstance(cmd, str):
        return None
    cmd = _strip_fd_redirects(cmd)
    if "| tee " in cmd:
        after = cmd.split("| tee ", 1)[1].strip()
        if after.startswith("-"):
            return None
        token = after.split()[0] if after.split() else ""
        return _clean_path(token)
    chunks = cmd.replace(">>", " > ").replace(">", " > ").split(" > ")
    if len(chunks) < 2:
        return None
    first = chunks[1].strip()
    if first.startswith("-"):
        return None
    token = first.split()[0] if first.split() else ""
    return _clean_path(token)


def _exec_write_paths(name, arguments, cwd=''):
    if name != "exec_command":
        return []
    try:
        args = json.loads(arguments or "{}")
    except ValueError:
        return []
    cmd = args.get("cmd", "")
    if not isinstance(cmd, str) or "apply_patch" in cmd.lower():
        return []
    variables = {}
    for match in re.finditer(r'(?:^|[;\n])\s*([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|\'[^\']*\'|[^\s;]+)', cmd):
        variables[match.group(1)] = match.group(2).strip('"\'')
    clean_cmd = _strip_fd_redirects(cmd)
    targets = re.findall(r'(?:>>|>)\s*("[^"]*"|\'[^\']*\'|[^\s;|]+)', clean_cmd)
    paths = []
    for target in targets:
        target = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)',
                        lambda match: variables.get(match.group(1) or match.group(2), match.group(0)),
                        target).strip('"\'')
        if not os.path.isabs(target):
            target = os.path.join(args.get('workdir') or cwd or '', target)
        cleaned = _clean_path(os.path.realpath(target))
        if cleaned and cleaned not in paths:
            paths.append(cleaned)
    return paths


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


@register("codex")
class CodexAdapter(BaseAdapter):
    agent_id = "codex"
    agent_label = "Codex"

    def discover_source_roots(self):
        return [os.path.expanduser("~/.codex/sessions")]

    def discover_sessions(self):
        sessions = []
        for root in self.discover_source_roots():
            if not os.path.isdir(root):
                continue
            for path in glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True):
                if _fresh(path):
                    sessions.append(path)
        return sessions

    def discover_all_sessions(self):
        sessions = []
        for root in self.discover_source_roots():
            if not os.path.isdir(root):
                continue
            for path in glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True):
                if _small_enough(path):
                    sessions.append(path)
        return sessions

    def read_session(self, session_ref):
        rounds = []
        current = None
        session_id = os.path.basename(session_ref)
        cwd = ""
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
            payload = entry.get("payload", {}) if isinstance(entry.get("payload"), dict) else {}
            if kind == "session_meta":
                session_id = str(payload.get("id") or session_id)
                cwd = payload.get("cwd") or cwd
            elif kind == "turn_context":
                cwd = payload.get("cwd") or cwd
                if current:
                    current["cwd"] = cwd
            elif kind == "event_msg":
                subtype = payload.get("type")
                if subtype == "user_message":
                    if current:
                        current["is_completed"] = True
                        rounds.append(current)
                    pending = {}
                    current = {
                        "session_id": session_id,
                        "turn_id": "user-%d" % offset,
                        "occurred_at": entry.get("timestamp") or "",
                        "cwd": cwd,
                        "request": str(payload.get("message", ""))[:REQUEST_KEEP],
                        "result": "",
                        "files": {},
                        "status": "observed",
                        "is_completed": False,
                        "offset": offset,
                    }
                elif subtype == "item_completed" and isinstance(payload.get("item"), dict):
                    item = payload["item"]
                    if item.get("type") == "UserMessage":
                        if current:
                            current["is_completed"] = True
                            rounds.append(current)
                        content = item.get("content") or []
                        request = "\n".join(
                            str(part.get("text", "")) for part in content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                        pending = {}
                        current = {
                            "session_id": session_id,
                            "turn_id": payload.get("turn_id") or "user-%d" % offset,
                            "occurred_at": entry.get("timestamp") or "",
                            "cwd": cwd,
                            "request": request[:REQUEST_KEEP],
                            "result": "",
                            "files": {},
                            "status": "observed",
                            "is_completed": False,
                            "offset": offset,
                        }
                elif subtype == "agent_message" and current is not None:
                    text = str(payload.get("message", ""))
                    if text:
                        current["result"] = (current["result"] + "\n" + text).strip()[-RESULT_KEEP:]
                elif subtype in ("task_complete", "task_completed", "turn_aborted") and current is not None:
                    current["is_completed"] = True
                    if payload.get("last_agent_message"):
                        current["result"] = str(payload["last_agent_message"])[-RESULT_KEEP:]
                    if subtype == "turn_aborted":
                        current["status"] = "error"
            elif kind == "response_item" and current is not None:
                subtype = payload.get("type")
                if subtype in ("custom_tool_call", "function_call"):
                    current["is_completed"] = False
                    name = payload.get("name", "")
                    changes = {}
                    if name == "apply_patch":
                        text = payload.get("input") or payload.get("arguments") or ""
                        for action, path in re.findall(r"(?m)^\*\*\* (Add|Update|Delete) File: (.+)$", text):
                            full = path.strip()
                            if not os.path.isabs(full):
                                full = os.path.join(cwd, full)
                            full = _clean_path(full)
                            if full:
                                changes[full] = {"Add": "added", "Update": "modified", "Delete": "deleted"}[action]
                    else:
                        for found in _exec_write_paths(name, payload.get("arguments", ""), cwd=cwd):
                            changes[found] = "modified"
                    pending[payload.get("call_id")] = changes
                elif subtype in ("custom_tool_call_output", "function_call_output"):
                    changes = pending.pop(payload.get("call_id"), {})
                    output = payload.get("output", "")
                    text = output if isinstance(output, str) else json.dumps(output)
                    failed = payload.get('exit_code', 0) not in (0, None) or payload.get('status') in ('failed', 'error') or re.search(r"(?im)(?:^Error:|Failed to |apply_patch verification failed|Process exited with code [1-9]|.*exit code[:=]\s*[1-9])", text)
                    if not payload.get("is_error") and not failed:
                        current["files"].update(changes)
                elif subtype == "message" and payload.get("role") == "assistant":
                    text = ""
                    for item in payload.get("content", []) or []:
                        if isinstance(item, dict) and item.get("type") == "output_text":
                            text += item.get("text", "")
                    if text.strip():
                        current["result"] = (current["result"] + "\n" + text).strip()[-RESULT_KEEP:]
                    if payload.get("phase") == "final_answer":
                        current["is_completed"] = True
        if current:
            rounds.append(current)
        return rounds

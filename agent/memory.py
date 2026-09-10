"""Agent session memory for cumulative conversation and change analysis.
Maintains context across multiple rounds of dialogue within a session.
Includes deterministic token-budget auto-compaction (no model call required).
"""

import os
import re
from typing import Any, Dict, List, Optional

from config import store as store_mod

VALID_LEVELS = ("novice", "practitioner", "expert")

MAX_LIVE_TURNS = 40          # 活跃轮次上限，超出后最老轮次折叠为一行摘要
MAX_COMPACTED_DIGESTS = 30   # 压缩摘要区最多保留的行数
DEFAULT_TOKEN_BUDGET = 2400  # 注入模型的历史上下文 token 预算


def estimate_tokens(text: str) -> int:
    """Rough token estimate for mixed Chinese/English text.

    Chinese chars ~ 1 token each; other chars (English/code/digits) ~ 1 per 3.5 chars.
    """
    if not text:
        return 0
    zh = len(re.findall(r"[\u4e00-\u9fa5]", text))
    return int(zh + (len(text) - zh) / 3.5) + 1


class SessionMemory:
    """Maintains working memory and context for an agent session."""

    def __init__(self, session_id: str, project: str = ""):
        self.session_id = session_id
        self.project = project
        self.turns: List[Dict[str, Any]] = []
        self.compacted_digests: List[str] = []
        self.inferred_user_level: str = "practitioner"
        self.known_concepts: set = set()
        self.touched_files: set = set()

    def update_from_history(self, history_events: List[Dict[str, Any]]) -> None:
        """Hydrate memory from past session events."""
        self.turns = []
        self.compacted_digests = []
        for ev in history_events:
            self.add_turn(ev, update_profile=False)
        self._recalculate_profile()

    def add_turn(self, event: Dict[str, Any], update_profile: bool = True) -> None:
        """Record a turn into memory, compacting overflow turns into one-line digests."""
        self.turns.append(event)
        for f in event.get("files", []):
            p = f.get("path")
            if p:
                self.touched_files.add(p)
        dialogue = event.get("dialogue") or event.get("analysis") or {}
        for kp in dialogue.get("knowledge_points", []):
            self.known_concepts.add(kp)
        if len(self.turns) > MAX_LIVE_TURNS:
            overflow = self.turns[:-MAX_LIVE_TURNS]
            self.turns = self.turns[-MAX_LIVE_TURNS:]
            self.compacted_digests.extend(self._digest_line(ev) for ev in overflow)
            self.compacted_digests = self.compacted_digests[-MAX_COMPACTED_DIGESTS:]
        if update_profile:
            self._recalculate_profile()

    def _recalculate_profile(self) -> None:
        """Estimate user expertise and communication trajectory from accumulated turns."""
        levels = []
        for ev in self.turns:
            d = ev.get("dialogue") or {}
            lvl = d.get("user_level")
            if lvl in ("novice", "practitioner", "expert"):
                levels.append(lvl)
        if levels:
            # Most recent turn weighting
            self.inferred_user_level = levels[-1]

    def _digest_line(self, ev: Dict[str, Any]) -> str:
        """One-line compact digest of a turn, used when compressing old history."""
        d = ev.get("dialogue") or {}
        files = [f.get("path") for f in ev.get("files", []) if f.get("path")]
        file_str = ",".join(files[:3]) if files else "无改动"
        req = (ev.get("request_text") or "").strip().replace("\n", " ")[:60]
        ts = str(ev.get("occurred_at") or "")[:16]
        return f"[{ts}|{d.get('user_level', '-')}|{file_str}] {req or '(无文本)'}"

    def build_context_summary(self, max_turns: int = 8, max_chars_per_turn: int = 800,
                              token_budget: int = DEFAULT_TOKEN_BUDGET) -> str:
        """Format past turns for model comprehension with token-budget auto-compaction.

        Recent turns render in full; older in-window turns degrade to one-line
        digests. The detail window shrinks stepwise until the estimated token
        count fits the budget, so over-long histories never blow up the prompt.
        """
        if not self.turns:
            return "(本会话首轮，无历史上下文)"
        recent = self.turns[-max_turns:]
        prefix = ""
        if self.compacted_digests:
            prefix = "更早历史(自动压缩摘要):\n" + "\n".join(self.compacted_digests[-6:]) + "\n\n"
        ladder = [(len(recent), max_chars_per_turn), (6, 400), (4, 300), (2, 200), (1, 150)]
        text = ""
        for keep, chars in ladder:
            keep = min(keep, len(recent))
            text = prefix + self._render_window(recent, keep, chars)
            if estimate_tokens(text) <= token_budget:
                break
        return text

    def _render_window(self, recent: List[Dict[str, Any]], keep: int,
                       max_chars_per_turn: int) -> str:
        lines = []
        old = recent[:-keep] if keep < len(recent) else []
        if old:
            lines.append("较早轮次(摘要):")
            lines.extend("  " + self._digest_line(ev) for ev in old)
        for i, ev in enumerate(recent[-keep:], 1):
            req = (ev.get("request_text") or "").strip()[:max_chars_per_turn]
            res = (ev.get("result_text") or "").strip()[:max_chars_per_turn]
            d = ev.get("dialogue") or {}
            files = [f.get("path") for f in ev.get("files", []) if f.get("path")]
            file_str = ", ".join(files[:5]) if files else "无改动"
            meaning = (d.get("technical_meaning") or d.get("summary") or "")[:max_chars_per_turn]
            lines.append(
                f"[轮次 {i} | 文件: {file_str}]\n"
                f"  用户诉求: {req or '(无文本)'}\n"
                f"  Agent回应: {res or '(无文本)'}\n"
                f"  改动含义: {meaning}"
            )
        return "\n".join(lines)


class UserMemory:
    """Retain the background profile and track encountered concepts across sessions."""

    def __init__(self, project: str):
        self.project = project
        self.state = store_mod.load_user_memory(project) or {
            "schema_version": "user.memory.v1",
            "user_level": "practitioner",
            "user_persona": "",
            "user_persona_reason": "",
            "levels_timeline": [],
            "sessions": [],
            "turns_analyzed": 0,
        }

    @property
    def user_level(self) -> str:
        return self.state.get("user_level", "practitioner")

    def record(self, event: Dict[str, Any]) -> Dict[str, Any]:
        dialogue = event.get("dialogue") or {}
        level = dialogue.get("user_level")
        if level in VALID_LEVELS:
            self.state["user_level"] = level
            timeline = self.state.setdefault("levels_timeline", [])
            timeline.append({"level": level, "at": store_mod.now_iso(),
                             "session": (event.get("session_id") or "")[:12]})
            self.state["levels_timeline"] = timeline[-50:]
        for key in ("user_persona", "user_persona_reason"):
            value = str(dialogue.get(key, "")).strip()
            if value:
                self.state[key] = value
        concepts = list(self.state.get("encountered_concepts", []))
        for point in dialogue.get("knowledge_points", []):
            if point in concepts:
                concepts.remove(point)
            concepts.append(point)
        self.state["encountered_concepts"] = concepts[-100:]
        self.state["turns_analyzed"] = self.state.get("turns_analyzed", 0) + 1
        sid = event.get("session_id") or ""
        if sid:
            sessions = self.state.setdefault("sessions", [])
            if sid not in sessions:
                sessions.append(sid)
                self.state["sessions"] = sessions[-20:]
        store_mod.save_user_memory(self.project, self.state)
        return self.state

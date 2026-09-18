"""Session supervision as a LangGraph state graph.

Replaces the flat counter rules of agent/supervise.decide_stop() with:

    load -> assess(model) -> route
        | allow     -> record -> allow (hook returns {})
        | block     -> nudge  -> block (hook returns decision=block)
        | escalate  -> interrupt() -> human_gate -> route by human action

What the graph adds over the rule-based version:
- assessment history persisted via the checkpointer (assess sees prior
  nudges and escalations, not just a block counter),
- escalate -> interrupt(): when the auto-nudge budget is exhausted the
  session surfaces as a human decision point in the desk modal instead of
  silently giving up,
- human actions (disable / extend / continue) resume the interrupted graph.

The graph orchestrates only TopoCode's own judgement; the coding agent is
still driven exclusively by its own hooks / `codex exec resume`.
"""

import os
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from agent.graphs.common import graph_checkpointer
from model_client import client as model_client

MAX_BLOCKS = 3
BLOCK_WINDOW_SEC = 600

STOP_QUESTION = (
    "The coding agent is about to stop. If the user goal is unfinished or the "
    "last round drifted, set status to incomplete or off_goal and put a short "
    "continuation instruction in nudge. If the work is done, status idle and empty nudge."
)


from langgraph.graph.message import add_messages
from typing import Annotated


def _merge_history(left, right):
    return list(left or []) + list(right or [])


class SupState(TypedDict, total=False):
    history: Annotated[list, _merge_history]
    agent_id: str
    session_id: str
    project: str
    goal: str
    last_message: str
    model_cfg: Optional[Dict[str, Any]]
    lang: str
    enabled: bool
    blocks: int
    last_block_at: float
    window_blocks: int
    question: str
    status: str
    nudge: str
    reply: str
    human_action: str
    decision: Dict[str, Any]


def _rec_key(state: SupState) -> str:
    return "%s:%s" % (state.get("agent_id") or "", state.get("session_id") or "")


def load(state: SupState) -> Dict[str, Any]:
    from agent import supervise as legacy
    rec = legacy.get(state["agent_id"], state["session_id"])
    blocks = int(rec.get("blocks") or 0)
    last = float(rec.get("last_block_at") or 0)
    window = 0 if time.time() - last > BLOCK_WINDOW_SEC else blocks
    return {
        "enabled": bool(rec.get("enabled")),
        "blocks": blocks,
        "last_block_at": last,
        "window_blocks": window,
        "project": rec.get("project") or state.get("project") or "",
        "goal": (rec.get("goal") or "")[:400],
    }


def assess(state: SupState) -> Dict[str, Any]:
    project = state.get("project") or ""
    if not project or not os.path.isdir(project):
        return {"status": "idle", "nudge": ""}
    question = STOP_QUESTION
    if state.get("goal"):
        question += " User goal: %s" % state["goal"][:300]
    if state.get("last_message"):
        question += " Last assistant: %s" % state["last_message"][:600]
    prior = [h for h in (state.get("history") or []) if h.get("nudge")]
    if prior:
        question += " Previous nudges: " + " | ".join(h["nudge"][:120] for h in prior[-3:])
    result = model_client.desk_chat(
        project, question, session_id=state.get("session_id") or "",
        model_cfg=state.get("model_cfg"), lang=state.get("lang") or "zh",
    )
    if not result:
        return {"status": "idle", "nudge": ""}
    status = str(result.get("status") or "idle")
    nudge = (result.get("nudge") or result.get("reply") or "").strip()
    return {"status": status, "nudge": nudge, "reply": result.get("reply") or ""}


def _touch(state: SupState) -> None:
    from agent import supervise as legacy
    legacy._touch_block(state["agent_id"], state["session_id"])


def _append_history(state: SupState, entry: Dict[str, Any]) -> Dict[str, Any]:
    return {"history": [{**entry, "at": time.strftime("%Y-%m-%d %H:%M:%S")}]}


def allow_node(state: SupState) -> Dict[str, Any]:
    out = {"decision": {}}
    out.update(_append_history(state, {"action": "allow", "status": state.get("status") or "idle", "nudge": ""}))
    return out


def nudge_node(state: SupState) -> Dict[str, Any]:
    _touch(state)
    out = {"decision": {"decision": "block", "reason": (state.get("nudge") or "")[:800]}}
    out.update(_append_history(state, {"action": "block", "status": state.get("status") or "", "nudge": state.get("nudge") or ""}))
    return out


def human_gate(state: SupState) -> Dict[str, Any]:
    payload = interrupt({
        "type": "supervise_escalation",
        "agent_id": state.get("agent_id"),
        "session_id": state.get("session_id"),
        "project": state.get("project") or "",
        "goal": state.get("goal") or "",
        "status": state.get("status") or "",
        "last_nudge": state.get("nudge") or "",
        "blocks": state.get("window_blocks") or 0,
    })
    return {"human_action": str((payload or {}).get("action") or "continue")}


def apply_human(state: SupState) -> Dict[str, Any]:
    action = state.get("human_action") or "continue"
    if action == "disable":
        from agent import supervise as legacy
        legacy.set_enabled(state["agent_id"], state["session_id"], state.get("project") or "", False)
        out = {"decision": {}}
        out.update(_append_history(state, {"action": "human_disable", "status": "", "nudge": ""}))
        return out
    if action == "extend":
        # Human granted another auto-nudge budget; this stop is allowed and
        # the next ones get a fresh MAX_BLOCKS window.
        from agent import supervise as legacy
        legacy._reset_blocks(state["agent_id"], state["session_id"])
        out = {"decision": {}}
        out.update(_append_history(state, {"action": "human_extend", "status": "", "nudge": state.get("nudge") or ""}))
        return out
    out = {"decision": {}}
    out.update(_append_history(state, {"action": "human_continue", "status": "", "nudge": ""}))
    return out


def _route_after_assess(state: SupState) -> str:
    status = state.get("status") or "idle"
    nudge = state.get("nudge") or ""
    if status in ("off_goal", "incomplete") and nudge:
        if (state.get("window_blocks") or 0) >= MAX_BLOCKS:
            return "escalate"
        return "block"
    if (state.get("window_blocks") or 0) >= MAX_BLOCKS:
        return "escalate"
    return "allow"


def _route_after_human(state: SupState) -> str:
    return "apply"


def build_graph():
    graph = StateGraph(SupState)
    graph.add_node("load", load)
    graph.add_node("assess", assess)
    graph.add_node("allow", allow_node)
    graph.add_node("block", nudge_node)
    graph.add_node("escalate", human_gate)
    graph.add_node("apply_human", apply_human)

    graph.set_entry_point("load")
    graph.add_conditional_edges("load", lambda s: "assess" if s.get("enabled") else "allow",
                                {"assess": "assess", "allow": "allow"})
    graph.add_conditional_edges("assess", _route_after_assess,
                                {"allow": "allow", "block": "block", "escalate": "escalate"})
    graph.add_edge("escalate", "apply_human")
    graph.add_edge("apply_human", END)
    graph.add_edge("allow", END)
    graph.add_edge("block", END)
    return graph.compile(checkpointer=graph_checkpointer("supervise"))


_COMPILED = None


def _graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def _thread_id(agent_id, session_id):
    return "sup-%s-%s" % (agent_id or "agent", session_id or "session")


def decide_stop(payload, model_cfg, lang="zh"):
    """LangGraph replacement for supervise.decide_stop(). Same contract."""
    session_id = str(payload.get("session_id") or "")
    agent_id = "claude-code"
    state: SupState = {
        "agent_id": agent_id,
        "session_id": session_id,
        "last_message": str(payload.get("last_assistant_message") or "")[:600],
        "model_cfg": model_cfg,
        "lang": lang,
    }
    config = {"configurable": {"thread_id": _thread_id(agent_id, session_id)}}
    final = _graph().invoke(state, config=config)
    if final.get("__interrupt__"):
        # Human gate is holding this session: the hook allows the stop and
        # the escalation surfaces via /api/supervise pending_escalations.
        return {}
    return final.get("decision") or {}


def pending_escalations():
    """List interrupted (human-gate) supervision runs across all sessions."""
    graph = _graph()
    found = []
    # Threads are keyed per session; enumerate enabled records and probe each.
    from agent import supervise as legacy
    for key in legacy.list_enabled():
        agent_id, _, session_id = key.partition(":")
        config = {"configurable": {"thread_id": _thread_id(agent_id, session_id)}}
        snapshot = graph.get_state(config)
        if snapshot and snapshot.next:
            for task in snapshot.tasks:
                for intr in getattr(task, "interrupts", []) or []:
                    found.append({"thread": key, "value": intr.value})
    return found


def resume_escalation(agent_id, session_id, action):
    """Resume a human-gate interrupt with action: disable | extend | continue."""
    if action not in ("disable", "extend", "continue"):
        return False, "unknown action"
    config = {"configurable": {"thread_id": _thread_id(agent_id, session_id)}}
    final = _graph().invoke(Command(resume={"action": action}), config=config)
    return True, final.get("decision") or {}

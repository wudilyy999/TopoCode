"""Architecture revision as a LangGraph state graph.

Replaces the straight-line body of the old knowledge.revision.revise() with
an explicit graph:

    acquire -> load -> route
        | full + has arch        -> synthesize -> inherit_ids -> validate -> persist
        | full + no arch         -> synthesize -> validate -> persist
        | incremental, no arch   -> fail 400 (generate first)
        | incremental, no pending-> unchanged 200
        | incremental            -> prepare_patch -> patch -> apply -> persist
    model failure -> backoff -> acquire (bounded retries)
    lock busy     -> fail 409 immediately

What the graph adds over the linear version:
- bounded in-graph retry with backoff for model failures,
- deterministic per-node timing and attempt count returned as `trace`,
- every run checkpointed under ~/.topocode/graphs/architecture.sqlite.

`revision.revise()` keeps its signature and return contract and just invokes
this graph.
"""

import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from agent.graphs.common import graph_checkpointer
from knowledge import architecture
from model_client import client
from snapshot.scanner import take_snapshot

MAX_RETRIES = 2
BACKOFF_SEC = 1.5


class ArchState(TypedDict, total=False):
    project: str
    model_cfg: Optional[Dict[str, Any]]
    lang: str
    full: bool
    attempt: int
    code: int
    result: Optional[Dict[str, Any]]
    events: List[Dict[str, Any]]
    pending: List[Dict[str, Any]]
    arch: Optional[Dict[str, Any]]
    previous: Optional[Dict[str, Any]]
    patch_target: Optional[Dict[str, Any]]
    patch: Optional[Dict[str, Any]]
    no_change_patch: bool
    lock_busy: bool
    lock_owned: bool
    trace: List[Dict[str, Any]]


def _timed(fn):
    def node(state):
        started = time.time()
        out = fn(state)
        trace = list(state.get("trace") or [])
        trace.append({"node": fn.__name__, "ms": int((time.time() - started) * 1000)})
        out["trace"] = trace
        return out
    node.__name__ = fn.__name__
    return node


def _fail(code, message, retryable=False):
    result = {"ok": False, "error": message}
    if retryable:
        result["retryable"] = True
    return {"code": code, "result": result}


@_timed
def acquire(state: ArchState) -> Dict[str, Any]:
    # Owns the per-project lock for the rest of the run. retry() releases
    # before backoff so a contending run can win the lock while we wait.
    from knowledge.revision import project_lock
    acquired = project_lock(state["project"]).acquire(blocking=False)
    return {"lock_busy": not acquired, "lock_owned": acquired, "no_change_patch": False}


@_timed
def load(state: ArchState) -> Dict[str, Any]:
    from knowledge.revision import completed_events
    events = completed_events(state["project"])
    arch = architecture.load_architecture(state["project"])
    return {"events": events, "arch": arch, "previous": arch}


@_timed
def synthesize(state: ArchState) -> Dict[str, Any]:
    from graph import builder
    project = state["project"]
    snapshot = take_snapshot(project)
    struct = builder.structure(project, snapshot=snapshot, events=state["events"])
    arch = client.abstract_architecture_full(
        project, state["model_cfg"], struct,
        builder.repo_info(project, snapshot=snapshot), lang=state["lang"])
    if arch is None:
        return _fail(502, "Architecture synthesis failed", retryable=True)
    return {"arch": arch, "code": 0, "result": None}


@_timed
def inherit_ids(state: ArchState) -> Dict[str, Any]:
    arch = architecture.preserve_ids(state.get("previous"), state["arch"])
    arch["base_revision"] = len(state["events"])
    arch["incorporated_events"] = {}
    return {"arch": arch}


@_timed
def prepare_patch(state: ArchState) -> Dict[str, Any]:
    from knowledge.revision import event_version, pending_events
    pending = pending_events(state["arch"], state["events"])[:20]
    if not pending:
        _release(state)
        return {"code": 200, "result": {"ok": True, "unchanged": True, "pending": 0}}
    changed = [event for event in pending if event.get("files")]
    if not changed:
        # Evidence-only rounds (no file diffs) carry no architecture signal;
        # mark them incorporated and persist directly.
        arch = state["arch"]
        arch.setdefault("incorporated_events", {}).update(
            {event["event_id"]: event_version(event) for event in pending})
        return {"pending": pending, "no_change_patch": True, "code": 0, "result": None}
    files = {f["path"]: f for event in changed for f in event["files"]}
    meanings = [str((event.get("dialogue") or {}).get("technical_meaning")
                    or event.get("result_text") or event.get("request_text") or "")[:600]
                for event in changed]
    target = {"files": list(files.values()),
              "dialogue": {"technical_meaning": "\n".join(meanings)}}
    return {"pending": pending, "patch_target": target, "code": 0, "result": None}


@_timed
def patch(state: ArchState) -> Dict[str, Any]:
    result = client.update_architecture_patch(
        state["arch"], state["patch_target"], state["model_cfg"],
        lang=state["lang"], project=state["project"])
    if result is None:
        return _fail(502, "Architecture revision failed", retryable=True)
    return {"patch": result, "code": 0, "result": None}


@_timed
def apply(state: ArchState) -> Dict[str, Any]:
    arch = state["arch"]
    architecture.apply_update(arch, state["patch"],
                              set(take_snapshot(state["project"])["files"]),
                              len(state["events"]))
    return {"arch": arch}


@_timed
def validate(state: ArchState) -> Dict[str, Any]:
    return {"arch": architecture.normalize_architecture(state["arch"])}


@_timed
def persist(state: ArchState) -> Dict[str, Any]:
    from knowledge.revision import completed_events, event_version, pending_events
    arch = state["arch"]
    pending = state.get("pending")
    if pending is None:
        pending = state["events"] if state["full"] else []
    incorporated = arch.setdefault("incorporated_events", {})
    incorporated.update({event["event_id"]: event_version(event) for event in pending})
    arch["analysis_revision"] = sum(
        incorporated.get(e["event_id"]) == event_version(e) for e in state["events"])
    from agent.skills.loader import fingerprint
    arch["skill_fingerprint"] = fingerprint()
    architecture.save_architecture(state["project"], arch)
    from graph import builder
    builder.MAP_CACHE.clear()
    _release(state)
    return {"code": 200, "result": {
        "ok": True,
        "components": len(arch.get("components", [])),
        "overview": arch.get("overview", {}),
        "analysis_revision": arch["analysis_revision"],
        "pending": len(pending_events(arch, completed_events(state["project"]))),
    }}


@_timed
def backoff(state: ArchState) -> Dict[str, Any]:
    time.sleep(BACKOFF_SEC * ((state.get("attempt") or 0) + 1))
    return {"attempt": (state.get("attempt") or 0) + 1, "code": 0, "result": None}


def _release(state: ArchState) -> None:
    if not state.get("lock_owned"):
        return
    from knowledge.revision import project_lock
    lock = project_lock(state["project"])
    if lock.locked():
        lock.release()


def _route_acquire(state: ArchState) -> str:
    return "fail" if state.get("lock_busy") else "load"


def _route_load(state: ArchState) -> str:
    if state["full"]:
        return "synthesize"
    if not state["arch"]:
        return "fail"
    return "prepare_patch"


def _route_model(state: ArchState) -> str:
    if state.get("code"):
        if (state.get("result") or {}).get("retryable") and (state.get("attempt") or 0) < MAX_RETRIES:
            return "retry"
        return "fail"
    return "continue"


def _route_prepare(state: ArchState) -> str:
    if state.get("code"):
        return "done"
    if state.get("no_change_patch"):
        return "persist"
    return "patch"


def _fail_node(state: ArchState) -> Dict[str, Any]:
    if not state.get("lock_busy") and not state.get("code"):
        _release(state)
        return {"code": 400, "result": {"ok": False, "error": "Generate the architecture first"}}
    if state.get("lock_busy"):
        return {"code": 409, "result": {"ok": False, "error": "Architecture update already running", "busy": True}}
    _release(state)
    return {}


def build_graph():
    graph = StateGraph(ArchState)
    graph.add_node("acquire", acquire)
    graph.add_node("load", load)
    graph.add_node("synthesize", synthesize)
    graph.add_node("inherit_ids", inherit_ids)
    graph.add_node("prepare_patch", prepare_patch)
    graph.add_node("patch", patch)
    graph.add_node("apply", apply)
    graph.add_node("validate", validate)
    graph.add_node("persist", persist)
    graph.add_node("backoff", backoff)
    graph.add_node("fail", _fail_node)

    graph.set_entry_point("acquire")
    graph.add_conditional_edges("acquire", _route_acquire,
                                {"fail": "fail", "load": "load"})
    graph.add_conditional_edges("load", _route_load, {
        "synthesize": "synthesize",
        "fail": "fail",
        "prepare_patch": "prepare_patch",
    })
    graph.add_conditional_edges("synthesize", _route_model, {
        "retry": "backoff_synthesize",
        "fail": "fail",
        "continue": "inherit_gate",
    })
    graph.add_node("backoff_synthesize", backoff)
    graph.add_edge("backoff_synthesize", "synthesize")

    def inherit_gate(state: ArchState) -> Dict[str, Any]:
        return {}

    graph.add_node("inherit_gate", inherit_gate)
    graph.add_conditional_edges(
        "inherit_gate",
        lambda s: "inherit_ids" if state_has_previous(s) else "validate",
        {"inherit_ids": "inherit_ids", "validate": "validate"})
    graph.add_edge("inherit_ids", "validate")
    graph.add_edge("validate", "persist")
    graph.add_conditional_edges("prepare_patch", _route_prepare, {
        "done": END,
        "persist": "persist",
        "patch": "patch",
    })
    graph.add_conditional_edges("patch", _route_model, {
        "retry": "backoff_patch",
        "fail": "fail",
        "continue": "apply",
    })
    graph.add_node("backoff_patch", backoff)
    graph.add_edge("backoff_patch", "patch")
    graph.add_edge("apply", "persist")
    graph.add_edge("persist", END)
    graph.add_edge("backoff", "acquire")  # lock-busy path only; model retries use backoff_synthesize/backoff_patch
    graph.add_edge("fail", END)
    return graph.compile(checkpointer=graph_checkpointer("architecture"))


def state_has_previous(state: ArchState) -> bool:
    previous = state.get("previous") or {}
    return bool(previous.get("components"))


_COMPILED = None


def _graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def thread_id_for(project):
    return "arch-" + (architecture.slugify_id(project.rstrip("/").rsplit("/", 1)[-1]) or "project")


def revise_graph(project, model_cfg, lang="zh", full=False):
    """Run the architecture revision graph. Mirrors revision.revise()'s contract."""
    state: ArchState = {
        "project": project,
        "model_cfg": model_cfg,
        "lang": lang,
        "full": bool(full),
        "attempt": 0,
        "code": 0,
        "result": None,
        "trace": [],
    }
    final = _graph().invoke(state, config={"configurable": {"thread_id": thread_id_for(project)}})
    _release(final)
    code = final.get("code") or 200
    result = final.get("result") or {"ok": False, "error": "revision produced no result"}
    trace = final.get("trace") or []
    result["trace"] = {
        "nodes": len(trace),
        "ms": sum(item["ms"] for item in trace),
        "attempts": (final.get("attempt") or 0) + 1,
    }
    return code, result

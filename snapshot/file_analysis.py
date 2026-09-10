"""Source file architecture analysis engine.

Deeply inspects a specific source file:
1. Lines of code, size, language, technology tags
2. Layer and component placement from blueprint / LLM architecture
3. Extracted symbols (classes, functions, constants)
4. Dependency flow: direct internal imports and inward dependents
5. RAG-matched technical concepts and big-tech interview questions
6. Historical modification turns and agent change rationale
"""

import os
from typing import Any, Dict, List, Optional

from config import store as store_mod
from graph import builder as graph_builder
from knowledge.rag import retrieve_knowledge
from model_client import client as model_client
from snapshot.ast_inspect import inspect_file_capabilities
from snapshot.languages import language_for, technologies_for
from snapshot.symbols import extract_symbols, resolve_import


import time
import threading
import copy
from collections import OrderedDict

_FILE_CACHE = OrderedDict()
_FILE_CACHE_LOCK = threading.Lock()


def analyze_source_file(project_root: str, file_rel_path: str, ui_lang: str = 'zh') -> Optional[Dict[str, Any]]:
    project = os.path.abspath(project_root)
    relative = file_rel_path.strip().lstrip('/')
    path = os.path.join(project, relative)
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return None
    key = (project, relative, ui_lang)
    version = (stat.st_mtime_ns, stat.st_size)
    with _FILE_CACHE_LOCK:
        cached = _FILE_CACHE.get(key)
        if cached and cached[0] == version and time.monotonic() - cached[1] < 5:
            _FILE_CACHE.move_to_end(key)
            return copy.deepcopy(cached[2])
        result = _analyze_source_file(project, relative, ui_lang)
        if result is not None:
            _FILE_CACHE[key] = (version, time.monotonic(), copy.deepcopy(result))
            _FILE_CACHE.move_to_end(key)
            while len(_FILE_CACHE) > 32:
                _FILE_CACHE.popitem(last=False)
        return result


def _analyze_source_file(project_root: str, file_rel_path: str, ui_lang: str = 'zh') -> Optional[Dict[str, Any]]:
    abs_proj = os.path.abspath(project_root)
    clean_rel = file_rel_path.strip().lstrip("/")
    abs_file = os.path.join(abs_proj, clean_rel)

    if not os.path.isfile(abs_file):
        return None

    # 1. Basic Stats
    try:
        with open(abs_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            line_count = len(lines)
            size_bytes = os.path.getsize(abs_file)
            content_preview = "".join(lines[:35])
    except OSError:
        line_count = 0
        size_bytes = 0
        content_preview = ""

    lang = language_for(clean_rel)
    techs = technologies_for(clean_rel)

    # 2. Symbols & AST Capabilities Inspection
    symbols_data = extract_symbols(abs_proj, clean_rel)
    defs = symbols_data.get("defs", [])
    raw_imports = symbols_data.get("imports", [])
    module_doc = symbols_data.get("doc", "")

    # Deep AST capabilities inspection
    ast_info = inspect_file_capabilities(abs_proj, clean_rel)
    if not module_doc:
        module_doc = ast_info.get("module_doc", "")
    capabilities = ast_info.get("capabilities", [])

    all_fn_details = []
    for f in ast_info.get("functions", []):
        all_fn_details.append(f)
    for c in ast_info.get("classes", []):
        all_fn_details.append({
            "name": c["name"],
            "signature": f"class {c['name']}",
            "line": c["line"],
            "kind": "class",
            "purpose": c["purpose"],
            "doc": c["doc"]
        })
        for m in c.get("methods", []):
            all_fn_details.append(m)

    # Enrich symbols with detailed purpose
    fn_map = {f["name"]: f for f in all_fn_details}
    for d in defs:
        match_fn = fn_map.get(d["name"])
        if match_fn:
            d["purpose"] = match_fn.get("purpose", "")
            d["signature"] = match_fn.get("signature", d["name"])
            if not d.get("doc"):
                d["doc"] = match_fn.get("doc", "")
        else:
            d["purpose"] = d.get("doc") or f"提供 {d['name']} 功能定义"
            d["signature"] = d["name"]

    # Resolve bidirectional imports with project structure
    internal_imports = []
    for imp in raw_imports:
        resolved = resolve_import(imp, abs_proj, clean_rel)
        if resolved and resolved != clean_rel:
            internal_imports.append(resolved)

    inward_dependents = []
    try:
        struct = graph_builder.structure(abs_proj)
        for src, dst in struct.get("import_edges", []):
            if dst == clean_rel and src != clean_rel:
                inward_dependents.append(src)
            elif src == clean_rel and dst != clean_rel and dst not in internal_imports:
                internal_imports.append(dst)
        scores = struct.get("scores", {})
        inward_dependents = sorted(list(set(inward_dependents)), key=lambda p: scores.get(p, 0), reverse=True)
    except Exception:
        inward_dependents = []

    internal_imports = sorted(list(set(internal_imports)))

    # 3. Component & Layer Placement (architecture knowledge first)
    arch = store_mod.load_architecture(abs_proj)
    comp_data = arch if arch else (store_mod.load_components(abs_proj) or {})
    file_role = ""
    layer_name = "pipeline"
    component_name = "通用逻辑模块"
    component_summary = "负责当前功能领域的基础逻辑与数据交互"

    comps = comp_data.get("components", [])
    for c in comps:
        c_files = c.get("files", []) or []
        c_dirs = [d for d in (c.get("dirs", []) or []) if d]
        matched = (clean_rel in c_files
                   or (c_dirs and clean_rel.startswith(tuple(c_dirs)))
                   or any(clean_rel.endswith(cf) for cf in c_files))
        if matched:
            component_name = c.get("name", component_name)
            component_summary = c.get("summary", component_summary)
            layer_name = c.get("layer", layer_name)
            file_role = (c.get("file_roles") or {}).get(clean_rel, "")
            break

    # If architecture didn't specify file_role, fallback to capabilities, module_doc or symbol capabilities
    if not file_role:
        if capabilities:
            file_role = capabilities[0]
        elif module_doc:
            file_role = module_doc
        elif defs:
            sym_names = [d["name"] for d in defs[:3]]
            file_role = f"导出 {', '.join(sym_names)} 等核心定义"
        else:
            base_name = os.path.basename(clean_rel).lower()
            if base_name.endswith((".md", ".txt", ".rst")):
                file_role = "项目说明文档与开发约束"
            elif "test" in base_name:
                file_role = "功能单元测试与回归用例"
            else:
                file_role = f"{layer_name} 模块实现与支撑代码"

    # 4. RAG Knowledge & Interview Questions
    def_names = [d.get("name", "") for d in defs[:5]]
    rag_query = f"{clean_rel} {' '.join(def_names)} {' '.join(techs)} {component_name} {component_summary}"
    rag_hits = retrieve_knowledge(rag_query, top_k=2)

    from snapshot.guide import build_reading_guide
    reading_guide = build_reading_guide(abs_proj, clean_rel, all_fn_details or defs)
    stat = os.stat(abs_file)
    cached = model_client._FILE_DEEP_CACHE.get((abs_proj, clean_rel, ui_lang))
    deep_analysis = cached[1] if cached and cached[0] == (stat.st_mtime_ns, stat.st_size) else None

    # 6. Historical Agent Modifications
    events = store_mod.read_events(abs_proj, limit=300)
    related_turns = []
    for ev in events:
        mod_files = [f.get("path") for f in (ev.get("files") or [])]
        if clean_rel in mod_files or any(mf and clean_rel.endswith(mf) for mf in mod_files):
            d = ev.get("dialogue") or {}
            related_turns.append({
                "event_id": ev.get("event_id"),
                "occurred_at": ev.get("occurred_at"),
                "turn_id": ev.get("turn_id"),
                "agent_label": ev.get("agent_label"),
                "session_id": ev.get("session_id"),
                "user_intent": (ev.get("request_text") or ev.get("evidence_summary") or "")[:80],
                "change_scope": d.get("change_scope") or "常规代码重构与维护",
                "technical_meaning": d.get("technical_meaning") or "修改该文件以支持业务或架构调整"
            })

    return {
        "file_path": clean_rel,
        "abs_path": abs_file,
        "language": lang,
        "technologies": techs,
        "lines": line_count,
        "size_bytes": size_bytes,
        "reading_guide": reading_guide,
        "module_doc": module_doc,
        "file_role": file_role,
        "capabilities": capabilities,
        "function_details": all_fn_details,
        "layer": layer_name,
        "component": {
            "name": component_name,
            "summary": component_summary
        },
        "symbols": {
            "classes_and_functions": defs,
            "import_count": len(internal_imports),
            "internal_imports": internal_imports,
            "inward_dependents": inward_dependents
        },
        "deep_analysis": deep_analysis,
        "knowledge_interview_points": rag_hits,
        "history_modifications": related_turns[-8:]
    }

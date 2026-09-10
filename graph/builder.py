"""Deterministic graph builder: events + repo fingerprint -> nodes/edges.

Node kinds: repository/component/file/symbol/agent/session/turn/technology/
knowledge. Symbol and component layers are structural abstraction over the
file layer: symbols come from local extraction, components from the optional
LLM pass (GitDiagram idea). Edges: contains/defines/imports/observed_during/
ran/uses/explains/relates.
Model output contributes only knowledge/component nodes and explains/relates
edges, labeled as analysis; everything else is deterministic evidence.
"""

import os
import json
import subprocess
import time

from config import store as store_mod
from graph.rank import pagerank
from knowledge import architecture as arch_knowledge
from platforms.base import REGISTRY
from snapshot.ast_inspect import inspect_file_capabilities
from snapshot.languages import LANGUAGE_BY_SUFFIX, language_for, technologies_for
from snapshot.scanner import take_snapshot
from snapshot.symbols import extract_symbols, resolve_import

try:
    import platforms.claude  # noqa: F401
    import platforms.codex  # noqa: F401
    import platforms.kimi  # noqa: F401
    import platforms.stubs  # noqa: F401
except ImportError:  # pragma: no cover - adapters ship with the project
    raise


def _language_names(snapshot):
    names = set()
    for path in snapshot["files"]:
        name = path.rsplit("/", 1)[-1]
        suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        language = LANGUAGE_BY_SUFFIX.get(suffix)
        if language:
            names.add(language)
    return sorted(names)


def extract_project_headline(project):
    """Extract a concise one-line summary for the project from README, manifests or metadata."""
    # 1. Try saved components from LLM
    try:
        data = store_mod.load_components(project)
        if data and data.get("system_summary"):
            return data["system_summary"].strip()
    except Exception:
        pass

    # 2. Try README.md
    for rname in ("README.md", "README.MD", "readme.md", "README.zh-CN.md", "README"):
        rpath = os.path.join(project, rname)
        if os.path.isfile(rpath):
            try:
                with open(rpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [line.strip() for line in f.readlines()[:30] if line.strip()]
                    title = ""
                    desc = ""
                    for line in lines:
                        if line.startswith("# ") and not title:
                            title = line.lstrip("# ").strip()
                        elif line.startswith("## ") and not desc:
                            d_text = line.lstrip("# ").strip()
                            if not any(k in d_text for k in ("简介", "背景", "概述", "目标")):
                                desc = d_text
                        elif not line.startswith(("#", "-", "*", "`", "<", "!", "[")) and len(line) > 6 and not desc:
                            desc = line
                    if title and desc and desc != title:
                        return "%s: %s" % (title[:25], desc[:45])
                    if title:
                        return title[:60]
                    if desc:
                        return desc[:60]
            except Exception:
                pass

    # 3. Try package.json
    pkg_path = os.path.join(project, "package.json")
    if os.path.isfile(pkg_path):
        try:
            import json
            with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                pj = json.load(f)
                if pj.get("description"):
                    return ("%s: %s" % (pj.get("name", ""), pj.get("description")))[:60]
        except Exception:
            pass

    # 4. Try pyproject.toml
    pyproj_path = os.path.join(project, "pyproject.toml")
    if os.path.isfile(pyproj_path):
        try:
            with open(pyproj_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("description"):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if val:
                            return val[:60]
        except Exception:
            pass

    return os.path.basename(os.path.abspath(project))


def repo_info(project, snapshot=None):
    branch, head, dirty = "", "", False
    try:
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=project, capture_output=True,
                                timeout=2).stdout.decode().strip()
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=project, capture_output=True,
                              timeout=2).stdout.decode().strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"],
                                    cwd=project, capture_output=True,
                                    timeout=1.5).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    if snapshot is None:
        snapshot = take_snapshot(project)
    languages = _language_names(snapshot)
    manifests = sorted({os.path.basename(p) for p in snapshot["files"]
                        if os.path.basename(p) in (
                            "package.json", "pyproject.toml", "requirements.txt",
                            "Cargo.toml", "go.mod", "pom.xml", "build.gradle")})
    build_systems = sorted({{"package.json": "npm", "pyproject.toml": "pep517",
                             "requirements.txt": "pip", "Cargo.toml": "cargo",
                             "go.mod": "go", "pom.xml": "maven",
                             "build.gradle": "gradle"}.get(m, m) for m in manifests})
    headline = extract_project_headline(project)
    return {"branch": branch, "head": head, "dirty": dirty,
            "headline": headline,
            "languages": languages[:20], "build_systems": build_systems,
            "manifests": manifests, "file_count": len(snapshot["files"]),
            "truncated": snapshot["truncated"]}


def structure(project, snapshot=None, events=None):
    """File/symbol/import layers + PageRank, independent of rendering."""
    project = os.path.abspath(project)
    snapshot = snapshot or take_snapshot(project)
    events = events if events is not None else store_mod.read_events(project)
    files = sorted(snapshot["files"])
    symbols = {}
    docs = {}
    import_edges = []
    for rel in files:
        info = extract_symbols(project, rel)
        if info["defs"]:
            symbols[rel] = info["defs"][:40]
        if info.get("doc"):
            docs[rel] = info["doc"]
        for spec in info["imports"]:
            target = resolve_import(spec, project, rel)
            if target and target in snapshot["files"]:
                import_edges.append((rel, target))
    import_edges = sorted(set(import_edges))
    change_groups = {tuple(sorted({f.get('path') for f in event.get('files', [])
                                   if f.get('path') in snapshot['files']})) for event in events}
    change_scores = {p: 0.0 for p in files}
    for group in change_groups:
        for path in group:
            change_scores[path] += 1.0 / len(group)
    total_change = sum(change_scores.values())
    change_scores = {p: value / total_change if total_change else 1.0 / len(files)
                     for p, value in change_scores.items()}
    dependency_scores = pagerank(files, import_edges)
    scores = {p: .9 * dependency_scores[p] + .1 * change_scores[p] for p in files}
    from snapshot.selection import select_files
    ranked, _ = select_files(files, len(files), scores)
    selected, coverage = select_files(files, 600, scores)
    return {"files": files, "symbols": symbols, "docs": docs, "import_edges": import_edges,
            "scores": scores, "ranked": ranked, "analysis_files": selected,
            "analysis_selection": coverage, "snapshot_selection": snapshot.get("selection", {})}


BLUEPRINT_LAYERS = [
    {
        "id": "presentation",
        "name": "应用与交互层 (Presentation & Interface)",
        "subtitle": "Web UI / HTTP Server / SSE Stream / CLI Hooks",
        "color": "#388bfd"
    },
    {
        "id": "agent",
        "name": "智能体与核心逻辑层 (Agent & Core Engine)",
        "subtitle": "Analysis Agent / Session Memory / Prompt Engine / Knowledge Graph",
        "color": "#bc8cff"
    },
    {
        "id": "pipeline",
        "name": "会话感知与流处理层 (Perception & Pipeline)",
        "subtitle": "Multi-Agent Adapters / Session Tailer / Attribution / Event Queue",
        "color": "#39c5bb"
    },
    {
        "id": "infrastructure",
        "name": "基础快照与数据层 (Infrastructure & Data)",
        "subtitle": "Repo Snapshot / AST Symbols / Redaction / State Store",
        "color": "#d29922"
    }
]


def _infer_layer(comp_name, files):
    name_low = comp_name.lower()
    first_file = (files[0] if files else "").lower()
    combined = name_low + " " + first_file
    if any(k in combined for k in ("web", "server", "hook", "ui", "入口", "界面", "交互")):
        return "presentation"
    if any(k in combined for k in ("agent", "memory", "prompt", "graph", "model", "智能体", "分析", "记忆", "图谱")):
        return "agent"
    if any(k in combined for k in ("platform", "tailer", "session", "adapter", "会话", "适配", "监听", "流")):
        return "pipeline"
    return "infrastructure"


def _infer_file_role(path, syms, doc=""):
    if doc:
        return doc[:60]
    if syms:
        names = [s["name"] for s in syms[:3] if isinstance(s, dict) and s.get("name")]
        if names:
            return f"实现 {', '.join(names)} 核心功能"
    base = os.path.basename(path).lower()
    if base.endswith((".md", ".txt", ".rst")):
        return "说明文档与项目规范"
    if "test" in base:
        return "功能测试与验证用例"
    if base in ("package.json", "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod"):
        return "依赖清单与项目配置"
    return "基础支撑与内部实现"


def _order_blueprint_components(names, dep_map):
    """Dependency-driven stable ordering, cycle-safe via SCC condensation.

    Names are module identifiers; dep_map maps each name to its known
    in-repo dependencies (already filtered to unknown targets and
    self-references). Returns (ordered_names, order_rank) where
    order_rank maps a name to its stable position. Deterministic: ties
    break alphabetically; mutually dependent modules (cycles) condense
    into one SCC block ordered internally by name.
    """
    names = list(dict.fromkeys(names))
    name_set = set(names)
    deps = {n: sorted({d for d in (dep_map.get(n) or []) if d in name_set and d != n})
            for n in names}

    # Tarjan SCC, iterative over names sorted for determinism.
    index_of, low_of, on_stack = {}, {}, set()
    stack, sccs, counter = [], [], [0]
    for root in sorted(names):
        if root in index_of:
            continue
        work = [(root, 0)]
        while work:
            node, child_i = work[-1]
            if child_i == 0 and node not in index_of:
                index_of[node] = low_of[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            advanced = False
            children = deps.get(node, [])
            for j in range(child_i, len(children)):
                child = children[j]
                if child not in index_of:
                    work[-1] = (node, j + 1)
                    work.append((child, 0))
                    advanced = True
                    break
                elif child in on_stack:
                    low_of[node] = min(low_of[node], index_of[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low_of[parent] = min(low_of[parent], low_of[node])
            if low_of[node] == index_of[node]:
                block = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    block.append(member)
                    if member == node:
                        break
                sccs.append(sorted(block))

    # Condensation DAG: edge SCC(a) -> SCC(b) when a depends on b.
    # Rank each SCC by longest chain to an SCC with no dependencies
    # (leaf-first), so dependencies render before their dependents.
    comp_of = {}
    for i, block in enumerate(sccs):
        for n in block:
            comp_of[n] = i
    scc_deps = {i: set() for i in range(len(sccs))}
    for n in names:
        for d in deps.get(n, []):
            si, di = comp_of[n], comp_of[d]
            if si != di:
                scc_deps[si].add(di)
    scc_rank, visiting = {}, set()

    def _scc_depth(i):
        if i in scc_rank:
            return scc_rank[i]
        visiting.add(i)
        depth = 0
        for d in sorted(scc_deps.get(i, ())):
            depth = max(depth, 0 if d in visiting else _scc_depth(d) + 1)
        visiting.discard(i)
        scc_rank[i] = depth
        return depth

    for i in range(len(sccs)):
        _scc_depth(i)
    ordered = [n for _, block in sorted(enumerate(sccs),
                                        key=lambda t: (scc_rank[t[0]], t[1][0]))
               for n in block]
    return ordered, {n: i for i, n in enumerate(ordered)}


def _build_blueprint(comp_data, struct, events, project=""):
    """Build a structured layered architecture blueprint."""
    layer_map = {l["id"]: dict(l, components=[]) for l in BLUEPRINT_LAYERS}
    
    # Track file modifications in events
    file_changes = {}
    for ev in events:
        for f in ev.get("files", []):
            p = f.get("path")
            if p:
                file_changes[p] = file_changes.get(p, 0) + 1

    # Map file to component
    file_to_comp = {}
    raw_components = comp_data.get("components", []) or []
    for comp in raw_components:
        cname = comp.get("name", "?")
        for f in comp.get("files", []) or []:
            file_to_comp[f] = cname

    # Calculate component-to-component dependencies from code imports,
    # with provenance tracked per dependency target.
    comp_deps = {}
    comp_dep_sources = {}
    for src, dst in struct.get("import_edges", []):
        c_src = file_to_comp.get(src)
        c_dst = file_to_comp.get(dst)
        if c_src and c_dst and c_src != c_dst:
            comp_deps.setdefault(c_src, set()).add(c_dst)
            comp_dep_sources.setdefault(c_src, {}).setdefault(c_dst, set()).add("code")

    docs = struct.get("docs", {})
    for comp in raw_components:
        cname = comp.get("name", "?")
        cfiles = comp.get("files", []) or []
        layer_id = comp.get("layer")
        if layer_id not in layer_map:
            layer_id = _infer_layer(cname, cfiles)

        # Build file objects
        file_objs = []
        comp_mod_count = 0
        all_symbols = []
        comp_roles = comp.get("file_roles") or {}
        for p in cfiles:
            syms = struct.get("symbols", {}).get(p, [])
            doc = docs.get(p, "")
            role = comp_roles.get(p) or _infer_file_role(p, syms, doc)
            all_symbols.extend([s["name"] for s in syms[:4] if isinstance(s, dict) and s.get("name")])
            mods = file_changes.get(p, 0)
            comp_mod_count += mods

            p_inspect = inspect_file_capabilities(project or ".", p) if project else {}
            p_caps = p_inspect.get("capabilities", [])[:2]
            p_funcs = []
            for f in p_inspect.get("functions", []):
                p_funcs.append({"name": f["signature"], "purpose": f["purpose"]})
            for c in p_inspect.get("classes", []):
                for m in c.get("methods", []):
                    p_funcs.append({"name": f"{c['name']}.{m['signature']}", "purpose": m["purpose"]})

            file_objs.append({
                "path": p,
                "role": role,
                "capabilities": p_caps,
                "key_functions": p_funcs[:3],
                "languages": [language_for(p)],
                "score": round(struct.get("scores", {}).get(p, 0), 4),
                "modified_count": mods,
                "symbols": [s["name"] for s in syms[:5] if isinstance(s, dict) and s.get("name")]
            })

        entry_files = comp.get("entry_files", []) or []
        entry_files_with_roles = []
        for ef in entry_files:
            ef_syms = struct.get("symbols", {}).get(ef, [])
            ef_doc = docs.get(ef, "")
            ef_role = comp_roles.get(ef) or _infer_file_role(ef, ef_syms, ef_doc)
            ef_inspect = inspect_file_capabilities(project or ".", ef) if project else {}
            ef_caps = ef_inspect.get("capabilities", [])[:3]
            ef_funcs = []
            for f in ef_inspect.get("functions", []):
                ef_funcs.append({"name": f["signature"], "purpose": f["purpose"]})
            for c in ef_inspect.get("classes", []):
                for m in c.get("methods", []):
                    ef_funcs.append({"name": f"{c['name']}.{m['signature']}", "purpose": m["purpose"]})

            entry_files_with_roles.append({
                "path": ef,
                "role": ef_role,
                "capabilities": ef_caps,
                "key_functions": ef_funcs[:4]
            })

        explicit_raw = comp.get("depends_on") or []
        known_names = {c.get("name", "?") for c in raw_components}
        code_deps = sorted(comp_deps.get(cname, set()) & known_names)
        explicit_deps = sorted({d for d in explicit_raw
                                if d in known_names and d != cname})
        merged_deps = sorted(set(explicit_deps) | set(code_deps))
        for d in explicit_deps:
            comp_dep_sources.setdefault(cname, {}).setdefault(d, set()).add("model")
        dep_sources = {d: sorted(comp_dep_sources.get(cname, {}).get(d, {"model"}))
                       for d in merged_deps}

        features = comp.get("key_features") or all_symbols[:4]

        layer_map[layer_id]["components"].append({
            "name": cname,
            "layer": layer_id,
            "summary": comp.get("summary", ""),
            "responsibilities": comp.get("responsibilities", []),
            "entry_files": entry_files,
            "entry_files_with_roles": entry_files_with_roles,
            "file_roles": comp.get("file_roles", {}),
            "key_features": features[:4],
            "files": file_objs,
            "modified_total": comp_mod_count,
            "depends_on": merged_deps,
            "dep_sources": dep_sources,
            "revision": comp.get("revision", 0),
        })

    ordered_names, order_rank = _order_blueprint_components(
        [c.get("name", "?") for c in raw_components],
        {c.get("name", "?"): [d for d in (c.get("depends_on") or [])] +
         sorted(comp_deps.get(c.get("name", "?"), set())) for c in raw_components})
    for layer in layer_map.values():
        layer["components"].sort(
            key=lambda c: (order_rank.get(c["name"], 0), c["name"]))

    return {
        "status": comp_data.get("status", "missing"),
        "overview": comp_data.get("overview", {}),
        "onboarding": comp_data.get("onboarding", []),
        "analysis": {
            "analysis_revision": comp_data.get("analysis_revision", 0),
            "base_revision": comp_data.get("base_revision", 0),
            "updated_at": comp_data.get("updated_at", ""),
        },
        "ordered_names": ordered_names,
        "layers": [layer_map[l["id"]] for l in BLUEPRINT_LAYERS]
    }


def _fallback_components(project, struct):
    """Deterministic directory grouping when the LLM pass never ran."""
    groups = {}
    for rel in struct["ranked"]:
        top = rel.split("/", 1)[0] if "/" in rel else "(root)"
        groups.setdefault(top, []).append(rel)
    components = []
    for name, paths in sorted(groups.items())[:8]:
        if not paths:
            continue
        layer = _infer_layer(name, paths)
        components.append({
            "name": name,
            "layer": layer,
            "summary": "包含 %d 个模块文件" % len(paths),
            "entry_files": paths[:2],
            "files": paths[:12]
        })
    return {"schema_version": "components.fallback",
            "components": components, "status": "fallback"}


def load_components(project, struct=None):
    arch = store_mod.load_architecture(project)
    if arch and arch.get("components"):
        if struct is not None:
            arch_knowledge.expand_files(arch, struct)
        return arch_knowledge.to_comp_data(arch)
    try:
        import json
        path = store_mod.components_path(project)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("components"), list):
            data.setdefault("status", "analysis")
            return data
    except (OSError, ValueError):
        pass
    if struct is None:
        return {"components": [], "status": "missing"}
    return _fallback_components(project, struct)


MAP_CACHE = {}


def build_map(project, dropped=0, top_n=60):
    project = os.path.abspath(project)
    events = store_mod.read_events(project)

    now = time.time()
    import hashlib
    event_version = hashlib.blake2b(json.dumps(events, sort_keys=True, ensure_ascii=False).encode(), digest_size=16).hexdigest()
    cache_key = (project, event_version, top_n)
    if cache_key in MAP_CACHE:
        cached_time, cached_res = MAP_CACHE[cache_key]
        if now - cached_time < 30.0:
            res = dict(cached_res)
            res["dropped_packets"] = dropped
            return res

    for old_key in list(MAP_CACHE):
        if old_key[0] == project:
            MAP_CACHE.pop(old_key, None)
    snap = take_snapshot(project)
    struct = structure(project, snapshot=snap, events=events)
    nodes = [{"id": "repo", "kind": "repository", "label": os.path.basename(project)}]
    edges = []
    shown = set(struct["ranked"][:top_n])
    for event in events:
        for item in event.get("files", []):
            shown.add(item.get("path"))
    comp_data = load_components(project, struct)
    comp_of = {}
    comp_origin = "analysis" if comp_data.get("status") == "analysis" else "evidence"
    for comp in comp_data.get("components", []):
        cid = "component:%s" % comp.get("name", "?")
        nodes.append({"id": cid, "kind": "component",
                      "label": comp.get("name", "?"),
                      "summary": comp.get("summary", ""), "origin": comp_origin})
        edges.append({"source": "repo", "target": cid, "kind": "contains",
                      "origin": comp_origin})
        for path in comp.get("files", []) or []:
            comp_of[path] = cid
    agents, sessions, turns, files, techs, knows = {}, {}, {}, {}, {}, {}
    for rel in struct["ranked"]:
        if rel not in shown:
            continue
        if rel not in files:
            files[rel] = "file:%s" % rel
            nodes.append({"id": files[rel], "kind": "file", "label": rel,
                          "score": round(struct["scores"].get(rel, 0), 5),
                          "languages": [language_for(rel)]})
            parent = comp_of.get(rel, "repo")
            if parent != "repo" and parent not in [n["id"] for n in nodes]:
                continue
            edges.append({"source": parent, "target": files[rel], "kind": "contains"})
            for sym in struct["symbols"].get(rel, [])[:12]:
                sid = "symbol:%s#%s" % (rel, sym["name"])
                nodes.append({"id": sid, "kind": "symbol",
                              "label": "%s (%s:%d)" % (sym["name"], rel, sym["line"])})
                edges.append({"source": files[rel], "target": sid, "kind": "defines"})
            for tech in technologies_for(rel):
                if tech not in techs:
                    techs[tech] = "tech:%s" % tech
                    nodes.append({"id": techs[tech], "kind": "technology",
                                  "label": tech})
                edges.append({"source": files[rel], "target": techs[tech],
                              "kind": "uses"})
    for src, dst in struct["import_edges"]:
        if src in files and dst in files:
            edges.append({"source": files[src], "target": files[dst], "kind": "imports"})
    for event in events:
        agent = event.get("agent_id", "?")
        if agent not in agents:
            agents[agent] = "agent:%s" % agent
            nodes.append({"id": agents[agent], "kind": "agent",
                          "label": event.get("agent_label", agent)})
            edges.append({"source": "repo", "target": agents[agent], "kind": "ran"})
        session = event.get("session_id", "?")
        if session not in sessions:
            sessions[session] = "session:%s" % session
            nodes.append({"id": sessions[session], "kind": "session",
                          "label": session[:12]})
            edges.append({"source": agents[agent], "target": sessions[session],
                          "kind": "contains"})
        turn = event.get("event_id", "?")
        if turn not in turns:
            turns[turn] = "turn:%s" % turn
            dialogue = event.get("dialogue") or {}
            label = (dialogue.get("technical_meaning") or dialogue.get("summary") or event.get("request_text") or turn)[:60]
            nodes.append({"id": turns[turn], "kind": "turn",
                          "label": label,
                          "dialogue_act": dialogue.get("dialogue_act", ""),
                          "involves_change": dialogue.get("involves_change"),
                          "user_level": dialogue.get("user_level", ""),
                          "status": event.get("status"),
                          "analysis_status": event.get("analysis_status", "evidence_only")})
            edges.append({"source": sessions[session], "target": turns[turn],
                          "kind": "contains"})
        for item in event.get("files", []):
            path = item.get("path", "?")
            if path not in files:
                files[path] = "file:%s" % path
                nodes.append({"id": files[path], "kind": "file", "label": path,
                              "languages": item.get("languages", [])})
                parent = comp_of.get(path, "repo")
                if parent == "repo" or parent in [n["id"] for n in nodes]:
                    edges.append({"source": parent, "target": files[path],
                                  "kind": "contains"})
            if path in files:
                edges.append({"source": turns[turn], "target": files[path],
                              "kind": "observed_during"})
        source = event.get("dialogue") or event.get("analysis") or {}
        items_by_pt = {it.get("point"): it for it in source.get("knowledge_items", []) if isinstance(it, dict)}
        for point in source.get("knowledge_points", []) or []:
            if point not in knows:
                knows[point] = "knowledge:%s" % point
                kitem = items_by_pt.get(point, {})
                nodes.append({
                    "id": knows[point],
                    "kind": "knowledge",
                    "label": point,
                    "origin": "analysis",
                    "definition": kitem.get("definition", ""),
                    "project_relevance": kitem.get("project_relevance", "")
                })
            edges.append({"source": turns[turn], "target": knows[point],
                          "kind": "explains", "origin": "analysis"})
        for span in source.get("knowledge_spans", []) or []:
            pt, sp = span.get("point"), span.get("path")
            if pt in knows and sp in files:
                edges.append({"source": files[sp], "target": knows[pt],
                              "kind": "embodies", "origin": "analysis"})
        for rel in source.get("relationships", []) or []:
            src, tgt = "file:%s" % rel.get("source"), "file:%s" % rel.get("target")
            if src in files.values() and tgt in files.values():
                edges.append({"source": src, "target": tgt,
                              "kind": rel.get("kind", "relates"),
                              "label": rel.get("label", ""), "origin": "analysis"})
    providers = [{"agent_id": name,
                  "agent_label": entry["adapter"].agent_label,
                  "implemented": entry["implemented"]}
                 for name, entry in REGISTRY.items()]
    kinds = {}
    for node in nodes:
        kinds[node["kind"]] = kinds.get(node["kind"], 0) + 1
    from graph.navigation import build_navigation
    result = {
        'file_tree': build_navigation(struct, comp_data),
        "repository": repo_info(project, snapshot=snap), "events": events,
        "nodes": nodes, "edges": edges,
        "blueprint": _build_blueprint(comp_data, struct, events, project=project),
        "structure": {"ranked": struct["ranked"][:top_n],
                      "analysis_selection": struct["analysis_selection"],
                      "snapshot_selection": struct["snapshot_selection"],
                      "total_files": len(struct["files"]),
                      "shown_files": len([n for n in nodes if n["kind"] == "file"]),
                      "components": comp_data.get("status", "missing")},
        "evidence_providers": providers, "dropped_packets": dropped
    }
    MAP_CACHE[cache_key] = (now, result)
    return result

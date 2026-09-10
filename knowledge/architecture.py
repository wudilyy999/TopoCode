"""Persistent per-project architecture knowledge.

Stored under the data dir (never inside a watched project). The analysis
agent performs one full synthesis and then incremental revisions per change
event, rewriting only the affected components.

Dir-prefix expansion (component declares "dirs") keeps large repositories
fully covered without asking the model to enumerate every file: snapshot
files under a declared prefix are pulled in, capped per component by
PageRank importance.
"""

from config import store as store_mod

LAYER_IDS = ("presentation", "agent", "pipeline", "infrastructure")
MAX_COMPONENTS = 10
MAX_FILES_PER_COMP = 200


def load_architecture(project):
    return store_mod.load_architecture(project)


def save_architecture(project, arch):
    return store_mod.save_architecture(project, arch)


def expand_files(arch, struct):
    """Resolve each component's effective file set against the snapshot."""
    comps = arch.get("components") or []
    known = set(struct["files"])
    scores = struct.get("scores", {})
    for comp in comps:
        comp["files"] = [p for p in comp.get("files", []) if p in known]
    dir_hints = [(d, i) for i, comp in enumerate(comps)
                 for d in (comp.get("dirs") or []) if d and d != "/"]
    if dir_hints:
        buckets = [[] for _ in comps]
        for rel in struct["ranked"]:
            for d, i in dir_hints:
                if rel.startswith(d):
                    buckets[i].append(rel)
                    break
        for i, rels in enumerate(buckets):
            rels.sort(key=lambda p: scores.get(p, 0), reverse=True)
            merged = set(comps[i]["files"])
            for rel in rels:
                if len(comps[i]["files"]) >= MAX_FILES_PER_COMP:
                    break
                if rel not in merged:
                    comps[i]["files"].append(rel)
                    merged.add(rel)
    for comp in comps:
        comp["entry_files"] = [p for p in (comp.get("entry_files") or [])
                               if p in known][:5]
    return arch


def to_comp_data(arch):
    return {
        "schema_version": "architecture.v2",
        "status": "analysis",
        "overview": arch.get("overview") or {},
        "onboarding": arch.get("onboarding") or [],
        "analysis_revision": arch.get("analysis_revision", 0),
        "base_revision": arch.get("base_revision", 0),
        "updated_at": arch.get("updated_at", ""),
        "components": arch.get("components") or [],
    }


def _clean_file_roles(raw, valid_paths):
    roles = {}
    for item in (raw or [])[:20]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        role = str(item.get("role", "")).strip()[:40]
        if path in valid_paths and role:
            roles[path] = role
    return roles


def _clean_component(raw, valid_paths, revision):
    name = str(raw.get("name", "")).strip()[:40]
    if not name:
        return None
    layer = str(raw.get("layer", "")).strip()
    if layer not in LAYER_IDS:
        layer = "infrastructure"
    return {
        "name": name,
        "layer": layer,
        "layer_title": str(raw.get("layer_title", "")).strip()[:30] or "核心模块",
        "summary": str(raw.get("summary", "")).strip()[:100],
        "responsibilities": [str(r).strip()[:40] for r in (raw.get("responsibilities") or [])
                             if str(r).strip()][:4],
        "key_features": [str(f).strip()[:40] for f in (raw.get("key_features") or [])
                         if str(f).strip()][:6],
        "entry_files": [p for p in (raw.get("entry_files") or []) if p in valid_paths][:5],
        "dirs": [d for d in (raw.get("dirs") or []) if d][:6],
        "files": [p for p in (raw.get("files") or []) if p in valid_paths][:MAX_FILES_PER_COMP],
        "file_roles": _clean_file_roles(raw.get("file_roles"), valid_paths),
        "depends_on": [str(d).strip()[:40] for d in (raw.get("depends_on") or [])
                       if str(d).strip()][:6],
        "revision": revision,
    }


def apply_update(arch, patch, valid_paths, revision):
    """Merge an architecture.update.v1 patch into the stored knowledge."""
    if not isinstance(patch, dict):
        return arch
    ov_patch = patch.get("overview_patch")
    if isinstance(ov_patch, dict):
        overview = arch.setdefault("overview", {})
        limits = {"one_liner": 60, "purpose": 150, "architecture_style": 60}
        for key, cap in limits.items():
            value = str(ov_patch.get(key, "")).strip()
            if value:
                overview[key] = value[:cap]

    by_name = {c["name"]: c for c in arch.setdefault("components", [])}
    for upd in patch.get("updates", []) or []:
        if not isinstance(upd, dict):
            continue
        comp = by_name.get(str(upd.get("name", "")).strip()[:40])
        if comp is None:
            continue
        summary = str(upd.get("summary", "")).strip()
        if summary:
            comp["summary"] = summary[:100]
        resp = [str(r).strip()[:40] for r in (upd.get("responsibilities") or [])
                if str(r).strip()]
        if resp:
            comp["responsibilities"] = resp[:4]
        deps = [str(d).strip()[:40] for d in (upd.get("depends_on") or [])
                if str(d).strip()]
        if deps:
            comp["depends_on"] = deps[:6]
        add = [p for p in (upd.get("add_files") or []) if p in valid_paths]
        remove = set(upd.get("remove_files") or [])
        if add or remove:
            kept = [p for p in comp.get("files", []) if p not in remove]
            for p in add:
                if p not in kept:
                    kept.append(p)
            comp["files"] = kept[:MAX_FILES_PER_COMP]
        roles = _clean_file_roles(upd.get("file_roles"), valid_paths)
        if roles:
            comp_roles = comp.setdefault("file_roles", {})
            for path in remove:
                comp_roles.pop(path, None)
            comp_roles.update(roles)
            comp["file_roles"] = {p: r for p, r in comp_roles.items()
                                  if p in comp["files"]}
        comp["revision"] = revision

    for raw in (patch.get("creates") or [])[:2]:
        if not isinstance(raw, dict):
            continue
        comp = _clean_component(raw, valid_paths, revision)
        if comp is None or comp["name"] in by_name:
            continue
        arch["components"].append(comp)
        by_name[comp["name"]] = comp

    for item in (patch.get("reassign") or [])[:50]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        target = str(item.get("component", "")).strip()[:40]
        if path not in valid_paths or target not in by_name:
            continue
        moved_role = None
        for comp in arch["components"]:
            if path in comp.get("files", []):
                comp["files"].remove(path)
                moved_role = (comp.get("file_roles") or {}).pop(path, None)
        dest = by_name[target]
        if path not in dest["files"]:
            dest["files"].append(path)
        dest["files"] = dest["files"][:MAX_FILES_PER_COMP]
        if moved_role:
            dest.setdefault("file_roles", {})[path] = moved_role
        dest["revision"] = revision

    arch["components"] = arch["components"][:MAX_COMPONENTS]
    arch["analysis_revision"] = revision
    return arch

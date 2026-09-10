"""Persistent per-project architecture knowledge.

Stored under the data dir (never inside a watched project). The analysis
agent performs one full synthesis and then incremental revisions per change
event, rewriting only the affected components.

Dir-prefix expansion (component declares "dirs") keeps large repositories
fully covered without asking the model to enumerate every file: snapshot
files under a declared prefix are pulled in, capped per component by
PageRank importance.

Component identity is `id` (kebab-case). `name` is a mutable display label.
"""

import re
import unicodedata

from config import store as store_mod

LAYER_IDS = ("presentation", "agent", "pipeline", "infrastructure")
MAX_COMPONENTS = 10
MAX_FILES_PER_COMP = 200
STORED_SCHEMA = "architecture.v3"
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
PRESERVE_OVERLAP = 0.5


def slugify_id(text):
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.replace("_", "-").replace("/", "-").replace(".", "-")
    text = re.sub(r"[^A-Za-z0-9-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()
    text = re.sub(r"^[^a-z]+", "", text)
    return text[:40].rstrip("-")


def unique_id(base, taken):
    base = slugify_id(base) or "component"
    candidate = base
    n = 2
    while candidate in taken:
        suffix = "-%d" % n
        candidate = (base[:40 - len(suffix)] + suffix).rstrip("-")
        n += 1
    return candidate


def id_seed(raw):
    proposed = slugify_id(raw.get("id", ""))
    if proposed:
        return proposed
    from_name = slugify_id(raw.get("name", ""))
    if from_name:
        return from_name
    for prefix in raw.get("dirs") or []:
        stem = slugify_id(str(prefix).strip("/").split("/")[0])
        if stem:
            return stem
    for path in list(raw.get("entry_files") or []) + list(raw.get("files") or []):
        rel = str(path).strip()
        stem = slugify_id(rel.split("/", 1)[0] if "/" in rel else rel.rsplit(".", 1)[0])
        if stem:
            return stem
    return "component"


def component_id(comp):
    cid = slugify_id((comp or {}).get("id", ""))
    if cid:
        return cid
    return slugify_id((comp or {}).get("name", "")) or "component"


def _indexes(components):
    by_id = {c["id"]: c for c in components if c.get("id")}
    by_name = {c["name"]: c for c in components if c.get("name")}
    return by_id, by_name


def resolve_ref(ref, by_id, by_name):
    key = str(ref or "").strip()[:40]
    if not key:
        return None
    return by_id.get(key) or by_name.get(key)


def ensure_component_ids(components):
    taken = set()
    for comp in components:
        cid = slugify_id(comp.get("id", ""))
        if ID_RE.match(cid) and cid not in taken:
            comp["id"] = cid
            taken.add(cid)
        else:
            comp["id"] = ""
    for comp in components:
        if comp["id"]:
            continue
        cid = unique_id(id_seed(comp), taken)
        comp["id"] = cid
        taken.add(cid)
    return components


def _resolve_depends(comp, by_id, by_name):
    refs, seen = [], set()
    self_id = comp.get("id")
    for raw in comp.get("depends_on") or []:
        target = resolve_ref(raw, by_id, by_name)
        if target is None:
            continue
        tid = target["id"]
        if tid == self_id or tid in seen:
            continue
        seen.add(tid)
        refs.append(tid)
        if len(refs) >= 6:
            break
    comp["depends_on"] = refs
    return comp


def normalize_architecture(arch):
    if not isinstance(arch, dict):
        return arch
    comps = list(arch.get("components") or [])
    ensure_component_ids(comps)
    by_id, by_name = _indexes(comps)
    for comp in comps:
        _resolve_depends(comp, by_id, by_name)
    arch["components"] = comps[:MAX_COMPONENTS]
    arch["schema_version"] = STORED_SCHEMA
    return arch


def preserve_ids(old_arch, new_arch):
    """Reuse stable ids when a regenerated component still owns the same files."""
    old_comps = list((old_arch or {}).get("components") or [])
    new_comps = list((new_arch or {}).get("components") or [])
    if not old_comps or not new_comps:
        return new_arch
    pairs = []
    for i, new in enumerate(new_comps):
        new_files = set(new.get("files") or [])
        for old in old_comps:
            oid = old.get("id") or ""
            if not oid:
                continue
            old_files = set(old.get("files") or [])
            if new_files and old_files:
                score = len(new_files & old_files) / len(new_files | old_files)
            elif new.get("name") == old.get("name"):
                score = 1.0
            elif (new.get("dirs") or []) and (new.get("dirs") or []) == (old.get("dirs") or []):
                score = 0.6
            else:
                score = 0.0
            pairs.append((-score, new.get("name") or "", i, oid))
    pairs.sort()
    used_old, used_new = set(), set()
    for neg_score, _, i, oid in pairs:
        if -neg_score < PRESERVE_OVERLAP or i in used_new or oid in used_old:
            continue
        new_comps[i]["id"] = oid
        used_old.add(oid)
        used_new.add(i)
    old_by_name = {c.get("name"): c for c in old_comps
                   if c.get("id") and c["id"] not in used_old}
    for i, new in enumerate(new_comps):
        if i in used_new:
            continue
        old = old_by_name.get(new.get("name"))
        if old:
            new["id"] = old["id"]
            used_old.add(old["id"])
            used_new.add(i)
        else:
            new["id"] = ""
    return new_arch


def load_architecture(project):
    arch = store_mod.load_architecture(project)
    if arch:
        normalize_architecture(arch)
    return arch


def save_architecture(project, arch):
    return store_mod.save_architecture(project, normalize_architecture(arch))


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
        "schema_version": STORED_SCHEMA,
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


def _clean_component(raw, valid_paths, revision, taken):
    name = str(raw.get("name", "")).strip()[:40]
    if not name:
        return None
    layer = str(raw.get("layer", "")).strip()
    if layer not in LAYER_IDS:
        layer = "infrastructure"
    cid = unique_id(id_seed(raw), taken)
    taken.add(cid)
    return {
        "id": cid,
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

    comps = arch.setdefault("components", [])
    ensure_component_ids(comps)
    by_id, by_name = _indexes(comps)
    taken = set(by_id)

    for upd in patch.get("updates", []) or []:
        if not isinstance(upd, dict):
            continue
        comp = resolve_ref(upd.get("id") or upd.get("name"), by_id, by_name)
        if comp is None:
            continue
        new_name = str(upd.get("name", "")).strip()[:40]
        if new_name and new_name != comp["name"]:
            other = by_name.get(new_name)
            if other is None or other is comp:
                by_name.pop(comp["name"], None)
                comp["name"] = new_name
                by_name[new_name] = comp
        summary = str(upd.get("summary", "")).strip()
        if summary:
            comp["summary"] = summary[:100]
        resp = [str(r).strip()[:40] for r in (upd.get("responsibilities") or [])
                if str(r).strip()]
        if resp:
            comp["responsibilities"] = resp[:4]
        if "depends_on" in upd:
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
        existing = resolve_ref(raw.get("id") or raw.get("name"), by_id, by_name)
        if existing is not None:
            continue
        comp = _clean_component(raw, valid_paths, revision, taken)
        if comp is None:
            continue
        if comp["name"] in by_name:
            taken.discard(comp["id"])
            continue
        comps.append(comp)
        by_id[comp["id"]] = comp
        by_name[comp["name"]] = comp

    for item in (patch.get("reassign") or [])[:50]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        dest = resolve_ref(item.get("component") or item.get("id"), by_id, by_name)
        if path not in valid_paths or dest is None:
            continue
        moved_role = None
        for comp in comps:
            if path in comp.get("files", []):
                comp["files"].remove(path)
                moved_role = (comp.get("file_roles") or {}).pop(path, None)
        if path not in dest["files"]:
            dest["files"].append(path)
        dest["files"] = dest["files"][:MAX_FILES_PER_COMP]
        if moved_role:
            dest.setdefault("file_roles", {})[path] = moved_role
        dest["revision"] = revision

    arch["components"] = comps[:MAX_COMPONENTS]
    normalize_architecture(arch)
    arch["analysis_revision"] = revision
    return arch

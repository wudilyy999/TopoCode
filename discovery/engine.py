"""Project Auto-Discovery Engine.
Actively sniffs local Agent sessions (Kimi, Claude, Codex, etc.), extracts referenced
project working directories and changed file roots, and presents candidates to the user.
"""

import os
import time
from typing import Any, Dict, List, Optional, Set

PROJECT_INDICATORS = {
    ".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "requirements.txt", "setup.py", "Makefile"
}

# Directories that should not be treated as a single isolated project
STOP_DIRS = {
    os.path.abspath(os.path.expanduser("~")),
    os.path.abspath(os.path.expanduser("~/Downloads")),
    os.path.abspath(os.path.expanduser("~/Desktop")),
    os.path.abspath(os.path.expanduser("~/Documents")),
    "/", "/tmp", "/private/tmp", "/var", "/private/var"
}

# Directories belonging to internal agent configs or temp testing that should never be presented as projects
INTERNAL_EXCLUDED_PREFIXES = (
    os.path.abspath(os.path.expanduser("~/.kimi-code")),
    os.path.abspath(os.path.expanduser("~/.claude")),
    os.path.abspath(os.path.expanduser("~/.codex")),
    os.path.abspath(os.path.expanduser("~/.topocode")),
    os.path.abspath(os.path.expanduser("~/.vibe-learning")),
    os.path.abspath(os.path.expanduser("~/.grok")),
    "/private/var",
    "/var/folders",
)


def _is_internal(path: str) -> bool:
    norm = os.path.abspath(path)
    if os.path.basename(norm).startswith("."):
        return True
    return any(norm == prefix or norm.startswith(prefix + os.sep) for prefix in INTERNAL_EXCLUDED_PREFIXES)


def detect_project_root(path: Optional[str], boundary: Optional[str] = None) -> Optional[str]:
    """Given a file or directory path, walk upwards to locate the project root."""
    if not path or not isinstance(path, str):
        return None
    abs_path = os.path.abspath(os.path.expanduser(path.strip()))
    if _is_internal(abs_path):
        return None
    if not os.path.exists(abs_path):
        # Try parent
        parent = os.path.dirname(abs_path)
        if os.path.isdir(parent):
            abs_path = parent
        else:
            return None

    if not os.path.isdir(abs_path):
        abs_path = os.path.dirname(abs_path)

    cur = abs_path
    git_root = None
    indicator_root = None

    boundary = os.path.realpath(boundary) if boundary else None
    while cur and cur != os.path.dirname(cur):
        if boundary and not (cur == boundary or cur.startswith(boundary + os.sep)):
            break
        if cur in STOP_DIRS:
            break
        if os.path.basename(cur).startswith("."):
            cur = os.path.dirname(cur)
            continue
        if os.path.exists(os.path.join(cur, ".git")):
            git_root = cur  # Keep climbing to see if there is an outer git root, or record this
        elif any(os.path.exists(os.path.join(cur, ind)) for ind in PROJECT_INDICATORS):
            if not indicator_root:
                indicator_root = cur
        cur = os.path.dirname(cur)

    if git_root:
        return git_root
    if indicator_root:
        return indicator_root

    # Downloads heuristic: if inside ~/Downloads/my-project, return the top project directory
    downloads = os.path.abspath(os.path.expanduser("~/Downloads"))
    if abs_path.startswith(downloads + os.sep) and abs_path != downloads:
        rel = os.path.relpath(abs_path, downloads)
        top = rel.split(os.sep)[0]
        cand = os.path.join(downloads, top)
        if os.path.isdir(cand):
            return cand

    return abs_path if abs_path not in STOP_DIRS else None


class ProjectDiscoveryEngine:
    """Discovers projects touched by any local Agent sessions."""

    def __init__(self, registry: Dict[str, Any]):
        self.registry = registry
        self._cached_results: List[Dict[str, Any]] = []
        self._last_scan_time: float = 0.0
        self._cache_ttl_seconds: float = 60.0

    def scan_discovered_projects(
        self,
        tracked_projects: List[str],
        ignored_projects: Optional[List[str]] = None,
        max_sessions_per_adapter: int = 50,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Inspect recent sessions across all registered adapters to find project roots."""
        from config.store import load_config
        config = load_config()
        scope = config.get('discovery_scope')
        roots = [os.path.realpath(scope)] if scope else [os.path.realpath(p) for p in tracked_projects]
        scope_key = tuple(sorted(roots))
        if getattr(self, '_scope_key', None) != scope_key:
            self._cached_results = []
            self._last_scan_time = 0
            self._scope_key = scope_key
        if not roots:
            return []
        ignored_set = set(os.path.abspath(p) for p in (ignored_projects or []))
        tracked_set = set(os.path.abspath(p) for p in tracked_projects)

        now = time.time()
        # Fast-path: return cached discovery results if within TTL
        if not force_refresh and self._cached_results and (now - self._last_scan_time < self._cache_ttl_seconds):
            results = []
            for item in self._cached_results:
                clone = dict(item)
                p = clone["path"]
                clone["is_tracked"] = p in tracked_set
                clone["is_ignored"] = p in ignored_set
                results.append(clone)
            return results

        candidates: Dict[str, Dict[str, Any]] = {}

        for name, entry in self.registry.items():
            if not entry.get("implemented"):
                continue
            adapter = entry["adapter"]
            discover_fn = getattr(adapter, "discover_all_sessions", adapter.discover_sessions)
            try:
                session_refs = discover_fn()
            except Exception:
                continue

            # Check most recent sessions
            try:
                session_refs = sorted(session_refs, key=lambda p: os.path.getmtime(p), reverse=True)
            except OSError:
                pass

            for sref in session_refs[:max_sessions_per_adapter]:
                try:
                    rounds = adapter.read_session(sref)
                except Exception:
                    continue

                for r in rounds:
                    roots_to_check = {}
                    cwd = r.get('cwd') or ''
                    changed_paths = list((r.get('files') or {}).keys())
                    paths = changed_paths or ([cwd] if cwd else [])
                    for path in paths:
                        full = os.path.realpath(path if os.path.isabs(path) else os.path.join(cwd, path))
                        for boundary in roots:
                            if full != boundary and not full.startswith(boundary + os.sep):
                                continue
                            detected = detect_project_root(full, boundary=boundary)
                            if detected and (detected == boundary or detected.startswith(boundary + os.sep)):
                                confidence = 'modified_file' if changed_paths else 'cwd_only'
                                roots_to_check[detected] = confidence
                            elif not changed_paths:
                                roots_to_check[boundary] = 'cwd_only'

                    for root, evidence in roots_to_check.items():
                        if not os.path.isdir(root):
                            continue
                        norm_root = os.path.abspath(root)
                        if os.path.basename(norm_root).startswith("."):
                            continue

                        if norm_root not in candidates:
                            candidates[norm_root] = {
                                "path": norm_root,
                                "name": os.path.basename(norm_root),
                                "agents": set(),
                                "agent_labels": set(),
                                "turn_count": 0,
                                "last_active": r.get("occurred_at") or "",
                                "evidence": evidence,
                                "example_files": [],
                                "is_tracked": norm_root in tracked_set,
                                "is_ignored": norm_root in ignored_set,
                            }

                        cand = candidates[norm_root]
                        cand["agents"].add(adapter.agent_id)
                        cand["agent_labels"].add(adapter.agent_label)
                        cand["turn_count"] += 1
                        if evidence == 'modified_file':
                            cand["evidence"] = evidence
                        for changed_path in changed_paths[:5]:
                            full_changed = os.path.realpath(changed_path if os.path.isabs(changed_path) else os.path.join(cwd, changed_path))
                            if full_changed == norm_root or full_changed.startswith(norm_root + os.sep):
                                rel_changed = os.path.relpath(full_changed, norm_root)
                                if rel_changed not in cand["example_files"]:
                                    cand["example_files"].append(rel_changed)
                        occ = r.get("occurred_at") or ""
                        if occ and occ > cand["last_active"]:
                            cand["last_active"] = occ

        # Format output
        results = []
        for path, info in candidates.items():
            info["agents"] = sorted(info["agents"])
            info["agent_labels"] = sorted(info["agent_labels"])
            results.append(info)

        # Sort: untracked & not ignored first, then by last_active descending
        def sort_key(item):
            status_priority = 0 if (not item["is_tracked"] and not item["is_ignored"]) else (1 if item["is_tracked"] else 2)
            return (status_priority, item["last_active"] or "")

        results.sort(key=sort_key, reverse=False)
        # For untracked ones, sort by activity newest first
        untracked = [r for r in results if not r["is_tracked"] and not r["is_ignored"]]
        untracked.sort(key=lambda x: x["last_active"], reverse=True)
        tracked = [r for r in results if r["is_tracked"]]
        tracked.sort(key=lambda x: x["last_active"], reverse=True)
        ignored = [r for r in results if r["is_ignored"]]

        final_results = untracked + tracked + ignored
        self._cached_results = final_results
        self._last_scan_time = time.time()
        return final_results

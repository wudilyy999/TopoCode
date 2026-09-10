"""Bounded read-only snapshot of a project directory.

Prefers `git ls-files --cached --others --exclude-standard`; falls back to
a directory walk that skips well-known generated/dependency directories.
Never writes to the observed directory. Only paths + digests + line counts
leave this module; file text is used transiently for counting and digesting.
"""

import hashlib
import os
import subprocess

MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_FILES = 8000

SKIP_DIRS = frozenset({
    ".git", "node_modules", "dist", "build", "__pycache__", ".venv",
    "venv", ".tox", ".mypy_cache", ".pytest_cache", "target", "out",
    ".next", ".nuxt", "coverage", ".idea", ".vscode",
})


def _git_files(root):
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def _walk_files(root):
    collected = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            collected.append(rel)
    return collected


def _digest_file(full_path):
    digest = hashlib.blake2b(digest_size=16)
    size = 0
    lines = 0
    truncated = False
    try:
        with open(full_path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size <= MAX_FILE_BYTES:
                    digest.update(chunk)
                    lines += chunk.count(b"\n")
                else:
                    truncated = True
    except OSError:
        return None
    return {
        "digest": digest.hexdigest(),
        "size": size,
        "lines": lines,
        "truncated": truncated or size > MAX_FILE_BYTES,
    }


_DIGEST_CACHE = {}  # root -> {rel: (stat_sig, info)}


def take_snapshot(root):
    """Return {root, files: {relpath: {digest,size,lines,truncated}}, truncated}.

    Digests are pooled per project and reused while (mtime_ns, size) is
    unchanged, so steady-state rebuilds only re-read modified files.
    """
    root = os.path.abspath(root)
    rels = _git_files(root)
    if rels is None:
        rels = _walk_files(root)
    from snapshot.selection import select_files
    selected, selection = select_files(rels, MAX_FILES)
    pool = _DIGEST_CACHE.setdefault(root, {})
    files = {}
    total = 0
    for rel in selected:
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        sig = None
        try:
            st = os.stat(full)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            continue
        cached = pool.get(rel)
        if cached and cached[0] == sig:
            info = cached[1]
        else:
            info = _digest_file(full)
            if info is None:
                continue
            pool[rel] = (sig, info)
        total += min(info["size"], MAX_FILE_BYTES)
        if total > MAX_TOTAL_BYTES:
            info = {"digest": info["digest"], "size": info["size"],
                    "lines": info["lines"], "truncated": True}
        files[rel] = info
    return {"root": root, "files": files, "truncated": bool(selection['omitted']), "selection": selection}


def diff_snapshots(before, after):
    """Return list of {path, status, additions, deletions} using line counts.

    Without stored text this is a heuristic: added lines for new files equal
    their line count, removed lines for deleted files equal their old count,
    and modified files report the absolute line delta symmetrically.
    """
    events = []
    old = before.get("files", {})
    new = after.get("files", {})
    for path in sorted(set(old) | set(new)):
        prev = old.get(path)
        curr = new.get(path)
        if prev is None:
            events.append({"path": path, "status": "added",
                           "additions": curr["lines"], "deletions": 0})
        elif curr is None:
            events.append({"path": path, "status": "deleted",
                           "additions": 0, "deletions": prev["lines"]})
        elif prev["digest"] != curr["digest"]:
            delta = curr["lines"] - prev["lines"]
            events.append({"path": path, "status": "modified",
                           "additions": max(delta, 0), "deletions": max(-delta, 0)})
    return events

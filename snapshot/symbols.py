"""Lightweight symbol extraction (Aider RepoMap idea, zero dependencies).

Per file: definitions (def/class/interface/function/const arrow) and
import edges (import x from / require() / from x import). Only names and
line numbers leave this module; no source text is retained.
"""

import os
import re

MAX_SYMBOLS_PER_FILE = 200
MAX_IMPORTS_PER_FILE = 100

_DEF_PATTERNS = (
    re.compile(r"^\s*(?:export\s+|async\s+)*(?:def|class)\s+([A-Za-z_][\w]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_][\w]*)"),
    re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
)

_IMPORT_PATTERNS = (
    re.compile(r"^\s*import\s+(?:[^'\"]*from\s+)?['\"]([^'\"]+)['\"]"),
    re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+"),
    re.compile(r"#include\s+[<\"]([^>\"]+)[>\"]"),
)

_SYMBOL_SUFFIXES = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".c", ".h", ".cc", ".cpp", ".hpp",
    ".cs", ".swift", ".scala",
})


def _suffix(path):
    name = path.rsplit("/", 1)[-1]
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _extract_module_doc(lines):
    doc_lines = []
    in_doc = False
    quote_char = None
    for line in lines[:30]:
        s = line.strip()
        if not in_doc:
            if not s:
                continue
            if s.startswith('"""') or s.startswith("'''"):
                quote_char = s[:3]
                rest = s[3:]
                if rest.endswith(quote_char) and len(rest) >= 3:
                    return rest[:-3].strip()[:160]
                doc_lines.append(rest)
                in_doc = True
            elif s.startswith("/*"):
                rest = s[2:]
                if rest.endswith("*/"):
                    return rest[:-2].strip()[:160]
                doc_lines.append(rest)
                in_doc = True
            elif s.startswith("#") and not s.startswith("#!"):
                doc_lines.append(s.lstrip("# "))
                in_doc = "comment"
            elif s.startswith("//"):
                doc_lines.append(s.lstrip("/ "))
                in_doc = "comment"
            else:
                break
        else:
            if in_doc == "comment":
                if s.startswith("#") or s.startswith("//"):
                    doc_lines.append(s.lstrip("#/ "))
                else:
                    break
            elif quote_char and quote_char in s:
                idx = s.find(quote_char)
                doc_lines.append(s[:idx])
                break
            elif "*/" in s:
                idx = s.find("*/")
                doc_lines.append(s[:idx])
                break
            else:
                doc_lines.append(s)
    text = " ".join(l.strip() for l in doc_lines if l.strip())
    return text[:160].strip()


def _extract_symbol_doc(lines, lineno):
    for next_line in lines[lineno:lineno + 4]:
        s = next_line.strip()
        if not s:
            continue
        if s.startswith('"""') or s.startswith("'''"):
            return s.strip('"\'')[:80]
        elif s.startswith("#"):
            return s.lstrip("# ")[:80]
        elif s.startswith("//"):
            return s.lstrip("/ ")[:80]
        break
    # Look at preceding line for JS/TS comments
    if lineno >= 2:
        prev = lines[lineno - 2].strip()
        if prev.startswith("//"):
            return prev.lstrip("/ ")[:80]
        elif prev.endswith("*/") and "/*" in prev:
            return prev.strip("/* ").strip()[:80]
    return ""


_SYMBOL_CACHE = {}  # (root, rel) -> ((mtime_ns, size), {"defs", "imports", "doc"})


def extract_symbols(root, rel):
    """Return {defs: [{name, line, kind, doc}], imports: [raw_spec], doc: str}.

    Results are pooled and reused while (mtime_ns, size) is unchanged.
    """
    if _suffix(rel) not in _SYMBOL_SUFFIXES:
        return {"defs": [], "imports": [], "doc": ""}
    full = os.path.join(root, rel)
    try:
        st = os.stat(full)
    except OSError:
        return {"defs": [], "imports": [], "doc": ""}
    sig = (st.st_mtime_ns, st.st_size)
    key = (root, rel)
    cached = _SYMBOL_CACHE.get(key)
    if cached and cached[0] == sig:
        return cached[1]
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read(256 * 1024).splitlines()[:5000]
    except OSError:
        return {"defs": [], "imports": [], "doc": ""}
    defs, imports = [], []
    for lineno, line in enumerate(lines, 1):
        if len(defs) < MAX_SYMBOLS_PER_FILE:
            for pattern in _DEF_PATTERNS:
                match = pattern.match(line)
                if match:
                    kind = "class" if "class" in pattern.pattern[:30] else "def"
                    s_doc = _extract_symbol_doc(lines, lineno)
                    defs.append({"name": match.group(1), "line": lineno, "kind": kind, "doc": s_doc})
                    break
        if len(imports) < MAX_IMPORTS_PER_FILE:
            for pattern in _IMPORT_PATTERNS:
                match = pattern.search(line)
                if match:
                    imports.append(match.group(1))
                    break
    if rel.endswith('.py'):
        import ast
        try:
            tree = ast.parse('\n'.join(lines))
        except SyntaxError:
            tree = None
        if tree is not None:
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = '.' * node.level + (node.module or '')
                    imports.append(module)
                    imports.extend(module + ('' if module.endswith('.') else '.') + alias.name
                                   for alias in node.names if alias.name != '*')
            imports = list(dict.fromkeys(imports))[:MAX_IMPORTS_PER_FILE]
    module_doc = _extract_module_doc(lines)
    result = {"defs": defs, "imports": imports, "doc": module_doc}
    _SYMBOL_CACHE[key] = (sig, result)
    return result


def resolve_import(spec, root, from_rel):
    """Resolve an import spec to a repo-relative path, else None.

    Handles both relative specs (./x, ../x) and repo-absolute dotted
    module specs (from graph.rank import pagerank -> graph/rank.py).
    """
    if not spec:
        return None
    if from_rel.endswith('.py'):
        level = len(spec) - len(spec.lstrip('.'))
        base_dir = os.path.dirname(os.path.join(root, from_rel)) if level else root
        for _ in range(max(0, level - 1)):
            base_dir = os.path.dirname(base_dir)
        target = os.path.join(base_dir, spec.lstrip('.').replace('.', '/'))
        candidates = [target + '.py', os.path.join(target, '__init__.py')]
    else:
        base_dir = os.path.dirname(os.path.join(root, from_rel)) if spec.startswith('.') else root
        target = os.path.normpath(os.path.join(base_dir, spec))
        suffixes = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte')
        candidates = [target] + [target+s for s in suffixes] + [os.path.join(target, 'index'+s) for s in suffixes]
    for cand in candidates:
        if os.path.isfile(cand):
            rel = os.path.relpath(cand, root)
            if not rel.startswith(".."):
                return rel
    return None

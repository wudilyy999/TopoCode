"""Model client facade delegating to the Project Analysis Agent framework.
Runs only when configured; any failure leaves the event as evidence_only without raising.
"""

import os
from typing import Any, Dict, List, Optional

from agent.analyzer import ProjectAnalysisAgent
from agent.prompts import DIALOGUE_SCHEMA_VERSION

SCHEMA_VERSION = "analysis.v1"


def configured(model_cfg: Optional[Dict[str, Any]]) -> bool:
    return bool(model_cfg and model_cfg.get("base_url") and model_cfg.get("model"))


def test_connection(model_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Test model connection and return diagnostics."""
    agent = ProjectAnalysisAgent(model_cfg)
    return agent.diagnose_connection()


def analyze_dialogue(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    model_cfg: Optional[Dict[str, Any]],
    project_root: str = "",
    lang: str = "zh"
) -> bool:
    """Cumulative dialogue pass powered by ProjectAnalysisAgent."""
    agent = ProjectAnalysisAgent(model_cfg)
    result = agent.analyze_dialogue_turn(event, history, project_root=project_root, lang=lang)
    if result:
        from knowledge.explanations import save_branch
        save_branch(project_root, 'dialogue', lang, agent)
    return result


def analyze_event(event: Dict[str, Any], model_cfg: Optional[Dict[str, Any]]) -> bool:
    """Fallback single-turn event analysis."""
    agent = ProjectAnalysisAgent(model_cfg)
    # Re-use dialogue pass with empty history if dialogue not yet run
    if "dialogue" in event and event.get("analysis_status") == "analysis_done":
        return True
    return agent.analyze_dialogue_turn(event, [], project_root="")


def _readme_text(project: str) -> str:
    for cand in ("README.md", "README.rst", "README.txt", "readme.md"):
        full = os.path.join(project, cand)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(4000)
        except OSError:
            continue
    return ""


def _dir_summary(struct: Dict[str, Any], max_dirs: int = 24) -> str:
    counts: Dict[str, int] = {}
    for rel in struct.get("files", []):
        parts = rel.split("/")
        prefix = "/".join(parts[:2]) if len(parts) > 2 else (
            "/".join(parts[:1]) if len(parts) > 1 else "(root)")
        counts[prefix] = counts.get(prefix, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:max_dirs]
    return "\n".join("%-48s %d 个文件" % (name, n) for name, n in top)


def abstract_architecture_full(
    project: str,
    model_cfg: Optional[Dict[str, Any]],
    struct: Dict[str, Any],
    repo: Dict[str, Any],
    lang: str = "zh"
) -> Optional[Dict[str, Any]]:
    """One-shot architecture knowledge synthesis over the ranked repo structure."""
    agent = ProjectAnalysisAgent(model_cfg)
    from snapshot.selection import select_files
    ranked, coverage = select_files(struct.get("files", []), 600, struct.get("scores"))
    repo_line = "%s @ %s · 语言: %s" % (
        repo.get("branch") or "main", repo.get("head") or "?",
        " / ".join((repo.get("languages") or [])[:6]) or "未知")
    repo_line += "\nCoverage: selected=%d/%d; protected=%d; protected omitted=%d; directories=%d/%d" % (
        coverage['selected'], coverage['total'], coverage['critical_total'], coverage['critical_omitted'],
        coverage['directories_covered'], coverage['directories_total'])
    repo_line += "\nSelection: rotate manifests, entries and registration/configuration across directories. When bounded, role protection uses up to 60%, directory coverage up to 20%, and dependency rank fills the remainder. Prefer shallow directories and break ties by score."
    repo_line += "\nSelection stage counts: " + str(coverage['stage_counts'])
    repo_line += "\nThis is a bounded selection, not the entire repository. Do not infer absence from an omitted path."
    snapshot_coverage = struct.get('snapshot_selection') or {}
    if snapshot_coverage.get('omitted'):
        repo_line += '\nSnapshot already bounded: selected=%s/%s; protected omitted=%s' % (
            snapshot_coverage['selected'], snapshot_coverage['total'], snapshot_coverage['critical_omitted'])
    if coverage['critical_omitted']:
        repo_line += "\nOmitted protected paths: " + ', '.join(coverage['critical_omitted_examples'])
    result = agent.abstract_architecture(
        project, ranked, _dir_summary(struct),
        readme_text=_readme_text(project),
        repo_line=repo_line, total_files=len(struct.get("files", [])),
        lang=lang)
    if result:
        from knowledge.explanations import save_branch
        save_branch(project, 'architecture', lang, agent)
    return result


def update_architecture_patch(
    arch: Dict[str, Any],
    event: Dict[str, Any],
    model_cfg: Optional[Dict[str, Any]],
    lang: str = "zh",
    project: str = ""
) -> Optional[Dict[str, Any]]:
    """Incremental revision prompt: only affected components are rewritten."""
    agent = ProjectAnalysisAgent(model_cfg)
    lines = []
    for comp in arch.get("components", []):
        entry = ", ".join((comp.get("entry_files") or comp.get("files") or [])[:3])
        lines.append("%s | %s | %s | 入口: %s" % (
            comp.get("name", "?"), comp.get("layer", "?"),
            comp.get("summary", ""), entry or "无"))
    changed = "\n".join("%s (+%s/-%s)" % (f.get("path"), f.get("additions", 0),
                                          f.get("deletions", 0))
                        for f in event.get("files", []) if f.get("path"))
    d = event.get("dialogue") or {}
    analysis = "技术含义: " + str(d.get("technical_meaning") or d.get("summary") or "")
    analysis += "\n相关知识点: " + ", ".join(d.get("knowledge_points") or [])
    result = agent.update_architecture("\n".join(lines), changed, analysis, lang=lang)
    if result:
        from knowledge.explanations import save_branch
        save_branch(project, 'architecture', lang, agent)
    return result


_FILE_DEEP_CACHE = {}  # (abs_project, rel, lang) -> ((mtime_ns, size), result)


def answer_knowledge(
    entry: Dict[str, Any],
    related_entries: List[Dict[str, Any]],
    question: str,
    model_cfg: Optional[Dict[str, Any]],
    lang: str = "zh"
) -> Optional[str]:
    """Facade for the knowledge-base ask-agent feature."""
    agent = ProjectAnalysisAgent(model_cfg)
    return agent.answer_knowledge_question(entry, related_entries, question, lang=lang)


def analyze_file_deep(
    project: str,
    rel_path: str,
    context: Dict[str, Any],
    model_cfg: Optional[Dict[str, Any]],
    lang: str = "zh"
) -> Optional[Dict[str, Any]]:
    """On-demand agent deep-dive of one source file, cached by stat signature."""
    abs_file = context.get("abs_path") or os.path.join(project, rel_path)
    try:
        st = os.stat(abs_file)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    key = (os.path.abspath(project), rel_path, lang)
    cached = _FILE_DEEP_CACHE.get(key)
    if cached and cached[0] == sig:
        return cached[1]

    agent = ProjectAnalysisAgent(model_cfg)
    symbols = context.get("symbols") or {}
    from snapshot.redact import redact
    guide = context.get('reading_guide') or {}
    sections = guide.get('sections') or symbols.get('classes_and_functions') or []
    symbols_text = '\n'.join('%s | L%s-%s | %s | calls: %s' % (
        d.get('name'), d.get('line'), d.get('end_line', d.get('line')),
        d.get('purpose', ''), ', '.join(d.get('calls', []))) for d in sections[:120])
    imports_text = "\n".join(symbols.get("internal_imports") or [])
    comp = context.get("component") or {}
    meta_lines = [
        "文件: %s" % rel_path,
        "语言: %s · 技术栈: %s" % (context.get("language", ""),
                                   ", ".join(context.get("technologies") or []) or "-"),
        "规模: %s 行 · %s 字节" % (context.get("lines", 0), context.get("size_bytes", 0)),
        "所属组件: %s (%s)" % (comp.get("name", "?"), comp.get("summary", "")),
        "档案中的作用: %s" % (context.get("file_role") or "(档案未标注，请补充)"),
    ]
    history_lines = []
    for t in (context.get("history_modifications") or [])[:5]:
        history_lines.append("- [%s] %s → %s (%s)" % (
            str(t.get("occurred_at", ""))[:16], t.get("user_intent", ""),
            t.get("change_scope", ""), t.get("technical_meaning", "")))
    startup = '\n'.join('%s L%s: %s' % (s['name'], s['line'], ', '.join(s['calls']))
                        for s in guide.get('startup', []))
    result = agent.deep_analyze_file(redact('\n'.join(meta_lines)), redact(symbols_text),
                                     redact(imports_text), redact('\n'.join(history_lines)), startup, lang=lang)
    if result:
        valid = {s['name'] for s in sections}
        result['reading_steps'] = [s for s in result.get('reading_steps', []) if s['symbol'] in valid]
        _FILE_DEEP_CACHE[key] = (sig, result)
        from knowledge.explanations import save_branch
        save_branch(project, 'file:' + rel_path, lang, agent)
    return result

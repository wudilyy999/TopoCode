"""Deterministic AST and source code capability inspector.

Deeply analyzes source files to extract:
1. Concrete functional capabilities (what features the file provides).
2. Per-function and per-class roles, signatures, and purposes.
3. Module-level architectural role.
"""

import ast
import os
import re
from typing import Any, Dict, List, Optional

_INSPECT_CACHE: Dict[str, Any] = {}


def _infer_fn_purpose(name: str, signature: str, calls: List[str], doc: str) -> str:
    """Derive a clear, human-readable Chinese description of a function's role."""
    if doc:
        return doc
    n = name.lower().strip("_")
    
    # Common routing and network handlers
    if n == "do_get":
        return "处理客户端 HTTP GET 请求（静态资源、图谱数据与 SSE 订阅）"
    if n == "do_post":
        return "分发 HTTP POST 接口（模型配置、全量/增量架构分析、测试）"
    if n == "main":
        return "程序启动入口，解析命令行参数、加载配置并启动核心服务"
    if n == "poll_loop" or n == "run_loop":
        return "后台主循环：周期性扫描未跟踪项目并监听各平台 Agent 会话"
    if n == "send" or n == "_send":
        return "序列化并向客户端发送 HTTP 响应报文与状态头"
    if n == "log_message":
        return "静默或格式化底层 HTTP 服务器的请求访问日志"
    
    # Architecture and knowledge operations
    if "architecture" in n or "arch" in n:
        if "update" in n or "revision" in n:
            return "根据最近的会话代码改动，增量修订受影响的架构组件与职责"
        if "load" in n:
            return "从本地数据目录读取持久化的项目架构知识档案"
        if "save" in n:
            return "将架构定位、组件分层与入口职责持久化保存到数据目录"
        if "expand" in n:
            return "结合代码快照与 PageRank 权重为架构组件补全归属文件"
        return "执行项目系统分层架构归纳与组件职责解析"
    
    # Analysis and dialogue
    if "analyze" in n:
        if "dialogue" in n:
            return "多轮累积对话分析：研判开发意图、改动范围、技术含义与知识点"
        if "file" in n or "deep" in n:
            return "深度解析单个源文件：分析核心机制、协作关系与改动影响"
        if "event" in n:
            return "对单条会话记录提取改动文件、技术栈并执行归因分析"
        return "执行语义分析并提取结构化元数据"

    # Snapshot and symbols
    if "snapshot" in n or "scan" in n:
        return "扫描项目目录，计算文件 blake2b 哈希摘要、行数与技术栈标签"
    if "symbol" in n:
        return "轻量级解析代码导出符号（类、函数、接口）与内部引用依赖"
    if "import" in n:
        return "解析内部 import 路径并计算代码依赖流向拓扑"
    if "pagerank" in n or "rank" in n:
        return "基于依赖引用边与共现关系执行 PageRank 图节点重要性打分"
    if "blueprint" in n:
        return "组装系统自顶向下的四层工程架构蓝图与组件拓扑"
    
    # Storage and config
    if n.startswith("load_"):
        target = n[5:].replace("_", " ")
        return f"从磁盘加载 {target} 持久化配置或状态数据"
    if n.startswith("save_"):
        target = n[5:].replace("_", " ")
        return f"将 {target} 安全写入本地数据目录（带文件锁与临时替换）"
    
    # Inference from calls
    if calls:
        top_calls = ", ".join(calls[:3])
        return f"协作执行核心逻辑，调用了 {top_calls}"
    
    return f"负责 {name} 相关的逻辑处理与功能支持"


def _inspect_python(content: str, rel_path: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _inspect_generic(content, rel_path)

    module_doc = ast.get_docstring(tree) or ""
    clean_module_doc = module_doc.split("\n")[0].strip() if module_doc else ""

    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            doc = (ast.get_docstring(node) or "").split("\n")[0].strip()
            calls = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name):
                        calls.append(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute):
                        calls.append(sub.func.attr)
            calls = list(dict.fromkeys(calls))[:5]
            sig = f"{node.name}({', '.join(args)})"
            purpose = _infer_fn_purpose(node.name, sig, calls, doc)
            functions.append({
                "name": node.name,
                "signature": sig,
                "line": node.lineno,
                "kind": "async def" if isinstance(node, ast.AsyncFunctionDef) else "def",
                "purpose": purpose,
                "doc": doc
            })
        elif isinstance(node, ast.ClassDef):
            c_doc = (ast.get_docstring(node) or "").split("\n")[0].strip()
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_args = [a.arg for a in item.args.args if a.arg != "self"]
                    m_doc = (ast.get_docstring(item) or "").split("\n")[0].strip()
                    m_sig = f"{item.name}({', '.join(m_args)})"
                    m_calls = []
                    for sub in ast.walk(item):
                        if isinstance(sub, ast.Call):
                            if isinstance(sub.func, ast.Name):
                                m_calls.append(sub.func.id)
                            elif isinstance(sub.func, ast.Attribute):
                                m_calls.append(sub.func.attr)
                    m_calls = list(dict.fromkeys(m_calls))[:5]
                    methods.append({
                        "name": item.name,
                        "signature": m_sig,
                        "line": item.lineno,
                        "kind": "method",
                        "purpose": _infer_fn_purpose(item.name, m_sig, m_calls, m_doc),
                        "doc": m_doc
                    })
            c_purpose = c_doc or f"定义核心业务类 {node.name}，封装内部状态与 {len(methods)} 个关键接口方法"
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "kind": "class",
                "purpose": c_purpose,
                "doc": c_doc,
                "methods": methods
            })

    # Synthesize concrete capabilities
    capabilities = []
    if clean_module_doc:
        capabilities.append(clean_module_doc)
    for c in classes:
        if c.get("methods"):
            m_names = ", ".join(m["name"] for m in c["methods"][:4])
            capabilities.append(f"封装核心类 {c['name']}，提供 {m_names} 等方法")
    for f in functions[:5]:
        if f["name"] not in ("main", "log_message"):
            capabilities.append(f"导出接口 {f['name']}()：{f['purpose']}")

    if len(capabilities) < 2:
        capabilities.append("实现当前领域的底层数据结构与功能逻辑支持")

    return {
        "module_doc": clean_module_doc,
        "classes": classes,
        "functions": functions,
        "capabilities": capabilities[:5]
    }


def _inspect_generic(content: str, rel_path: str) -> Dict[str, Any]:
    lines = content.splitlines()[:1000]
    
    # Extract top comment/doc
    doc_lines = []
    for line in lines[:25]:
        s = line.strip()
        if not s:
            continue
        if s.startswith(("//", "#", "/*", "*")):
            clean = s.lstrip("/#* ").rstrip("*/").strip()
            if clean and not clean.startswith("!"):
                doc_lines.append(clean)
        else:
            break
    module_doc = " ".join(doc_lines)[:160].strip()

    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []

    fn_pattern = re.compile(r"^\s*(?:export\s+|async\s+)*(?:function|const|def)\s+([A-Za-z_][\w]*)\s*(?:=\s*(?:async\s*)?\([^)]*\)|=|\()")
    class_pattern = re.compile(r"^\s*(?:export\s+)*(?:class|interface|type)\s+([A-Za-z_][\w]*)")

    for lineno, line in enumerate(lines, 1):
        c_m = class_pattern.match(line)
        if c_m:
            cname = c_m.group(1)
            classes.append({
                "name": cname,
                "line": lineno,
                "kind": "class",
                "purpose": f"声明核心数据结构或类型接口 {cname}",
                "doc": ""
            })
            continue
        f_m = fn_pattern.match(line)
        if f_m:
            fname = f_m.group(1)
            if fname not in [f["name"] for f in functions]:
                functions.append({
                    "name": fname,
                    "signature": f"{fname}()",
                    "line": lineno,
                    "kind": "function",
                    "purpose": _infer_fn_purpose(fname, fname, [], ""),
                    "doc": ""
                })

    capabilities = []
    if module_doc:
        capabilities.append(module_doc)
    if classes:
        c_names = ", ".join(c["name"] for c in classes[:3])
        capabilities.append(f"定义类型与接口：{c_names}")
    for f in functions[:4]:
        capabilities.append(f"实现函数 {f['name']}()：{f['purpose']}")
    if not capabilities:
        base = os.path.basename(rel_path).lower()
        if base.endswith(".html"):
            capabilities.append("构建单页可交互前端与 SVG 动态拓扑图谱渲染界面")
        elif base.endswith((".md", ".txt")):
            capabilities.append("记录项目说明、架构规范与工程约束文档")
        else:
            capabilities.append(f"提供 {rel_path} 相关的核心功能实现与数据支撑")

    return {
        "module_doc": module_doc,
        "classes": classes,
        "functions": functions,
        "capabilities": capabilities[:5]
    }


def inspect_file_capabilities(project_root: str, rel_path: str) -> Dict[str, Any]:
    """Inspect a source file and return its capabilities and detailed function roles."""
    abs_path = os.path.join(os.path.abspath(project_root), rel_path.strip().lstrip("/"))
    if not os.path.isfile(abs_path):
        return {
            "module_doc": "",
            "classes": [],
            "functions": [],
            "capabilities": ["文件不存在或不可读取"]
        }

    try:
        st = os.stat(abs_path)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = (0, 0)

    cache_key = f"{abs_path}::{sig}"
    if cache_key in _INSPECT_CACHE:
        return _INSPECT_CACHE[cache_key]

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(512 * 1024)
    except OSError:
        return {
            "module_doc": "",
            "classes": [],
            "functions": [],
            "capabilities": []
        }

    if rel_path.endswith(".py"):
        result = _inspect_python(content, rel_path)
    else:
        result = _inspect_generic(content, rel_path)

    _INSPECT_CACHE[cache_key] = result
    return result

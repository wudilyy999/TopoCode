"""Shared language / technology classification tables.

Pure data + pure function. First version is a fixed table per spec;
a future version may load overrides from config without changing callers.
"""

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".xml": "XML",
}

_TECH_BY_SUFFIX = {
    ".tsx": ("React",),
    ".jsx": ("React",),
    ".vue": ("Vue",),
    ".svelte": ("Svelte",),
    ".ts": ("TypeScript",),
    ".js": ("JavaScript",),
    ".mjs": ("JavaScript",),
    ".cjs": ("JavaScript",),
    ".py": ("Python",),
    ".go": ("Go",),
    ".rs": ("Rust",),
    ".java": ("Java",),
}

_TECH_BY_PATH = (
    ("test", "Testing"),
    ("tests", "Testing"),
    ("__tests__", "Testing"),
    ("spec", "Testing"),
    ("api", "API"),
    ("apis", "API"),
    ("routes", "API"),
    ("server", "API"),
    ("docs", "Docs"),
)

MAX_TECHNOLOGIES = 8


def language_for(path):
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return LANGUAGE_BY_SUFFIX.get(suffix, "Other")


def technologies_for(path):
    found = []
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    for tech in _TECH_BY_SUFFIX.get(suffix, ()):
        if tech not in found:
            found.append(tech)
    lowered = path.lower()
    for keyword, tech in _TECH_BY_PATH:
        if keyword in lowered and tech not in found:
            found.append(tech)
    return found[:MAX_TECHNOLOGIES]

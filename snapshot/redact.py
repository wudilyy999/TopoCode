"""Credential redaction + evidence text truncation.

Only metadata (paths, line counts, language tags) leaves this module.
Source text is summarized, never quoted verbatim beyond a short,
redacted prefix.
"""

import re

REPLACEMENT = "[credential omitted]"

_PATTERNS = (
    re.compile(r"(?i)[\"']?(api[_-]?key|secret|token|password|passwd|pwd|client[_-]?secret)[\"']?\s*[:=]\s*[\"']?[^\s\"',}\]]+"),
    re.compile(r"(?i)[\"']?(authorization)[\"']?\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)\b(aws_|github_|openai-|sk-)[A-Za-z0-9\-_]+"),
)

REQUEST_LIMIT = 500
RESULT_LIMIT = 500


def redact(text):
    if not text:
        return ""
    out = str(text)
    for pattern in _PATTERNS:
        out = pattern.sub(REPLACEMENT, out)
    return out


def truncate(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def evidence_summary(request_text, result_text):
    clean_req = re.sub(r"(?i)^request\s*:\s*", "", (request_text or "").strip())
    # Split off any leaked result/META inside request
    for marker in ("\nresult: META:", "\nresult:", "\nResult:"):
        if marker in clean_req:
            clean_req = clean_req.split(marker)[0].strip()
    res = (result_text or "").strip()
    if "META:" in res:
        res = re.sub(r"META:\s*\{.*?\}", "[session metadata]", res, flags=re.DOTALL).strip()
    request = truncate(redact(clean_req), REQUEST_LIMIT)
    result = truncate(redact(res), RESULT_LIMIT)
    if request and result:
        return "request: %s\nresult: %s" % (request, result)
    return request or result or ""

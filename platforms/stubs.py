"""Stub adapters for platforms without a verified session format yet.

Each stub registers its name so the tailer and /api/map report it as a
known-but-unimplemented evidence provider instead of silently ignoring it.
"""

from platforms.base import BaseAdapter, register

_STUBS = (
    ("qoder", "qoder", "Qoder"),
    ("cursor", "cursor", "Cursor"),
    ("qwen", "qwen", "Qwen"),
    ("copilot", "copilot", "Copilot"),
    ("pi", "pi", "Pi"),
    ("workbuddy", "workbuddy", "WorkBuddy"),
    ("grok", "grok", "Grok"),
    ("augment", "augment", "Augment"),
    ("deepseek", "deepseek", "DeepSeek Harness"),
)


def _make(agent_id, agent_label):
    @register(agent_id, implemented=False)
    class StubAdapter(BaseAdapter):
        pass
    StubAdapter.agent_id = agent_id
    StubAdapter.agent_label = agent_label
    StubAdapter.__name__ = "Stub_%s" % agent_id
    return StubAdapter


for _name, _id, _label in _STUBS:
    _make(_id, _label)

"""Platform adapter interface.

Every agent platform implements: resolve_scope / discover_source_roots /
discover_sessions / read_session / normalize_event. Platforms that only
have a stub register with implemented=False so the tailer skips them
without pretending to parse unknown formats.
"""

REGISTRY = {}


def register(name, implemented=True):
    def wrap(cls):
        REGISTRY[name] = {"adapter": cls(), "implemented": implemented}
        return cls
    return wrap


class BaseAdapter:
    agent_id = "unknown"
    agent_label = "Unknown"

    def resolve_scope(self, session_ref):
        return None

    def discover_source_roots(self):
        return []

    def discover_sessions(self):
        return []

    def read_session(self, session_ref):
        return []

    def normalize_event(self, raw):
        return raw

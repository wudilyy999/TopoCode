"""Shared checkpointer for TopoCode's LangGraph pipelines.

Checkpoints live under the TopoCode data dir (never inside a watched
project), one SQLite database per graph.
"""

import os
import sqlite3

from config import store

_CHECKPOINTERS = {}


def graph_checkpointer(name):
    """Return the shared SqliteSaver for a graph, creating it on first use."""
    saver = _CHECKPOINTERS.get(name)
    if saver is None:
        from langgraph.checkpoint.sqlite import SqliteSaver
        store.ensure_dirs()
        path = os.path.join(store.data_dir(), "graphs", name + ".sqlite")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        saver = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
        saver.setup()
        _CHECKPOINTERS[name] = saver
    return saver

"""Extended knowledge bank: domain expansion packs.

Each bank_ext_<domain>.py is a standalone data module defining EXTRA_ENTRIES.
This aggregator concatenates them; knowledge/bank.py appends the result to
KNOWLEDGE_ENTRIES before building ID_INDEX / KEYWORD_MAP.
"""

from knowledge.bank_ext_agent_algo import EXTRA_ENTRIES as _AGENT_ALGO
from knowledge.bank_ext_agent_dev import EXTRA_ENTRIES as _AGENT_DEV
from knowledge.bank_ext_backend import EXTRA_ENTRIES as _BACKEND
from knowledge.bank_ext_biz_algo import EXTRA_ENTRIES as _BIZ_ALGO
from knowledge.bank_ext_frontend import EXTRA_ENTRIES as _FRONTEND
from knowledge.bank_ext_post_train import EXTRA_ENTRIES as _POST_TRAIN
from knowledge.bank_ext_fundamentals import EXTRA_ENTRIES as _FUNDAMENTALS

EXTRA_ENTRIES = (
    _AGENT_DEV
    + _AGENT_ALGO
    + _FRONTEND
    + _BACKEND
    + _BIZ_ALGO
    + _POST_TRAIN
    + _FUNDAMENTALS
)

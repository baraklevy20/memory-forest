"""What the tests share: the add-on on the import path, a fixed "today", and small
builders for cards and database rows. The tests cover the pure-Python parts of Memory
Forest (no Anki needed).

Run from the repo root:
    python -m unittest discover anki_forest/tests
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import study_log

DAY = study_log.DAY_SECS
CUTOFF = int(dt.datetime(2026, 9, 20, 4, 0).timestamp())  # next rollover; "today" is 19 Sep
TODAY = 2000


def ms(days_ago: int, hour: int = 12) -> int:
    """Revlog-style ms timestamp at `hour` o'clock on the Anki day `days_ago` days back."""
    return int((CUTOFF - (days_ago + 1) * DAY + (hour - 4) * 3600) * 1000)


def card(cid, ctype=2, ivl=30, s=None):
    data = json.dumps({"s": s}) if s is not None else "{}"
    return (cid, ctype, 2, ivl, data)


def rows(cards, first_last=None, lapses=(), review_days=(0,), total=100, today=10):
    return study_log.Rows(list(cards), first_last or {}, set(lapses), set(review_days), total, today)

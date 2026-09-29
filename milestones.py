"""The milestone animals that move into the forest, and the trees whose planting day comes
round again.

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable

# The milestones the animals come for. The forest remembers the day each animal came
# (events_state.py), which is when the journal announces it.
RABBIT_TREES = 50
DEER_STREAK = 30
STAG_STREAK = 100
FOX_REVIEWS = 10_000
CABIN_AGE_DAYS = 365
# the later ones, years in: a two-year streak, and mature cards (remembered three weeks and more)
BEAR_STREAK = 730
SQUIRREL_MATURE, EAGLE_MATURE = 10_000, 25_000

VISITORS = (
    # key, who, why they came, test
    ("rabbit", "a rabbit", "your forest reached 50 trees", lambda s: s["trees"] >= RABBIT_TREES),
    ("deer", "a deer", "you kept a 30-day streak", lambda s: s["longest_streak"] >= DEER_STREAK),
    ("fox", "a fox", "you passed 10,000 reviews", lambda s: s["reviews"] >= FOX_REVIEWS),
    ("owl", "an owl", "your first tree became ancient", lambda s: s["ancient"] >= 1),
    ("heron", "a heron", "a pond formed where you took a break", lambda s: s.get("ponds", 0) >= 1),
    ("stag", "a stag", "you kept a 100-day streak", lambda s: s["longest_streak"] >= STAG_STREAK),
    ("cabin", "a cabin", "your forest turned one year old", lambda s: s["forest_age"] >= CABIN_AGE_DAYS),
    ("bear", "a bear", "you kept a two-year streak", lambda s: s["longest_streak"] >= BEAR_STREAK),
    ("squirrel", "a family of squirrels", "you knew 10,000 cards well", lambda s: s.get("mature_cards", 0) >= SQUIRREL_MATURE),
    ("eagle", "an eagle", "you knew 25,000 cards well", lambda s: s.get("mature_cards", 0) >= EAGLE_MATURE),
)


def visitors(stats: dict, arrived: dict | None = None, today: int | None = None) -> list:
    """Milestone animals that have moved in.

    Once an animal has come it stays for good: `arrived` holds every one that has (see
    arrivals), and each is new on the day it came (`today`, the scheduler's day number).
    Only an asteroid sends them away, and then they have to be earned again.

    Without `arrived` (the test forest, a deck's own forest) there is nothing remembered, so
    the animals are those today's numbers bring, and new when _arrived_today can tell.
    """
    out = []
    for key, label, why, test in VISITORS:
        if arrived is not None:
            if key in arrived:
                out.append({"key": key, "label": label, "why": why, "new": today is not None and arrived[key] == today})
        elif test(stats):
            out.append({"key": key, "label": label, "why": why, "new": _arrived_today(key, stats)})
    return out


def arrivals(stats: dict, known: dict, today: int | None) -> dict:
    """`known` - every animal that has come, and the day it came - with those today's
    numbers bring added, as coming on `today` (None: quietly, on no day to announce, for
    the first look at a forest that already had them)."""
    out = dict(known)
    for key, _label, _why, test in VISITORS:
        if key not in out and test(stats):
            out[key] = today
    return out


def _arrived_today(key: str, s: dict) -> bool:
    if key == "fox":
        return s["reviews"] - s["today_reviews"] < FOX_REVIEWS <= s["reviews"]
    if key == "deer":
        return s["streak"] == DEER_STREAK and s["longest_streak"] == DEER_STREAK
    if key == "stag":
        return s["streak"] == STAG_STREAK and s["longest_streak"] == STAG_STREAK
    if key == "bear":
        return s["streak"] == BEAR_STREAK and s["longest_streak"] == BEAR_STREAK
    if key == "cabin":
        return s["forest_age"] == CABIN_AGE_DAYS
    if key == "rabbit":
        return s["trees"] == RABBIT_TREES and s["planted_today"]
    return False


def anniversaries(trees: Iterable[dict], on: _dt.date) -> list:
    """Indexes of trees planted on this calendar day in an earlier year."""
    out = []
    for i, t in enumerate(trees):
        d = _dt.date.fromisoformat(t["date"])
        if d.year < on.year and (d.month, d.day) == (on.month, on.day):
            out.append(i)
    return out

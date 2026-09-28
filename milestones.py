"""The milestone animals that move into the forest, and the trees whose planting day comes
round again.

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable

# The milestones the animals come for; `_arrived_today` watches for the day each is crossed.
RABBIT_TREES = 50
DEER_STREAK = 30
STAG_STREAK = 100
FOX_REVIEWS = 10_000
CABIN_AGE_DAYS = 365

VISITORS = (
    # key, who, why they came, test
    ("rabbit", "a rabbit", "your forest reached 50 trees", lambda s: s["trees"] >= RABBIT_TREES),
    ("deer", "a deer", "you kept a 30-day streak", lambda s: s["longest_streak"] >= DEER_STREAK),
    ("fox", "a fox", "you passed 10,000 reviews", lambda s: s["reviews"] >= FOX_REVIEWS),
    ("owl", "an owl", "your first tree became ancient", lambda s: s["ancient"] >= 1),
    ("heron", "a heron", "a pond formed where you took a break", lambda s: s.get("ponds", 0) >= 1),
    ("stag", "a stag", "you kept a 100-day streak", lambda s: s["longest_streak"] >= STAG_STREAK),
    ("cabin", "a cabin", "your forest turned one year old", lambda s: s["forest_age"] >= CABIN_AGE_DAYS),
)


def visitors(stats: dict) -> list:
    """Milestone animals that have moved in.

    Each test reads today's numbers, so an animal can leave again if the numbers it came
    for go away - deleting or suspending a day's cards can drop the tree count below 50,
    or take the last ancient tree with it. The streak ones use the longest-ever streak,
    which never falls.
    """
    out = []
    for key, label, why, test in VISITORS:
        if test(stats):
            out.append({"key": key, "label": label, "why": why, "new": _arrived_today(key, stats)})
    return out


def _arrived_today(key: str, s: dict) -> bool:
    if key == "fox":
        return s["reviews"] - s["today_reviews"] < FOX_REVIEWS <= s["reviews"]
    if key == "deer":
        return s["streak"] == DEER_STREAK and s["longest_streak"] == DEER_STREAK
    if key == "stag":
        return s["streak"] == STAG_STREAK and s["longest_streak"] == STAG_STREAK
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

"""The milestone animals that move into the forest, and the trees whose planting day comes
round again.

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import calendar
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
    Only an asteroid sends them away (see events_state._animals), and then they have to be
    earned again.

    Without `arrived` (the test forest) there is nothing remembered, so the animals are
    those today's numbers bring, and new when _arrived_today can tell.
    """
    out = []
    for key, label, why, test in VISITORS:
        if arrived is not None:
            if key in arrived:
                # the day it came (the scheduler's day number), if it came while the forest watched
                out.append({"key": key, "label": label, "why": why, "new": today is not None and arrived[key] == today,
                            "day": arrived[key]})
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
    """Indexes of trees planted on this calendar day in an earlier year. A tree planted on
    29 Feb has its anniversary on 28 Feb in the years without one."""
    leapless = on.month == 2 and on.day == 28 and not calendar.isleap(on.year)
    out = []
    for i, t in enumerate(trees):
        d = _dt.date.fromisoformat(t["date"])
        if d.year < on.year and ((d.month, d.day) == (on.month, on.day) or (leapless and (d.month, d.day) == (2, 29))):
            out.append(i)
    return out


# the test forest's made-up day for an animal its history cannot date (the owl, the squirrels,
# the eagle): this many days ago, and this many more for each animal before it in VISITORS
MADE_UP_AGO, MADE_UP_APART = 9, 13


def animal_days(visitors: list, trees: list, day_reviews: dict, today: int, made_up: bool = False) -> list:
    """When each animal in the forest came, as days ago: worked out from the history where its
    milestone can be (the day a streak reached its length, the 50th tree, the 10,000th review,
    the first pond, the forest's first birthday), so the animals a forest had before the add-on
    came still have their day; otherwise the day the forest saw it come, if it did. The test
    forest (`made_up`) saw none come, so it gives those a made-up day, to see them all."""
    studied = sorted((ago for ago, n in day_reviews.items() if n), reverse=True)  # oldest first
    streak_at, run, last = {}, 0, None
    for ago in studied:
        run = run + 1 if last is not None and last - ago == 1 else 1
        last = ago
        streak_at.setdefault(run, ago)
    total, passed = 0, None
    for ago in sorted(day_reviews, reverse=True):
        total += day_reviews[ago]
        if passed is None and total >= FOX_REVIEWS:
            passed = ago
    first_pond = next((t["ago"] for t in trees if t.get("gap")), None)
    birthday = trees[0]["ago"] - CABIN_AGE_DAYS if trees else -1
    found = {
        "deer": streak_at.get(DEER_STREAK), "stag": streak_at.get(STAG_STREAK),
        "bear": streak_at.get(BEAR_STREAK),
        "rabbit": trees[RABBIT_TREES - 1]["ago"] if len(trees) >= RABBIT_TREES else None,
        "fox": passed, "heron": first_pond, "cabin": birthday if birthday >= 0 else None,
    }
    out = []
    for v in visitors:
        ago = found.get(v["key"])
        if ago is None and isinstance(v.get("day"), int):
            ago = today - v["day"]
        if ago is None and made_up:
            ago = MADE_UP_AGO + MADE_UP_APART * [k for k, *_rest in VISITORS].index(v["key"])
        if ago is not None and ago >= 0:
            out.append({"key": v["key"], "ago": ago, "label": v["label"], "why": v["why"]})
    return out

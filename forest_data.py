"""Turn a collection's cards and review log into forest trees.

One tree per Anki day on which new cards were first studied. A tree's stage
comes from how well that day's cards are remembered now (FSRS stability when
available, otherwise the review interval), its crown size from how many cards
it holds, and its health from how many of them are currently being relearned
or were recently forgotten. The rows come from study_log, the memory maths from
memory, and the animals from milestones.

This module never imports aqt, so it runs in unit tests and in the dev export
script against a plain sqlite3 connection.
"""

from __future__ import annotations

import hashlib
from statistics import median

try:
    from .memory import retrievability, stability
    from .milestones import visitors
    from .study_log import DAY_SECS, Rows, day_date, days_ago
except ImportError:  # tests and dev scripts import these files as top-level modules
    from memory import retrievability, stability
    from milestones import visitors
    from study_log import DAY_SECS, Rows, day_date, days_ago

MATURE_DAYS = 21
OLD_DAYS = 180
ANCIENT_DAYS = 365
SEEDLING, SAPLING, YOUNG, MATURE, OLD, ANCIENT = range(6)  # a tree's stage
# A day whose cards are mostly still in their first learning steps stays a sapling.
SAPLING_LEARNING_SHARE = 0.5

# Cards a day needs for a medium, then a large crown.
CROWN_SIZE_CARDS = (15, 40)
# About a third of the trees are conifers, picked by each day's seed.
PINE_PERCENT = 34

HEALTH_THRESHOLDS = (0.12, 0.25, 0.45)  # share of struggling cards → health 1, 2, 3
# Forgetting is part of learning new cards, so trees only yellow once they have matured.
HEALTH_MIN_STAGE = MATURE

# A break has to be long enough to be worth marking: a week away shows as a pond and a
# gap in the planting, a long weekend does not.
BREAK_DAYS = 7

# Trees drawn one by one. Older ones become the deep forest at the back: a few receding
# bands of canopy instead of hundreds of sprites. At a tree a day this keeps well over a
# year individual, and holds the render cost (and the payload) flat however long you study.
MAX_INDIVIDUAL_TREES = 420


def _seed(day: int) -> int:
    return int.from_bytes(hashlib.sha1(f"anki-forest-{day}".encode()).digest()[:4], "big") & 0x7FFFFFFF


def make_tree(day: int, ago: int, date: str, n: int, stage: int, health: int,
          remembered: float, strength: float, struggling: int, measured: bool = True) -> dict:
    """One tree, however the numbers were arrived at (real cohort or test forest)."""
    seed = _seed(day)
    return {
        "day": day,
        "ago": ago,
        "date": date,
        "n": n,
        "stage": stage,
        "size": 0 if n < CROWN_SIZE_CARDS[0] else 1 if n < CROWN_SIZE_CARDS[1] else 2,
        "health": health,
        "kind": 1 if seed % 100 < PINE_PERCENT else 0,
        "seed": seed,
        "remembered": round(remembered, 3),
        "strength": round(strength, 1),
        "struggling": struggling,
        "measured": measured,  # False when "% remembered" is a guess, not a forgetting curve
    }


def make_forest(trees: list, streak: int, longest: int, reviews: int, today_reviews: int) -> dict:
    stats = {
        "trees": len(trees),
        "cards": sum(t["n"] for t in trees),
        "ancient": sum(1 for t in trees if t["stage"] == ANCIENT),
        "old": sum(1 for t in trees if t["stage"] == OLD),
        "young": sum(1 for t in trees if t["stage"] == YOUNG),
        "yellowing": sum(1 for t in trees if t["health"] > 0),
        "streak": streak,
        "longest_streak": longest,
        "reviews": reviews,
        "today_reviews": today_reviews,
        "forest_age": trees[0]["ago"] if trees else 0,
        "oldest_date": trees[0]["date"] if trees else None,
        "planted_today": bool(trees and trees[-1]["ago"] == 0),
        "today_cards": trees[-1]["n"] if trees and trees[-1]["ago"] == 0 else 0,
        "ponds": sum(1 for t in trees if t.get("gap")),
    }
    return {"trees": trees, "stats": stats, "visitors": visitors(stats),
            "forest_seed": trees[0]["seed"] if trees else 0}


def _stage(strengths: list, learning_share: float, is_today: bool) -> int:
    if is_today:
        return SEEDLING
    if not strengths or learning_share > SAPLING_LEARNING_SHARE:
        return SAPLING
    m = median(strengths)
    if m >= ANCIENT_DAYS:
        return ANCIENT
    if m >= OLD_DAYS:
        return OLD
    if m >= MATURE_DAYS:
        return MATURE
    return YOUNG


def _health(struggling_share: float) -> int:
    level = 0
    for threshold in HEALTH_THRESHOLDS:
        if struggling_share >= threshold:
            level += 1
    return level


def _streaks(review_days: set) -> tuple:
    """(current streak, longest streak). A streak survives until today ends."""
    if not review_days:
        return 0, 0
    current = 0
    start = 0 if 0 in review_days else 1
    while start + current in review_days:
        current += 1
    longest = run = 0
    prev = None
    for d in sorted(review_days):
        run = run + 1 if prev is not None and d == prev + 1 else 1
        longest = max(longest, run)
        prev = d
    return current, longest


def _breaks(review_days: set, oldest: int) -> list:
    """(days_ago of the day that ended the break, length) for each stretch of at least
    BREAK_DAYS days without reviews, oldest first. A break still in progress is ignored."""
    out = []
    gap = 0
    for d in range(oldest, -1, -1):
        if d in review_days:
            if gap >= BREAK_DAYS:
                out.append((d, gap))
            gap = 0
        else:
            gap += 1
    return out


def build_forest(rows: Rows, day_cutoff: int, today: int, now_ts: float | None = None) -> dict:
    """Group cards into daily trees and compute everything the renderer shows.

    `today` is the scheduler's day number (sched.today); trees are keyed by absolute
    day number so their seed and position never change.
    """
    now_ts = now_ts if now_ts is not None else day_cutoff - DAY_SECS / 2
    cohorts: dict = {}
    for cid, ctype, queue, ivl, data in rows.cards:
        first_last = rows.first_last.get(cid)
        first_ms = first_last[0] if first_last else cid
        d = days_ago(first_ms / 1000, day_cutoff)
        if d < 0:
            continue
        c = cohorts.setdefault(d, {"n": 0, "learning": 0, "strengths": [], "struggling": 0, "r": [], "suspended": 0})
        c["n"] += 1
        stab = stability(data)
        if ctype == 1:  # still in initial learning
            c["learning"] += 1
        else:
            c["strengths"].append(stab if stab is not None else max(ivl, 0))
        # a suspended card keeps its place in the tree as it stood when it was suspended: it
        # can neither struggle nor slip any more, so it counts towards neither
        if queue == -1:
            c["suspended"] += 1
            continue
        if ctype == 3 or cid in rows.recent_lapses:
            c["struggling"] += 1
        if stab is not None and first_last:
            elapsed = max(0.0, (now_ts - first_last[1] / 1000) / DAY_SECS)
            c["r"].append(retrievability(stab, elapsed, data))

    # which day's tree each leech belongs to (a suspended leech is not among the cards
    # above, so go by its first review)
    def per_day(cids: set) -> dict:
        out: dict = {}
        for cid in cids:
            fl = rows.first_last.get(cid)
            d = days_ago((fl[0] if fl else cid) / 1000, day_cutoff)
            if d >= 0:
                out[d] = out.get(d, 0) + 1
        return out
    leeches = per_day(rows.leeches)

    trees = []
    for d in sorted(cohorts, reverse=True):  # oldest first
        c = cohorts[d]
        n = c["n"]
        # health and recall are about the cards still being studied; suspended ones only
        # hold the tree's size and stage
        active = n - c["suspended"]
        stage = _stage(c["strengths"], c["learning"] / n, d == 0)
        health = _health(c["struggling"] / active) if active and stage >= HEALTH_MIN_STAGE else 0
        strength = round(median(c["strengths"]), 1) if c["strengths"] else 0
        measured = bool(active) and len(c["r"]) >= active / 2  # most of the day's cards have a forgetting curve
        remembered = sum(c["r"]) / len(c["r"]) if c["r"] else 1 - c["struggling"] / active if active else 1.0
        t = make_tree(today - d, d, day_date(d, day_cutoff).isoformat(), n, stage, health,
                  remembered, strength, c["struggling"], measured)
        if c["suspended"]:
            t["suspended"] = c["suspended"]
        if leeches.get(d):
            t["leeches"] = leeches[d]
        trees.append(t)

    if trees:
        for resumed, length in _breaks(rows.review_days, trees[0]["ago"]):
            # the pond sits just before the first tree planted after the break; if that
            # tree already holds one, the next tree takes it, so two breaks never merge
            # into a single pond claiming their combined length
            after = next((t for t in trees if t["ago"] <= resumed and not t.get("gap")), None)
            if after is not None:
                after["gap"] = length
            elif trees[-1].get("gap", 0) < length:
                trees[-1]["gap"] = length  # nowhere left to put it: keep the longer break

    current, longest = _streaks(rows.review_days)
    forest = make_forest(trees, current, longest, rows.total_reviews, rows.today_reviews)
    forest["review_days"] = rows.review_days  # for the events; never sent to the page
    return forest


def merge_old(forest: dict, limit: int = MAX_INDIVIDUAL_TREES) -> dict:
    """Fold everything older than the newest `limit` trees into one summary.

    The renderer draws that summary as the deep forest at the back, so a ten-year
    forest costs the same to draw (and to send to the page) as a one-year one. The
    stats line still counts every tree; only the drawing is grouped.
    """
    trees = forest["trees"]  # oldest first
    if len(trees) <= limit:
        return forest
    old, kept = trees[:len(trees) - limit], trees[len(trees) - limit:]
    merged = {
        "count": len(old),
        "cards": sum(t["n"] for t in old),
        "ancient": sum(1 for t in old if t["stage"] == ANCIENT),
        "ponds": sum(1 for t in old if t.get("gap")),
        "from_date": old[0]["date"],
        "to_date": old[-1]["date"],
        "from_ago": old[0]["ago"],
        "to_ago": old[-1]["ago"],
    }
    return dict(forest, trees=kept, merged=merged)

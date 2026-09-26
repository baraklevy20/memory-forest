"""Turn a collection's cards and review log into forest trees.

One tree per Anki day on which new cards were first studied. A tree's stage
comes from how well that day's cards are remembered now (FSRS stability when
available, otherwise the review interval), its crown size from how many cards
it holds, and its health from how many of them are currently being relearned
or were recently forgotten.

This module never imports aqt, so it runs in unit tests and in the dev export
script against a plain sqlite3 connection.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

DAY_SECS = 86400

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

LAPSE_WINDOW_DAYS = 7
HEALTH_THRESHOLDS = (0.12, 0.25, 0.45)  # share of struggling cards → health 1, 2, 3
# Forgetting is part of learning new cards, so trees only yellow once they have matured.
HEALTH_MIN_STAGE = MATURE

# FSRS forgetting curve: R = (1 + factor * elapsed / stability) ** -decay. FSRS-6 gives
# every card its own decay next to its stability; 0.5 is the FSRS-4.5/5 value, for which
# factor works out to the familiar 19/81.
DEFAULT_DECAY = 0.5
# Stability is the number of days until recall falls to this.
STABILITY_RECALL = 0.9

# A break has to be long enough to be worth marking: a fortnight away shows as a pond
# and a gap in the planting, a long weekend does not.
BREAK_DAYS = 14

# Trees drawn one by one. Older ones become the deep forest at the back: a few receding
# bands of canopy instead of hundreds of sprites. At a tree a day this keeps well over a
# year individual, and holds the render cost (and the payload) flat however long you study.
MAX_INDIVIDUAL_TREES = 420

# Revlog types 0-3 are real study (learn, review, relearn, filtered). 4+ are manual
# reschedules and resets, which shouldn't plant or date anything.
STUDY_TYPES = "(0, 1, 2, 3)"

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


@dataclass
class Rows:
    """Everything the forest needs from the database, already fetched."""

    cards: list  # (cid, type, queue, ivl, data_json)
    first_last: dict  # cid -> (first_review_ms, last_review_ms)
    recent_lapses: set  # cids lapsed within LAPSE_WINDOW_DAYS
    review_days: set  # days_ago values that had at least one review
    total_reviews: int
    today_reviews: int


def load_rows(db, day_cutoff: int, dids: list | None = None) -> Rows:
    """Fetch rows with a DB object exposing .all(sql, *args) and .scalar(sql, *args).

    With `dids`, only cards in those decks (a deck and its subdecks) and their reviews count.
    Works with Anki's mw.col.db and with the small sqlite3 wrapper in dev/.
    """
    ids = ",".join(str(int(d)) for d in dids) if dids else ""
    # a card borrowed by a filtered deck has its home deck in odid, which is what
    # Anki's own deck: search follows
    in_decks = f" and (c.did in ({ids}) or c.odid in ({ids}))" if dids else ""
    only = f" and cid in (select id from cards c where 1{in_decks})" if dids else ""
    cards = db.all(
        "select c.id, c.type, c.queue, c.ivl, c.data "
        "from cards c "
        f"where c.type != 0 and c.queue != -1{in_decks}"
    )
    first_last = {
        cid: (first, last)
        for cid, first, last in db.all(
            f"select cid, min(id), max(id) from revlog "
            f"where ease > 0 and type in {STUDY_TYPES}{only} group by cid"
        )
    }
    lapse_since_ms = (day_cutoff - LAPSE_WINDOW_DAYS * DAY_SECS) * 1000
    recent_lapses = {
        row[0] for row in db.all(f"select distinct cid from revlog where type = 1 and ease = 1 and id > ?{only}", lapse_since_ms)
    }
    review_days = {
        row[0]
        for row in db.all(
            f"select distinct (? - 1 - id / 1000) / {DAY_SECS} from revlog "
            f"where ease > 0 and type in {STUDY_TYPES} and id < ?{only}",
            day_cutoff,
            day_cutoff * 1000,
        )
    }
    total = db.scalar(f"select count() from revlog where ease > 0 and type in {STUDY_TYPES}{only}") or 0
    today = db.scalar(
        f"select count() from revlog where ease > 0 and type in {STUDY_TYPES} and id >= ?{only}",
        (day_cutoff - DAY_SECS) * 1000,
    ) or 0
    return Rows(cards, first_last, recent_lapses, review_days, total, today)


def load_deck_days(db, day_cutoff: int, dids: list) -> set:
    """The `ago` values of the trees a deck would grow, without building its forest.

    Deck screens only need to know which of the main forest's trees hold this deck's
    cards, and that is one query instead of the whole pipeline.
    """
    ids = ",".join(str(int(d)) for d in dids)
    rows = db.all(
        "select distinct (? - 1 - coalesce((select min(r.id) from revlog r "
        f"where r.cid = c.id and r.ease > 0 and r.type in {STUDY_TYPES}), c.id) / 1000) / {DAY_SECS} "
        f"from cards c where c.type != 0 and c.queue != -1 and (c.did in ({ids}) or c.odid in ({ids}))",
        day_cutoff,
    )
    return {int(row[0]) for row in rows if row[0] is not None and row[0] >= 0}


def day_search(days_ago_from: int, until_days_ago: int | None = None) -> list:
    """Anki search terms for the cards a tree (or the deep forest) holds.

    `introduced:N` means "first studied within the last N days", so one day is the
    difference of two of them. Suspended cards are excluded because the forest does not
    count them either - without that the tooltip and the browser disagree.
    """
    newest = days_ago_from if until_days_ago is None else until_days_ago
    terms = [f"introduced:{days_ago_from + 1}", "-is:suspended"]
    if newest > 0:
        terms.append(f"-introduced:{newest}")
    return terms


def days_ago(ts_seconds: float, day_cutoff: int) -> int:
    """0 for today's Anki day, 1 for yesterday, ... (respects the rollover hour)."""
    return int((day_cutoff - 1 - ts_seconds) // DAY_SECS)


def day_date(days: int, day_cutoff: int) -> _dt.date:
    """Calendar date of an Anki day (the day that ends at the matching cutoff)."""
    return _dt.datetime.fromtimestamp(day_cutoff - days * DAY_SECS - DAY_SECS // 2).date()


_S_RE = re.compile(r'"s"\s*:\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)')
_DECAY_RE = re.compile(r'"decay"\s*:\s*([0-9.]+(?:[eE][-+]?\d+)?)')


def _retrievability(stability: float, elapsed_days: float, data: str) -> float:
    """How likely this card still is to be recalled, on its own forgetting curve."""
    m = _DECAY_RE.search(data or "")
    try:
        decay = float(m.group(1)) if m else DEFAULT_DECAY
    except ValueError:
        decay = DEFAULT_DECAY
    if not 0 < decay < 1:
        decay = DEFAULT_DECAY
    factor = STABILITY_RECALL ** (-1.0 / decay) - 1
    return (1 + factor * elapsed_days / stability) ** -decay


def _stability(data: str):
    """FSRS memory stability from a card's data blob. Parsing every card's JSON is a
    measurable slice of a whole-collection build, so read the one key directly and only
    fall back to a real parse when the shortcut doesn't match."""
    if not data:
        return None
    m = _S_RE.search(data)
    if m:
        try:
            s = float(m.group(1))
        except ValueError:
            return None
        return s if s > 0 else None
    try:
        s = json.loads(data).get("s")
    except (ValueError, AttributeError):
        return None
    return float(s) if isinstance(s, (int, float)) and s > 0 else None


def _seed(day: int) -> int:
    return int.from_bytes(hashlib.sha1(f"anki-forest-{day}".encode()).digest()[:4], "big") & 0x7FFFFFFF


def _tree(day: int, ago: int, date: str, n: int, stage: int, health: int,
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


def _forest(trees: list, streak: int, longest: int, reviews: int, today_reviews: int) -> dict:
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
    for cid, ctype, _queue, ivl, data in rows.cards:
        first_last = rows.first_last.get(cid)
        first_ms = first_last[0] if first_last else cid
        d = days_ago(first_ms / 1000, day_cutoff)
        if d < 0:
            continue
        c = cohorts.setdefault(d, {"n": 0, "learning": 0, "strengths": [], "struggling": 0, "r": []})
        c["n"] += 1
        stability = _stability(data)
        if ctype == 1:  # still in initial learning
            c["learning"] += 1
        else:
            c["strengths"].append(stability if stability is not None else max(ivl, 0))
        if ctype == 3 or cid in rows.recent_lapses:
            c["struggling"] += 1
        if stability is not None and first_last:
            elapsed = max(0.0, (now_ts - first_last[1] / 1000) / DAY_SECS)
            c["r"].append(_retrievability(stability, elapsed, data))

    trees = []
    for d in sorted(cohorts, reverse=True):  # oldest first
        c = cohorts[d]
        n = c["n"]
        stage = _stage(c["strengths"], c["learning"] / n, d == 0)
        health = _health(c["struggling"] / n) if stage >= HEALTH_MIN_STAGE else 0
        strength = round(median(c["strengths"]), 1) if c["strengths"] else 0
        measured = len(c["r"]) >= n / 2  # most of the day's cards have a forgetting curve
        remembered = sum(c["r"]) / len(c["r"]) if c["r"] else 1 - c["struggling"] / n
        trees.append(_tree(today - d, d, day_date(d, day_cutoff).isoformat(), n, stage, health,
                           remembered, strength, c["struggling"], measured))

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
    return _forest(trees, current, longest, rows.total_reviews, rows.today_reviews)


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


# The test forest: about one day in seven skipped, one long break once there are enough
# trees to spare it, a few dozen cards on most days and a handful on some, and trees
# that have been around long enough grown and occasionally yellowing.
FAKE_SEED = 20260919
FAKE_SKIP_CHANCE = 0.15
FAKE_BREAK_DAYS = 16  # longer than BREAK_DAYS, so there is a pond to see
FAKE_BREAK_MIN_TREES = 60
FAKE_SMALL_DAY_CHANCE = 0.12
FAKE_SMALL_DAY_CARDS, FAKE_DAY_CARDS = (4, 12), (20, 60)
FAKE_STRENGTH = (0.5, 0.75)  # a tree's strength in days: its age times this much, plus up to this much more
FAKE_SAPLING_DAYS = 3
FAKE_HEALTH_ROLLS = (0.88, 0.95, 0.985)  # a matured tree's roll above each of these yellows it a step further
FAKE_STRUGGLING = (0, 0.15, 0.3, 0.5)  # share of a tree's cards struggling, by health
FAKE_REMEMBERED = (0.8, 0.18)  # from this, up to this much more
FAKE_TODAY = 100000  # the scheduler's day number the test forest pretends it is
FAKE_REVIEWS_PER_TREE, FAKE_TODAY_REVIEWS = 700, 200


def fake_forest(n: int, seed: int = FAKE_SEED) -> dict:
    """A made-up forest of n trees, for trying the look at any size (Test forest setting)."""
    import random

    r = random.Random(seed)
    trees, day = [], 0
    ages = []
    while len(ages) < n:
        if day and r.random() < FAKE_SKIP_CHANCE:
            day += 1
            continue
        ages.append(day)
        day += 1
        if n > FAKE_BREAK_MIN_TREES and len(ages) == n // 3:
            day += FAKE_BREAK_DAYS
    ages = sorted(ages, reverse=True)
    today = _dt.date.today()
    prev = None
    for ago in ages:
        count = r.randint(*FAKE_SMALL_DAY_CARDS) if r.random() < FAKE_SMALL_DAY_CHANCE else r.randint(*FAKE_DAY_CARDS)
        strength = ago * (FAKE_STRENGTH[0] + r.random() * FAKE_STRENGTH[1])
        stage = (SEEDLING if ago == 0 else SAPLING if strength < FAKE_SAPLING_DAYS else YOUNG if strength < MATURE_DAYS
                 else MATURE if strength < OLD_DAYS else OLD if strength < ANCIENT_DAYS else ANCIENT)
        roll = r.random()
        health = 0 if stage < HEALTH_MIN_STAGE else sum(1 for step in FAKE_HEALTH_ROLLS if roll >= step)
        t = _tree(FAKE_TODAY - ago, ago, (today - _dt.timedelta(days=ago)).isoformat(), count, stage, health,
                  FAKE_REMEMBERED[0] + r.random() * FAKE_REMEMBERED[1], strength,
                  int(count * FAKE_STRUGGLING[health]))
        if prev is not None and prev - ago > BREAK_DAYS:
            t["gap"] = prev - ago - 1
        prev = ago
        trees.append(t)
    return _forest(trees, n, n, n * FAKE_REVIEWS_PER_TREE, FAKE_TODAY_REVIEWS)  # a streak as long as the forest, so signs that show it can be tried at any size

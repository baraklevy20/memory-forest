"""What the way you study does to the forest, besides the trees themselves.

The Stakes setting decides what missing days costs: nothing (Peaceful), or the whole
forest after a week (Wild) or a single day (Merciless) without reviews. Peaceful only ever
brings good things: a big day of learning leaves flowers, and a songbird comes when a
leech is cured. Wild and Merciless add the rest - leeches bring crows, a week without new
cards lets the grass grow tall, and a pile of overdue reviews brings tumbleweeds, which
blow away the day it is cleared.

Nothing here imports aqt, so it runs in the tests and the dev scripts. Days are counted
as `ago` (0 today, 1 yesterday, ...), as everywhere else in the forest.
"""

from __future__ import annotations

#: Stakes: how many days in a row without reviews the forest survives (None: forever).
STAKES = {"peaceful": None, "wild": 7, "merciless": 1}
STAKES_LABELS = {"peaceful": "Peaceful", "wild": "Wild", "merciless": "Merciless"}
DEFAULT_STAKES = "peaceful"


def _span(days: int) -> str:
    return {1: "a single day", 7: "a whole week"}.get(days, f"{days} days in a row")


# what each level means, for the settings dialog
# (the asteroid, the one lasting cost, by name; the rest each level brings only as a hint:
# it is for the forest to show)
STAKES_NOTES = {
    level: ("Missing days costs nothing, and the forest never scolds you." if grace is None else
            f"Miss {_span(grace)} of reviews and an asteroid wipes out the forest. Bad habits leave marks too, until you fix them.")
    for level, grace in STAKES.items()
}


def calm(level: str) -> bool:
    """Whether these stakes keep the forest to the good things only (Peaceful)."""
    return STAKES.get(level) is None

# how many days after a strike it is still news: the journal says so, and the caption
# offers to play it again
STRIKE_NEWS_DAYS = 7

# A big learning day: at least BIG_DAY_JUMP times, and BIG_DAY_MORE cards more than, the
# most you learned on any day of the BIG_DAY_WINDOW days before it - once there are
# BIG_DAY_HISTORY days of learning to measure against.
BIG_DAY_WINDOW, BIG_DAY_JUMP, BIG_DAY_MORE, BIG_DAY_HISTORY = 14, 1.25, 2, 7

# The grass grows tall after STAGNANT_AFTER days without new cards, while you are still
# reviewing (some review within the last STAGNANT_REVIEWING days); it is at its tallest
# at STAGNANT_FULL.
STAGNANT_AFTER, STAGNANT_FULL, STAGNANT_REVIEWING = 7, 30, 3

# Review hell: more overdue reviews than REVIEW_HELL_TIMES your usual day's reviews (the
# median of the days you studied among the last REVIEW_HELL_USUAL_DAYS), and more than
# REVIEW_HELL_MIN, so a new deck's first backlog is no hell. The tumbleweeds are at their
# most at twice that.
REVIEW_HELL_TIMES, REVIEW_HELL_MIN, REVIEW_HELL_USUAL_DAYS = 2, 30, 30
# The backlog counts as cleared on the day you bring it down to nothing, if review hell was
# on within the BACKLOG_CLEARED_WITHIN days before.
BACKLOG_CLEARED_WITHIN = 7

# A leech is cured once its interval grows mature (study_log.CURED_IVL): its
# crow is gone, and a songbird sits on its tree for CURED_DAYS days.
CURED_DAYS = 7

# how far back a run of missed days is looked for
LOOKBACK_DAYS = 3660


def missed_now(review_days: set) -> int:
    """Days in a row without reviews up to now, counting today while it has none yet."""
    run = 0
    while run < LOOKBACK_DAYS and run not in review_days:
        run += 1
    return run


def _runs(review_days: set, oldest: int) -> list:
    """(oldest missed day, newest missed day) for each run of days without reviews,
    oldest first. Today is left out: it is not over yet."""
    out, start = [], None
    for d in range(oldest, 0, -1):
        if d in review_days:
            if start is not None:
                out.append((start, d + 1))
            start = None
        elif start is None:
            start = d
    if start is not None:
        out.append((start, 1))
    return out


def strikes(review_days: set, level: str, since_ago: int | None) -> list:
    """The days the forest was destroyed, oldest first: in each run of missed days long
    enough, the day it reached the limit. One strike per run, however long the break.
    Only days on or after `since_ago` (when these stakes were chosen) count, so choosing
    Merciless never punishes a break from before."""
    grace = STAKES.get(level)
    if not grace or since_ago is None or not review_days:
        return []
    out = []
    # from the first day you ever studied: the days before it are no break
    for start, end in _runs(review_days, min(max(review_days), since_ago)):
        first = min(start, since_ago)  # missed days before the stakes were chosen don't count
        if first - end + 1 >= grace:
            out.append(first - grace + 1)
    return out


def _streak_before(review_days: set, ago: int) -> int:
    """The run of review days that ended just before the break containing `ago`."""
    d = ago
    while d not in review_days and d < LOOKBACK_DAYS:
        d += 1
    run = 0
    while d + run in review_days:
        run += 1
    return run


def _wipe(trees: list, hits: list, review_days: set) -> tuple:
    """What strikes on the days in `hits` (oldest first) leave: each takes every tree
    planted from the one before it up to its own day. Returns the craters (one per strike
    that took anything: its day, the trees it took, the streak it ended), the latest of
    them with the trees it took (for replaying it), and the trees still standing."""
    craters, standing, prev = [], [], None
    for ago in hits:
        lost = [t for t in trees if t["ago"] >= ago and (prev is None or t["ago"] < prev)]
        prev = ago
        if not lost:
            continue  # nothing had grown since the last one: no crater, nothing to replay
        craters.append({"ago": ago, "lost": len(lost), "streak": _streak_before(review_days, ago)})
        standing = lost
    latest = dict(craters[-1], before=standing) if craters else None
    kept = [t for t in trees if not hits or t["ago"] < hits[-1]]
    if hits and kept and kept[0].get("gap"):
        # the break that struck is marked by its crater: no pond for it in the new forest
        kept[0] = {k: v for k, v in kept[0].items() if k != "gap"}
    return craters, latest, kept


def apply_stakes(trees: list, review_days: set, level: str, since_ago: int | None, past: tuple = ()) -> dict:
    """What the stakes do to this forest.

    `past` holds the days of strikes already remembered, which stand whatever the level is
    now: an asteroid resets everything, and changing the setting afterwards can't undo it.

    Returns `hits` (every strike's day, oldest first, to remember), `trees` (only those
    planted since the last strike), `craters`, `latest` (see _wipe) and `doom` (how near the
    next strike is, or None).
    """
    hits = sorted(set(strikes(review_days, level, since_ago)) | set(past), reverse=True)
    craters, latest, kept = _wipe(trees, hits, review_days)
    doom = None
    grace = STAKES.get(level)
    run = missed_now(review_days)
    counted = min(run, since_ago + 1) if since_ago is not None else 0  # only days since the stakes were chosen
    # nothing to warn about before the first review, nor once this break has struck
    if grace and counted and review_days and not (hits and hits[-1] < run):
        # counting today, while it has no reviews yet: the strike comes when the day ends
        doom = {"missed": counted, "grace": grace, "left": max(0, grace - counted)}
    return {"hits": hits, "trees": kept, "craters": craters, "latest": latest, "doom": doom}


# The Debug tab's timeline passes days on the test forest, each step so many days of one
# kind: studying (reviews and new cards), reviewing only, or away (neither). Between them,
# things happen on the day they are reached: a card turns into a leech, or a leech is cured.
TIMELINE_KINDS = ("study", "review", "away")
TIMELINE_HAPPENINGS = ("leech", "cure")
TIMELINE_MAX_DAYS, TIMELINE_MAX_HAPPENINGS = 3650, 50


def timeline_steps(raw) -> list:
    """The timeline's steps as the config holds them, [kind, how many] each - days, or
    times it happened - keeping only those that make sense (older versions kept strikes
    and bare numbers)."""
    out, total = [], 0
    for step in raw if isinstance(raw, list) else []:
        if not (isinstance(step, list) and len(step) == 2 and type(step[1]) is int):
            continue
        if step[0] in TIMELINE_KINDS:
            n = min(step[1], TIMELINE_MAX_DAYS - total)  # never more days than it holds
            total += max(0, n)
        elif step[0] in TIMELINE_HAPPENINGS:
            n = min(step[1], TIMELINE_MAX_HAPPENINGS)
        else:
            continue
        if n > 0:
            out.append([step[0], n])
    return out


def timeline_days(steps: list) -> tuple:
    """The days the timeline's `steps` pass, as (how many, the days with new cards, the
    days with reviews, and what happened when: (kind, day, how many times) in order), each
    day as `ago`. Every step's days are over: today is the day after the last of them, and
    goes on as it did - with reviews, unless you were away - so a day away is a whole day
    missed, as the Stakes count it. What happens, happens on the next day to come (today,
    after the last step)."""
    days = [s for s in steps if s[0] in TIMELINE_KINDS]
    span = sum(n for _kind, n in days)
    ago, new, reviewed, happened = span, [], set(), []
    for kind, n in steps:
        if kind in TIMELINE_HAPPENINGS:
            happened.append((kind, ago, n))
            continue
        for _ in range(n):
            if kind != "away":
                reviewed.add(ago)
            if kind == "study":
                new.append(ago)
            ago -= 1
    if days and days[-1][0] != "away":
        reviewed.add(0)
    return span, new, reviewed, happened


def mark_big_days(trees: list) -> list:
    """The trees, each whose day was a big jump in new cards (see BIG_DAY_*) copied with
    `big`: what it beat, the most in the two weeks before. The trees given are left alone
    (they may be cached)."""
    out = []
    for i, t in enumerate(trees):
        t = {k: v for k, v in t.items() if k != "big"}
        if i >= BIG_DAY_HISTORY:
            window = [u["n"] for u in trees[:i] if t["ago"] < u["ago"] <= t["ago"] + BIG_DAY_WINDOW]
            best = max(window, default=0)
            if best and t["n"] >= best * BIG_DAY_JUMP and t["n"] >= best + BIG_DAY_MORE:
                t["big"] = best
        out.append(t)
    return out


def stagnation(trees: list, review_days: set) -> float:
    """0, or how tall the grass has grown (up to 1) after weeks without new cards."""
    if not trees or not any(d in review_days for d in range(STAGNANT_REVIEWING)):
        return 0.0  # not reviewing either: that is a break, not coasting
    idle = trees[-1]["ago"]
    if idle < STAGNANT_AFTER:
        return 0.0
    return min(1.0, (idle - STAGNANT_AFTER + 1) / (STAGNANT_FULL - STAGNANT_AFTER + 1))


def usual_reviews(day_counts: list) -> float:
    """Your usual day's reviews: the median of the counts of the days you studied."""
    counts = sorted(n for n in day_counts if n > 0)
    if not counts:
        return 0.0
    mid = len(counts) // 2
    return float(counts[mid]) if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2


def review_hell(overdue: int, usual: float) -> float:
    """0, or how deep in review hell (up to 1) this many overdue reviews put you."""
    limit = max(REVIEW_HELL_MIN, REVIEW_HELL_TIMES * usual)
    if overdue <= limit:
        return 0.0
    return min(1.0, overdue / limit - 1)


def backlog_cleared(overdue: int, today: int, hell_day: int | None, cleared_day: int | None) -> bool:
    """Whether today is the day a backlog was cleared: nothing overdue, review hell on (at
    `hell_day`, the last day it was) within BACKLOG_CLEARED_WITHIN days, and not already
    cleared since. `today`, `hell_day` and `cleared_day` are the scheduler's day numbers."""
    if cleared_day == today:
        return True
    return (overdue == 0 and hell_day is not None and 0 <= today - hell_day <= BACKLOG_CLEARED_WITHIN
            and (cleared_day is None or cleared_day < hell_day))


def calm_trees(trees: list) -> list:
    """The trees without their crows, for Peaceful. The trees given are left alone (they
    may be cached)."""
    return [{k: v for k, v in t.items() if k != "leeches"} if t.get("leeches") else t for t in trees]

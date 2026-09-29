"""What the way you study does to the forest, besides the trees themselves.

The Stakes setting decides what missing days costs: nothing (Peaceful), or the whole
forest after a week (Wild) or a single day (Chaotic) without reviews. Everything else
here is the same at every level - leeches bring crows, a week without new cards lets the
grass grow tall, and a big day of learning leaves flowers.

Nothing here imports aqt, so it runs in the tests and the dev scripts. Days are counted
as `ago` (0 today, 1 yesterday, ...), as everywhere else in the forest.
"""

from __future__ import annotations

#: Stakes: how many days in a row without reviews the forest survives (None: forever).
STAKES = {"peaceful": None, "wild": 7, "chaotic": 1}
STAKES_LABELS = {"peaceful": "Peaceful", "wild": "Wild", "chaotic": "Chaotic"}
DEFAULT_STAKES = "peaceful"


def _span(days: int) -> str:
    return {1: "a single day", 7: "a whole week"}.get(days, f"{days} days in a row")


# what each level means, for the settings dialog
STAKES_NOTES = {
    level: ("Missing days costs nothing: a long break just leaves a pond." if grace is None else
            f"Miss {_span(grace)} of reviews and an asteroid wipes out the forest. "
            + ("It warns you on the day." if grace == 1 else "It warns you as it comes."))
    for level, grace in STAKES.items()
}

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
    Chaotic never punishes a break from before."""
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


def timeline(trees: list, steps: list) -> dict:
    """The Debug group's timeline, played on a made-up forest: `steps` are "strike" or a
    number of days skipped, and `trees` must reach back far enough to hold every skip (its
    newest tree is the day the timeline ends on). Each strike takes what grew since the one
    before, as a real one would, and each crater ages with the days skipped after it.

    Returns what apply_stakes does, each crater also carrying `spot` (where it lands, fixed
    to its step, since each skip moves the dates) and `key` (to remember it was seen).
    """
    pos, hits, step_of = sum(x for x in steps if isinstance(x, int)), [], {}
    for i, step in enumerate(steps):
        if step == "strike":
            hits.append(pos)
            step_of.setdefault(pos, i)
        elif isinstance(step, int):
            pos -= step
    craters, latest, kept = _wipe(trees, hits, {t["ago"] for t in trees})
    for c in craters:
        i = step_of[c["ago"]]
        c.update(spot=f"timeline-{i}", key=f"timeline-{i}-{steps[:i]}")
    if latest:
        latest.update(spot=craters[-1]["spot"], key=craters[-1]["key"])
    return {"hits": hits, "trees": kept, "craters": craters, "latest": latest, "doom": None}


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

"""What the way you study does to the forest, besides the trees themselves.

The Nature setting decides what missing days costs. Peaceful: nothing (a week away leaves a
pond). Wild: from the second day in a row without reviews a fire takes hold, a little more
of the forest each day, and it burns until you have studied for a week again. Merciless:
a single day without reviews and an asteroid wipes out the forest. Nothing of it is
remembered: it is all read from the days you studied, so changing the setting changes it
back and forth.

Peaceful only ever brings good things: a big day of learning leaves flowers, and a
songbird comes when a leech is cured. Wild and Merciless add the rest - leeches bring
crows, a week without new cards lets the grass grow tall, and a pile of overdue reviews
brings tumbleweeds, which blow away the day it is cleared.

Nothing here imports aqt, so it runs in the tests and the dev scripts. Days are counted
as `ago` (0 today, 1 yesterday, ...), as everywhere else in the forest.
"""

from __future__ import annotations

import zlib

NATURE_LABELS = {"peaceful": "Peaceful", "wild": "Wild", "merciless": "Merciless"}
DEFAULT_NATURE = "peaceful"

# what each level means, for the settings dialog (what it costs, by name; the rest each
# level brings only as a hint: it is for the forest to show)
NATURE_NOTES = {
    "peaceful": "Missing days costs nothing, and the forest never scolds you.",
    "wild": "Miss two days of reviews in a row and a fire breaks out, spreading each day you stay away; "
            "a week of study puts it out. Bad habits leave marks too, until you fix them. "
            "Switch back any time and the forest is as it was.",
    "merciless": "Miss a single day of reviews and an asteroid wipes out the forest. "
                 "Bad habits leave marks too, until you fix them. Switch back any time and the forest is as it was.",
}


def nature_level(value) -> str:
    """A setting's value, or the default if it isn't one of the levels."""
    return value if isinstance(value, str) and value in NATURE_LABELS else DEFAULT_NATURE


def calm(level: str) -> bool:
    """Whether this nature keeps the forest to the good things only (Peaceful)."""
    return level == "peaceful"

# how many days after a strike it is still news: the journal says so, the caption offers
# to play it again, and it plays by itself if it hasn't been seen
STRIKE_NEWS_DAYS = 7

# Wild's fire: it breaks out on the FIRE_FROM-th day in a row without reviews, and each day
# away from then on sets FIRE_PER_DAY of the forest burning, up to FIRE_MAX of it. It is out
# once you have studied on FIRE_HEAL_DAYS days since; staying away FIRE_FROM days again before
# that fans it up anew. A single day off pauses it, no more.
FIRE_FROM, FIRE_PER_DAY, FIRE_MAX, FIRE_HEAL_DAYS = 2, 0.05, 0.5, 7

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


def strikes(review_days: set) -> list:
    """The days Merciless's asteroid struck, oldest first: the first day of each run of
    days without reviews since you first studied - one strike a run, however long."""
    if not review_days:
        return []
    return [start for start, _end in _runs(review_days, min(max(review_days), LOOKBACK_DAYS))]


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
    planted from the one before it up to its own day. Returns the latest crater (of the
    strikes that took anything: its day, the trees it took, the streak it ended - the older
    ones lie under the forest that grew since), with the trees it took (for replaying it),
    and the trees still standing."""
    latest, prev = None, None
    for ago in hits:
        lost = [t for t in trees if t["ago"] >= ago and (prev is None or t["ago"] < prev)]
        prev = ago
        if lost:  # nothing had grown since the last one: no crater, nothing to replay
            latest = {"ago": ago, "lost": len(lost), "streak": _streak_before(review_days, ago), "before": lost}
    kept = [t for t in trees if not hits or t["ago"] < hits[-1]]
    if hits and kept and kept[0].get("gap"):
        # the break that struck is marked by its crater: no pond for it in the new forest
        kept[0] = {k: v for k, v in kept[0].items() if k != "gap"}
    return latest, kept


def merciless(trees: list, review_days: set, hold: frozenset = frozenset()) -> dict:
    """What Merciless does to this forest: a strike for every run of missed days, and the
    forest starts again after the latest. Strikes on the days in `hold` don't come (yet:
    the review log may not be all there, another device's reviews still on their way).

    Returns `trees` (only those planted since the last strike), `latest` (its crater, see
    _wipe, or None) and `doom` (today, with no reviews yet after a day you studied: the
    asteroid strikes when the day ends).
    """
    hits = [d for d in strikes(review_days) if d not in hold]
    latest, kept = _wipe(trees, hits, review_days)
    doom = {"missed": 1, "grace": 1, "left": 0} if 0 not in review_days and 1 in review_days else None
    return {"hits": hits, "trees": kept, "latest": latest, "doom": doom}


def fire_state(review_days: set) -> dict | None:
    """Wild's fire as the days studied leave it (see FIRE_*): the `share` of the forest
    burning, the days studied since (`healed`), the longest run `missed` that fanned it,
    `began` (the first missed day, as `ago`) and `epoch` (how many days you had studied
    before it: the same every day, to pick the same trees by), `news` on the days you come
    back to it, and `out` if today is the day it went out. None when nothing is burning."""
    if not review_days:
        return None
    share, healed, run, missed, began, epoch, out = 0.0, 0, 0, 0, None, 0, False
    for d in range(min(max(review_days), LOOKBACK_DAYS), -1, -1):
        if d in review_days:
            run = 0
            if share:
                healed += 1
                if healed >= FIRE_HEAL_DAYS:
                    share, out = 0.0, d == 0
        elif d:  # (today is not over: it is no day missed yet)
            run += 1
            out = False
            if run >= FIRE_FROM:
                if not share:  # a new fire: the forest that stood when the break began
                    began = d + run - 1
                    epoch = sum(1 for x in review_days if x > began)
                    missed = 0
                share = min(FIRE_MAX, max(share, FIRE_PER_DAY * (run - FIRE_FROM + 1)))
                healed, missed = 0, max(missed, run)
    if not share and not out:
        return None
    # news on the days you come back to it: until you have studied, and that day itself
    news = bool(share) and (healed == 0 or (healed == 1 and 0 in review_days))
    return {"share": share, "healed": healed, "missed": missed, "began": began, "epoch": epoch, "out": out, "news": news}


def set_fire(trees: list, review_days: set, limit: int | None = None) -> tuple:
    """The trees with Wild's fire on them, and what the page says of it (or None): each
    burning tree copied with `burn`, 1 while it blazes and less each day you study, down to
    nothing when it is out. The fire takes FIRE_* of the trees that stood when the break
    began - among the newest `limit`, the ones drawn one by one - picked by lot, the same
    ones every day until it is out. The trees given are left alone (they may be cached)."""
    st = fire_state(review_days)
    if st is None:
        return trees, None
    info = {"left": 0, "trees": 0, "missed": st["missed"], "began": st["began"], "out": st["out"], "news": st["news"]}
    if not st["share"]:
        return trees, info
    pool = [t for t in (trees[-limit:] if limit else trees) if t["ago"] > st["began"]]
    n = min(len(pool), max(1, round(st["share"] * len(pool)))) if pool else 0
    lot = lambda t: zlib.crc32(f"fire|{t.get('seed', t['ago'])}|{st['epoch']}".encode())  # noqa: E731
    burning = {id(t) for t in sorted(pool, key=lot)[:n]}
    burn = round(1 - st["healed"] / FIRE_HEAL_DAYS, 3)
    info.update(left=FIRE_HEAL_DAYS - st["healed"], trees=n)
    return [dict(t, burn=burn) if id(t) in burning else t for t in trees], info


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
    missed, as Nature counts it. What happens, happens on the next day to come (today,
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

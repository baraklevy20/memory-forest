"""The Debug tab's study events: each one on demand, on whatever forest is showing, and
the timeline that passes days on the test forest - studying, reviewing only, or away -
for the events that follow from time passing (the asteroid, the fire, the tall grass) to
come as they would. Only while debug is on."""

from __future__ import annotations

import datetime as _dt
import random

from . import events, fake_forest, forest_data
from .events_state import ago_date, strike_payload
from .state import TEST_TREES_DEFAULT, TEST_TREES_MAX, clamp_int, load_state, save_state

# the Debug tab's range for how deep the review hell (in percent); a big day's flowers on
# every DEBUG_BIG_EVERY-th tree, each having "beaten" DEBUG_BIG_BEAT of its own cards (the
# crows, the robins and the tall grass come from what happens on the timeline)
DEBUG_BACKLOG_MAX = 100
DEBUG_BIG_EVERY, DEBUG_BIG_BEAT = 9, 0.7
# the usual day's reviews a made-up review hell is measured against, when there is none to go by
DEBUG_USUAL = 50
DEBUG_CLEARS_MAX = 10 ** 6


def new_timeline_run() -> None:
    """A timeline starts anew: its strikes land elsewhere than the last run's did, rather
    than each day of every run on the same spot as that day of the one before."""
    save_state(dict(load_state(), timeline_run=random.randrange(10 ** 6)))


def _timeline(forest: dict, cfg: dict, steps: list, extras: dict) -> dict:
    """The test forest after the timeline's days have passed (see events.timeline_days):
    a tree for each day studied, and Nature applied as it is to a real forest - so a day
    away on Merciless brings the asteroid, and two on Wild a fire, which a week of study
    puts out. The trees keep their looks as the days go by: each is still the tree of the
    same day."""
    span, new, reviewed, happened = events.timeline_days(steps)
    base = fake_forest.make(clamp_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX))
    shift = span + 1  # the test forest's own today is the day before the timeline began
    now = _dt.date.today()  # each tree dated by its new age, as the days studied since are
    trees = [dict(t, ago=t["ago"] + shift, date=(now - _dt.timedelta(days=t["ago"] + shift)).isoformat()) for t in base["trees"]]
    # every day before the timeline counts as studied: only its own days away cost anything
    days = set(range(shift, max((t["ago"] for t in trees), default=shift) + 1)) | reviewed
    today = fake_forest.FAKE_TODAY + shift  # the scheduler's day number, now
    r = random.Random(fake_forest.FAKE_SEED + 1)  # the same trees for the same days, however many are added
    for ago in sorted(new, reverse=True):
        trees.append(fake_forest.tree(r, today - ago, ago))
    # a pond for each long break on the timeline, before the first tree after it (as build_forest does)
    for resumed, length in forest_data._breaks(days, trees[0]["ago"] if trees else 0):
        after = next((t for t in trees if t["ago"] <= resumed and not t.get("gap")), None)
        if resumed <= span and after is not None:
            after["gap"] = length
    _leeches(trees, happened)
    reviews = None  # all the test forest's
    level = extras["nature"]
    if level == "merciless":
        out = events.merciless(trees, days)
        latest = out["latest"]
        if latest:  # where each lands stays put as days pass: it is that day's, in this run
            run = load_state().get("timeline_run", 0)
            for c in [*out["craters"], latest]:
                c["spot"] = f"timeline-{run}-{today - c['ago']}"
            extras.update(strike_payload(out, f"debug-{latest['spot']}-{len(base['trees'])}", ago_date))
        if out["hits"]:
            days = {d for d in days if d < out["hits"][-1]}
            reviews = len(days) * fake_forest.FAKE_TODAY_REVIEWS  # only a day's worth for each day since
        trees = out["trees"]
        extras["doom"] = out["doom"]
    elif level == "wild":
        trees, extras["fire"] = events.set_fire(trees, days, forest_data.MAX_INDIVIDUAL_TREES)
    extras["stagnation"] = events.stagnation(trees, days)
    return forest_data.rebuild(dict(base, test=True), events.mark_big_days(trees), days, reviews)


def _leeches(trees: list, happened: list) -> None:
    """The timeline's leeches, on the trees they belong to: each card that turns into a
    leech brings a crow to a grown tree standing by then (one without a crow, the newest
    first), and each leech cured takes the oldest crow away, leaving a robin for the
    events.CURED_DAYS days after."""
    crows = []  # the trees holding a leech, oldest leech first
    for kind, ago, n in happened:
        for _ in range(n):
            if kind == "leech":
                standing = [t for t in reversed(trees) if t["ago"] >= ago]  # newest first
                grown = [t for t in standing if t["stage"] >= forest_data.MATURE]
                t = next((t for t in grown if not t.get("leeches")), None) or next(iter(grown or standing), None)
                if t is not None:
                    t["leeches"] = t.get("leeches", 0) + 1
                    crows.append(t)
            elif kind == "cure" and crows:
                t = crows.pop(0)
                t["leeches"] -= 1
                if not t["leeches"]:
                    del t["leeches"]
                if ago < events.CURED_DAYS:
                    t["cured"] = t.get("cured", 0) + 1


def apply(forest: dict, extras: dict, cfg: dict) -> tuple:
    """The Debug tab's switches, on top of what events_state made of the forest. They
    follow Nature as the real events do: Peaceful keeps the crows, the tall grass and the
    tumbleweeds away, and the timeline's days bring the asteroid or the fire only as they
    would."""
    steps = events.timeline_steps(cfg.get("debug_timeline"))
    if steps and forest.get("test"):
        forest = _timeline(forest, cfg, steps, extras)
    trees = [dict(t) for t in forest["trees"]]
    hell = clamp_int(cfg.get("debug_backlog"), 0, 0, DEBUG_BACKLOG_MAX) / DEBUG_BACKLOG_MAX
    clears = clamp_int(cfg.get("debug_backlog_cleared"), 0, 0, DEBUG_CLEARS_MAX)  # how many times "Clear the backlog" was clicked
    if hell or clears:
        backlog = dict(extras.get("backlog") or {"overdue": 0, "usual": 0, "hell": 0.0, "cleared": False})
        if hell:
            usual = backlog["usual"] or DEBUG_USUAL
            limit = max(events.REVIEW_HELL_MIN, events.REVIEW_HELL_TIMES * usual)
            backlog.update(hell=hell, usual=usual, overdue=round(limit * (1 + hell)))
        elif clears:  # the tumbleweeds of the review hell it was blow away, again on each click
            was = clamp_int(cfg.get("debug_backlog_was"), DEBUG_BACKLOG_MAX // 2, 1, DEBUG_BACKLOG_MAX) / DEBUG_BACKLOG_MAX
            backlog.update(cleared=True, was=was, replay=f"debug-{clears}")
        extras["backlog"] = backlog
    if cfg.get("debug_big_days"):
        for t in trees[::DEBUG_BIG_EVERY]:
            t["big"] = max(1, round(t["n"] * DEBUG_BIG_BEAT))  # what the day "beat", for its tooltip
    if events.calm(extras["nature"]):
        trees = events.calm_trees(trees)
        extras["stagnation"] = 0.0
        if extras.get("backlog"):
            extras["backlog"] = dict(extras["backlog"], hell=0.0)
    return dict(forest, trees=trees), extras

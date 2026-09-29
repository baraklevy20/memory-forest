"""The Debug group's study events: each one on demand, on whatever forest is showing, and
the timeline that plays strikes and skipped days forward on the test forest. Only while
debug is on."""

from __future__ import annotations

from . import events, fake_forest, forest_data
from .events_state import ago_date, strike_payload
from .state import TEST_TREES_DEFAULT, TEST_TREES_MAX, clamp_int

# the Debug group's ranges (the settings dialog offers the same): missed days, trees with
# crows, and how tall the grass (in percent); a big day's flowers on every DEBUG_BIG_EVERY-th
# tree, each having "beaten" DEBUG_BIG_BEAT of its own cards
DEBUG_MISSED_MAX, DEBUG_LEECHES_MAX, DEBUG_STAGNATION_MAX = 30, 12, 100
DEBUG_BIG_EVERY, DEBUG_BIG_BEAT = 9, 0.7


def _timeline(forest: dict, cfg: dict, steps: list, extras: dict) -> dict:
    """The test forest after the Debug group's timeline (see events.timeline): a made-up
    forest long enough to hold the days skipped."""
    skipped = sum(x for x in steps if isinstance(x, int))
    full = fake_forest.make(clamp_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX) + skipped)
    out = events.timeline(full["trees"], steps)
    if out["craters"]:
        extras.update(strike_payload(out, "debug-" + out["latest"]["key"], ago_date))
    return forest_data.rebuild(dict(full, test=True), out["trees"], {t["ago"] for t in out["trees"]})


def apply(forest: dict, extras: dict, cfg: dict) -> tuple:
    """The Debug group's switches, on top of what events_state made of the forest."""
    grace = events.STAKES[extras["stakes"]] or events.STAKES["wild"]
    missed = clamp_int(cfg.get("debug_missed"), 0, 0, DEBUG_MISSED_MAX)
    if missed:
        extras["doom"] = {"missed": min(missed, grace), "grace": grace, "left": max(0, grace - missed)}
    steps = cfg.get("debug_timeline")
    if isinstance(steps, list) and steps and forest.get("test"):
        forest = _timeline(forest, cfg, steps, extras)
    trees = [dict(t) for t in forest["trees"]]
    # the newest grown trees, which are always drawn (the oldest may have joined the deep forest)
    for t in [t for t in reversed(trees) if t["stage"] >= forest_data.MATURE][:clamp_int(cfg.get("debug_leeches"), 0, 0, DEBUG_LEECHES_MAX)]:
        t["leeches"] = t.get("leeches") or 1 + t["seed"] % 3
    tall = clamp_int(cfg.get("debug_stagnation"), 0, 0, DEBUG_STAGNATION_MAX)
    if tall:
        extras["stagnation"] = max(extras["stagnation"], tall / DEBUG_STAGNATION_MAX)
    if cfg.get("debug_big_days"):
        for t in trees[::DEBUG_BIG_EVERY]:
            t["big"] = max(1, round(t["n"] * DEBUG_BIG_BEAT))  # what the day "beat", for its tooltip
    return dict(forest, trees=trees), extras

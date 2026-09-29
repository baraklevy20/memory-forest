"""The Debug group's study events: each one on demand, on whatever forest is showing. Only
while debug is on."""

from __future__ import annotations

from . import forest_data
from .state import clamp_int

# the Debug group's ranges (the settings dialog offers the same): trees with crows, and how
# tall the grass (in percent); a big day's flowers on every DEBUG_BIG_EVERY-th tree, each
# having "beaten" DEBUG_BIG_BEAT of its own cards
DEBUG_LEECHES_MAX, DEBUG_STAGNATION_MAX = 12, 100
DEBUG_BIG_EVERY, DEBUG_BIG_BEAT = 9, 0.7


def apply(forest: dict, extras: dict, cfg: dict) -> tuple:
    """The Debug group's switches, on top of the forest and what the page is sent with it."""
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

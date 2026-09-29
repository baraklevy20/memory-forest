"""What the way you study does to the forest, besides the trees themselves: a week and more
without new cards lets the grass grow tall, and a big day of learning leaves flowers.

Nothing here imports aqt, so it runs in the tests and the dev scripts. Days are counted
as `ago` (0 today, 1 yesterday, ...), as everywhere else in the forest.
"""

from __future__ import annotations

# A big learning day: at least BIG_DAY_JUMP times, and BIG_DAY_MORE cards more than, the
# most you learned on any day of the BIG_DAY_WINDOW days before it - once there are
# BIG_DAY_HISTORY days of learning to measure against.
BIG_DAY_WINDOW, BIG_DAY_JUMP, BIG_DAY_MORE, BIG_DAY_HISTORY = 14, 1.25, 2, 7

# The grass grows tall after STAGNANT_AFTER days without new cards, while you are still
# reviewing (some review within the last STAGNANT_REVIEWING days); it is at its tallest
# at STAGNANT_FULL.
STAGNANT_AFTER, STAGNANT_FULL, STAGNANT_REVIEWING = 7, 30, 3


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

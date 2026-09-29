"""What the way you study does to the forest, besides the trees themselves: a week and more
without new cards lets the grass grow tall.

Nothing here imports aqt, so it runs in the tests and the dev scripts. Days are counted
as `ago` (0 today, 1 yesterday, ...), as everywhere else in the forest.
"""

from __future__ import annotations

# The grass grows tall after STAGNANT_AFTER days without new cards, while you are still
# reviewing (some review within the last STAGNANT_REVIEWING days); it is at its tallest
# at STAGNANT_FULL.
STAGNANT_AFTER, STAGNANT_FULL, STAGNANT_REVIEWING = 7, 30, 3


def stagnation(trees: list, review_days: set) -> float:
    """0, or how tall the grass has grown (up to 1) after weeks without new cards."""
    if not trees or not any(d in review_days for d in range(STAGNANT_REVIEWING)):
        return 0.0  # not reviewing either: that is a break, not coasting
    idle = trees[-1]["ago"]
    if idle < STAGNANT_AFTER:
        return 0.0
    return min(1.0, (idle - STAGNANT_AFTER + 1) / (STAGNANT_FULL - STAGNANT_AFTER + 1))

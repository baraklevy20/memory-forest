"""A made-up forest of any size, for trying the look without the history to grow it (the
Test forest setting, only there while debug is on).

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt
import random

try:
    from .forest_data import (
        ANCIENT,
        ANCIENT_DAYS,
        BREAK_DAYS,
        HEALTH_MIN_STAGE,
        MATURE,
        MATURE_DAYS,
        OLD,
        OLD_DAYS,
        SAPLING,
        SEEDLING,
        YOUNG,
        make_forest,
        make_tree,
    )
except ImportError:  # tests and dev scripts import these files as top-level modules
    from forest_data import (
        ANCIENT,
        ANCIENT_DAYS,
        BREAK_DAYS,
        HEALTH_MIN_STAGE,
        MATURE,
        MATURE_DAYS,
        OLD,
        OLD_DAYS,
        SAPLING,
        SEEDLING,
        YOUNG,
        make_forest,
        make_tree,
    )

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


def make(n: int, seed: int = FAKE_SEED) -> dict:
    """A made-up forest of n trees, for trying the look at any size (Test forest setting)."""
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
        t = make_tree(FAKE_TODAY - ago, ago, (today - _dt.timedelta(days=ago)).isoformat(), count, stage, health,
                  FAKE_REMEMBERED[0] + r.random() * FAKE_REMEMBERED[1], strength,
                  int(count * FAKE_STRUGGLING[health]))
        if prev is not None and prev - ago > BREAK_DAYS:
            t["gap"] = prev - ago - 1
        prev = ago
        trees.append(t)
    return make_forest(trees, n, n, n * FAKE_REVIEWS_PER_TREE, FAKE_TODAY_REVIEWS)  # a streak as long as the forest, so signs that show it can be tried at any size


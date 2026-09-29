"""What the events do (events.py)."""

from __future__ import annotations

import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import events


class EventTests(unittest.TestCase):
    @staticmethod
    def trees(agos, n=10):
        return [{"ago": a, "n": n} for a in sorted(agos, reverse=True)]

    def test_big_learning_days(self):
        def big(counts):
            trees = [{"ago": len(counts) - i, "n": n} for i, n in enumerate(counts)]
            marked = events.mark_big_days(trees)
            self.assertFalse(any("big" in t for t in trees))  # the trees given (maybe cached) are left alone
            return [t["n"] for t in marked if t.get("big")]
        week = [1] * 7
        self.assertEqual(big(week + [3, 3, 3]), [3])  # the first 3 only: after it, 3 is no jump
        self.assertEqual(big(week + [3, 6]), [3, 6])  # 6 doubles the new best, the very next day
        self.assertEqual(big(week + [2]), [])  # not two cards more
        self.assertEqual(big([18] * 7 + [25]), [25])  # a 15-20 a day pace: 25 counts
        self.assertEqual(big([1, 1, 5]), [])  # too little history to judge yet
        # only the last BIG_DAY_WINDOW days count: a big day long ago sets no bar
        window = events.BIG_DAY_WINDOW
        self.assertEqual(big([1] * 7 + [50] + [1] * (window - 1) + [5]), [50])  # still in the window
        self.assertEqual(big([1] * 7 + [50] + [1] * window + [5]), [50, 5])

    def test_stagnation_is_reviewing_without_planting(self):
        trees = self.trees([30, 20])  # the newest tree is twenty days old
        self.assertGreater(events.stagnation(trees, {0, 1, 5}), 0)
        self.assertEqual(events.stagnation(trees, {20}), 0)  # not reviewing: a break, not coasting
        self.assertEqual(events.stagnation(self.trees([30, 5]), {0}), 0)  # planted five days ago
        at = events.STAGNANT_AFTER
        self.assertGreater(events.stagnation(self.trees([40, at]), {0}), 0)  # starts on the day
        self.assertEqual(events.stagnation(self.trees([40, at - 1]), {0}), 0)
        self.assertEqual(events.stagnation(self.trees([99, events.STAGNANT_FULL]), {0}), 1.0)

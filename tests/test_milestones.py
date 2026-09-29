"""The animals that move in (milestones.py), and the counts they come for."""

from __future__ import annotations

import unittest

from helpers import CUTOFF, TODAY, card, rows

import fake_forest
import forest_data as fd
import milestones


class MilestoneTests(unittest.TestCase):
    def test_cards_known_well_bring_the_squirrels_the_bear_and_the_eagle(self):
        def keys(mature):
            stats = dict(fake_forest.make(1)["stats"], mature_cards=mature)
            return {v["key"] for v in milestones.visitors(stats) if v["key"] in ("squirrel", "bear", "eagle")}
        self.assertEqual(keys(999), set())
        self.assertEqual(keys(1000), {"squirrel"})
        self.assertEqual(keys(5000), {"squirrel", "bear"})
        self.assertEqual(keys(10000), {"squirrel", "bear", "eagle"})

    def test_a_card_is_known_well_from_three_weeks_on(self):
        forest = fd.build_forest(rows([card(1, ivl=21), card(2, ivl=20), card(3, s=400.0)]), CUTOFF, TODAY)
        self.assertEqual(forest["stats"]["mature_cards"], 2)  # three weeks of interval, or of FSRS stability
        self.assertEqual(sum(t["mature"] for t in forest["trees"]), 2)


if __name__ == "__main__":
    unittest.main()

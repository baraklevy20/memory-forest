"""The animals that move in (milestones.py), and the counts they come for."""

from __future__ import annotations

import datetime as dt
import unittest

from helpers import CUTOFF, TODAY, card, rows

import fake_forest
import forest_data as fd
import i18n
import journal
import milestones


class MilestoneTests(unittest.TestCase):
    def test_a_year_of_streak_and_cards_known_well_bring_the_bear_the_squirrels_and_the_eagle(self):
        def keys(mature, streak=1):
            stats = dict(fake_forest.make(1)["stats"], mature_cards=mature, longest_streak=streak)
            return {v["key"] for v in milestones.visitors(stats) if v["key"] in ("squirrel", "bear", "eagle")}
        self.assertEqual(keys(9999, 729), set())
        self.assertEqual(keys(0, 730), {"bear"})
        self.assertEqual(keys(10000), {"squirrel"})
        self.assertEqual(keys(25000), {"squirrel", "eagle"})

    def test_the_animals_that_have_come_stay_and_are_new_the_day_they_came(self):
        stats = dict(fake_forest.make(1)["stats"], mature_cards=25000)
        arrived = milestones.arrivals(stats, {"fox": 1990}, 2000)
        self.assertEqual(arrived, {"fox": 1990, "squirrel": 2000, "eagle": 2000})
        v = {x["key"]: x["new"] for x in milestones.visitors(dict(stats, mature_cards=0), arrived, 2000)}
        self.assertEqual(v, {"fox": False, "squirrel": True, "eagle": True})  # still here with the numbers gone
        self.assertEqual(milestones.arrivals(stats, {}, None), {"squirrel": None, "eagle": None})  # a first look: quietly

    def test_every_animal_is_announced_the_day_it_comes(self):
        stats = fake_forest.make(1)["stats"]
        for key, _test in milestones.VISITORS:
            forest = dict(fake_forest.make(1), visitors=milestones.visitors(stats, {key: 2000}, 2000))
            line = journal.journal(forest, {"time": "day"}, dt.date(2026, 9, 19), [])
            self.assertEqual(line, i18n.t(milestones.ARRIVED[key]), key)

    def test_the_test_forest_has_every_card_animal_from_420_trees(self):
        keys = {v["key"] for v in fake_forest.make(fake_forest.FAKE_ALL_ANIMALS_TREES)["visitors"]}
        self.assertTrue({"squirrel", "bear", "eagle"} <= keys)
        self.assertFalse({"squirrel", "bear", "eagle"} & {v["key"] for v in fake_forest.make(300)["visitors"]})

    def test_a_card_is_known_well_from_three_weeks_on(self):
        forest = fd.build_forest(rows([card(1, ivl=21), card(2, ivl=20), card(3, s=400.0)]), CUTOFF, TODAY)
        self.assertEqual(forest["stats"]["mature_cards"], 2)  # three weeks of interval, or of FSRS stability
        self.assertEqual(sum(t["mature"] for t in forest["trees"]), 2)


class AnimalDayTests(unittest.TestCase):
    """The day each animal came, for the study calendar (milestones.animal_days)."""

    @staticmethod
    def visitor(key, day=None):
        return {"key": key, "label": key, "why": "", "new": False, "day": day}

    def test_a_streak_animal_came_the_day_the_streak_reached_its_length(self):
        # studied 40 days ago, then every day from 35 days ago: the 30th day in a row is 6 days ago
        reviews = {40: 5, **dict.fromkeys(range(36), 5)}
        got = milestones.animal_days([self.visitor("deer")], [], reviews, TODAY)
        self.assertEqual(got, [{"key": "deer", "ago": 6}])

    def test_the_fox_came_with_the_10000th_review_and_the_heron_with_the_first_pond(self):
        reviews = {9: 6000, 5: 3000, 2: 2000, 0: 10}
        trees = [{"ago": 9}, {"ago": 2, "gap": 6}, {"ago": 0}]
        got = milestones.animal_days([self.visitor("fox"), self.visitor("heron")], trees, reviews, TODAY)
        self.assertEqual([(a["key"], a["ago"]) for a in got], [("fox", 2), ("heron", 2)])

    def test_one_the_history_cannot_date_goes_by_the_day_the_forest_saw_it_come(self):
        got = milestones.animal_days([self.visitor("owl", TODAY - 12), self.visitor("eagle")], [], {}, TODAY)
        self.assertEqual([(a["key"], a["ago"]) for a in got], [("owl", 12)])  # the eagle came unseen

    def test_the_test_forest_makes_up_a_day_for_each_animal_it_cannot_date(self):
        got = milestones.animal_days([self.visitor("owl"), self.visitor("eagle")], [], {}, TODAY, made_up=True)
        self.assertEqual([a["key"] for a in got], ["owl", "eagle"])
        self.assertNotEqual(got[0]["ago"], got[1]["ago"])


if __name__ == "__main__":
    unittest.main()

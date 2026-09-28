"""How days of cards become trees: cohorts, stages, health, ponds and the stats."""

from __future__ import annotations

import datetime as dt
import unittest

from helpers import CUTOFF, DAY, TODAY, card, ms, rows

import fake_forest
import forest_data as fd
import milestones


class CohortTests(unittest.TestCase):
    def test_cards_grouped_by_first_review_day_not_creation(self):
        # three cards created in one bulk import, but studied on different days
        created = ms(100)
        cards = [card(created + i, s=40) for i in range(3)]
        fl = {created: (ms(10), ms(1)), created + 1: (ms(10, 20), ms(1)), created + 2: (ms(5), ms(1))}
        f = fd.build_forest(rows(cards, fl), CUTOFF, TODAY)
        self.assertEqual([(t["ago"], t["n"]) for t in f["trees"]], [(10, 2), (5, 1)])

    def test_rollover_hour_keeps_late_night_study_on_the_same_day(self):
        cards = [card(1, s=30), card(2, s=30)]
        fl = {1: (ms(3, 23), ms(1)), 2: (ms(3, 27), ms(1))}  # 23:00 and 03:00 the next morning
        f = fd.build_forest(rows(cards, fl), CUTOFF, TODAY)
        self.assertEqual([t["ago"] for t in f["trees"]], [3])

    def test_card_without_revlog_falls_back_to_creation_day(self):
        f = fd.build_forest(rows([card(ms(7), s=30)]), CUTOFF, TODAY)
        self.assertEqual(f["trees"][0]["ago"], 7)

    def test_stages_from_fsrs_stability_and_ivl_fallback(self):
        cards = [card(1, s=400), card(2, s=200), card(3, s=30), card(4, s=5), card(5, ivl=45)]
        fl = {i: (ms(20 + i), ms(1)) for i in range(1, 6)}
        stages = {t["ago"]: t["stage"] for t in fd.build_forest(rows(cards, fl), CUTOFF, TODAY)["trees"]}
        self.assertEqual(stages, {21: 5, 22: 4, 23: 3, 24: 2, 25: 3})

    def test_today_is_a_seedling_and_learning_cohort_is_a_sapling(self):
        cards = [card(1, ctype=1, s=1), card(2, ctype=1), card(3, ctype=1), card(4, s=2)]
        fl = {1: (ms(0), ms(0)), 2: (ms(2), ms(0)), 3: (ms(2), ms(0)), 4: (ms(2), ms(0))}
        stages = {t["ago"]: t["stage"] for t in fd.build_forest(rows(cards, fl), CUTOFF, TODAY)["trees"]}
        self.assertEqual(stages, {0: 0, 2: 1})

    def test_health_only_for_matured_trees(self):
        mature = [card(i, s=60) for i in range(1, 11)]
        young = [card(i, s=5) for i in range(11, 21)]
        fl = {i: (ms(40 if i <= 10 else 12), ms(2)) for i in range(1, 21)}
        lapses = {1, 2, 3, 11, 12, 13}  # 30% of each cohort
        trees = {t["ago"]: t for t in fd.build_forest(rows(mature + young, fl, lapses), CUTOFF, TODAY)["trees"]}
        self.assertEqual(trees[40]["health"], 2)
        self.assertEqual(trees[12]["health"], 0)

    def test_fake_forest_sizes(self):
        for n in (0, 3, 150, 1000):
            f = fake_forest.make(n)
            self.assertEqual(len(f["trees"]), n)
            self.assertEqual(f["stats"]["trees"], n)
        self.assertGreaterEqual(fake_forest.make(200)["stats"]["ponds"], 1)

    def test_small_forests_are_never_merged(self):
        for n in (0, 150, fd.MAX_INDIVIDUAL_TREES):
            f = fd.merge_old(fake_forest.make(n))
            self.assertNotIn("merged", f)
            self.assertEqual(len(f["trees"]), n)

    def test_merge_keeps_the_newest_trees_and_sums_the_rest(self):
        full = fake_forest.make(1000)
        f = fd.merge_old(full)
        m = f["merged"]
        self.assertEqual(len(f["trees"]), fd.MAX_INDIVIDUAL_TREES)
        self.assertEqual(m["count"] + len(f["trees"]), 1000)
        self.assertEqual(m["count"] + sum(1 for _ in f["trees"]), full["stats"]["trees"])
        self.assertEqual(m["cards"] + sum(t["n"] for t in f["trees"]), full["stats"]["cards"])
        # the kept trees are the newest ones, and the summary covers everything older
        self.assertEqual(f["trees"][-1]["ago"], full["trees"][-1]["ago"])
        self.assertEqual(m["from_ago"], full["trees"][0]["ago"])
        self.assertGreater(m["from_ago"], m["to_ago"])
        self.assertGreater(m["to_ago"], f["trees"][0]["ago"])
        self.assertEqual(f["stats"], full["stats"])  # the numbers under the forest still count them all

    def test_positions_seeded_by_absolute_day(self):
        cards = [card(1, s=30)]
        a = fd.build_forest(rows(cards, {1: (ms(5), ms(1))}), CUTOFF, TODAY)["trees"][0]
        b = fd.build_forest(rows(cards, {1: (ms(5), ms(1))}), CUTOFF + DAY, TODAY + 1)["trees"][0]
        self.assertEqual((a["seed"], b["ago"]), (b["seed"], a["ago"] + 1))


class StatsTests(unittest.TestCase):
    def test_streaks_survive_until_today_ends(self):
        self.assertEqual(fd._streaks({1, 2, 3, 10, 11}), (3, 3))
        self.assertEqual(fd._streaks({0, 1, 2}), (3, 3))
        self.assertEqual(fd._streaks({2, 3}), (0, 2))

    def test_long_break_becomes_a_pond_before_the_next_tree(self):
        cards = [card(1, s=30), card(2, s=30)]
        fl = {1: (ms(30), ms(1)), 2: (ms(15), ms(1))}
        review_days = set(range(0, 16)) | {30}
        trees = fd.build_forest(rows(cards, fl, review_days=review_days), CUTOFF, TODAY)["trees"]
        self.assertNotIn("gap", trees[0])
        self.assertEqual(trees[1]["gap"], 14)

    def test_a_week_off_is_a_pond_and_a_long_weekend_is_not(self):
        for away, pond in ((fd.BREAK_DAYS - 1, False), (fd.BREAK_DAYS, True)):
            cards = [card(1, s=30), card(2, s=30)]
            back = away + 2  # the first day, the days away, then the day you came back
            fl = {1: (ms(back), ms(1)), 2: (ms(1), ms(1))}
            trees = fd.build_forest(rows(cards, fl, review_days={back, 1, 0}), CUTOFF, TODAY)["trees"]
            self.assertEqual("gap" in trees[1], pond, f"{away} days away")

    def test_visitors_and_arrivals(self):
        s = {"trees": 50, "longest_streak": 30, "streak": 30, "reviews": 10_020, "today_reviews": 40,
             "ancient": 0, "forest_age": 100, "planted_today": True}
        v = {x["key"]: x["new"] for x in milestones.visitors(s)}
        self.assertEqual(v, {"rabbit": True, "deer": True, "fox": True})
        s.update(ponds=1, forest_age=365)
        v = {x["key"]: x["new"] for x in milestones.visitors(s)}
        self.assertTrue(v["heron"] is False and v["cabin"] is True)

    def test_anniversaries(self):
        trees = [{"date": "2025-09-19"}, {"date": "2026-09-19"}, {"date": "2025-09-18"}]
        self.assertEqual(milestones.anniversaries(trees, dt.date(2026, 9, 19)), [0])

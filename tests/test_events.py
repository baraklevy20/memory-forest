"""What the stakes and the other study events do (events.py), and the milestone animals
and forest rebuilds they lean on."""

from __future__ import annotations

import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import events
import fake_forest
import forest_data as fd


class EventTests(unittest.TestCase):
    """What the stakes and the other study events do (events.py)."""

    @staticmethod
    def trees(agos, n=10):
        return [{"ago": a, "n": n} for a in sorted(agos, reverse=True)]

    def test_peaceful_never_strikes(self):
        days = set(range(20, 40)) | {1}  # a long break, then back
        out = events.apply_stakes(self.trees(range(25, 40)), days, "peaceful", 100)
        self.assertEqual((len(out["trees"]), out["craters"], out["doom"]), (15, [], None))

    def test_chaotic_one_missed_day_wipes_the_forest(self):
        days = set(range(0, 40)) - {10}  # one day off, ten days ago (so no tree that day either)
        out = events.apply_stakes(self.trees(days), days, "chaotic", 100)
        self.assertEqual([t["ago"] for t in out["trees"]], list(range(9, -1, -1)))  # only what came after
        self.assertEqual(len(out["craters"]), 1)
        self.assertEqual((out["craters"][0]["ago"], out["craters"][0]["lost"], out["craters"][0]["streak"]), (10, 29, 29))

    def test_wild_forgives_six_days_but_not_seven(self):
        six = set(range(0, 40)) - set(range(10, 16))
        self.assertEqual(events.apply_stakes(self.trees(range(0, 40)), six, "wild", 100)["craters"], [])
        seven = set(range(0, 40)) - set(range(10, 17))
        out = events.apply_stakes(self.trees(range(0, 40)), seven, "wild", 100)
        self.assertEqual([c["ago"] for c in out["craters"]], [10])  # the seventh missed day, the newest of the run

    def test_a_break_that_struck_leaves_a_crater_not_a_pond(self):
        days = set(range(0, 40)) - set(range(10, 20))  # ten days off, on Wild
        trees = self.trees(set(range(0, 40)) - set(range(10, 20)))
        trees[-10]["gap"] = 10  # the first tree after the break, as build_forest marks it
        trees[5]["gap"] = 8  # an older pond, from a break before the stakes were chosen
        out = events.apply_stakes(trees, days, "wild", 100)
        self.assertEqual(len(out["craters"]), 1)
        self.assertFalse(any(t.get("gap") for t in out["trees"]))
        self.assertEqual(trees[-10]["gap"], 10)  # the forest it was given is left as it was
        # on Peaceful the same break is a pond
        self.assertEqual(events.apply_stakes(trees, days, "peaceful", 100)["trees"][-10]["gap"], 10)

    def test_one_crater_per_break_however_long(self):
        days = set(range(0, 60)) - set(range(10, 30))  # twenty days off, on Chaotic
        self.assertEqual(len(events.apply_stakes(self.trees(range(30, 60)), days, "chaotic", 100)["craters"]), 1)

    def test_two_breaks_two_craters_each_with_its_own_losses(self):
        days = set(range(0, 70)) - {31, 62}  # a month, a day off, a month, a day off
        out = events.apply_stakes(self.trees(set(range(0, 70)) - {31, 62}), days, "chaotic", 100)
        self.assertEqual([(c["ago"], c["lost"]) for c in out["craters"]], [(62, 7), (31, 30)])
        self.assertEqual(len(out["latest"]["before"]), 30)  # the trees the latest strike took, to replay it

    def test_only_breaks_after_choosing_the_stakes_count(self):
        days = set(range(0, 40)) - {20}
        out = events.apply_stakes(self.trees(range(0, 40)), days, "chaotic", 5)  # chosen five days ago
        self.assertEqual((out["craters"], len(out["trees"])), ([], 40))

    def test_the_asteroid_approaches_before_it_strikes(self):
        days = set(range(3, 40))  # nothing for the last two days, nor yet today
        doom = events.apply_stakes(self.trees(range(3, 40)), days, "wild", 100)["doom"]
        self.assertEqual((doom["missed"], doom["left"]), (3, 4))
        # on Chaotic the warning is today itself: strike tonight unless you review
        doom = events.apply_stakes(self.trees(range(1, 40)), set(range(1, 40)), "chaotic", 100)["doom"]
        self.assertEqual((doom["missed"], doom["left"]), (1, 0))
        self.assertIsNone(events.apply_stakes(self.trees(range(0, 40)), set(range(0, 40)), "chaotic", 100)["doom"])

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

    def test_missed_now_counts_today_while_it_has_no_reviews(self):
        self.assertEqual(events.missed_now({0, 1}), 0)
        self.assertEqual(events.missed_now({2, 3}), 2)  # yesterday and today so far
        self.assertEqual(events.missed_now(set()), events.LOOKBACK_DAYS)

    def test_a_crater_remembers_the_streak_it_ended(self):
        days = set(range(3, 10)) | set(range(12, 40))  # 28 days, a break at 10-11, then 7 more
        self.assertEqual(events._streak_before(days, 11), 28)
        self.assertEqual(events._streak_before(days, 2), 7)  # a break starting yesterday

    def test_no_strikes_without_stakes_or_reviews(self):
        self.assertEqual(events.strikes({5, 6}, "chaotic", None), [])  # stakes never chosen
        self.assertEqual(events.strikes(set(), "chaotic", 100), [])  # never studied: no break
        out = events.apply_stakes([], set(), "chaotic", 10)
        self.assertEqual((out["trees"], out["craters"], out["doom"]), ([], [], None))  # and no endless warning

    def test_a_strike_with_nothing_grown_since_leaves_no_crater(self):
        days = set(range(0, 40)) - {10, 20}
        trees = self.trees(set(range(21, 40)))  # nothing planted between the two strikes
        out = events.apply_stakes(trees, days, "chaotic", 100)
        self.assertEqual(out["hits"], [20, 10])
        self.assertEqual([c["ago"] for c in out["craters"]], [20])
        self.assertEqual(out["latest"]["ago"], 20)

    def test_no_warning_once_the_break_has_struck(self):
        days = set(range(12, 40))  # eleven days and counting, on Wild: struck at day 5
        out = events.apply_stakes(self.trees(range(12, 40)), days, "wild", 100)
        self.assertEqual((out["hits"], out["doom"]), ([5], None))

    def test_a_strike_stands_whatever_the_stakes_become(self):
        days = set(range(0, 40)) - {10}
        trees = self.trees(days)
        struck = events.apply_stakes(trees, days, "chaotic", 100)["hits"]
        for level, since in (("peaceful", 0), ("wild", 0), ("chaotic", 0)):  # changed today
            out = events.apply_stakes(trees, days, level, since, past=struck)
            self.assertEqual(([c["ago"] for c in out["craters"]], len(out["trees"])), ([10], 10), level)

    def test_the_timeline_plays_strikes_and_skipped_days(self):
        trees = self.trees(range(0, 60))
        # strike, a week, strike again at once (nothing grown since: no second crater), a day
        out = events.timeline(trees, ["strike", 7, "strike", "strike", 1])
        self.assertEqual([(c["ago"], c["lost"], c["spot"]) for c in out["craters"]], [(8, 52, "timeline-0"), (1, 7, "timeline-2")])
        self.assertEqual([t["ago"] for t in out["trees"]], [0])  # the day skipped since
        self.assertEqual(out["latest"]["key"], "timeline-2-['strike', 7]")
        self.assertEqual(len(out["latest"]["before"]), 7)
        self.assertEqual(events.timeline(trees, [7])["craters"], [])

    def test_rebuild_counts_again_from_the_trees_left(self):
        forest = dict(fake_forest.make(40), lit_count=40, review_days={1, 2})
        for t in forest["trees"]:
            t["dim"] = t["ago"] % 2 == 0
        kept = forest["trees"][-10:]
        out = fd.rebuild(forest, kept, set(range(0, 10)))
        self.assertEqual((out["stats"]["trees"], out["stats"]["streak"]), (10, 10))
        self.assertEqual(out["lit_count"], sum(1 for t in kept if not t["dim"]))
        self.assertEqual(out["review_days"], {1, 2})  # kept for the stakes

    def test_stagnation_is_reviewing_without_planting(self):
        trees = self.trees([30, 20])  # the newest tree is twenty days old
        self.assertGreater(events.stagnation(trees, {0, 1, 5}), 0)
        self.assertEqual(events.stagnation(trees, {20}), 0)  # not reviewing: a break, not coasting
        self.assertEqual(events.stagnation(self.trees([30, 5]), {0}), 0)  # planted five days ago
        at = events.STAGNANT_AFTER
        self.assertGreater(events.stagnation(self.trees([40, at]), {0}), 0)  # starts on the day
        self.assertEqual(events.stagnation(self.trees([40, at - 1]), {0}), 0)
        self.assertEqual(events.stagnation(self.trees([99, events.STAGNANT_FULL]), {0}), 1.0)

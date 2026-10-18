"""How a day's cards become a tree, and the forest's numbers, at their edges (forest_data.py):
crown sizes, health steps, saplings, ponds at the ends, streaks and days off."""

from __future__ import annotations

import datetime as dt
import unittest

from helpers import CUTOFF, TODAY, card, ms, rows

import forest_data as fd


def tree_of(cards, first=40, lapses=()):
    """The one tree `cards` grow, all first studied `first` days ago and last seen two days ago."""
    fl = {c[0]: (ms(first), ms(2)) for c in cards}
    return fd.build_forest(rows(cards, fl, lapses), CUTOFF, TODAY)["trees"][0]


class CrownTests(unittest.TestCase):
    def test_a_crown_grows_at_15_and_at_40_cards(self):
        for n, size in ((1, 0), (14, 0), (15, 1), (39, 1), (40, 2), (500, 2)):
            self.assertEqual(fd.make_tree(1, 1, "2026-09-18", n, fd.MATURE, 0, 1, 30, 0)["size"], size, n)

    def test_about_a_third_of_the_trees_are_conifers_and_always_the_same_ones(self):
        kinds = [fd.make_tree(day, 0, "", 1, 0, 0, 1, 0, 0)["kind"] for day in range(3000)]
        self.assertTrue(0.28 < sum(kinds) / len(kinds) < 0.40)
        self.assertEqual(kinds, [fd.make_tree(day, 5, "", 9, 3, 1, 0.5, 9, 2)["kind"] for day in range(3000)])


class HealthTests(unittest.TestCase):
    def test_each_step_of_yellowing_starts_at_its_share(self):
        for share, level in ((0, 0), (0.11, 0), (0.12, 1), (0.24, 1), (0.25, 2), (0.44, 2), (0.45, 3), (1.0, 3)):
            self.assertEqual(fd._health(share), level, share)

    def test_a_card_being_relearned_struggles(self):
        cards = [card(1, ctype=3, s=60)] + [card(i, s=60) for i in range(2, 5)]  # one in four relearning
        tree = tree_of(cards)
        self.assertEqual((tree["struggling"], tree["health"]), (1, 2))

    def test_a_tree_without_forgetting_curves_guesses_its_recall_from_the_struggling(self):
        cards = [card(i, ivl=60) for i in range(1, 5)]  # no FSRS: intervals only
        tree = tree_of(cards, lapses={1})
        self.assertFalse(tree["measured"])
        self.assertEqual(tree["remembered"], 0.75)
        self.assertEqual(tree["strength"], 60)


class StageTests(unittest.TestCase):
    def test_today_s_tree_is_a_seedling_however_well_it_is_known(self):
        cards = [card(1, s=900)]
        tree = fd.build_forest(rows(cards, {1: (ms(0), ms(0))}), CUTOFF, TODAY)["trees"][0]
        self.assertEqual(tree["stage"], fd.SEEDLING)

    def test_a_day_mostly_still_learning_is_a_sapling_and_half_is_not(self):
        half = [card(1, ctype=1), card(2, s=30)]
        most = [card(1, ctype=1), card(2, ctype=1), card(3, s=30)]
        self.assertEqual(tree_of(half)["stage"], fd.MATURE)
        self.assertEqual(tree_of(most)["stage"], fd.SAPLING)

    def test_the_stage_steps_at_three_weeks_half_a_year_and_a_year(self):
        for s, stage in ((20.9, fd.YOUNG), (21, fd.MATURE), (179, fd.MATURE), (180, fd.OLD), (364, fd.OLD), (365, fd.ANCIENT)):
            self.assertEqual(tree_of([card(1, s=s)])["stage"], stage, s)

    def test_the_cards_known_well_are_counted_per_tree_and_in_all(self):
        cards = [card(1, s=21), card(2, s=20), card(3, ivl=100), card(4, ctype=1)]
        forest = fd.build_forest(rows(cards, {c[0]: (ms(30), ms(2)) for c in cards}), CUTOFF, TODAY)
        self.assertEqual((forest["trees"][0]["mature"], forest["stats"]["mature_cards"]), (2, 2))


class PondEdgeTests(unittest.TestCase):
    def forest(self, firsts: dict, review_days: set) -> list:
        cards = [card(cid, s=30) for cid in firsts]
        fl = {cid: (ms(d), ms(1)) for cid, d in firsts.items()}
        return fd.build_forest(rows(cards, fl, review_days=review_days), CUTOFF, TODAY)["trees"]

    def test_a_break_still_going_on_is_no_pond_yet(self):
        trees = self.forest({1: 40, 2: 30}, set(range(30, 41)))  # nothing studied for 29 days, to today
        self.assertFalse(any("gap" in t for t in trees))

    def test_a_break_after_the_last_tree_marks_that_tree(self):
        trees = self.forest({1: 40, 2: 30}, set(range(30, 41)) | set(range(0, 11)))
        self.assertEqual([t.get("gap") for t in trees], [None, 19])
        date = lambda d: fd.day_date(d, CUTOFF).isoformat()  # noqa: E731
        self.assertEqual((trees[1]["gap_from"], trees[1]["gap_to"]), (date(29), date(11)))

    def test_ponds_are_counted_in_the_stats(self):
        cards = [card(1, s=30), card(2, s=30)]
        fl = {1: (ms(30), ms(1)), 2: (ms(15), ms(1))}
        forest = fd.build_forest(rows(cards, fl, review_days=set(range(0, 16)) | {30}), CUTOFF, TODAY)
        self.assertEqual(forest["stats"]["ponds"], 1)

    def test_ponds_marked_afresh_from_other_days_lose_their_old_marks(self):
        trees = self.forest({1: 40, 2: 30, 3: 10}, {40} | set(range(0, 31)))  # one pond, before the 30-day tree
        self.assertEqual([t.get("gap") for t in trees], [None, 9, None])
        date = lambda d: fd.day_date(d, CUTOFF).isoformat()  # noqa: E731
        again = fd.with_ponds(trees, set(range(30, 41)) | set(range(0, 11)), date)  # (a deck's: the main forest's days)
        self.assertEqual([t.get("gap") for t in again], [None, None, 19])
        self.assertEqual(trees[1]["gap"], 9)  # (copies: the forest it came from is as it was)
        self.assertEqual(fd.with_ponds([], {1}, date), [])


class RebuildTests(unittest.TestCase):
    def test_a_lit_forest_rebuilt_counts_the_lit_trees_left(self):
        cards = [card(i, s=30) for i in (1, 2, 3)]
        fl = {1: (ms(9), ms(1)), 2: (ms(5), ms(1)), 3: (ms(2), ms(1))}
        forest = fd.build_forest(rows(cards, fl, review_days=set(range(10))), CUTOFF, TODAY)
        lit = dict(forest, trees=[dict(t, dim=t["ago"] == 5) for t in forest["trees"]], lit_count=2)
        out = fd.rebuild(lit, lit["trees"][1:])
        self.assertEqual((out["stats"]["trees"], out["lit_count"]), (2, 1))
        self.assertNotIn("lit_count", fd.rebuild(forest, forest["trees"][1:]))

    def test_rebuilt_without_days_its_streak_is_its_own(self):
        cards = [card(1, s=30)]
        forest = fd.build_forest(rows(cards, {1: (ms(3), ms(1))}, review_days={0, 1, 2, 3}), CUTOFF, TODAY)
        self.assertEqual(fd.rebuild(forest, forest["trees"])["stats"]["streak"], 4)
        self.assertEqual(fd.rebuild(forest, [], review_days=set())["stats"]["streak"], 0)


class MergeEdgeTests(unittest.TestCase):
    def test_one_tree_past_the_limit_goes_into_the_deep_forest(self):
        trees = [fd.make_tree(TODAY - d, d, fd.day_date(d, CUTOFF).isoformat(), 3, fd.MATURE, 0, 1, 30, 0)
                 for d in range(fd.MAX_INDIVIDUAL_TREES, -1, -1)]
        out = fd.merge_old(fd.make_forest(trees, 0, 0, 0, 0))
        self.assertEqual((len(out["trees"]), out["merged"]["count"]), (fd.MAX_INDIVIDUAL_TREES, 1))
        self.assertEqual((out["merged"]["from_ago"], out["merged"]["to_ago"]), (fd.MAX_INDIVIDUAL_TREES,) * 2)


class StreakEdgeTests(unittest.TestCase):
    def test_no_reviews_is_no_streak(self):
        self.assertEqual(fd._streaks(set()), (0, 0))
        self.assertEqual(fd._streaks(set(), frozenset({1, 2, 3})), (0, 0))  # (nothing due is no study)

    def test_studied_only_today_is_one(self):
        self.assertEqual(fd._streaks({0}), (1, 1))

    def test_yesterday_missed_ends_it_however_long_it_was(self):
        self.assertEqual(fd._streaks(set(range(2, 400))), (0, 398))

    def test_days_with_nothing_due_join_the_longest_streak_too(self):
        self.assertEqual(fd._streaks({10, 11, 12, 15, 16}, frozenset({13, 14})), (0, 5))

    def test_a_free_today_still_waits_for_today(self):
        self.assertEqual(fd._streaks({1, 2}, frozenset({0})), (2, 2))


class DaysOffEdgeTests(unittest.TestCase):
    def test_nothing_is_passed_over_without_a_day_chosen_or_any_study(self):
        today = dt.date(2026, 10, 14)
        self.assertEqual(fd.days_off(set(range(1, 30)) - {4}, frozenset(), 2, None, today, 1), frozenset())
        self.assertEqual(fd.days_off(set(), frozenset(), 2, 60, today, 1), frozenset())

    def test_the_days_before_your_first_review_are_none(self):
        today = dt.date(2026, 10, 14)
        studied = set(range(1, 11)) - {5}  # first studied 10 days ago
        self.assertEqual(fd.days_off(studied, frozenset(), 2, 60, today, 1), frozenset({5}))

    def test_the_week_holding_a_leap_day_is_seven_days(self):
        today = dt.date(2028, 3, 8)  # a Wednesday
        missed = {9, 8, 7, 2}  # Mon 28 Feb, Tue 29 Feb, Wed 1 Mar; Mon 6 Mar
        studied = set(range(1, 40)) - missed
        self.assertEqual(fd.days_off(studied, frozenset(), 2, 60, today, 1), frozenset({9, 8, 2}))

    def test_the_week_turns_at_the_year_s_end_as_any_week(self):
        today = dt.date(2027, 1, 6)  # a Wednesday; Thu 31 Dec 2026 and Fri 1 Jan 2027 are one Monday week
        missed = {6, 5}
        studied = set(range(1, 40)) - missed
        self.assertEqual(fd.days_off(studied, frozenset(), 1, 60, today, 1), frozenset({6}))


if __name__ == "__main__":
    unittest.main()

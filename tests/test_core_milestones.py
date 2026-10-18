"""The animals' arrival days, the journal's lines and the heatmap's marked days, at their edges
(milestones.py, journal.py, marks.py)."""

from __future__ import annotations

import datetime as dt
import unittest

from helpers import TODAY

import journal
import marks
import milestones

STATS = {"trees": 10, "longest_streak": 5, "streak": 5, "reviews": 100, "today_reviews": 10, "ancient": 0,
         "forest_age": 30, "planted_today": False, "ponds": 0, "mature_cards": 0}


def new_ones(**stats) -> dict:
    """{animal: whether it is new today} for a forest with these numbers and nothing remembered."""
    return {v["key"]: v["new"] for v in milestones.visitors(dict(STATS, **stats))}


class ArrivedTodayTests(unittest.TestCase):
    """The test forest has nothing remembered: an animal is new the day its numbers say it came."""

    def test_the_fox_is_new_the_day_the_10000th_review_is_made(self):
        self.assertTrue(new_ones(reviews=10_010, today_reviews=20)["fox"])
        self.assertFalse(new_ones(reviews=10_030, today_reviews=20)["fox"])  # (passed yesterday)
        self.assertTrue(new_ones(reviews=10_000, today_reviews=1)["fox"])  # (the 10,000th itself)

    def test_a_streak_animal_is_new_only_on_the_day_the_streak_first_reaches_it(self):
        self.assertTrue(new_ones(streak=30, longest_streak=30)["deer"])
        self.assertFalse(new_ones(streak=30, longest_streak=45)["deer"])  # (a streak that long once before)
        self.assertTrue(new_ones(streak=100, longest_streak=100)["stag"])
        self.assertTrue(new_ones(streak=730, longest_streak=730)["bear"])
        self.assertFalse(new_ones(streak=731, longest_streak=731)["bear"])

    def test_the_cabin_is_new_on_the_first_birthday_only(self):
        self.assertTrue(new_ones(forest_age=365)["cabin"])
        self.assertFalse(new_ones(forest_age=366)["cabin"])
        self.assertNotIn("cabin", new_ones(forest_age=364))

    def test_the_rabbit_is_new_the_day_the_50th_tree_is_planted(self):
        self.assertTrue(new_ones(trees=50, planted_today=True)["rabbit"])
        self.assertFalse(new_ones(trees=50, planted_today=False)["rabbit"])
        self.assertFalse(new_ones(trees=51, planted_today=True)["rabbit"])

    def test_an_animal_with_no_day_to_tell_is_never_new_unremembered(self):
        got = new_ones(ancient=1, ponds=1, mature_cards=25_000)
        self.assertEqual((got["owl"], got["heron"], got["squirrel"], got["eagle"]), (False,) * 4)


class AnimalDayEdgeTests(unittest.TestCase):
    @staticmethod
    def visitor(key, day=None):
        return {"key": key, "label": key, "why": "", "new": False, "day": day}

    def test_the_rabbit_came_with_the_50th_tree(self):
        trees = [{"ago": 200 - 3 * i} for i in range(60)]
        got = milestones.animal_days([self.visitor("rabbit")], trees, {}, TODAY)
        self.assertEqual([a["ago"] for a in got], [200 - 3 * 49])

    def test_the_cabin_came_a_year_after_the_first_tree(self):
        got = milestones.animal_days([self.visitor("cabin")], [{"ago": 400}], {}, TODAY)
        self.assertEqual([a["ago"] for a in got], [400 - milestones.CABIN_AGE_DAYS])

    def test_one_seen_coming_later_than_its_history_says_goes_by_its_history(self):
        reviews = dict.fromkeys(range(40), 3)  # 40 days running: the 30th was 10 days ago
        got = milestones.animal_days([self.visitor("deer", TODAY - 2)], [], reviews, TODAY)
        self.assertEqual([a["ago"] for a in got], [10])

    def test_a_streak_broken_and_begun_again_dates_the_first_time_it_got_there(self):
        reviews = {**dict.fromkeys(range(100, 135), 1), **dict.fromkeys(range(0, 40), 1)}
        got = milestones.animal_days([self.visitor("deer")], [], reviews, TODAY)
        self.assertEqual([a["ago"] for a in got], [105])  # (134 down to 105 is 30 days)

    def test_a_day_ahead_of_today_is_left_out(self):
        got = milestones.animal_days([self.visitor("owl", TODAY + 3)], [], {}, TODAY)
        self.assertEqual(got, [])

    def test_a_day_with_no_reviews_counted_is_no_day_of_a_streak(self):
        reviews = {**dict.fromkeys(range(31), 2), 15: 0}  # (a day kept with none: a deleted card's undo, say)
        got = milestones.animal_days([self.visitor("deer")], [], reviews, TODAY)
        self.assertEqual(got, [])


class JournalEdgeTests(unittest.TestCase):
    MOOD = {"weather": "clear", "special": "none", "time": "day"}

    def say(self, forest_trees=None, visitors=(), evs=(), ann=(), today=dt.date(2026, 9, 19), mood=None, **stats):
        s = dict(STATS, today_cards=0)
        s.update(stats)
        forest = {"trees": [{"date": "2024-09-19", "n": 30, "ago": 0}] if forest_trees is None else forest_trees, "stats": s,
                  "visitors": list(visitors)}
        return journal.journal(forest, mood or self.MOOD, today, list(ann), list(evs))

    def test_an_empty_forest_says_where_the_first_tree_will_grow(self):
        self.assertEqual(self.say(forest_trees=[]), "Study some new cards and your first tree will take root here.")

    def test_the_cabin_has_its_own_line(self):
        cabin = {"key": "cabin", "label": "a cabin", "why": "", "new": True}
        self.assertEqual(self.say(visitors=[cabin]),
                         "A little cabin now stands at the edge of your forest: a year since your first tree.")

    def test_the_first_tree_and_the_tenth_count_their_cards(self):
        self.assertEqual(self.say(trees=1, planted_today=True, today_cards=1), "Your first tree. It holds 1 card.")
        self.assertEqual(self.say(trees=10, planted_today=True, today_cards=1), "Your 10th tree, planted today with 1 new card.")
        self.assertEqual(self.say(trees=25, planted_today=True, today_cards=7), "Your 25th tree, planted today with 7 new cards.")

    def test_a_tree_milestone_comes_before_a_streak_one(self):
        self.assertIn("100th tree", self.say(trees=100, streak=30, planted_today=True, today_cards=3))

    def test_an_anniversary_counts_its_years_and_names_its_day(self):
        self.assertEqual(self.say(ann=[0]), "The tree you planted on 19 Sep 2024 turned 2 years old today.")

    def test_a_new_ancient_tree_comes_before_an_anniversary(self):
        self.assertEqual(self.say(ann=[0], evs=["new_ancient"]), "One of your trees became ancient today.")

    def test_a_harvest_moon_on_a_clear_night(self):
        night = {"weather": "clear", "special": "none", "time": "night"}
        self.assertEqual(self.say(evs=["harvest_moon"], mood=night), "A harvest moon rises over your forest's anniversary.")


class MarkEdgeTests(unittest.TestCase):
    class Col:
        def __init__(self, kept=None):
            self.conf = {} if kept is None else {marks.KEY: kept}

        def get_config(self, key, default=None):
            return self.conf.get(key, default)

        def set_config(self, key, value):
            self.conf[key] = value

    def test_a_collection_that_can_t_say_has_no_marks(self):
        class Broken:
            def get_config(self, *_a):
                raise RuntimeError("closed")
        self.assertEqual(marks.important_days(Broken()), [])
        self.assertEqual(marks.important_days(self.Col({"day": "2026-11-02"})), [])  # (not a list)

    def test_a_day_kept_twice_is_one_mark_the_later_one(self):
        col = self.Col(["2026-11-02", {"day": "2026-11-02", "icon": "exam", "name": "Final"}])
        self.assertEqual(marks.important_days(col), [{"day": "2026-11-02", "icon": "exam", "name": "Final"}])

    def test_marking_a_day_again_changes_it_and_unmarking_an_unmarked_day_changes_nothing(self):
        col = self.Col()
        marks.set_mark(col, "2026-11-02", "exam", "Final")
        marks.set_mark(col, "2026-11-02", "trip")
        self.assertEqual(marks.important_days(col), [{"day": "2026-11-02", "icon": "trip", "name": ""}])
        marks.unmark(col, "2026-12-25")
        self.assertEqual(len(marks.important_days(col)), 1)

    def test_a_name_that_is_not_text_is_no_name(self):
        col = self.Col([{"day": "2026-11-02", "icon": "star", "name": 42}])
        self.assertEqual(marks.important_days(col)[0]["name"], "")

    def test_a_leap_day_can_be_marked_and_a_day_that_never_was_cannot(self):
        col = self.Col()
        marks.set_mark(col, "2028-02-29")
        self.assertEqual(marks.important_days(col)[0]["day"], "2028-02-29")
        with self.assertRaises(ValueError):
            marks.set_mark(col, "2027-02-29")


class LeapDayAnniversaryTests(unittest.TestCase):
    TREES = [{"date": "2024-02-29"}, {"date": "2025-02-28"}, {"date": "2025-03-01"}]

    def test_a_tree_planted_on_29_feb_has_its_anniversary_on_28_feb_in_other_years(self):
        self.assertEqual(milestones.anniversaries(self.TREES, dt.date(2027, 2, 28)), [0, 1])

    def test_in_a_leap_year_it_keeps_its_own_day(self):
        self.assertEqual(milestones.anniversaries(self.TREES, dt.date(2028, 2, 28)), [1])
        self.assertEqual(milestones.anniversaries(self.TREES, dt.date(2028, 2, 29)), [0])

    def test_1_march_is_only_its_own_trees(self):
        self.assertEqual(milestones.anniversaries(self.TREES, dt.date(2027, 3, 1)), [2])


if __name__ == "__main__":
    unittest.main()

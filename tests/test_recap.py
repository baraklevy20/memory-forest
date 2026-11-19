"""Your year in the forest (recap.py, recap_actions.py): which year is offered when, the year's numbers
by the heatmap's own rules, the animals of the year by the day each was earned, the rhythm's word, what
was answered, and the page's message for each of it."""

from __future__ import annotations

import base64
import datetime as dt
import importlib
import os
import random
import tempfile
import unittest
from unittest import mock

from fake_anki import addon, reset

recap = importlib.import_module(addon.__name__ + ".recap")
recap_actions = importlib.import_module(addon.__name__ + ".recap_actions")
actions = addon.actions
D = dt.date
MODULE = addon.state.MODULE
YEAR_END, LONG_AGO = D(2026, 12, 31), D(2020, 1, 1)


def days(first: D, last: D):
    d = first
    while d <= last:
        yield d
        d += dt.timedelta(days=1)


class WindowTests(unittest.TestCase):
    def test_the_year_is_offered_from_mid_december_to_mid_january(self):
        self.assertIsNone(recap.year_for(D(2026, 12, 14)))
        self.assertEqual(recap.year_for(D(2026, 12, 15)), 2026)
        self.assertEqual(recap.year_for(D(2026, 12, 31)), 2026)
        self.assertEqual(recap.year_for(D(2027, 1, 1)), 2026)
        self.assertEqual(recap.year_for(D(2027, 1, 15)), 2026)
        self.assertIsNone(recap.year_for(D(2027, 1, 16)))
        self.assertIsNone(recap.year_for(D(2026, 6, 15)))


class StreakTests(unittest.TestCase):
    def test_a_day_with_nothing_due_passes_without_growing_the_streak(self):
        studied = {D(2026, 3, 1), D(2026, 3, 2), D(2026, 3, 4)}
        self.assertEqual(recap.runs(studied, {D(2026, 3, 3)}, D(2026, 3, 1), D(2026, 3, 31)), [(3, D(2026, 3, 1), D(2026, 3, 4))])

    def test_a_missed_day_with_cards_due_ends_it(self):
        studied = {D(2026, 3, 1), D(2026, 3, 2), D(2026, 3, 4)}
        self.assertEqual(recap.runs(studied, set(), D(2026, 3, 1), D(2026, 3, 31)),
                         [(2, D(2026, 3, 1), D(2026, 3, 2)), (1, D(2026, 3, 4), D(2026, 3, 4))])

    def test_a_streak_is_cut_at_the_years_edges(self):
        # (a streak running on from December counts its days in this year only)
        studied = set(days(D(2025, 12, 20), D(2026, 1, 5)))
        n = recap.numbers(2026, dict.fromkeys(studied, 5), {}, [], set(), D(2026, 12, 31))
        self.assertEqual(n["bestStreak"], [5, "2026-01-01", "2026-01-05"])
        self.assertEqual(n["studied"], 5)


class NumbersTests(unittest.TestCase):
    def setUp(self):
        self.reviews = {D(2026, 1, 3): 10, D(2026, 1, 4): 40, D(2026, 2, 10): 40, D(2026, 2, 11): 5, D(2025, 12, 31): 999, D(2026, 2, 12): 0}
        self.trees = [{"date": "2025-12-31", "n": 50}, {"date": "2026-01-03", "n": 7}, {"date": "2026-02-10", "n": 3}]
        self.n = recap.numbers(2026, self.reviews, {D(2026, 1, 3): 600, D(2025, 12, 31): 9999}, self.trees, set(), D(2026, 12, 31),
                               [("deer", D(2026, 2, 10)), ("cabin", D(2026, 3, 1)), ("fox", D(2025, 11, 2)), ("rabbit", D(2026, 1, 4))])

    def test_the_year_alone_is_counted(self):
        n = self.n
        self.assertEqual((n["studied"], n["reviews"], n["seconds"], n["newCards"], n["trees"]), (4, 95, 600, 10, 2))
        self.assertEqual(n["first"], "2026-01-03")
        self.assertEqual(n["months"][:3], [50, 45, 0])

    def test_best_day_and_month_take_the_earliest_of_a_tie(self):
        self.assertEqual(self.n["bestDay"], ["2026-01-04", 40])
        self.assertEqual(self.n["bestMonth"], [0, 50, 2])

    def test_the_years_animals_in_order_without_buildings(self):
        self.assertEqual(self.n["animals"], [{"key": "rabbit", "date": "2026-01-04"}, {"key": "deer", "date": "2026-02-10"}])

    def test_only_animals_never_a_building_or_a_plant(self):
        # the cabin, the birdhouse and the mushrooms are milestones but no animals; the stork, a bird, is one
        got = recap.numbers(2026, {D(2026, 3, 1): 5}, {}, [], set(), D(2026, 12, 31),
                            [("birdhouse", D(2026, 2, 23)), ("cabin", D(2026, 3, 1)), ("mushrooms", D(2026, 4, 1)),
                             ("stork", D(2026, 5, 1)), ("heron", D(2026, 5, 14))])["animals"]
        self.assertEqual([a["key"] for a in got], ["stork", "heron"])

    def test_every_non_animal_milestone_is_left_out(self):
        # (each milestone the add-on has that is a structure or a plant: on HEAD the cabin, with 1.8 more)
        structures = {"cabin", "birdhouse", "mushrooms"}
        keys = [k for k, _test in getattr(recap.milestones, "MILESTONES", recap.milestones.VISITORS)]
        self.assertTrue(structures & set(keys) <= recap.NOT_ANIMALS)
        self.assertNotIn("stork", recap.NOT_ANIMALS)

    def test_a_short_year_and_a_year_begun_after_january(self):
        self.assertTrue(self.n["short"])
        self.assertIsNone(self.n["cropFrom"])
        late = recap.numbers(2026, {D(2026, 11, 24) + dt.timedelta(days=i): 30 for i in range(9)}, {}, [], set(), D(2026, 12, 31))
        self.assertFalse(late["short"])
        self.assertEqual(late["cropFrom"], "2026-11-01")

    def test_only_the_days_up_to_the_last_one(self):
        n = recap.numbers(2026, {D(2026, 5, 1): 3, D(2026, 5, 9): 8}, {}, [], set(), D(2026, 5, 5))
        self.assertEqual((n["studied"], n["reviews"], n["last"]), (1, 3, "2026-05-05"))

    def test_nothing_studied(self):
        n = recap.numbers(2026, {}, {}, [], set(), D(2026, 12, 31))
        self.assertEqual((n["studied"], n["bestDay"], n["bestStreak"], n["label"]["key"]), (0, None, None, "quiet"))


class LabelTests(unittest.TestCase):
    def label(self, studied, last=YEAR_END, first_ever=LONG_AGO, skip=(), off=()):
        studied = sorted(studied)
        streak = (recap.runs(set(studied), set(skip) | set(off), D(2026, 1, 1), last) or [None])[-1]
        return recap.label(2026, studied, last, first_ever, streak, set(skip) | set(off), set(off))

    def test_his_year_came_back_in_may(self):
        # (January studied, away three months, a little in April, back on May 12 and every day since but one)
        studied = set(days(D(2026, 1, 1), D(2026, 1, 11))) | {D(2026, 1, 23), D(2026, 4, 12), D(2026, 4, 14)}
        studied |= set(days(D(2026, 5, 12), D(2026, 11, 18))) - {D(2026, 5, 26)}
        self.assertEqual(self.label(studied, D(2026, 11, 18)), {"key": "comeback", "month": 4})

    def test_a_comeback_after_a_longer_streak_earlier_in_the_year(self):
        # (every day to May, the summer away, every day from September: its best streak is the spring's)
        studied = set(days(D(2026, 1, 1), D(2026, 5, 31))) | set(days(D(2026, 9, 1), D(2026, 12, 31)))
        n = recap.numbers(2026, dict.fromkeys(studied, 50), {}, [], set(), YEAR_END)
        self.assertEqual(n["bestStreak"][1], "2026-01-01")
        self.assertEqual(n["label"], {"key": "comeback", "month": 8})

    def test_a_streak_broken_before_the_end_is_no_comeback(self):
        studied = set(days(D(2026, 1, 1), D(2026, 1, 11))) | set(days(D(2026, 5, 12), D(2026, 11, 1)))
        self.assertNotEqual(self.label(studied, D(2026, 11, 18))["key"], "comeback")

    def test_a_new_forest(self):
        studied = set(days(D(2026, 11, 24), D(2026, 11, 30))) | {D(2026, 12, 12), D(2026, 12, 20)}
        self.assertEqual(self.label(studied, first_ever=D(2026, 11, 24)), {"key": "new", "date": "2026-11-24", "days": 9})
        self.assertEqual(self.label({D(2026, 12, 30)}, first_ever=D(2026, 12, 30))["days"], 1)

    def test_steady_season_patient_quiet(self):
        self.assertEqual(self.label(set(days(D(2026, 1, 1), D(2026, 12, 31))) - {D(2026, 3, 3)})["key"], "steady")
        self.assertEqual(self.label(set(days(D(2026, 3, 1), D(2026, 3, 20))) | {D(2026, 8, 1), D(2026, 10, 1)}), {"key": "season", "month": 2, "days": 20})
        self.assertEqual(self.label({D(2026, 2, 1), D(2026, 6, 1), D(2026, 9, 1)})["key"], "patient")
        self.assertEqual(self.label({D(2026, 2, 1)})["key"], "quiet")

    def test_a_month_then_nothing_is_its_season_not_steady(self):
        self.assertEqual(self.label(set(days(D(2026, 1, 3), D(2026, 2, 6))))["key"], "season")

    def test_a_five_days_a_week_streak_kept_all_year_is_steady(self):
        weekdays = [d for d in days(D(2026, 1, 1), D(2026, 12, 31)) if d.weekday() < 5]
        weekends = {d for d in days(D(2026, 1, 1), D(2026, 12, 31)) if d.weekday() >= 5}
        self.assertEqual(self.label(set(weekdays), off=weekends)["key"], "steady")
        self.assertEqual(self.label(set(weekdays))["key"], "patient")  # (with no days off set: five days in seven)

    def test_weekends_all_year_are_weekly(self):
        weekends = {d for d in days(D(2026, 1, 1), D(2026, 12, 31)) if d.weekday() >= 5}
        self.assertEqual(self.label(weekends | {D(2026, 3, 4), D(2026, 7, 8)})["key"], "weekly")

    def test_every_year_gets_a_word(self):
        R = random.Random(7)
        keys = set()
        for _ in range(300):
            k = R.choice([1, 3, 8, 30, 120, 300])
            studied = {D(2026, 1, 1) + dt.timedelta(days=R.randrange(365)) for _ in range(k)}
            got = self.label(studied, first_ever=R.choice([D(2019, 5, 1), min(studied)]))
            self.assertIn(got["key"], {"comeback", "new", "steady", "weekly", "season", "patient", "quiet"})
            keys.add(got["key"])
        self.assertGreaterEqual(len(keys), 3)


class EarnedTests(unittest.TestCase):
    def test_animals_are_dated_by_the_day_their_milestone_was_earned(self):
        # a 30-day streak reached 5 days ago, and a deer the forest recorded only today: the history's day wins
        day_reviews = dict.fromkeys(range(5, 35), 2)
        cut = D(2026, 9, 19)
        got = recap.earned([{"key": "deer", "day": 2000}, {"key": "owl", "day": 1990}], [], day_reviews, 2000,
                           lambda ago: cut - dt.timedelta(days=ago))
        self.assertEqual(got, [("deer", D(2026, 9, 14))])  # (the owl: no day the history can tell, left out)


class AnsweredTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_opened_stays_opened_and_the_debug_open_is_done_with(self):
        recap.ask_open(2026)
        self.assertEqual(recap.asked_open(), 2026)
        recap.answer(2026, recap.OPENED)
        recap.answer(2026, recap.DISMISSED)
        self.assertEqual(recap.answered(2026), recap.OPENED)
        self.assertIsNone(recap.asked_open())
        self.assertEqual(recap.answered(2025), "")
        recap.forget()
        self.assertEqual(recap.answered(2026), "")


def forest_cards(days_ago):
    return [(1000 + i, 10, d) for i, d in enumerate(days_ago)]


class PageTests(unittest.TestCase):
    """The deck list's payload, on the stand-in Anki (its today is Sep 19 2026)."""

    def setUp(self):
        # a card first reviewed on each of these days: 2026's from Jan 1 (261 days ago), and 2025's
        reset(forest_cards(list(range(0, 40)) + [200, 201, 400]))

    def page(self, **kw):
        return addon.payload.payload(**kw)

    def test_nothing_outside_its_window(self):
        self.assertIsNone(self.page()["recap"])

    def test_the_debug_open_brings_it_any_day_with_the_heatmaps_numbers(self):
        recap.ask_open(2026)
        r = self.page()["recap"]
        self.assertEqual((r["year"], r["studied"], r["reviews"], r["entry"], r["openNow"]), (2026, 42, 42, "none", True))
        # (the days between with nothing due pass, as on the heatmap: one streak from Mar 2 to today)
        self.assertEqual(r["bestStreak"], [42, "2026-03-02", "2026-09-19"])
        cal = r["calendar"]
        self.assertEqual((cal["view"], cal["start"], len(cal["days"])), ("by_year", "2026-01-01", 262))
        self.assertEqual(sum(cal["days"]), 42)
        self.assertIn("look", cal)
        self.assertEqual(r["newCards"], 42)
        self.assertEqual(r["trees"], 42)
        self.assertEqual(r["label"]["key"], "season")  # (September holds 19 of its 42 days)

    def test_in_its_window_a_card_then_a_link(self):
        with mock.patch.object(recap, "year_for", return_value=2026):
            self.assertEqual(self.page()["recap"]["entry"], "card")
            actions.on_js_message((False, None), f"{MODULE}:recap:dismissed:2026", actions.DeckBrowser())
            self.assertEqual(self.page()["recap"]["entry"], "link")

    def test_with_a_start_date_the_years_days_are_the_heatmaps(self):
        reset(forest_cards(list(range(0, 40)) + [200, 201, 400]), {"ignore_before": "2026-09-01"})
        recap.ask_open(2026)
        page = self.page()
        r, cal = page["recap"], page["calendar"]
        start = D.fromisoformat(cal["start"])
        shown = sum(1 for i, n in enumerate(cal["days"]) if n and (start + dt.timedelta(days=i)).year == 2026)
        self.assertEqual((r["studied"], shown), (42, 42))
        self.assertNotEqual(r["label"]["key"], "new")  # (studied since 2025: the forest is new, not you)

    def test_a_year_with_no_day_studied_has_none(self):
        recap.ask_open(2024)
        self.assertIsNone(self.page()["recap"])

    def test_a_debug_year_with_nothing_studied_never_hides_the_real_one(self):
        recap.ask_open(2024)
        with mock.patch.object(recap, "year_for", return_value=2026):
            r = self.page()["recap"]
        self.assertEqual((r["year"], r["entry"], r["openNow"]), (2026, "card", False))
        self.assertIsNone(recap.asked_open())

    def test_never_on_a_decks_screen(self):
        recap.ask_open(2026)
        self.assertIsNone(self.page(did=10)["recap"])


class SaveTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_the_picture_from_the_page_is_saved_where_chosen(self):
        png = b"\x89PNG\r\n\x1a\nmade up"
        url = "data:image/png;base64," + base64.b64encode(png).decode()
        with tempfile.TemporaryDirectory() as tmp:
            where = os.path.join(tmp, "my year")
            dialog = mock.Mock(getSaveFileName=mock.Mock(return_value=(where, "PNG (*.png)")))
            with mock.patch.object(recap_actions, "QFileDialog", dialog), \
                    mock.patch.object(recap_actions, "default_path", return_value="memory-forest-2026.png"):
                actions.on_js_message((False, None), f"{MODULE}:recap:save:2026:{url}", actions.DeckBrowser())
            self.assertEqual(dialog.getSaveFileName.call_args[0][2], "memory-forest-2026.png")
            with open(where + ".png", "rb") as f:
                self.assertEqual(f.read(), png)

    def test_cancelled_saves_nothing(self):
        dialog = mock.Mock(getSaveFileName=mock.Mock(return_value=("", "")))
        with mock.patch.object(recap_actions, "QFileDialog", dialog), mock.patch.object(recap_actions, "default_path", return_value="x.png"):
            self.assertEqual(recap_actions.save(2026, b"png"), "")

    def test_the_answers_from_the_page(self):
        actions.on_js_message((False, None), f"{MODULE}:recap:opened:2026", actions.DeckBrowser())
        self.assertEqual(recap.answered(2026), recap.OPENED)
        actions.on_js_message((False, None), f"{MODULE}:recap:opened:nope", actions.DeckBrowser())  # (ignored)

    def test_the_debug_tabs_open_leaves_the_card_unanswered(self):
        recap.ask_open(2026)
        actions.on_js_message((False, None), f"{MODULE}:recap:debug_opened:2026", actions.DeckBrowser())
        self.assertIsNone(recap.asked_open())
        self.assertEqual(recap.answered(2026), "")


if __name__ == "__main__":
    unittest.main()


class FinishedDecksTests(unittest.TestCase):
    """The decks learned to their last card in the year: big enough, nothing new left, the last
    first answer that year, said once with their subdecks."""
    NAMES = {1: "German", 2: "German::A1", 3: "German::A2", 4: "Kanji", 5: "Tiny", 6: "Old", 7: "Spanish"}
    DAY = {1: D(2026, 3, 1), 2: D(2026, 5, 2), 3: D(2026, 8, 3), 4: D(2025, 6, 1), 5: D(2026, 1, 1)}

    def finished(self, rows):
        return recap.finished(rows, self.NAMES, 2026, self.DAY.__getitem__)

    def test_a_whole_deck_with_its_subdecks_is_said_once(self):
        rows = [(2, 30, 0, 2), (3, 30, 0, 3), (5, 5, 0, 5), (6, 40, 0, 4), (7, 40, 3, 3)]
        # German (its two subdecks, the later one in August) once; Tiny too small; Old in 2025; Spanish has new cards left
        self.assertEqual(self.finished(rows), [{"name": "German", "full": "German", "date": "2026-08-03"}])

    def test_a_subdeck_alone_when_its_parent_still_has_new_cards(self):
        rows = [(2, 30, 0, 2), (3, 30, 4, 3)]
        self.assertEqual([f["full"] for f in self.finished(rows)], ["German::A1"])
        self.assertEqual(self.finished(rows)[0]["name"], "A1")

    def test_none_when_no_deck_ran_out_of_new_cards(self):
        self.assertEqual(self.finished([(7, 40, 3, 3)]), [])


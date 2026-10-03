"""The journal: what it says, and on which days it says nothing."""

from __future__ import annotations

import datetime as dt
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import journal


class JournalTests(unittest.TestCase):
    def journal_for(self, **stats):
        base = {"trees": 40, "young": 3, "ancient": 0, "old": 2, "yellowing": 0, "streak": 12,
                "planted_today": True, "today_cards": 20, "oldest_date": "2025-09-19", "ponds": 0}
        base.update(stats)
        forest = {"trees": [{"date": "2025-09-19", "n": 30}], "stats": base, "visitors": []}
        mood = {"weather": "clear", "special": "none", "time": "day"}
        return journal.journal(forest, mood, dt.date(2026, 9, 19), [])

    def test_an_ordinary_day_says_nothing(self):
        # a line every day is wallpaper; most days the forest should be quiet
        self.assertEqual(self.journal_for(), "")
        self.assertEqual(self.journal_for(planted_today=False), "")
        for w in ("rain", "snow", "fog", "storm"):
            mood = {"weather": w, "special": "none", "time": "day"}
            forest = {"trees": [{"date": "2025-09-19", "n": 30}], "visitors": [],
                      "stats": {"trees": 40, "young": 3, "ancient": 1, "old": 2, "yellowing": 1, "streak": 12,
                                "planted_today": True, "today_cards": 20, "oldest_date": "2025-09-19", "ponds": 1}}
            self.assertEqual(journal.journal(forest, mood, dt.date(2026, 9, 19), []), "")

    def test_it_speaks_on_the_day_a_milestone_is_reached(self):
        self.assertIn("first tree", self.journal_for(trees=1))
        self.assertIn("100th tree", self.journal_for(trees=100))
        self.assertIn("30 days in a row", self.journal_for(streak=30))
        # ... and not the day after
        self.assertEqual(self.journal_for(trees=101), "")
        self.assertEqual(self.journal_for(streak=31), "")

    def test_a_milestone_only_counts_on_a_day_you_planted(self):
        self.assertEqual(self.journal_for(trees=100, planted_today=False), "")

    def test_journal_prefers_new_visitors_then_anniversaries(self):
        forest = {"trees": [{"date": "2025-09-19", "n": 30}], "stats": {"trees": 1, "young": 0, "ancient": 0, "old": 0, "yellowing": 0, "streak": 0, "planted_today": False, "today_cards": 0, "oldest_date": "2025-09-19"},
                  "visitors": [{"key": "fox", "label": "a fox", "why": "you passed 10,000 reviews", "new": True}]}
        mood = {"weather": "clear", "special": "none", "time": "day"}
        self.assertIn("fox", journal.journal(forest, mood, dt.date(2026, 9, 19), [0]))
        forest["visitors"] = []
        self.assertIn("turned a year old", journal.journal(forest, mood, dt.date(2026, 9, 19), [0]))

    def test_the_night_sky_is_only_spoken_of_when_it_is_clear(self):
        forest = {"trees": [{"date": "2025-09-19", "n": 30, "ago": 0}], "visitors": [],
                  "stats": {"trees": 40, "streak": 12, "planted_today": False, "today_cards": 0}}
        say = lambda weather, time="night", evs=("meteor_shower",): journal.journal(  # noqa: E731
            forest, {"weather": weather, "special": "none", "time": time}, dt.date(2026, 9, 19), [], list(evs))
        self.assertEqual(say("clear"), "Meteors are falling tonight.")
        self.assertEqual(say("after_rain"), "Meteors are falling tonight.")
        self.assertEqual(say("cloudy"), "")  # drawn behind no clouds: not said either
        self.assertEqual(say("clear", "day"), "")
        self.assertEqual(say("cloudy", evs=("harvest_moon",)), "")
        self.assertEqual(say("cloudy", evs=("new_ancient",)), "One of your trees became ancient today.")
        self.assertEqual(say("clear", evs=("new_ancient",)), "One of your trees became ancient today. Watch for a shooting star.")

    def test_the_tall_grass_says_why_it_is_there(self):
        stats = {"trees": 40, "streak": 12, "planted_today": False, "today_cards": 0}
        mood = {"weather": "clear", "special": "none", "time": "day"}
        for ago, line in ((9, "a week"), (20, "2 weeks"), (30, "4 weeks")):
            forest = {"trees": [{"date": "2025-09-19", "n": 30, "ago": ago}], "visitors": [], "stats": stats}
            self.assertEqual(journal.journal(forest, mood, dt.date(2026, 9, 19), [], stagnation=0.5),
                             f"The grass is growing tall: no new cards for {line}.")
        self.assertEqual(journal.journal(forest, mood, dt.date(2026, 9, 19), [], stagnation=0.0), "")

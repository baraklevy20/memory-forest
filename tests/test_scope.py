"""What the forest counts (scope.py), in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import unittest

from fake_anki import addon, reset
from helpers import CUTOFF

import study_log

scope = addon.scope


class ScopeTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_left_out_deck_takes_its_subdecks_with_it(self):
        self.assertEqual(scope.excluded_decks({"excluded_decks": [10]}), {10, 11})
        # a hand-edited id, or a deck deleted since, is passed over
        self.assertEqual(scope.excluded_decks({"excluded_decks": ["x", 999, 20]}), {20})

    def test_the_start_date_is_when_that_anki_day_began(self):
        start = scope.since({"ignore_before": "2026-09-01"})
        self.assertEqual(start, study_log.day_start(dt.date(2026, 9, 1), CUTOFF))
        self.assertIsNone(scope.since({"ignore_before": ""}))
        self.assertIsNone(scope.since({"ignore_before": "not a date"}))


if __name__ == "__main__":
    unittest.main()

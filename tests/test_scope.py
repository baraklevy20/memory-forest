"""What the forest counts (scope.py), in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import unittest

import fake_anki
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

    def test_a_filtered_subdeck_lends_its_parent_nothing(self):
        # French::Lent, a filtered subdeck of French, with a German card (40) and a French one (41)
        fake_anki.DECKS[31] = "French::Lent"
        fake_anki.FILTERED.add(31)
        self.addCleanup(fake_anki.DECKS.pop, 31)
        self.addCleanup(fake_anki.FILTERED.discard, 31)
        reset([(40, 31, 3, 20), (41, 31, 4, 10)])
        self.assertEqual(sorted(scope.deck_ids(10, set())), [10, 11])
        self.assertEqual(scope.borrowed_from_elsewhere(10), [40])
        self.assertEqual(scope.borrowed_from_elsewhere(20), [])

    def test_the_start_date_is_when_that_anki_day_began(self):
        start = scope.since({"ignore_before": "2026-09-01"})
        self.assertEqual(start, study_log.day_start(dt.date(2026, 9, 1), CUTOFF))
        self.assertIsNone(scope.since({"ignore_before": ""}))
        self.assertIsNone(scope.since({"ignore_before": "not a date"}))

    def test_a_start_date_past_ankis_today_is_today(self):
        # Anki's today is 19 Sep (until the rollover): 20 Sep, picked after midnight, starts today
        self.assertEqual(scope.anki_today(), dt.date(2026, 9, 19))
        self.assertEqual(scope.since({"ignore_before": "2026-09-20"}), scope.since({"ignore_before": "2026-09-19"}))


if __name__ == "__main__":
    unittest.main()

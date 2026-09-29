"""The config and what is remembered per profile (state.py), in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import unittest

from fake_anki import addon, mw, reset
from helpers import CUTOFF

import study_log

state = addon.state


class StateTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_left_out_deck_takes_its_subdecks_with_it(self):
        self.assertEqual(state.excluded_decks({"excluded_decks": [10]}), {10, 11})
        # a hand-edited id, or a deck deleted since, is passed over
        self.assertEqual(state.excluded_decks({"excluded_decks": ["x", 999, 20]}), {20})

    def test_the_start_date_is_when_that_anki_day_began(self):
        start = state.since({"ignore_before": "2026-09-01"})
        self.assertEqual(start, study_log.day_start(dt.date(2026, 9, 1), CUTOFF))
        self.assertIsNone(state.since({"ignore_before": ""}))
        self.assertIsNone(state.since({"ignore_before": "not a date"}))

    def test_suspended_cards_keep_their_trees_unless_switched_off(self):
        self.assertTrue(state.keeps_suspended({}))
        for off in (False, "false", 0, "0"):
            self.assertFalse(state.keeps_suspended({"keep_suspended": off}))

    def test_a_hand_edited_number_is_brought_back_in_range(self):
        self.assertEqual(state.clamp_int("abc", 800, 400, 2000), 800)
        self.assertEqual(state.clamp_int(99999, 800, 400, 2000), 2000)
        self.assertEqual(state.clamp_int("450", 800, 400, 2000), 450)

    def test_saving_leaves_out_what_is_still_at_its_default(self):
        state.save_config(dict(state.config(), max_width=900, weather=mw.addonManager.defaults["weather"], gone=1))
        self.assertEqual(mw.addonManager.config, {"max_width": 900})

    def test_each_profile_remembers_its_own(self):
        state.save_state({"last_planted": "2026-09-19"})
        self.assertEqual(state.load_state(), {"last_planted": "2026-09-19"})
        mw.pm.name = "Someone else"
        try:
            self.assertEqual(state.load_state(), {})
        finally:
            mw.pm.name = "Test profile"


if __name__ == "__main__":
    unittest.main()

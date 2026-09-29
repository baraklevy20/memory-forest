"""The events on Anki's side (events_state.py): what the page is sent - in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import addon, mw, reset
from helpers import ms

payload = addon.payload


class GrassTests(unittest.TestCase):
    def test_the_grass_grows_tall_while_you_review_without_new_cards(self):
        reset([(1, 10, 20)])  # nothing new for twenty days
        mw.col.db.con.execute("insert into revlog values (?, 999, 3, 1)", (ms(0, 18),))  # reviewing today
        self.assertGreater(payload.payload()["stagnation"], 0)

    def test_not_while_you_are_away_nor_on_a_decks_own_forest(self):
        reset([(1, 10, 20)])  # nothing since, not even a review: a break, not coasting
        self.assertEqual(payload.payload()["stagnation"], 0)
        reset([(1, 10, 20)], {"deck_forest_mode": "own"})
        mw.col.db.con.execute("insert into revlog values (?, 999, 3, 1)", (ms(0, 18),))
        self.assertNotIn("stagnation", payload.payload(10))


if __name__ == "__main__":
    unittest.main()

"""The "a new tree was planted" message (planting.py), in a stand-in Anki."""

from __future__ import annotations

import types
import unittest

from fake_anki import addon, mw, reset, tooltips
from helpers import ms

planting = addon.planting


def answer(cid, did=10):
    planting.on_answer(None, types.SimpleNamespace(id=cid, did=did, odid=0), 3)


class PlantingTests(unittest.TestCase):
    def test_once_a_day_on_the_first_new_card(self):
        reset([(1, 10, 0), (2, 10, 0)])
        answer(1)
        answer(2)
        self.assertEqual(len(tooltips), 1)

    def test_remembered_across_restarts(self):
        reset([(1, 10, 0), (2, 10, 0)])
        answer(1)
        planting._planted_today = None  # Anki restarted: only the state file remembers
        answer(2)
        self.assertEqual(len(tooltips), 1)

    def test_not_for_a_review_nor_a_left_out_deck(self):
        reset([(1, 10, 0)], {"excluded_decks": [10]})
        answer(1)
        reset([(1, 10, 3)])
        mw.col.db.con.execute("insert into revlog values (?, 1, 3, 1)", (ms(0),))  # seen before: a review
        answer(1)
        reset([(1, 10, 0)], {"planting_tooltip": False})
        answer(1)
        self.assertEqual(tooltips, [])


if __name__ == "__main__":
    unittest.main()

"""Telling the phone's note, deck and cards apart (phone_note.py), in a stand-in Anki."""

from __future__ import annotations

import unittest
from unittest import mock

from fake_anki import addon, mw, reset

phone_note = addon.phone_note


class PhoneNoteTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_the_phone_s_deck_and_cards_are_looked_up_once_per_change_to_the_collection(self):
        mw.col.decks.id_for_name = mock.Mock(return_value=20)
        mw.col.models = mock.Mock()
        mw.col.models.by_name.return_value = {"id": 7}
        mw.col.db.list = mock.Mock(return_value=[900])
        self.assertEqual(phone_note.phone_decks(), {20})
        self.assertEqual(addon.scope.excluded_decks({}), {20})
        self.assertEqual(phone_note.phone_cards(), {900})
        self.assertEqual(phone_note.phone_cards(), {900})
        self.assertEqual((mw.col.decks.id_for_name.call_count, mw.col.db.list.call_count), (1, 1))
        # every card seen, or removed with the setting turned off, stays left out once gone
        phone_note.remember_phone_cards([800])
        mw.col.mod += 1
        mw.col.db.list.return_value = [901]
        self.assertEqual(phone_note.phone_cards(), {800, 900, 901})
        self.assertEqual(mw.col.db.list.call_count, 2)


if __name__ == "__main__":
    unittest.main()

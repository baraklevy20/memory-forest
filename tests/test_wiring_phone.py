"""The phone's note against the Anki versions it runs in (phone.py): the calls older Ankis take
differently, the deck options and template it keeps up to date (and the ones it leaves alone),
and the collection's media - in a stand-in Anki."""

from __future__ import annotations

import importlib
import os
import shutil
import unittest
from unittest import mock

import fake_anki
from fake_anki import mw, reset
from test_phone import Col

phone = importlib.import_module(f"{fake_anki.PACKAGE}.phone")
phone_note = importlib.import_module(f"{fake_anki.PACKAGE}.phone_note")


class OldCol(Col):
    """An Anki before 2.1.50: update_note takes no skip_undo_entry, schedule_cards_as_new no
    restore_position."""

    def __init__(self):
        super().__init__()
        self.sched.schedule_cards_as_new = self._old_as_new

    def update_note(self, note):
        super().update_note(note)

    def _old_as_new(self, cids):
        self._as_new(cids)


class PhoneAnkiTests(unittest.TestCase):
    def setUp(self):
        decks = mock.patch.dict(fake_anki.DECKS)
        decks.start()
        self.addCleanup(decks.stop)
        reset()
        self.logged = []
        quiet = mock.patch.object(phone, "log", self.logged.append)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.use(Col())

    def use(self, col):
        mw.col = self.col = col
        self.addCleanup(shutil.rmtree, col.media.folder, True)
        phone._written = (None, frozenset())

    def forest(self) -> str:
        return next(iter(self.col.notes.values()))["Forest"]

    def test_an_anki_before_2_1_50_still_gets_its_forest_and_a_new_card(self):
        self.use(OldCol())
        phone.switch(True)
        self.assertTrue(self.forest())
        self.col.db.con.execute("update cards set type = 2, queue = 2")
        self.col.notes[next(iter(self.col.notes))]["Forest"] = ""  # (so it is written again)
        phone.publish()
        self.assertTrue(self.forest())
        self.assertEqual(self.col.db.all("select type, queue from cards"), [(0, 0)])
        self.assertFalse([m for m in self.logged if "Traceback" in m])

    def test_deck_options_of_your_own_are_left_alone(self):
        phone.switch(True)
        did = self.col.decks.id_for_name(phone.PHONE_DECK)
        mine = self.col.decks.add_config("My options")
        mine["new"]["perDay"] = 3
        self.col.decks.deck_conf[did] = mine["id"]
        phone.publish()
        self.assertEqual(self.col.decks.config_dict_for_deck_id(did)["new"]["perDay"], 3)

    def test_the_phone_s_own_options_changed_by_hand_are_put_back(self):
        phone.switch(True)
        did = self.col.decks.id_for_name(phone.PHONE_DECK)
        conf = self.col.decks.config_dict_for_deck_id(did)
        conf["new"]["perDay"], conf["new"]["delays"] = 1, [10]
        phone.publish()
        conf = self.col.decks.config_dict_for_deck_id(did)
        self.assertEqual((conf["new"]["perDay"], len(conf["new"]["delays"])), (phone.NEW_PER_DAY, len(phone.STEPS)))

    def test_an_older_version_s_template_is_brought_up_to_date(self):
        phone.switch(True)
        m = self.col.models.by_id[next(iter(self.col.models.by_id))]
        m["tmpls"][0]["qfmt"], m["css"] = "{{Forest}} (as 1.1 drew it)", ".card {}"
        mod = self.col.mod
        phone.publish()
        m = self.col.models.by_name(phone.PHONE_NOTETYPE)
        self.assertEqual((m["tmpls"][0]["qfmt"], m["tmpls"][0]["afmt"], m["css"]), (phone.FRONT, phone.BACK, phone.CSS))
        self.assertGreater(self.col.mod, mod)
        # and up to date, it is left as it is (a change to a note type is a change to sync)
        mod = self.col.mod
        phone._up_to_date(self.col.models, self.col.models.by_name(phone.PHONE_NOTETYPE))
        self.assertEqual(self.col.mod, mod)

    def test_an_older_version_s_scripts_go_from_media_and_yours_stay(self):
        folder = self.col.media.folder
        for name in ("_memory_forest-0123456789.js", "my_picture.png", "_memory_forest-notes.txt"):
            with open(os.path.join(folder, name), "w") as f:
                f.write("x")
        phone.switch(True)
        left = set(os.listdir(folder))
        self.assertNotIn("_memory_forest-0123456789.js", left)
        self.assertLessEqual({"my_picture.png", "_memory_forest-notes.txt"}, left)
        phone.switch(False)
        self.assertEqual(set(os.listdir(folder)), {"my_picture.png", "_memory_forest-notes.txt"})

    def test_nothing_happens_without_a_collection(self):
        mw.col = None
        self.assertFalse(phone.switch(True))
        phone.publish()
        phone.remove()
        phone.after_sync()
        self.assertFalse(phone_note.phone_on())
        self.assertEqual(phone_note.phone_decks(), set())
        self.assertEqual(phone_note.phone_cards(), set())
        self.assertEqual(self.logged, [])

    def test_a_failure_writing_the_forest_is_logged_and_the_sync_goes_on(self):
        phone.switch(True)
        with mock.patch.object(self.col, "update_note", side_effect=RuntimeError("database locked")):
            self.col.notes[next(iter(self.col.notes))]["Forest"] = ""
            phone.publish()  # (must not raise: it runs inside sync_will_start)
        self.assertTrue(any("could not update the forest" in m for m in self.logged))

    def test_a_failure_taking_it_away_is_logged(self):
        phone.switch(True)
        with mock.patch.object(self.col, "remove_notes", side_effect=RuntimeError("locked")):
            phone.switch(False)
        self.assertTrue(any("could not take the forest off" in m for m in self.logged))


if __name__ == "__main__":
    unittest.main()

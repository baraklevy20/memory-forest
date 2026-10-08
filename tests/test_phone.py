"""The forest on your phone (phone.py): its note, deck and options, and taking them away
again, in a stand-in Anki."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

import fake_anki
from fake_anki import addon, mw, reset
from helpers import CUTOFF, TODAY, ms

phone = importlib.import_module(f"{fake_anki.PACKAGE}.phone")
study_log = importlib.import_module(f"{fake_anki.PACKAGE}.study_log")


class Models:
    """col.models: note types by name, with their fields and one template."""

    def __init__(self, col):
        self.col, self.by_id = col, {}

    def by_name(self, name):
        return next((dict(m) for m in self.by_id.values() if m["name"] == name), None)

    def all_names_and_ids(self):
        return [types.SimpleNamespace(name=m["name"], id=m["id"]) for m in self.by_id.values()]

    def get(self, mid):
        m = self.by_id.get(mid)
        return dict(m) if m else None

    def new(self, name):
        return {"name": name, "flds": [], "tmpls": [], "css": ""}

    def new_field(self, name):
        return {"name": name}

    def add_field(self, m, field):
        m["flds"].append(field)

    def new_template(self, name):
        return {"name": name, "qfmt": "", "afmt": ""}

    def add_template(self, m, t):
        m["tmpls"].append(t)

    def add(self, m):
        m["id"] = 5000 + len(self.by_id)
        self.by_id[m["id"]] = m
        self.col.mod += 1

    def update_dict(self, m):
        self.by_id[m["id"]] = m
        self.col.mod += 1


class Decks(fake_anki.Decks):
    """col.decks, with decks that can be made and removed, and their options presets."""

    def __init__(self, col):
        super().__init__()
        self.col = col
        self.conf = {1: {"id": 1, "name": "Default", "new": {"perDay": 20, "delays": [1, 10]}, "rev": {"perDay": 200}}}
        self.deck_conf: dict = {}

    def get(self, did, default=True):
        deck = super().get(did, default)
        if deck is not None:
            deck["conf"] = self.deck_conf.get(did, 1)
        return deck

    def id(self, name):
        found = self.id_for_name(name)
        if found:
            return found
        did = max(fake_anki.DECKS) + 1
        fake_anki.DECKS[did] = name
        return did

    def id_for_name(self, name):
        return next((d for d, n in fake_anki.DECKS.items() if n == name), None)

    def save(self, deck):
        self.deck_conf[deck["id"]] = deck["conf"]

    def remove(self, dids):
        for did in dids:
            fake_anki.DECKS.pop(did, None)

    def all_config(self):
        return list(self.conf.values())

    def add_config(self, name):
        conf = {"id": max(self.conf) + 1, "name": name, "new": {"perDay": 20, "delays": [1, 10]}, "rev": {"perDay": 200}}
        self.conf[conf["id"]] = conf
        return conf

    def config_dict_for_deck_id(self, did):
        return self.conf[self.deck_conf.get(did, 1)]

    def update_config(self, conf):
        self.conf[conf["id"]] = conf


class Note(dict):
    def __init__(self, nid, mid, fields):
        super().__init__(fields)
        self.id, self.mid = nid, mid


class Media:
    def __init__(self):
        self.folder = tempfile.mkdtemp(prefix="memory-forest-media-")

    def dir(self):
        return self.folder

    def write_data(self, name, data):
        with open(os.path.join(self.folder, name), "wb") as f:
            f.write(data)
        return name

    def trash_files(self, names):
        for name in names:
            os.remove(os.path.join(self.folder, name))


class Col(fake_anki.Col):
    """The stand-in collection, with what making and removing the phone's note needs."""

    def __init__(self):
        super().__init__()
        self.db.list = lambda sql, *args: [r[0] for r in self.db.all(sql, *args)]
        self.db.con.execute("alter table notes add column mid integer")
        self.models, self.decks, self.media = Models(self), Decks(self), Media()
        self.sched.schedule_cards_as_new = self._as_new
        self.notes: dict = {}

    def new_note(self, m):
        return Note(0, m["id"], {f["name"]: "" for f in m["flds"]})

    def add_note(self, note, did):
        note.id = 9000 + len(self.notes)
        self.notes[note.id] = dict(note)
        self.db.con.execute("insert into notes (id, tags, mid) values (?, '', ?)", (note.id, note.mid))
        self.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (?, ?, ?, 0, 0, 0, 0, '{}', 1)",
                            (note.id, note.id, did))
        self.mod += 1

    def get_note(self, nid):
        mid = self.db.scalar("select mid from notes where id = ?", nid)
        return Note(nid, mid, self.notes[nid])

    def update_note(self, note, skip_undo_entry=False):
        self.notes[note.id] = dict(note)
        self.mod += 1

    def remove_notes(self, nids):
        for nid in nids:
            self.notes.pop(nid, None)
            self.db.con.execute("delete from notes where id = ?", (nid,))
            self.db.con.execute("delete from cards where nid = ?", (nid,))
        self.mod += 1

    def card_ids_of_note(self, nid):
        return self.db.list("select id from cards where nid = ?", nid)

    def get_card(self, cid):
        ctype, queue = self.db.all("select type, queue from cards where id = ?", cid)[0]
        return types.SimpleNamespace(type=ctype, queue=queue)

    def _as_new(self, cids, **_kw):
        for cid in cids:
            self.db.con.execute("update cards set type = 0, queue = 0 where id = ?", (cid,))
        self.mod += 1


class PhoneTests(unittest.TestCase):
    def setUp(self):
        decks = mock.patch.dict(fake_anki.DECKS)
        decks.start()
        self.addCleanup(decks.stop)
        reset()
        mw.col = self.col = Col()
        self.addCleanup(shutil.rmtree, self.col.media.folder, True)
        quiet = mock.patch.object(phone, "log", lambda _msg: None)
        quiet.start()
        self.addCleanup(quiet.stop)

    def cards(self):
        """(deck, type, queue) of the phone note's cards."""
        return self.col.db.all("select did, type, queue from cards where nid in (select id from notes where mid is not null)")

    def test_turning_it_on_makes_the_note_its_deck_and_options(self):
        self.assertFalse(addon.state.phone_on())
        phone.switch(True)
        self.assertTrue(addon.state.phone_on())
        m = self.col.models.by_name(phone.PHONE_NOTETYPE)
        self.assertEqual([f["name"] for f in m["flds"]], list(phone.FIELDS))
        self.assertEqual((m["tmpls"][0]["qfmt"], m["css"]), (phone.FRONT, phone.CSS))
        did = self.col.decks.id_for_name(phone.DECK)
        self.assertEqual(self.cards(), [(did, 0, 0)])
        conf = self.col.decks.config_dict_for_deck_id(did)
        self.assertEqual((conf["name"], conf["new"]["perDay"], conf["rev"]["perDay"]),
                         (phone.DECK, phone.NEW_PER_DAY, phone.REVIEWS_PER_DAY))
        forest = next(iter(self.col.notes.values()))["Forest"]
        self.assertIn('"script":"_memory_forest-', forest)
        # in media: the script, and a file for every piece of scenery this copy ships; the note
        # names the ones its days draw with
        sent = json.loads(forest)
        media = set(os.listdir(self.col.media.folder))
        self.assertEqual(len(media), 1 + len(addon.phone_data.all_scenery()))
        self.assertLessEqual({sent["script"], *sent["parts"].values()}, media)
        self.assertTrue(sent["parts"])
        # another scenery: the note changes, the media doesn't (it changes once an update)
        mw.addonManager.config.update(environment="aurora", landscape="lake")
        phone.publish()
        again = json.loads(next(iter(self.col.notes.values()))["Forest"])
        self.assertIn("envs/aurora.js", again["parts"])
        self.assertEqual(set(os.listdir(self.col.media.folder)), media)
        # a file taken away (by the other edition of the add-on, say) is written again
        os.remove(os.path.join(self.col.media.folder, again["parts"]["envs/aurora.js"]))
        phone.publish()
        self.assertEqual(set(os.listdir(self.col.media.folder)), media)
        # its deck is never part of the forest, nor offered as a deck to leave out
        self.assertIn(did, addon.state.excluded_decks({}))

    def test_a_second_sync_makes_nothing_new_and_an_answered_card_is_new_again(self):
        phone.switch(True)
        self.col.db.con.execute("update cards set type = 2, queue = 2")
        phone.publish()
        self.assertEqual(len(self.col.notes), 1)
        self.assertEqual([c[1:] for c in self.cards()], [(0, 0)])
        self.assertEqual(len(self.col.decks.all_config()), 2)

    def test_turning_it_off_takes_the_note_and_deck_away(self):
        phone.switch(True)
        did = self.col.decks.id_for_name(phone.DECK)
        phone.switch(False)
        self.assertFalse(addon.state.phone_on())
        self.assertEqual(self.col.notes, {})
        self.assertIsNone(self.col.decks.name_if_exists(did))
        self.assertEqual(os.listdir(self.col.media.folder), [])
        # the note type stays: removing it forces a full sync
        self.assertIsNotNone(self.col.models.by_name(phone.PHONE_NOTETYPE))

    def test_it_says_when_the_deck_has_just_come_or_gone(self):
        self.assertTrue(phone.switch(True))  # turned on: the deck is made
        self.assertFalse(phone.switch(True))  # already on: nothing to show
        self.assertTrue(phone.switch(False))  # turned off: the deck goes
        self.assertFalse(phone.switch(False))

    def test_turned_off_on_another_computer_the_next_sync_takes_it_away(self):
        phone.switch(True)
        self.col.remove_notes(list(self.col.notes))  # what the sync brought in
        messages = []
        with mock.patch.object(phone, "log", messages.append):
            phone.after_sync()
            self.assertEqual(self.col.notes, {})
            self.assertIsNone(self.col.decks.id_for_name(phone.DECK))
            self.assertEqual(os.listdir(self.col.media.folder), [])
            self.assertEqual(messages, ["took the forest off your phone"])
            phone.publish()  # every sync after that: nothing left to do, and nothing said
            self.assertEqual(messages, ["took the forest off your phone"])

    def test_off_in_a_collection_that_never_had_it_makes_nothing(self):
        phone.publish()
        self.assertEqual((self.col.notes, self.col.models.by_id), ({}, {}))

    def test_removing_keeps_a_deck_that_holds_other_cards(self):
        phone.switch(True)
        did = self.col.decks.id_for_name(phone.DECK)
        self.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (1, 1, ?, 0, 2, 2, 5, '{}', 1)", (did,))
        phone.remove()
        self.assertEqual(self.col.notes, {})
        self.assertEqual(self.col.decks.name_if_exists(did), phone.DECK)

    def test_reviews_of_the_phone_s_cards_never_count_even_once_they_are_gone(self):
        phone.switch(True)
        cid = self.col.db.scalar("select id from cards")
        # looked at on the phone every day for a week, and answered anyway
        self.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, ?, 3, 0)",
                                    [(ms(d), cid) for d in range(7)])
        self.col.db.con.execute("update cards set type = 2, queue = 2 where id = ?", (cid,))
        self.assertEqual(addon.state.phone_cards(), {cid})
        phone.switch(False)
        self.assertEqual(self.col.db.scalar("select count() from cards"), 0)
        # the card is gone, its reviews stay (as in Anki), and they are still not study
        self.assertEqual(addon.state.phone_cards(), {cid})
        self.assertEqual(addon.state.load_state()["phone_cards"], [cid])
        skip = addon.state.phone_cards()
        rows = study_log.load_rows(self.col.db, CUTOFF, skip=skip)
        self.assertEqual((rows.total_reviews, rows.review_days, rows.first_last), (0, set(), {}))
        self.assertEqual(study_log.load_review_days(self.col.db, CUTOFF, skip=skip), set())
        self.assertEqual(study_log.load_backlog(self.col.db, TODAY, CUTOFF, 30, skip=skip)[1], [])
        self.assertEqual(addon.payload.payload()["stats"]["trees"], 0)
        # without it they would count, as the reviews of any other deleted card do
        self.assertEqual(study_log.load_rows(self.col.db, CUTOFF).total_reviews, 7)

    def test_a_phone_card_deleted_by_a_sync_from_elsewhere_stays_left_out(self):
        phone.switch(True)
        cid = self.col.db.scalar("select id from cards")
        self.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, ?, 3, 0)",
                                    [(ms(d), cid) for d in range(3)])
        self.assertEqual(addon.state.phone_cards(), {cid})  # seen once: remembered
        with mock.patch.object(addon.state, "save_state") as save:
            self.col.mod += 1
            addon.state.phone_cards()
        save.assert_not_called()  # nothing new, nothing written
        # another computer turned the setting off, and the sync took the note away here
        self.col.remove_notes(list(self.col.notes))
        self.assertEqual(addon.state.phone_cards(), {cid})
        self.assertEqual(study_log.load_rows(self.col.db, CUTOFF, skip=addon.state.phone_cards()).total_reviews, 0)

    def test_a_card_in_a_filtered_deck_still_gets_the_forest(self):
        phone.switch(True)
        mine = self.col.decks.id_for_name(phone.DECK)
        self.col.db.con.execute("update cards set did = 30, odid = ?", (mine,))  # Custom Study borrowed it
        messages = []
        with mock.patch.object(phone, "log", messages.append):
            addon.state._phone_cards = (None, None, frozenset())
            self.col.mod += 1
            with mock.patch.object(phone.phone_data, "same_forest", return_value=False):
                phone.publish()
        self.assertEqual(messages, [])
        self.assertNotIn(30, self.col.decks.deck_conf)
        self.assertEqual(addon.state.phone_decks(), {mine})

    def test_a_card_moved_to_a_deck_of_yours_leaves_that_deck_as_it_was(self):
        phone.switch(True)
        mine = self.col.decks.id_for_name(phone.DECK)
        self.col.db.con.execute("update cards set did = 20")  # moved into German
        self.col.mod += 1
        phone.publish()
        self.assertEqual(self.col.decks.config_dict_for_deck_id(20)["name"], "Default")
        # German is still yours to count and to leave out; only the add-on's deck isn't
        self.assertEqual(addon.state.phone_decks(), {mine})
        self.assertNotIn(20, addon.state.excluded_decks({}))
        # and turning it off takes the note, but never your deck, even left empty
        phone.remove()
        self.assertEqual(self.col.decks.name_if_exists(20), "German")
        self.assertIsNone(self.col.decks.name_if_exists(mine))

    def test_an_old_on_in_the_collection_s_config_never_brings_it_back(self):
        # Anki syncs the collection's config as one piece, from whichever device changed
        # anything last: a phone that only opened a deck since sends back the old "on"
        phone.switch(True)
        phone.switch(False)
        self.col.set_config(addon.state.OLD_PHONE_SWITCH, True)
        phone.after_sync()
        self.assertFalse(addon.state.phone_on())
        self.assertEqual(self.col.notes, {})
        self.assertIsNone(self.col.decks.id_for_name(phone.DECK))

    def test_a_sync_never_makes_the_note(self):
        phone.after_sync()
        phone.publish()
        self.assertEqual(self.col.notes, {})
        self.assertFalse(addon.state.phone_on())

    def test_the_switch_takes_the_old_setting_away(self):
        self.col.set_config(addon.state.OLD_PHONE_SWITCH, False)
        phone.switch(True)
        self.assertNotIn(addon.state.OLD_PHONE_SWITCH, self.col.conf)

    def test_two_notes_from_two_computers_become_one(self):
        phone.switch(True)
        # another computer turned it on before the two synced: its note came in with the sync
        m = self.col.models.by_name(phone.PHONE_NOTETYPE)
        other = self.col.new_note(m)
        self.col.add_note(other, self.col.decks.id_for_name(phone.DECK))
        first = min(self.col.notes)
        phone.publish()
        self.assertEqual(list(self.col.notes), [first])  # the oldest stays, on every computer alike
        self.assertIn(other.id, addon.state.phone_cards())  # its card's reviews stay left out

    def test_two_note_types_of_the_same_name_keep_one_note(self):
        phone.switch(True)
        # the other computer made its own note type too, and the sync brought both
        mm = self.col.models
        dup = mm.new(phone.PHONE_NOTETYPE)
        for name in phone.FIELDS:
            mm.add_field(dup, mm.new_field(name))
        mm.add_template(dup, mm.new_template("Forest"))
        mm.add(dup)
        other = self.col.new_note(dup)
        self.col.add_note(other, self.col.decks.id_for_name(phone.DECK))
        first = min(self.col.notes)
        phone.publish()
        self.assertEqual(list(self.col.notes), [first])
        self.assertEqual(mm.get(dup["id"])["tmpls"][0]["qfmt"], phone.FRONT)  # both brought up to date
        self.assertIn(other.id, addon.state.phone_cards())
        # turning it off takes the notes of both away
        self.col.add_note(self.col.new_note(dup), self.col.decks.id_for_name(phone.DECK))
        phone.remove()
        self.assertEqual(self.col.notes, {})


class EditionTests(unittest.TestCase):
    """Memory Forest and Memory Forest Plus installed together: only Plus writes the note."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="memory-forest-addons-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.metas, self.configs = [], {}
        am = types.SimpleNamespace(all_addon_meta=lambda: list(self.metas),
                                   addonsFolder=lambda d: os.path.join(self.folder, d),
                                   getConfig=lambda d: self.configs.get(d))
        patch = mock.patch.object(phone.mw, "addonManager", am)
        patch.start()
        self.addCleanup(patch.stop)
        quiet = mock.patch.object(phone, "log", lambda _msg: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.me("memory_forest")

    def me(self, package):
        """This copy, with `package` in its manifest."""
        here = self.install("1255432496", package, "Memory Forest")
        patch = mock.patch.object(phone, "HERE", here)
        patch.start()
        self.addCleanup(patch.stop)

    def install(self, dir_name, package, name, enabled=True):
        path = os.path.join(self.folder, dir_name)
        os.makedirs(path, exist_ok=True)
        if package:
            with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"package": package, "name": name}, f)
        self.metas.append(types.SimpleNamespace(dir_name=dir_name, enabled=enabled, provided_name=name))
        self.configs[dir_name] = {}
        return path

    def test_alone_it_writes(self):
        self.install("2000", "something_else", "Another add-on")
        self.assertFalse(phone.steps_aside())

    def test_the_base_edition_leaves_the_phone_to_plus(self):
        self.install("memory_forest_plus", "memory_forest_plus", "Memory Forest Plus")
        self.assertTrue(phone.steps_aside())

    def test_found_by_its_name_too(self):
        self.install("memory_forest_plus", None, "Memory Forest Plus")
        self.assertTrue(phone.steps_aside())

    def test_not_to_a_plus_that_is_disabled(self):
        self.install("memory_forest_plus", "memory_forest_plus", "Memory Forest Plus", enabled=False)
        self.assertFalse(phone.steps_aside())

    def test_plus_and_a_copy_in_development_never_step_aside(self):
        self.install("memory_forest_plus", "memory_forest_plus", "Memory Forest Plus")
        for package in ("memory_forest_plus", "anki_forest"):
            with open(os.path.join(phone.HERE, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"package": package}, f)
            self.assertFalse(phone.steps_aside(), package)

    def test_if_the_add_ons_cant_be_read_it_writes_as_before(self):
        def broken():
            raise RuntimeError("no add-on manager")
        phone.mw.addonManager.all_addon_meta = broken
        self.assertFalse(phone.steps_aside())

    def test_stepping_aside_writes_nothing_but_still_switches(self):
        decks = mock.patch.dict(fake_anki.DECKS)
        decks.start()
        self.addCleanup(decks.stop)
        col = Col()
        self.addCleanup(shutil.rmtree, col.media.folder, True)
        self.install("memory_forest_plus", "memory_forest_plus", "Memory Forest Plus")
        with mock.patch.object(phone.mw, "col", col), mock.patch.object(phone, "config", lambda: {}):
            phone.switch(True)  # the note is the switch, the same for both editions...
            self.assertTrue(addon.state.phone_on(col))
            phone.publish()  # ... but only Plus writes the forest into it
            self.assertEqual(next(iter(col.notes.values()))["Forest"], "")
            self.assertEqual(os.listdir(col.media.folder), [])
            self.metas.pop()
            phone.publish()  # Plus gone: this copy writes
            self.assertNotEqual(next(iter(col.notes.values()))["Forest"], "")
            scripts = os.listdir(col.media.folder)
            self.install("memory_forest_plus", "memory_forest_plus", "Memory Forest Plus")
            phone.switch(False)  # unticked here: the note goes, Plus's script is Plus's to take
            self.assertEqual(col.notes, {})
            self.assertEqual(os.listdir(col.media.folder), scripts)

if __name__ == "__main__":
    unittest.main()

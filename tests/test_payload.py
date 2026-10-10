"""What a panel is drawn from (payload.py), in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import Col, addon, hooks, mw, reset
from helpers import ms

payload = addon.payload

# French (10) and its subdeck (11) on days 5 and 3, German (20) on day 3; card 4 is French's,
# borrowed by the filtered deck (30)
CARDS = [(1, 10, 5), (2, 11, 5), (3, 20, 3), (4, 30, 3, 10)]


class PayloadTests(unittest.TestCase):
    def test_the_whole_collection_grows_one_tree_a_day(self):
        reset(CARDS)
        p = payload.payload()
        self.assertEqual([(t["ago"], t["n"]) for t in p["trees"]], [(5, 2), (3, 2)])
        self.assertEqual(p["stats"]["trees"], 2)
        self.assertFalse(p["testForest"])
        self.assertEqual(p["channel"], addon.state.MODULE)

    def test_a_decks_own_forest_holds_its_cards_and_its_subdecks(self):
        reset(CARDS)
        p = payload.payload(10)
        self.assertEqual([(t["ago"], t["n"]) for t in p["trees"]], [(5, 2), (3, 1)])  # card 4 is still French's
        self.assertEqual(p["deckName"], "French")
        self.assertFalse(p["highlight"])

    def test_highlighting_a_deck_lights_its_trees_in_the_main_forest(self):
        reset(CARDS)
        p = payload.payload(20, highlight=True)
        self.assertEqual([(t["ago"], t["dim"]) for t in p["trees"]], [(5, True), (3, False)])
        self.assertEqual(p["litCount"], 1)

    def test_a_left_out_deck_plants_nothing(self):
        reset(CARDS, {"excluded_decks": [10]})
        self.assertEqual([(t["ago"], t["n"]) for t in payload.payload()["trees"]], [(3, 1)])

    def test_the_test_forest_needs_debug_on(self):
        reset(CARDS, {"test_forest": True, "test_trees": 30, "debug": False})
        self.assertFalse(payload.payload()["testForest"])
        reset(CARDS, {"test_forest": True, "test_trees": 30, "debug": True})
        p = payload.payload()
        self.assertTrue(p["testForest"])
        self.assertEqual(p["stats"]["trees"], 30)

    def test_the_forest_is_built_once_until_the_study_data_changes(self):
        reset(CARDS)
        first = payload._forest()
        self.assertIs(payload._forest(), first)
        mw.col.mod += 1  # the collection changed, but not what the forest grows from (a deck picked, say)
        self.assertIs(payload._forest(), first)
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 1, 3, 1)", (ms(0, 15),))  # a review
        second = payload._forest()
        self.assertIsNot(second, first)
        mw.col.db.con.execute("update cards set mod = 5 where id = 1")  # a card suspended or moved
        self.assertIsNot(payload._forest(), second)

    def test_the_deck_list_keeps_the_last_deck_s_forest(self):
        reset(CARDS)
        deck = payload._forest(10)
        payload._forest()  # back on the deck list: the whole collection's is built beside it
        self.assertIn(10, payload._logs)
        self.assertIs(payload._forest(10), deck)  # and the deck opened again reads nothing afresh
        payload._forest(20)  # another deck: only the latest deck's is kept
        self.assertEqual(set(payload._forest_cache), {None, 20})
        self.assertEqual(set(payload._logs), {None, 20})

    def test_a_collection_put_in_place_of_the_last_is_read_afresh(self):
        reset(CARDS)
        mw.col.path = "/profile/collection.anki2"
        self.assertEqual(len(payload._forest()["trees"]), 2)
        # a backup restored (or a .colpkg imported): the same path, and a review older than
        # any the review log has read, which reading on from where it stopped never sees
        mw.col = Col()
        mw.col.path = "/profile/collection.anki2"
        for cid, did, days in CARDS[:3] + [(9, 10, 7)]:
            mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (?, ?, ?, 0, 2, 2, 30, '{}', ?)",
                                  (cid, cid, did, mw.col.sched.today + 30))
            mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, ?, 3, 0)", (ms(days), cid))
            mw.col.db.con.execute("insert into notes (id, tags) values (?, '')", (cid,))
        self.assertIn(payload.collection_loaded, hooks.collection_did_load)
        for hook in hooks.collection_did_load:
            hook(mw.col)
        self.assertEqual([t["ago"] for t in payload._forest()["trees"]], [7, 5, 3])

    def test_a_tree_turned_ancient_is_no_news_once_a_start_date_leaves_it_out(self):
        reset([(1, 10, 500), (2, 10, 0)])
        payload.payload()  # the first look: nothing ancient yet
        mw.col.db.con.execute("update cards set ivl = 400, mod = 5 where id = 1")  # the old tree turns ancient today
        self.assertIn("ancient", payload.payload()["journal"])
        mw.addonManager.config["ignore_before"] = "2026-09-19"  # the forest starts today
        p = payload.payload()
        self.assertEqual(p["stats"]["trees"], 1)
        self.assertNotIn("ancient", p["journal"])
        self.assertNotIn("new_ancient", p["events"])

    def test_a_hand_edited_width_stays_in_range(self):
        reset(CARDS, {"max_width": "wide"})
        self.assertEqual(payload.payload()["maxWidth"], addon.state.MAX_WIDTH_DEFAULT)
        reset(CARDS, {"max_width": 99999})
        self.assertEqual(payload.payload()["maxWidth"], addon.state.MAX_WIDTH_MAX)

    def test_no_city_means_no_live_weather(self):
        reset(CARDS, {"city": "", "weather": "auto"})
        self.assertEqual(addon.live_weather.for_config({"city": "", "weather": "auto"}), (None, None, ""))
        self.assertEqual(payload.payload()["weatherError"], "")


    def test_leeches_bring_crows_to_their_own_tree(self):
        reset([(1, 10, 30), (2, 10, 30), (3, 10, 20)], {"nature": "wild"}, leeches={2})
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 2, 1, 1)", (ms(1),))  # studied lately
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual((trees[30].get("leeches"), trees[20].get("leeches")), (1, None))

    def test_an_old_leech_brings_no_crow(self):
        reset([(1, 10, 90)], leeches={1})  # last studied three months ago: an abandoned deck
        self.assertIsNone(payload.payload()["trees"][0].get("leeches"))

    def test_the_cards_each_tree_knows_well_stay_on_this_side(self):
        reset(CARDS)
        self.assertTrue(all("mature" not in t for t in payload.payload()["trees"]))  # only for the animals' milestones


if __name__ == "__main__":
    unittest.main()

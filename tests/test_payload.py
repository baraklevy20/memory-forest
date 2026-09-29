"""What a panel is drawn from (payload.py), in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import addon, mw, reset
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

    def test_the_forest_is_built_once_until_the_collection_changes(self):
        reset(CARDS)
        first = payload._forest()
        self.assertIs(payload._forest(), first)
        mw.col.mod += 1
        self.assertIsNot(payload._forest(), first)

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
        reset([(1, 10, 30), (2, 10, 30), (3, 10, 20)], leeches={2})
        mw.col.db.con.execute("insert into revlog values (?, 2, 1, 1)", (ms(1),))  # studied lately
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual((trees[30].get("leeches"), trees[20].get("leeches")), (1, None))

    def test_an_old_leech_brings_no_crow(self):
        reset([(1, 10, 90)], leeches={1})  # last studied three months ago: an abandoned deck
        self.assertIsNone(payload.payload()["trees"][0].get("leeches"))


if __name__ == "__main__":
    unittest.main()

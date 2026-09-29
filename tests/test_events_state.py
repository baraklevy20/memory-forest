"""The study events on Anki's side (events_state.py, debug_events.py): the Stakes
remembered per profile, strikes that stand, and what the page is sent - in a stand-in Anki."""

from __future__ import annotations

import unittest
from unittest import mock

from fake_anki import addon, mw, reset
from helpers import TODAY, ms

state, payload = addon.state, addon.payload

# a card first studied each day from 40 to 20 days ago, and two more after a break: reviews
# every day but the eight from 17 to 10 days ago
PLANTED = [(i, 10, 40 - i) for i in range(21)] + [(100, 10, 5), (101, 10, 4)]
MISSED = range(10, 18)


def studied_every_day_but_the_break(**config):
    reset(PLANTED, config)
    for d in range(41):
        if d not in MISSED:
            # on a card of its own (one since deleted), so no tree's first day moves
            mw.col.db.con.execute("insert into revlog values (?, 999, 3, 1)", (ms(d, 18),))


class StakesTests(unittest.TestCase):
    def test_the_day_the_stakes_were_chosen_is_remembered(self):
        reset(PLANTED, {"stakes": "wild"})
        payload.payload()
        self.assertEqual(state.load_state()["stakes"], "wild")
        self.assertEqual(state.load_state()["stakes_since"], TODAY)
        mw.col.sched.today = TODAY + 3  # three days on, the same choice keeps its day
        try:
            self.assertEqual(addon.events_state._stakes_since("wild"), 3)
        finally:
            mw.col.sched.today = TODAY

    def test_a_level_only_previewed_in_the_settings_is_not_remembered(self):
        reset(PLANTED, {"stakes": "chaotic"})
        with mock.patch.object(addon.settings, "is_open", return_value=True):
            self.assertEqual(addon.events_state._stakes_since("chaotic"), 0)
        self.assertNotIn("stakes", state.load_state())

    def test_a_break_from_before_choosing_the_stakes_never_strikes(self):
        studied_every_day_but_the_break(stakes="wild")
        p = payload.payload()
        self.assertEqual((p["craters"], p["strike"]), ([], None))
        self.assertEqual(p["stats"]["trees"], 23)

    def test_a_week_away_on_wild_takes_the_forest(self):
        studied_every_day_but_the_break(stakes="wild")
        state.save_state({"stakes": "wild", "stakes_since": TODAY - 60})
        p = payload.payload()
        self.assertEqual(len(p["craters"]), 1)
        self.assertEqual(p["strike"]["lost"], 21)
        self.assertTrue(p["strike"]["fresh"])
        self.assertEqual([t["ago"] for t in p["trees"]], [5, 4])  # only what grew since
        # eleven days on it is no longer news: the journal only speaks of it for a week
        self.assertFalse(p["strike"]["news"])
        self.assertNotIn("asteroid", p["journal"])
        self.assertEqual(addon.events_state.strike_line(dict(p, strike=dict(p["strike"], news=True))),
                         "An asteroid took your forest of 21 trees. A new one grows from here.")
        self.assertEqual(len(state.load_state()["strike_days"]), 1)

    def test_a_strike_plays_once_and_stands_whatever_the_stakes_become(self):
        studied_every_day_but_the_break(stakes="wild")
        state.save_state({"stakes": "wild", "stakes_since": TODAY - 60})
        seen = payload.payload()["strike"]["seen"]
        addon.actions.on_js_message((False, None), f"{state.MODULE}:struck:{seen}", addon.actions.DeckBrowser())
        self.assertFalse(payload.payload()["strike"]["fresh"])
        mw.addonManager.config["stakes"] = "peaceful"
        p = payload.payload()
        self.assertEqual((len(p["craters"]), [t["ago"] for t in p["trees"]]), (1, [5, 4]))

    def test_a_decks_own_forest_shows_the_trees_alone(self):
        studied_every_day_but_the_break(stakes="wild", deck_forest_mode="own")
        state.save_state({"stakes": "wild", "stakes_since": TODAY - 60})
        p = payload.payload(10)
        self.assertNotIn("craters", p)
        self.assertEqual(p["stats"]["trees"], 23)


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


class FlowerTests(unittest.TestCase):
    def test_a_big_day_of_learning_is_marked_on_its_tree(self):
        # two cards a day for a week and more, then eight in one day
        reset([(i, 10, 20 - i // 2) for i in range(20)] + [(100 + i, 10, 3) for i in range(8)])
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual(trees[3]["big"], 2)  # what it beat: the most in the two weeks before
        self.assertFalse(any(t.get("big") for a, t in trees.items() if a != 3))


if __name__ == "__main__":
    unittest.main()

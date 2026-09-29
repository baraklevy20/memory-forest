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
            mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", (ms(d, 18),))


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
        reset(PLANTED, {"stakes": "merciless"})
        with mock.patch.object(addon.settings, "is_open", return_value=True):
            self.assertEqual(addon.events_state._stakes_since("merciless"), 0)
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

    def test_the_animals_leave_with_the_forest_and_are_earned_again(self):
        # enough reviews for the fox, all before the break
        for stakes in ("peaceful", "wild"):
            studied_every_day_but_the_break(stakes=stakes)
            mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                      [(ms(30, 12) + i,) for i in range(10_000)])
            state.save_state({"stakes": stakes, "stakes_since": TODAY - 60})
            p = payload.payload()
            if stakes == "peaceful":
                self.assertIn("fox", [v["key"] for v in p["visitors"]])
            else:
                self.assertEqual(p["visitors"], [])
                self.assertEqual(p["stats"]["reviews"], 12)  # a review a day since, and the two cards planted since

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
        reset([(1, 10, 20)], {"stakes": "wild"})  # nothing new for twenty days
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", (ms(0, 18),))  # reviewing today
        self.assertGreater(payload.payload()["stagnation"], 0)

    def test_not_while_you_are_away_nor_on_a_decks_own_forest(self):
        reset([(1, 10, 20)])  # nothing since, not even a review: a break, not coasting
        self.assertEqual(payload.payload()["stagnation"], 0)
        reset([(1, 10, 20)], {"deck_forest_mode": "own"})
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", (ms(0, 18),))
        self.assertNotIn("stagnation", payload.payload(10))


class FlowerTests(unittest.TestCase):
    def test_a_big_day_of_learning_is_marked_on_its_tree(self):
        # two cards a day for a week and more, then eight in one day
        reset([(i, 10, 20 - i // 2) for i in range(20)] + [(100 + i, 10, 3) for i in range(8)])
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual(trees[3]["big"], 2)  # what it beat: the most in the two weeks before
        self.assertFalse(any(t.get("big") for a, t in trees.items() if a != 3))



def overdue(n: int) -> None:
    """`n` more reviews, due yesterday."""
    for i in range(n):
        mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) "
                              "values (?, ?, 10, 0, 2, 2, 30, '{}', ?)", (5000 + i, 5000 + i, TODAY - 1))


class PeacefulTests(unittest.TestCase):
    """Peaceful brings the good things only: no crows, no tall grass, no tumbleweeds."""

    def coasting_with_a_leech_and_a_backlog(self, stakes):
        reset([(1, 10, 30), (2, 10, 20)], {"stakes": stakes}, leeches={1})
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 1, 1, 1)", (ms(0),))  # reviewing today
        overdue(100)
        return payload.payload()

    def test_peaceful_keeps_the_bad_things_away(self):
        p = self.coasting_with_a_leech_and_a_backlog("peaceful")
        self.assertFalse(any(t.get("leeches") for t in p["trees"]))
        self.assertEqual((p["stagnation"], p["backlog"]["hell"]), (0, 0))
        self.assertEqual(p["backlog"]["overdue"], 100)  # still counted, to know when it is cleared

    def test_wild_brings_them(self):
        p = self.coasting_with_a_leech_and_a_backlog("wild")
        self.assertTrue(any(t.get("leeches") for t in p["trees"]))
        self.assertGreater(p["stagnation"], 0)
        self.assertGreater(p["backlog"]["hell"], 0)


class BacklogTests(unittest.TestCase):
    def test_review_hell_and_the_day_it_is_cleared(self):
        reset([(1, 10, 5)], {"stakes": "wild"})
        overdue(60)
        self.assertEqual(payload.payload()["backlog"], {"overdue": 60, "usual": 1, "hell": 1.0, "cleared": False})
        mw.col.db.con.execute("delete from cards where id >= 5000")  # all done
        p = payload.payload()
        self.assertEqual((p["backlog"]["cleared"], p["backlog"]["was"]), (True, 1.0))  # as deep as it was
        self.assertEqual(p["journal"], "You cleared your overdue reviews. The tumbleweeds blew away.")
        self.assertTrue(payload.payload()["backlog"]["cleared"])  # all day long

    def test_a_small_backlog_is_no_hell(self):
        reset([(1, 10, 5)], {"stakes": "wild"})
        overdue(20)
        self.assertEqual(payload.payload()["backlog"]["hell"], 0)
        mw.col.db.con.execute("delete from cards where id >= 5000")
        self.assertFalse(payload.payload()["backlog"]["cleared"])  # there was no hell to clear

    def test_a_left_out_deck_brings_no_backlog(self):
        reset([(1, 10, 5)], {"stakes": "wild", "excluded_decks": [10]})
        overdue(60)
        self.assertEqual(payload.payload()["backlog"]["overdue"], 0)


class CuredTests(unittest.TestCase):
    def test_a_cured_leech_brings_a_robin_and_takes_its_crow(self):
        reset([(1, 10, 30), (2, 10, 20)], {"stakes": "wild"})
        mw.col.db.con.execute("update cards set ivl = 25 where id = 1")
        mw.col.db.con.execute("update notes set tags = ' leech ' where id = 1")
        mw.col.db.con.execute("insert into revlog values (?, 1, 3, 1, 25, 12)", (ms(2),))  # mature two days ago
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual((trees[30].get("cured"), trees[30].get("leeches"), trees[20].get("cured")), (1, None, None))


if __name__ == "__main__":
    unittest.main()

"""The study events on Anki's side (events_state.py): Nature read from the days you
studied, what is remembered of what was shown, and what the page is sent - in a stand-in Anki."""

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


def studied_every_day_but(missed, **config):
    """PLANTED's forest, with a review every day but the `missed` ones."""
    reset(PLANTED, config)
    mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                              [(ms(d, 18),) for d in range(41) if d not in missed])
    mw.col.mod += 1  # a new review log: the days studied are read again


class NatureTests(unittest.TestCase):
    def test_a_day_away_on_merciless_takes_the_forest(self):
        studied_every_day_but_the_break(nature="merciless")
        p = payload.payload()
        self.assertEqual(len(p["craters"]), 1)
        self.assertEqual(p["strike"]["lost"], 21)
        self.assertEqual([t["ago"] for t in p["trees"]], [5, 4])  # only what grew since
        # seventeen days on it is no news: it doesn't play by itself, and the journal is quiet
        self.assertEqual((p["strike"]["news"], p["strike"]["fresh"]), (False, False))
        self.assertNotIn("asteroid", p["journal"])
        self.assertEqual(addon.events_state.strike_line(dict(p, strike=dict(p["strike"], news=True, told=True))),
                         "An asteroid took your forest of 21 trees. A new one grows from here.")
        self.assertFalse({"strike_days", "stakes_since"} & set(state.load_state()))  # nothing of it remembered

    def test_changing_the_setting_changes_it_back_and_forth(self):
        studied_every_day_but_the_break(nature="merciless")
        self.assertEqual(payload.payload()["stats"]["trees"], 2)
        mw.addonManager.config["nature"] = "peaceful"
        p = payload.payload()
        self.assertEqual((p["craters"], p["strike"], p["stats"]["trees"]), ([], None, 23))
        mw.addonManager.config["nature"] = "merciless"
        self.assertEqual(len(payload.payload()["craters"]), 1)

    def test_a_recent_strike_plays_once(self):
        studied_every_day_but({3}, nature="merciless")
        p = payload.payload()
        self.assertEqual((p["strike"]["news"], p["strike"]["fresh"]), (True, True))
        self.assertIn("asteroid", p["journal"])
        addon.actions.on_js_message((False, None), f"{state.MODULE}:struck:{p['strike']['seen']}", addon.actions.DeckBrowser())
        self.assertFalse(payload.payload()["strike"]["fresh"])

    def test_the_settings_preview_shows_the_crater_without_playing_it(self):
        studied_every_day_but({3}, nature="merciless")
        with mock.patch.object(addon.settings, "is_open", return_value=True):
            p = payload.payload()
        self.assertEqual((len(p["craters"]), p["strike"]["fresh"]), (1, False))
        self.assertTrue(payload.payload()["strike"]["fresh"])  # it plays once the dialog is closed

    def test_wild_sets_part_of_the_forest_on_fire(self):
        studied_every_day_but({1, 2, 3}, nature="wild")  # three days away, back today
        p = payload.payload()
        fire, burning = p["fire"], [t for t in p["trees"] if t.get("burn")]
        self.assertEqual((fire["trees"], fire["left"], len(burning)), (2, 6, 2))  # 10% of the 23 trees
        self.assertEqual({t["burn"] for t in burning}, {round(1 - 1 / 7, 3)})
        self.assertEqual((p["craters"], p["stats"]["trees"]), ([], 23))  # every tree still counts
        self.assertEqual(p["journal"], "A fire broke out while you were away: 2 trees are burning. Study on 7 days to put it out.")
        mw.addonManager.config["nature"] = "peaceful"
        p = payload.payload()
        self.assertEqual((p["fire"], [t for t in p["trees"] if t.get("burn")]), (None, []))

    def test_the_day_the_fire_goes_out(self):
        studied_every_day_but({7, 8}, nature="wild")  # back for seven days, today the seventh
        p = payload.payload()
        self.assertEqual((p["fire"]["out"], p["fire"]["trees"]), (True, 0))
        self.assertEqual(p["journal"], "The last of the fire is out. Your forest is green again.")

    def test_a_decks_own_forest_shows_the_trees_alone(self):
        studied_every_day_but_the_break(nature="merciless", deck_forest_mode="own")
        p = payload.payload(10)
        self.assertNotIn("craters", p)
        self.assertEqual(p["stats"]["trees"], 23)


class NoStrikeFromHalfTheStoryTests(unittest.TestCase):
    """A strike only comes from the whole review log: after a sync has brought in the other
    devices' reviews, and from every deck."""

    def test_no_unseen_strike_before_a_sync_when_the_profile_syncs(self):
        ev = addon.events_state
        studied_every_day_but({3}, nature="merciless")
        mw.pm.sync_auth = lambda: object()  # logged in to AnkiWeb
        try:
            ev._synced.clear()
            p = payload.payload()  # the deck list, drawn before the startup sync
            self.assertEqual((p["craters"], p["strike"], p["stats"]["trees"]), ([], None, 23))
            ev.sync_started()
            self.assertEqual(payload.payload()["craters"], [])  # the forest written for your phone as the sync starts
            ev.sync_finished()  # nothing came in: the day away was real
            p = payload.payload()
            self.assertEqual((len(p["craters"]), p["strike"]["fresh"]), (1, True))
            ev.mark_seen(p["strike"]["seen"])
            ev._synced.clear()  # a later session: a strike already seen shows before any sync
            self.assertEqual(len(payload.payload()["craters"]), 1)
        finally:
            del mw.pm.sync_auth
            ev._synced.clear()
            ev._syncing = False

    def test_days_studied_only_in_a_left_out_deck_are_not_missed(self):
        def studied_the_break_in_deck_20(**config):
            studied_every_day_but_the_break(nature="merciless", **config)
            mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) "
                                  "values (500, 500, 20, 0, 2, 2, 30, '{}', ?)", (TODAY + 30,))
            mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 500, 3, 1)", [(ms(d),) for d in MISSED])
        studied_the_break_in_deck_20(excluded_decks=[20])
        p = payload.payload()
        self.assertEqual((p["craters"], p["strike"]), ([], None))
        self.assertEqual(p["stats"]["trees"], 23)  # and the German card still plants nothing
        # ... but looking at the forest on your phone is not studying
        reset([])
        studied_the_break_in_deck_20()
        with mock.patch.object(addon.events_state, "phone_decks", return_value={20}):
            self.assertEqual(len(payload.payload()["craters"]), 1)


class StrikeJournalTests(unittest.TestCase):
    def test_the_strike_is_news_until_it_has_played_and_that_day(self):
        # a day away three days ago, and a first card in the new forest today
        reset(PLANTED[:-2] + [(102, 10, 0)], {"nature": "merciless"})
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(41) if d != 3])
        mw.col.mod += 1
        p = payload.payload()
        self.assertIn("asteroid", addon.events_state.news_line(p))
        addon.events_state.mark_seen(p["strike"]["seen"])
        self.assertIn("asteroid", payload.payload()["journal"])  # all that day
        s = state.load_state()
        state.save_state(dict(s, strike_seen_day=TODAY - 1))  # seen yesterday
        p = payload.payload()
        self.assertEqual(addon.events_state.strike_line(p), "")
        self.assertEqual(p["journal"], "Your first tree. It holds 1 card.")


class AnimalTests(unittest.TestCase):
    """The animals stay once they have come (only an asteroid sends them away), and each is
    announced on the day it came."""

    def studied_every_day(self):
        """A few days' forest, with nothing yet for any animal."""
        reset([(1, 10, 3)])
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", [(ms(d, 18),) for d in range(4)])

    def fox_reviews(self):
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(30, 12) + i,) for i in range(10_000)])
        mw.col.mod += 1

    def test_the_first_look_remembers_them_without_announcing_them(self):
        self.studied_every_day()
        self.fox_reviews()
        p = payload.payload()
        self.assertEqual([(v["key"], v["new"]) for v in p["visitors"]], [("fox", False)])
        self.assertNotIn("wandered", p["journal"])

    def test_an_animal_is_announced_the_day_it_comes_and_stays(self):
        self.studied_every_day()
        self.assertEqual(payload.payload()["visitors"], [])
        self.fox_reviews()
        for _ in range(2):  # all day long
            p = payload.payload()
            self.assertEqual([(v["key"], v["new"]) for v in p["visitors"]], [("fox", True)])
            self.assertEqual(p["journal"], "A fox wandered in: you passed 10,000 reviews.")
        mw.col.db.con.execute("delete from revlog where cid = 999 and id between ? and ?", (ms(30, 12), ms(30, 12) + 10_000))
        mw.col.mod += 1
        p = payload.payload()
        self.assertLess(p["stats"]["reviews"], 10_000)
        self.assertEqual([v["key"] for v in p["visitors"]], ["fox"])  # it stays

    def test_an_asteroid_sends_them_away_and_changing_back_brings_them_quietly(self):
        studied_every_day_but_the_break()
        self.fox_reviews()
        self.assertIn("fox", [v["key"] for v in payload.payload()["visitors"]])
        mw.addonManager.config["nature"] = "merciless"
        p = payload.payload()
        self.assertEqual((len(p["craters"]), p["visitors"]), (1, []))
        self.assertEqual(p["stats"]["reviews"], 12)  # a review a day since, and the two cards planted since
        mw.addonManager.config["nature"] = "peaceful"
        p = payload.payload()
        self.assertIn("fox", [v["key"] for v in p["visitors"]])
        self.assertFalse(any(v["new"] for v in p["visitors"]))
        self.assertNotIn("wandered", p["journal"])


class GrassTests(unittest.TestCase):
    def test_the_grass_grows_tall_while_you_review_without_new_cards(self):
        reset([(1, 10, 20)], {"nature": "wild"})  # nothing new for twenty days
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

    def coasting_with_a_leech_and_a_backlog(self, nature):
        reset([(1, 10, 30), (2, 10, 20)], {"nature": nature}, leeches={1})
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
        reset([(1, 10, 5)], {"nature": "wild"})
        # a review a day since (on Wild, days away would set the forest on fire)
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", [(ms(d, 18),) for d in range(5)])
        overdue(60)
        self.assertEqual(payload.payload()["backlog"], {"overdue": 60, "usual": 1, "hell": 1.0, "cleared": False})
        mw.col.db.con.execute("delete from cards where id >= 5000")  # all done
        p = payload.payload()
        self.assertEqual((p["backlog"]["cleared"], p["backlog"]["was"]), (True, 1.0))  # as deep as it was
        self.assertEqual(p["journal"], "You cleared your overdue reviews. The tumbleweeds blew away.")
        self.assertTrue(payload.payload()["backlog"]["cleared"])  # all day long

    def test_a_small_backlog_is_no_hell(self):
        reset([(1, 10, 5)], {"nature": "wild"})
        overdue(20)
        self.assertEqual(payload.payload()["backlog"]["hell"], 0)
        mw.col.db.con.execute("delete from cards where id >= 5000")
        self.assertFalse(payload.payload()["backlog"]["cleared"])  # there was no hell to clear

    def test_a_left_out_deck_brings_no_backlog(self):
        reset([(1, 10, 5)], {"nature": "wild", "excluded_decks": [10]})
        overdue(60)
        self.assertEqual(payload.payload()["backlog"]["overdue"], 0)


class CuredTests(unittest.TestCase):
    def test_a_cured_leech_brings_a_robin_and_takes_its_crow(self):
        reset([(1, 10, 30), (2, 10, 20)], {"nature": "wild"})
        mw.col.db.con.execute("update cards set ivl = 25 where id = 1")
        mw.col.db.con.execute("update notes set tags = ' leech ' where id = 1")
        mw.col.db.con.execute("insert into revlog values (?, 1, 3, 1, 25, 12)", (ms(2),))  # mature two days ago
        trees = {t["ago"]: t for t in payload.payload()["trees"]}
        self.assertEqual((trees[30].get("cured"), trees[30].get("leeches"), trees[20].get("cured")), (1, None, None))


if __name__ == "__main__":
    unittest.main()

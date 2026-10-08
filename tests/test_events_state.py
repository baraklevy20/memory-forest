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


def a_new_card(did: int = 10) -> None:
    """A card not yet learned, in deck `did`."""
    mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) "
                          "values (900, 900, ?, 0, 0, 0, 0, '{}', 1)", (did,))


class Unsynced:
    """A profile that syncs, before its first sync of the session."""

    def __enter__(self):
        mw.pm.sync_auth = lambda: object()  # logged in to AnkiWeb
        addon.events_state._synced.clear()
        return addon.events_state

    def __exit__(self, *_exc):
        del mw.pm.sync_auth
        addon.events_state._synced.clear()
        addon.events_state._syncing = False


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

    def test_the_forest_a_strike_took_comes_only_to_play_it(self):
        studied_every_day_but({3}, nature="merciless")
        p = payload.payload()
        self.assertEqual(len(p["strike"]["before"]), 23)  # it plays by itself: the page needs it now
        seen = p["strike"]["seen"]
        message = lambda key: f"{state.MODULE}:strike:{key}"  # noqa: E731
        addon.actions.on_js_message((False, None), f"{state.MODULE}:struck:{seen}", addon.actions.DeckBrowser())
        self.assertNotIn("before", payload.payload()["strike"])  # seen: a replay asks for it
        handled, got = addon.actions.on_js_message((False, None), message(seen), addon.actions.DeckBrowser())
        self.assertEqual((handled, len(got["before"])), (True, 23))
        self.assertEqual(addon.actions.on_js_message((False, None), message("another"), addon.actions.DeckBrowser()),
                         (True, None))  # not the latest strike: nothing to play

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
        self.assertEqual((fire["trees"], fire["left"], len(burning)), (1, 6, 1))  # 5% of the 23 trees
        self.assertEqual({t["burn"] for t in burning}, {round(1 - 1 / 7, 3)})
        self.assertEqual((p["craters"], p["stats"]["trees"]), ([], 23))  # every tree still counts
        self.assertEqual(p["journal"], "A fire broke out while you were away: 1 tree is burning. Study on 7 days to put it out.")
        mw.addonManager.config["nature"] = "peaceful"
        p = payload.payload()
        self.assertEqual((p["fire"], [t for t in p["trees"] if t.get("burn")]), (None, []))

    def test_the_day_the_fire_goes_out(self):
        studied_every_day_but({7, 8, 9}, nature="wild")  # back for seven days, today the seventh
        p = payload.payload()
        self.assertEqual((p["fire"]["out"], p["fire"]["trees"]), (True, 0))
        self.assertEqual(p["journal"], "The last of the fire is out. Your forest is green again.")

    def test_a_decks_own_forest_takes_the_strike_too(self):
        studied_every_day_but_the_break(nature="merciless", deck_forest_mode="own")
        main, own = payload.payload(), payload.payload(10)  # deck 10 holds every card
        self.assertEqual(len(own["craters"]), 1)
        self.assertEqual((own["stats"]["trees"], [t["ago"] for t in own["trees"]]),
                         (main["stats"]["trees"], [t["ago"] for t in main["trees"]]))


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


    def test_craters_already_shown_stay_as_they_were_before_a_sync(self):
        # ten strikes shown last session, each with its own trees, and an eleventh since
        missed = {30, 27, 24, 21, 18, 15, 12, 9, 6, 3}
        reset([(i, 10, d) for i, d in enumerate(range(33, 0, -1)) if d not in missed | {1}], {"nature": "merciless"})
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(34) if d not in missed])
        p = payload.payload()
        self.assertEqual(len(p["craters"]), 10)
        before = [(c["date"], c["lost"]) for c in p["craters"]]
        with Unsynced() as ev:
            self.assertEqual([(c["date"], c["lost"]) for c in payload.payload()["craters"]], before)
            ev.sync_started()
            self.assertEqual([(c["date"], c["lost"]) for c in payload.payload()["craters"]], before)
        # a day away since, not seen yet: it waits for the sync, the others stay put
        mw.col.db.con.execute("delete from revlog where cid = 999 and id between ? and ?", (ms(1), ms(1, 23)))
        payload.after_sync()  # (read afresh: a review gone is no newer review)
        with Unsynced() as ev:
            self.assertEqual([(c["date"], c["lost"]) for c in payload.payload()["craters"]], before)
            ev.sync_finished()
            self.assertEqual(len(payload.payload()["craters"]), 11)

    def test_no_doom_before_a_sync(self):
        studied_every_day_but({0}, nature="merciless")  # nothing yet today
        with Unsynced() as ev:
            self.assertIsNone(payload.payload()["doom"])
            ev.sync_finished()
            self.assertIsNotNone(payload.payload()["doom"])
            ev._synced.clear()  # a later session the same day: shown already, it stays
            self.assertIsNotNone(payload.payload()["doom"])

    def test_no_smoke_nor_fire_before_a_sync(self):
        for missed, kind in (({0, 1, 2}, "smoke"), ({1, 2, 3}, "burn")):
            studied_every_day_but(missed, nature="wild")
            with Unsynced() as ev:
                p = payload.payload()
                self.assertEqual((p["fire"], [t for t in p["trees"] if t.get(kind)]), (None, []))
                self.assertNotIn("fire", p["journal"].lower())
                self.assertNotIn("smoke", p["journal"].lower())
                ev.sync_started()  # the forest written for your phone as the sync starts
                self.assertIsNone(payload.payload()["fire"])
                ev.sync_finished()
                p = payload.payload()
                self.assertTrue(p["fire"] and [t for t in p["trees"] if t.get(kind)])
                ev._synced.clear()  # a later session: shown already, it stays
                self.assertTrue(payload.payload()["fire"])


class StrikeJournalTests(unittest.TestCase):
    def test_the_strike_is_news_until_it_has_played_and_that_day(self):
        # a day away three days ago, and a first card in the new forest today
        reset(PLANTED[:-2] + [(102, 10, 0)], {"nature": "merciless"})
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(41) if d != 3])
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
        payload.after_sync()  # reviews from a month back only ever come in with a sync

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
        payload.after_sync()  # old reviews gone (a sync from elsewhere): read afresh
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
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(20)])  # reviewing every day
        self.assertEqual(payload.payload()["stagnation"], 0)  # no new card left to learn: nothing to stall
        a_new_card()
        p = payload.payload()
        self.assertGreater(p["stagnation"], 0)
        self.assertEqual(p["journal"], "The grass is growing tall: no new cards for 2 weeks.")

    def test_new_cards_only_in_a_left_out_deck_grow_no_grass(self):
        reset([(1, 10, 20)], {"nature": "wild", "excluded_decks": [20]})
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)", (ms(0, 18),))
        a_new_card(20)
        self.assertEqual(payload.payload()["stagnation"], 0)

    def test_not_while_you_are_away(self):
        reset([(1, 10, 20)])  # nothing since, not even a review: a break, not coasting
        self.assertEqual(payload.payload()["stagnation"], 0)


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
    """Peaceful brings the good things only: no crows, no tall grass, no tumbleweeds - on
    every forest. Wild and Merciless bring them all."""

    VIEWS = {"main": (None, None), "highlight": ("highlight", 10), "own": ("own", 10)}

    def coasting_with_a_leech_and_a_backlog(self, nature, view="main"):
        mode, did = self.VIEWS[view]
        reset([(1, 10, 30), (2, 10, 20)], {"nature": nature, **({"deck_forest_mode": mode} if mode else {})}, leeches={1})
        # a review every day since (no day missed: Merciless's asteroid would take the crows
        # with the forest), the one today on the leech
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(1, 31)])
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, 1, 1, 1)", (ms(0),))
        overdue(100)
        a_new_card()
        return payload.payload(did, highlight=mode == "highlight")

    def test_peaceful_keeps_the_bad_things_away(self):
        for view in self.VIEWS:
            with self.subTest(view=view):
                p = self.coasting_with_a_leech_and_a_backlog("peaceful", view)
                self.assertFalse(any(t.get("leeches") for t in p["trees"]))
                self.assertEqual((p["stagnation"], p["backlog"]["hell"]), (0, 0))
                self.assertEqual(p["backlog"]["overdue"], 100)  # still counted, to know when it is cleared

    def test_wild_and_merciless_bring_them(self):
        for nature in ("wild", "merciless"):
            for view in self.VIEWS:
                with self.subTest(nature=nature, view=view):
                    p = self.coasting_with_a_leech_and_a_backlog(nature, view)
                    self.assertEqual(p["craters"], [])  # nothing struck: the crows are there to see
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



# PLANTED with every other card in deck 20: deck 10 holds half of each stretch of trees
SPLIT = [(cid, 10 if cid % 2 == 0 else 20, ago) for cid, _did, ago in PLANTED]
# (and the what's new note, which only the deck list's forest shows)
DECK_ONLY = {"deckId", "deckName", "highlight", "litCount", "news"}


class DeckForestTests(unittest.TestCase):
    """A deck's screen shows the main forest with that deck's trees lit, or a forest of the
    deck's own (the Deck screens setting) - and either one acts as the main forest does:
    Nature, the bad habits and the good days all come to it."""

    def compared(self, view: str, did: int = 10) -> tuple:
        """(the main forest, the deck's), each read first in turn: what one leaves behind
        (a strike shown, the animals) must not change the other."""
        pages = []
        for first_main in (True, False):
            mw.addonManager.config["deck_forest_mode"] = view
            calls = [payload.payload, lambda: payload.payload(did, highlight=view == "highlight")]
            got = [c() for c in (calls if first_main else calls[::-1])]
            pages.append(got if first_main else got[::-1])
        return pages

    def scenarios(self):
        """Each Nature, and each event it brings, set up afresh."""
        peaceful = PeacefulTests()
        return {
            "merciless strike": lambda: studied_every_day_but({3}, nature="merciless"),
            "wild fire": lambda: studied_every_day_but({1, 2, 3}, nature="wild"),
            "wild smoke": lambda: studied_every_day_but({0, 1, 2}, nature="wild"),  # and none yet today
            "peaceful break": lambda: studied_every_day_but(set(range(1, 9)), nature="peaceful"),
            "wild leech and backlog": lambda: peaceful.coasting_with_a_leech_and_a_backlog("wild"),
            "peaceful leech and backlog": lambda: peaceful.coasting_with_a_leech_and_a_backlog("peaceful"),
        }

    def test_the_lit_up_forest_is_the_main_forest(self):
        for name, setup in self.scenarios().items():
            with self.subTest(name):
                setup()
                for main, deck in self.compared("highlight"):
                    self.assertTrue(deck["highlight"])
                    leave = lambda p: {k: v for k, v in p.items() if k not in DECK_ONLY | {"trees", "strike"}}  # noqa: E731
                    self.assertEqual(leave(deck), leave(main))
                    self.assertEqual([{k: v for k, v in t.items() if k != "dim"} for t in deck["trees"]], main["trees"])

    def test_a_forest_of_the_decks_own_has_the_main_forests_events_when_it_holds_every_card(self):
        # (the rest may differ: the reviews every day are on a card of no deck, so the deck's
        # own streak, review count and ponds are its own)
        def events_of(p):
            marks = [{k: t[k] for k in ("leeches", "cured", "big", "burn") if k in t} for t in p["trees"]]
            craters = [c["date"] for c in p["craters"]]
            return (p["nature"], craters, bool(p["strike"]), p["doom"], p["fire"], p["stagnation"], p["backlog"],
                    [t["ago"] for t in p["trees"]], marks)

        for name, setup in self.scenarios().items():
            with self.subTest(name):
                setup()  # every card is deck 10's
                for main, own in self.compared("own"):
                    self.assertFalse(own["highlight"])
                    self.assertEqual(events_of(own), events_of(main))

    def test_the_lit_trees_are_counted_as_drawn(self):
        for nature, missed in (("merciless", {10}), ("wild", {1, 2, 3}), ("peaceful", set())):
            with self.subTest(nature):
                reset(SPLIT, {"nature": nature})
                mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                          [(ms(d, 18),) for d in range(41) if d not in missed])
                p = payload.payload(10, highlight=True)
                self.assertEqual(p["litCount"], sum(1 for t in p["trees"] if not t["dim"]))
                self.assertGreater(p["litCount"], 0)

    def own(self, missed, nature, cards=SPLIT):
        reset(cards, {"nature": nature, "deck_forest_mode": "own"})
        mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                  [(ms(d, 18),) for d in range(41) if d not in missed])
        return payload.payload(10)

    def test_the_asteroid_takes_a_decks_own_forest_from_the_day_it_struck(self):
        p = self.own({10}, "merciless")
        self.assertEqual(len(p["craters"]), 1)
        self.assertTrue(all(t["ago"] < 10 for t in p["trees"]))  # only what grew since

    def test_the_fire_burns_a_decks_own_forest(self):
        p = self.own({1, 2, 3}, "wild")
        self.assertTrue(p["fire"] and p["fire"]["trees"])
        self.assertTrue(any(t.get("burn") for t in p["trees"]))
        self.assertTrue(self.own({0, 1, 2}, "wild")["fire"]["smoke"])

    def test_a_day_studied_in_another_deck_is_no_day_missed(self):
        # deck 10's cards were only studied the day each was planted; the reviews every day
        # are elsewhere - Nature goes by every deck, as on the main forest
        p = self.own(set(), "merciless")
        self.assertEqual((p["craters"], p["doom"]), ([], None))

    def test_flowers_on_a_decks_own_big_days(self):
        reset([(i, 10, 20 - i // 2) for i in range(20)] + [(100 + i, 10, 3) for i in range(8)], {"deck_forest_mode": "own"})
        trees = {t["ago"]: t for t in payload.payload(10)["trees"]}
        self.assertEqual(trees[3].get("big"), 2)

    def test_a_robin_for_a_leech_cured_in_the_deck_only(self):
        for deck, robin in ((10, 1), (20, None)):
            with self.subTest(deck=deck):
                # card 1 (the leech) in `deck`, card 2 in deck 10: both on the tree of 30 days ago
                reset([(1, deck, 30), (2, 10, 30)], {"nature": "wild", "deck_forest_mode": "own"})
                mw.col.db.con.execute("update cards set ivl = 25 where id = 1")
                mw.col.db.con.execute("update notes set tags = ' leech ' where id = 1")
                mw.col.db.con.execute("insert into revlog values (?, 1, 3, 1, 25, 12)", (ms(2),))
                trees = {t["ago"]: t for t in payload.payload(10)["trees"]}
                self.assertEqual(trees[30].get("cured"), robin)

    def test_the_grass_grows_on_a_deck_left_without_new_cards(self):
        for new_in, grass in ((10, True), (20, False)):  # a new card left to learn in that deck
            with self.subTest(new_in=new_in):
                reset([(1, 10, 20), (2, 20, 1)], {"nature": "wild", "deck_forest_mode": "own"})
                mw.col.db.con.executemany("insert into revlog (id, cid, ease, type) values (?, 999, 3, 1)",
                                          [(ms(d, 18),) for d in range(20)])
                a_new_card(new_in)
                self.assertEqual(payload.payload(10)["stagnation"] > 0, grass)

    def test_tumbleweeds_on_a_decks_own_forest(self):
        p = PeacefulTests().coasting_with_a_leech_and_a_backlog("wild", "own")
        self.assertGreater(p["backlog"]["hell"], 0)

    def test_no_pond_for_a_deck_left_alone_while_you_studied_others(self):
        # deck 10 untouched for 35 days, but a review somewhere every day
        p = self.own(set(), "peaceful", [(1, 10, 40), (2, 10, 5)])
        self.assertEqual([t.get("gap") for t in p["trees"]], [None, None])

    def test_a_break_from_every_deck_is_the_same_pond_on_a_decks_own_forest(self):
        studied_every_day_but_the_break(deck_forest_mode="own")  # eight days of nothing at all
        ponds = lambda p: [(t["ago"], t.get("gap"), t.get("gap_from"), t.get("gap_to")) for t in p["trees"] if t.get("gap")]  # noqa: E731
        main, own = payload.payload(), payload.payload(10)
        self.assertEqual(len(ponds(main)), 1)
        self.assertEqual(ponds(own), ponds(main))

    def test_a_decks_own_forest_earns_its_own_animals(self):
        AnimalTests().studied_every_day()
        AnimalTests().fox_reviews()  # the fox's reviews are on a card of no deck
        mw.addonManager.config["deck_forest_mode"] = "own"
        self.assertEqual([v["key"] for v in payload.payload()["visitors"]], ["fox"])
        self.assertEqual(payload.payload(10)["visitors"], [])
        p = payload.payload()
        self.assertEqual([(v["key"], v["new"]) for v in p["visitors"]], [("fox", False)])  # not announced again

    def test_the_strike_plays_once_whichever_forest_shows_it(self):
        studied_every_day_but({3}, nature="merciless", deck_forest_mode="own")
        main = payload.payload()
        self.assertTrue(main["strike"]["fresh"])
        addon.events_state.mark_seen(main["strike"]["seen"])
        self.assertFalse(payload.payload(10)["strike"]["fresh"])


if __name__ == "__main__":
    unittest.main()

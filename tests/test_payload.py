"""What a panel is drawn from (payload.py), in a stand-in Anki."""

from __future__ import annotations

import unittest
from unittest import mock

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

    def test_the_calendar_holds_each_day_s_reviews_from_the_first_to_today(self):
        reset(CARDS)
        cal = payload.payload()["calendar"]
        self.assertEqual(cal["view"], "timeline")
        self.assertEqual(len(cal["days"]), 6)  # days 5 to 0 ago
        self.assertEqual([i for i, n in enumerate(cal["days"]) if n], [0, 2])  # 5 and 3 days ago
        self.assertEqual(cal["start"], addon.study_log.day_date(5, mw.col.sched.day_cutoff).isoformat())
        self.assertEqual(len(cal["due"]), payload.CALENDAR_DUE_DAYS)

    def test_with_a_start_date_the_calendar_still_has_the_record_before_it(self):
        reset(CARDS, {"ignore_before": "2026-09-16"})  # the forest from 3 days ago: the day 5 days ago is before it
        cal = payload.payload()["calendar"]
        self.assertEqual(cal["forestStart"], "2026-09-16")
        self.assertEqual(len(cal["days"]), 6)  # from day 5 ago, as without a start date
        self.assertEqual([i for i, n in enumerate(cal["days"]) if n], [0, 2])
        reset(CARDS, {"ignore_before": "2026-09-16", "calendar_record": False})  # a clean slate: from the start date only
        self.assertIsNone(payload.payload()["calendar"]["forestStart"])
        self.assertEqual(len(payload.payload()["calendar"]["days"]), 4)
        reset(CARDS)
        self.assertIsNone(payload.payload()["calendar"]["forestStart"])

    def test_with_a_start_date_the_streak_is_still_your_real_one(self):
        days = [(1, 10, 2), (2, 10, 1), (3, 10, 0)]  # studied three days running, up to today
        reset(days, {"ignore_before": "2026-09-18"})  # the forest from yesterday
        p = payload.payload()
        self.assertEqual(p["stats"]["streak"], 3)  # the caption: the streak isn't broken by it
        self.assertEqual(payload._forest()["stats"]["streak"], 2)  # the forest's own, for its animals
        self.assertFalse(p["calendar"]["streakFromStart"])
        reset(days, {"ignore_before": "2026-09-18", "streak_from_start": True})  # counted from the start date too
        p = payload.payload()
        self.assertEqual(p["stats"]["streak"], 2)
        self.assertTrue(p["calendar"]["streakFromStart"])

    def test_the_streak_is_the_calendar_s_own(self):
        days = [(1, 10, 2), (2, 20, 1), (3, 10, 1), (4, 10, 0)]  # French three days running, German only yesterday
        reset(days)
        self.assertEqual(payload.payload(20, highlight=True)["stats"]["streak"], 1)  # under the main forest: German's calendar
        self.assertEqual(payload.payload(10, highlight=True)["stats"]["streak"], 3)
        reset(days, {"calendar_decks": False})  # no calendar: the main forest's own streak
        self.assertEqual(payload.payload(20, highlight=True)["stats"]["streak"], 3)
        reset(days, {"ignore_before": "2026-09-18", "calendar_record": False})  # the calendar from the start date only
        self.assertEqual(payload.payload()["stats"]["streak"], 2)
        reset(days, {"ignore_before": "2026-09-18", "calendar_record": False, "calendar_main": False})  # no calendar there
        self.assertEqual(payload.payload()["stats"]["streak"], 3)

    def test_a_day_with_nothing_due_never_breaks_the_streak(self):
        reset([(1, 10, 5), (2, 10, 4), (3, 10, 1)])  # each answered once, and due nowhere since (ivl 0)
        p = payload.payload()
        self.assertEqual(p["stats"]["streak"], 3)  # 2 and 3 days ago had nothing due: passed over
        self.assertEqual(p["calendar"]["free"], [[3, 2], [0, 0]])
        # card 2 due again the day after it was answered, and never since: those days were missed
        mw.col.db.con.execute("update revlog set ivl = 1 where cid = 2")
        addon.payload.forget_remembered()
        p = payload.payload()
        self.assertEqual(p["stats"]["streak"], 1)
        self.assertEqual(p["calendar"]["free"], [])

    def test_a_days_cards_since_deleted_are_counted_for_its_tooltip(self):
        reset([(1, 10, 5), (2, 10, 5), (3, 10, 3)])
        mw.col.db.con.execute("delete from cards where id = 2")  # its review stays in the log, as Anki keeps it
        addon.payload.forget_remembered()
        cal = payload.payload()["calendar"]
        self.assertEqual(cal["gone"], [[5, 1, 2]])  # 5 days ago: one of its two cards is gone
        self.assertEqual(cal["days"][0], 2)  # and still counted in that day's reviews
        self.assertEqual(payload.payload(10, highlight=True)["calendar"]["gone"], [])  # a deck holds no deleted cards

    def test_a_deck_screens_calendar_is_that_decks_own(self):
        reset(CARDS)
        cal = payload.payload(20, highlight=True)["calendar"]  # German: card 3, first studied 3 days ago
        self.assertEqual([i for i, n in enumerate(cal["days"]) if n], [0])
        self.assertEqual(cal["start"], addon.study_log.day_date(3, mw.col.sched.day_cutoff).isoformat())
        self.assertEqual(cal["animals"], [])  # the lit-up main forest's animals are not the deck's
        self.assertIsNotNone(payload.payload(10)["calendar"])  # beside a deck's own forest too

    def test_the_calendar_follows_its_settings(self):
        reset(CARDS, {"calendar": "by_year"})
        self.assertEqual(payload.payload()["calendar"]["view"], "by_year")
        reset(CARDS, {"calendar": "nonsense"})
        self.assertEqual(payload.payload()["calendar"]["view"], "timeline")
        reset(CARDS, {"calendar_main": False})
        self.assertIsNone(payload.payload()["calendar"])
        self.assertIsNotNone(payload.payload(20, highlight=True)["calendar"])
        reset(CARDS, {"calendar_decks": False})
        self.assertIsNone(payload.payload(20, highlight=True)["calendar"])
        self.assertIsNotNone(payload.payload()["calendar"])

    def test_a_day_marked_important_is_on_the_calendar_until_unmarked(self):
        reset(CARDS)
        self.assertEqual(payload.payload()["calendar"]["marks"], [])
        addon.marks.set_mark(mw.col, "2026-11-02")
        self.assertEqual(payload.payload()["calendar"]["marks"], [{"day": "2026-11-02", "icon": "pin", "name": ""}])
        addon.marks.set_mark(mw.col, "2026-11-02", "exam", "  Final\nexam  ")  # renamed, one line
        addon.marks.set_mark(mw.col, "2026-10-30", "rocket", "x" * 99)  # an icon it doesn't know: a pin
        self.assertEqual(payload.payload()["calendar"]["marks"], [
            {"day": "2026-10-30", "icon": "pin", "name": "x" * addon.marks.NAME_MAX},
            {"day": "2026-11-02", "icon": "exam", "name": "Final exam"}])
        addon.marks.unmark(mw.col, "2026-11-02")
        addon.marks.unmark(mw.col, "2026-10-30")
        self.assertEqual(payload.payload()["calendar"]["marks"], [])
        with self.assertRaises(ValueError):
            addon.marks.set_mark(mw.col, "not a day")
        # a hand edit, or an older version's bare dates
        mw.col.set_config(addon.marks.KEY, ["2026-11-03", 7, "nonsense", {"day": "2026-11-04", "icon": "trip", "name": "Rome"}])
        self.assertEqual(addon.marks.important_days(mw.col), [{"day": "2026-11-03", "icon": "pin", "name": ""},
                                                              {"day": "2026-11-04", "icon": "trip", "name": "Rome"}])

    def test_the_calendar_s_weeks_start_on_the_chosen_day_or_the_system_s(self):
        reset(CARDS, {"calendar_week_start": "sunday"})
        self.assertEqual(payload.payload()["calendar"]["weekStart"], 0)
        reset(CARDS, {"calendar_week_start": "saturday"})
        self.assertEqual(payload.payload()["calendar"]["weekStart"], 6)
        reset(CARDS, {"calendar_week_start": "nonsense"})  # the system's: here, with no Qt, Monday
        self.assertIn(payload.payload()["calendar"]["weekStart"], range(7))

    def test_the_test_forests_calendar_counts_as_many_days_as_its_streak(self):
        reset(CARDS, {"test_forest": True, "test_trees": 30, "debug": True})
        p = payload.payload()
        days = p["calendar"]["days"]
        streak = 0
        while streak < len(days) and days[-1 - streak]:
            streak += 1
        self.assertEqual(streak, p["stats"]["streak"])
        self.assertFalse(p["calendar"]["browse"])  # a made-up day has no cards to open

    def test_zooming_is_held_back_but_while_debugging(self):
        reset(CARDS, {"debug": False})
        self.assertEqual(payload.payload()["zoom"], payload.ZOOM_RELEASED)
        reset(CARDS, {"debug": True})
        self.assertTrue(payload.payload()["zoom"])
        reset(CARDS, {"debug": True, "debug_edition": "base"})  # the Debug tab pretending to be a release
        self.assertEqual(payload.payload()["zoom"], payload.ZOOM_RELEASED)

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

    def test_the_deep_forest_s_trees_are_kept_for_a_zoom_to_ask_for(self):
        reset(CARDS, {"test_forest": True, "test_trees": 1000, "debug": True})
        p = payload.payload()
        deep = payload.deep_trees("")
        self.assertEqual(len(p["trees"]) + len(deep), 1000)
        self.assertEqual(p["merged"]["count"], len(deep))
        self.assertGreater(deep[0]["ago"], deep[-1]["ago"])  # oldest first
        self.assertGreater(deep[-1]["ago"], p["trees"][0]["ago"])  # all older than the trees drawn
        self.assertFalse(set(payload.PAGE_LEAVES_OUT) & set(deep[0]))
        self.assertEqual(payload.deep_trees("12345"), [])  # a forest never sent: nothing

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

    def test_unticking_a_start_date_announces_no_long_ancient_tree(self):
        reset([(1, 10, 500), (2, 10, 0)], {"ignore_before": "2026-09-01"})
        mw.col.db.con.execute("update cards set ivl = 400 where id = 1")  # ancient for months
        payload.payload()  # the first look, at the forest begun on 1 Sep: the old tree isn't in it
        with mock.patch.object(addon.state, "_settings_open", True):  # unticked in the dialog's preview
            mw.addonManager.config.pop("ignore_before")
            self.assertNotIn("ancient", payload.payload()["journal"])
        p = payload.payload()  # and saved
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

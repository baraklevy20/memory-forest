"""What a panel is drawn from (payload.py) on the days people actually have: an empty
collection, the first day, reviews before the rollover, a sync, an undo, 6 days a week, Pace,
and a state file left by 1.2.0 - in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import json
import types
import unittest
from unittest import mock

from fake_anki import addon, mw, reset
from helpers import TODAY, ms

payload, state, presets = addon.payload, addon.state, addon.presets

QUIET = {"debug": False}  # (as a release: whatever this copy's own debug switch says)


def start(cards=(), **config):
    reset(cards, dict(QUIET, **config))


def add_review(cid: int, days: int, hour: int = 12, ivl: int = 0, took: int = 0) -> int:
    rid = ms(days, hour)
    mw.col.db.con.execute("insert into revlog (id, cid, ease, type, ivl, time) values (?, ?, 3, 1, ?, ?)", (rid, cid, ivl, took))
    return rid


class FirstDaysTests(unittest.TestCase):
    def test_an_empty_collection_draws_an_empty_forest_and_a_one_day_heatmap(self):
        start()
        p = payload.payload()
        self.assertEqual(p["trees"], [])
        self.assertEqual((p["stats"]["trees"], p["stats"]["streak"], p["stats"]["reviews"]), (0, 0, 0))
        self.assertEqual(p["journal"], "Study some new cards and your first tree will take root here.")
        cal = p["calendar"]
        self.assertEqual(cal["days"], [0])
        self.assertEqual(cal["start"], "2026-09-19")
        self.assertEqual((cal["ponds"], cal["gone"], cal["free"], cal["daysOff"], cal["animals"]), ([], [], [], [], []))
        self.assertEqual(cal["answerTime"], [None])
        self.assertIsNone(p["merged"])

    def test_the_first_card_studied_plants_a_seedling_and_says_so(self):
        start([(1, 10, 0)])
        p = payload.payload()
        self.assertEqual([(t["ago"], t["stage"], t["n"]) for t in p["trees"]], [(0, addon.forest_data.SEEDLING, 1)])
        self.assertTrue(p["stats"]["planted_today"])
        self.assertEqual(p["stats"]["streak"], 1)
        self.assertEqual(p["journal"], "Your first tree. It holds 1 card.")
        self.assertEqual(p["calendar"]["days"], [1])

    def test_the_first_look_at_a_deck_with_nothing_studied(self):
        start([(1, 20, 4)])
        p = payload.payload(10)  # French: nothing yet
        self.assertEqual((p["trees"], p["deckName"]), ([], "French"))
        self.assertEqual(p["calendar"]["days"], [0])


class RolloverTests(unittest.TestCase):
    def test_a_review_at_three_in_the_morning_is_the_night_before_s(self):
        start()
        mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (1, 1, 10, 0, 2, 2, 30, '{}', ?)",
                              (TODAY + 30,))
        mw.col.db.con.execute("insert into notes (id, tags) values (1, '')")
        add_review(1, 1, hour=27)  # 03:00 on 19 Sep, before the 04:00 rollover
        p = payload.payload()
        self.assertEqual([t["ago"] for t in p["trees"]], [1])
        self.assertEqual(p["trees"][0]["date"], "2026-09-18")
        self.assertEqual(p["calendar"]["days"], [1, 0])
        self.assertEqual(p["stats"]["streak"], 1)  # (today isn't over yet)
        self.assertEqual(p["stats"]["today_reviews"], 0)


def at(when: dt.datetime):
    """payload.py's clock stopped at `when`."""
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return when
    return mock.patch.object(payload, "_dt", types.SimpleNamespace(datetime=Clock, date=dt.date, timedelta=dt.timedelta))


class AnniversaryTests(unittest.TestCase):
    # trees planted on 19 Sep 2025, 20 Sep 2025 and today, 19 Sep 2026 (Anki's dates)
    CARDS = [(1, 10, 365), (2, 10, 364), (3, 10, 0)]

    def test_a_tree_s_planting_day_coming_round_glows_it(self):
        start(self.CARDS)
        with at(dt.datetime(2026, 9, 19, 15, 0)):
            p = payload.payload()
        self.assertEqual(p["anniversaries"], [0])
        self.assertEqual(p["journal"], "The tree you planted on 19 Sep 2025 turned a year old today.")

    def test_after_midnight_and_before_the_rollover_it_is_still_the_day_before(self):
        start(self.CARDS)
        with at(dt.datetime(2026, 9, 20, 0, 30)):  # Anki's day still 19 Sep until 04:00
            self.assertEqual(payload.payload()["anniversaries"], [0])


class SyncAndUndoTests(unittest.TestCase):
    def test_an_old_review_a_sync_brings_in_counts_once_it_finishes(self):
        start([(1, 10, 3), (2, 10, 1)])
        payload.payload()
        add_review(1, 10)  # studied on the phone ten days ago, synced in: older than any review read
        payload.after_sync()
        p = payload.payload()
        self.assertEqual(len(p["calendar"]["days"]), 11)
        self.assertEqual(p["calendar"]["days"][0], 1)
        self.assertEqual([t["ago"] for t in p["trees"]], [10, 1])  # (card 1 first studied then, after all)

    def test_an_undone_answer_is_taken_off_today(self):
        start([(1, 10, 3)])
        rid = add_review(1, 0, hour=15, took=5000)
        p = payload.payload()
        self.assertEqual((p["stats"]["today_reviews"], p["calendar"]["days"][-1], p["calendar"]["time"][-1]), (1, 1, 5))
        mw.col.db.con.execute("delete from revlog where id = ?", (rid,))
        p = payload.payload()
        self.assertEqual((p["stats"]["today_reviews"], p["calendar"]["days"][-1], p["calendar"]["time"][-1]), (0, 0, 0))
        self.assertEqual(p["calendar"]["answerTime"][-1], None)

    def test_a_card_deleted_since_keeps_its_day_but_takes_its_tree(self):
        start([(1, 10, 5), (2, 10, 3)])
        mw.col.db.con.execute("delete from cards where id = 1")
        payload.after_sync()  # (a deletion on another device)
        p = payload.payload()
        self.assertEqual([t["ago"] for t in p["trees"]], [3])
        self.assertEqual(p["calendar"]["days"][0], 1)  # 5 days ago: still a day studied
        self.assertEqual(p["calendar"]["gone"], [[5, 1, 1]])


class DaysAWeekTests(unittest.TestCase):
    """A streak of 6 days a week on a real collection: a missed day with cards due is passed over
    from the day it was chosen, never back in time."""

    def studied_every_day_but_three_days_ago(self, **config):
        start([(1, 10, 20)], **config)
        mw.col.db.con.execute("update revlog set ivl = 1")  # due again the next day, every day
        for d in range(20):
            if d != 3:
                add_review(1, d, ivl=1)

    def test_every_day_counted_a_missed_day_ends_the_streak(self):
        self.studied_every_day_but_three_days_ago()
        p = payload.payload()
        self.assertEqual(p["stats"]["streak"], 3)
        self.assertEqual(p["calendar"]["free"], [])  # (the card was due that day: missed, not free)
        self.assertEqual(p["calendar"]["daysOff"], [])

    def test_six_days_a_week_passes_over_it(self):
        self.studied_every_day_but_three_days_ago(streak_week=6, streak_week_since="2026-08-20")
        p = payload.payload()
        self.assertEqual(p["calendar"]["daysOff"], [3])
        self.assertEqual((p["stats"]["streak"], p["stats"]["streak_week"]), (20, 6))
        self.assertEqual(p["stats"]["longest_streak"], 20)

    def test_chosen_after_the_missed_day_it_changes_nothing_back_in_time(self):
        self.studied_every_day_but_three_days_ago(streak_week=6, streak_week_since="2026-09-18")
        p = payload.payload()
        self.assertEqual((p["calendar"]["daysOff"], p["stats"]["streak"]), ([], 3))

    def test_chosen_for_a_day_still_to_come_it_changes_nothing_yet(self):
        self.studied_every_day_but_three_days_ago(streak_week=5, streak_week_since="2026-12-01")
        self.assertEqual(payload.payload()["stats"]["streak"], 3)

    def test_with_no_day_chosen_it_changes_nothing(self):
        # (a hand edit: fewer days a week, but no day it began)
        self.studied_every_day_but_three_days_ago(streak_week=6, streak_week_since="")
        self.assertEqual(payload.payload()["stats"]["streak"], 3)


class PaceTests(unittest.TestCase):
    def test_each_day_s_median_answer_to_a_tenth_and_none_on_a_day_off(self):
        start()
        mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (1, 1, 10, 0, 2, 2, 30, '{}', ?)",
                              (TODAY + 30,))
        mw.col.db.con.execute("insert into notes (id, tags) values (1, '')")
        for hour, took in ((9, 1234), (10, 2000), (11, 9000)):
            add_review(1, 2, hour=hour, took=took)
        add_review(1, 0, took=4567)
        cal = payload.payload()["calendar"]
        self.assertEqual(cal["answerTime"], [2.0, None, 4.6])
        self.assertEqual(cal["time"], [12, 0, 4])  # (seconds, whole)
        self.assertEqual(len(cal["answerTime"]), len(cal["days"]))

    def test_a_new_answer_today_moves_only_today_s_pace(self):
        start([(1, 10, 2)])
        add_review(1, 0, hour=9, took=3000)
        self.assertEqual(payload.payload()["calendar"]["answerTime"][-1], 3.0)
        add_review(1, 0, hour=10, took=5000)
        cal = payload.payload()["calendar"]
        self.assertEqual(cal["answerTime"][-1], 4.0)
        self.assertEqual(cal["answerTime"][0], 0.0)  # (2 days ago: its one answer, logged with no time)


class OlderStateTests(unittest.TestCase):
    """The ancient trees as 1.2.0 remembered them (ancient_days) are still known after the update."""

    def ancient_forest(self, known):
        start([(1, 10, 500), (2, 10, 0)])
        mw.col.db.con.execute("update cards set ivl = 400 where id = 1")
        with open(state.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"Test profile": {"ancient_days": known}}, f)
        return TODAY - 500  # the old tree's day

    def test_a_tree_1_2_0_knew_was_ancient_is_no_news(self):
        day = self.ancient_forest([TODAY - 500])
        self.assertNotIn("new_ancient", payload.payload()["events"])
        self.assertNotIn("new_ancient", payload.payload()["events"])
        # once another tree turns, the old record moves to where 1.3 keeps them, the old tree still known
        mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (3, 3, 10, 0, 2, 2, 400, '{}', 0)")
        mw.col.db.con.execute("insert into notes (id, tags) values (3, '')")
        add_review(3, 450)
        payload.after_sync()  # (an older review, as a sync brings)
        self.assertIn("new_ancient", payload.payload()["events"])
        kept = state.load_state()
        self.assertEqual(kept["ancient"], {"all": [day, TODAY - 450]})
        self.assertNotIn("ancient_days", kept)
        self.assertEqual(kept["ancient_event_days"], [TODAY - 450])  # (the old one is no news)

    def test_a_tree_turned_ancient_since_1_2_0_is_news(self):
        self.ancient_forest([])
        p = payload.payload()
        self.assertIn("new_ancient", p["events"])
        self.assertEqual(p["journal"][:len("One of your trees became ancient today.")], "One of your trees became ancient today.")
        self.assertIn("new_ancient", payload.payload()["events"])  # (all that day)

    def test_with_a_start_date_the_first_look_is_quiet(self):
        self.ancient_forest([])
        mw.addonManager.config["ignore_before"] = "2024-01-01"  # (a forest 1.2.0 never saw the ancient trees of)
        self.assertNotIn("new_ancient", payload.payload()["events"])


class SceneNameTests(unittest.TestCase):
    DAY = dt.date(2026, 9, 19)

    def setUp(self):
        start()

    def test_the_default_scenery_goes_unnamed(self):
        self.assertEqual(payload._scene_name(dict(state.config()), self.DAY), {})
        self.assertNotIn("sceneName", payload.payload())

    def test_a_preset_is_named_by_its_label(self):
        p = next(p for p in presets.FOREST_PRESETS[1:] if not p.season and p.key != presets.DAILY)
        self.assertEqual(payload._scene_name(presets.apply(p.key, {}), self.DAY), {"sceneName": p.label})

    def test_surprise_me_daily_names_today_s_pick(self):
        got = payload._scene_name(presets.apply(presets.DAILY, {}), self.DAY)
        self.assertEqual(got["sceneName"], presets.of_the_day(self.DAY).label)
        self.assertIn("Tomorrow", got["sceneTip"])

    def test_a_mix_is_named_after_its_environment(self):
        cfg = dict(presets.apply(presets.FOREST_PRESETS[0].key, {}), weather="storm", time_of_day="night")
        self.assertEqual(presets.match(cfg), presets.CUSTOM)
        got = payload._scene_name(cfg, self.DAY)
        self.assertEqual(got["sceneName"], addon.scene.ENVIRONMENTS[cfg["environment"]])
        self.assertEqual(payload._scene_name(dict(cfg, environment="gone_since"), self.DAY), {})  # (one it doesn't know)

    def test_a_seasonal_scenery_picked_by_hand_says_when_it_goes(self):
        seasonal = [p for p in presets.FOREST_PRESETS if p.season]
        if not seasonal:
            self.skipTest("no seasonal scenery in this copy")
        p = seasonal[0]
        day = dt.date(max(p.season[0].year, 2026), *p.season[1])
        last = presets.season_ends(p, day) - dt.timedelta(days=1)
        got = payload._scene_name(presets.apply(p.key, {}), day)
        self.assertEqual(got, {"sceneName": p.label, "sceneTip": f"Seasonal scenery, here until {last.day} {last.strftime('%B')}."})


if __name__ == "__main__":
    unittest.main()

"""Small edges of the phone's data, the preset catalogue and what the forest counts (phone_data.py,
presets.py, scope.py)."""

from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

from fake_anki import addon, mw, reset

import phone_data
import presets

scope = addon.scope
NOW = dt.datetime(2026, 12, 25, 15, 0)
PAGE = {"trees": [], "stats": {"trees": 0}, "mood": {"time": "day"}, "journal": "",
        "calendar": {"days": [3, 0, 2], "browse": True}}


class PhoneDataEdgeTests(unittest.TestCase):
    def test_a_sunrise_that_is_not_a_time_is_the_default_one(self):
        data = phone_data.phone_payload(PAGE, {}, NOW, "s.js", real={"sunrise": "dawn", "sunset": None})
        self.assertEqual((data["sun"]["rise"], data["sun"]["set"]), ("06:30", "19:00"))

    def test_the_phone_s_heatmap_opens_nothing_and_the_desktop_s_is_left_as_it_was(self):
        data = phone_data.phone_payload(PAGE, {}, NOW, "s.js")
        self.assertFalse(data["calendar"]["browse"])
        self.assertTrue(PAGE["calendar"]["browse"])
        self.assertIsNone(phone_data.phone_payload(dict(PAGE, calendar=None), {}, NOW, "s.js")["calendar"])

    def test_two_weeks_of_scenes_run_on_over_the_new_year(self):
        days = phone_data.schedule({}, NOW)
        self.assertEqual(len(days), phone_data.SCHEDULE_DAYS)
        self.assertEqual([d["date"] for d in days[6:8]], ["2026-12-31", "2027-01-01"])
        self.assertEqual([d["dayNumber"] for d in days], list(range(NOW.date().toordinal(), NOW.date().toordinal() + 14)))
        self.assertTrue(all("liveUntil" not in d for d in days))  # (no live weather asked for)

    def test_a_leap_day_is_one_of_the_phone_s_days(self):
        days = phone_data.schedule({}, dt.datetime(2028, 2, 27, 9, 0), days=4)
        self.assertEqual([d["date"] for d in days], ["2028-02-27", "2028-02-28", "2028-02-29", "2028-03-01"])


class PresetEdgeTests(unittest.TestCase):
    def test_picking_a_preset_no_longer_there_changes_nothing(self):
        current = {"environment": "natural", "landscape": "lake"}
        out = presets.apply("gone_since", current)
        self.assertEqual(out, current)
        self.assertIsNot(out, current)  # (a copy: the dialog's own is left alone)

    def test_the_dropdown_ends_with_custom(self):
        options = presets.options()
        self.assertEqual(options[-1], (presets.CUSTOM, "Custom"))
        self.assertEqual(options[0][0], presets.FOREST_PRESETS[0].key)
        self.assertEqual(len(options), len(presets.FOREST_PRESETS) + 1)

    def test_a_scenery_whose_environment_no_preset_has_starts_from_the_closest(self):
        first = presets.FOREST_PRESETS[0]
        cfg = dict(first.values(), environment="gone_since")
        best, differ = presets.nearest(cfg)
        self.assertEqual((best.key, differ), (first.key, ["environment"]))

    def test_surprise_me_daily_comes_round_again_after_as_many_days_as_there_are(self):
        day = dt.date(2026, 3, 1)
        turn = len([p for p in presets.available(day) if p.environment != presets.DAILY and not p.season])
        picks = [presets.of_the_day(day + dt.timedelta(days=i)).key for i in range(turn)]
        self.assertEqual(len(set(picks)), turn)  # a new one each day
        self.assertEqual(presets.of_the_day(day + dt.timedelta(days=turn)).key, picks[0])

    def test_surprise_me_daily_takes_a_leap_day_in_its_turn(self):
        days = [dt.date(2028, 2, 28) + dt.timedelta(days=i) for i in range(3)]  # 28 Feb, 29 Feb, 1 Mar
        picks = [presets.of_the_day(d).key for d in days]
        self.assertEqual(len(set(picks)), 3)

    def test_the_real_sky_on_a_preset_is_still_that_preset(self):
        p = presets.FOREST_PRESETS[1]
        self.assertEqual(presets.match(dict(p.values(), weather="auto", time_of_day="auto")), p.key)
        self.assertEqual(presets.match(dict(p.values(), weather="auto")), presets.CUSTOM)  # (only half of it)


class ChangesTests(unittest.TestCase):
    """scope.changes: the cheap look at whether anything the forest grows from changed."""

    def setUp(self):
        reset([(1, 10, 3)])

    def test_with_no_collection_it_can_t_say(self):
        with mock.patch.object(mw, "col", None):
            self.assertIsNone(scope.changes())

    def test_a_collection_it_can_t_read_says_nothing_rather_than_failing(self):
        with mock.patch.object(mw.col.db, "scalar", side_effect=RuntimeError("locked")):
            self.assertIsNone(scope.changes())

    def test_a_review_a_card_or_a_note_changes_it_and_picking_a_deck_does_not(self):
        before = scope.changes()
        mw.col.mod += 1  # (a deck picked)
        self.assertEqual(scope.changes(), before)
        for sql in ("insert into revlog (id, cid, ease, type) values (99999999999999, 1, 3, 1)",
                    "update cards set mod = 7", "update notes set mod = 9",
                    "insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (5, 5, 10, 0, 0, 0, 0, '{}', 0)"):
            mw.col.db.con.execute(sql)
            now = scope.changes()
            self.assertNotEqual(now, before, sql)
            before = now

    def test_an_older_anki_s_scheduler_names_its_day_cutoff_the_old_way(self):
        import types
        col = types.SimpleNamespace(sched=types.SimpleNamespace(dayCutoff=1234))
        self.assertEqual(scope.day_cutoff(col), 1234)


class HeatmapLookEdgeTests(unittest.TestCase):
    HL = addon.heatmap_look

    def test_which_way_busier_days_run_is_lighter_unless_darker_is_chosen(self):
        self.assertEqual(self.HL.busier({}), "lighter")
        self.assertEqual(self.HL.busier({"calendar_busier": "darker"}), "darker")
        for bad in ("Darker", "dark", None, 1):
            self.assertEqual(self.HL.busier({"calendar_busier": bad}), "lighter")
        self.assertTrue(self.HL.page_look({"calendar_busier": "darker"}, {"special": "natural"})["darker"])

    def test_your_second_colour_is_used_only_when_switched_on(self):
        self.assertFalse(self.HL.mine_two({}))
        for off in (False, None, "false", "False", 0, "0"):
            self.assertFalse(self.HL.mine_two({"calendar_mine_two": off}))
        self.assertTrue(self.HL.mine_two({"calendar_mine_two": True}))

    def test_one_colour_kept_is_completed_with_the_default_second(self):
        self.assertEqual(self.HL.mine({"calendar_mine": ["#000000"]}), ["#000000", self.HL.MINE_DEFAULT[1]])
        self.assertEqual(self.HL.mine({"calendar_mine": ["#1", "#zzzzzz", "#abcdef"]}), self.HL.MINE_DEFAULT)
        self.assertEqual(self.HL.mine({}), self.HL.MINE_DEFAULT)

    def test_the_settings_pictures_always_have_colours_to_draw(self):
        look = self.HL.preview_look({}, "natural")
        self.assertEqual(look["colours"], self.HL.scenery_own("natural"))
        self.assertEqual(self.HL.scenery_own("gone_since"), self.HL.own_keys().get("natural") or "#8fb35e")
        mine = {"calendar_colours": "mine", "calendar_mine": ["#112233", "#445566"]}
        self.assertEqual(self.HL.preview_look(mine, "natural")["colours"], "#112233")

    def test_with_nothing_out_of_season_the_config_is_left_alone_and_unsaved(self):
        reset()
        cfg = {"calendar_colours": "ready:flame", "calendar_tiles": "round"}
        self.assertIs(self.HL.follow_season(cfg), cfg)
        self.assertEqual(mw.addonManager.config, {})


if __name__ == "__main__":
    unittest.main()

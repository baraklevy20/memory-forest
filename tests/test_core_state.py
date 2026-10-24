"""The config's switches as the add-on reads them (state.py), however they were hand-edited or
left behind by an older version, and what is remembered between redraws - in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import json
import os
import unittest
from unittest import mock

from fake_anki import addon, mw, reset
from helpers import out_of_season

state = addon.state
payload = addon.payload

# what Memory Forest 1.2.0 shipped as its config.json: no heatmap, no week start, no streak rules
CONFIG_1_2_0 = {
    "environment": "natural", "weather": "clear", "time_of_day": "golden_hour", "landscape": "lake", "landmark": "none",
    "city": "", "animations": True, "planting_tooltip": True, "main_forest": True, "deck_forest_mode": "highlight",
    "nature": "peaceful", "excluded_decks": [], "ignore_before": "", "keep_suspended": True, "max_width": 800,
    "debug": False, "test_forest": False, "test_trees": 150, "debug_timeline": [], "debug_backlog": 0,
    "debug_backlog_cleared": 0, "debug_backlog_was": 0, "debug_big_days": False, "debug_date": "", "debug_edition": "",
}
OFF = (False, "false", "False", 0, "0")


class SwitchTests(unittest.TestCase):
    """Each switch is on unless switched off, and a hand-edited "false" or 0 switches it off too."""

    SWITCHES = (state.shows_on_finished, state.shows_record, state.shows_on_deck_list)
    KEYS = ("finished_decks", "calendar_record", "main_forest")

    def setUp(self):
        reset()

    def test_on_unless_switched_off(self):
        for read, key in zip(self.SWITCHES, self.KEYS):
            self.assertTrue(read({}), key)
            self.assertTrue(read({key: True}), key)
            self.assertTrue(read({key: "yes"}), key)  # (anything else a hand edit leaves: still on)
            for off in OFF:
                self.assertFalse(read({key: off}), (key, off))

    def test_the_layout_is_under_the_list_unless_chosen(self):
        state = addon.state
        self.assertEqual(state.layout({}), {"forest": "below", "heatmap": "below", "first": "forest"})
        for side in state.LAYOUT_SIDES:
            for first in state.LAYOUT_FIRST:
                cfg = {"layout_side": side, "layout_first": first}
                got = {key: state.layout(dict(cfg, layout=key)) for key in state.LAYOUTS}
                self.assertEqual(got["under"], {"forest": "below", "heatmap": "below", "first": first})
                self.assertEqual(got["beside"], {"forest": side, "heatmap": side, "first": first})
                other = "heatmap" if first == "forest" else "forest"
                self.assertEqual(got["one_beside"], {first: side, other: "below", "first": first})

    def test_above_the_list_puts_the_first_over_it_and_the_other_under_it(self):
        state = addon.state
        self.assertEqual(state.layout({"layout": "above", "layout_side": "left"}), {"forest": "above", "heatmap": "below", "first": "forest"})
        self.assertEqual(state.layout({"layout": "above", "layout_first": "heatmap"}), {"forest": "below", "heatmap": "above", "first": "heatmap"})

    def test_a_deck_screen_keeps_them_stacked_in_the_first_order(self):
        state = addon.state
        for key in state.LAYOUTS:
            for first in state.LAYOUT_FIRST:
                got = state.layout({"layout": key, "layout_side": "left", "layout_first": first}, deck_screen=True)
                self.assertEqual(got, {"forest": "below", "heatmap": "below", "first": first}, key)

    def test_a_hand_edited_layout_falls_back_to_the_defaults(self):
        state = addon.state
        for bad in ("nonsense", None, 3, ["under"], "both_side"):
            self.assertEqual(state.layout_key({"layout": bad}), "under", bad)
        self.assertEqual(state.layout_side({"layout_side": "top"}), "right")
        self.assertEqual(state.layout_first({"layout_first": "middle"}), "forest")

    def test_the_heatmap_is_the_forests_width_with_more_days_unless_chosen(self):
        state = addon.state
        self.assertEqual((state.calendar_width({}), state.calendar_fill({})), ("forest", "more"))
        for value in state.CALENDAR_WIDTHS:
            self.assertEqual(state.calendar_width({"calendar_width": value}), value)
        for bad in ("wide", 900, -1, None, True):
            self.assertEqual(state.calendar_width({"calendar_width": bad}), "forest", bad)
        self.assertEqual(state.calendar_fill({"calendar_fill": "bigger"}), "bigger")
        self.assertEqual(state.calendar_fill({"calendar_fill": "huge"}), "more")

    def test_the_shipped_config_holds_the_layouts_defaults(self):
        with open(os.path.join(os.path.dirname(addon.__file__), "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual((cfg["layout"], cfg["layout_side"], cfg["layout_first"], cfg["calendar_width"], cfg["calendar_fill"]),
                         (addon.state.LAYOUT_DEFAULT, "right", "forest", "forest", "more"))

    def test_the_heatmap_shows_on_each_screen_unless_switched_off_there(self):
        self.assertTrue(state.calendar_on("main", {}) and state.calendar_on("decks", {}))
        self.assertFalse(state.calendar_on("main", {"calendar_main": "0"}))
        self.assertTrue(state.calendar_on("decks", {"calendar_main": False}))
        self.assertFalse(state.calendar_on("decks", {"calendar_decks": 0}))

    def test_the_streak_counts_from_the_start_date_only_when_switched_on(self):
        self.assertFalse(state.streak_from_start({}))
        self.assertTrue(state.streak_from_start({"streak_from_start": True}))
        for off in (*OFF, None, ""):
            self.assertFalse(state.streak_from_start({"streak_from_start": off}), off)

    def test_the_switches_read_the_saved_config_when_given_none(self):
        mw.addonManager.config = {"finished_decks": False, "calendar_record": False, "main_forest": False}
        self.assertEqual([read() for read in self.SWITCHES], [False, False, False])


class ChoiceTests(unittest.TestCase):
    """A choice it doesn't offer (a hand edit, a later version's) is the default."""

    def test_the_heatmap_s_view_and_shade(self):
        self.assertEqual(state.calendar_view({}), "timeline")
        self.assertEqual(state.calendar_view({"calendar": "by_year"}), "by_year")
        self.assertEqual(state.calendar_view({"calendar": "BY_YEAR"}), "timeline")
        self.assertEqual(state.calendar_shade({}), "reviews")
        for shade in state.CALENDAR_SHADES:
            self.assertEqual(state.calendar_shade({"calendar_shade": shade}), shade)
        for bad in ("pace", None, 3, ["time"]):
            self.assertEqual(state.calendar_shade({"calendar_shade": bad}), "reviews")

    def test_the_days_a_week_the_streak_counts(self):
        self.assertEqual(state.streak_week({}), 7)
        for n in (7, 6, 5):
            self.assertEqual(state.streak_week({"streak_week": n}), n)
        for bad in (4, 0, "6", None, 6.5, True):
            self.assertEqual(state.streak_week({"streak_week": bad}), 7, bad)

    def test_the_day_fewer_days_a_week_were_chosen(self):
        self.assertEqual(state.streak_week_since({"streak_week_since": "2026-10-01"}), dt.date(2026, 10, 1))
        for bad in ("", None, "yesterday", "2026-02-30", 7):
            self.assertIsNone(state.streak_week_since({"streak_week_since": bad}), bad)

    def test_the_week_start(self):
        self.assertEqual(state.week_start({}), "system")
        for day in ("monday", "sunday", "saturday"):
            self.assertEqual(state.week_start({"calendar_week_start": day}), day)
        for bad in ("friday", "Monday", 1, None):
            self.assertEqual(state.week_start({"calendar_week_start": bad}), "system")

    def test_a_chosen_week_start_is_the_page_s_day_number(self):
        self.assertEqual([payload.week_start_day({"calendar_week_start": d}) for d in ("sunday", "monday", "saturday")], [0, 1, 6])
        self.assertIn(payload.week_start_day({}), range(7))  # (the system's; Monday where it can't say)

    def test_a_hand_edited_number_that_is_a_float_or_a_bool(self):
        self.assertEqual(state.clamp_int(450.9, 800, 400, 2000), 450)
        self.assertEqual(state.clamp_int(None, 800, 400, 2000), 800)
        self.assertEqual(state.clamp_int(-5, 150, 0, 5000), 0)


class SettingsOpenTests(unittest.TestCase):
    def test_the_dialog_says_when_it_is_up(self):
        self.addCleanup(state.set_settings_open, False)
        self.assertFalse(state.settings_open())
        state.set_settings_open(True)
        self.assertTrue(state.settings_open())
        state.set_settings_open(False)
        self.assertFalse(state.settings_open())


class RememberedTests(unittest.TestCase):
    def setUp(self):
        state.forget_remembered()
        self.addCleanup(state.forget_remembered)
        self.calls = 0

    def work(self):
        self.calls += 1
        return self.calls

    def test_the_same_key_gives_the_same_answer_without_working_it_out(self):
        self.assertEqual(state.remembered("x", ("a", 1), self.work), 1)
        self.assertEqual(state.remembered("x", ("a", 1), self.work), 1)
        self.assertEqual(self.calls, 1)

    def test_a_new_key_works_it_out_afresh_and_only_the_latest_is_kept(self):
        state.remembered("x", 1, self.work)
        self.assertEqual(state.remembered("x", 2, self.work), 2)
        self.assertEqual(state.remembered("x", 1, self.work), 3)  # (one answer per name)

    def test_no_key_is_never_remembered(self):
        # (scope.changes is None when the collection can't say: then everything is read afresh)
        state.remembered("x", None, self.work)
        state.remembered("x", None, self.work)
        self.assertEqual(self.calls, 2)

    def test_each_name_keeps_its_own(self):
        state.remembered("x", 1, self.work)
        state.remembered("y", 1, self.work)
        self.assertEqual((state.remembered("x", 1, self.work), state.remembered("y", 1, self.work)), (1, 2))

    def test_forgetting_works_everything_out_again(self):
        state.remembered("x", 1, self.work)
        state.forget_remembered()
        self.assertEqual(state.remembered("x", 1, self.work), 2)

    def test_a_sync_forgets_them_all(self):
        state.remembered("x", 1, self.work)
        payload.after_sync()
        self.assertEqual(state.remembered("x", 1, self.work), 2)


class StateFileTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_profile_s_section_that_is_not_an_object_reads_as_empty(self):
        with open(state.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"Test profile": ["junk"], "Other": {"kept": 1}}, f)
        self.assertEqual(state.load_state(), {})
        state.save_state({"a": 1})
        with open(state.STATE_PATH, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"Test profile": {"a": 1}, "Other": {"kept": 1}})  # (the other profile's kept)

    def test_a_disk_that_can_t_be_written_loses_only_the_save(self):
        with mock.patch.object(state, "save_json", side_effect=OSError("read-only")):
            state.save_state({"a": 1})  # (no error: the forest still draws)
        self.assertEqual(state.load_state(), {})

    def test_with_no_profile_name_it_is_the_first_profile_s(self):
        with mock.patch.object(mw.pm, "name", None):
            state.save_state({"a": 1})
        with open(state.STATE_PATH, encoding="utf-8") as f:
            self.assertIn("User 1", json.load(f))


class OlderConfigTests(unittest.TestCase):
    """A config saved by 1.2.0: every key it knew, at its values, and none of the heatmap's."""

    def test_a_1_2_0_config_draws_the_heatmap_with_its_defaults(self):
        reset([(1, 10, 3), (2, 10, 1)], CONFIG_1_2_0)
        with out_of_season():  # (in Halloween's week the heatmap wears pumpkins)
            p = payload.payload()
        cal = p["calendar"]
        self.assertIsNotNone(cal)  # (on for everyone, on both screens)
        self.assertEqual((cal["view"], cal["shadeBy"], cal["streakFromStart"]), ("timeline", "reviews", False))
        self.assertEqual(cal["daysOff"], [])  # every day counts
        self.assertEqual(p["stats"]["streak_week"], 7)
        self.assertEqual(cal["look"]["colours"], None)  # the scenery's own colours
        self.assertEqual(cal["look"]["tile"], "flat")
        self.assertIsNotNone(payload.payload(10, highlight=True)["calendar"])

    def test_saving_a_1_2_0_config_keeps_only_what_was_changed(self):
        reset(config=CONFIG_1_2_0)
        state.save_config(dict(state.config(), nature="wild", max_width=1000, debug=mw.addonManager.defaults["debug"]))  # (debug as this copy ships it)
        self.assertEqual(mw.addonManager.config, {"nature": "wild", "max_width": 1000})

    def test_a_key_no_version_knows_is_dropped_on_saving(self):
        reset(config={"calendar_colour": "#ff0000", "stakes": "high"})  # (typos, or a key since renamed)
        state.save_config(state.config())
        self.assertEqual(mw.addonManager.config, {})

    def test_every_key_1_2_0_knew_is_still_known(self):
        with open(os.path.join(addon.state.ADDON_DIR, "config.json"), encoding="utf-8") as f:
            now = json.load(f)
        self.assertEqual(set(CONFIG_1_2_0) - set(now), set())


if __name__ == "__main__":
    unittest.main()

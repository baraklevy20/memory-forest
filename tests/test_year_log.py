"""What next year's recap keeps of each day (year_log.py): the scenery and the real sky's weather,
one synced config key a month, written by the deck list's forest on a day you studied."""

from __future__ import annotations

import datetime as dt
import importlib
import unittest
from unittest import mock

from fake_anki import addon, mw, reset

year_log = importlib.import_module(addon.__name__ + ".year_log")
payload = addon.payload
D = dt.date


def cherry() -> dict:
    return addon.presets.apply("cherry_blossom", {})


class RecordTests(unittest.TestCase):
    def setUp(self):
        reset()
        self.col = mw.col

    def test_a_day_keeps_its_scenery_under_its_month(self):
        self.assertTrue(year_log.record(self.col, cherry(), D(2027, 3, 5), {"source": "preset", "weather": "clear"}))
        self.assertEqual(self.col.conf["memoryForestDays.2027-03"], {"5": {"s": "cherry_blossom"}})
        self.assertEqual(year_log.days(self.col, 2027), {D(2027, 3, 5): {"scenery": "cherry_blossom", "weather": []}})

    def test_the_real_sky_keeps_each_weather_once_in_the_order_seen(self):
        for w in ("rain", "clear", "rain"):
            year_log.record(self.col, cherry(), D(2027, 3, 5), {"source": "real", "weather": w})
        self.assertEqual(self.col.conf["memoryForestDays.2027-03"]["5"]["w"], ["rain", "clear"])
        # (the place it was for is never kept)
        self.assertEqual(set(self.col.conf["memoryForestDays.2027-03"]["5"]), {"s", "w"})

    def test_a_chosen_or_scenery_weather_is_not_kept(self):
        year_log.record(self.col, cherry(), D(2027, 3, 5), {"source": "manual", "weather": "snow"})
        self.assertNotIn("w", self.col.conf["memoryForestDays.2027-03"]["5"])

    def test_a_redraw_that_changes_nothing_writes_nothing(self):
        year_log.record(self.col, cherry(), D(2027, 3, 5), {"source": "real", "weather": "rain"})
        with mock.patch.object(self.col, "set_config") as write:
            self.assertFalse(year_log.record(self.col, cherry(), D(2027, 3, 5), {"source": "real", "weather": "rain"}))
        write.assert_not_called()

    def test_the_last_scenery_of_the_day_is_its_scenery(self):
        year_log.record(self.col, cherry(), D(2027, 3, 5), {})
        year_log.record(self.col, addon.presets.apply("deep_winter", {}), D(2027, 3, 5), {})
        self.assertEqual(year_log.days(self.col, 2027)[D(2027, 3, 5)]["scenery"], "deep_winter")

    def test_surprise_me_keeps_the_days_pick_and_your_own_mix_is_custom(self):
        daily = addon.presets.apply("daily", {})
        year_log.record(self.col, daily, D(2027, 3, 5), {})
        pick = addon.presets.todays(daily, D(2027, 3, 5)).key
        self.assertEqual(year_log.days(self.col, 2027)[D(2027, 3, 5)]["scenery"], pick)
        year_log.record(self.col, dict(cherry(), environment="bamboo"), D(2027, 3, 6), {})
        self.assertEqual(year_log.days(self.col, 2027)[D(2027, 3, 6)]["scenery"], "custom")

    def test_the_scenery_is_the_one_chosen_for_its_date(self):
        # (after midnight, before Anki's rollover: yesterday's day, the new date's pick)
        daily = addon.presets.apply("daily", {})
        year_log.record(self.col, daily, D(2027, 3, 5), {}, shown=D(2027, 3, 6))
        self.assertEqual(year_log.days(self.col, 2027)[D(2027, 3, 5)]["scenery"], addon.presets.todays(daily, D(2027, 3, 6)).key)

    def test_other_months_and_other_versions_fields_are_left_as_they_were(self):
        self.col.conf["memoryForestDays.2027-03"] = {"5": {"s": "cherry_blossom", "x": 1}, "9": {"s": "golden_lake", "y": [2]}}
        self.col.conf["memoryForestDays.2027-04"] = {"1": {"s": "golden_lake"}}
        year_log.record(self.col, addon.presets.apply("deep_winter", {}), D(2027, 3, 5), {})
        self.assertEqual(self.col.conf["memoryForestDays.2027-03"], {"5": {"s": "deep_winter", "x": 1}, "9": {"s": "golden_lake", "y": [2]}})
        self.assertEqual(self.col.conf["memoryForestDays.2027-04"], {"1": {"s": "golden_lake"}})

    def test_what_it_cant_read_is_left_out(self):
        self.col.conf["memoryForestDays.2027-01"] = {"3": {"s": "golden_lake", "w": ["rain", 4]}, "40": {"s": "x"}, "x": {}, "7": "no",
                                                     "8": {"s": ""}, "31": {"s": "golden_lake"}}
        self.col.conf["memoryForestDays.2027-02"] = {"30": {"s": "golden_lake"}}  # (no such day)
        self.col.conf["memoryForestDays.2027-05"] = ["not", "a", "month"]
        self.assertEqual(year_log.days(self.col, 2027), {D(2027, 1, 3): {"scenery": "golden_lake", "weather": ["rain"]},
                                                         D(2027, 1, 31): {"scenery": "golden_lake", "weather": []}})
        with mock.patch.object(self.col, "get_config", side_effect=RuntimeError):
            self.assertEqual(year_log.days(self.col, 2027), {})


class FromThePanelTests(unittest.TestCase):
    def kept(self) -> dict:
        return {k: v for k, v in mw.col.conf.items() if k.startswith(year_log.PREFIX)}

    def test_a_day_you_studied_is_kept_by_the_deck_lists_forest(self):
        reset([(1, 10, 0)], config=cherry())
        payload.payload()
        today = addon.payload.anki_today()
        self.assertEqual(year_log.days(mw.col, today.year)[today]["scenery"], "cherry_blossom")

    def test_nothing_is_kept_before_you_study_or_on_a_decks_screen(self):
        reset([(1, 10, 2)], config=cherry())
        payload.payload()
        self.assertEqual(self.kept(), {})
        reset([(1, 10, 0)], config=cherry())
        payload.payload(10)
        self.assertEqual(self.kept(), {})

    def test_nothing_is_kept_on_the_test_forest_or_a_debug_date(self):
        reset([(1, 10, 0)], config=dict(cherry(), debug=True, test_forest=True))
        payload.payload()
        self.assertEqual(self.kept(), {})
        reset([(1, 10, 0)], config=dict(cherry(), debug=True, debug_date="2027-04-01"))
        payload.payload()
        self.assertEqual(self.kept(), {})

    def test_a_failed_write_never_stops_the_forest(self):
        reset([(1, 10, 0)], config=cherry())
        with mock.patch.object(mw.col, "set_config", side_effect=RuntimeError("read only")):
            self.assertTrue(payload.payload()["trees"])
        self.assertEqual(self.kept(), {})


if __name__ == "__main__":
    unittest.main()

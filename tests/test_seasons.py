"""The day the forest is drawn for (seasons.py)."""

from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

from fake_anki import addon

edition, seasons = addon.edition, addon.seasons


class TodayTests(unittest.TestCase):
    def test_the_scenery_date_is_today_unless_debug_says_otherwise(self):
        real = dt.date.today()
        self.assertEqual(seasons.today({"debug_date": "2026-10-24"}), real)  # debug off: ignored
        on = {"debug": True, "debug_date": "2026-10-24"}
        self.assertEqual(seasons.today(on), dt.date(2026, 10, 24))
        self.assertEqual(seasons.today(dict(on, debug_date="")), real)
        self.assertEqual(seasons.today(dict(on, debug_date="nonsense")), real)
        # a release ships without the debug tools: debug turned on by hand there changes nothing
        with mock.patch.object(seasons.os.path, "exists", return_value=False):
            self.assertFalse(edition.debug_available(on))
            self.assertEqual(seasons.today(on), real)

    def test_days_passed_on_the_test_forest_move_the_scenery_date_on(self):
        on = {"debug": True, "debug_date": "2026-10-24", "debug_timeline": [["study", 5], ["away", 3]]}
        self.assertEqual(seasons.today(on), dt.date(2026, 10, 24))  # only on the test forest
        self.assertEqual(seasons.today(dict(on, test_forest=True)), dt.date(2026, 11, 1))


class OfferDayTests(unittest.TestCase):
    """While debugging with no date set, the settings offer every seasonal preset; a debug
    date offers only what that day would."""

    def keys(self, day):
        return {p.key for p in addon.presets.available(day)}

    def test_debug_with_no_date_offers_every_season(self):
        self.assertEqual(seasons.offer_day({}), dt.date.today())  # debug off: today, as ever
        self.assertIsNone(seasons.offer_day({"debug": True}))
        self.assertTrue({"pumpkin_patch", "frozen_market"} <= self.keys(None))

    def test_a_debug_date_offers_only_what_that_day_would(self):
        june = {"debug": True, "debug_date": "2026-06-01"}
        self.assertEqual(seasons.offer_day(june), dt.date(2026, 6, 1))
        self.assertFalse({"pumpkin_patch", "frozen_market"} & self.keys(seasons.offer_day(june)))
        halloween = self.keys(seasons.offer_day(dict(june, debug_date="2026-10-25")))
        self.assertIn("pumpkin_patch", halloween)
        self.assertNotIn("frozen_market", halloween)

    def test_a_seasonal_scenery_picked_in_debug_stays_out_of_its_week(self):
        P = addon.presets
        look = P.apply("pumpkin_patch", {})
        june = dt.date(2026, 6, 1)
        self.assertEqual(P.follow_season(look, {}, june)[0]["environment"], P.FOREST_PRESETS[0].environment)
        self.assertEqual(P.follow_season(look, {}, june, every_season=True)[0], {})


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

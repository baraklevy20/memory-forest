"""Telling days apart: Anki's day number in the payload exporter (dev/export_payload.py), and
reviews bucketed into days across a daylight saving change (study_log.days_ago)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import time
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)
from fake_anki import addon

study_log = addon.study_log
HERE = os.path.dirname(os.path.abspath(__file__))


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_payload", os.path.join(HERE, "..", "dev", "export_payload.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def at(y, m, d, h, mi=0) -> int:
    return int(dt.datetime(y, m, d, h, mi).timestamp())


class SchedTodayTests(unittest.TestCase):
    def test_a_collection_made_after_the_rollover_counts_its_first_day_as_day_0(self):
        ex = load_exporter()
        crt = at(2026, 10, 1, 10)  # made at 10:00, the day ending at 4:00
        self.assertEqual(ex.sched_today(crt, at(2026, 10, 2, 4), 4), 0)  # still its first day
        self.assertEqual(ex.sched_today(crt, at(2026, 10, 3, 4), 4), 1)
        self.assertEqual(ex.sched_today(crt, at(2026, 10, 12, 4), 4), 10)

    def test_a_collection_made_before_the_rollover(self):
        ex = load_exporter()
        crt = at(2026, 10, 1, 2)  # made at 2:00: its day ends at 4:00 the same morning
        self.assertEqual(ex.sched_today(crt, at(2026, 10, 1, 4), 4), 0)
        self.assertEqual(ex.sched_today(crt, at(2026, 10, 2, 4), 4), 1)


@unittest.skipUnless(hasattr(time, "tzset"), "needs time.tzset to change the time zone")
class DaylightSavingTests(unittest.TestCase):
    """A review a day at noon, across the night the clocks change, lands on a day of its own each
    time: no day missed (a hole in the calendar) and none counted twice."""

    def in_zone(self, tz: str):
        old = os.environ.get("TZ")
        os.environ["TZ"] = tz
        time.tzset()
        self.addCleanup(lambda: (os.environ.__setitem__("TZ", old) if old else os.environ.pop("TZ", None), time.tzset()))

    def check(self, tz: str, first: dt.date):
        self.in_zone(tz)
        days = [first + dt.timedelta(days=i) for i in range(6)]
        last = days[-1]
        cutoff = at(last.year, last.month, last.day + 1, 4)  # the last day ends at 4:00 the morning after
        agos = [study_log.days_ago(at(d.year, d.month, d.day, 12), cutoff) for d in days]
        self.assertEqual(agos, [5, 4, 3, 2, 1, 0])

    def test_europe_in_october(self):  # the clocks go back an hour on 25 October 2026
        self.check("Europe/Berlin", dt.date(2026, 10, 23))

    def test_australia_in_october(self):  # and forward in Sydney on 4 October 2026
        self.check("Australia/Sydney", dt.date(2026, 10, 2))


if __name__ == "__main__":
    unittest.main()

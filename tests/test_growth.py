"""Growth (growth.py): each card's change in stability over a day it was reviewed, and the day's median."""

from __future__ import annotations

import unittest

from fake_anki import addon

growth = addon.growth
DAY = 86400
CUT = 100 * DAY  # (the next rollover, as epoch seconds: day 0 is the 24 hours before it)


def at(ago: int, hour: int = 10) -> int:
    return CUT - (ago + 1) * DAY + hour * 3600


class CardDayTests(unittest.TestCase):
    def test_a_day_goes_from_the_stability_before_it_to_after_its_last_review(self):
        history = [(at(5), True, 20.0), (at(3), True, 25.0), (at(3, 15), True, 30.0)]
        self.assertEqual(growth.card_days(history, CUT), {3: 50.0})  # (20 going in, 30 after the last: +50%; day 5 had none before it)

    def test_a_lapse_counts_and_lowers_it(self):
        history = [(at(9), True, 3.0), (at(4), True, 40.0), (at(1), True, 10.0)]
        self.assertEqual(growth.card_days(history, CUT), {4: (40 - 3) / 3 * 100, 1: -75.0})

    def test_a_new_card_s_first_day_is_left_out(self):
        self.assertEqual(growth.card_days([(at(2), True, 1.5), (at(2, 11), True, 3.0)], CUT), {})

    def test_a_manual_change_is_no_review_but_is_where_the_next_day_starts(self):
        history = [(at(6), True, 5.0), (at(4), False, 8.0), (at(2), True, 16.0)]
        self.assertEqual(growth.card_days(history, CUT), {2: 100.0})  # (from the 8 the change left)


if __name__ == "__main__":
    unittest.main()

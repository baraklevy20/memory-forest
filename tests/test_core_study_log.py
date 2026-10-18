"""The collection's days and rows (study_log.py), at their edges: the rollover hour, leap days,
the clocks changing, an empty collection, undo, and reviews that are no study."""

from __future__ import annotations

import datetime as dt
import os
import time
import unittest

from fake_anki import DB
from helpers import CUTOFF, DAY, TODAY, ms

import forest_data as fd
import study_log


def a_db() -> DB:
    """An empty collection, with every column the queries read."""
    return DB()


def add_card(db: DB, cid: int, did: int = 10, ctype: int = 2, queue: int = 2, ivl: int = 30, tags: str = "",
             odid: int = 0, due: int = TODAY + 30) -> None:
    db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (?, ?, ?, ?, ?, ?, ?, '{}', ?)",
                   (cid, cid, did, odid, ctype, queue, ivl, due))
    db.con.execute("insert into notes (id, tags) values (?, ?)", (cid, tags))


def review(db: DB, rid: int, cid: int, ease: int = 3, rtype: int = 1, took: int = 0, ivl: int = 30) -> None:
    db.con.execute("insert into revlog (id, cid, ease, type, time, ivl) values (?, ?, ?, ?, ?, ?)", (rid, cid, ease, rtype, took, ivl))


class DayBoundaryTests(unittest.TestCase):
    """Where one Anki day ends and the next begins: at the rollover hour, not midnight."""

    def test_the_last_second_before_the_rollover_is_still_today(self):
        self.assertEqual(study_log.days_ago(CUTOFF - 1, CUTOFF), 0)

    def test_the_rollover_itself_starts_the_day_after(self):
        self.assertEqual(study_log.days_ago(CUTOFF, CUTOFF), -1)  # (not yet: tomorrow's)
        self.assertEqual(study_log.days_ago(CUTOFF - DAY, CUTOFF), 0)  # today began at the rollover
        self.assertEqual(study_log.days_ago(CUTOFF - DAY - 1, CUTOFF), 1)  # a second before it: yesterday

    def test_three_in_the_morning_is_the_night_before(self):
        # 03:00 on 19 Sep, before the 04:00 rollover: still 18 Sep's day
        three_am = int(dt.datetime(2026, 9, 19, 3, 0).timestamp())
        self.assertEqual(study_log.days_ago(three_am, CUTOFF), 1)
        self.assertEqual(study_log.day_date(1, CUTOFF), dt.date(2026, 9, 18))

    def test_each_day_back_is_the_date_before(self):
        for n in range(0, 400, 37):
            self.assertEqual(study_log.day_date(n, CUTOFF), dt.date(2026, 9, 19) - dt.timedelta(days=n), n)

    def test_a_day_s_start_and_its_number_agree(self):
        for n in range(0, 800, 53):
            start = study_log.day_start(study_log.day_date(n, CUTOFF), CUTOFF)
            self.assertEqual(study_log.days_ago(start, CUTOFF), n, n)
            self.assertEqual(study_log.days_ago(start - 1, CUTOFF), n + 1, n)

    def test_a_leap_day_is_a_day_of_its_own(self):
        cutoff = int(dt.datetime(2028, 3, 1, 4, 0).timestamp())  # 29 Feb 2028 is yesterday
        self.assertEqual([study_log.day_date(n, cutoff) for n in range(3)],
                         [dt.date(2028, 2, 29), dt.date(2028, 2, 28), dt.date(2028, 2, 27)])
        self.assertEqual(study_log.day_start(dt.date(2028, 2, 28), cutoff), cutoff - 2 * DAY)
        self.assertEqual(study_log.day_date(366, cutoff), dt.date(2027, 2, 28))  # (a leap year back: 366 days)

    def test_the_year_turns_at_the_rollover_after_new_year_s_eve(self):
        cutoff = int(dt.datetime(2027, 1, 1, 4, 0).timestamp())
        self.assertEqual(study_log.day_date(0, cutoff), dt.date(2026, 12, 31))
        half_past_midnight = int(dt.datetime(2027, 1, 1, 0, 30).timestamp())
        self.assertEqual(study_log.days_ago(half_past_midnight, cutoff), 0)  # a New Year's party's reviews: 31 Dec's


@unittest.skipUnless(hasattr(time, "tzset"), "needs time.tzset to change the time zone")
class ClocksChangeTests(unittest.TestCase):
    """The week the clocks change: every date still has one Anki day, and a start date's day and
    the reviews in it agree."""

    def setUp(self):
        old = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        time.tzset()
        self.addCleanup(lambda: (os.environ.__setitem__("TZ", old) if old else os.environ.pop("TZ", None), time.tzset()))

    def test_every_date_across_the_change_is_one_day(self):
        cutoff = int(dt.datetime(2026, 10, 28, 4, 0).timestamp())  # the clocks went back on 25 Oct
        dates = [study_log.day_date(n, cutoff) for n in range(8)]
        self.assertEqual(dates, [dt.date(2026, 10, 27) - dt.timedelta(days=n) for n in range(8)])

    def test_a_start_date_across_the_change_begins_where_its_day_does(self):
        cutoff = int(dt.datetime(2026, 10, 28, 4, 0).timestamp())
        for date in (dt.date(2026, 10, 24), dt.date(2026, 10, 25), dt.date(2026, 10, 26)):
            start = study_log.day_start(date, cutoff)
            ago = (study_log.day_date(0, cutoff) - date).days
            self.assertEqual((study_log.days_ago(start, cutoff), study_log.days_ago(start - 1, cutoff)), (ago, ago + 1))
            # and a review at noon that day is in it
            noon = int(dt.datetime(date.year, date.month, date.day, 12).timestamp())
            self.assertEqual(study_log.days_ago(noon, cutoff), ago)


class EmptyCollectionTests(unittest.TestCase):
    """A profile with nothing studied yet: no rows, no trees, nothing due, nothing free."""

    def test_nothing_read_is_nothing_drawn(self):
        db = a_db()
        rows = study_log.load_rows(db, CUTOFF)
        self.assertEqual((rows.cards, rows.first_last, rows.review_days, rows.total_reviews, rows.today_reviews),
                         ([], {}, set(), 0, 0))
        forest = fd.build_forest(rows, CUTOFF, TODAY)
        self.assertEqual(forest["trees"], [])
        s = forest["stats"]
        self.assertEqual((s["trees"], s["cards"], s["streak"], s["longest_streak"], s["forest_age"], s["oldest_date"]),
                         (0, 0, 0, 0, 0, None))
        self.assertFalse(s["planted_today"])
        self.assertEqual((forest["visitors"], forest["forest_seed"]), ([], 0))

    def test_every_query_answers_for_an_empty_log(self):
        db = a_db()
        self.assertEqual(study_log.load_free_days(db, CUTOFF, None), [])
        self.assertEqual(study_log.load_review_days(db, CUTOFF), set())
        self.assertEqual(study_log.load_backlog(db, TODAY, CUTOFF, 30), (0, []))
        self.assertEqual(study_log.load_due(db, TODAY, 3), [0, 0, 0])
        self.assertEqual(study_log.load_deleted_cards(db, CUTOFF), {})
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, None), {})
        self.assertEqual(study_log.load_day_time(db, CUTOFF, None), {})
        self.assertEqual(study_log.load_day_answer_time(db, CUTOFF, None), {})
        self.assertEqual(study_log.load_cured(db, CUTOFF, 7), {})
        self.assertEqual(study_log.load_tree_days(db, CUTOFF), {})
        self.assertFalse(study_log.has_new_cards(db))
        self.assertFalse(study_log.undone(db, 0))
        self.assertEqual(study_log.AnswerTimes().read(db, CUTOFF, None), {})

    def test_new_cards_alone_plant_nothing(self):
        db = a_db()
        for cid in (1, 2, 3):
            add_card(db, cid, ctype=0, queue=0, ivl=0)
        self.assertEqual(study_log.load_rows(db, CUTOFF).cards, [])
        self.assertTrue(study_log.has_new_cards(db))


class NotStudyTests(unittest.TestCase):
    """Reviews that are no study - a manual reschedule, a card shown and not answered - never
    plant, date or count."""

    def test_a_reschedule_never_dates_a_card(self):
        db = a_db()
        created = ms(20)
        add_card(db, created)
        review(db, ms(3), created, ease=0, rtype=4)  # set due date, 3 days ago
        rows = study_log.load_rows(db, CUTOFF)
        self.assertEqual(rows.first_last, {})
        self.assertEqual(rows.review_days, set())
        # the card stands on the day it was made, as one never studied would
        self.assertEqual([t["ago"] for t in fd.build_forest(rows, CUTOFF, TODAY)["trees"]], [20])

    def test_no_review_type_beyond_filtered_counts_for_a_day(self):
        db = a_db()
        add_card(db, 1)
        review(db, ms(2), 1, rtype=0)
        review(db, ms(1), 1, ease=3, rtype=5)  # (a later Anki's manual entry)
        review(db, ms(0), 1, ease=0, rtype=1)  # shown, never answered
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, None), {2: 1})
        self.assertEqual(study_log.load_review_days(db, CUTOFF), {2})

    def test_a_review_after_the_rollover_is_not_counted_yet(self):
        # (a clock put forward, or a phone a day ahead: it can't be a day already passed)
        db = a_db()
        add_card(db, 1)
        review(db, ms(0), 1, rtype=0)
        review(db, CUTOFF * 1000 + 60_000, 1)
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, None), {0: 1})
        self.assertEqual(study_log.load_rows(db, CUTOFF).total_reviews, 1)


class UndoTests(unittest.TestCase):
    def test_a_newest_review_still_there_is_not_undone(self):
        db = a_db()
        review(db, ms(0), 1)
        self.assertFalse(study_log.undone(db, ms(0)))
        self.assertFalse(study_log.undone(db, 0))  # (nothing read before)

    def test_a_newest_review_gone_is_an_undo(self):
        db = a_db()
        review(db, ms(1), 1)
        review(db, ms(0), 1)
        db.con.execute("delete from revlog where id = ?", (ms(0),))
        self.assertTrue(study_log.undone(db, ms(0)))

    def test_today_s_count_goes_back_down_after_an_undo(self):
        db = a_db()
        add_card(db, 1)
        review(db, ms(3), 1, rtype=0)
        log = study_log.ReviewLog()
        review(db, ms(0, 9), 1)
        self.assertEqual(study_log.load_rows(db, CUTOFF, log=log).today_reviews, 1)
        db.con.execute("delete from revlog where id = ?", (ms(0, 9),))
        rows = study_log.load_rows(db, CUTOFF, log=log)
        self.assertEqual((rows.today_reviews, rows.total_reviews, rows.review_days), (0, 1, {3}))

    def test_a_new_day_reads_the_log_again_one_day_on(self):
        db = a_db()
        add_card(db, 1)
        review(db, ms(1), 1, rtype=0)
        log = study_log.ReviewLog()
        self.assertEqual(study_log.load_rows(db, CUTOFF, log=log).review_days, {1})
        # the rollover passes: yesterday is two days ago, and nothing is counted twice
        self.assertEqual(study_log.load_rows(db, CUTOFF + DAY, log=log).review_days, {2})
        self.assertEqual(study_log.load_rows(db, CUTOFF + DAY, log=log).total_reviews, 1)


class LeechAndLapseTests(unittest.TestCase):
    def leech_ids(self, db) -> set:
        return study_log.load_rows(db, CUTOFF).leeches

    def test_a_leech_tag_is_read_whatever_its_case(self):
        db = a_db()
        add_card(db, 1, ivl=5, tags=" LEECH ")
        review(db, ms(2), 1, rtype=0)
        self.assertEqual(self.leech_ids(db), {1})

    def test_a_tag_that_only_contains_leech_is_none(self):
        db = a_db()
        add_card(db, 1, ivl=5, tags=" unleeched leeches ")
        review(db, ms(2), 1, rtype=0)
        self.assertEqual(self.leech_ids(db), set())

    def test_a_leech_grown_mature_is_cured(self):
        db = a_db()
        add_card(db, 1, ivl=study_log.CURED_IVL - 1, tags=" leech ")
        add_card(db, 2, ivl=study_log.CURED_IVL, tags=" leech ")
        for cid in (1, 2):
            review(db, ms(2), cid, rtype=0)
        self.assertEqual(self.leech_ids(db), {1})

    def test_a_leech_last_studied_two_months_ago_is_left_alone(self):
        db = a_db()
        for cid, last in ((1, study_log.ACTIVE_DAYS - 1), (2, study_log.ACTIVE_DAYS + 1)):
            add_card(db, cid, ivl=5, tags=" leech ")
            review(db, ms(last, 12), cid, rtype=0)
        self.assertEqual(self.leech_ids(db), {1})

    def test_only_a_week_s_lapses_make_a_tree_struggle(self):
        db = a_db()
        for cid, lapsed in ((1, study_log.LAPSE_WINDOW_DAYS - 1), (2, study_log.LAPSE_WINDOW_DAYS + 1)):
            add_card(db, cid)
            review(db, ms(30), cid, rtype=0)
            review(db, ms(lapsed), cid, ease=1, rtype=1)  # Again on a review card
        review(db, ms(1), 3, ease=1, rtype=0)  # (Again on a card still learning: no lapse)
        self.assertEqual(study_log.load_rows(db, CUTOFF).recent_lapses, {1})


class AnswerTimeTests(unittest.TestCase):
    """Pace: the median seconds an answer took, each day."""

    def test_the_median_of_an_even_day_is_the_mean_of_its_middle_two(self):
        db = a_db()
        for i, took in enumerate((1000, 9000, 3000, 5000)):
            review(db, ms(2) + i, 1, took=took)
        for i, took in enumerate((2000, 60000, 4000)):
            review(db, ms(1) + i, 1, took=took)
        self.assertEqual(study_log.load_day_answer_time(db, CUTOFF, None), {2: 4.0, 1: 4.0})

    def test_a_zero_time_counts_and_a_reschedule_does_not(self):
        db = a_db()
        for i, (took, ease, rtype) in enumerate(((0, 3, 1), (0, 3, 1), (6000, 3, 1), (90000, 0, 4))):
            review(db, ms(0) + i, 1, ease=ease, rtype=rtype, took=took)
        self.assertEqual(study_log.load_day_answer_time(db, CUTOFF, None), {0: 0.0})

    def test_answer_times_kept_follow_an_undo(self):
        db = a_db()
        review(db, ms(1), 1, took=4000)
        times = study_log.AnswerTimes()
        review(db, ms(0, 9), 1, took=8000)
        self.assertEqual(times.read(db, CUTOFF, None), {1: 4.0, 0: 8.0})
        db.con.execute("delete from revlog where id = ?", (ms(0, 9),))
        self.assertEqual(times.read(db, CUTOFF, None), {1: 4.0})


class DeletedCardTests(unittest.TestCase):
    def test_a_day_counts_its_cards_deleted_since_of_those_it_reviewed(self):
        db = a_db()
        for cid in (1, 2, 3):
            add_card(db, cid)
            review(db, ms(4) + cid, cid, rtype=0)
        review(db, ms(4) + 9, 2)  # the same card twice: one card
        review(db, ms(1), 1)
        db.con.execute("delete from cards where id in (2, 3)")
        self.assertEqual(study_log.load_deleted_cards(db, CUTOFF), {4: (2, 3)})  # day 1 lost none: not listed

    def test_reviews_of_a_deleted_card_still_count_for_their_days(self):
        db = a_db()
        review(db, ms(4), 77, rtype=0)  # its card long gone
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, None), {4: 1})
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, None, excluded=[10]), {4: 1})  # (no deck to leave out)
        self.assertEqual(study_log.load_day_reviews(db, CUTOFF, [10]), {})  # but no deck holds it


class TreeDayFilterTests(unittest.TestCase):
    def test_trees_older_than_the_start_and_only_suspended_ones_drop_out(self):
        days = {10: {9: True, 5: False, 2: True}, 20: {5: True}}
        self.assertEqual(study_log.tree_days(days, [10]), {9, 5, 2})
        self.assertEqual(study_log.tree_days(days, [10], since_ago=5), {5, 2})
        self.assertEqual(study_log.tree_days(days, [10], suspended=False), {9, 2})
        self.assertEqual(study_log.tree_days(days, [10, 20], suspended=False), {9, 5, 2})  # 20's day 5 is studied
        self.assertEqual(study_log.tree_days(days, [99]), set())  # a deck deleted since


class HugeHistoryTests(unittest.TestCase):
    def test_ten_years_of_a_tree_a_day_draw_two_years_and_count_them_all(self):
        db = a_db()
        days = 3650
        db.con.executemany("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (?, ?, 10, 0, 2, 2, 400, '{}', 0)",
                           [(d + 1, d + 1) for d in range(days)])
        db.con.executemany("insert into revlog (id, cid, ease, type) values (?, ?, 3, 0)", [(ms(d), d + 1) for d in range(days)])
        started = time.perf_counter()
        forest = fd.build_forest(study_log.load_rows(db, CUTOFF), CUTOFF, TODAY)
        merged = fd.merge_old(forest)
        self.assertLess(time.perf_counter() - started, 5)  # (seconds; a fraction of one here)
        self.assertEqual(forest["stats"]["trees"], days)
        self.assertEqual((forest["stats"]["streak"], forest["stats"]["longest_streak"]), (days, days))
        self.assertEqual(len(merged["trees"]), fd.MAX_INDIVIDUAL_TREES)
        self.assertEqual(merged["merged"]["count"], days - fd.MAX_INDIVIDUAL_TREES)
        self.assertEqual(merged["merged"]["from_ago"], days - 1)
        self.assertEqual(forest["stats"]["forest_age"], days - 1)


if __name__ == "__main__":
    unittest.main()

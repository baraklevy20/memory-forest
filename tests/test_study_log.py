"""What is read from the collection: deck filters, suspended cards, the start date, and
the searches behind a tree."""

from __future__ import annotations

import datetime as dt
import json
import unittest

from helpers import CUTOFF, DAY, TODAY, card, ms, rows

import forest_data as fd
import study_log


class DeckFilterTests(unittest.TestCase):
    def test_deck_forest_only_counts_that_decks_cards_and_reviews(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        # cid, current deck, home deck (odid != 0 means a filtered deck borrowed it), day
        for cid, did, odid, days in ((1, 10, 0, 5), (2, 10, 0, 5), (3, 20, 0, 3), (4, 99, 10, 5)):
            con.execute("insert into cards values (?, ?, ?, ?, 2, 2, ?, '{}', 0)", (cid, cid, did, odid, 5 if cid == 3 else 30))
            con.execute("insert into notes values (?, ?)", (cid, " leech " if cid == 3 else ""))
            con.execute("insert into revlog values (?, ?, 3, 0)", (ms(days), cid))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]

        whole = fd.build_forest(study_log.load_rows(DB(), CUTOFF), CUTOFF, TODAY)
        deck = fd.build_forest(study_log.load_rows(DB(), CUTOFF, [10]), CUTOFF, TODAY)
        self.assertEqual([t["n"] for t in whole["trees"]], [3, 1])
        # the card a filtered deck borrowed still belongs to its home deck's forest
        self.assertEqual([(t["ago"], t["n"]) for t in deck["trees"]], [(5, 3)])
        self.assertEqual(deck["stats"]["reviews"], 3)
        self.assertEqual(study_log.load_deck_days(DB(), CUTOFF, [10]), {5})
        # the leech (card 3, in deck 20) brings a crow to its own day's tree, and not to deck 10's forest
        self.assertEqual([(t["ago"], t.get("leeches", 0)) for t in whole["trees"]], [(5, 0), (3, 1)])
        self.assertFalse(any(t.get("leeches") for t in deck["trees"]))


class SuspendedTests(unittest.TestCase):
    """Suspended cards keep their trees, frozen as they were: size and stage, but no
    struggling and no recall."""

    @staticmethod
    def suspended(cid, ctype=2, s=60):
        return (cid, ctype, -1, 30, json.dumps({"s": s}))

    def test_a_tree_of_suspended_cards_stands_as_it_was(self):
        # suspended while relearning: it would otherwise yellow the tree for good
        cards = [self.suspended(1, ctype=3), self.suspended(2), self.suspended(3)]
        fl = {i: (ms(40), ms(30)) for i in (1, 2, 3)}
        tree = fd.build_forest(rows(cards, fl, lapses={2}), CUTOFF, TODAY)["trees"][0]
        self.assertEqual((tree["n"], tree["stage"], tree["health"], tree["struggling"]), (3, fd.MATURE, 0, 0))
        self.assertEqual(tree["suspended"], 3)
        self.assertFalse(tree["measured"])

    def test_health_and_recall_only_weigh_the_cards_still_studied(self):
        active = [card(i, s=60) for i in range(1, 5)]
        cards = active + [self.suspended(i) for i in range(5, 21)]
        fl = {i: (ms(40), ms(2)) for i in range(1, 21)}
        tree = fd.build_forest(rows(cards, fl, lapses={1, 2}), CUTOFF, TODAY)["trees"][0]
        # 2 of the 4 studied cards lapsed: half, not a tenth of all 20
        self.assertEqual((tree["n"], tree["suspended"], tree["health"]), (20, 16, 3))
        self.assertTrue(tree["measured"])

    def test_the_loader_only_brings_them_when_asked(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        for cid, queue in ((1, 2), (2, -1)):
            con.execute("insert into cards values (?, ?, 10, 0, 2, ?, 30, '{}', 0)", (cid, cid, queue))
            con.execute("insert into revlog values (?, ?, 3, 0)", (ms(5), cid))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        self.assertEqual([c[0] for c in study_log.load_rows(DB(), CUTOFF).cards], [1])
        self.assertEqual(sorted(c[0] for c in study_log.load_rows(DB(), CUTOFF, suspended=True).cards), [1, 2])
        con.execute("update cards set queue = -1")
        self.assertEqual(study_log.load_deck_days(DB(), CUTOFF, [10]), set())
        self.assertEqual(study_log.load_deck_days(DB(), CUTOFF, [10], suspended=True), {5})


class HistoryFilterTests(unittest.TestCase):
    """The History tab: decks left out of the forest, and a day it starts from."""

    def setUp(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        # cid, current deck, home deck, the days it was reviewed on (first one first)
        for cid, did, odid, days in ((1, 10, 0, (9, 2)), (2, 20, 0, (5,)), (3, 99, 20, (5,)), (4, 10, 0, (3, 1))):
            con.execute("insert into cards values (?, ?, ?, ?, 2, 2, 30, '{}', 0)", (cid, cid, did, odid))
            con.execute("insert into notes values (?, '')", (cid,))
            for d in days:
                con.execute("insert into revlog values (?, ?, 3, 0)", (ms(d), cid))
        # a deleted card's review: no card left to say which deck it was in
        con.execute("insert into revlog values (?, 7, 3, 0)", (ms(4),))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        self.db = DB()

    def test_a_left_out_deck_plants_nothing_and_its_reviews_dont_count(self):
        rows = study_log.load_rows(self.db, CUTOFF, excluded=[20])
        # card 3 sits in a filtered deck, but its home is deck 20, so it goes too
        self.assertEqual(sorted(c[0] for c in rows.cards), [1, 4])
        self.assertNotIn(5, rows.review_days)
        # the deleted card's review stays: 4 reviews of decks 10, and that one
        self.assertEqual(rows.total_reviews, 5)
        self.assertIn(4, rows.review_days)

    def test_the_review_log_kept_between_reads_adds_up_as_reading_it_whole(self):
        log = study_log.ReviewLog()
        same = lambda **kw: self.assertEqual(  # noqa: E731
            vars(study_log.load_rows(self.db, CUTOFF, log=log, **kw)), vars(study_log.load_rows(self.db, CUTOFF, **kw)))
        same(excluded=[20], since=ms(8) // 1000)
        # reviews come in: a new card's, one of a left-out deck's, and a manual reschedule
        for rid, cid, ease, rtype in ((ms(0, 9), 4, 3, 1), (ms(0, 10), 2, 3, 1), (ms(0, 11), 1, 0, 4), (ms(0, 12), 8, 3, 0)):
            self.db.all("insert into revlog values (?, ?, ?, ?)", rid, cid, ease, rtype)
        same(excluded=[20], since=ms(8) // 1000)
        self.assertEqual(log.newest, ms(0, 12))
        # an undo takes the newest review away: read whole again
        self.db.all("delete from revlog where id = ?", ms(0, 12))
        same(excluded=[20], since=ms(8) // 1000)
        # another choice of decks: read whole again
        same(dids=[10])

    def test_nothing_before_the_start_date_counts(self):
        rows = study_log.load_rows(self.db, CUTOFF, since=ms(4, hour=4) // 1000)
        # card 1 was first studied 9 days ago, so its tree would stand before the forest
        self.assertEqual(sorted(c[0] for c in rows.cards), [4])
        # ... but a review of it since then still counts as a day of study
        self.assertEqual(rows.review_days, {1, 2, 3, 4})
        self.assertEqual(rows.total_reviews, 4)
        # the cards that remain are dated by their whole history, not from the start date
        tree = fd.build_forest(rows, CUTOFF, TODAY)["trees"]
        self.assertEqual([t["ago"] for t in tree], [3])

    def test_the_start_date_begins_at_the_rollover_hour(self):
        today = study_log.day_date(0, CUTOFF)
        self.assertEqual(study_log.day_start(today, CUTOFF), CUTOFF - DAY)
        self.assertEqual(study_log.day_start(today - dt.timedelta(days=3), CUTOFF), CUTOFF - 4 * DAY)


class TreeCountTests(unittest.TestCase):
    """The History tab's tree counts: one query, then the same trees the forest would grow
    for any choice of decks, start date and suspended cards."""

    def setUp(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        # cid, current deck, home deck, type, queue (-1 suspended), the days it was reviewed on
        for cid, did, odid, ctype, queue, days in (
                (1, 10, 0, 2, 2, (9, 2)), (2, 20, 0, 2, 2, (5,)), (3, 99, 20, 2, 2, (6,)),
                (4, 10, 0, 2, -1, (3, 1)), (5, 10, 0, 2, 2, (3,)), (6, 20, 0, 2, -1, (7,)),
                (7, 10, 0, 0, 0, ()), (8, 30, 0, 2, 2, (8,)), (9, 30, 0, 2, 2, (4,))):
            con.execute("insert into cards values (?, ?, ?, ?, ?, ?, 30, '{}', 0)", (cid, cid, did, odid, ctype, queue))
            con.execute("insert into notes values (?, '')", (cid,))
            for d in days:
                con.execute("insert into revlog values (?, ?, 3, 0)", (ms(d), cid))
        # a reschedule is not study, so it never dates a card
        con.execute("insert into revlog values (?, 5, 0, 4)", (ms(12),))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        self.db = DB()

    def test_the_counts_match_the_forest(self):
        days = study_log.load_tree_days(self.db, CUTOFF, skip=[9])
        # card 3 counts for its home deck, 20, not the filtered deck it sits in; 9 is skipped
        self.assertEqual(days, {10: {9: True, 3: True}, 20: {5: True, 6: True, 7: False}, 30: {8: True}})
        for excluded in ([], [20], [10, 30]):
            for since_ago in (None, 6):
                for suspended in (False, True):
                    since = study_log.day_start(study_log.day_date(since_ago, CUTOFF), CUTOFF) if since_ago is not None else None
                    rows = study_log.load_rows(self.db, CUTOFF, excluded=excluded, since=since, suspended=suspended, skip=[9])
                    forest = {t["ago"] for t in fd.build_forest(rows, CUTOFF, TODAY)["trees"]}
                    counted = [d for d in (10, 20, 30) if d not in excluded]
                    with self.subTest(excluded=excluded, since=since_ago, suspended=suspended):
                        self.assertEqual(study_log.tree_days(days, counted, since_ago, suspended), forest)


class SearchTests(unittest.TestCase):
    """What clicking a tree asks Anki for. When the forest skips suspended cards the
    search must too, or the tooltip's count and the browser's list disagree."""

    def test_one_day_is_the_difference_of_two_introduced_terms(self):
        self.assertEqual(study_log.day_search(5), ["introduced:6", "-is:suspended", "-introduced:5"])

    def test_today_needs_no_lower_bound(self):
        self.assertEqual(study_log.day_search(0), ["introduced:1", "-is:suspended"])

    def test_a_range_spans_from_the_oldest_day_to_the_newest(self):
        terms = study_log.day_search(1200, 420)
        self.assertEqual(terms, ["introduced:1201", "-is:suspended", "-introduced:420"])

    def test_a_one_day_range_is_the_same_as_that_day(self):
        self.assertEqual(study_log.day_search(30, 30), study_log.day_search(30))

    def test_a_forest_that_keeps_suspended_cards_finds_them_too(self):
        self.assertEqual(study_log.day_search(5, suspended=True), ["introduced:6", "-introduced:5"])


class EventQueryTests(unittest.TestCase):
    """What the events read on their own: the backlog, and the leeches cured."""

    @staticmethod
    def db():
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text,
                                due integer, odue integer);
            create table revlog (id integer, cid integer, ease integer, type integer, ivl integer, lastIvl integer);
            create table notes (id integer, tags text);
        """)

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        return con, DB()

    def test_the_backlog_counts_reviews_due_before_today_in_their_home_decks(self):
        con, db = self.db()
        # cid, deck, home deck, queue, due, home deck's due
        for row in ((1, 10, 0, 2, TODAY - 3, 0), (2, 10, 0, 2, TODAY, 0), (3, 10, 0, 0, 5, 0),
                    (4, 30, 10, 2, 9, TODAY - 1), (5, 20, 0, 3, TODAY - 1, 0), (6, 20, 0, -1, TODAY - 9, 0)):
            con.execute("insert into cards values (?, ?, ?, ?, 2, ?, 30, '{}', ?, ?)", (row[0], row[0], *row[1:]))
        for days, n in ((1, 4), (2, 6), (0, 50), (40, 99)):  # today's, and those before the window, don't count
            for i in range(n):
                con.execute("insert into revlog values (?, 1, 3, 1, 30, 30)", (ms(days) + i,))
        # due before today: 1, the filtered deck's 4 (by its home deck's due) and 5 (relearning)
        overdue, counts = study_log.load_backlog(db, TODAY, CUTOFF, 30)
        self.assertEqual((overdue, sorted(counts)), (3, [4, 6]))
        self.assertEqual(study_log.load_backlog(db, TODAY, CUTOFF, 30, excluded=[20])[0], 2)

    def test_a_leech_is_cured_once_it_grows_mature_and_stays_so(self):
        con, db = self.db()
        # cid, interval now, tagged, when it grew mature (days ago)
        for cid, ivl, tagged, matured in ((1, 25, True, 2), (2, 25, True, 30), (3, 25, False, 2), (4, 8, True, 2)):
            con.execute("insert into cards values (?, ?, 10, 0, 2, 2, ?, '{}', 0, 0)", (cid, cid, ivl))
            con.execute("insert into notes values (?, ?)", (cid, " leech " if tagged else ""))
            con.execute("insert into revlog values (?, ?, 3, 0, 1, 0)", (ms(40 + cid), cid))  # first studied
            con.execute("insert into revlog values (?, ?, 3, 1, 25, 12)", (ms(matured), cid))
        # only card 1: card 2 was cured a month ago, 3 was never a leech, 4 has lapsed again since
        self.assertEqual(study_log.load_cured(db, CUTOFF, 7), {41: 1})

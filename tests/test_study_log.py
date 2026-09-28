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
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text);
            create table revlog (id integer, cid integer, ease integer, type integer);
        """)
        # cid, current deck, home deck (odid != 0 means a filtered deck borrowed it), day
        for cid, did, odid, days in ((1, 10, 0, 5), (2, 10, 0, 5), (3, 20, 0, 3), (4, 99, 10, 5)):
            con.execute("insert into cards values (?, ?, ?, ?, 2, 2, 30, '{}')", (cid, cid, did, odid))
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

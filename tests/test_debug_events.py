"""The Debug tab's switches (debug_events.py): each event on demand, only while debug is
on - in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import addon, reset

state, payload = addon.state, addon.payload
PLANTED = [(i, 10, 40 - i) for i in range(21)] + [(100, 10, 5), (101, 10, 4)]


class DebugEventTests(unittest.TestCase):
    def test_nothing_without_debug_on(self):
        reset(PLANTED, {"debug": False, "debug_big_days": True,
                        "test_forest": True, "debug_timeline": [["study", 1], ["leech", 2], ["review", 8]]})
        p = payload.payload()
        self.assertFalse(any(t.get("leeches") or t.get("big") for t in p["trees"]))
        self.assertIsNone(p["doom"])
        self.assertEqual(p["stagnation"], 0)

    def test_each_leech_brings_a_crow_to_a_grown_tree_of_its_own(self):
        trees = self.passed("wild", ("study", 2), ("leech", 2))["trees"]
        crows = [t for t in trees if t.get("leeches")]
        self.assertEqual([t["leeches"] for t in crows], [1, 1])
        self.assertTrue(all(t["stage"] >= addon.forest_data.MATURE for t in crows))
        grown = [t for t in trees if t["stage"] >= addon.forest_data.MATURE]
        self.assertEqual(crows, grown[-2:])  # the newest grown trees

    def test_a_leech_cured_sends_the_oldest_crow_off_and_leaves_a_robin_for_a_week(self):
        steps = (("study", 1), ("leech", 1), ("leech", 1), ("cure", 1))
        trees = self.passed("wild", *steps)["trees"]
        self.assertEqual([(bool(t.get("leeches")), t.get("cured")) for t in trees if t.get("leeches") or t.get("cured")],
                         [(True, None), (False, 1)])  # the first leech's tree (the newest grown) has the robin
        self.assertTrue(any(t.get("cured") for t in self.passed("wild", *steps, ("study", 6))["trees"]))
        self.assertFalse(any(t.get("cured") for t in self.passed("wild", *steps, ("study", 7))["trees"]))  # a week on, it has gone

    def test_tumbleweeds_and_the_backlog_cleared(self):
        reset(PLANTED, {"debug": True, "nature": "wild", "debug_backlog": 50})
        backlog = payload.payload()["backlog"]
        self.assertEqual((backlog["hell"], backlog["cleared"]), (0.5, False))
        self.assertGreater(backlog["overdue"], 30)  # made up, for its tooltip
        # "Clear the backlog", clicked twice: the tumbleweeds it had blow away, again on each click
        reset(PLANTED, {"debug": True, "nature": "wild", "debug_backlog_cleared": 2, "debug_backlog_was": 80})
        backlog = payload.payload()["backlog"]
        self.assertEqual((backlog["cleared"], backlog["was"], backlog["replay"]), (True, 0.8, "debug-2"))
        # and once the tumbleweeds are back, it is review hell again, not cleared
        reset(PLANTED, {"debug": True, "nature": "wild", "debug_backlog_cleared": 2, "debug_backlog": 30})
        self.assertFalse(payload.payload()["backlog"]["cleared"])

    def test_peaceful_keeps_the_bad_things_away_here_too(self):
        reset(PLANTED, {"debug": True, "debug_backlog": 50, "test_forest": True,  # crows, and grass that would grow
                        "debug_timeline": [["study", 1], ["review", 8], ["leech", 3], ["cure", 1]]})
        p = payload.payload()
        self.assertFalse(any(t.get("leeches") for t in p["trees"]))
        self.assertEqual((p["stagnation"], p["backlog"]["hell"]), (0, 0))
        self.assertTrue(any(t.get("cured") for t in p["trees"]))  # the good things stay

    def test_big_learning_days(self):
        reset(PLANTED, {"debug": True, "debug_big_days": True})
        self.assertTrue(any(t.get("big") for t in payload.payload()["trees"]))

    @staticmethod
    def passed(nature, *steps):
        reset(PLANTED, {"debug": True, "nature": nature, "test_forest": True, "test_trees": 40, "debug_timeline": [list(s) for s in steps]})
        return payload.payload()

    def test_a_day_away_on_merciless_brings_the_asteroid(self):
        p = self.passed("merciless", ("study", 3), ("away", 1))
        self.assertEqual((len(p["craters"]), p["strike"]["lost"]), (1, 43))  # the forest and the three days studied
        self.assertTrue(p["strike"]["seen"].startswith("debug-timeline-"))
        self.assertEqual((p["trees"], p["visitors"]), ([], []))  # the animals go with the forest
        self.assertEqual(state.load_state().get("strike_days"), None)  # the test forest remembers no strikes

    def test_each_strike_on_the_timeline_leaves_its_own_crater(self):
        p = self.passed("merciless", ("away", 1), ("study", 1), ("away", 1))
        self.assertEqual([(c["ago"], c["lost"]) for c in p["craters"]], [(3, 40), (1, 1)])
        self.assertEqual(len({c["spot"] for c in p["craters"]}), 2)  # each where its own day put it
        self.assertEqual(p["strike"]["lost"], 1)  # the latest is the one to play

    def test_a_new_timeline_strikes_somewhere_new(self):
        first = self.passed("merciless", ("away", 1))["craters"][0]["spot"]
        self.assertEqual(self.passed("merciless", ("away", 1))["craters"][0]["spot"], first)  # stays put as it is redrawn
        addon.debug_events.new_timeline_run()
        self.assertNotEqual(payload.payload()["craters"][0]["spot"], first)

    def test_two_days_away_on_wild_start_a_fire_that_a_week_of_study_puts_out(self):
        p = self.passed("wild", ("away", 1))  # today is the second: not over yet, only smoke
        self.assertEqual((p["fire"]["trees"], p["fire"]["smoke"]), (0, 2))
        self.assertEqual(len([t for t in p["trees"] if t.get("smoke")]), 2)
        self.assertIn("Study today", p["journal"])
        p = self.passed("wild", ("away", 2))
        self.assertEqual((p["craters"], p["doom"], p["fire"]["trees"], p["fire"]["left"]), ([], None, 2, 7))  # 5% of 40
        self.assertEqual(len([t for t in p["trees"] if t.get("burn")]), 2)
        self.assertEqual(self.passed("wild", ("away", 2), ("study", 5))["fire"]["left"], 1)  # today makes six
        self.assertTrue(self.passed("wild", ("away", 2), ("study", 6))["fire"]["out"])

    def test_peaceful_lets_the_days_go_by(self):
        p = self.passed("peaceful", ("away", 30))
        self.assertEqual((p["craters"], p["doom"], len(p["trees"])), ([], None, 40))

    def test_the_trees_dates_run_in_order_as_the_days_pass(self):
        trees = self.passed("wild", ("study", 30))["trees"]
        dates = [t["date"] for t in trees]
        self.assertEqual(dates, sorted(dates))  # oldest first, as sent
        self.assertEqual(len(set(dates)), len(dates))

    def test_studying_plants_a_tree_a_day_and_keeps_the_old_ones_as_they_were(self):
        # a tree's seed comes from its day: the old ones keep theirs, in their places (oldest
        # first), and the new ones come after them
        before = [t["seed"] for t in self.passed("wild", ("study", 2))["trees"]]
        after = [t["seed"] for t in self.passed("wild", ("study", 2), ("study", 3))["trees"]]
        self.assertEqual(len(after), len(before) + 3)
        self.assertEqual(after[:len(before)], before)

    def test_a_week_reviewing_only_lets_the_grass_grow(self):
        self.assertEqual(self.passed("wild", ("study", 1), ("review", 3))["stagnation"], 0)
        self.assertGreater(self.passed("wild", ("study", 1), ("review", 8))["stagnation"], 0)


if __name__ == "__main__":
    unittest.main()

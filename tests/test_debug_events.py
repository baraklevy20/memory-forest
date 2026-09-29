"""The Debug group's switches (debug_events.py): each event on demand, only while debug is
on - in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import addon, reset

state, payload = addon.state, addon.payload
PLANTED = [(i, 10, 40 - i) for i in range(21)] + [(100, 10, 5), (101, 10, 4)]


class DebugEventTests(unittest.TestCase):
    def test_nothing_without_debug_on(self):
        reset(PLANTED, {"debug": False, "debug_leeches": 3, "debug_missed": 3, "debug_stagnation": 50, "debug_big_days": True})
        p = payload.payload()
        self.assertFalse(any(t.get("leeches") or t.get("big") for t in p["trees"]))
        self.assertIsNone(p["doom"])
        self.assertEqual(p["stagnation"], 0)

    def test_crows_on_the_newest_grown_trees(self):
        reset(PLANTED, {"debug": True, "debug_leeches": 3})
        with_crows = [t["ago"] for t in payload.payload()["trees"] if t.get("leeches")]
        self.assertEqual(with_crows, [20, 5, 4])  # the newest three grown trees (oldest first, as sent)

    def test_the_asteroid_on_its_way(self):
        reset(PLANTED, {"debug": True, "stakes": "wild", "debug_missed": 3})
        self.assertEqual(payload.payload()["doom"], {"missed": 3, "grace": 7, "left": 4})

    def test_tall_grass(self):
        reset(PLANTED, {"debug": True, "debug_stagnation": 50})
        self.assertEqual(payload.payload()["stagnation"], 0.5)

    def test_big_learning_days(self):
        reset(PLANTED, {"debug": True, "debug_big_days": True})
        self.assertTrue(any(t.get("big") for t in payload.payload()["trees"]))

    def test_the_timeline_plays_on_the_test_forest(self):
        reset(PLANTED, {"debug": True, "test_forest": True, "test_trees": 40, "debug_timeline": ["strike", 7]})
        p = payload.payload()
        self.assertEqual(len(p["craters"]), 1)
        self.assertTrue(p["strike"]["seen"].startswith("debug-"))
        self.assertEqual(state.load_state().get("strike_days"), None)  # the test forest remembers no strikes


if __name__ == "__main__":
    unittest.main()

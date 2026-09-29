"""The Debug group's switches (debug_events.py): each event on demand, only while debug is
on - in a stand-in Anki."""

from __future__ import annotations

import unittest

from fake_anki import addon, reset

payload = addon.payload
PLANTED = [(i, 10, 40 - i) for i in range(21)] + [(100, 10, 5), (101, 10, 4)]


class DebugEventTests(unittest.TestCase):
    def test_nothing_without_debug_on(self):
        reset(PLANTED, {"debug": False, "debug_leeches": 3, "debug_stagnation": 50})
        p = payload.payload()
        self.assertFalse(any(t.get("leeches") for t in p["trees"]))
        self.assertEqual(p["stagnation"], 0)

    def test_crows_on_the_newest_grown_trees(self):
        reset(PLANTED, {"debug": True, "debug_leeches": 3})
        with_crows = [t["ago"] for t in payload.payload()["trees"] if t.get("leeches")]
        self.assertEqual(with_crows, [20, 5, 4])  # the newest three grown trees (oldest first, as sent)


    def test_tall_grass(self):
        reset(PLANTED, {"debug": True, "debug_stagnation": 50})
        self.assertEqual(payload.payload()["stagnation"], 0.5)


if __name__ == "__main__":
    unittest.main()

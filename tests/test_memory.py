"""The FSRS forgetting curve."""

from __future__ import annotations

import unittest

import memory


class RetrievabilityTests(unittest.TestCase):
    """The "% remembered" number, which the tooltip states as fact."""

    def test_a_card_just_reviewed_is_remembered(self):
        self.assertAlmostEqual(memory.retrievability(100, 0, "{}"), 1.0, places=6)

    def test_at_its_stability_a_card_sits_at_ninety_percent(self):
        # that is what FSRS stability means: 90% recall after `stability` days
        self.assertAlmostEqual(memory.retrievability(100, 100, "{}"), 0.9, places=6)
        self.assertAlmostEqual(memory.retrievability(7, 7, '{"decay":0.2}'), 0.9, places=6)

    def test_each_card_uses_its_own_decay(self):
        # FSRS-6 gives every card a decay; a flatter curve forgets more slowly
        late_default = memory.retrievability(10, 100, "{}")
        late_flat = memory.retrievability(10, 100, '{"decay":0.15}')
        self.assertGreater(late_flat, late_default)

    def test_nonsense_decay_falls_back_to_the_default(self):
        for blob in ('{"decay":0}', '{"decay":5}', '{"decay":"x"}', "{}", ""):
            self.assertAlmostEqual(memory.retrievability(50, 50, blob), 0.9, places=6)

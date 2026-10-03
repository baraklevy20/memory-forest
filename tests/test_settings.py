"""The settings dialog's logic that needs no window: what Cancel puts back of the decks left
out, and what Restore defaults says it keeps."""

from __future__ import annotations

import importlib
import unittest

from fake_anki import PACKAGE, mw

dialog = importlib.import_module(f"{PACKAGE}.settings.dialog")
history = importlib.import_module(f"{PACKAGE}.settings.history")


def cancel(original: set, *outside: set) -> set:
    """The decks left out after Cancel, the config having gone through `outside` behind the
    dialog's back (each step from the one before, or from what the dialog last wrote)."""
    left_out, brought_back = set(), set()
    for before, after in outside:
        left_out, brought_back = history.outside_moves(before, after, left_out, brought_back)
    return history.undo_here(original, left_out, brought_back)


class CancelDecksTests(unittest.TestCase):
    def test_a_deck_unticked_here_comes_back(self):
        # unticked here (written: {10, 20}), then 30 left out from its gear menu
        self.assertEqual(cancel({10}, ({10, 20}, {10, 20, 30})), {10, 30})

    def test_a_deck_ticked_here_is_left_out_again(self):
        self.assertEqual(cancel({10, 20}, ({10}, {10, 30})), {10, 20, 30})

    def test_a_deck_brought_back_outside_stays_back(self):
        self.assertEqual(cancel({10, 20}, ({10, 20}, {20})), {20})

    def test_a_deck_left_out_and_brought_back_outside_is_as_it_was(self):
        self.assertEqual(cancel({10}, ({10}, {10, 30}), ({10, 30}, {10})), {10})
        self.assertEqual(cancel({30}, ({30}, set()), (set(), {30})), {30})

    def test_unticked_here_then_left_out_outside_too_stays_out(self):
        # the gear menu left out a deck the dialog had already left out: nothing moved there
        self.assertEqual(cancel({10}, ({10, 20}, {10, 20})), {10})


class RestoreDefaultsTests(unittest.TestCase):
    def test_it_says_what_it_keeps(self):
        note = dialog.restore_note(mw.addonManager.addonConfigDefaults("x"))
        self.assertIn("Peaceful", note)
        for kept in ("decks you left out", "start date", "suspended", "phone"):
            self.assertIn(kept, note)

    def test_what_it_says_it_keeps_is_what_it_keeps(self):
        self.assertEqual(set(dialog.DATA_KEYS), {"excluded_decks", "ignore_before", "keep_suspended"})


if __name__ == "__main__":
    unittest.main()

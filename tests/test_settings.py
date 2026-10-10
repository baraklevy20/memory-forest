"""The settings dialog's logic that needs no window: what Cancel puts back of the decks left
out, and what Restore defaults says it keeps."""

from __future__ import annotations

import importlib
import sys
import types
import unittest

from fake_anki import PACKAGE, mw

dialog = importlib.import_module(f"{PACKAGE}.settings.dialog")
decks = importlib.import_module(f"{PACKAGE}.settings.decks")
palette = importlib.import_module(f"{PACKAGE}.settings.palette")


def cancel(original: set, *outside: set) -> set:
    """The decks left out after Cancel, the config having gone through `outside` behind the
    dialog's back (each step from the one before, or from what the dialog last wrote)."""
    left_out, brought_back = set(), set()
    for before, after in outside:
        left_out, brought_back = decks.outside_moves(before, after, left_out, brought_back)
    return decks.undo_here(original, left_out, brought_back)


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


class PaletteTests(unittest.TestCase):
    """The settings' colours on Anki's design system (2.1.55 and later) and on the older
    palette (2.1.45 to 2.1.54), which has no var(), no aqt.props and no themed icons."""

    def setUp(self):
        self.was = (palette.theme_manager, palette.colors, sys.modules.get("aqt.props"))

    def tearDown(self):
        palette.theme_manager, palette.colors, props = self.was
        sys.modules["aqt.props"] = props

    def test_the_design_system_where_anki_has_it(self):
        palette.colors = types.SimpleNamespace(FG="--fg", BORDER_FOCUS="--focus")
        palette.theme_manager = types.SimpleNamespace(var=lambda v: f"var{v}", themed_icon=lambda p: f"/icons/{p}")
        sys.modules["aqt.props"] = types.SimpleNamespace(BORDER_RADIUS="--radius")
        self.assertEqual((palette.color("FG"), palette.color("BORDER_FOCUS")), ("var--fg", "var--focus"))
        self.assertEqual(palette.radius(), "var--radius")
        self.assertEqual(palette.chevron(), "/icons/mdi:chevron-down")

    def test_the_old_palette_on_anki_2_1_50(self):
        old = {name: (f"{name}-day", f"{name}-night") for name in set(palette.OLD.values())}
        palette.colors = types.SimpleNamespace(**old)
        palette.theme_manager = types.SimpleNamespace(color=lambda pair: pair[1], night_mode=True)
        sys.modules.pop("aqt.props", None)
        for new, was in palette.OLD.items():
            self.assertEqual(palette.color(new), f"{was}-night")
        self.assertEqual(palette.radius(), palette.OLD_RADIUS)
        self.assertIsNone(palette.chevron())  # Qt draws its own arrow


if __name__ == "__main__":
    unittest.main()

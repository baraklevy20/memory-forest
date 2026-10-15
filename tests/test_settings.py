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
whats_new = importlib.import_module(f"{PACKAGE}.settings.whats_new")


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


class OutsideTests(unittest.TestCase):
    def test_the_heatmaps_toggle_outlives_the_dialog(self):
        # Reviews | Time clicked on the heatmap while the dialog is open: neither its next
        # change nor Cancel puts it back
        now = {"calendar_shade": "time", "nature": "wild"}
        opened = {"calendar_shade": "reviews", "nature": "peaceful"}
        kept = {k: v for k, v in opened.items() if k not in dialog.OUTSIDE_KEYS}
        kept.update({k: v for k, v in now.items() if k in dialog.OUTSIDE_KEYS})
        self.assertEqual(kept, {"calendar_shade": "time", "nature": "peaceful"})
        self.assertNotIn("calendar_shade", dialog.DATA_KEYS)  # (Restore defaults still resets it)


    def test_the_heatmaps_view_switch_outlives_the_dialog(self):
        # By year chosen on the heatmap while the dialog is open: kept on its next save and on Cancel
        cfg = {"calendar": "timeline", "nature": "peaceful"}
        dialog.keep_heatmap_view(cfg, {"calendar": "by_year"}, touched=False)
        self.assertEqual(cfg, {"calendar": "by_year", "nature": "peaceful"})

    def test_the_view_changed_here_wins(self):
        cfg = {"calendar": "timeline"}
        dialog.keep_heatmap_view(cfg, {"calendar": "by_year"}, touched=True)
        self.assertEqual(cfg, {"calendar": "timeline"})

    def test_the_default_view_left_unset(self):
        cfg = {"calendar": "timeline"}
        dialog.keep_heatmap_view(cfg, {}, touched=False)
        self.assertEqual(cfg, {})


class RestoreDefaultsTests(unittest.TestCase):
    def test_it_says_what_it_keeps(self):
        note = dialog.restore_note(mw.addonManager.addonConfigDefaults("x"))
        self.assertIn("Peaceful", note)
        for kept in ("decks you left out", "start date", "suspended", "phone"):
            self.assertIn(kept, note)

    def test_what_it_says_it_keeps_is_what_it_keeps(self):
        self.assertEqual(set(dialog.DATA_KEYS), {"excluded_decks", "ignore_before", "keep_suspended", "calendar_record", "streak_from_start"})


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


class HeatmapViewTests(unittest.TestCase):
    def test_the_view_choice_offers_every_view(self):
        tab = importlib.import_module(f"{PACKAGE}.settings.heatmap_tab")
        state = importlib.import_module(f"{PACKAGE}.state")
        self.assertEqual([key for key, _label in tab.CALENDAR_OPTIONS], list(state.CALENDAR_VIEWS))



class FakeBadge:
    """The NEW pill: 40 x 16, where it was put and on what."""

    def __init__(self):
        self.parent, self.at, self.shown = None, None, False

    def setParent(self, parent):
        self.parent = parent

    def adjustSize(self):
        pass

    def width(self):
        return 40

    def height(self):
        return 16

    def move(self, x, y):
        self.at = (x, y)

    def show(self):
        self.shown = True


class FakeBar:
    """A tab bar: each character 8 px wide, each tab 100 px from x 0, any widget put on a tab
    (which there must be none of)."""

    def __init__(self):
        self.props, self.buttons, self.filters = {}, [], []
        self.ButtonPosition = types.SimpleNamespace(RightSide=1, LeftSide=0)

    def property(self, key):
        return self.props.get(key)

    def setProperty(self, key, value):
        self.props[key] = value

    def fontMetrics(self):
        return types.SimpleNamespace(horizontalAdvance=lambda text: 8 * len(text))

    def tabRect(self, i):
        return types.SimpleNamespace(center=lambda: types.SimpleNamespace(x=lambda: 100 * i + 50, y=lambda: 12))

    def installEventFilter(self, f):
        self.filters.append(f)

    def setTabButton(self, *a):
        self.buttons.append(a)


class FakeTabs:
    def __init__(self, *names):
        self.names, self.bar = list(names), FakeBar()

    def tabText(self, i):
        return self.names[i]

    def setTabText(self, i, text):
        self.names[i] = text

    def tabBar(self):
        return self.bar


class NewTabTests(unittest.TestCase):
    def setUp(self):
        # (stand-ins for the pill and the bar's watcher, which the tests' Qt can't build)
        self.saved = whats_new.pill, whats_new._KeepPlaced
        self.badges = []
        whats_new.pill = lambda: self.badges.append(FakeBadge()) or self.badges[-1]
        whats_new._KeepPlaced = lambda bar, place: place

    def tearDown(self):
        whats_new.pill, whats_new._KeepPlaced = self.saved

    def test_room_after_the_name_for_the_pill(self):
        text = whats_new.tab_text("Heatmap", 40, 8)
        self.assertTrue(text.startswith("Heatmap"))
        self.assertGreaterEqual(8 * (len(text) - len("Heatmap")), 40 + whats_new.TAB_GAP)

    def test_no_widget_put_on_the_tab(self):
        # (macOS's tabs cut the name short to make room for one: "He... NEW")
        tabs = FakeTabs("Scenery", "Heatmap")
        whats_new.tag_tab(tabs, 1)
        self.assertEqual(tabs.bar.buttons, [])

    def test_the_pill_sits_after_the_name_on_the_bar(self):
        tabs = FakeTabs("Scenery", "Heatmap")
        whats_new.tag_tab(tabs, 1)
        badge, text = self.badges[0], tabs.names[1]
        self.assertIs(badge.parent, tabs.bar)
        self.assertTrue(badge.shown)
        name_end = 150 - 8 * len(text) // 2 + 8 * len("Heatmap")
        self.assertEqual(badge.at[0], name_end + whats_new.TAB_GAP)
        self.assertLessEqual(badge.at[0] + badge.width(), 150 + 8 * len(text) // 2)  # (inside the room made)

    def test_kept_in_place_when_the_bar_is_laid_out_again(self):
        tabs = FakeTabs("Heatmap")
        whats_new.tag_tab(tabs, 0)
        self.assertEqual(len(tabs.bar.filters), 1)

    def test_tagged_once(self):
        tabs = FakeTabs("Heatmap")
        whats_new.tag_tab(tabs, 0)
        once = tabs.names[0]
        whats_new.tag_tab(tabs, 0)
        self.assertEqual((tabs.names[0], len(self.badges)), (once, 1))

    def test_no_tab_no_tag(self):
        tabs = FakeTabs("Heatmap")
        whats_new.tag_tab(tabs, -1)
        self.assertEqual((tabs.names, self.badges), (["Heatmap"], []))


if __name__ == "__main__":
    unittest.main()

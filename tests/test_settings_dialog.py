"""The real settings dialog, opened offscreen and driven as a user drives it: opening it in each
edition, Done, Cancel, the window's X, Restore defaults, the tab it reopens on, its hook on
Anki's theme and a theme switch while it is open. (Each control's own round trip into the
config: test_settings_dialog_controls.py.) Skipped without PyQt6: see settings_qt.py."""

from __future__ import annotations

import unittest

import settings_qt as Q
from settings_qt import QtCase, addon, current, needs_editions, saved

if Q.HAVE_QT:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox

BASE_TABS = ["Scenery", "Forest", "Heatmap", "Decks", "About"]


def plus_manifest():
    return {"package": "memory_forest_plus"}


class HarnessTests(QtCase):
    def test_an_exception_inside_a_slot_fails_the_test(self):
        # (PyQt hands it to sys.excepthook, and the click or timer goes on as if nothing happened)
        def slot():
            raise ValueError("raised in a slot")
        Q.QtCore.QTimer.singleShot(0, slot)
        Q.settle()
        self.assertEqual(len(self.slot_errors), 1)
        self.assertIn("raised in a slot", self.slot_errors[0])
        self.slot_errors.clear()

    def test_the_hooks_are_anki_s_not_lists(self):
        # Anki's hooks have no `in` (the Cancel crash of 2026-10-18 asked one); remove() lets a missing one pass
        hook = Q.hooks.theme_did_change
        with self.assertRaises(TypeError):
            print in hook  # noqa: B015
        hook.remove(print)


class OpeningTests(QtCase):
    def test_a_release_opens_on_five_tabs_without_debug(self):
        d = self.open_dialog()
        self.assertEqual(self.tab_names(d), BASE_TABS)
        self.assertEqual(d.windowTitle(), "Memory Forest")
        self.assertIsInstance(d.debug, addon.s_dialog.NoDebugTab)

    def test_plus_names_itself_in_the_title(self):
        edition = addon.edition
        was = edition.manifest
        edition.manifest = lambda folder=edition.ADDON_DIR: plus_manifest()
        self.addCleanup(setattr, edition, "manifest", was)
        d = self.open_dialog()
        self.assertEqual(d.windowTitle(), "Memory Forest Plus")
        self.assertEqual(self.tab_names(d), BASE_TABS)

    def test_debug_adds_a_debug_tab_in_every_edition(self):
        for edition in ("", "base", "plus"):
            with self.subTest(edition=edition or "dev"):
                d = self.open_dialog({"debug": True, "debug_edition": edition})
                self.assertEqual(self.tab_names(d), BASE_TABS[:4] + ["Debug", "About"])
                self.assertEqual(d.windowTitle(), "Memory Forest Plus" if edition == "plus" else "Memory Forest")
                self.cancel(d)

    @needs_editions
    def test_the_base_edition_offers_only_its_own_sceneries_and_shows_plus_ones_locked(self):
        d = self.open_dialog({"debug": True, "debug_edition": "base"})
        ships = addon.edition.edition_presets("base")
        offered = set(d.scenery.scenery_choices())
        self.assertTrue(offered, "no scenery offered")
        self.assertLessEqual(offered, ships)
        locked = [t.preset.key for t in d.scenery.picker.tiles if t.locked]
        self.assertTrue(locked, "no Plus scenery shown locked")
        self.assertFalse(set(locked) & offered)

    @needs_editions
    def test_plus_offers_its_own_sceneries_and_none_locked(self):
        d = self.open_dialog({"debug": True, "debug_edition": "plus"})
        offered = set(d.scenery.scenery_choices())
        self.assertIn("cherry_blossom", offered)
        self.assertLessEqual(offered, addon.edition.edition_presets("plus"))
        self.assertEqual([t for t in d.scenery.picker.tiles if t.locked], [])

    def test_every_tab_shows(self):
        for cfg in ({}, {"debug": True}):
            with self.subTest(debug=bool(cfg)):
                d = self.open_dialog(cfg)
                for i in range(d.tabs.count()):
                    d.tabs.setCurrentIndex(i)
                    Q.settle()
                    page = d.tabs.currentWidget()
                    self.assertTrue(page.isVisible(), d.tabs.tabText(i))
                    self.assertGreater(page.height(), 50, d.tabs.tabText(i))
                self.cancel(d)

    def test_opening_writes_nothing(self):
        self.open_dialog({"nature": "wild"})
        Q.let_save()
        self.assertEqual(saved(), {"nature": "wild"})
        self.assertEqual(self.changes, 0)

    def test_a_hand_edited_config_opens_on_the_defaults(self):
        d = self.open_dialog({"nature": "bogus", "animations": [1], "max_width": "wide", "streak_week": True,
                              "calendar_tiles": "nope", "calendar_colours": "ready:nope", "calendar_mine": "red",
                              "deck_forest_mode": {}, "excluded_decks": ["x", 20], "ignore_before": "soon"})
        self.assertEqual(d.forest.nature.currentData(), "peaceful")
        self.assertEqual(d.forest.animations.currentData(), "on")
        self.assertEqual(d.forest.max_width.value(), addon.state.MAX_WIDTH_DEFAULT)
        self.assertEqual(d.heatmap.streak_week.currentData(), 7)
        self.assertEqual(d.heatmap.look.tile_choice.currentData(), "scenery")
        self.assertEqual(d.heatmap.look.source.currentData(), "scenery")
        self.assertEqual(d.forest.deck_mode.currentData(), "highlight")
        self.assertEqual(d.decks.excluded, {20})
        self.assertFalse(d.decks.since_on.isChecked())

    def test_settings_from_an_older_version_are_dropped_on_done(self):
        self.open_dialog({"old_setting": 1, "nature": "wild"})
        d = self.dialog
        d.forest.planting.setChecked(False)
        self.done()
        self.assertEqual(saved(), {"nature": "wild", "planting_tooltip": False})

    def test_open_settings_opens_one_dialog_and_raises_it_again(self):
        settings = addon.settings
        made = []
        real = settings.SettingsDialog

        def dialog(*a, **k):
            d = real(*a, parent=self.host, **k)
            d.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            made.append(d)
            self.dialogs.append(d)
            return d
        settings.SettingsDialog = dialog
        self.addCleanup(setattr, settings, "SettingsDialog", real)
        self.addCleanup(setattr, settings, "_open", None)
        settings.open_settings(Q.PACKAGE, self.on_change, self.on_phone)
        Q.settle()
        self.assertTrue(addon.state._settings_open)
        settings.open_settings(Q.PACKAGE, self.on_change, self.on_phone, focus="decks")
        Q.settle()
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].tab_key(), "decks")  # (the note's button, on the dialog already up)
        self.assertTrue(made[0].testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose))
        self.cancel(made[0])
        self.assertIsNone(settings._open)
        self.assertFalse(addon.state._settings_open)


class DoneTests(QtCase):
    def test_done_without_a_change_writes_nothing(self):
        self.open_dialog()
        self.done()
        self.assertEqual(saved(), {})
        self.assertEqual(self.changes, 1)  # (the forest redrawn once, as it closes)

    def test_done_saves_exactly_what_changed(self):
        d = self.open_dialog({"nature": "wild", "city": "Berlin"})
        d.forest.planting.setChecked(False)
        d.heatmap.calendar_decks.setChecked(False)
        self.done()
        self.assertEqual(saved(), {"nature": "wild", "city": "Berlin", "planting_tooltip": False, "calendar_decks": False})
        self.assertFalse(d.isVisible())

    def test_a_change_is_saved_while_the_dialog_is_open(self):
        # the forest behind the dialog is its preview: each change saved and redrawn a moment after
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        self.assertEqual(saved(), {})  # (not at once: a slider dragged is one redraw)
        Q.let_save()
        self.assertEqual(saved(), {"planting_tooltip": False})
        self.assertEqual(self.changes, 1)

    def test_changing_a_setting_back_saves_nothing(self):
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        d.forest.planting.setChecked(True)
        self.done()
        self.assertEqual(saved(), {})

    def test_a_setting_back_at_its_default_is_left_unset(self):
        d = self.open_dialog({"planting_tooltip": False})
        d.forest.planting.setChecked(True)
        self.done()
        self.assertNotIn("planting_tooltip", saved())

    def test_enter_means_done(self):
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        self.press(d, Qt.Key.Key_Return)
        self.assertFalse(d.isVisible())
        self.assertEqual(d.result(), 1)
        self.assertEqual(saved(), {"planting_tooltip": False})

    def test_the_heatmaps_own_toggle_is_saved_as_it_is_now(self):
        # Reviews | Time and Timeline | By year are switched on the heatmap, maybe while the dialog is up
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        Q.fake_anki.mw.addonManager.config["calendar_shade"] = "time"
        Q.fake_anki.mw.addonManager.config["calendar"] = "by_year"
        self.done()
        self.assertEqual(saved(), {"planting_tooltip": False, "calendar_shade": "time", "calendar": "by_year"})


class CancelTests(QtCase):
    def change_and_save(self, d):
        d.forest.planting.setChecked(False)
        d.forest.nature.buttons["merciless"].click()
        d.heatmap.week.buttons["monday"].click()
        Q.let_save()
        self.assertEqual(current()["nature"], "merciless")  # (saved: the preview)

    def test_cancel_puts_back_what_was_changed(self):
        d = self.open_dialog({"nature": "wild", "city": "Berlin"})
        self.change_and_save(d)
        self.cancel(d)
        self.assertEqual(saved(), {"nature": "wild", "city": "Berlin"})
        self.assertFalse(d.isVisible())

    def test_cancel_before_the_change_is_saved_writes_the_old_config(self):
        d = self.open_dialog({"nature": "wild"})
        d.forest.planting.setChecked(False)
        self.cancel(d)
        Q.let_save()  # (and nothing saved after it)
        self.assertEqual(saved(), {"nature": "wild"})

    def test_closing_the_window_cancels(self):
        d = self.open_dialog({"nature": "wild"})
        self.change_and_save(d)
        d.close()  # (the window's X)
        Q.settle()
        self.assertEqual(saved(), {"nature": "wild"})
        self.assertEqual(Q.hooks.theme_did_change.count(), 0)

    def test_escape_cancels(self):
        d = self.open_dialog({"nature": "wild"})
        self.change_and_save(d)
        self.press(d, Qt.Key.Key_Escape)
        self.assertFalse(d.isVisible())
        self.assertEqual(saved(), {"nature": "wild"})

    def test_cancel_redraws_the_forest(self):
        d = self.open_dialog()
        self.change_and_save(d)
        before = self.changes
        self.cancel(d)
        self.assertEqual(self.changes, before + 1)

    def test_cancel_leaves_the_heatmaps_own_toggle_as_it_is_now(self):
        d = self.open_dialog({"calendar_shade": "reviews"})
        self.change_and_save(d)
        Q.fake_anki.mw.addonManager.config["calendar_shade"] = "time"
        self.cancel(d)
        self.assertEqual(saved(), {"calendar_shade": "time"})

    def test_cancel_brings_back_a_deck_unticked_here(self):
        d = self.open_dialog({"excluded_decks": [20]})
        self.toggle_deck(d, 10)
        Q.let_save()
        self.assertEqual(current()["excluded_decks"], [10, 20])
        self.cancel(d)
        self.assertEqual(saved(), {"excluded_decks": [20]})

    def test_cancel_keeps_a_deck_left_out_from_its_gear_menu_meanwhile(self):
        d = self.open_dialog({"excluded_decks": [20]})
        self.toggle_deck(d, 10)
        Q.let_save()
        # the gear menu leaves Default out while the dialog is open (actions.py writes the config)
        Q.fake_anki.mw.addonManager.config["excluded_decks"] = [1, 10, 20]
        self.cancel(d)
        self.assertEqual(saved(), {"excluded_decks": [1, 20]})

    def test_cancel_keeps_a_deck_brought_back_from_its_gear_menu_meanwhile(self):
        d = self.open_dialog({"excluded_decks": [1, 20]})
        d.forest.planting.setChecked(False)
        Q.let_save()
        Q.fake_anki.mw.addonManager.config["excluded_decks"] = [20]
        self.cancel(d)
        self.assertEqual(saved(), {"excluded_decks": [20]})

    def test_the_decks_tab_takes_in_a_deck_left_out_from_its_gear_menu_when_you_come_back(self):
        d = self.open_dialog()
        Q.fake_anki.mw.addonManager.config["excluded_decks"] = [20]
        d.isActiveWindow = lambda: True  # (back in the dialog: offscreen, no window is ever active)
        d.changeEvent(Q.QtCore.QEvent(Q.QtCore.QEvent.Type.ActivationChange))
        self.assertEqual(d.decks.items[20].checkState(0), Qt.CheckState.Unchecked)
        self.done()
        self.assertEqual(saved(), {"excluded_decks": [20]})

    def test_cancel_puts_the_phone_back(self):
        d = self.open_dialog()
        d.forest.phone.setChecked(True)
        self.assertEqual(self.phone_calls, [True])
        self.cancel(d)
        self.assertEqual(self.phone_calls, [True, False])
        self.assertFalse(self.phone)

    def test_cancel_with_the_phone_as_it_was_leaves_it_be(self):
        d = self.open_dialog()
        d.forest.phone.setChecked(True)
        d.forest.phone.setChecked(False)
        self.cancel(d)
        self.assertEqual(self.phone_calls, [True, False])

    def test_done_keeps_the_phone(self):
        d = self.open_dialog()
        d.forest.phone.setChecked(True)
        self.done(d)
        self.assertEqual(self.phone_calls, [True])
        self.assertTrue(self.phone)


class RestoreDefaultsTests(QtCase):
    def restore(self, d, confirm: bool = True):
        seen = {}

        def choose(box):
            seen["text"], seen["more"] = box.text(), box.informativeText()
            for b in box.buttons():
                if (box.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole) == confirm:
                    b.click()
                    return
        Q.answer_modal(choose)
        self.button(d, QDialogButtonBox.StandardButton.RestoreDefaults).click()
        Q.settle()
        return seen

    SETTINGS = {"nature": "wild", "environment": "bamboo", "landscape": "river", "landmark": "pagoda", "weather": "rain",
                "time_of_day": "day", "city": "Berlin", "planting_tooltip": False, "calendar_week_start": "monday",
                "calendar_tiles": "round", "excluded_decks": [20], "ignore_before": "2026-09-01", "keep_suspended": False,
                "calendar_record": False, "streak_week": 6, "streak_week_since": "2026-09-10"}

    def test_restore_defaults_asks_first_and_says_what_it_keeps(self):
        d = self.open_dialog(self.SETTINGS)
        seen = self.restore(d, confirm=False)
        self.assertEqual(seen["text"], addon.s_dialog.RESTORE_QUESTION)
        self.assertIn("Keeps: the decks you left out", seen["more"])
        self.assertTrue(d.isVisible())
        self.assertEqual(saved(), self.SETTINGS)

    def test_restore_defaults_resets_the_look_and_keeps_your_study_data(self):
        d = self.open_dialog(self.SETTINGS)
        self.restore(d)
        self.assertFalse(d.isVisible())
        kept = {k: v for k, v in self.SETTINGS.items() if k in addon.s_dialog.DATA_KEYS}
        self.assertEqual(saved(), kept)
        self.assertEqual(len(self.dialogs), 2)  # (opened again, on the defaults)
        again = self.dialog
        self.assertTrue(again.isVisible())
        self.assertEqual(again.forest.nature.currentData(), "peaceful")
        self.assertEqual(again.scenery.preset.currentData(), "golden_lake")
        self.assertEqual(again.decks.excluded, {20})

    def test_restore_defaults_keeps_a_data_change_not_saved_yet(self):
        d = self.open_dialog()
        d.decks.keep_suspended.setChecked(False)
        self.restore(d)
        self.assertEqual(saved(), {"keep_suspended": False})

    def test_cancel_after_restore_defaults_goes_back_to_before_it(self):
        d = self.open_dialog(self.SETTINGS)
        d.forest.phone.setChecked(True)
        self.restore(d)
        self.cancel(self.dialog)
        self.assertEqual(saved(), self.SETTINGS)
        self.assertEqual(self.phone_calls, [True, False])  # (the phone too, as the first dialog found it)

    def test_done_after_restore_defaults_keeps_the_defaults(self):
        d = self.open_dialog(self.SETTINGS)
        self.restore(d)
        self.done(self.dialog)
        self.assertEqual(saved(), {k: v for k, v in self.SETTINGS.items() if k in addon.s_dialog.DATA_KEYS})

    def test_restore_defaults_lets_go_of_the_theme_hook(self):
        d = self.open_dialog()
        self.restore(d)
        self.assertEqual(list.__len__(Q.hooks.theme_did_change), 1)
        self.assertIs(list.__getitem__(Q.hooks.theme_did_change, 0).__self__, self.dialog)


class LastTabTests(QtCase):
    def test_the_dialog_reopens_on_the_tab_it_was_left_on(self):
        for close in ("done", "cancel", "close"):
            with self.subTest(close=close):
                d = self.open_dialog()
                self.tab(d, "Decks")
                getattr(self, close)(d) if close != "close" else d.close()
                Q.settle()
                again = self.open_dialog()
                self.assertEqual(again.tab_key(), "decks")
                self.tab(again, "Scenery")
                self.cancel(again)

    def test_the_first_dialog_opens_on_the_scenery_tab(self):
        self.assertEqual(self.open_dialog().tab_key(), "scenery")

    def test_a_notes_button_opens_its_tab_or_setting(self):
        for focus, tab in (("heatmap", "heatmap"), ("history", "decks"), ("animations", "forest"), ("streak_week", "heatmap"),
                           ("about", "about"), ("nonsense", "scenery")):
            with self.subTest(focus=focus):
                Q.addon.s_dialog._last_tab = ""
                d = self.open_dialog(focus=focus)
                self.assertEqual(d.tab_key(), tab)
                d._reverting = False
                d.done(0)
                Q.settle()

    def test_a_debug_tab_left_on_opens_on_scenery_without_debug(self):
        d = self.open_dialog({"debug": True})
        self.tab(d, "Debug")
        self.cancel(d)
        self.assertEqual(self.open_dialog({"debug": False}).tab_key(), "scenery")


class ThemeHookTests(QtCase):
    def test_opening_registers_on_the_theme_hook_and_closing_removes_it(self):
        for close in ("done", "cancel", "close"):
            with self.subTest(close=close):
                d = self.open_dialog()
                self.assertEqual(Q.hooks.theme_did_change.count(), 1)
                getattr(self, close)(d) if close != "close" else d.close()
                Q.settle()
                self.assertEqual(Q.hooks.theme_did_change.count(), 0)

    def test_closing_an_anki_without_the_theme_hook_is_fine(self):
        # Anki 2.1.45-2.1.49: no theme_did_change
        hook = Q.hooks.theme_did_change
        del Q.hooks.theme_did_change
        self.addCleanup(setattr, Q.hooks, "theme_did_change", hook)
        d = self.open_dialog()
        self.cancel(d)
        self.assertFalse(d.isVisible())

    def test_a_theme_switch_opens_the_dialog_again_in_its_new_colours(self):
        d = self.open_dialog()
        self.tab(d, "Heatmap")
        self.assertFalse(d.heatmap.look.busier_box.isVisible())  # (Busier days: dark mode only)
        self.switch_theme(dark=True)
        self.assertFalse(d.isVisible())
        again = self.dialog
        self.assertIsNot(again, d)
        self.assertTrue(again.isVisible())
        self.assertEqual(again.tab_key(), "heatmap")
        self.assertTrue(again.heatmap.look.busier_box.isVisible())
        self.assertEqual(Q.hooks.theme_did_change.count(), 1)

    def test_a_theme_switch_keeps_a_change_not_saved_yet(self):
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        self.switch_theme()
        self.assertEqual(saved(), {"planting_tooltip": False})
        self.assertFalse(self.dialog.forest.planting.isChecked())

    def test_cancel_after_a_theme_switch_still_goes_back_to_before_the_dialog(self):
        d = self.open_dialog({"nature": "wild"})
        d.forest.planting.setChecked(False)
        d.forest.phone.setChecked(True)
        self.switch_theme()
        self.switch_theme(dark=False)
        self.cancel(self.dialog)
        self.assertEqual(saved(), {"nature": "wild"})
        self.assertEqual(self.phone_calls, [True, False])

    def test_done_after_a_theme_switch_keeps_the_changes(self):
        d = self.open_dialog()
        d.forest.planting.setChecked(False)
        self.switch_theme()
        self.done(self.dialog)
        self.assertEqual(saved(), {"planting_tooltip": False})

    def test_a_theme_switch_leaves_the_other_theme_callbacks_to_run(self):
        self.open_dialog()
        ran = []
        Q.hooks.theme_did_change.append(lambda: ran.append("other add-on"))
        self.switch_theme()
        self.assertEqual(len(self.dialogs), 2)
        self.assertEqual(ran, ["other add-on"])


if __name__ == "__main__":
    unittest.main()

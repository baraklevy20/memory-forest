"""The panel's edges in Anki (panel.py): redraws on every screen and with no collection, the
shortcuts held while a mark is named, a deck screen's setting gone wrong, and the gear menu's
and the phone switch's redraws (actions.py) - in a stand-in Anki."""

from __future__ import annotations

import json
import types
import unittest
from unittest import mock

from fake_anki import Web, addon, mw, reset, tooltips

panel, actions = addon.panel, addon.actions
CARDS = [(1, 10, 5), (2, 20, 3)]


def shortcut(enabled: bool = True):
    s = mock.Mock()
    s.isEnabled.return_value = enabled
    return s


class Screens:
    """The deck list and a deck's screen, each a web view that counts its reloads."""

    def __init__(self):
        self.list, self.deck = Web(), Web()
        mw.deckBrowser = types.SimpleNamespace(web=self.list, refresh=lambda: setattr(self.list, "reloads", self.list.reloads + 1))
        mw.overview = types.SimpleNamespace(web=self.deck, refresh=lambda: setattr(self.deck, "reloads", self.deck.reloads + 1))


class RefreshTests(unittest.TestCase):
    def setUp(self):
        reset(CARDS)
        self.screens = Screens()

    def test_no_collection_yet_draws_nothing(self):
        mw.col = None
        panel.refresh()
        self.assertEqual((self.screens.list.evaluated, self.screens.deck.evaluated), ([], []))
        reset(CARDS)

    def test_the_reviewer_and_other_screens_are_left_alone(self):
        for state in ("review", "resetRequired", "profileManager"):
            mw.state = state
            panel.refresh()
        self.assertEqual((self.screens.list.evaluated, self.screens.deck.evaluated), ([], []))

    def test_a_deck_screen_swaps_its_own_forest(self):
        mw.state = "overview"
        self.screens.deck.url = lambda: types.SimpleNamespace(toString=lambda: "http://127.0.0.1/_anki/legacyPageData?id=3")
        panel.refresh()
        self.assertEqual(len(self.screens.deck.evaluated), 1)
        self.assertIn("r.afSwap(", self.screens.deck.evaluated[0])
        self.assertEqual(self.screens.list.evaluated, [])

    def test_a_swap_the_page_cannot_take_reloads_the_screen(self):
        self.screens.list.evalWithCallback = lambda js, cb: (self.screens.list.evaluated.append(js), cb(False))
        panel.refresh()
        self.assertEqual(self.screens.list.reloads, 1)

    def test_a_forest_that_fails_to_build_is_logged_and_the_page_kept(self):
        with mock.patch.object(panel, "payload", side_effect=RuntimeError("bad data")), mock.patch.object(panel, "log") as logged:
            panel.refresh()
        logged.assert_called_once()
        self.assertEqual((self.screens.list.evaluated, self.screens.list.reloads), ([], 0))

    def test_the_deck_list_with_nothing_on_it_reloads_only_while_the_forest_is_still_there(self):
        reset(CARDS, {"main_forest": False, "calendar_main": False})
        gone = Web()
        gone.evalWithCallback = lambda js, cb: (gone.evaluated.append(js), cb(False))
        mw.deckBrowser = types.SimpleNamespace(web=gone, refresh=lambda: setattr(gone, "reloads", gone.reloads + 1))
        panel.refresh()
        self.assertEqual((len(gone.evaluated), gone.reloads), (1, 0))

    def test_a_redraw_lets_go_of_the_shortcuts(self):
        s = shortcut()
        with mock.patch.object(mw, "findChildren", create=True, return_value=[s]):
            panel.hold_shortcuts(True)
        panel.refresh()
        s.setEnabled.assert_called_with(True)

    def test_the_swap_carries_the_data_and_the_scripts_without_the_boot_script(self):
        panel.refresh()
        js = self.screens.list.evaluated[0]
        _root, data, srcs = panel._panel_parts()
        self.assertIn(json.dumps(srcs), js)
        self.assertFalse(any(panel.BOOT in s for s in srcs))
        self.assertIn(data, js)


class DeckScreenSettingTests(unittest.TestCase):
    def test_an_unknown_deck_screen_setting_shows_no_forest_but_still_the_calendar(self):
        reset(CARDS, {"deck_forest_mode": "giant"})
        with mock.patch.object(panel, "log") as logged:
            shows = panel._deck_panel(mw.col.decks.current())
        logged.assert_called_once()
        self.assertEqual(shows, (10, True, False))
        reset(CARDS, {"deck_forest_mode": "giant", "calendar_decks": False})
        with mock.patch.object(panel, "log"):
            self.assertIsNone(panel._deck_panel(mw.col.decks.current()))

    def test_a_deck_s_screen_that_fails_to_build_is_left_as_anki_made_it(self):
        reset(CARDS)
        content = types.SimpleNamespace(table="<t>")
        with mock.patch.object(mw.col.decks, "current", side_effect=RuntimeError("no deck")), mock.patch.object(panel, "log") as logged:
            panel.on_overview(None, content)
        self.assertEqual(content.table, "<t>")
        logged.assert_called_once()

    def test_a_finished_deck_s_page_with_no_collection_gets_nothing(self):
        reset(CARDS)
        web = Web()
        web.eval = web.evaluated.append
        mw.overview = types.SimpleNamespace(web=web)
        mw.state, mw.col = "overview", None
        panel.on_page_loaded(web)
        self.assertEqual(web.evaluated, [])
        reset(CARDS)

    def test_a_page_whose_address_cannot_be_read_is_not_a_finished_deck(self):
        web = Web()
        web.url = mock.Mock(side_effect=RuntimeError("deleted"))
        self.assertFalse(panel._on_congrats(web))


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        reset()
        panel.hold_shortcuts(False)

    def test_only_the_shortcuts_that_were_on_are_turned_back_on(self):
        on, off = shortcut(True), shortcut(False)
        with mock.patch.object(mw, "findChildren", create=True, return_value=[on, off]):
            panel.hold_shortcuts(True)
            panel.hold_shortcuts(False)
        on.setEnabled.assert_has_calls([mock.call(False), mock.call(True)])
        off.setEnabled.assert_not_called()

    def test_holding_twice_keeps_the_first_list(self):
        s = shortcut()
        with mock.patch.object(mw, "findChildren", create=True, return_value=[s]) as found:
            panel.hold_shortcuts(True)
            s.isEnabled.return_value = False  # (now held off by us)
            panel.hold_shortcuts(True)
            panel.hold_shortcuts(False)
        found.assert_called_once()
        s.setEnabled.assert_called_with(True)

    def test_a_shortcut_qt_has_deleted_since_is_skipped(self):
        gone, kept = shortcut(), shortcut()
        with mock.patch.object(mw, "findChildren", create=True, return_value=[gone, kept]):
            panel.hold_shortcuts(True)
        gone.setEnabled.side_effect = RuntimeError("wrapped C/C++ object has been deleted")
        panel.hold_shortcuts(False)
        kept.setEnabled.assert_called_with(True)
        self.assertEqual(panel._held, [])

    def test_letting_go_with_nothing_held_does_nothing(self):
        with mock.patch.object(mw, "findChildren", create=True) as found:
            panel.release_shortcuts()
            panel.release_shortcuts("review", "overview")
        found.assert_not_called()


class Menu:
    def __init__(self):
        self.actions = []

    def addAction(self, text):
        action = mock.Mock()
        action.text = text
        self.actions.append(action)
        return action


class GearMenuTests(unittest.TestCase):
    def setUp(self):
        reset(CARDS)

    def test_leaving_a_deck_out_redraws_the_forest_and_says_so(self):
        menu = Menu()
        with mock.patch.object(actions, "refresh") as redraw:
            actions.on_deck_options_menu(menu, 20)
            menu.actions[0].triggered.connect.call_args.args[0]()
        redraw.assert_called_once_with()
        self.assertEqual(tooltips, [actions.LEFT_OUT])
        self.assertEqual(mw.addonManager.config["excluded_decks"], [20])

    def test_a_deck_that_is_gone_gets_nothing(self):
        menu = Menu()
        actions.on_deck_options_menu(menu, 999)
        self.assertEqual(menu.actions, [])

    def test_a_hand_edited_list_of_left_out_decks_still_works(self):
        reset(CARDS, {"excluded_decks": ["10", "junk", None, -5]})
        menu = Menu()
        actions.on_deck_options_menu(menu, 10)
        self.assertEqual(menu.actions[0].text, "Bring back into Memory Forest")
        with mock.patch.object(actions, "refresh"):
            menu.actions[0].triggered.connect.call_args.args[0]()
        self.assertEqual(mw.addonManager.config["excluded_decks"], [-5])

    def test_a_failing_menu_is_logged_not_raised(self):
        with mock.patch.object(mw.col.decks, "get", side_effect=RuntimeError("closed")), mock.patch.object(actions, "log") as logged:
            actions.on_deck_options_menu(Menu(), 10)
        logged.assert_called_once()


class PhoneSwitchTests(unittest.TestCase):
    def setUp(self):
        reset(CARDS)

    def test_the_phone_s_deck_coming_on_a_deck_screen_only_swaps_the_forest(self):
        mw.state = "overview"
        with mock.patch.object(actions, "switch", return_value=True), mock.patch.object(actions, "refresh") as redraw:
            actions.phone_switched(True)
        redraw.assert_called_once_with()

    def test_no_collection_only_swaps(self):
        mw.col = None
        with mock.patch.object(actions, "switch", return_value=True), mock.patch.object(actions, "refresh") as redraw:
            actions.phone_switched(True)
        redraw.assert_called_once_with()
        reset(CARDS)

    def test_the_settings_are_opened_with_their_callbacks_and_a_tab(self):
        with mock.patch.object(actions, "open_dialog") as opened:
            actions.open_settings("heatmap")
        opened.assert_called_once_with(addon.state.MODULE, actions.settings_changed, actions.phone_switched, "heatmap")


if __name__ == "__main__":
    unittest.main()

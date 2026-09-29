"""Clicks on the forest and the deck list's gear menu (actions.py), in a stand-in Anki."""

from __future__ import annotations

import unittest
from unittest import mock

from fake_anki import addon, browser, mw, reset

actions = addon.actions


class Menu:
    def __init__(self):
        self.actions = []

    def addAction(self, text):
        action = mock.Mock()
        action.text = text
        self.actions.append(action)
        return action


class ActionTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_tree_opens_the_browser_on_its_day(self):
        actions.browse_day(5)
        self.assertEqual(browser.searches, ["introduced:6 -introduced:5"])

    def test_on_a_deck_screen_only_that_decks_cards(self):
        actions.browse_day(5, 10)
        self.assertEqual(browser.searches, ['"deck:French" introduced:6 -introduced:5'])

    def test_the_deep_forest_spans_its_days_and_leaves_out_left_out_decks(self):
        reset(config={"excluded_decks": [20], "keep_suspended": False})
        actions.browse_day(400, None, 30)
        self.assertEqual(browser.searches, ['introduced:401 -is:suspended -introduced:30 -"deck:German"'])

    def test_only_this_add_ons_messages_are_answered(self):
        context = actions.DeckBrowser()
        self.assertEqual(actions.on_js_message((False, None), "someone_else:browse:5", context), (False, None))
        self.assertEqual(actions.on_js_message((False, None), f"{addon.state.MODULE}:browse:5", object()), (False, None))
        self.assertEqual(actions.on_js_message((False, None), f"{addon.state.MODULE}:browse:5::", context), (True, None))
        self.assertEqual(browser.searches, ["introduced:6 -introduced:5"])
        with mock.patch.object(actions, "open_settings") as opened:
            actions.on_js_message((False, None), f"{addon.state.MODULE}:settings", context)
            opened.assert_called_once()

    def test_the_gear_menu_leaves_a_deck_out_and_brings_it_back(self):
        menu = Menu()
        with mock.patch.object(actions, "refresh"):
            actions.on_deck_options_menu(menu, 10)
            self.assertEqual(menu.actions[0].text, "Leave out of Memory Forest")
            menu.actions[0].triggered.connect.call_args[0][0]()
            self.assertEqual(mw.addonManager.config["excluded_decks"], [10])
            menu = Menu()
            actions.on_deck_options_menu(menu, 11)  # its subdeck goes with it
            self.assertEqual(menu.actions[0].text, "Left out of Memory Forest with its parent deck")
            menu = Menu()
            actions.on_deck_options_menu(menu, 10)
            self.assertEqual(menu.actions[0].text, "Bring back into Memory Forest")
            menu.actions[0].triggered.connect.call_args[0][0]()
            self.assertNotIn("excluded_decks", mw.addonManager.config)
        menu = Menu()
        actions.on_deck_options_menu(menu, 30)  # a filtered deck has no forest to leave
        self.assertEqual(menu.actions, [])


if __name__ == "__main__":
    unittest.main()

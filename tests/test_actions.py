"""Clicks on the forest and the deck list's gear menu (actions.py), in a stand-in Anki."""

from __future__ import annotations

import unittest
from unittest import mock

from fake_anki import addon, browser, hooks, mw, reset, tooltips

actions = addon.actions
# the phone's note plants no tree, so the browser leaves it out like the tooltip does
NOT_PHONE = f'-"note:{addon.phone_note.PHONE_NOTETYPE}"'


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

    def test_shortcuts_held_while_a_mark_is_named_come_back_when_its_page_goes(self):
        shortcut = mock.Mock()
        shortcut.isEnabled.return_value = True
        with mock.patch.object(mw, "findChildren", create=True, return_value=[shortcut]):
            addon.panel.hold_shortcuts(True)
        shortcut.setEnabled.assert_called_with(False)
        for hook in (hooks.deck_browser_will_render_content, hooks.overview_will_render_content, hooks.state_did_change):
            self.assertIn(addon.panel.release_shortcuts, hook)
        addon.panel.release_shortcuts("deckBrowser", "review")  # (as state_did_change calls it)
        shortcut.setEnabled.assert_called_with(True)

    def test_a_tree_opens_the_browser_on_its_day(self):
        actions.browse_day(5)
        self.assertEqual(browser.searches, [f"introduced:6 -introduced:5 {NOT_PHONE}"])

    def test_answer_time_sort_is_slowest_first_and_only_for_the_opening_search(self):
        import types

        hook = []
        context = types.SimpleNamespace(browser=browser, ids=[1, 2, 3, 4])
        def search(_text):
            for callback in hook:
                callback(context)
        with mock.patch.object(actions.gui_hooks, "browser_did_search", hook, create=True), \
                mock.patch.object(mw.col, "find_cards", return_value=[1, 2, 3, 4], create=True), \
                mock.patch.object(browser, "table", mock.Mock(), create=True), \
                mock.patch.object(browser, "search_for", side_effect=search):
            browser.table.is_notes_mode.return_value = False
            actions._open_browser(["rated:1"], answer_times={1: 2000, 2: 9000, 3: 4000})
            self.assertEqual(context.ids, [2, 3, 1, 4])
            self.assertEqual(hook, [])
            browser.table.is_notes_mode.return_value = True
            context.ids = [100, 200, 300]
            with mock.patch.object(mw.col.db, "all", return_value=[(1, 100), (2, 100), (3, 200)]):
                actions._open_browser(["rated:1"], answer_times={1: 2000, 2: 9000, 3: 4000})
            self.assertEqual(context.ids, [100, 200, 300])
            self.assertEqual(hook, [])
            with mock.patch.object(browser, "search_for", side_effect=RuntimeError), self.assertRaises(RuntimeError):
                actions._open_browser(["rated:1"], answer_times={})
            self.assertEqual(hook, [])

    def test_metric_values_are_filtered_before_notes_are_aggregated(self):
        with mock.patch.object(mw.col, "find_cards", return_value=[1], create=True) as find, \
                mock.patch.object(actions.answer_column, "show") as show, \
                mock.patch.object(actions.gui_hooks, "browser_did_search", [], create=True):
            actions._open_browser(["rated:1"], 10, {1: 2, 2: 30}, "Attempts", "reviews")
            self.assertEqual(show.call_args.args[1], {1: 2})
            self.assertIn('"deck:French"', find.call_args.args[0])

    def test_review_and_time_clicks_choose_daily_metric_and_second_column(self):
        for mode, title in (("reviews", "Attempts"), ("time", "Total time"), ("median", "Answer time")):
            with mock.patch.object(actions.study_log, "day_card_totals", return_value={1: 42}) as totals, \
                    mock.patch.object(actions.study_log, "day_answer_times", return_value={1: 42}), \
                    mock.patch.object(actions, "_open_browser") as opened:
                actions.browse_calendar_day(-2, 10, answer_mode=mode)
                args = opened.call_args.args
                self.assertEqual(args[1:3], (10, {1: 42}))
                self.assertTrue(args[3].startswith(title + " ("))
                self.assertEqual(args[4], mode)
                if mode != "median":
                    self.assertEqual(totals.call_args.args[-1], mode)
        with mock.patch.object(actions.study_log, "day_card_totals") as totals, \
                mock.patch.object(actions, "_open_browser") as opened:
            actions.browse_calendar_day(0, due=True, answer_mode="time")
            totals.assert_not_called()
            self.assertIsNone(opened.call_args.args[2])

    def test_metric_modes_are_forwarded_from_heatmap_clicks(self):
        for mode in ("reviews", "time", "median"):
            with mock.patch.object(actions, "browse_calendar_day") as browse:
                actions.on_js_message((False, None), f"{addon.state.MODULE}:day:-2:10:{mode}", actions.DeckBrowser())
                browse.assert_called_once_with(-2, 10, False, mode)

    def test_on_a_deck_screen_only_that_decks_cards(self):
        actions.browse_day(5, 10)
        self.assertEqual(browser.searches, [f'"deck:French" introduced:6 -introduced:5 {NOT_PHONE}'])

    def test_the_deep_forest_spans_its_days_and_leaves_out_left_out_decks(self):
        reset(config={"excluded_decks": [20], "keep_suspended": False})
        actions.browse_day(400, None, 30)
        self.assertEqual(browser.searches, [f'introduced:401 -is:suspended -introduced:30 -"deck:German" {NOT_PHONE}'])

    def test_only_this_add_ons_messages_are_answered(self):
        context = actions.DeckBrowser()
        self.assertEqual(actions.on_js_message((False, None), "someone_else:browse:5", context), (False, None))
        self.assertEqual(actions.on_js_message((False, None), f"{addon.state.MODULE}:browse:5", object()), (False, None))
        self.assertEqual(actions.on_js_message((False, None), f"{addon.state.MODULE}:browse:5::", context), (True, None))
        self.assertEqual(browser.searches, [f"introduced:6 -introduced:5 {NOT_PHONE}"])
        with mock.patch.object(actions, "open_settings") as opened:
            actions.on_js_message((False, None), f"{addon.state.MODULE}:settings", context)
            opened.assert_called_once()

    def test_the_deck_list_reloads_when_the_phone_s_deck_comes_or_goes(self):
        deck_list = mock.Mock()
        with mock.patch.object(mw, "deckBrowser", deck_list, create=True), mock.patch.object(actions, "refresh") as redraw:
            with mock.patch.object(actions, "switch", return_value=True) as switch:
                actions.phone_switched(False)
            switch.assert_called_once_with(False)
            deck_list.refresh.assert_called_once()
            redraw.assert_not_called()
            with mock.patch.object(actions, "switch", return_value=False):
                actions.phone_switched(True)  # it was on already: only the forest is swapped
            redraw.assert_called_once()
            deck_list.refresh.assert_called_once()

    def test_any_setting_brings_the_phone_s_forest_up_to_date(self):
        with mock.patch.object(actions, "refresh") as redraw, mock.patch.object(actions, "publish_for_phone") as publish:
            actions.settings_changed()
        publish.assert_called_once()
        redraw.assert_called_once()

    def test_the_gear_menu_leaves_a_deck_out_and_brings_it_back(self):
        menu = Menu()
        with mock.patch.object(actions, "refresh"):
            actions.on_deck_options_menu(menu, 10)
            self.assertEqual(menu.actions[0].text, "Leave out of Memory Forest")
            menu.actions[0].triggered.connect.call_args[0][0]()
            self.assertEqual(mw.addonManager.config["excluded_decks"], [10])
            self.assertEqual(tooltips, [actions.LEFT_OUT])
            menu = Menu()
            actions.on_deck_options_menu(menu, 11)  # its subdeck goes with it
            self.assertEqual(menu.actions[0].text, "Left out of Memory Forest with its parent deck")
            menu = Menu()
            actions.on_deck_options_menu(menu, 10)
            self.assertEqual(menu.actions[0].text, "Bring back into Memory Forest")
            menu.actions[0].triggered.connect.call_args[0][0]()
            self.assertNotIn("excluded_decks", mw.addonManager.config)
            self.assertEqual(tooltips[-1], actions.BROUGHT_BACK)
        menu = Menu()
        actions.on_deck_options_menu(menu, 30)  # a filtered deck has no forest to leave
        self.assertEqual(menu.actions, [])


    def test_the_phone_s_deck_has_nothing_in_its_gear_menu(self):
        menu = Menu()
        with mock.patch.object(actions, "phone_decks", return_value={20}):
            actions.on_deck_options_menu(menu, 20)
        self.assertEqual(menu.actions, [])


if __name__ == "__main__":
    unittest.main()

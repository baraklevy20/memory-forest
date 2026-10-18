"""How the add-on plugs into Anki (__init__.py): every hook it goes on, in which order, what each
one does once Anki calls it, and what it hands the add-on manager - in a stand-in Anki whose
hooks behave as Anki's do (append, remove, called; never iterable)."""

from __future__ import annotations

import os
import re
import types
import unittest
from unittest import mock

import fake_anki
from fake_anki import PACKAGE, Web, addon, hooks, mw, reset, tooltips

import catalog

panel, actions, payload, planting = addon.panel, addon.actions, addon.payload, addon.planting
events_state, phone = addon.events_state, addon.phone
CARDS = [(1, 10, 5), (2, 20, 3)]
# what the add-on handed live_weather as it loaded (read now: a test may swap in its own since)
REDRAW_AT_LOAD = addon.live_weather._redraw


class NoModels:
    """col.models of a collection that never had the phone's note type."""

    def all_names_and_ids(self):
        return []

    def by_name(self, _name):
        return None


def ours(hook) -> list:
    """The callbacks this copy of the add-on put on `hook`, in the order Anki calls them (the
    hook may also hold other copies', loaded by other tests)."""
    return [cb for cb in list.__iter__(hook) if (getattr(cb, "__module__", "") or "").startswith(PACKAGE)]


class FakeHooksBehaveLikeAnkisTests(unittest.TestCase):
    """What the tests take for granted about Anki's hooks (aqt/hooks_gen.py, the same since
    2.1.45): if the stand-in lets more through than Anki does, a crash only shows in Anki."""

    def test_a_hook_cannot_be_searched_and_a_missing_callback_is_removed_quietly(self):
        hook = fake_anki._Hook()
        hook.append(print)
        with self.assertRaises(TypeError):
            print in hook  # noqa: B015 - what crashed the settings' Cancel
        hook.remove(len)  # never there: nothing happens, as in Anki
        hook.remove(print)
        self.assertEqual(hook.count(), 0)
        self.assertTrue(hook)  # (an empty one too: Anki's have no length)

    def test_a_callback_that_raises_is_taken_off_and_the_error_goes_on(self):
        hook, ran = fake_anki._Hook(), []

        def bad(*_a):
            raise ValueError("boom")
        hook.append(bad)
        hook.append(lambda *a: ran.append(a))
        with self.assertRaises(ValueError):
            hook(1)
        self.assertEqual(ran, [])  # the ones after it never ran this time
        hook(2)
        self.assertEqual(ran, [(2,)])
        self.assertEqual(hook.count(), 1)

    def test_a_filter_hook_hands_each_callback_the_last_answer(self):
        hook = hooks.webview_did_receive_js_message
        self.assertIsInstance(hook, fake_anki._FilterHook)
        self.assertEqual(hook((False, None), "nobody's:message", object()), (False, None))


class RegistrationTests(unittest.TestCase):
    """Each hook the add-on goes on as it loads, exactly once and in order."""

    def test_every_hook_has_exactly_the_add_ons_callbacks_in_order(self):
        expected = {
            "deck_browser_will_render_content": [panel.release_shortcuts, panel.on_deck_browser],
            "overview_will_render_content": [panel.release_shortcuts, panel.on_overview],
            "state_did_change": [panel.release_shortcuts],
            "webview_did_inject_style_into_page": [panel.on_page_loaded],
            "reviewer_did_answer_card": [planting.on_answer],
            "webview_did_receive_js_message": [actions.on_js_message],
            "deck_browser_will_show_options_menu": [actions.on_deck_options_menu],
            # the strike waits for a sync first, the phone's forest goes by what it settled
            "sync_will_start": [events_state.sync_started, phone.publish],
            # the caches cleared before the phone's forest is written from them
            "sync_did_finish": [events_state.sync_finished, payload.after_sync, phone.after_sync],
            "collection_did_load": [payload.collection_loaded],
            # (only an open settings dialog goes on these)
            "theme_did_change": [],
            "browser_did_search": [], "browser_did_fetch_row": [], "browser_will_search": [],
        }
        for name, callbacks in expected.items():
            self.assertEqual(ours(getattr(hooks, name)), callbacks, name)

    def test_the_release_shortcuts_go_first_so_a_failing_panel_cannot_keep_them_held(self):
        for hook in (hooks.deck_browser_will_render_content, hooks.overview_will_render_content):
            self.assertIs(ours(hook)[0], panel.release_shortcuts)

    def test_the_config_button_opens_the_settings_and_an_edited_config_redraws(self):
        self.assertIs(mw.addonManager.config_actions[PACKAGE], actions.open_settings)
        with mock.patch.object(actions, "publish_for_phone") as publish, mock.patch.object(actions, "refresh") as redraw:
            mw.addonManager.config_updated_actions[PACKAGE]({"anything": 1})
        publish.assert_called_once_with()
        redraw.assert_called_once_with()

    def test_the_page_may_fetch_every_script_and_style_it_loads_and_nothing_else(self):
        pattern = re.compile(mw.addonManager.web_exports[PACKAGE])
        reset(CARDS)
        html = panel._panel_html()
        loaded = re.findall(r'(?:src|href)="/_addons/[^/]+/([^"?]+)', html)
        self.assertGreater(len(loaded), len(catalog.SCRIPTS))
        for rel in loaded:
            self.assertTrue(pattern.fullmatch(rel), rel)
            self.assertTrue(os.path.exists(os.path.join(fake_anki.ADDON_DIR, rel)), rel)
        # every script and style in web/ can be served (a scenery's own file included) ...
        web = os.path.join(fake_anki.ADDON_DIR, "web")
        for root, _dirs, names in os.walk(web):
            for n in names:
                rel = os.path.relpath(os.path.join(root, n), fake_anki.ADDON_DIR).replace(os.sep, "/")
                if n.endswith((".js", ".css")):
                    self.assertTrue(pattern.fullmatch(rel), rel)
        # ... and never the add-on's Python, its config or what it keeps about you
        for rel in ("__init__.py", "config.json", "meta.json", "user_files/state.json", "web/envs/natural.json"):
            self.assertIsNone(pattern.fullmatch(rel), rel)

    def test_new_weather_redraws_the_forest(self):
        self.assertIs(REDRAW_AT_LOAD, panel.refresh)

    def test_the_add_on_finds_its_own_folder_name(self):
        # its web files are served under it, and two copies (base and Plus) each draw their own
        self.assertEqual(addon.state.MODULE, PACKAGE)
        self.assertEqual(panel.WEB, f"/_addons/{PACKAGE}/web")
        self.assertIn(PACKAGE, panel.ROOT)


class HooksCalledTests(unittest.TestCase):
    """The hooks called the way Anki calls them, with what Anki passes."""

    def setUp(self):
        reset(CARDS)
        mw.col.models = NoModels()

    def test_the_deck_list_s_render_hook_puts_the_panel_above_its_stats(self):
        content = types.SimpleNamespace(tree="<table></table>", stats="<p>stats</p>")
        hooks.deck_browser_will_render_content(object(), content)
        self.assertIn(f'id="{panel.ROOT}"', content.stats)
        self.assertTrue(content.stats.endswith("<p>stats</p>"))
        self.assertEqual(content.tree, "<table></table>")

    def test_a_deck_screen_s_render_hook_adds_the_panel_under_its_table(self):
        content = types.SimpleNamespace(table="<table></table>")
        hooks.overview_will_render_content(object(), content)
        self.assertTrue(content.table.startswith("<table></table>"))
        self.assertIn(f'id="{panel.ROOT}"', content.table)

    def test_a_panel_that_fails_to_build_leaves_the_page_as_anki_made_it(self):
        logged = []
        with mock.patch.object(panel, "payload", side_effect=RuntimeError("no forest")), \
                mock.patch.object(panel, "log", logged.append):
            content = types.SimpleNamespace(stats="<p>stats</p>", table="<t>")
            hooks.deck_browser_will_render_content(object(), content)
            hooks.overview_will_render_content(object(), content)
        self.assertEqual((content.stats, content.table), ("<p>stats</p>", "<t>"))
        self.assertEqual(len(logged), 2)
        # and the hook kept its callbacks: one that raised would have been taken off for good
        self.assertIn(panel.on_deck_browser, ours(hooks.deck_browser_will_render_content))
        self.assertIn(panel.on_overview, ours(hooks.overview_will_render_content))

    def test_a_change_of_screen_lets_go_of_the_held_shortcuts(self):
        shortcut = mock.Mock()
        shortcut.isEnabled.return_value = True
        with mock.patch.object(mw, "findChildren", create=True, return_value=[shortcut]):
            panel.hold_shortcuts(True)
        hooks.state_did_change("review", "deckBrowser")
        shortcut.setEnabled.assert_called_with(True)

    def test_the_first_new_card_of_the_day_plants_through_the_answer_hook(self):
        reset([(1, 10, 0)])  # its first review just now
        hooks.reviewer_did_answer_card(object(), types.SimpleNamespace(id=1, did=10, odid=0), 3)
        self.assertEqual(len(tooltips), 1)
        hooks.reviewer_did_answer_card(object(), types.SimpleNamespace(id=1, did=10, odid=0), 3)
        self.assertEqual(len(tooltips), 1)  # once a day

    def test_a_failing_planting_check_never_breaks_answering(self):
        reset([(1, 10, 0)])
        with mock.patch.object(planting, "log") as logged, \
                mock.patch.object(mw.col.db, "scalar", side_effect=RuntimeError("locked")):
            hooks.reviewer_did_answer_card(object(), types.SimpleNamespace(id=1, did=10, odid=0), 3)
        logged.assert_called_once()
        self.assertIn(planting.on_answer, ours(hooks.reviewer_did_answer_card))

    def test_the_planting_message_can_be_switched_off(self):
        reset([(1, 10, 0)], {"planting_tooltip": False})
        hooks.reviewer_did_answer_card(object(), types.SimpleNamespace(id=1, did=10, odid=0), 3)
        self.assertEqual(tooltips, [])

    def test_a_message_from_the_add_on_s_page_is_answered_and_others_passed_on(self):
        context = actions.DeckBrowser()
        self.assertEqual(hooks.webview_did_receive_js_message((False, None), "someone:else", context), (False, None))
        with mock.patch.object(actions, "open_settings") as opened:
            self.assertEqual(hooks.webview_did_receive_js_message((False, None), f"{PACKAGE}:settings", context), (True, None))
        opened.assert_called_once_with()

    def test_a_sync_holds_back_the_strike_until_it_has_finished(self):
        events_state._syncing = False
        events_state._synced.discard(events_state._profile())
        with mock.patch.object(phone, "steps_aside", return_value=False):
            hooks.sync_will_start()
            self.assertTrue(events_state._syncing)
            self.assertFalse(events_state.settled())
            payload._forest_cache["x"] = "kept"
            hooks.sync_did_finish()
        self.assertFalse(events_state._syncing)
        self.assertIn(events_state._profile(), events_state._synced)
        self.assertTrue(events_state.settled())
        self.assertNotIn("x", payload._forest_cache)  # read afresh: the sync may have brought old reviews

    def test_the_phone_s_forest_is_written_before_and_after_each_sync(self):
        with mock.patch.object(phone, "phone_on", return_value=True) as on, \
                mock.patch.object(phone, "_note", side_effect=RuntimeError("stop here")), \
                mock.patch.object(phone, "steps_aside", return_value=False), \
                mock.patch.object(phone, "log") as logged:
            hooks.sync_will_start()
            hooks.sync_did_finish()
        self.assertEqual(on.call_count, 2)
        self.assertEqual(logged.call_count, 2)  # (a failure is only logged: a sync must never stop for it)

    def test_a_collection_opened_in_place_of_another_forgets_the_old_one(self):
        payload._forest_cache["x"] = "kept"
        payload._logs["x"] = "kept"
        hooks.collection_did_load(mw.col)
        self.assertEqual((payload._forest_cache, payload._logs), ({}, {}))

    def test_a_page_of_another_window_loading_is_left_alone(self):
        mw.overview = types.SimpleNamespace(web=Web())
        other = Web()
        hooks.webview_did_inject_style_into_page(other)
        self.assertEqual(other.evaluated, [])

    def test_the_gear_menu_hook_offers_leaving_the_deck_out(self):
        menu = mock.Mock()
        hooks.deck_browser_will_show_options_menu(menu, 10)
        menu.addAction.assert_called_once_with("Leave out of Memory Forest")


if __name__ == "__main__":
    unittest.main()

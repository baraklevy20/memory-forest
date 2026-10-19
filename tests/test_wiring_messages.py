"""Every message the forest's page sends back to Anki (pycmd, actions.on_js_message), written the
way the page's scripts write them (web/core.js, caption.js, hover.js, calendar.js, news.js,
visit.js, events/asteroid.js), and what each one does - in a stand-in Anki."""

from __future__ import annotations

import os
import unittest
from unittest import mock

import fake_anki
from fake_anki import PACKAGE, addon, browser, hooks, mw, reset

actions, marks, news, events_state, payload = addon.actions, addon.marks, addon.news, addon.events_state, addon.payload
NOT_PHONE = f'-"note:{addon.phone_note.PHONE_NOTETYPE}"'


def send(message: str, context=None):
    """The page's pycmd(message), as Anki hands it on: through the hook, from the deck list."""
    return hooks.webview_did_receive_js_message((False, None), message, actions.DeckBrowser() if context is None else context)


def msg(*parts) -> str:
    return ":".join([PACKAGE, *map(str, parts)])


class MessageTests(unittest.TestCase):
    def setUp(self):
        reset([(1, 10, 5), (2, 20, 3)])
        self.logged = []
        patcher = mock.patch.object(actions, "log", self.logged.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    # where a message may come from

    def test_a_deck_s_own_screen_is_answered_too(self):
        self.assertEqual(send(msg("browse", 5, ""), actions.Overview()), (True, None))
        self.assertEqual(browser.searches, [f"introduced:6 -introduced:5 {NOT_PHONE}"])

    def test_the_reviewer_and_other_pages_are_never_answered(self):
        for context in (None, object(), "review"):
            self.assertEqual(hooks.webview_did_receive_js_message((False, None), msg("settings"), context), (False, None))

    def test_a_message_answered_by_another_add_on_first_stays_answered(self):
        self.assertEqual(hooks.webview_did_receive_js_message((True, "theirs"), "other:x", actions.DeckBrowser()), (True, "theirs"))

    def test_a_message_that_is_not_text_is_passed_on(self):
        self.assertEqual(hooks.webview_did_receive_js_message((False, None), {"cmd": 1}, actions.DeckBrowser()), (False, None))

    def test_another_copy_s_messages_are_left_to_it(self):
        # the base edition and Plus side by side: each answers only its own channel
        self.assertEqual(send(f"{PACKAGE}_plus:settings"), (False, None))
        self.assertEqual(send(f"x{PACKAGE}:settings"), (False, None))

    def test_the_page_s_channel_is_the_one_answered(self):
        self.assertEqual(payload.payload()["channel"], PACKAGE)

    # what each one does

    def test_the_cog_opens_the_settings(self):
        with mock.patch.object(actions, "open_dialog") as opened:
            self.assertEqual(send(msg("settings")), (True, None))
        self.assertEqual(opened.call_args.args[0], PACKAGE)
        self.assertEqual(opened.call_args.args[3], "")  # (no tab asked for: the one it was left on)

    def test_a_tree_and_the_deep_forest_open_the_browser_on_their_cards(self):
        send(msg("browse", 5, ""))  # hover.js: a tree of the main forest
        send(msg("browse", 5, 10))  # one lit on a deck's screen
        send(msg("browse", 400, "", 30))  # caption.js / hover.js: the deep forest, from its oldest day to its newest
        self.assertEqual(browser.searches, [
            f"introduced:6 -introduced:5 {NOT_PHONE}",
            f'"deck:French" introduced:6 -introduced:5 {NOT_PHONE}',
            f"introduced:401 -introduced:30 {NOT_PHONE}",
        ])

    def test_a_calendar_day_click_opens_the_browser_on_that_day(self):
        with mock.patch.object(actions, "browse_calendar_day") as browse:
            send(msg("day", -3, "", "reviews"))  # calendar.js: a past day, the main heatmap, shaded by reviews
            send(msg("day", 2, 10, "due"))  # a day ahead, on a deck's screen
            send(msg("day", 0, "", "due"))  # today before studying: what is due
        self.assertEqual([c.args for c in browse.call_args_list],
                         [(-3, None, False, "reviews"), (2, 10, True, "due"), (0, None, True, "due")])

    def test_a_past_day_opens_the_browser_on_its_reviews(self):
        send(msg("day", -3))
        self.assertEqual(browser.searches, [f"prop:rated=-3 {NOT_PHONE}"])
        browser.searches.clear()
        send(msg("day", 0))
        self.assertEqual(browser.searches, [f"rated:1 {NOT_PHONE}"])

    def test_a_day_of_a_deck_left_out_keeps_to_the_forest_s_decks(self):
        reset(config={"excluded_decks": [20]})
        send(msg("day", -1, 10))
        self.assertEqual(browser.searches, [f'"deck:French" prop:rated=-1 -"deck:German" {NOT_PHONE}'])

    def test_a_deck_that_is_gone_opens_the_whole_collection_s_day(self):
        send(msg("day", -1, 999))  # (deleted since the page was drawn)
        self.assertEqual(browser.searches, [f"prop:rated=-1 {NOT_PHONE}"])

    def test_a_mark_is_kept_in_the_collection_with_its_icon_and_name(self):
        self.assertEqual(send(msg("mark", "2026-09-01", "exam", "Finals: part 1")), (True, None))
        self.assertEqual(marks.important_days(mw.col), [{"day": "2026-09-01", "icon": "exam", "name": "Finals: part 1"}])
        send(msg("mark", "2026-09-01", "trip", ""))  # its icon changed, its name taken away
        self.assertEqual(marks.important_days(mw.col), [{"day": "2026-09-01", "icon": "trip", "name": ""}])
        send(msg("unmark", "2026-09-01"))
        self.assertEqual(marks.important_days(mw.col), [])
        self.assertEqual(self.logged, [])

    def test_a_mark_on_something_that_is_not_a_day_is_refused_without_a_crash(self):
        self.assertEqual(send(msg("mark", "tomorrow", "pin", "x")), (True, None))
        self.assertEqual(marks.important_days(mw.col), [])
        self.assertEqual(len(self.logged), 1)

    def test_the_heatmap_s_toggles_are_saved_as_settings(self):
        send(msg("shade", "time"))
        send(msg("view", "by_year"))
        cfg = addon.state.config()
        self.assertEqual((cfg["calendar_shade"], cfg["calendar"]), ("time", "by_year"))

    def test_a_toggle_to_something_unknown_changes_nothing(self):
        send(msg("shade", "colour"))
        send(msg("view", "spiral"))
        send(msg("shade"))
        self.assertEqual(mw.addonManager.config, {})

    def test_typing_a_mark_s_name_holds_anki_s_one_key_shortcuts(self):
        with mock.patch.object(actions, "hold_shortcuts") as hold:
            send(msg("typing", 1))
            send(msg("typing", 0))
            send(msg("typing"))
        self.assertEqual([c.args for c in hold.call_args_list], [(True,), (False,), (False,)])

    def test_a_strike_played_is_seen_and_a_replay_gets_the_forest_it_took(self):
        with mock.patch.object(events_state, "mark_seen") as seen:
            send(msg("struck", "2026-09-10", "3"))  # a key with colons in it comes whole
        seen.assert_called_once_with("2026-09-10:3")
        with mock.patch.object(events_state, "strike_before", return_value={"before": []}) as before:
            self.assertEqual(send(msg("strike", "2026-09-10", "3")), (True, {"before": []}))
        before.assert_called_once_with("2026-09-10:3")
        self.assertEqual(send(msg("strike", "never-struck")), (True, None))

    def test_the_deep_forest_s_trees_are_sent_when_zoomed_into(self):
        with mock.patch.object(payload, "deep_trees", return_value=[{"ago": 400}]) as deep:
            self.assertEqual(send(msg("deep", "")), (True, [{"ago": 400}]))
            self.assertEqual(send(msg("deep", 10)), (True, [{"ago": 400}]))
            send(msg("deep"))
        self.assertEqual([c.args for c in deep.call_args_list], [("",), ("10",), ("",)])

    def test_a_note_answered_is_seen_for_good_and_its_button_opens_its_tab(self):
        with mock.patch.object(news, "mark_seen") as seen, mock.patch.object(news, "opens", return_value="heatmap"), \
                mock.patch.object(actions, "open_settings") as opened:
            send(msg("news", "seen", "calendar-1.3"))
            opened.assert_not_called()
            send(msg("news", "open", "calendar-1.3"))
        self.assertEqual([c.args for c in seen.call_args_list], [(["calendar-1.3"],), (["calendar-1.3"],)])
        opened.assert_called_once_with("heatmap")

    def test_news_ids_fit_in_a_message(self):
        # the page sends news:<button>:<id>, and only the part after the second colon is read
        with open(os.path.join(fake_anki.ADDON_DIR, "release_notes.json"), encoding="utf-8") as f:
            text = f.read()
        ids = [e["announce"]["id"] for e in news._items()]  # (the notes the page can show)
        self.assertTrue(ids or '"announce"' not in text)
        for i in ids:
            self.assertNotIn(":", i)

    def test_a_broken_message_is_logged_and_still_answered(self):
        for broken in (msg("browse", "x"), msg("day", "soon"), msg("browse")):
            self.assertEqual(send(broken), (True, None), broken)
        self.assertEqual(len(self.logged), 3)
        self.assertEqual(browser.searches, [])
        # the hook still has the add-on on it (a callback that raised would have been taken off)
        self.assertEqual(send(msg("browse", 5, "")), (True, None))

    def test_an_unknown_command_is_answered_and_does_nothing(self):
        self.assertEqual(send(msg("teleport", 1)), (True, None))
        self.assertEqual((browser.searches, self.logged, mw.addonManager.config), ([], [], {}))

    def test_a_browser_that_will_not_open_never_crashes_the_page(self):
        with mock.patch.object(actions.dialogs, "open", side_effect=RuntimeError("no browser")):
            self.assertEqual(send(msg("browse", 5, "")), (True, None))
        self.assertEqual(len(self.logged), 1)


class MessageFormatsTests(unittest.TestCase):
    """The messages the page's scripts write match what on_js_message reads: each command the
    page sends is one it handles."""

    HANDLED = {"settings", "news", "struck", "strike", "deep", "mark", "unmark", "shade", "view", "typing", "day", "days", "browse"}

    def test_every_command_the_page_sends_is_handled(self):
        import re
        web = os.path.join(fake_anki.ADDON_DIR, "web")
        sent = set()
        for root, dirs, names in os.walk(web):
            dirs[:] = [d for d in dirs if d != "drafts"]
            for n in names:
                if n.endswith(".js"):
                    with open(os.path.join(root, n), encoding="utf-8") as f:
                        sent |= set(re.findall(r"\$\{data\.channel\}:([a-z]+)", f.read()))
        self.assertTrue(sent)
        self.assertEqual(sent - self.HANDLED, set())


if __name__ == "__main__":
    unittest.main()

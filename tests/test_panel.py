"""The forest panel (panel.py): its HTML and scripts, and where it shows, in a stand-in Anki."""

from __future__ import annotations

import json
import re
import types
import unittest
from unittest import mock

from fake_anki import Web, addon, hooks, mw, reset

import catalog

panel = addon.panel
CARDS = [(1, 10, 5), (2, 20, 3)]
# neither the forest nor the study calendar on the deck list, or on the deck screens
NO_MAIN = {"main_forest": False, "calendar_main": False}
NO_DECKS = {"deck_forest_mode": "off", "calendar_decks": False}


def shown(html: str) -> dict:
    """The data a panel's HTML carries."""
    return json.loads(re.search(r'-data">(.*?)</script>', html, re.S).group(1))


class PanelTests(unittest.TestCase):
    def setUp(self):
        reset(CARDS)

    def test_the_scripts_load_in_order_with_the_boot_script_last(self):
        html = panel._panel_html()
        srcs = re.findall(r'<script src="([^"]+)"', html)
        # each address carries its file's modification time, so Anki's cache never serves an old copy
        self.assertTrue(all(re.search(r"\?v=\d+$", s) for s in srcs))
        names = [s.split("/web/", 1)[1].split("?")[0] for s in srcs]
        self.assertEqual(names[:len(catalog.SCRIPTS)], list(catalog.SCRIPTS))
        self.assertEqual(names[-1], panel.BOOT)
        # then this copy's experiments, and between them and the boot script the scene's own parts that have a file
        drafts = catalog.draft_scripts()
        self.assertEqual(names[len(catalog.SCRIPTS):len(catalog.SCRIPTS) + len(drafts)], list(drafts))
        mood = json.loads(re.search(r'-data">(.*?)</script>', html, re.S).group(1))["mood"]
        for rel in names[len(catalog.SCRIPTS) + len(drafts):-1]:
            self.assertIn(rel.split("/")[0], ("envs", "landscapes", "landmarks"))
            self.assertIn(rel.split("/")[1][:-3], (mood["special"], mood["landscape"], mood["landmark"]))

    def test_the_data_cannot_close_its_script_tag(self):
        _root, data, _srcs = panel._panel_parts()
        self.assertNotIn("</", data)
        self.assertEqual(json.loads(data)["stats"]["trees"], 2)

    def test_the_panel_sits_above_the_deck_lists_stats(self):
        content = types.SimpleNamespace(stats="<p>stats</p>")
        panel.on_deck_browser(None, content)
        self.assertTrue(content.stats.startswith('<link rel="stylesheet"'))
        self.assertTrue(content.stats.endswith("<p>stats</p>"))

    def test_the_deck_list_can_go_without_a_forest(self):
        reset(CARDS, NO_MAIN)
        content = types.SimpleNamespace(stats="<p>stats</p>")
        panel.on_deck_browser(None, content)
        self.assertEqual(content.stats, "<p>stats</p>")
        # a deck's own screen still has one
        reset(CARDS, NO_MAIN, current_deck=10)
        content = types.SimpleNamespace(table="")
        panel.on_overview(None, content)
        self.assertTrue(content.table)

    def test_the_study_calendar_can_show_without_the_forest(self):
        reset(CARDS, {"main_forest": False})
        content = types.SimpleNamespace(stats="")
        panel.on_deck_browser(None, content)
        data = shown(content.stats)
        self.assertFalse(data["showForest"])
        self.assertIsNotNone(data["calendar"])
        # and the forest without it
        reset(CARDS, {"calendar_main": False})
        content = types.SimpleNamespace(stats="")
        panel.on_deck_browser(None, content)
        data = shown(content.stats)
        self.assertTrue(data["showForest"])
        self.assertIsNone(data["calendar"])

    def test_switching_the_deck_list_forest_off_takes_it_away_at_once(self):
        reset(CARDS, NO_MAIN)
        web = Web()
        mw.deckBrowser = types.SimpleNamespace(web=web, refresh=lambda: setattr(web, "reloads", web.reloads + 1))
        panel.refresh()
        # the forest still on the page: the list is drawn again without it, not swapped
        self.assertNotIn("afSwap", web.evaluated[0])
        self.assertEqual(web.reloads, 1)

    def test_a_deck_screen_follows_the_deck_screens_setting(self):
        for mode, calendar, deck, forest in (("highlight", True, 10, True), ("own", True, 10, True), ("off", False, 10, None),
                                             ("off", True, 10, False),  # the deck's study calendar on its own
                                             ("highlight", True, 30, None)):  # 30 is filtered: it borrows cards, so no forest
            reset(CARDS, {"deck_forest_mode": mode, "calendar_decks": calendar}, current_deck=deck)
            content = types.SimpleNamespace(table="")
            panel.on_overview(None, content)
            self.assertEqual(shown(content.table)["showForest"] if content.table else None, forest, (mode, calendar, deck))
        reset(CARDS, {"excluded_decks": [10]}, current_deck=11)  # left out with its parent
        content = types.SimpleNamespace(table="")
        panel.on_overview(None, content)
        self.assertEqual(content.table, "")

    def test_a_redraw_swaps_the_forest_in_place(self):
        web = Web()
        mw.deckBrowser = types.SimpleNamespace(web=web, refresh=lambda: setattr(web, "reloads", web.reloads + 1))
        panel.refresh()
        self.assertEqual(len(web.evaluated), 1)
        # through the panel itself, so another copy of the add-on on the page is never asked
        self.assertIn(f"getElementById({json.dumps(panel._panel_parts()[0])})", web.evaluated[0])
        self.assertIn("r.afSwap(", web.evaluated[0])
        self.assertEqual(web.reloads, 0)


class CongratsWeb(Web):
    """The main window's web view showing a finished deck's page (Anki's congratulations
    page, loaded by its address) - or, with `url`, another page of its own."""

    def __init__(self, url: str = "http://127.0.0.1:1234/_anki/pages/congrats.html#night", swaps: bool = True):
        super().__init__()
        self._url, self.swaps = url, swaps

    def url(self):
        return types.SimpleNamespace(toString=lambda: self._url)

    def eval(self, js):
        self.evaluated.append(js)

    def evalWithCallback(self, js, callback):
        self.evaluated.append(js)
        callback(self.swaps if "afSwap" in js else True)


def injected(js: str) -> tuple:
    """What panel.on_page_loaded's script puts on the page: (the data, the scripts it loads, in order)."""
    data = json.loads(re.search(r"JSON\.stringify\((\{.*\})\); box\.append", js, re.S).group(1))
    srcs = json.loads(re.search(r"for \(const src of (\[.*?\])\)", js).group(1))
    return data, srcs


class FinishedDeckTests(unittest.TestCase):
    """A finished deck's page: the panel added once it has loaded (panel.on_page_loaded), and
    redrawn, taken off or put back by refresh()."""

    def setUp(self):
        reset(CARDS)
        self.web = CongratsWeb()
        mw.overview = types.SimpleNamespace(web=self.web, refresh=lambda: setattr(self.web, "reloads", self.web.reloads + 1))
        mw.state = "overview"

    def test_the_panel_is_added_to_a_finished_decks_page_once_it_has_loaded(self):
        self.assertIn(panel.on_page_loaded, hooks.webview_did_inject_style_into_page)
        panel.on_page_loaded(self.web)
        self.assertEqual(len(self.web.evaluated), 1)
        js = self.web.evaluated[0]
        root = panel._panel_parts()[0]
        self.assertIn(f"getElementById({json.dumps(root)})", js)  # (never twice)
        self.assertIn(json.dumps(root + "-data"), js)
        self.assertIn("s.async = false", js)  # (scripts added by hand run in order only then)
        data, srcs = injected(js)
        self.assertEqual((data["deckId"], data["showForest"], data["highlight"]), (10, True, True))
        self.assertTrue(srcs[-1].startswith(f"{panel.WEB}/{panel.BOOT}?v="))  # the boot script last
        self.assertIn(f"if (src.indexOf({json.dumps(panel.BOOT)}) >= 0) s.dataset.root = {json.dumps(root)}", js)
        self.assertEqual(srcs[:-1], panel._panel_parts(10, True)[2])

    def test_only_a_finished_decks_page_of_the_overview_gets_one(self):
        for why, web, state, config in (("the usual deck screen", CongratsWeb("http://127.0.0.1:1234/_anki/legacyPageData?id=3"), "overview", None),
                                        ("another screen", CongratsWeb(), "deckBrowser", None),
                                        ("the setting off", CongratsWeb(), "overview", {"finished_decks": False})):
            reset(CARDS, config)
            mw.overview.web, mw.state = web, state
            panel.on_page_loaded(web)
            self.assertEqual(web.evaluated, [], why)
        reset(CARDS)
        panel.on_page_loaded(Web())  # another window's web view: not the overview's
        self.assertEqual(self.web.evaluated, [])
        reset(CARDS, {"deck_forest_mode": "off", "calendar_decks": False})  # no deck panel at all
        panel.on_page_loaded(self.web)
        self.assertEqual(self.web.evaluated, [])

    def test_a_page_loaded_afresh_releases_the_shortcuts_held_while_a_mark_was_named(self):
        shortcut = mock.Mock()
        shortcut.isEnabled.return_value = True
        with mock.patch.object(mw, "findChildren", create=True, return_value=[shortcut]):
            panel.hold_shortcuts(True)
        shortcut.setEnabled.assert_called_with(False)
        panel.on_page_loaded(Web())  # another window's page: the main window's shortcuts stay held
        shortcut.setEnabled.assert_called_with(False)
        mw.state = "deckBrowser"  # (any page of the main window: the one typed on is gone)
        panel.on_page_loaded(self.web)
        shortcut.setEnabled.assert_called_with(True)

    def test_a_redraw_swaps_the_finished_decks_panel_in_place(self):
        panel.refresh()
        self.assertEqual(len(self.web.evaluated), 1)
        self.assertIn("r.afSwap(", self.web.evaluated[0])
        self.assertEqual(self.web.reloads, 0)

    def test_a_redraw_puts_the_panel_back_without_reloading_ankis_page(self):
        self.web.swaps = False  # nothing there to swap: the setting was just turned on
        panel.refresh()
        self.assertEqual(len(self.web.evaluated), 2)
        self.assertIn("r.afSwap(", self.web.evaluated[0])
        self.assertIn("af-finished", self.web.evaluated[1])
        self.assertEqual(injected(self.web.evaluated[1])[0]["deckId"], 10)
        self.assertEqual(self.web.reloads, 0)

    def test_switching_finished_decks_off_takes_the_panel_off_the_page(self):
        reset(CARDS, {"finished_decks": False})
        mw.state = "overview"
        panel.refresh()
        self.assertEqual(len(self.web.evaluated), 1)
        self.assertIn(".af-finished", self.web.evaluated[0])
        self.assertNotIn("afSwap", self.web.evaluated[0])
        self.assertEqual(self.web.reloads, 0)

    def test_a_deck_screen_with_no_panel_reloads_only_while_one_is_still_on_it(self):
        for url in ("http://127.0.0.1:1234/_anki/pages/congrats.html", "http://127.0.0.1:1234/_anki/legacyPageData?id=3"):
            for there, reloads in ((True, 1), (False, 0)):
                reset(CARDS, {"excluded_decks": [10]})  # left out of the forest: no panel for it
                web = Web()
                web.evalWithCallback = lambda js, callback, web=web, there=there: (web.evaluated.append(js), callback(there))
                web.url = lambda url=url: types.SimpleNamespace(toString=lambda: url)
                mw.overview = types.SimpleNamespace(web=web, refresh=lambda web=web: setattr(web, "reloads", web.reloads + 1))
                mw.state = "overview"
                panel.refresh()
                self.assertEqual(len(web.evaluated), 1, (url, there))
                self.assertIn(f"!!document.getElementById({json.dumps(panel.ROOT)})", web.evaluated[0])
                self.assertEqual(web.reloads, reloads, (url, there))


if __name__ == "__main__":
    unittest.main()

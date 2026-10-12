"""The forest panel (panel.py): its HTML and scripts, and where it shows, in a stand-in Anki."""

from __future__ import annotations

import json
import re
import types
import unittest

from fake_anki import Web, addon, mw, reset

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


if __name__ == "__main__":
    unittest.main()

"""The release notes (release_notes.json, release_notes.py): the one place they are written,
and what is made from them."""

from __future__ import annotations

import json
import os
import sys
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import release_notes

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ADDON, "dev"))
import notes

VERSIONS = [
    {"version": "2.0.0", "new": ["A new thing.", {"text": "Plus only.", "needs": "scenery:plus_only"}],
     "improved": ["Better <b>now</b>."], "fixed": ['A <a href="https://x.y">link</a> fixed.']},
    {"version": "1.0.0", "notes": ["First release."]},
]


class FileTests(unittest.TestCase):
    def test_the_file_reads(self):
        versions = release_notes.load()
        self.assertTrue(versions)
        for v in versions:
            # (and "plus": the names of what Plus got more, in the free edition's copy: for_edition)
            self.assertTrue(set(v) <= {"version", "summary", "plus"} | {k for k, _h in release_notes.SECTIONS}, v["version"])
            self.assertTrue(all(isinstance(name, str) and name.strip() for name in v.get("plus", [])), v["version"])
            for e in release_notes.items(v):
                self.assertTrue(e["text"].strip())

    def test_the_ankiweb_page_is_up_to_date(self):
        with open(notes.PAGE, encoding="utf-8") as f:
            self.assertEqual(notes.page(), f.read(), "run npm run notes")

    def test_announcements_have_ids_of_their_own(self):
        ids = [e["announce"]["id"] for v in release_notes.load() for e in release_notes.items(v) if "announce" in e]
        self.assertEqual(len(ids), len(set(ids)))


class MadeFromItTests(unittest.TestCase):
    def test_html(self):
        self.assertEqual(release_notes.to_html(VERSIONS[1:]), "<i>1.0.0</i>\n<ul>\n<li>First release.</li>\n</ul>\n")
        self.assertIn("<div><b>Improved</b></div>\n<ul>\n<li>Better <b>now</b>.</li>\n</ul>", release_notes.to_html(VERSIONS))

    def test_markdown(self):
        self.assertEqual(release_notes.to_markdown(VERSIONS, "2.0.0"),
                         "### New\n\n- A new thing.\n- Plus only.\n\n### Improved\n\n- Better **now**.\n\n"
                         "### Fixed\n\n- A [link](https://x.y) fixed.\n")
        self.assertIsNone(release_notes.to_markdown(VERSIONS, "3.0.0"))

    def test_a_summary_comes_before_the_lists_everywhere(self):
        versions = [{"version": "4.0.0", "summary": "All about <b>trees</b>.", "new": ["A tree."]}]
        self.assertTrue(release_notes.to_html(versions).startswith("<i>4.0.0</i>\n<div>All about <b>trees</b>.</div>\n"))
        self.assertTrue(release_notes.to_markdown(versions, "4.0.0").startswith("All about **trees**.\n"))
        self.assertEqual(release_notes.for_edition(versions, {})[0]["summary"], "All about <b>trees</b>.")

    def test_an_edition_without_the_scenery_never_lists_it(self):
        base = release_notes.for_edition(VERSIONS, {"scenery": {"other"}})
        self.assertEqual(base[0]["new"], ["A new thing."])
        self.assertEqual(release_notes.for_edition(VERSIONS, {"scenery": None})[0]["new"], VERSIONS[0]["new"])

    def test_an_edition_without_plus_items_names_them_in_a_closing_line(self):
        versions = [{"version": "5.0.0", "new": ["Free.", {"text": "A Plus scenery.", "needs": "scenery:x", "plus": "X"},
                                                   {"text": "Another.", "needs": "scenery:y", "plus": "the Y landscape"},
                                                   {"text": "Unnamed.", "needs": "scenery:z"}]}]
        base = release_notes.for_edition(versions, {"scenery": {"other"}})
        self.assertEqual((base[0]["new"], base[0]["plus"]), (["Free."], ["X", "the Y landscape"]))
        self.assertEqual(release_notes.plus_line(base[0]), "Also new in Memory Forest Plus: X and the Y landscape.")
        self.assertTrue(release_notes.to_markdown(base, "5.0.0").endswith("- Free.\n\nAlso new in Memory Forest Plus: X and the Y landscape.\n"))
        self.assertNotIn("Plus", release_notes.to_html(base))  # (the AnkiWeb page's own pictures say it)
        # (the base copy's file, filtered again by the add-on, keeps its names)
        self.assertEqual(release_notes.for_edition(base, {"scenery": {"other"}})[0]["plus"], ["X", "the Y landscape"])
        everything = release_notes.for_edition(versions, {"scenery": None})
        self.assertNotIn("plus", everything[0])
        self.assertEqual(release_notes.plus_line(everything[0]), "")

    def test_a_line_for_one_edition_alone(self):
        entry = {"text": "Now free.", "needs": "scenery:x edition:base"}
        self.assertTrue(release_notes.has(entry, {"scenery": {"x"}, "edition": {"base"}}))
        self.assertFalse(release_notes.has(entry, {"scenery": {"x"}, "edition": {"plus"}}))
        self.assertTrue(release_notes.has(entry, {"scenery": None, "edition": None}))  # (this copy, every edition's lines)
        if notes.editions.available():  # (the public repo has no editions.json, nor any Plus to build)
            self.assertNotIn("Starry night, after Van Gogh, is now in the free edition.",
                             [release_notes.item(e)["text"] for e in notes.versions("plus")[0]["new"]])

    def test_a_need_with_no_key_wants_any_of_its_kind(self):
        entry = {"text": "x", "needs": "gizmos"}
        self.assertFalse(release_notes.has(entry, {}))
        self.assertFalse(release_notes.has(entry, {"gizmos": set()}))
        self.assertTrue(release_notes.has(entry, {"gizmos": {"a"}}))

    def test_the_public_copy_of_the_file_is_the_public_page(self):
        with open(release_notes.PATH, encoding="utf-8") as f:
            public = json.loads(notes.edition_json(notes.PUBLIC, f.read()))["versions"]
        self.assertEqual(public, notes.versions())


if __name__ == "__main__":
    unittest.main()

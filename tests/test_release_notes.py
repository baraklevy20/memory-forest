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
            self.assertTrue(set(v) <= {"version"} | {k for k, _h in release_notes.SECTIONS}, v["version"])
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

    def test_an_edition_without_the_scenery_never_lists_it(self):
        base = release_notes.for_edition(VERSIONS, {"scenery": {"other"}})
        self.assertEqual(base[0]["new"], ["A new thing."])
        self.assertEqual(release_notes.for_edition(VERSIONS, {"scenery": None})[0]["new"], VERSIONS[0]["new"])

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

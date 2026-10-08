"""Which edition this copy is (edition.py)."""

from __future__ import annotations

import unittest
from unittest import mock

from fake_anki import addon, reset

edition = addon.edition


class EditionTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_the_debug_edition_needs_debug_on_and_names_an_edition(self):
        self.assertEqual(edition.debug_edition({"debug_edition": "base"}), "")  # debug off: ignored
        on = {"debug": True}
        self.assertEqual(edition.debug_edition(dict(on, debug_edition="base")), "base")
        self.assertEqual(edition.debug_edition(dict(on, debug_edition="plus")), "plus")
        self.assertEqual(edition.debug_edition(dict(on, debug_edition="nonsense")), "")
        with mock.patch.object(edition.os.path, "exists", return_value=False):  # a release
            self.assertEqual(edition.debug_edition(dict(on, debug_edition="base")), "")

    def test_an_edition_offers_only_the_presets_it_ships(self):
        self.assertIsNone(edition.edition_presets(""))
        base, plus = edition.edition_presets("base"), edition.edition_presets("plus")
        if base is None:
            self.skipTest("no editions.json: the public repo is one edition")
        self.assertIn(edition.presets.DAILY, base)
        self.assertNotIn("cherry_blossom", base)
        self.assertIn("cherry_blossom", plus)
        self.assertLess(base, plus)


class ManifestTests(unittest.TestCase):
    def test_the_shipped_manifest_has_a_version(self):
        self.assertTrue(edition.manifest().get("human_version"))

    def test_plus_is_told_by_the_package(self):
        with mock.patch.object(edition, "manifest", return_value={"package": edition.PLUS_PACKAGE}):
            self.assertTrue(edition.is_plus())
        with mock.patch.object(edition, "manifest", return_value={}):
            self.assertFalse(edition.is_plus())


if __name__ == "__main__":
    unittest.main()

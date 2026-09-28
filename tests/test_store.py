"""Reading and writing the add-on's JSON files."""

from __future__ import annotations

import os
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import store


class StoreTests(unittest.TestCase):
    """The small JSON files under user_files/."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "state.json")

    def test_a_missing_file_reads_as_empty(self):
        self.assertEqual(store.load_json(self.path), {})

    def test_it_makes_its_own_directory_and_round_trips(self):
        store.save_json(self.path, {"a": 1})
        self.assertEqual(store.load_json(self.path), {"a": 1})

    def test_anything_that_is_not_an_object_reads_as_empty(self):
        store.save_json(self.path, {})
        for junk in ("null", "[1, 2]", "not json at all", ""):
            open(self.path, "w").write(junk)
            self.assertEqual(store.load_json(self.path), {})

    def test_a_failed_write_leaves_the_old_file_alone(self):
        store.save_json(self.path, {"keep": True})
        try:
            store.save_json(self.path, {"bad": {1, 2}})  # a set is not JSON
        except TypeError:
            pass
        self.assertEqual(store.load_json(self.path), {"keep": True})

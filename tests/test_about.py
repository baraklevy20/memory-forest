"""The About tab's data: the sponsors it thanks (goats.json) and the manifest it reads."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

from fake_anki import PACKAGE

about = importlib.import_module(f"{PACKAGE}.settings.about")
patreon = importlib.import_module(f"{PACKAGE}.settings.patreon")


def written(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class GoatsFileTests(unittest.TestCase):
    def read(self, content: str) -> list:
        path = written(content)
        try:
            with mock.patch.object(about, "GOATS", path):
                return about.goats()
        finally:
            os.remove(path)

    def test_names_are_read_in_order(self):
        self.assertEqual(self.read(json.dumps(["Ada", "Bea"])), ["Ada", "Bea"])

    def test_blanks_and_non_names_are_left_out(self):
        self.assertEqual(self.read(json.dumps(["Ada", "  ", 3, None, "Bea"])), ["Ada", "Bea"])

    def test_a_broken_or_missing_file_thanks_no_one(self):
        self.assertEqual(self.read("not json"), [])
        self.assertEqual(self.read(json.dumps({"Ada": 1})), [])
        with mock.patch.object(about, "GOATS", os.path.join(tempfile.gettempdir(), "no-such-goats.json")):
            self.assertEqual(about.goats(), [])


if __name__ == "__main__":
    unittest.main()

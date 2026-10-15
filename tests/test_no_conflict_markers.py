"""No merge left half done: a conflict marker in a shipped file breaks it quietly (a CSS rule the
browser drops, 2026-10-14: the streak notes fell out of their lane)."""

from __future__ import annotations

import os
import re
import unittest

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = re.compile(r"^(<{7} |={7}$|>{7} )", re.MULTILINE)
SKIP = {"node_modules", ".git", "__pycache__", "user_files"}
TEXT = (".py", ".js", ".mjs", ".css", ".html", ".json", ".md")


class ConflictMarkerTests(unittest.TestCase):
    def test_no_file_holds_a_conflict_marker(self):
        found = []
        for root, dirs, files in os.walk(ADDON):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for name in files:
                if name.endswith(TEXT):
                    path = os.path.join(root, name)
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        if MARKER.search(f.read()):
                            found.append(os.path.relpath(path, ADDON))
        self.assertEqual(found, [], "merge conflict markers left in: " + ", ".join(found))


if __name__ == "__main__":
    unittest.main()

"""Every environment, landscape and landmark is one file plus one row."""

from __future__ import annotations

import os
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import scene


class RegistryFileTests(unittest.TestCase):
    """Environments, landscapes and landmarks are each one file plus one row.

    A key with no file is a setting the dialog offers and the panel cannot draw; a file
    nothing names is code that ships and never runs. Either way it is a dead setting, and
    that is the failure this catches before anyone sees it.
    """

    WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

    def files(self, kind: str) -> set:
        return {f[:-3] for f in os.listdir(os.path.join(self.WEB, kind)) if f.endswith(".js")}

    def check(self, kind: str, keys: set, register: str, exempt: set | None = None) -> None:
        files = self.files(kind)
        self.assertEqual(keys - files, exempt or set(), f"{kind}: a .json with no .js to draw it")
        self.assertEqual(files - keys, set(), f"{kind}: a .js with no .json to name it")
        for name in files:
            src = open(os.path.join(self.WEB, kind, name + ".js"), encoding="utf-8").read()
            self.assertIn(f"{register}('{name}'", src, f"{kind}/{name}.js should register {name!r}")

    def test_every_environment_names_its_own_file(self):
        # the plain forest needs no file, because it is what every other one departs from
        self.check("envs", set(scene.ENVIRONMENTS), "AF.env", exempt={"natural"})

    def test_every_landscape_names_its_own_file(self):
        self.check("landscapes", set(scene.LANDSCAPES), "AF.landscape")

    def test_every_landmark_names_its_own_file(self):
        self.check("landmarks", set(scene.LANDMARKS), "AF.landmark", exempt={"none"})

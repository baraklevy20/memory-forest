"""The .ankiaddon each edition is built as (dev/package.py): exactly the files it should ship, the
debug tools and switches off, no drafts, only its own scenery - and the built add-on loads and
draws its panel in the stand-in Anki without the files it left behind."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest
import zipfile

import fake_anki
from fake_anki import hooks, mw, reset

import catalog

ADDON = fake_anki.ADDON_DIR
DEV = os.path.join(ADDON, "dev")
sys.path.insert(0, DEV)
import editions
import package

ESBUILD = package.ESBUILD


def expected_editions() -> list:
    """The editions this folder builds: each one in editions.json, or the one the public repo is."""
    return list(editions.available()) or [None]


_TMP = tempfile.mkdtemp(prefix="memory-forest-build-test-")
_built: dict = {}


def built(edition: str | None) -> str:
    """The edition's .ankiaddon, built once for every test here."""
    if edition not in _built:
        out = os.path.join(_TMP, f"{edition or 'public'}.ankiaddon")
        flags = ["--edition", edition] if edition else []
        subprocess.run([sys.executable, os.path.join(DEV, "package.py"), *flags, out], check=True, capture_output=True, text=True)
        _built[edition] = out
    return _built[edition]


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(os.path.exists(ESBUILD), "esbuild is not installed (npm install)")
class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = _TMP
        cls.built = {}
        for edition in expected_editions():
            out = built(edition)
            with zipfile.ZipFile(out) as z:
                cls.built[edition] = (out, {n: z.read(n) for n in z.namelist()})

    def each(self):
        for edition, (out, files) in self.built.items():
            with self.subTest(edition=edition):
                yield edition, out, files

    def test_nothing_of_this_machine_or_of_development_gets_in(self):
        for _edition, _out, files in self.each():
            for name in files:
                self.assertFalse(name.startswith(("dev/", "tests/", "e2e/", "docs/", "node_modules/", "user_files/", "dist/")), name)
                self.assertNotIn("__pycache__", name)
                self.assertNotIn("meta.json", name)
                self.assertFalse(name.startswith("web/drafts/"), name)  # experiments stay here
                self.assertNotIn(name, package.DEBUG_ONLY)
                self.assertNotIn(os.path.basename(name), (".DS_Store", "editions.json", "package.json"))

    def test_every_module_the_add_on_runs_ships(self):
        py = {n for n in os.listdir(ADDON) if n.endswith(".py")} - set(package.DEBUG_ONLY)
        settings = {f"settings/{n}" for n in os.listdir(os.path.join(ADDON, "settings")) if n.endswith(".py")} - set(package.DEBUG_ONLY)
        for _edition, _out, files in self.each():
            self.assertEqual({n for n in files if n.endswith(".py")}, py | settings)
            for name in ("config.json", "manifest.json", "goats.json", "release_notes.json", "web/forest.css", "web/forest.js", "web/phone.js"):
                self.assertIn(name, files)

    def test_the_page_s_scripts_ship_as_one_bundle_in_their_order(self):
        for _edition, _out, files in self.each():
            self.assertIn(f"web/{catalog.BUNDLE}", files)
            for rel in catalog.SCRIPTS:
                self.assertNotIn(f"web/{rel}", files)  # (only inside the bundle)
            bundle = files[f"web/{catalog.BUNDLE}"].decode("utf-8")
            self.assertGreater(len(bundle), 10000)
            self.assertNotIn("\n  //", bundle)  # minified

    def test_each_edition_ships_exactly_its_own_scenery(self):
        for edition, _out, files in self.each():
            keep = editions.scenery(edition) if edition else {k: set(catalog.entries(k)) for k in editions.SCENERY}
            for kind in editions.SCENERY:
                shipped = {os.path.splitext(n.split("/")[2])[0] for n in files if n.startswith(f"web/{kind}/")}
                self.assertEqual(shipped, set(keep[kind]), kind)
                for key in keep[kind]:  # each with its label and preset beside it
                    self.assertIn(f"web/{kind}/{key}.json", files)

    def test_the_editions_scenery_lists_name_only_sceneries_that_are_here(self):
        envs = set(catalog.entries("envs"))
        for name, spec in editions.available().items():
            if spec["envs"] != editions.ALL:
                self.assertLessEqual(set(spec["envs"]), envs, name)
                self.assertEqual(len(spec["envs"]), len(set(spec["envs"])), name)

    def test_the_debug_switches_ship_off_and_every_other_default_as_it_is(self):
        with open(os.path.join(ADDON, "config.json"), encoding="utf-8") as f:
            source = json.load(f)
        for _edition, _out, files in self.each():
            shipped = json.loads(files["config.json"])
            self.assertEqual({k: shipped[k] for k in package.RELEASE_CONFIG}, package.RELEASE_CONFIG)
            self.assertFalse(shipped["debug"])
            self.assertEqual({k: v for k, v in shipped.items() if k not in package.RELEASE_CONFIG},
                             {k: v for k, v in source.items() if k not in package.RELEASE_CONFIG})

    def test_each_edition_has_its_own_name_and_package(self):
        with open(os.path.join(ADDON, "manifest.json"), encoding="utf-8") as f:
            source = json.load(f)
        packages = set()
        for edition, _out, files in self.each():
            m = json.loads(files["manifest.json"])
            spec = editions.spec(edition) if edition else {"name": source["name"], "package": source["package"]}
            self.assertEqual((m["name"], m["package"]), (spec["name"], spec["package"]))
            self.assertEqual(m["human_version"], source["human_version"])
            self.assertEqual(m["min_point_version"], source["min_point_version"])
            packages.add(m["package"])
        self.assertEqual(len(packages), len(self.built))  # (two editions installed side by side, each in its own folder)

    def test_the_python_ships_without_comments_and_still_compiles(self):
        for _edition, _out, files in self.each():
            for name, data in files.items():
                if name.endswith(".py"):
                    text = data.decode("utf-8")
                    compile(text, name, "exec")
                    comments = [t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type == tokenize.COMMENT]
                    self.assertEqual(comments, [], name)

    def test_the_shipped_release_notes_are_the_edition_s_own(self):
        for _edition, _out, files in self.each():
            notes = json.loads(files["release_notes.json"])
            self.assertTrue(notes)

    def test_a_version_given_is_the_one_shipped(self):
        out = os.path.join(self.tmp, "versioned.ankiaddon")
        edition = expected_editions()[0]
        flags = ["--edition", edition] if edition else []
        subprocess.run([sys.executable, os.path.join(DEV, "package.py"), *flags, "--version", "9.8.7", out],
                       check=True, capture_output=True)
        with zipfile.ZipFile(out) as z:
            self.assertEqual(json.loads(z.read("manifest.json"))["human_version"], "9.8.7")

    def test_without_an_edition_named_the_private_folder_refuses_to_build(self):
        if not editions.available():
            self.skipTest("the public repo has one edition")
        got = subprocess.run([sys.executable, os.path.join(DEV, "package.py"), os.path.join(self.tmp, "x.ankiaddon")],
                             capture_output=True, text=True)
        self.assertNotEqual(got.returncode, 0)
        self.assertIn("name an edition", got.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x.ankiaddon")))


class ReleaseConfigTests(unittest.TestCase):
    def test_the_release_config_turns_the_debug_tools_off_whatever_the_folder_has(self):
        text = json.dumps({"debug": True, "test_forest": True, "scenery": "x"})
        self.assertEqual(json.loads(package.release_config(text)), {"debug": False, "test_forest": False, "scenery": "x"})

    def test_stripping_keeps_every_line_where_it_was(self):
        source = 'def f():\n    """Doc\n    more."""\n    x = 1  # note\n    # alone\n    return x\n'
        out = package.stripped(source)
        self.assertEqual(len(out.splitlines()), len(source.splitlines()))
        self.assertNotIn("note", out)
        self.assertNotIn("Doc", out)
        self.assertEqual(out.splitlines()[5], "    return x")


@unittest.skipUnless(os.path.exists(ESBUILD), "esbuild is not installed (npm install)")
class BuiltAddonLoadsTests(unittest.TestCase):
    """Each built add-on unpacked into a folder of its package's name and loaded as Anki loads it:
    it must run without the debug tools it left behind (debug on by hand changes nothing)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="memory-forest-built-addon-", dir=_TMP)
        cls.saved = {name: list(list.__iter__(hook)) for name, hook in vars(hooks).items()}
        cls.loaded = {}
        for edition in expected_editions():
            with zipfile.ZipFile(built(edition)) as z:
                name = json.loads(z.read("manifest.json"))["package"]
                folder = os.path.join(cls.tmp, "addons21", name)
                z.extractall(folder)
            module = f"{name}_built_test"
            spec = importlib.util.spec_from_file_location(module, os.path.join(folder, "__init__.py"),
                                                          submodule_search_locations=[folder])
            pkg = importlib.util.module_from_spec(spec)
            sys.modules[module] = pkg
            spec.loader.exec_module(pkg)
            importlib.import_module(f"{module}.payload").log = lambda _msg: None  # ("built N trees in M ms")
            cls.loaded[edition] = (module, folder)

    @classmethod
    def tearDownClass(cls):
        for name, hook in vars(hooks).items():  # the built copies off the hooks again
            hook[:] = cls.saved[name]
        for module, _folder in cls.loaded.values():
            for m in [m for m in sys.modules if m == module or m.startswith(module + ".")]:
                del sys.modules[m]
        reset()

    def each(self):
        for edition, (module, folder) in self.loaded.items():
            with self.subTest(edition=edition):
                yield edition, module, folder

    def mod(self, module, name):
        return importlib.import_module(f"{module}.{name}")

    def test_it_goes_on_anki_s_hooks_as_this_folder_does(self):
        for _edition, module, _folder in self.each():
            on = [cb for cb in list.__iter__(hooks.deck_browser_will_render_content) if cb.__module__.startswith(module)]
            self.assertEqual([cb.__name__ for cb in on], ["release_shortcuts", "on_deck_browser"])
            self.assertIn(module, mw.addonManager.config_actions)

    def test_debug_on_by_hand_changes_nothing_in_a_release(self):
        for _edition, module, _folder in self.each():
            edition_mod, payload_mod = self.mod(module, "edition"), self.mod(module, "payload")
            self.assertFalse(edition_mod.debug_available({"debug": True}))
            self.assertEqual(edition_mod.debug_edition({"debug": True, "debug_edition": "plus"}), "")
            self.assertIsNone(payload_mod.debug_tools({"debug": True, "test_forest": True}))

    def test_it_knows_which_edition_it_is(self):
        for edition, module, _folder in self.each():
            self.assertEqual(self.mod(module, "edition").is_plus(), edition == "plus")

    def test_it_draws_its_panel_from_the_bundle_and_its_own_scenery(self):
        for _edition, module, folder in self.each():
            reset([(1, 10, 5), (2, 20, 3)])
            panel = self.mod(module, "panel")
            html = panel._panel_html()
            srcs = [s.split("/web/", 1)[1].split("?")[0] for s in re.findall(r'<script src="([^"]+)"', html)]
            self.assertEqual(srcs[0], catalog.BUNDLE)
            self.assertEqual(srcs[-1], panel.BOOT)
            for rel in srcs:
                self.assertTrue(os.path.exists(os.path.join(folder, "web", rel)), rel)
            self.assertFalse(any(rel.startswith("drafts/") for rel in srcs))
            # its own channel and element, apart from this folder's
            self.assertIn(module, panel.ROOT)
            self.assertEqual(json.loads(re.search(r'-data">(.*?)</script>', html, re.S).group(1))["channel"], module)

    def test_its_settings_have_no_debug_tab(self):
        for _edition, module, _folder in self.each():
            dialog = self.mod(module, "settings.dialog")
            self.assertIsInstance(dialog.debug_tab({"debug": True}), dialog.NoDebugTab)


if __name__ == "__main__":
    unittest.main()

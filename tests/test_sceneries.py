"""The shipped sceneries, without a browser: what each edition ships and draws with, the holiday
weeks of the real catalogue, the scene a preset resolves to at any hour, scripts that draw the
same day the same way, and the numbers every forest's trees are placed by, which must never
change between versions (e2e/scenery_check.py draws them all in Chrome)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import catalog
import forest_data
import presets
import scene

ADDON = os.path.dirname(catalog.WEB)
sys.path.insert(0, os.path.join(ADDON, "dev"))
import editions


def shipped_envs() -> list:
    """Every environment an edition ships (all of them here in the public repo, one edition)."""
    if not editions.available():
        return list(scene.ENVIRONMENTS)
    keep = set().union(*(editions.scenery(name)["envs"] for name in editions.available()))
    return [e for e in scene.ENVIRONMENTS if e in keep]


class EditionTests(unittest.TestCase):
    """editions.json names the sceneries each add-on ships: a typo there, or a Plus scenery
    the base needs, only shows in a build nobody has drawn yet."""

    def setUp(self):
        if not editions.available():
            self.skipTest("no editions.json: the public repo is one edition")
        self.eds = editions.available()

    def test_every_environment_an_edition_lists_is_here_with_a_preset(self):
        for name, spec in self.eds.items():
            if spec["envs"] == editions.ALL:
                continue
            self.assertEqual(len(set(spec["envs"])), len(spec["envs"]), f"{name} lists an environment twice")
            for env in spec["envs"]:
                self.assertIn(env, scene.ENVIRONMENTS, f"{name} lists {env!r}, which has no files")
                self.assertTrue(any(p.environment == env for p in presets.FOREST_PRESETS), f"{name}: {env} has no preset")

    def test_plus_has_everything_the_base_has(self):
        base, plus = editions.scenery("base"), editions.scenery("plus")
        for kind in ("envs", "landscapes", "landmarks", "presets"):
            self.assertLessEqual(base[kind], plus[kind], kind)

    def test_the_default_scenery_ships_in_every_edition(self):
        # a fresh install, and a forest whose scenery is not in this edition, fall back to it
        default = presets.FOREST_PRESETS[0]
        self.assertFalse(default.season, "the default can't be kept to a week")
        with open(os.path.join(ADDON, "config.json"), encoding="utf-8") as f:
            fresh = presets.match(json.load(f))
        for name in self.eds:
            keep = editions.scenery(name)
            self.assertIn(default.key, keep["presets"], name)
            self.assertIn(fresh, keep["presets"] | {presets.DAILY}, f"a fresh install of {name} opens on a scenery it lacks")

    def test_an_edition_ships_every_file_its_presets_draw_with(self):
        noon = dt.datetime(2026, 10, 18, 12)
        for name in self.eds:
            keep = editions.scenery(name)
            for f in catalog.SCRIPTS:
                self.assertTrue(editions.keeps(f"web/{f}", keep), f"{name} leaves out web/{f}")
            for p in presets.FOREST_PRESETS:
                if p.key not in keep["presets"] or p.key == presets.DAILY:
                    continue
                mood = scene.choose_mood(p.values(), noon)
                for rel in catalog.scenery_files(mood):
                    self.assertTrue(editions.keeps(f"web/{rel}", keep), f"{name}: {p.key} draws with web/{rel}, left out")

    def test_no_edition_ships_the_drafts(self):
        for name in self.eds:
            keep = editions.scenery(name)
            for rel in catalog.draft_scripts():
                self.assertFalse(editions.keeps(f"web/{rel}", keep), f"{name} ships the draft web/{rel}")
            for env in set(scene.ENVIRONMENTS) - keep["envs"]:
                self.assertFalse(editions.keeps(f"web/envs/{env}.js", keep), f"{name} ships {env}")


D = dt.date
SEASONAL = [p for p in presets.FOREST_PRESETS if p.season]


def in_week(p: presets.Preset, day: dt.date) -> bool:
    first, starts, ends = p.season
    return day >= first and starts <= (day.month, day.day) <= ends


class ShippedSeasonTests(unittest.TestCase):
    """The real holiday sceneries (test_presets.py tries the rules on a made-up one): each is
    there in its own week only, and a year of days brings each once and takes it back."""

    def setUp(self):
        if not SEASONAL:
            self.skipTest("no seasonal scenery here")

    def test_the_holiday_weeks_never_overlap_and_hold_their_holiday(self):
        weeks = sorted((p.season[1], p.season[2], p.key) for p in SEASONAL)
        for (_s, ends, a), (starts, _e, b) in zip(weeks, weeks[1:]):
            self.assertLess(ends, starts, f"{a} and {b} share days")
        for p in SEASONAL:
            _first, starts, ends = p.season
            length = (D(2027, *ends) - D(2027, *starts)).days + 1
            self.assertTrue(1 <= length <= 14, f"{p.key} lasts {length} days")
        holidays = {"pumpkin_patch": (10, 31), "frozen_market": (12, 25)}  # Halloween, Christmas
        for p in SEASONAL:
            if p.environment in holidays:
                self.assertTrue(p.season[1] <= holidays[p.environment] <= p.season[2], f"{p.key}'s week misses its day")

    def test_a_holiday_scenery_is_offered_in_its_week_only(self):
        day = D(2026, 1, 1)
        while day < D(2028, 1, 1):
            offered = presets.available(day)
            hidden = presets.hidden_environments(day)
            for p in SEASONAL:
                self.assertEqual(p in offered, in_week(p, day), f"{p.key} on {day}")
                self.assertEqual(p.environment in hidden, not in_week(p, day), f"{p.environment} on {day}")
            self.assertEqual(presets.in_season(day), next((p for p in SEASONAL if in_week(p, day)), None), day)
            day += dt.timedelta(days=1)

    def test_two_years_of_days_bring_each_holiday_once_and_give_the_forest_back(self):
        for start in (presets.FOREST_PRESETS[0], presets.FOREST_PRESETS[3]):
            cfg, record, day, seen = start.values(), None, D(2026, 1, 1), []
            while day < D(2028, 1, 1):
                change, record = presets.follow_season(cfg, record, day)
                cfg = dict(cfg, **change)
                now = next((p for p in SEASONAL if in_week(p, day)), None)
                self.assertEqual(presets.match(cfg), (now or start).key, f"{day}, from {start.key}")
                if now and (not seen or seen[-1] != (now.key, day.year)):
                    seen.append((now.key, day.year))
                day += dt.timedelta(days=1)
            self.assertEqual(cfg, start.values())
            self.assertEqual(len(seen), sum(1 for p in SEASONAL for year in (2026, 2027) if year >= p.season[0].year))

    def test_surprise_me_takes_every_other_scenery_in_turn(self):
        turn = [p for p in presets.FOREST_PRESETS if p.key != presets.DAILY and not p.season]
        day = D(2027, 1, 3)  # (two rounds clear of any holiday's week: one takes turns in its week, test_presets)
        for _round in range(2):
            picks = [presets.of_the_day(day + dt.timedelta(days=i)) for i in range(len(turn))]
            self.assertEqual(sorted(p.key for p in picks), sorted(p.key for p in turn))
            day += dt.timedelta(days=len(turn))

    def test_the_week_says_when_yours_comes_back(self):
        from fake_anki import addon, reset
        reset((), {})
        for p in SEASONAL:
            first = D(p.season[0].year, *p.season[1])
            cfg = addon.seasons.follow_season(presets.FOREST_PRESETS[0].values(), first)
            self.assertEqual(presets.match(cfg), p.key)
            self.assertEqual(addon.seasons.season_returns(cfg, first), D(first.year, *p.season[2]) + dt.timedelta(days=1))
            after = addon.seasons.follow_season(cfg, D(first.year, *p.season[2]) + dt.timedelta(days=1))
            self.assertEqual(presets.match(after), presets.FOREST_PRESETS[0].key)


class MoodTests(unittest.TestCase):
    """Whatever the preset and the hour, the scene is one the page can draw."""

    def test_every_preset_at_every_hour_resolves_to_registered_settings(self):
        for p in presets.FOREST_PRESETS:
            for real_sky in (False, True):
                cfg = dict(p.values(), **(dict.fromkeys(presets.SKY, "auto") if real_sky else {}))
                for n in range(0, 24 * 40, 7):  # (forty days, for Surprise me daily's turns)
                    now = dt.datetime(2026, 10, 1) + dt.timedelta(hours=n)
                    m = scene.choose_mood(cfg, now)
                    where = f"{p.key} at {now}"
                    self.assertIn(m["environment"], scene.ENVIRONMENTS, where)
                    self.assertEqual(m["special"], m["environment"], where)
                    self.assertIn(m["landscape"], scene.LANDSCAPES, where)
                    self.assertIn(m["landmark"], scene.LANDMARKS, where)
                    self.assertIn(m["weather"], scene.WEATHERS, where)
                    self.assertIn(m["time"], scene.TIMES, where)
                    self.assertTrue(0 <= m["moon"] <= 1, where)  # (1 rounds a moon about to be new: as 0)

    def test_a_days_scene_holds_all_day_but_the_hour(self):
        for p in presets.FOREST_PRESETS:
            cfg = dict(p.values(), time_of_day="auto")
            morning, evening = (scene.choose_mood(cfg, dt.datetime(2026, 10, 20, h)) for h in (9, 21))
            for k in ("environment", "landscape", "landmark", "weather", "wind"):
                self.assertEqual(morning[k], evening[k], f"{p.key}: {k}")

    def test_a_scenery_this_copy_lacks_is_drawn_as_the_default(self):
        # a Plus config read by the base edition, or a scenery since removed
        m = scene.choose_mood({"environment": "no_such_scenery", "landscape": "nowhere", "landmark": "nothing",
                               "weather": "clear", "time_of_day": "day"}, dt.datetime(2026, 10, 20, 12))
        base = presets.FOREST_PRESETS[0]
        self.assertEqual((m["environment"], m["landscape"], m["landmark"]), (base.environment, base.landscape, base.landmark))


# the scripts a scene is drawn with, which must draw the same day the same way every time: no
# random numbers, no reading the clock (the frame's time comes from core.js)
DRAWING = ("layout.js", "scenery.js", "theme.js", "visitors.js", "ponds.js", "effects.js")
DRAWING_DIRS = ("engines/pixel", "effects", "events", "landscapes", "landmarks")
# (core.js's clock; the engine's time budget for drawing sprites, which core.js redraws after)
CLOCK_ALLOWED = {"engines/pixel/engine.js": "performance.now"}
NONDETERMINISTIC = re.compile(r"Math\.random\s*\(|Date\.now\s*\(|new Date\s*\(\s*\)|performance\.now\s*\(")


class DeterministicScriptTests(unittest.TestCase):
    def test_the_scenery_scripts_read_no_randomness_and_no_clock(self):
        files = list(DRAWING) + [f"envs/{e}.js" for e in shipped_envs()]
        for d in DRAWING_DIRS:
            files += [f"{d}/{n}" for n in sorted(os.listdir(os.path.join(catalog.WEB, d))) if n.endswith(".js")]
        found = []
        for rel in files:
            path = os.path.join(catalog.WEB, rel)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    code = line.split("//")[0]
                    for m in NONDETERMINISTIC.finditer(code):
                        if CLOCK_ALLOWED.get(rel) and m.group().startswith(CLOCK_ALLOWED[rel]):
                            continue
                        found.append(f"web/{rel}:{i}: {m.group()}")
        self.assertEqual(found, [], "a scene must draw the same day the same way: use AF.u.rng(seed) and the frame's t")


def fingerprint(values) -> str:
    return hashlib.sha1(json.dumps(values, separators=(",", ":")).encode()).hexdigest()[:16]


def made_up_trees(n: int) -> list:
    """n trees planted on consecutive days but for a break of 12 days a third of the way in
    (a pond), with their real seeds: what the layout places."""
    out, day = [], 50000
    for i in range(n):
        day += 13 if i == n // 3 and n > 20 else 1
        t = forest_data.make_tree(day, 60000 - day, "2026-01-01", 20, 3, 0, 0.9, 30.0, 0)
        if i == n // 3 and n > 20:
            t["gap"] = 12
        out.append(t)
    return out


class StableSeedTests(unittest.TestCase):
    """Every forest's trees take their shape and their place from these numbers, so a change to
    any of them changes every user's forest at once: a tree that moves, or grows another shape
    overnight. If the change is meant, update the fingerprint (and say so in the release notes)."""

    SEEDS = "1ae998a53b3f231c"
    JS_RANDOM = "a4309b873b70d7cb"
    LAYOUT = "3ed7e4935c1f05ff"

    def test_a_trees_seed_never_changes(self):
        seeds = [forest_data._seed(day) for day in range(0, 200000, 97)]
        self.assertEqual(fingerprint(seeds), self.SEEDS)
        # and only its day decides it
        a = forest_data.make_tree(41000, 3, "2026-10-15", 10, 2, 0, 0.9, 3.0, 0)
        b = forest_data.make_tree(41000, 900, "2024-01-01", 99, 5, 3, 0.1, 400.0, 50)
        self.assertEqual((a["seed"], a["kind"]), (b["seed"], b["kind"]))

    def node(self, script: str, data) -> object:
        if not shutil.which("node"):
            self.skipTest("no node")
        prelude = ("const vm = require('vm'), fs = require('fs'), ctx = { Math, console }; ctx.window = ctx;"
                   "vm.createContext(ctx); for (const f of ['util.js', 'layout.js'])"
                   f" vm.runInContext(fs.readFileSync({json.dumps(catalog.WEB)} + '/' + f, 'utf8'), ctx);"
                   "const AF = ctx.AnkiForest, data = JSON.parse(fs.readFileSync(0, 'utf8'));")
        run = subprocess.run(["node", "-e", prelude + script], input=json.dumps(data), capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_the_pages_random_numbers_never_change(self):
        got = self.node("const out = data.map(s => { const r = AF.u.rng(s); return [r(), r(), r()].map(v => v.toFixed(9)); });"
                        "out.push(['abc', 'tree-7', ''].map(AF.u.hashStr)); console.log(JSON.stringify(out));",
                        [1, 2, 42, 123456789, 2147483647])
        self.assertEqual(fingerprint(got), self.JS_RANDOM)

    def test_the_trees_keep_their_places(self):
        # (the layout alone: where the landscape then puts the rows is e2e/render_check.py's)
        forests = [made_up_trees(n) for n in (1, 5, 30, 200, 731)]
        got = self.node("console.log(JSON.stringify(data.map(trees => { const L = AF.layout(trees);"
                        " return [L.perRow, L.rows, +L.zoom.toFixed(6), L.items.map(i => [i.pond ? 1 : 0, i.cell,"
                        " +i.x.toFixed(6), +i.depth.toFixed(6), +i.jy.toFixed(6)])]; })));", forests)
        self.assertEqual(fingerprint(got), self.LAYOUT)


BASELINE = os.path.join(ADDON, "e2e", "render_baseline.json")


@unittest.skipUnless(os.path.exists(BASELINE), "no e2e/render_baseline.json here (it is kept locally only)")
class RenderBaselineTests(unittest.TestCase):
    """npm run compare tells a scenery that changed by its pictures in e2e/render_baseline.json:
    a shipped scenery with no picture there can change unnoticed."""

    def test_every_shipped_scenery_has_its_pictures_in_every_sky(self):
        with open(BASELINE, encoding="utf-8") as f:
            baseline = json.load(f)
        lands = (set().union(*(editions.scenery(n)["landscapes"] for n in editions.available()))
                 if editions.available() else set(scene.LANDSCAPES))
        missing = []
        for env in shipped_envs():
            names = [f"{env}-{land}" for land in sorted(lands)] + [f"{env}-at-{t}" for t in scene.TIMES]
            names += [f"{env}-in-{w}" for w in scene.WEATHERS]
            names += [f"preset-{p.key}" for p in presets.FOREST_PRESETS if p.environment == env]
            missing += [n for n in names if n not in baseline]
        self.assertEqual(missing, [], "record them: npm run baseline -- --only <scenery>")


class PickerTileTests(unittest.TestCase):
    def test_every_picker_tile_is_the_same_size(self):
        # a tile drawn at another size sits askew in the picker's grid
        folder = os.path.join(ADDON, "settings")
        sizes = {}
        for p in presets.FOREST_PRESETS:
            if p.key == presets.DAILY:
                continue
            for sub, ext in (("scenery", "png"), ("scenery_anim", "gif")):
                path = os.path.join(folder, sub, f"{p.key}.{ext}")
                if not os.path.exists(path):
                    continue  # (test_presets.py asks for the missing ones)
                with open(path, "rb") as f:
                    head = f.read(24)
                size = struct.unpack(">II", head[16:24]) if ext == "png" else struct.unpack("<HH", head[6:10])
                sizes.setdefault(sub, {}).setdefault(size, []).append(p.key)
        for sub, by_size in sizes.items():
            self.assertEqual(len(by_size), 1, f"{sub} tiles come in several sizes: {by_size}")


if __name__ == "__main__":
    unittest.main()

"""The heatmap's look (heatmap_look.py): the Heatmap tab's colours and tiles as the config keeps
them, what the page is handed to draw with, and the sums the settings' pictures share with
web/calendar.js."""

from __future__ import annotations

import json
import os
import unittest

from fake_anki import ADDON_DIR, addon, reset

HL = addon.heatmap_look
payload = addon.payload
GOLDEN = {"special": "natural"}  # (Golden lake's environment)


def shipped_envs() -> list:
    """The environments an edition ships: editions.json's, or (the public copy) every one here."""
    try:
        with open(os.path.join(ADDON_DIR, "editions.json"), encoding="utf-8") as f:
            eds = json.load(f)
        return sorted({e for name in ("base", "plus") for e in eds[name]["envs"]})
    except OSError:
        return sorted({"natural", *addon.catalog.entries("envs")})


class ChoiceTests(unittest.TestCase):
    def test_the_defaults_are_today_s_heatmap(self):
        look = HL.page_look({}, GOLDEN)
        self.assertEqual((look["colours"], look["env"], look["tile"], look["files"]), (None, None, "flat", []))
        self.assertFalse(look["exact"])
        self.assertTrue(look["smooth"] and look["gaps"])  # (Flat's own: smooth corners, spaces)

    def test_a_value_it_can_t_use_is_the_default(self):
        # (another scenery's colours, "scenery:aurora", were cut: the scenery's own instead)
        for bad in ("nonsense", "ready:purple", "scenery:aurora", 7, None, ["x"]):
            self.assertEqual(HL.colours_choice({"calendar_colours": bad}), HL.MATCH)
        for gone in ("chalk", "plain", "smooth"):  # (Plain and Smooth were cut: Flat)
            self.assertEqual(HL.tiles_choice({"calendar_tiles": gone}), "flat")
        self.assertEqual(HL.mine({"calendar_mine": ["#ABCDEF", "red"]}), ["#abcdef", HL.MINE_DEFAULT[1]])
        self.assertEqual(HL.mine({"calendar_mine": "#123456"}), HL.MINE_DEFAULT)

    def test_a_ready_ramp_and_your_colours_are_drawn_as_picked(self):
        look = HL.page_look({"calendar_colours": "ready:flame"}, GOLDEN)
        self.assertEqual(look["colours"], HL.READY["flame"])
        self.assertTrue(look["exact"])
        mine = {"calendar_colours": "mine", "calendar_mine": ["#112233", "#445566"]}
        self.assertEqual(HL.page_look(mine, GOLDEN)["colours"], "#112233")
        self.assertEqual(HL.page_look(dict(mine, calendar_mine_two=True), GOLDEN)["colours"], ["#112233", "#445566"])

    def test_a_scenery_s_colours_among_the_ready_ones_are_shaded_as_the_scenery_s(self):
        look = HL.page_look({"calendar_colours": "ready:aurora"}, GOLDEN)
        self.assertEqual(look["colours"], HL.own_keys()["aurora"])
        self.assertFalse(look["exact"])
        self.assertEqual(look["files"], [])  # (its colour comes from KEYS_FILE, not its scenery's file)

    def test_tiles(self):
        self.assertEqual(HL.page_look({"calendar_tiles": "scanlines"}, GOLDEN)["files"], ["envs/synthwave.js"])
        self.assertEqual(HL.page_look({"calendar_tiles": "scanlines"}, {"special": "synthwave"})["files"], [])
        for plain in ("flat", "round", "contours"):
            look = HL.page_look({"calendar_tiles": plain}, GOLDEN)
            self.assertEqual((look["tile"], look["files"]), (plain, []))

    def test_plus_sceneries_are_locked_in_the_base_edition(self):
        base = {"debug": True, "debug_edition": "base", "calendar_tiles": "brush"}
        if not os.path.exists(HL.edition_presets.__globals__["EDITIONS_FILE"]):
            base = {k: v for k, v in base.items() if not k.startswith("debug")}  # (the public copy: it has no Plus files)
        look = HL.page_look(base, GOLDEN)
        self.assertEqual((look["colours"], look["env"], look["tile"], look["files"]), (None, None, "flat", []))

    def test_light_page_shades_are_the_debug_tab_s_only_while_debug_is_on(self):
        self.assertFalse(HL.page_look({"debug_light_shades": "dark"}, GOLDEN)["lightSame"])
        reset(config={"debug": True})
        self.assertEqual(HL.light_shades({"debug": True, "debug_light_shades": "dark"}) == "dark",
                         addon.edition.debug_available({"debug": True}))

    def test_each_tile_style_has_its_own_spaces_and_corners_but_while_debugging(self):
        for style, (gaps, smooth) in HL.TILE_STYLE.items():
            cfg = {"calendar_tiles": style, "debug_gaps": not gaps, "debug_smooth": not smooth}  # (debug off: ignored)
            self.assertEqual((HL.gaps(cfg), HL.smooth(cfg)), (gaps, smooth), style)
        self.assertFalse(HL.gaps({"calendar_tiles": "contours"}))
        debugging = addon.edition.debug_available({"debug": True})
        self.assertEqual(HL.gaps({"debug": True, "debug_gaps": False}), not debugging)
        self.assertTrue(HL.gaps({"debug": True, "debug_gaps": None}))  # (None: the style's own)

    def test_a_seasonal_scenery_s_colours_are_offered_only_in_its_week(self):
        out = {"debug_date": "2026-07-01", "debug": True}
        inside = {"debug_date": "2026-10-28", "debug": True}
        if not addon.edition.debug_available({"debug": True}):
            self.skipTest("the debug date needs debug")
        self.assertFalse(HL.scenery_ready_shown("pumpkin_patch", out))
        self.assertTrue(HL.scenery_ready_shown("pumpkin_patch", inside))
        self.assertTrue(HL.scenery_ready_shown("aurora", out))
        no_date = {"debug": True}  # (the real date: not every season at once)
        in_week = HL.presets.unlocked(HL.presets.by_key()["pumpkin_patch"], HL.today(no_date))
        self.assertEqual(HL.scenery_ready_shown("pumpkin_patch", no_date), in_week)
        self.assertIsNone(HL.page_look(dict(out, calendar_colours="ready:pumpkin_patch"), GOLDEN)["colours"])

    def test_a_seasonal_scenery_s_choices_go_when_its_week_is_over(self):
        if not addon.edition.debug_available({"debug": True}):
            self.skipTest("the debug date needs debug")
        chosen = {"calendar_colours": "ready:pumpkin_patch", "calendar_tiles": "pumpkin", "debug": True}
        self.assertEqual(HL.out_of_season(dict(chosen, debug_date="2026-10-28")), {})
        self.assertEqual(HL.out_of_season(dict(chosen, debug_date="2026-11-02")), {"calendar_colours": "scenery", "calendar_tiles": "flat"})
        self.assertFalse(HL.tile_shown("pumpkin", {"debug": True, "debug_date": "2026-07-01"}))
        self.assertEqual(HL.tile_env({"calendar_tiles": "pumpkin", "debug": True, "debug_date": "2026-07-01"}), "flat")
        self.assertEqual(HL.out_of_season({"calendar_colours": "ready:aurora", "calendar_tiles": "brush"}), {})  # (not seasonal)


class TileFileTests(unittest.TestCase):
    def test_each_tile_style_s_files_say_what_the_tab_needs(self):
        web = os.path.join(ADDON_DIR, "web")
        scripts = set(addon.catalog.SCRIPTS) | set(addon.catalog.draft_scripts())
        for key, spec in HL.TILE_SPECS.items():
            self.assertTrue(spec.get("label") and spec.get("tip"), key)
            if spec.get("env"):
                self.assertTrue(os.path.exists(os.path.join(web, "envs", f"{spec['env']}.js")) or HL.plus_locked(spec["env"], {}), key)
            else:  # (a style that draws itself has its script loaded, and it registers under its key)
                rel = next((s for s in scripts if s.endswith(f"heatmap/{key}.js")), None)
                self.assertIsNotNone(rel, f"{key}: no web/heatmap/{key}.js")
                with open(os.path.join(web, rel), encoding="utf-8") as f:
                    self.assertIn(f"AF.heatmapTiles.{key} =", f.read(), key)

    def test_a_release_s_tiles_never_come_from_the_drafts(self):
        released = {n[:-5] for n in os.listdir(os.path.join(ADDON_DIR, "web", "heatmap")) if n.endswith(".json")}
        self.assertTrue({"flat", "round", "contours"} <= released)
        self.assertNotIn("glass", released)  # (it waits for its scenery: web/drafts/heatmap/)
        drafts = [k for k, v in HL.TILE_SPECS.items() if v.get("draft")]
        for edition in ("base", "plus"):  # (nor while the Debug tab pretends this is a release)
            pretend = {"debug": True, "debug_edition": edition}
            if addon.edition.debug_available(pretend) and HL.debug_edition(pretend):
                self.assertEqual([k for k in drafts if HL.tile_shown(k, pretend)], [], edition)


class SceneryColourTests(unittest.TestCase):
    def test_every_shipped_scenery_has_its_own_colour_listed(self):
        keys = HL.own_keys()
        for env in shipped_envs():
            self.assertIn(env, keys, f"{env} has no colour in settings/heatmap_keys.json: npm run heatmap-keys")


class ShadeTests(unittest.TestCase):
    DARK, LIGHT = HL.PAGES["dark"], HL.PAGES["light"]

    def test_colours_you_pick_are_the_same_on_either_page(self):
        for colours in (["#2a9d8f", "#e9c46a"], HL.READY["flame"]):
            for bg, dark in ((self.DARK, True), (self.LIGHT, False)):
                steps = HL.exact_steps(colours, bg, dark)
                self.assertEqual(HL.to_hex(steps[3]), colours[1])  # the busiest exactly the second
                self.assertEqual(HL.to_hex(steps[1]), HL.to_hex(HL.blend(HL.hexc(colours[0]), HL.hexc(colours[1]), 1 / 3)))

    def test_one_colour_runs_from_dim_to_full_keeping_its_hue(self):
        steps = HL.exact_steps("#3366cc", self.LIGHT, False)
        self.assertEqual(HL.to_hex(steps[3]), "#3366cc")
        self.assertGreater(HL.apart(steps[0], steps[3]), HL.apart(steps[2], steps[3]))

    def test_the_faintest_shade_stands_clear_of_an_empty_day(self):
        empty = HL.empty_on(self.DARK, True)
        for colours in ("#468478", "#627a9c", "#808080"):  # Misty valley's, Aurora's, a grey
            self.assertGreaterEqual(HL.apart(HL.shades(colours, self.DARK, True)[0][0], empty), HL.EMPTY_APART - 1e-6)
        self.assertGreaterEqual(HL.apart(HL.shades(["#2a9d8f", "#e9c46a"], self.DARK, True, exact=True)[0][0], empty), HL.EMPTY_APART - 1e-6)

    def test_a_light_page_can_take_the_dark_page_s_shades(self):
        self.assertEqual(HL.shades("#8fb35e", self.LIGHT, False, light_same=True), HL.shades("#8fb35e", self.DARK, True))

    def test_busier_days_darker_turns_only_a_dark_page_s_shades_round(self):
        self.assertFalse(HL.page_look({}, GOLDEN)["darker"])
        self.assertTrue(HL.page_look({"calendar_busier": "darker"}, GOLDEN)["darker"])
        lighter = HL.shades("#8fb35e", self.DARK, True)
        self.assertEqual(HL.shades("#8fb35e", self.DARK, True, darker=True), lighter[::-1])
        self.assertEqual(HL.shades("#8fb35e", self.LIGHT, False, darker=True), HL.shades("#8fb35e", self.LIGHT, False))

    def test_a_pale_colour_is_said_to_be_hard_to_see_on_a_light_page(self):
        self.assertEqual(HL.faint_on("#f6efb0"), ["light"])
        self.assertEqual(HL.faint_on(["#000000", "#1a1a1a"]), ["dark"])
        self.assertEqual(HL.faint_on(HL.READY["green"]), [])

    def test_the_shade_steps_are_calendar_js_s(self):
        with open(os.path.join(ADDON_DIR, "web", "calendar.js"), encoding="utf-8") as f:
            js = f.read()
        for name in ("LIGHT_STEPS", "DARK_STEPS", "DARK_CHROMA"):
            self.assertIn(f"{name} = [{', '.join(str(v) for v in getattr(HL, name))}]", js, name)

    def test_the_hash_is_calendar_js_s(self):
        self.assertEqual(HL.hash_str("0,1,2"), 3119553578)  # (hashStr('0,1,2') in web/util.js)


class PayloadTests(unittest.TestCase):
    def test_the_calendar_carries_the_look(self):
        reset([(1, 10, 3)], {"calendar_colours": "ready:ice", "calendar_tiles": "round"})
        look = payload.payload()["calendar"]["look"]
        self.assertEqual((look["colours"], look["tile"]), (HL.READY["ice"], "round"))


if __name__ == "__main__":
    unittest.main()

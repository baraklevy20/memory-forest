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
        self.assertEqual((look["colours"], look["tile"], look["files"]), (None, "flat", []))
        self.assertFalse(look["exact"])
        self.assertTrue(look["smooth"] and look["gaps"])  # (Flat's own: smooth corners, spaces)

    def test_a_value_it_can_t_use_is_the_default(self):
        # (another scenery's colours, "scenery:aurora", were cut: the scenery's own instead)
        for bad in ("nonsense", "ready:purple", "scenery:aurora", 7, None, ["x"]):
            self.assertEqual(HL.colours_choice({"calendar_colours": bad}), HL.MATCH)
        for bad in ("no_such_style", 7, None):  # (a style it doesn't have: the scenery's own)
            self.assertEqual(HL.tiles_choice({"calendar_tiles": bad}), HL.TILE_FOLLOW)
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

    def test_scenery_s_style_follows_the_scenery_and_a_chosen_one_stays(self):
        lanterns = {"special": "lanterns"}
        look = HL.page_look({}, lanterns)
        self.assertEqual((look["tile"], look["smooth"], look["gap"]), ("round", True, 2))
        self.assertEqual(HL.page_look({"calendar_tiles": "flat"}, lanterns)["tile"], "flat")
        starry, synth = {"special": "starry_night"}, {"special": "synthwave"}
        # The public/base copy lacks Starry Night: its tiles fall back to Flat.
        has_starry = os.path.isfile(os.path.join(ADDON_DIR, "web", "envs", "starry_night.js"))
        self.assertEqual(HL.page_look({}, starry)["tile"], "starry_night" if has_starry else "flat")
        self.assertEqual(HL.page_look({}, synth)["tile"], "synthwave")
        self.assertEqual(HL.page_look({}, GOLDEN)["tile"], "flat")  # (a scenery with no style of its own)
        self.assertEqual(HL.page_look({"calendar_tiles": "flat"}, starry)["tile"], "flat")  # (chosen: kept)
        self.assertEqual(HL.tile_style({"calendar_tiles": "scenery"}, "starry_night"), "brush" if has_starry else "flat")
        self.assertEqual(HL.gaps({}, "starry_night"), HL.TILE_STYLE["brush" if has_starry else "flat"][0])

    def test_the_space_between_tiles_is_the_style_s_own(self):
        # (Round keeps its 2: its circles apart; the rest calendar.js's own)
        self.assertEqual(HL.page_look({"calendar_tiles": "round"}, GOLDEN)["gap"], 2)
        self.assertIsNone(HL.page_look({"calendar_tiles": "flat"}, GOLDEN)["gap"])
        self.assertIsNone(HL.page_look({"debug": True, "debug_tile_gap": 4}, GOLDEN)["gap"])  # (no debug setting)

    def test_tiles(self):
        self.assertEqual(HL.page_look({"calendar_tiles": "scanlines"}, GOLDEN)["files"], ["envs/synthwave.js"])
        self.assertEqual(HL.page_look({"calendar_tiles": "scanlines"}, {"special": "synthwave"})["files"], [])
        for plain in ("flat", "round", "contours"):
            look = HL.page_look({"calendar_tiles": plain}, GOLDEN)
            self.assertEqual((look["tile"], look["files"]), (plain, []))

    def test_plus_sceneries_are_locked_in_the_base_edition(self):
        base = {"debug": True, "debug_edition": "base"}
        if not os.path.exists(HL.edition_presets.__globals__["EDITIONS_FILE"]):
            base = {}  # (the public copy: it has no Plus files)
        locked = [k for k, env in HL.TILE_ENVS.items() if HL.plus_locked(env, base)]
        if not locked:
            self.skipTest("no tile style is a Plus scenery's just now")
        for key in locked:
            look = HL.page_look({**base, "calendar_tiles": key}, GOLDEN)
            self.assertEqual((look["colours"], look["tile"], look["files"]), (None, "flat", []), key)

    def test_only_a_ready_ramp_runs_the_other_way_on_a_light_page(self):
        self.assertTrue(HL.page_look({"calendar_colours": "ready:ice"}, GOLDEN)["flipLight"])
        mine = {"calendar_colours": "mine", "calendar_mine": ["#112233", "#445566"], "calendar_mine_two": True}
        self.assertFalse(HL.page_look(mine, GOLDEN)["flipLight"])  # (your own: as you picked them)
        self.assertFalse(HL.page_look({}, GOLDEN)["flipLight"])

    def test_each_tile_style_has_its_own_spaces_and_corners_but_while_debugging(self):
        for style in HL.TILE_STYLE:
            # (each as the style it draws in: Scenery's, or one out of its week, Flat's here)
            gaps, smooth = HL.TILE_STYLE[HL.tile_style({"calendar_tiles": style})]
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
        self.assertEqual(HL.out_of_season(dict(chosen, debug_date="2026-11-02")), {"calendar_colours": "scenery", "calendar_tiles": "scenery"})
        self.assertFalse(HL.tile_shown("pumpkin", {"debug": True, "debug_date": "2026-07-01"}))
        self.assertEqual(HL.tile_env({"calendar_tiles": "pumpkin", "debug": True, "debug_date": "2026-07-01"}), "flat")
        # (the scenery's own, as Scenery is: Lanterns wears Round)
        self.assertEqual(HL.tile_env({"calendar_tiles": "pumpkin", "debug": True, "debug_date": "2026-07-01"}, "lanterns"), "round")
        self.assertEqual(HL.out_of_season({"calendar_colours": "ready:aurora", "calendar_tiles": "brush"}), {})  # (not seasonal)

    def test_debugging_with_no_date_a_holiday_scenery_wears_its_own_tiles(self):
        # (its scenery is offered then whatever the day, seasons.offer_day: its pumpkins come with it,
        # not Flat outside its week)
        if not addon.edition.debug_available({"debug": True}):
            self.skipTest("the debug date needs debug")
        self.assertEqual(HL.tile_env({"debug": True}, "pumpkin_patch"), "pumpkin_patch")
        self.assertEqual(HL.tile_env({"debug": True, "debug_date": "2026-07-01"}, "pumpkin_patch"), "flat")


class TileFileTests(unittest.TestCase):
    def test_each_tile_style_s_files_say_what_the_tab_needs(self):
        web = os.path.join(ADDON_DIR, "web")
        scripts = set(addon.catalog.SCRIPTS) | set(addon.catalog.draft_scripts())
        for key, spec in HL.TILE_SPECS.items():
            self.assertTrue(spec.get("label") and spec.get("tip"), key)
            if spec.get("follow"):  # (Scenery: no drawing of its own, the scenery's)
                continue
            if spec.get("env"):
                self.assertTrue(os.path.exists(os.path.join(web, "envs", f"{spec['env']}.js")) or HL.plus_locked(spec["env"], {}), key)
            else:  # (a style that draws itself has its script loaded, and it registers under its key)
                rel = next((s for s in scripts if s.endswith(f"heatmap/{key}.js")), None)
                self.assertIsNotNone(rel, f"{key}: no web/heatmap/{key}.js")
                with open(os.path.join(web, rel), encoding="utf-8") as f:
                    self.assertIn(f"AF.heatmapTiles.{key} =", f.read(), key)

    def test_a_style_s_smooth_corners_go_to_the_page_from_its_file(self):
        # (round.json holds them alone; calendar.js reads them from the look)
        look = HL.page_look({"calendar_tiles": "round"}, GOLDEN)
        spec = HL.TILE_SPECS["round"]
        self.assertEqual((look["smoothRadius"], look["smoothGrow"]), (spec["smoothRadius"], spec["smoothGrow"]))
        self.assertNotIn("smoothRadius", HL.page_look({"calendar_tiles": "flat"}, GOLDEN))

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

    def test_the_listed_colours_are_the_sceneries_own(self):
        # (a scenery recoloured since the files were written draws the Heatmap tab's pictures wrong)
        import re
        for env in shipped_envs():
            path = os.path.join(ADDON_DIR, "web", "envs", f"{env}.js")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                js = f.read()
            for name, listed in (("calendar", HL.own_keys().get(env)), ("calendarDay", (HL.own_hours().get(env) or {}).get("day"))):
                found = re.search(rf"^\s*{name}: (\[[^\]]*\]|'#[0-9a-fA-F]{{6}}'),", js, re.M)
                if found:
                    self.assertEqual(listed, json.loads(found.group(1).replace("'", '"')),
                                     f"{env}'s {name} has changed: npm run heatmap-keys")


    def test_chalkboard_s_colours_are_offered_where_chalkboard_is(self):
        for edition, env in (("plus", "chalkboard"), ("base", None)):
            pretend = {"debug": True, "debug_edition": edition}
            if addon.edition.debug_available(pretend) and HL.debug_edition(pretend):
                self.assertEqual(HL.scenery_ready_env("chalkboard", pretend), env, edition)


class HourTests(unittest.TestCase):
    """The Heatmap tab's pictures wear a scenery's colours at the forest's hour, as calendar.js
    hourOf does (a check against calendar.js itself matched every shipped scenery at every hour)."""

    def test_the_hour_s_numbers_are_calendar_js_s(self):
        with open(os.path.join(ADDON_DIR, "web", "calendar.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("HOUR_TURN = { dusk: 0.1, night: 0.35 }, AFTER_DARK = ['dusk', 'night']", js)
        self.assertIn("DAY_SHARE = { dawn: 0.5, day: 1, golden_hour: 0.5 }", js)
        self.assertEqual(HL.HOUR_TURN, {"dusk": 0.1, "night": 0.35})
        self.assertEqual(HL.DAY_SHARE, {"dawn": 0.5, "day": 1, "golden_hour": 0.5})

    def test_a_day_scenery_keeps_its_colours_while_the_sun_is_up_and_cools_after_dark(self):
        for time in ("dawn", "day", "golden_hour"):
            self.assertIsNone(HL.hour_of("natural", time))
        self.assertEqual(HL.hour_of("natural", "night")["turn"], 0.35)
        self.assertEqual(HL.hour_of("natural", "dusk")["turn"], 0.1)

    def test_a_night_scenery_wears_its_day_colours_by_day(self):
        day = HL.own_hours()["aurora"]["day"]
        self.assertEqual(HL.hour_of("aurora", "day"), {"to": day, "share": 1})
        self.assertEqual(HL.hour_of("aurora", "golden_hour"), {"to": day, "share": 0.5})
        self.assertIsNone(HL.hour_of("aurora", "night"))

    def test_synthwave_wears_each_hour_s_own(self):
        self.assertEqual(HL.hour_of("synthwave", "day")["to"], HL.own_hours()["synthwave"]["hours"]["day"])
        self.assertIsNone(HL.hour_of("synthwave", "dusk"))  # (its own colours at the rest)

    def test_the_scenery_s_own_colours_follow_the_hour_and_chosen_ones_stay(self):
        dark = (HL.PAGES["dark"], True)
        plain = HL.shades(HL.scenery_own("aurora"), *dark)
        look = HL.preview_look({}, "aurora", "day")
        self.assertNotEqual(HL.shades(look["colours"], *dark, hour=look["hour"]), plain)
        self.assertIsNone(HL.preview_look({}, "aurora", "night")["hour"])
        self.assertNotIn("hour", HL.preview_look({"calendar_colours": "ready:aurora"}, "natural", "day"))
        self.assertNotIn("hour", HL.preview_look({"calendar_colours": "ready:flame"}, "aurora", "day"))


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

    def test_a_ready_ramp_s_busiest_day_is_its_deep_colour_on_a_light_page(self):
        ice = HL.READY["ice"]
        light = HL.shades(ice, self.LIGHT, False, exact=True, flip_light=True)
        self.assertEqual(light[3][0], HL.hexc(ice[0]))  # (the busiest: deep blue)
        self.assertEqual(HL.shades(ice, self.DARK, True, exact=True, flip_light=True)[3][0], HL.hexc(ice[1]))  # (dark: pale)

    def test_busier_days_darker_turns_only_a_dark_page_s_shades_round(self):
        self.assertFalse(HL.page_look({}, GOLDEN)["darker"])
        self.assertTrue(HL.page_look({"calendar_busier": "darker"}, GOLDEN)["darker"])
        lighter = HL.shades("#8fb35e", self.DARK, True)
        self.assertEqual(HL.shades("#8fb35e", self.DARK, True, darker=True), lighter[::-1])
        self.assertEqual(HL.shades("#8fb35e", self.LIGHT, False, darker=True), HL.shades("#8fb35e", self.LIGHT, False))

    def test_a_pale_colour_is_said_to_be_hard_to_see_on_a_light_page(self):
        self.assertEqual(HL.faint_on("#f6efb0"), ["light"])
        self.assertEqual(HL.faint_on(["#000000", "#1a1a1a"]), ["dark"])
        self.assertEqual(HL.faint_on(["#1e6823", "#378f36"]), [])

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

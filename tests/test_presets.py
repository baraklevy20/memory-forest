"""The presets, and matching a config back to one."""

from __future__ import annotations

import datetime
import json
import os
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import presets
import scene


class PresetTests(unittest.TestCase):
    """A preset is a shortcut that fills the five look settings, so each of the five has
    to be something the dialog would have offered anyway."""

    def test_every_preset_names_settings_that_exist(self):
        D = presets.DAILY
        for p in presets.FOREST_PRESETS:
            self.assertIn(p.environment, set(scene.ENVIRONMENTS) | {D}, p.key)
            self.assertIn(p.landscape, set(scene.LANDSCAPES) | {D}, p.key)
            self.assertIn(p.landmark, set(scene.LANDMARKS) | {D}, p.key)
            self.assertIn(p.weather, set(scene.WEATHERS) | {D}, p.key)
            self.assertIn(p.time, set(scene.TIMES) | {D}, p.key)

    def test_following_the_real_sky_keeps_the_preset(self):
        # the checkbox swaps a preset's weather and hour for the real ones, not the preset
        for p in presets.FOREST_PRESETS:
            real = dict(p.values(), weather="auto", time_of_day="auto")
            self.assertEqual(presets.match(real), p.key)
            self.assertEqual(presets.apply(p.key, real), real)

    def test_every_preset_has_its_still_and_moving_picture(self):
        # drawn by dev/thumbnails.py (npm run thumbs) and dev/tile_gifs.py: run both for a new
        # preset. Surprise me daily's is a mosaic of others', made as it is shown
        settings = os.path.join(os.path.dirname(presets.__file__), "settings")
        missing = [f"{p.key} ({folder})" for folder, ext in (("scenery", "png"), ("scenery_anim", "gif"))
                   for p in presets.FOREST_PRESETS
                   if p.key != presets.DAILY and not os.path.exists(os.path.join(settings, folder, f"{p.key}.{ext}"))]
        self.assertEqual(missing, [], "run npm run thumbs and dev/tile_gifs.py for " + ", ".join(missing))

    def test_every_environment_is_reachable_from_a_preset(self):
        # an environment no preset offers is one most people will never see
        used = {p.environment for p in presets.FOREST_PRESETS}
        self.assertEqual(set(scene.ENVIRONMENTS) - used, set())

    def test_keys_and_labels_are_unique(self):
        keys = [p.key for p in presets.FOREST_PRESETS]
        self.assertEqual(len(set(keys)), len(keys))
        labels = [p.label for p in presets.FOREST_PRESETS]
        self.assertEqual(len(set(labels)), len(labels))
        self.assertNotIn(presets.CUSTOM, keys)  # Custom is the dropdown's own last row

    def test_a_fresh_install_is_a_preset_and_not_custom(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = json.load(open(os.path.join(here, "config.json"), encoding="utf-8"))
        self.assertNotEqual(presets.match(cfg), presets.CUSTOM,
                            "the shipped config should be one of the presets, or the dialog opens on Custom")

    def test_settings_that_match_nothing_are_custom(self):
        odd = dict(presets.FOREST_PRESETS[1].values(), weather="storm", time_of_day="night")
        self.assertEqual(presets.match(odd), presets.CUSTOM)

    def test_a_mix_starts_from_its_environments_preset(self):
        a, b = presets.FOREST_PRESETS[0], presets.FOREST_PRESETS[1]
        # a preset itself, with nothing changed
        self.assertEqual(presets.nearest(b.values()), (b, []))
        # one setting from another preset: still the first, with that one setting to put back
        landmark = next(p.landmark for p in presets.FOREST_PRESETS if p.landmark != b.landmark)
        mix = dict(b.values(), landmark=landmark)
        self.assertEqual(presets.nearest(mix), (b, ["landmark"]))
        # following the real sky is never a difference
        self.assertEqual(presets.nearest(dict(mix, weather="auto", time_of_day="auto")), (b, ["landmark"]))
        # its own environment decides, however many other settings another scenery shares
        other = next(p for p in presets.FOREST_PRESETS[2:] if p.environment != b.environment and p.landscape != b.landscape)
        borrowed = dict(b.values(), landscape=other.landscape, landmark=other.landmark, weather=other.weather, time_of_day=other.time)
        self.assertEqual(presets.nearest(borrowed)[0], b)
        # nothing in common with any: the first in the catalogue, all five differing
        odd = dict.fromkeys(presets.LOOK, "nothing")
        self.assertEqual(presets.nearest(odd), (a, list(presets.LOOK)))

    def test_a_preset_round_trips_through_match(self):
        for p in presets.FOREST_PRESETS:
            self.assertEqual(presets.match(p.values()), p.key)

    def test_no_two_presets_stand_for_the_same_five_settings(self):
        # two identical presets would be indistinguishable: picking the second would snap
        # the dropdown back to the first
        seen = {}
        for p in presets.FOREST_PRESETS:
            fingerprint = tuple(sorted(p.values().items()))
            self.assertNotIn(fingerprint, seen, f"{p.key} draws the same scene as {seen.get(fingerprint)}")
            seen[fingerprint] = p.key

    def test_picking_a_preset_fills_the_advanced_settings(self):
        """What the drawer shows after picking a preset: that preset's own five settings,
        not the ones that happened to be there before."""
        before = {"environment": "old_env", "landscape": "old_land", "landmark": "old_mark",
                  "weather": "storm", "time_of_day": "dawn"}
        for p in presets.FOREST_PRESETS:
            after = presets.apply(p.key, before)
            self.assertEqual(after, p.values(), p.key)
            self.assertEqual(presets.match(after), p.key)      # and the dropdown still says so

    def test_custom_leaves_the_settings_alone(self):
        before = {"environment": "old_env", "landscape": "old_land", "landmark": "old_mark",
                  "weather": "storm", "time_of_day": "dawn"}
        self.assertEqual(presets.apply(presets.CUSTOM, before), before)
        self.assertEqual(presets.apply("no_such_preset", before), before)

    def test_changing_one_setting_afterwards_makes_it_custom(self):
        after = presets.apply("synthwave", {})
        self.assertEqual(presets.match(after), "synthwave")
        self.assertEqual(presets.match(dict(after, weather="snow")), presets.CUSTOM)


D = datetime.date
PLAIN = presets.Preset("plain", "Plain", "natural", "lake")
OTHER = presets.Preset("other", "Other", "aurora", "lake", weather="snow", time="night")
# a made-up seasonal preset: first out on 24 Oct 2026, its week 24-31 Oct each year
HARVEST = presets.Preset("harvest_week", "Harvest week", "harvest", "meadow", time="dusk",
                        season=(D(2026, 10, 24), (10, 24), (10, 31)))
CATALOGUE = (PLAIN, OTHER, HARVEST)


class SeasonTests(unittest.TestCase):
    """A seasonal preset is there in its week only, from its first year; the forest changes
    to it once in that week, and goes back after unless something else was chosen."""

    def run_days(self, cfg: dict, days: list, record: dict | None = None) -> tuple:
        for day in days:
            change, record = presets.follow_season(cfg, record, day, CATALOGUE)
            cfg = dict(cfg, **change)
        return cfg, record

    def test_a_seasonal_preset_is_there_in_its_week_only(self):
        self.assertNotIn(HARVEST, presets.available(D(2026, 10, 23), CATALOGUE))
        self.assertEqual(presets.hidden_environments(D(2026, 10, 23), CATALOGUE), {"harvest"})
        self.assertIn(HARVEST, presets.available(D(2026, 10, 24), CATALOGUE))
        self.assertIn(HARVEST, presets.available(D(2026, 10, 31), CATALOGUE))
        self.assertNotIn(HARVEST, presets.available(D(2026, 11, 1), CATALOGUE))  # gone with its week
        self.assertEqual(presets.hidden_environments(D(2027, 3, 1), CATALOGUE), {"harvest"})
        self.assertIn(HARVEST, presets.available(D(2027, 10, 24), CATALOGUE))  # and back next year
        self.assertNotIn(HARVEST, presets.available(D(2025, 10, 24), CATALOGUE))  # but not before it arrives

    def test_surprise_me_never_repeats_a_day_round_its_week(self):
        days = [D(2026, 10, 1) + datetime.timedelta(days=n) for n in range(60)]
        picks = [presets.of_the_day(day, CATALOGUE) for day in days]
        self.assertNotIn(HARVEST, picks)
        self.assertTrue(all(a is not b for a, b in zip(picks, picks[1:])))

    def test_surprise_me_never_picks_it_early(self):
        for n in range(60):
            self.assertIsNot(presets.of_the_day(D(2026, 8, 1) + datetime.timedelta(days=n), CATALOGUE), HARVEST)

    def test_nothing_happens_outside_its_week(self):
        cfg = PLAIN.values()
        change, record = presets.follow_season(cfg, None, D(2026, 10, 1), CATALOGUE)
        self.assertEqual(change, {})
        self.assertIsNone(record["active"])

    def test_its_week_brings_it_and_the_day_after_takes_it_back(self):
        cfg = OTHER.values()
        during, record = self.run_days(cfg, [D(2026, 10, 24)])
        self.assertEqual(presets.match(during, CATALOGUE), HARVEST.key)
        still, record = self.run_days(during, [D(2026, 10, 25), D(2026, 10, 31)], record)
        self.assertEqual(presets.match(still, CATALOGUE), HARVEST.key)
        after, record = self.run_days(still, [D(2026, 11, 1)], record)
        self.assertEqual(after, cfg)
        self.assertIsNone(record["active"])

    def test_first_opened_in_the_middle_of_its_week_still_brings_it(self):
        during, _ = self.run_days(PLAIN.values(), [D(2026, 10, 29)])
        self.assertEqual(presets.match(during, CATALOGUE), HARVEST.key)

    def test_changing_it_back_during_the_week_is_respected(self):
        _, record = self.run_days(PLAIN.values(), [D(2026, 10, 24)])
        chosen = OTHER.values()
        later, record = self.run_days(chosen, [D(2026, 10, 25), D(2026, 10, 30)], record)
        self.assertEqual(later, chosen)
        # and whatever was chosen stays once the week is over
        after, _ = self.run_days(later, [D(2026, 11, 1)], record)
        self.assertEqual(after, chosen)

    def test_picked_again_by_hand_it_still_goes_with_its_week(self):
        _, record = self.run_days(PLAIN.values(), [D(2026, 10, 24)])
        _, record = self.run_days(OTHER.values(), [D(2026, 10, 25)], record)
        # picked again, with a landscape of its own: no longer what the week applied
        again = dict(HARVEST.values(), landscape="lake")
        after, record = self.run_days(again, [D(2026, 10, 27), D(2026, 11, 1)], record)
        self.assertEqual(after, PLAIN.values())
        self.assertIsNone(record["active"])

    def test_a_forest_left_in_it_with_no_week_to_go_back_from_gets_the_first_preset(self):
        after, _ = self.run_days(HARVEST.values(), [D(2026, 12, 1)])
        self.assertEqual(presets.match(after, CATALOGUE), PLAIN.key)
        real = dict(HARVEST.values(), weather="auto", time_of_day="auto")
        after, _ = self.run_days(real, [D(2026, 12, 1)])
        self.assertEqual((presets.match(after, CATALOGUE), after["weather"]), (PLAIN.key, "auto"))

    def test_a_clock_put_back_before_its_week_lets_it_happen_again(self):
        # a debug date typed a digit at a time can pass through the week on its way elsewhere
        cfg, record = self.run_days(PLAIN.values(), [D(2026, 10, 30), D(2026, 10, 2)])
        self.assertEqual(cfg, PLAIN.values())
        during, _ = self.run_days(cfg, [D(2026, 10, 24)], record)
        self.assertEqual(presets.match(during, CATALOGUE), HARVEST.key)

    def test_it_comes_again_next_year(self):
        _, record = self.run_days(PLAIN.values(), [D(2026, 10, 24), D(2026, 11, 1)])
        during, _ = self.run_days(PLAIN.values(), [D(2027, 10, 24)], record)
        self.assertEqual(presets.match(during, CATALOGUE), HARVEST.key)

    def test_surprise_me_and_the_real_sky_come_back_as_they_were(self):
        daily = dict.fromkeys(presets.LOOK, presets.DAILY)
        after, _ = self.run_days(daily, [D(2026, 10, 24), D(2026, 11, 1)])
        self.assertEqual(after, daily)
        real = dict(PLAIN.values(), weather="auto", time_of_day="auto")
        during, record = self.run_days(real, [D(2026, 10, 24)])
        self.assertEqual((during["weather"], during["time_of_day"]), ("auto", "auto"))  # the real sky stays on
        after, _ = self.run_days(during, [D(2026, 11, 1)], record)
        self.assertEqual(after, real)

    def test_every_real_season_fits_in_one_year(self):
        for p in presets.FOREST_PRESETS:
            if p.season:
                first, starts, ends = p.season
                self.assertLessEqual(starts, ends, p.key)
                self.assertEqual((first.month, first.day), starts, f"{p.key} first appears on the first day of its week")


class PlusTileTests(unittest.TestCase):
    """The base edition's picker shows the Plus sceneries locked: settings/plus.json lists
    them, and the base build ships their picker tiles (dev/editions.py)."""

    def setUp(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(presets.__file__), "dev"))
        import editions
        self.editions = editions
        if not editions.available():
            self.skipTest("no editions.json: the public repo is one edition")

    def test_the_plus_list_is_up_to_date(self):
        with open(self.editions.PLUS_LIST, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.editions.plus_list_text(), "run npm run thumbs to rewrite settings/plus.json")

    def test_the_base_ships_the_plus_tiles_but_not_their_scenery(self):
        keep = self.editions.scenery("base")
        for entry in self.editions.plus_only():
            key = entry["key"]
            self.assertTrue(self.editions.keeps(f"settings/scenery/{key}.png", keep), key)
            self.assertTrue(self.editions.keeps(f"settings/scenery_anim/{key}.gif", keep), key)
            self.assertFalse(self.editions.keeps(f"web/envs/{key}.js", keep), key)

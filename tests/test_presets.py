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
    """A seasonal preset hides until its first week, then the forest changes to it once
    in its week each year, and goes back after unless it was changed in the meantime."""

    def run_days(self, cfg: dict, days: list, record: dict | None = None) -> tuple:
        for day in days:
            change, record = presets.follow_season(cfg, record, day, CATALOGUE)
            cfg = dict(cfg, **change)
        return cfg, record

    def test_a_seasonal_preset_hides_until_its_first_week(self):
        self.assertNotIn(HARVEST, presets.available(D(2026, 10, 23), CATALOGUE))
        self.assertEqual(presets.hidden_environments(D(2026, 10, 23), CATALOGUE), {"harvest"})
        self.assertIn(HARVEST, presets.available(D(2026, 10, 24), CATALOGUE))
        self.assertIn(HARVEST, presets.available(D(2027, 3, 1), CATALOGUE))  # and stays out of season
        self.assertEqual(presets.hidden_environments(D(2026, 12, 1), CATALOGUE), set())

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

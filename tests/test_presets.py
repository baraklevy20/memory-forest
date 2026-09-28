"""The presets, and matching a config back to one."""

from __future__ import annotations

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

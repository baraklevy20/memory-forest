"""Choosing the day's scene: environment, weather, time, events and the journal."""

from __future__ import annotations

import datetime as dt
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import presets
import scene


class SceneTests(unittest.TestCase):
    NOW = dt.datetime(2026, 9, 19, 15, 0)

    def test_fixed_weather_wins_over_real(self):
        real = {"weather": "rain", "local_time": "2026-09-19T15:00", "sunrise": None, "sunset": None, "windy": False}
        m = scene.choose_mood({"weather": "snow"}, self.NOW, real)
        self.assertEqual((m["weather"], m["source"]), ("snow", "manual"))

    def test_environment_weather_and_time_are_independent(self):
        m = scene.choose_mood({"environment": "aurora", "weather": "snow", "time_of_day": "auto"}, self.NOW)
        # the hour is the clock's, and says so: the phone follows its own
        self.assertEqual((m["special"], m["weather"], m["time"], m["clock"]), ("aurora", "snow", "day", True))
        m = scene.choose_mood({"environment": "synthwave", "weather": "rain", "time_of_day": "dawn"}, self.NOW)
        self.assertEqual((m["special"], m["weather"], m["time"], m["clock"]), ("synthwave", "rain", "dawn", False))

    def test_fixed_time_is_respected_even_for_night_environments(self):
        m = scene.choose_mood({"environment": "lanterns", "time_of_day": "dusk"}, self.NOW)
        self.assertEqual((m["special"], m["time"]), ("lanterns", "dusk"))

    def test_real_weather_used_when_auto(self):
        real = {"weather": "fog", "local_time": "2026-09-19T06:40", "sunrise": "2026-09-19T06:58", "sunset": "2026-09-19T19:12", "windy": False, "temp": 9}
        m = scene.choose_mood({"weather": "auto", "time_of_day": "auto"}, self.NOW, real, {"name": "Berlin", "lat": 52.5})
        self.assertEqual((m["weather"], m["time"], m["source"], m["city"]), ("fog", "dawn", "real", "Berlin"))

    def test_the_real_sky_keeps_time_after_the_weather_was_fetched(self):
        # fetched at 06:40 in a UTC+2 city; four hours later it must be day there, not dawn
        real = {"weather": "clear", "local_time": "2026-09-19T06:40", "utc_offset": 7200, "sunrise": "2026-09-19T06:58",
                "sunset": "2026-09-19T19:12", "windy": False}
        later = dt.datetime(2026, 9, 19, 8, 40, tzinfo=dt.timezone.utc)  # 10:40 in the city
        m = scene.choose_mood({"weather": "auto", "time_of_day": "auto"}, later, real)
        self.assertEqual(m["time"], "day")

    def test_no_city_keeps_the_presets_own_weather(self):
        # the real sky without a city follows only the clock; nothing is made up for the date
        wet = next(p for p in presets.FOREST_PRESETS if p.weather not in ("clear", presets.DAILY))
        cfg = dict(wet.values(), weather="auto", time_of_day="auto")
        for d in range(1, 20):
            self.assertEqual(scene.choose_mood(cfg, dt.datetime(2026, 5, d, 12))["weather"], wet.weather)

    def test_nothing_set_is_the_default_preset(self):
        m = scene.choose_mood({}, self.NOW)
        base = presets.FOREST_PRESETS[0]
        self.assertEqual((m["environment"], m["landscape"], m["landmark"], m["weather"], m["time"]),
                         (base.environment, base.landscape, base.landmark, base.weather, base.time))

    def test_surprise_me_daily_takes_the_presets_in_turn(self):
        daily = presets.by_key()["daily"].values()
        # a stretch after every seasonal preset has first come out, so all of them take turns
        days = [dt.datetime(2027, 1, 10, 12) + dt.timedelta(days=d) for d in range(60)]
        picks = [scene.choose_mood(daily, d)["environment"] for d in days]
        turn = [p for p in presets.available(days[0].date()) if p.key != "daily"]
        self.assertTrue(all(a != b for a, b in zip(picks, picks[1:])), "a new preset every day")
        self.assertEqual(set(picks[:len(turn)]), {p.environment for p in turn}, "every preset comes round")
        # and each day is that preset whole: its landscape, landmark, weather and hour too
        p = presets.of_the_day(days[0].date())
        m = scene.choose_mood(daily, days[0])
        self.assertEqual((m["landscape"], m["weather"], m["time"]), (p.landscape, p.weather, p.time))

    def test_surprise_me_daily_can_follow_the_real_sky(self):
        real = {"weather": "fog", "local_time": "2026-09-19T15:00", "sunrise": None, "sunset": None, "windy": False}
        cfg = dict(presets.by_key()["daily"].values(), weather="auto", time_of_day="auto")
        m = scene.choose_mood(cfg, self.NOW, real)
        self.assertEqual((m["weather"], m["source"]), ("fog", "real"))

    def test_time_of_day(self):
        self.assertEqual([scene.time_of_day(dt.datetime(2026, 9, 19, h)) for h in (3, 7, 12, 19, 23)],
                         ["night", "dawn", "day", "dusk", "night"])

    def test_golden_hour_before_dusk(self):
        self.assertEqual(scene.time_of_day(dt.datetime(2026, 9, 19, 17, 30)), "golden_hour")

    def test_landscape_and_landmark_defaults(self):
        m = scene.choose_mood({}, self.NOW)
        self.assertEqual((m["landscape"], m["landmark"]), ("lake", "none"))
        self.assertEqual(scene.choose_mood({"landscape": "auto"}, self.NOW)["landscape"], "lake")
        m = scene.choose_mood({"landscape": "river", "landmark": "peak"}, self.NOW)
        self.assertEqual((m["landscape"], m["landmark"]), ("river", "peak"))
        # a landmark that no longer exists falls back to the default preset's
        self.assertEqual(scene.choose_mood({"landmark": "gone"}, self.NOW)["landmark"], presets.FOREST_PRESETS[0].landmark)

    def test_sky_events(self):
        self.assertIn("meteor_shower", scene.events({"streak": 100}, dt.date(2026, 5, 1)))
        self.assertIn("meteor_shower", scene.events({"streak": 3}, dt.date(2026, 8, 12)))
        self.assertIn("harvest_moon", scene.events({"forest_age": 730}, dt.date(2026, 5, 1)))
        self.assertEqual(scene.events({"streak": 3, "forest_age": 10}, dt.date(2026, 5, 1), True), ["new_ancient"])

    def test_every_environment_is_its_own_special(self):
        for key in scene.ENVIRONMENTS:
            self.assertEqual(scene.choose_mood({"environment": key}, self.NOW)["special"], key)

    def test_moon_phase(self):
        self.assertAlmostEqual(scene.moon_phase(dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)), 0, places=3)
        self.assertAlmostEqual(scene.moon_phase(dt.datetime(2000, 1, 21, 9, 0, tzinfo=dt.timezone.utc)), 0.5, delta=0.02)

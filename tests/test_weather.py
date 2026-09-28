"""The live weather lookup and its cache."""

from __future__ import annotations

import os
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import weather


class WeatherTests(unittest.TestCase):
    def test_wmo_mapping(self):
        self.assertEqual([weather.map_wmo(c) for c in (0, 3, 45, 61, 81, 73, 96)],
                         ["clear", "cloudy", "fog", "rain", "rain", "snow", "storm"])

    def forecast(self, code=0, is_day=1, precip=(0, 0, 0), wind=5):
        return {
            "current": {"time": "2026-09-19T15:00", "weather_code": code, "is_day": is_day, "temperature_2m": 14.2, "wind_speed_10m": wind},
            "hourly": {"time": ["2026-09-19T13:00", "2026-09-19T14:00", "2026-09-19T15:00", "2026-09-19T16:00"], "precipitation": list(precip) + [5]},
            "daily": {"time": ["2026-09-18", "2026-09-19"], "sunrise": ["x", "2026-09-19T06:58"], "sunset": ["y", "2026-09-19T19:12"]},
        }

    def test_parse_forecast(self):
        w = weather.parse_forecast(self.forecast(wind=40))
        self.assertEqual((w["weather"], w["sunrise"], w["windy"]), ("clear", "2026-09-19T06:58", True))

    def test_recent_rain_then_sun_is_after_rain(self):
        self.assertEqual(weather.parse_forecast(self.forecast(precip=(0, 1.2, 0)))["weather"], "after_rain")
        self.assertEqual(weather.parse_forecast(self.forecast(precip=(0, 1.2, 0), is_day=0))["weather"], "clear")

    def test_cache_refresh_and_offline_fallback(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        cache = weather.WeatherCache(path)
        calls = []

        def fake(url):
            calls.append(url)
            if "geocoding" in url:
                return {"results": [{"name": "Berlin", "latitude": 52.5, "longitude": 13.4}]}
            return self.forecast(code=61)

        self.assertEqual(cache.refresh("Berlin", fake, now=1000)["weather"], "rain")
        self.assertFalse(cache.needs_refresh("berlin ", now=1000 + 60))
        self.assertTrue(cache.needs_refresh("Berlin", now=1000 + weather.MAX_AGE_SECS + 1))

        def offline(url):
            raise OSError("no network")

        self.assertIsNone(cache.refresh("Berlin", offline, now=5000))
        kept = weather.WeatherCache(path)
        self.assertEqual(kept.current("Berlin", now=5000)["weather"], "rain")  # last good kept
        self.assertFalse(cache.needs_refresh("Berlin", now=5000 + 60))  # backs off after failure
        # but it carries the sunrise, sunset and local time of the moment it was fetched,
        # so once it is hours old the real clock and a daily pick are more honest
        self.assertIsNone(kept.current("Berlin", now=1000 + weather.STALE_SECS + 1))
        self.assertIn("no network", kept.failing("Berlin"))

"""The live weather lookup and its cache."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import weather

BERLIN = {"name": "Berlin", "lat": 52.52, "lon": 13.4, "country": "DE"}


def at(iso: str) -> float:
    return dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc).timestamp()


NOW = at("2026-09-19T15:20")  # mid-afternoon in Berlin (sunrise 04:46, sunset 17:14 UTC)
EXPIRES = "Sat, 19 Sep 2026 15:50:00 GMT"


class WeatherTests(unittest.TestCase):
    def test_symbol_mapping(self):
        self.assertEqual([weather.map_symbol(c) for c in ("clearsky_day", "cloudy", "fog", "rain", "lightrainshowers_night",
                                                          "snow", "rainandthunder")],
                         ["clear", "cloudy", "fog", "rain", "rain", "snow", "storm"])
        self.assertEqual([weather.map_symbol(c) for c in ("fair_night", "partlycloudy_day", "lightsleet", "heavysnowshowers_day")],
                         ["clear", "cloudy", "rain", "snow"])

    def forecast(self, symbol="clearsky_day", precip=(0, 0, 0), wind=1.5):
        """A MET compact forecast from 13:00 UTC; `precip` is the rain in each hour from then."""
        hours = ["2026-09-19T13:00:00Z", "2026-09-19T14:00:00Z", "2026-09-19T15:00:00Z", "2026-09-19T16:00:00Z"]
        rain = list(precip) + [5]
        return {"properties": {"timeseries": [
            {"time": h, "data": {"instant": {"details": {"air_temperature": 14.2, "wind_speed": wind}},
                                 "next_1_hours": {"summary": {"symbol_code": symbol}, "details": {"precipitation_amount": mm}}}}
            for h, mm in zip(hours, rain)]}}

    def test_parse_forecast(self):
        sky, rain, _ = weather.parse_forecast(self.forecast(wind=12), NOW)  # 12 m/s = 43 km/h
        w = weather.resolve(sky, rain, BERLIN, NOW)
        self.assertEqual((w["weather"], w["sunrise"], w["windy"]), ("clear", "2026-09-19T04:46+00:00", True))

    def test_recent_rain_then_sun_is_after_rain(self):
        sky, rain, _ = weather.parse_forecast(self.forecast(precip=(0, 1.2, 0)), NOW)
        self.assertEqual(weather.resolve(sky, rain, BERLIN, NOW)["weather"], "after_rain")
        night = at("2026-09-19T21:20")
        self.assertEqual(weather.resolve(sky, {"2026-09-19T20:00:00Z": 1.2}, BERLIN, night)["weather"], "clear")
        self.assertEqual(weather.resolve(sky, {"2026-09-19T12:00:00Z": 1.2}, BERLIN, NOW)["weather"], "clear")  # too long ago

    def test_rain_history_survives_newer_forecasts(self):
        # the 14:00 rain came from an earlier forecast; a later one starts at 15:00 and must not drop it
        later = {"properties": {"timeseries": self.forecast()["properties"]["timeseries"][2:]}}
        old = {"2026-09-18T10:00:00Z": 3.0, "2026-09-19T14:00:00Z": 1.2, "2026-09-19T15:00:00Z": 9.0}
        merged = weather._merge_hours(old, weather.parse_forecast(later, NOW)[1], NOW)
        self.assertEqual(merged, {"2026-09-19T14:00:00Z": 1.2, "2026-09-19T15:00:00Z": 0, "2026-09-19T16:00:00Z": 5})

    def test_sun_times(self):
        tokyo = weather.sun_times(35.68, 139.69, at("2026-09-19T12:00"))  # its day began at 20:26 UTC the day before
        self.assertEqual((tokyo["sunrise"], tokyo["sunset"]), ("2026-09-18T20:26+00:00", "2026-09-19T08:44+00:00"))
        self.assertEqual(weather.sun_times(69.65, 18.96, at("2026-06-21T12:00"))["polar"], "day")  # Tromsø
        self.assertEqual(weather.sun_times(69.65, 18.96, at("2026-12-21T12:00"))["polar"], "night")
        self.assertFalse(weather.resolve({"sky": "clear"}, {}, {"lat": 69.65, "lon": 18.96}, at("2026-12-21T12:00"))["is_day"])

    def cache(self):
        cache = weather.WeatherCache(os.path.join(tempfile.mkdtemp(), "w.json"))
        cache.slept = []
        cache.sleep = cache.slept.append  # the pause before a second try, without the wait
        return cache

    def network(self, calls, symbol="rain", status=200, expires=EXPIRES):
        def get(url, headers=None, timeout=None):
            calls.append((url, headers or {}))
            if "photon" in url:
                return weather.Reply(200, {"features": [{"geometry": {"coordinates": [13.4, 52.52]},
                                                         "properties": {"name": "Berlin", "countrycode": "DE", "osm_value": "city"}}]}, {})
            if status == 304:
                return weather.Reply(304, None, {"Expires": expires})
            return weather.Reply(200, self.forecast(symbol=symbol), {"Expires": expires, "Last-Modified": "Sat, 19 Sep 2026 15:10:00 GMT"})
        return get

    def test_cache_refresh_and_offline_fallback(self):
        cache, calls = self.cache(), []
        self.assertEqual(cache.refresh("Berlin", self.network(calls), now=NOW)["weather"], "rain")
        self.assertFalse(cache.needs_refresh("berlin ", now=NOW + 60))
        self.assertTrue(cache.needs_refresh("Berlin", now=at("2026-09-19T15:50") + 1))

        def offline(url, headers=None, timeout=None):
            raise OSError("no network")

        self.assertIsNone(cache.refresh("Berlin", offline, now=NOW + 3600))
        kept = weather.WeatherCache(cache.path)
        self.assertEqual(kept.current("Berlin", now=NOW + 3600)["weather"], "rain")  # last good kept
        self.assertFalse(cache.needs_refresh("Berlin", now=NOW + 3600 + 60))  # backs off after failure
        # once it is hours old, the preset's own weather is more honest
        self.assertIsNone(kept.current("Berlin", now=NOW + weather.STALE_SECS + 1))
        self.assertIn("no network", kept.failing("Berlin"))

    def test_expires_rules_and_the_15_minutes_are_only_a_fallback(self):
        cache, calls = self.cache(), []
        cache.refresh("Berlin", self.network(calls, expires="Sat, 19 Sep 2026 16:00:00 GMT"), now=NOW)
        self.assertFalse(cache.needs_refresh("Berlin", now=NOW + weather.MAX_AGE_SECS + 60))  # 15:36, before Expires
        self.assertTrue(cache.needs_refresh("Berlin", now=at("2026-09-19T16:00")))

        def offline(url, headers=None, timeout=None):
            raise OSError("no network")

        # a retry after a failure still waits for Expires
        cache.refresh("Berlin", offline, now=at("2026-09-19T15:25"))
        self.assertFalse(cache.needs_refresh("Berlin", now=at("2026-09-19T15:45")))
        # with no Expires to go by, 15 minutes
        cache, calls = self.cache(), []
        cache.refresh("Berlin", self.network(calls, expires="nonsense"), now=NOW)
        self.assertFalse(cache.needs_refresh("Berlin", now=NOW + weather.MAX_AGE_SECS - 1))
        self.assertTrue(cache.needs_refresh("Berlin", now=NOW + weather.MAX_AGE_SECS + 1))

    def test_not_modified_keeps_the_forecast(self):
        cache, calls = self.cache(), []
        cache.refresh("Berlin", self.network(calls), now=NOW)
        later = at("2026-09-19T15:51")
        w = cache.refresh("Berlin", self.network(calls, status=304, expires="Sat, 19 Sep 2026 16:20:00 GMT"), now=later)
        self.assertEqual(w["weather"], "rain")
        self.assertEqual(calls[-1][1], {"If-Modified-Since": "Sat, 19 Sep 2026 15:10:00 GMT"})
        self.assertEqual(sum("photon" in u for u, _ in calls), 1)  # the place is looked up once
        self.assertFalse(cache.needs_refresh("Berlin", now=at("2026-09-19T16:10")))  # the new Expires

    def test_caches_without_a_version_are_refetched(self):
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        weather.save_json(path, {"city": "berlin", "place": BERLIN, "weather": {"weather": "rain"}, "fetched_at": NOW})
        cache = weather.WeatherCache(path)
        self.assertIsNone(cache.current("Berlin", now=NOW))
        self.assertTrue(cache.needs_refresh("Berlin", now=NOW))

    def test_geocode_picks_the_city(self):
        def photon(*places):
            feats = [{"geometry": {"coordinates": [lon, lat]}, "properties": {"name": n, "countrycode": cc, "osm_value": kind}}
                     for n, cc, kind, lat, lon in places]
            return lambda url, headers=None, timeout=None: weather.Reply(200, {"features": feats}, {})
        # a city named after its state, which ranks above it
        sao_paulo = weather.geocode("Sao Paulo", photon(("São Paulo", "BR", "state", -22.07, -48.43),
                                                       ("São Paulo", "BR", "municipality", -23.55, -46.63)))
        self.assertEqual((sao_paulo["lat"], sao_paulo["lon"]), (-23.55, -46.63))
        # a neighbourhood of the same name is skipped; a region with no city of its name stays
        tokyo = weather.geocode("東京", photon(("東京", "JP", "neighbourhood", 36.69, 137.97),
                                              ("Tokyo", "JP", "province", 35.68, 139.76),
                                              ("Tokyo", "PG", "hamlet", -5.8, 142.84)))
        self.assertEqual((tokyo["name"], tokyo["country"]), ("Tokyo", "JP"))
        # a town ranked first is kept, even with a bigger city of the name further down
        paris = weather.geocode("Paris, Texas", photon(("Paris", "US", "town", 33.66, -95.56), ("Paris", "FR", "city", 48.85, 2.35)))
        self.assertEqual(paris["country"], "US")

    def test_a_blip_is_tried_again_straight_away(self):
        cache, calls = self.cache(), []
        good, tries = self.network(calls), []

        def blip(url, headers=None, timeout=None):
            if "met.no" in url and not tries:
                tries.append(url)
                raise TimeoutError("The read operation timed out")
            return good(url, headers, timeout)

        self.assertEqual(cache.refresh("Berlin", blip, now=NOW)["weather"], "rain")
        self.assertEqual(cache.slept, [weather.RETRY_PAUSE_SECS])
        self.assertEqual(cache.failing("Berlin"), "")

    def test_a_refused_request_is_not_tried_again(self):
        import urllib.error
        cache, calls = self.cache(), []
        good = self.network(calls)

        def refused(url, headers=None, timeout=None):
            if "met.no" in url:
                calls.append((url, headers))
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
            return good(url, headers, timeout)

        self.assertIsNone(cache.refresh("Berlin", refused, now=NOW))
        self.assertEqual(cache.slept, [])
        self.assertEqual(sum("met.no" in u for u, _ in calls), 1)

    def test_the_place_is_kept_when_the_forecast_fails(self):
        cache, calls = self.cache(), []
        good = self.network(calls)

        def met_down(url, headers=None, timeout=None):
            if "met.no" in url:
                raise OSError("no network")
            return good(url, headers, timeout)

        self.assertIsNone(cache.refresh("Berlin", met_down, now=NOW))
        self.assertEqual(cache.place("Berlin")["name"], "Berlin")
        calls.clear()
        self.assertEqual(cache.refresh("Berlin", good, now=NOW + 60)["weather"], "rain")
        self.assertFalse(any("photon" in u for u, _ in calls))  # not looked up again

    def test_retries_come_sooner_with_no_weather_to_show(self):
        def offline(url, headers=None, timeout=None):
            raise OSError("no network")

        cache, t = self.cache(), NOW
        for wait in weather.RETRY_STEPS_SECS + (weather.RETRY_STEPS_SECS[-1],):
            cache.refresh("Berlin", offline, now=t)
            self.assertFalse(cache.needs_refresh("Berlin", now=t + wait - 1))
            self.assertTrue(cache.needs_refresh("Berlin", now=t + wait))
            t += wait
        # a success starts the steps over
        cache.refresh("Berlin", self.network([], expires="nonsense"), now=t)
        cache.refresh("Berlin", offline, now=t + weather.MAX_AGE_SECS + 1)
        # ...and while the last weather still shows, there is no hurry
        self.assertFalse(cache.needs_refresh("Berlin", now=t + weather.MAX_AGE_SECS + 1 + weather.RETRY_STEPS_SECS[0]))
        self.assertTrue(cache.needs_refresh("Berlin", now=t + weather.MAX_AGE_SECS + 1 + weather.RETRY_WHILE_SHOWING_SECS))

    def test_unknown_city(self):
        cache, calls = self.cache(), []

        def nowhere(url, headers=None, timeout=None):
            calls.append(url)
            return weather.Reply(200, {"features": []}, {})

        self.assertIsNone(cache.refresh("Xyzzy", nowhere, now=NOW))
        self.assertIn("city not found", cache.failing("Xyzzy"))  # for the settings and the forest's tooltip
        self.assertEqual(cache.slept, [])  # nothing found is not a blip
        # not asked again while the city text stays the same, however long Anki runs
        self.assertFalse(cache.needs_refresh(" Xyzzy", now=NOW + 24 * 3600))
        # a restart asks once more, and still shows why meanwhile
        restarted = weather.WeatherCache(cache.path)
        self.assertIn("city not found", restarted.failing("Xyzzy"))
        self.assertTrue(restarted.needs_refresh("Xyzzy", now=NOW + weather.RETRY_STEPS_SECS[0]))
        restarted.refresh("Xyzzy", nowhere, now=NOW + weather.RETRY_STEPS_SECS[0])
        self.assertFalse(restarted.needs_refresh("Xyzzy", now=NOW + 24 * 3600))
        self.assertEqual(len(calls), 2)
        # a new city text is looked up straight away
        self.assertTrue(restarted.needs_refresh("Xyzzyx", now=NOW + 60))

    def test_the_sky_follows_the_forecast_hour_without_a_new_forecast(self):
        def entry(hour, symbol):
            return {"time": f"2026-09-19T{hour}:00:00Z",
                    "data": {"instant": {"details": {"air_temperature": 14.2, "wind_speed": 1.5}},
                             "next_1_hours": {"summary": {"symbol_code": symbol}, "details": {"precipitation_amount": 0}}}}

        storm = {"properties": {"timeseries": [entry("15", "clearsky_day"), entry("16", "heavyrainandthunder"),
                                               entry("17", "heavyrainandthunder")]}}

        def met(status):
            def get(url, headers=None, timeout=None):
                if status == 304:
                    return weather.Reply(304, None, {"Expires": "Sat, 19 Sep 2026 17:20:00 GMT"})
                return weather.Reply(200, storm, {"Expires": EXPIRES, "Last-Modified": "Sat, 19 Sep 2026 15:10:00 GMT"})
            return get

        cache = self.cache()
        cache._state = {"v": weather.CACHE_VERSION, "city": "berlin", "place": BERLIN}
        self.assertEqual(cache.refresh("Berlin", met(200), now=NOW)["weather"], "clear")  # 15:20
        # offline: the forecast held still says what each hour brings
        self.assertEqual(weather.WeatherCache(cache.path).current("Berlin", now=at("2026-09-19T16:30"))["weather"], "storm")
        # MET's "nothing changed" at 16:51
        self.assertEqual(cache.refresh("Berlin", met(304), now=at("2026-09-19T16:51"))["weather"], "storm")
        self.assertEqual(cache.current("Berlin", now=at("2026-09-19T16:52"))["weather"], "storm")

    def test_a_cache_without_hours_still_shows_and_is_fetched_afresh(self):
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        weather.save_json(path, {"v": weather.CACHE_VERSION, "city": "berlin", "place": BERLIN, "fetched_at": NOW,
                                 "modified": "Sat, 19 Sep 2026 15:10:00 GMT",
                                 "weather": {"sky": "rain", "symbol": "rain", "temp": 14.2, "wind": 5.4, "windy": False}})
        cache, calls = weather.WeatherCache(path), []
        self.assertEqual(cache.current("Berlin", now=NOW + 60)["weather"], "rain")
        self.assertEqual(cache.refresh("Berlin", self.network(calls, symbol="snow"), now=NOW + 3600)["weather"], "snow")
        self.assertEqual(calls[-1][1], {})  # no If-Modified-Since: a 304 would leave it with no hours

    def test_user_agent_names_the_version(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(weather.__file__)), "manifest.json"), encoding="utf-8") as f:
            version = json.load(f)["human_version"]
        self.assertTrue(weather.USER_AGENT.startswith(f"MemoryForest/{version} "))
        self.assertIn("https://github.com/baraklevy20/memory-forest", weather.USER_AGENT)  # MET asks for a contact

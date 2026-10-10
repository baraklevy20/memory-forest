"""Real-world weather from MET Norway (free, no account, CC BY 4.0), for a city found with
Photon (OpenStreetMap data, free, no account).

Only used when the user types a city into the config. Network calls happen on a
background thread (see live_weather.py); everything here is plain Python so it can be
unit-tested without Anki.

MET's forecast has no time zone, sunrise or past rain, so the rest is worked out here:
sunrise and sunset from the sun's position, and the rain of the last hours from the
hourly forecasts already fetched. Everything time-related is kept in UTC.
"""

from __future__ import annotations

import datetime as _dt
import email.utils
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple

try:
    from .store import load_json, save_json
except ImportError:  # tests and dev scripts import this file as a top-level module
    from store import load_json, save_json

# Places only, a few of them: Photon files some big cities as districts, which its city
# layer leaves out (Mexico City, Lima and Auckland came back as other places)
GEOCODE_URL = "https://photon.komoot.io/api/?limit=6&lang=en&osm_tag=place&q={name}"
TOWNS = ("city", "town", "village", "hamlet", "municipality")
REGIONS = ("state", "province", "county", "region", "country")
# MET asks for at most 4 decimals, so nearby users share its cache
FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"


def _version() -> str:
    """This add-on's version, from its manifest.json, or "" if it can't be read."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json"), encoding="utf-8") as f:
            version = json.load(f).get("human_version")
    except (OSError, ValueError, AttributeError):
        return ""
    return version if isinstance(version, str) else ""


# MET and Photon both ask to be told who is calling, and how to reach them
VERSION = _version()
USER_AGENT = f"MemoryForest{'/' + VERSION if VERSION else ''} (Anki add-on; https://github.com/baraklevy20/memory-forest)"
CACHE_VERSION = 2  # caches from before it have none: they are refetched
# How long a forecast is kept when MET's reply has no Expires we can read. MET's Expires
# (about 20-30 minutes after each fetch) always rules when it has one.
MAX_AGE_SECS = 15 * 60
# After a failure: with no weather to show, try again soon, then less often; while the last
# weather still shows, there is no hurry. MET's Expires still comes first.
RETRY_STEPS_SECS = (60, 2 * 60, 5 * 60, 10 * 60)
RETRY_WHILE_SHOWING_SECS = 10 * 60
# A dropped connection or a slow server is often gone a moment later: one more try, then
# the steps above
RETRY_PAUSE_SECS = 2
# Past this, the cache is not weather any more: offline for hours, the preset's own
# weather is more honest than an old sky.
STALE_SECS = 6 * 3600
# Beaufort 6, "strong breeze": large branches move. MET's 10 m wind reads high, so a
# lower line would call too many ordinary days windy.
WINDY_KMH = 39
# Clear or cloudy counts as "after the rain" when more than this fell in the last hours.
RECENT_RAIN_HOURS = 2
RECENT_RAIN_MM = 0.1
# Hourly rain and sky kept from the forecasts, either side of now: the past for "after the
# rain", the future so a forecast that is not fetched again (MET's 304, or going offline)
# still covers the hours after.
KEEP_HOURS = 24
HTTP_TIMEOUT_SECS = 15  # MET answers in under a second, but this runs in the background
# Photon's public server can take 10 s and more; a city is looked up once, in the background
GEOCODE_TIMEOUT_SECS = 30
MAX_ERROR_CHARS = 200  # of an error message kept in the cache, for the settings dialog
SUN_ALTITUDE = -0.833  # degrees: the sun's top edge on the horizon, through the air
HOUR = _dt.timedelta(hours=1)


class Reply(NamedTuple):
    status: int  # 200, or 304 when nothing changed since If-Modified-Since
    body: dict | None
    headers: dict


def map_symbol(symbol: str) -> str:
    """MET symbol code (e.g. "lightrainshowers_day") → forest weather."""
    s = symbol.split("_")[0]
    if "thunder" in s:
        return "storm"
    if "snow" in s:
        return "snow"
    if "rain" in s or "sleet" in s or "drizzle" in s:
        return "rain"
    if s == "fog":
        return "fog"
    if s in ("clearsky", "fair"):
        return "clear"
    return "cloudy"


def _utc(now: float) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(now, _dt.timezone.utc)


def _hour_key(when: _dt.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:00:00Z")


def parse_forecast(js: dict, now: float | None = None) -> tuple:
    """(the weather now, {UTC hour: mm of rain in it}, {UTC hour: its symbol, temperature
    and wind}) from a MET compact forecast."""
    hours, rain = {}, {}
    for e in js["properties"]["timeseries"]:
        data = e["data"]
        nxt = data.get("next_1_hours") or data.get("next_6_hours") or {}
        details = data["instant"]["details"]
        hours[e["time"]] = {"symbol": (nxt.get("summary") or {}).get("symbol_code", "cloudy"),
                            "temp": details.get("air_temperature"),
                            "wind": round(float(details.get("wind_speed") or 0) * 3.6, 1)}  # m/s → km/h
        one = data.get("next_1_hours")
        if one and "precipitation_amount" in (one.get("details") or {}):
            rain[e["time"]] = one["details"]["precipitation_amount"]
    return sky_at(hours, now or time.time()), rain, hours


def sky_at(hours: dict, now: float) -> dict | None:
    """The sky at `now` from the hourly forecast: the hour now, or the first one when the
    forecast starts later. None when there are no hours at all."""
    if not hours:
        return None
    stamp = _hour_key(_utc(now))
    times = sorted(hours)
    hour = hours[next((h for h in reversed(times) if h <= stamp), times[0])]
    weather, wind = map_symbol(hour["symbol"]), hour.get("wind") or 0.0
    return {
        "sky": weather,  # before "after the rain", which depends on the hour it is read
        "symbol": hour["symbol"],
        "temp": hour.get("temp"),
        "wind": wind,
        "windy": wind >= WINDY_KMH and weather != "fog",
    }


def sun_times(lat: float, lon: float, now: float) -> dict:
    """Sunrise and sunset (UTC ISO) on the place's solar day around `now`, from the
    sunrise equation (NOAA's, to about a minute). `polar` is "day" or "night" when the
    sun does not cross the horizon that day, and the times are then None."""
    # the place's own day, by the sun: it turns at solar midnight, not at UTC's
    day = (_utc(now) + _dt.timedelta(hours=lon / 15)).date()
    n = (day - _dt.date(2000, 1, 1)).days
    j_star = n - lon / 360
    m = (357.5291 + 0.98560028 * j_star) % 360
    rm = math.radians(m)
    c = 1.9148 * math.sin(rm) + 0.02 * math.sin(2 * rm) + 0.0003 * math.sin(3 * rm)
    ecl = math.radians((m + c + 180 + 102.9372) % 360)
    transit = 2451545.0 + j_star + 0.0053 * math.sin(rm) - 0.0069 * math.sin(2 * ecl)
    sin_d = math.sin(ecl) * math.sin(math.radians(23.4397))
    cos_d = math.cos(math.asin(sin_d))
    phi = math.radians(lat)
    cos_w = (math.sin(math.radians(SUN_ALTITUDE)) - math.sin(phi) * sin_d) / (math.cos(phi) * cos_d)
    if cos_w < -1:
        return {"sunrise": None, "sunset": None, "polar": "day"}
    if cos_w > 1:
        return {"sunrise": None, "sunset": None, "polar": "night"}
    half = math.degrees(math.acos(cos_w)) / 360

    def iso(jd: float) -> str:
        return _utc((jd - 2440587.5) * 86400).isoformat(timespec="minutes")

    return {"sunrise": iso(transit - half), "sunset": iso(transit + half), "polar": None}


def is_day(sun: dict, now: float) -> bool:
    if sun["polar"]:
        return sun["polar"] == "day"
    t = _utc(now)
    return _dt.datetime.fromisoformat(sun["sunrise"]) <= t < _dt.datetime.fromisoformat(sun["sunset"])


def rained_recently(rain: dict, now: float) -> bool:
    """More than a trace fell in the last whole hours before this one."""
    hour = _utc(now).replace(minute=0, second=0, microsecond=0)
    return sum(rain.get(_hour_key(hour - k * HOUR)) or 0 for k in range(1, RECENT_RAIN_HOURS + 1)) > RECENT_RAIN_MM


def resolve(sky: dict, rain: dict, place: dict, now: float) -> dict:
    """The weather as the forest uses it at `now`: the fetched sky, the sun's times for the
    place, and "after the rain" when it has just stopped in daylight."""
    sun = sun_times(place["lat"], place["lon"], now)
    day = is_day(sun, now)
    weather = sky["sky"]
    if weather in ("clear", "cloudy") and day and rained_recently(rain, now):
        weather = "after_rain"
    return {**sky, **sun, "weather": weather, "is_day": day}


def _merge_hours(old: dict, new: dict, now: float) -> dict:
    """New hours over old ones (of rain, or of sky), kept within KEEP_HOURS of now."""
    t = _utc(now)
    lo, hi = _hour_key(t - KEEP_HOURS * HOUR), _hour_key(t + KEEP_HOURS * HOUR)
    return {h: mm for h, mm in sorted({**old, **new}.items()) if lo <= h <= hi}


def _expiry(headers: dict) -> float:
    try:
        return email.utils.parsedate_to_datetime(headers.get("Expires", "")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _get(url: str, headers: dict | None = None, timeout: float = HTTP_TIMEOUT_SECS) -> Reply:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Reply(resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers))
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return Reply(304, None, dict(e.headers))
        raise


def _passing(e: Exception) -> bool:
    """A failure worth one more try straight away: the network or the server, not the request."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500
    return isinstance(e, OSError)  # timeouts and dropped connections


def _twice(fetch, sleep=time.sleep):
    try:
        return fetch()
    except Exception as e:
        if not _passing(e):
            raise
        sleep(RETRY_PAUSE_SECS)
        return fetch()


def geocode(city: str, get=_get) -> dict | None:
    js = get(GEOCODE_URL.format(name=urllib.parse.quote(city.strip())), timeout=GEOCODE_TIMEOUT_SECS).body or {}
    # a neighbourhood, suburb or island of the same name is not where anyone means
    feats = [f for f in js.get("features") or [] if (f.get("properties") or {}).get("osm_value") in TOWNS + REGIONS]
    if not feats:
        return None
    best = feats[0]
    if best["properties"]["osm_value"] in REGIONS:
        # a city named after its state ranks under it (São Paulo, Mexico City): the city
        # is the one meant, and the state's middle can be hundreds of km from it
        key = (best["properties"].get("name"), best["properties"].get("countrycode"))
        best = next((f for f in feats[1:] if f["properties"]["osm_value"] in TOWNS
                     and (f["properties"].get("name"), f["properties"].get("countrycode")) == key), best)
    props = best["properties"]
    lon, lat = best["geometry"]["coordinates"]
    return {"name": props.get("name") or city, "lat": lat, "lon": lon, "country": props.get("countrycode")}


class CityNotFound(ValueError):
    """Photon knows no town or region by the name typed in."""


class WeatherCache:
    """Weather for one configured city, cached in a JSON file under user_files/."""

    def __init__(self, path: str):
        self.path = path
        self.sleep = time.sleep
        self._state = self._load()
        # the city text Photon did not know: not asked again until the text changes. Kept
        # out of the file, so a restart asks once more (Photon's data does grow).
        self._not_found = None

    def _load(self) -> dict:
        state = load_json(self.path)
        return state if state.get("v") == CACHE_VERSION else {}

    def _save(self) -> None:
        save_json(self.path, self._state)

    def _ours(self, city: str) -> bool:
        return self._state.get("city") == city.strip().lower()

    def current(self, city: str, now: float | None = None) -> dict | None:
        """Last known weather for `city`, or None if there is none recent enough to use."""
        now = now or time.time()
        if not self._ours(city) or not self._state.get("weather"):
            return None
        if now - self._state.get("fetched_at", 0) > STALE_SECS:
            return None  # offline for hours: the preset's own weather is more honest
        # the forecast's own hour, so the sky moves on with it between fetches; a cache from
        # before the hours were kept has only the sky of its fetch
        sky = sky_at(self._state.get("hours") or {}, now) or self._state["weather"]
        return resolve(sky, self._state.get("rain") or {}, self._state["place"], now)

    def failing(self, city: str) -> str:
        """The last error for `city`, while it is the reason there is no weather."""
        if not self._ours(city) or not self._state.get("failed_at"):
            return ""
        return str(self._state.get("error") or "could not reach MET Norway")

    def place(self, city: str) -> dict | None:
        return self._state.get("place") if self._ours(city) else None

    def needs_refresh(self, city: str, now: float | None = None) -> bool:
        now = now or time.time()
        if not self._ours(city):
            return True
        if self._not_found == city.strip():
            return False  # asking again would only find nothing again
        expires = self._state.get("expires") or 0
        if now < expires:  # MET asks never to come back before its Expires, failure or not
            return False
        if self._state.get("failed_at"):
            fails = self._state.get("fails") or 1
            wait = RETRY_WHILE_SHOWING_SECS if self.current(city, now) else RETRY_STEPS_SECS[min(fails, len(RETRY_STEPS_SECS)) - 1]
            return now - self._state["failed_at"] >= wait
        return bool(expires) or now - self._state.get("fetched_at", 0) > MAX_AGE_SECS

    def refresh(self, city: str, get=_get, now: float | None = None) -> dict | None:
        """Blocking network refresh; call from a background thread. Never raises."""
        key = city.strip().lower()
        now = now or time.time()
        prev = self._state if self._ours(city) else {}
        place = prev.get("place")
        try:
            if not place:
                place = _twice(lambda: geocode(city, get), self.sleep)
                if not place:
                    raise CityNotFound(f"city not found: {city}")
            # a cache with no hours (from before they were kept) fetches the forecast afresh
            headers = {"If-Modified-Since": prev["modified"]} if prev.get("modified") and prev.get("hours") else {}
            reply = _twice(lambda: get(FORECAST_URL.format(lat=place["lat"], lon=place["lon"]), headers), self.sleep)
            state = {"v": CACHE_VERSION, "city": key, "place": place, "fetched_at": now,
                     "expires": _expiry(reply.headers), "modified": reply.headers.get("Last-Modified") or prev.get("modified")}
            if reply.status == 304:  # nothing new: the forecast we hold is still MET's latest
                rain, hours = prev.get("rain") or {}, prev["hours"]
            else:
                _, rain, hours = parse_forecast(reply.body, now)
            rain = _merge_hours(prev.get("rain") or {}, rain, now)
            hours = _merge_hours(prev.get("hours") or {}, hours, now)
            sky = sky_at(hours, now)
            if not sky:
                raise ValueError("the forecast has no hours")
            self._state = {**state, "weather": sky, "rain": rain, "hours": hours}
            weather = resolve(sky, rain, place, now)
        except Exception as e:  # offline, bad city, API change: fall back quietly
            if isinstance(e, CityNotFound):
                self._not_found = city.strip()
            # the place is kept, though the forecast failed: Photon is the slow one to ask again
            self._state = {**(prev or {"v": CACHE_VERSION, "city": key}), **({"place": place} if place else {}),
                           "failed_at": now, "fails": (prev.get("fails") or 0) + 1, "error": str(e)[:MAX_ERROR_CHARS]}
            weather = None
        try:
            self._save()
        except OSError:
            pass
        return weather

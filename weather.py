"""Real-world weather from Open-Meteo (free, no API key, CC-BY 4.0).

Only used when the user types a city into the config. Network calls happen on a
background thread (see __init__.py); everything here is plain Python so it can be
unit-tested without Anki.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

try:
    from .store import load_json, save_json
except ImportError:  # tests and dev scripts import this file as a top-level module
    from store import load_json, save_json

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search?count=1&language=en&format=json&name={name}"
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=weather_code,is_day,temperature_2m,precipitation,wind_speed_10m"
    "&hourly=precipitation&daily=sunrise,sunset&past_days=1&forecast_days=1&timezone=auto"
)
USER_AGENT = "MemoryForest/1.0 (Anki add-on)"
MAX_AGE_SECS = 45 * 60
RETRY_AFTER_FAIL_SECS = 10 * 60
# Past this, the cache is not weather any more: it also carries the sunrise, sunset and
# local time of the moment it was fetched, which would freeze the forest at that hour.
STALE_SECS = 6 * 3600
WINDY_KMH = 30
# Clear or cloudy counts as "after the rain" when more than this fell in the last hours.
RECENT_RAIN_HOURS = 2
RECENT_RAIN_MM = 0.1
HTTP_TIMEOUT_SECS = 6
MAX_ERROR_CHARS = 200  # of an error message kept in the cache, for the settings dialog


def map_wmo(code: int) -> str:
    """WMO weather interpretation code → forest weather."""
    if code in (0, 1):
        return "clear"
    if code in (2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 95 <= code <= 99:
        return "storm"
    return "cloudy"


def parse_forecast(js: dict) -> dict:
    """Pick out what the forest uses from an Open-Meteo forecast response."""
    cur = js["current"]
    local_time = cur["time"]  # ISO in the location's timezone, e.g. "2026-09-19T18:45"
    weather = map_wmo(int(cur.get("weather_code", 0)))

    hourly = js.get("hourly") or {}
    times, precip = hourly.get("time") or [], hourly.get("precipitation") or []
    past = [p or 0 for t, p in zip(times, precip) if t <= local_time][-RECENT_RAIN_HOURS:]
    rained_recently = sum(past) > RECENT_RAIN_MM
    if weather in ("clear", "cloudy") and rained_recently and cur.get("is_day"):
        weather = "after_rain"

    today = local_time[:10]
    daily = js.get("daily") or {}
    sunrise = sunset = None
    for d, rise, set_ in zip(daily.get("time") or [], daily.get("sunrise") or [], daily.get("sunset") or []):
        if d == today:
            sunrise, sunset = rise, set_
    wind = float(cur.get("wind_speed_10m") or 0)
    return {
        "weather": weather,
        "is_day": bool(cur.get("is_day")),
        "temp": cur.get("temperature_2m"),
        "wind": wind,
        "windy": wind >= WINDY_KMH and weather != "fog",
        "local_time": local_time,
        "utc_offset": js.get("utc_offset_seconds"),  # so the city's clock can be read later, not frozen at the fetch
        "sunrise": sunrise,
        "sunset": sunset,
    }


def _get_json(url: str, timeout: float = HTTP_TIMEOUT_SECS) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode(city: str, get_json=_get_json) -> dict | None:
    js = get_json(GEOCODE_URL.format(name=urllib.parse.quote(city.strip())))
    results = js.get("results") or []
    if not results:
        return None
    r = results[0]
    return {"name": r.get("name") or city, "lat": r["latitude"], "lon": r["longitude"], "country": r.get("country_code")}


class WeatherCache:
    """Weather for one configured city, cached in a JSON file under user_files/."""

    def __init__(self, path: str):
        self.path = path
        self._state = self._load()

    def _load(self) -> dict:
        return load_json(self.path)

    def _save(self) -> None:
        save_json(self.path, self._state)

    def current(self, city: str, now: float | None = None) -> dict | None:
        """Last known weather for `city`, or None if there is none recent enough to use."""
        if self._state.get("city") != city.strip().lower():
            return None
        if (now or time.time()) - self._state.get("fetched_at", 0) > STALE_SECS:
            return None  # offline for hours: the preset's own weather and the real clock are more honest
        return self._state.get("weather")

    def failing(self, city: str) -> str:
        """The last error for `city`, while it is the reason there is no weather."""
        if self._state.get("city") != city.strip().lower() or not self._state.get("failed_at"):
            return ""
        return str(self._state.get("error") or "could not reach Open-Meteo")

    def place(self, city: str) -> dict | None:
        if self._state.get("city") != city.strip().lower():
            return None
        return self._state.get("place")

    def needs_refresh(self, city: str, now: float | None = None) -> bool:
        now = now or time.time()
        if self._state.get("city") != city.strip().lower():
            return True
        if self._state.get("failed_at") and now - self._state["failed_at"] < RETRY_AFTER_FAIL_SECS:
            return False
        return now - self._state.get("fetched_at", 0) > MAX_AGE_SECS

    def refresh(self, city: str, get_json=_get_json, now: float | None = None) -> dict | None:
        """Blocking network refresh; call from a background thread. Never raises."""
        key = city.strip().lower()
        now = now or time.time()
        try:
            place = self._state.get("place") if self._state.get("city") == key else None
            if not place:
                place = geocode(city, get_json)
                if not place:
                    raise ValueError(f"city not found: {city}")
            weather = parse_forecast(get_json(FORECAST_URL.format(lat=place["lat"], lon=place["lon"])))
            self._state = {"city": key, "place": place, "weather": weather, "fetched_at": now}
        except Exception as e:  # offline, bad city, API change: fall back quietly
            prev = self._state if self._state.get("city") == key else {"city": key}
            self._state = {**prev, "failed_at": now, "error": str(e)[:MAX_ERROR_CHARS]}
            weather = None
        try:
            self._save()
        except OSError:
            pass
        return weather

"""Decide what the forest looks like right now: time of day, weather, special
touches, and the one-line journal under it.

Everything is either set by the user in the config, taken from real weather, or taken
from the preset of the day, so the scene is stable for the whole day and never needs a click.
"""

from __future__ import annotations

import datetime as _dt
import hashlib

try:
    from . import catalog
    from . import presets as presets_mod
except ImportError:  # tests and dev scripts import these files as top-level modules
    import catalog
    import presets as presets_mod

# The settings dialog and the dev gallery both label weather and time from here.
WEATHER_LABELS = {"clear": "Clear", "cloudy": "Cloudy", "fog": "Fog", "rain": "Rain", "storm": "Thunderstorm",
                  "snow": "Snow", "deep_winter": "Deep winter", "after_rain": "After the rain"}
TIME_LABELS = {"dawn": "Dawn", "day": "Day", "golden_hour": "Golden hour", "dusk": "Dusk", "night": "Night"}
WEATHERS = tuple(WEATHER_LABELS)
TIMES = tuple(TIME_LABELS)

# The look of the forest, and what it stands in and looks out on: key -> label, read from
# the files under web/ (see catalog.py). An environment's key names its own file in
# web/envs/, which holds everything about it; only the plain forest has no JS of its own.
ENVIRONMENTS = catalog.labels("envs")
LANDSCAPES = catalog.labels("landscapes")
LANDMARKS = catalog.labels("landmarks")

SYNODIC_MONTH = 29.530588853
KNOWN_NEW_MOON = _dt.datetime(2000, 1, 6, 18, 14, tzinfo=_dt.timezone.utc)

DEFAULT_SUNRISE = _dt.time(6, 30)
DEFAULT_SUNSET = _dt.time(19, 0)
# Dawn and dusk last this long either side of sunrise and sunset; golden hour is the
# stretch of the same length just before dusk.
TWILIGHT = _dt.timedelta(minutes=60)

# Without live weather, a cloudy or rainy day is windy this often.
WIND_CHANCE = 0.3

# Meteor showers fall on these streak days, and every year on the night of the Perseids.
METEOR_SHOWER_STREAKS = (100, 200, 365, 500, 730, 1000)
PERSEIDS = (8, 12)  # (month, day)
# the harvest moon rises on each of the forest's birthdays
DAYS_PER_YEAR = 365


def _roll(date: _dt.date, salt: str) -> float:
    """Deterministic 0..1 value for a date, so choices hold all day."""
    h = hashlib.sha1(f"{date.isoformat()}|{salt}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**32


def moon_phase(when: _dt.datetime) -> float:
    """0 = new moon, 0.5 = full moon."""
    if when.tzinfo is None:
        when = when.astimezone()
    days = (when - KNOWN_NEW_MOON).total_seconds() / 86400
    return (days / SYNODIC_MONTH) % 1.0


def time_of_day(now: _dt.datetime, sunrise: _dt.datetime | None = None, sunset: _dt.datetime | None = None) -> str:
    sunrise = sunrise or _dt.datetime.combine(now.date(), DEFAULT_SUNRISE)
    sunset = sunset or _dt.datetime.combine(now.date(), DEFAULT_SUNSET)
    if sunrise - TWILIGHT <= now < sunrise + TWILIGHT:
        return "dawn"
    if sunset - TWILIGHT <= now < sunset + TWILIGHT:
        return "dusk"
    if sunset - 2 * TWILIGHT <= now < sunset - TWILIGHT:
        return "golden_hour"
    if sunrise + TWILIGHT <= now < sunset - TWILIGHT:
        return "day"
    return "night"


def _parse_local(iso: str | None) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def preset_weather(cfg: dict, today, base) -> str:
    """The weather the chosen preset shows, for when the real sky is on but there is no
    live weather to follow: Surprise me daily takes today's preset's."""
    spec = presets_mod.by_key().get(presets_mod.match(cfg))
    weather = spec.weather if spec else base.weather
    if weather == presets_mod.DAILY:
        weather = today.weather
    return weather if weather in WEATHERS else base.weather


def choose_mood(cfg: dict, now: _dt.datetime, real: dict | None = None, place: dict | None = None) -> dict:
    """Resolve the five look settings for this moment. Each is fixed in the config, or
    `daily`: taken from today's preset, so Surprise me daily is a new preset every day.
    Weather and time can also be `auto`: the real sky for your city (the preset's own
    weather without one) and your own clock. A missing setting is the default preset's."""
    date = now.date()
    today, base = presets_mod.of_the_day(date), presets_mod.FOREST_PRESETS[0]

    def setting(key: str, attr: str) -> str:
        value = cfg.get(key) or getattr(base, attr)
        return getattr(today, attr) if value == presets_mod.DAILY else value

    env_cfg, weather_cfg, time_cfg = setting("environment", "environment"), setting("weather", "weather"), setting("time_of_day", "time")
    landscape, landmark = setting("landscape", "landscape"), setting("landmark", "landmark")

    local_now, sunrise, sunset = now, None, None
    use_real = real is not None and weather_cfg == "auto"
    if use_real:
        # the city's clock now: our own clock moved to its time zone. The time the
        # weather was fetched is only a fallback, for a cache from before the offset.
        offset = real.get("utc_offset")
        if isinstance(offset, (int, float)):
            aware = now if now.tzinfo else now.astimezone()
            local_now = (aware.astimezone(_dt.timezone.utc) + _dt.timedelta(seconds=offset)).replace(tzinfo=None)
        else:
            local_now = _parse_local(real.get("local_time")) or now
        sunrise, sunset = _parse_local(real.get("sunrise")), _parse_local(real.get("sunset"))

    if weather_cfg in WEATHERS:
        weather, source = weather_cfg, "manual"
    elif use_real:
        weather, source = real["weather"], "real"
    else:
        # no live weather (no city, or one that can't be found): the preset keeps its own
        weather, source = preset_weather(cfg, today, base), "preset"

    time = time_cfg if time_cfg in TIMES else time_of_day(local_now, sunrise, sunset)

    environment = env_cfg if env_cfg in ENVIRONMENTS else base.environment

    windy = bool(real.get("windy")) if use_real else (weather in ("cloudy", "rain", "storm") and _roll(date, "wind") < WIND_CHANCE)
    if landscape not in LANDSCAPES:
        landscape = base.landscape
    if landmark not in LANDMARKS:  # one that no longer exists
        landmark = base.landmark
    # `clock`: the hour is the real one, so a night-only environment may overrule it
    mood = {"time": time, "clock": time_cfg not in TIMES, "weather": weather, "special": environment, "wind": windy,
            "environment": environment, "landscape": landscape, "landmark": landmark,
            "moon": round(moon_phase(now), 3), "source": source}
    if use_real:
        mood["temp"] = real.get("temp")
        mood["city"] = (place or {}).get("name")
    return mood


def events(stats: dict, today: _dt.date, new_ancient: bool = False) -> list:
    """Night-sky events tied to your study: they only show on clear nights."""
    out = []
    streak = stats.get("streak", 0)
    if streak in METEOR_SHOWER_STREAKS or (today.month, today.day) == PERSEIDS:
        out.append("meteor_shower")
    age = stats.get("forest_age", 0)
    if age and age % DAYS_PER_YEAR == 0:
        out.append("harvest_moon")
    if new_ancient:
        out.append("new_ancient")
    return out


def _plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def _fmt_date(iso: str) -> str:
    d = _dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


# Counts worth remarking on. A forest passing its hundredth tree is news; its hundred
# and first is not.
TREE_MILESTONES = (1, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000)
STREAK_MILESTONES = (7, 30, 50, 100, 200, 365, 500, 730, 1000)


def journal(forest: dict, mood: dict, today: _dt.date, anniversary_idx: list, evs: list = ()) -> str:
    """One sentence, on the days there is something to say.

    It speaks when something became true today - an animal arrived, a tree turned
    ancient, an anniversary came round, a milestone was passed - and stays quiet
    otherwise, which is most days.
    """
    s = forest["stats"]
    trees = forest["trees"]
    if not trees:
        return "Study some new cards and your first tree will take root here."

    for v in forest.get("visitors", []):
        if v.get("new"):
            if v["key"] == "cabin":
                return "A little cabin now stands at the edge of your forest: a year since your first tree."
            return f"{v['label'].capitalize()} wandered in: {v['why']}."
    night = mood["time"] == "night"
    if "harvest_moon" in evs and night:  # the moon is only drawn at night
        return "A harvest moon rises over your forest's anniversary."
    if "meteor_shower" in evs and night:
        return "Meteors are falling tonight."
    if "new_ancient" in evs:
        return "One of your trees became ancient today." + (" Watch for a shooting star." if night else "")
    if anniversary_idx:
        t = trees[anniversary_idx[0]]
        years = today.year - _dt.date.fromisoformat(t["date"]).year
        span = "a year" if years == 1 else f"{years} years"
        return f"The tree you planted on {_fmt_date(t['date'])} turned {span} old today."

    # milestones, but only on the day they are reached
    if s["planted_today"]:
        if s["trees"] in TREE_MILESTONES:
            if s["trees"] == 1:
                return f"Your first tree. It holds {_plural(s['today_cards'], 'card')}."
            return f"Your {s['trees']}th tree, planted today with {_plural(s['today_cards'], 'new card')}."
        if s["streak"] in STREAK_MILESTONES:
            return f"{s['streak']} days in a row. The forest has not missed one."

    # Nothing happened today that the forest has not already said. A line every day
    # becomes wallpaper; saying nothing is what makes the next line worth reading.
    return ""

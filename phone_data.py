"""The forest as your phone gets it: a note that syncs through AnkiWeb holds it as JSON,
and a card template draws it with the same scripts as the deck list (phone.py writes the
note; web/phone.js is the card's boot script).

The phone cannot work anything out for itself, so the note carries what the desktop page
is drawn from plus the scene for each of the next SCHEDULE_DAYS days. The phone picks
today's, and follows its own clock for the time of day when the settings say to.

Nothing here imports aqt, so it runs in the tests.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os

try:
    from . import catalog, scene
except ImportError:  # tests and dev scripts import these files as top-level modules
    import catalog
    import scene

# Bumped whenever the note's JSON changes shape, so web/phone.js can tell an old note.
VERSION = 1
# A temperature this close to the one the phone already has is not worth an upload of its own
TEMP_UPLOAD_DEGREES = 3
# How many days of scenes the note holds: a phone that goes this long without a sync from
# the computer keeps showing the last of them.
SCHEDULE_DAYS = 14
# Live weather counts as live on the phone for this long after it was sent; after that the
# phone shows the preset's own weather, as the desktop does without live weather.
LIVE_WEATHER_HOURS = 6
# The page's width limit, on a phone: as wide as the card is.
PHONE_MAX_WIDTH = 1200
# What only makes sense on the desktop's deck list: which add-on answers clicks, and the
# deck screens.
DESKTOP_ONLY = ("channel", "deckId", "deckName", "highlight", "litCount", "weatherError")
# The script the card loads, named after what is in it: an update gets a new name, so no
# phone keeps drawing with yesterday's copy from its cache.
SCRIPT_PREFIX = "_memory_forest-"
BOOT = "phone.js"


def bundle(scripts=None, web: str = catalog.WEB) -> str:
    """The scripts every forest uses, as one file: a phone has no add-on to load them from.
    The stylesheet comes along inside it, and web/phone.js goes last to mount the forest. The
    scenery is not in it: each environment, landscape and landmark is a file of its own
    (part_name), and the card loads only today's - parsing all of them at every look was
    half the work of showing the card."""
    parts = [os.path.join(web, rel) for rel in (catalog.core_scripts(web) if scripts is None else scripts)]
    with open(os.path.join(web, "forest.css"), encoding="utf-8") as f:
        css = f.read()
    out = ["/* Memory Forest, for the card that shows it on your phone. Written by the add-on: "
           "edits here are lost at the next sync. */",
           f"(function () {{ const s = document.createElement('style'); s.textContent = {json.dumps(css)}; "
           "document.head.appendChild(s); })();"]
    for path in parts + [os.path.join(web, BOOT)]:
        with open(path, encoding="utf-8") as f:
            out.append(f.read())
    return "\n".join(out) + "\n"


def scenery(days: list, web: str = catalog.WEB) -> list:
    """The scenery files (as "envs/aurora.js") the days' scenes draw with, that this copy has."""
    out = []
    for day in days:
        out += [rel for rel in catalog.scenery_files(day.get("mood") or {}, web) if rel not in out]
    return out


def all_scenery(web: str = catalog.WEB) -> list:
    """Every scenery file this copy ships (as "envs/aurora.js")."""
    return [f"{kind}/{key}.js" for kind in catalog.KINDS for key in catalog.entries(kind)
            if os.path.exists(os.path.join(web, kind, f"{key}.js"))]


def part_name(rel: str, text: bytes) -> str:
    """A scenery file's name in the collection's media, named after what is in it too."""
    kind, key = rel[:-len(".js")].split("/")
    return f"{SCRIPT_PREFIX}{kind}-{key}-{hashlib.sha1(text).hexdigest()[:10]}.js"


def _hhmm(iso: str | None, fallback: _dt.time) -> str:
    """The hour of a sunrise or sunset on this computer's clock, which the phone shares."""
    try:
        when = _dt.datetime.fromisoformat(iso) if iso else None
    except ValueError:
        when = None
    if when is None:
        return fallback.strftime("%H:%M")
    return (when.astimezone() if when.tzinfo else when).strftime("%H:%M")


def schedule(cfg: dict, now: _dt.datetime, real: dict | None = None, place: dict | None = None,
             scene_name=lambda _date: {}, days: int = SCHEDULE_DAYS) -> list:
    """The scene for each of the next `days` days, from today: what the settings choose on
    that date. The time of day is only a guess here; the phone uses its own clock when
    the mood says `clock`. Live weather is only known for today, and holds until `liveUntil`
    (ms); `fallback` is the weather after that."""
    out = []
    for i in range(days):
        date = now.date() + _dt.timedelta(days=i)
        noon = _dt.datetime.combine(date, _dt.time(12))
        mood = scene.choose_mood(cfg, noon, real if i == 0 else None, place if i == 0 else None)
        entry = {"date": date.isoformat(), "dayNumber": date.toordinal(), "mood": mood, **scene_name(date)}
        if mood.get("source") == "real":
            plain = scene.choose_mood(cfg, noon)
            entry["fallback"] = {"weather": plain["weather"], "wind": plain["wind"], "source": plain["source"]}
            entry["liveUntil"] = int((now + _dt.timedelta(hours=LIVE_WEATHER_HOURS)).timestamp() * 1000)
        out.append(entry)
    return out


def phone_payload(page: dict, cfg: dict, now: _dt.datetime, script: str, real: dict | None = None,
                  place: dict | None = None, scene_name=lambda _date: {}, parts: dict | None = None,
                  days: list | None = None) -> dict:
    """What the note holds: the desktop page's data (`page`, from payload.payload()), less
    what only the deck list can use, with the days' scenes and the script to draw it with."""
    data = {k: v for k, v in page.items() if k not in DESKTOP_ONLY}
    data.update(
        v=VERSION,
        script=script,
        parts=parts or {},  # "envs/aurora.js" -> its file in media, for the days' scenes (see scenery)
        updated=now.isoformat(timespec="minutes"),
        inAnki=False,  # no settings cog, and nothing to click through to
        tooltips=True,
        maxWidth=PHONE_MAX_WIDTH,
        # a strike plays once, and the phone cannot say it has been seen: the desktop plays it,
        # and the phone only when asked (a tap on its crater, or on "Asteroid struck")
        strike=dict(page["strike"], fresh=False) if page.get("strike") else None,
        days=schedule(cfg, now, real, place, scene_name) if days is None else days,
        sun={"rise": _hhmm((real or {}).get("sunrise"), scene.DEFAULT_SUNRISE),
             "set": _hhmm((real or {}).get("sunset"), scene.DEFAULT_SUNSET),
             "twilight": int(scene.TWILIGHT.total_seconds() // 60)},
    )
    return data


def encode(data: dict) -> str:
    """JSON for a note's field. The field is HTML, so it holds nothing HTML could take for
    markup (no <, > or &) and nothing Anki's editor would rewrite (ASCII only)."""
    text = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def same_forest(old: str, new: dict) -> bool:
    """Whether a note already holds this forest (whenever it was written), so a sync that
    changed nothing uploads nothing - unless the live weather it holds is running out."""
    try:
        was = json.loads(old)
    except ValueError:
        return False
    if not isinstance(was, dict):
        return False

    def gist(data: dict) -> dict:
        # when it was written, and how long its live weather holds, change at every sync; and
        # the temperature with every look at the weather (compared on its own, below)
        days = [{k: v for k, v in d.items() if k != "liveUntil"} for d in data.get("days") or []]
        for d in days:
            if isinstance(d.get("mood"), dict):
                d["mood"] = {k: v for k, v in d["mood"].items() if k != "temp"}
        return dict({k: v for k, v in data.items() if k != "updated"}, days=days)

    def temp(data: dict):
        mood = ((data.get("days") or [{}])[0].get("mood") or {})
        return mood.get("temp") if isinstance(mood.get("temp"), (int, float)) else None
    def live_until(data: dict):
        until = ((data.get("days") or [{}])[0]).get("liveUntil")
        return until if isinstance(until, (int, float)) else None
    now = json.loads(encode(new))
    a, b = temp(was), temp(now)
    near = a == b or (a is not None and b is not None and abs(a - b) < TEMP_UPLOAD_DEGREES)
    # live weather the phone is about to drop (less than half its hours left, by the new
    # note's own reckoning) is sent again, so it stays live while the computer keeps syncing
    held, fresh = live_until(was), live_until(now)
    expiring = held is not None and fresh is not None and held < fresh - LIVE_WEATHER_HOURS * 3600 * 1000 / 2
    return near and not expiring and gist(was) == gist(now)

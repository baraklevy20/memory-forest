"""What next year's recap (recap.py) can't read back from the review history: the scenery
the forest was in on each day you studied, and the real sky's weather on it while the
weather follows your city. Kept in the collection's own config, so it syncs to your other
computers with it, one key a month ("memoryForestDays.2027-01"): two computers studying
the same day can only write over that month's days, never the year's. The place the
weather was for is never kept, only what it was.

A month is {"5": {"s": "cherry", "w": ["rain", "clear"]}}: the day of the month, the
preset it was in ("custom" for your own mix; Surprise me daily's pick of the day, not
"daily"), and each weather seen on it, in the order seen (no "w" while the sky was not
the real one). Only the deck list's forest writes, on a day with reviews, never on a
debug date or the test forest."""

from __future__ import annotations

import datetime as _dt

from . import presets, scene

PREFIX = "memoryForestDays."  # + "YYYY-MM": the collection config key (synced)
DAILY = "daily"  # presets.match's answer for Surprise me daily


def key(day: _dt.date) -> str:
    return f"{PREFIX}{day.year:04d}-{day.month:02d}"


def scenery(cfg: dict, day: _dt.date) -> str:
    """The preset the forest is in on `day`: Surprise me daily's pick of that day, "custom" for
    your own mix."""
    which = presets.match(cfg)
    return presets.todays(cfg, day).key if which == DAILY else which


def record(col, cfg: dict, day: _dt.date, mood: dict, shown: _dt.date | None = None) -> bool:
    """Keep `day`'s scenery (Anki's day: until the rollover hour, still yesterday), and its weather if
    the real sky's; True if anything new was written. `shown`: the date the scenery was chosen for, if
    not `day` (after midnight, Surprise me daily has the new date's pick). A redraw that changes
    nothing writes nothing: each write marks the collection changed."""
    entry_key = key(day)
    was = _month(col, entry_key).get(str(day.day)) or {}
    now = {"s": scenery(cfg, shown or day)}
    seen = list(was.get("w") or [])
    if mood.get("source") == "real" and mood.get("weather") in scene.WEATHERS and mood["weather"] not in seen:
        seen.append(mood["weather"])
    if seen:
        now["w"] = seen
    if now == was:
        return False
    # (written over the month as kept, so a day or a field a newer version keeps stays as it was)
    kept = _raw(col, entry_key)
    kept[str(day.day)] = dict(kept.get(str(day.day)) if isinstance(kept.get(str(day.day)), dict) else {}, **now)
    col.set_config(entry_key, kept)
    return True


def days(col, year: int) -> dict:
    """The year's kept days: {date: {"scenery": key, "weather": [kinds]}}, oldest first; none
    the collection can't say."""
    out = {}
    for m in range(1, 13):
        for d, entry in sorted(_month(col, f"{PREFIX}{year:04d}-{m:02d}").items(), key=lambda kv: int(kv[0])):
            try:
                day = _dt.date(year, m, int(d))
            except ValueError:
                continue
            out[day] = {"scenery": entry["s"], "weather": list(entry.get("w") or [])}
    return out


def _raw(col, entry_key: str) -> dict:
    """A month as the collection keeps it ({} if it keeps none, or something else)."""
    try:
        kept = col.get_config(entry_key, {})
    except Exception:
        return {}
    return dict(kept) if isinstance(kept, dict) else {}


def _month(col, entry_key: str) -> dict:
    """A month as kept, less any day it can't read (an older or newer version's, or a hand edit)."""
    out = {}
    for d, entry in _raw(col, entry_key).items():
        if not (isinstance(d, str) and d.isdigit() and 1 <= int(d) <= 31 and isinstance(entry, dict)):
            continue
        if not (isinstance(entry.get("s"), str) and entry["s"]):
            continue
        clean = {"s": entry["s"]}
        w = entry.get("w")
        if isinstance(w, list):
            w = [x for x in w if isinstance(x, str)]
            if w:
                clean["w"] = w
        out[d] = clean
    return out

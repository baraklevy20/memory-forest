"""Presets: the ready-made scenes the settings dialog offers.

A preset is not a setting of its own - it is a shortcut that fills the five that matter
(environment, landscape, landmark, weather, time of day) in one go. Everything downstream
still reads those five, so nothing else in the add-on has to know presets exist, and the
Fine-tuning tab always shows exactly what is being drawn.

A preset pins its own weather and hour. "Follow the real weather and time" sets those two
to Automatic instead, and the preset still counts as chosen. Surprise me daily sets all
five to `daily`, which takes them from a different preset each day, in turn.

A seasonal preset (a `season` in its JSON) stays out of sight until the first day of its
week in the year it arrives, and from then on is there like any other. Each year, on the
first day of its week, everyone's forest changes to it once; the day after, the forest goes
back to what it was, unless it was changed in the meantime (see `follow_season`).

Nothing here imports aqt, so it also runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

#: In any of the five settings: take it from today's preset (see `of_the_day`).
DAILY = "daily"
LOOK = ("environment", "landscape", "landmark", "weather", "time_of_day")
SKY = ("weather", "time_of_day")


@dataclass(frozen=True)
class Preset:
    """One ready-made scene. `note` is the line shown under the dropdown."""

    key: str
    label: str
    environment: str
    landscape: str
    landmark: str = "none"
    weather: str = "clear"
    time: str = "day"
    note: str = ""
    #: (the day it first appears, (month, day) its week starts, (month, day) its last day), or ()
    season: tuple = ()

    def values(self) -> dict:
        """The five settings this preset stands for."""
        return {"environment": self.environment, "landscape": self.landscape,
                "landmark": self.landmark, "weather": self.weather, "time_of_day": self.time}


try:
    from . import catalog
except ImportError:  # tests and dev scripts import these files as top-level modules
    import catalog


def _month_day(text: str) -> tuple:
    month, day = (int(n) for n in text.split("-"))
    return month, day


def _season(spec: dict | None) -> tuple:
    """A preset's `season` from its JSON: {"from": "MM-DD", "to": "MM-DD", "first": year}.
    Its week has to fall within one year: from on or before to."""
    if not spec:
        return ()
    starts, ends = _month_day(spec["from"]), _month_day(spec["to"])
    return _dt.date(int(spec["first"]), *starts), starts, ends


def _catalogue() -> tuple:
    """One preset per environment, from the JSON beside its file, in their `order`."""
    out = []
    for env, spec in catalog.entries("envs").items():
        p = spec.get("preset")
        if p:
            out.append(Preset(p.get("key", env), p["label"], env, p["landscape"], p.get("landmark", "none"),
                              p.get("weather", "clear"), p.get("time", "day"), p.get("note", ""), _season(p.get("season"))))
    # not a scene of its own: a different one of the above each day
    out.append(Preset("daily", "Surprise me daily", DAILY, DAILY, DAILY, DAILY, DAILY,
                      "A different scenery every day, taking turns so each one comes round in order."))
    return tuple(out)


#: The catalogue, in the order the dropdown shows it. The first is the default.
FOREST_PRESETS: tuple = _catalogue()

CUSTOM = "custom"  # what the dropdown shows when the settings match no preset


def by_key(presets=FOREST_PRESETS) -> dict:
    return {p.key: p for p in presets}


def unlocked(preset: Preset, date) -> bool:
    """Whether a preset is out yet: a seasonal one waits for the first day of its first week."""
    return not preset.season or date >= preset.season[0]


def available(date, presets=FOREST_PRESETS) -> tuple:
    """The presets there are to choose from on `date`."""
    return tuple(p for p in presets if unlocked(p, date))


def hidden_environments(date, presets=FOREST_PRESETS) -> set:
    """The environments only a preset still waiting for its season uses: not to be offered yet."""
    return {p.environment for p in presets if not unlocked(p, date)} - {p.environment for p in available(date, presets)}


def of_the_day(date, presets=FOREST_PRESETS) -> Preset:
    """Today's preset for Surprise me daily: they take turns, one a day, so a new one
    comes every day and each comes round again after as many days as there are."""
    turn = [p for p in available(date, presets) if p.environment != DAILY]
    return turn[date.toordinal() % len(turn)]


def in_season(date, presets=FOREST_PRESETS) -> Preset | None:
    """The preset whose week `date` falls in, if any."""
    for p in available(date, presets):
        if p.season and p.season[1] <= (date.month, date.day) <= p.season[2]:
            return p
    return None


def season_ends(preset: Preset, date) -> _dt.date:
    """The day this year's week of a seasonal preset is over, and the forest goes back."""
    return _dt.date(date.year, *preset.season[2]) + _dt.timedelta(days=1)


def _before_its_week(tag: str | None, date, presets) -> bool:
    """Whether `date` comes before the week a season's tag ("key:year") stands for."""
    key, _, year = (tag or "").rpartition(":")
    p = by_key(presets).get(key)
    return bool(p and p.season and year.isdigit() and date < _dt.date(int(year), *p.season[1]))


# how many past seasons the record keeps, so a week already had is never had twice
SEASONS_REMEMBERED = 10


def follow_season(cfg: dict, record: dict | None, date, presets=FOREST_PRESETS) -> tuple:
    """(the look settings to change, or {}; the record to keep) for `date`.

    On the first day of a seasonal preset's week (or the first day the forest is drawn in
    it) the forest changes to that preset, once a year: changing it back during the week is
    respected. Once the week is over, the settings from before come back - unless they were
    changed in the meantime, when whatever was chosen stays. The record holds the week in
    progress (`active`: its tag, the settings before and after) and the weeks already had."""
    record = record if isinstance(record, dict) else {}
    done, active = list(record.get("done") or []), record.get("active")
    look = {k: cfg.get(k) for k in LOOK}
    now = in_season(date, presets)
    tag = f"{now.key}:{date.year}" if now else None
    change = {}
    if isinstance(active, dict) and active.get("tag") != tag:
        if look == active.get("applied"):  # untouched since: put back what was there
            change = dict(active.get("before") or {})
        if _before_its_week(active.get("tag"), date, presets):  # the clock went back: it hasn't happened yet
            done = [t for t in done if t != active.get("tag")]
        active = None
    if now and tag not in done:
        before = change or look
        change = apply(now.key, before, presets)
        active = {"tag": tag, "before": before, "applied": change}
        done.append(tag)
    return change, {"done": done[-SEASONS_REMEMBERED:], "active": active}


def follows_real_sky(cfg: dict) -> bool:
    """Weather and time both Automatic: the real sky and the clock, whatever the preset."""
    return all(cfg.get(k) == "auto" for k in SKY)


def match(cfg: dict, presets=FOREST_PRESETS) -> str:
    """Which preset these settings are, or CUSTOM.

    The dialog derives the dropdown from the five settings rather than storing a preset
    of its own, so a config edited by hand, or left behind by an older version, can never
    claim to be a preset it no longer matches.
    """
    # following the real sky replaces a preset's own weather and hour, not the preset
    keys = [k for k in LOOK if not (follows_real_sky(cfg) and k in SKY)]
    for p in presets:
        values = p.values()
        if all(cfg.get(k) == values[k] for k in keys):
            return p.key
    return CUSTOM


def options(presets=FOREST_PRESETS) -> list:
    """(key, label) pairs for the dropdown, with Custom last."""
    return [(p.key, p.label) for p in presets] + [(CUSTOM, "Custom")]


def apply(key: str, current: dict, presets=FOREST_PRESETS) -> dict:
    """The five settings after picking `key` from the dropdown.

    This is what makes the Fine-tuning tab show the preset's own choices rather than
    whatever was there before it: picking Synthwave really does set environment,
    landscape, landmark, weather and time of day, and the tab is only displaying them.
    Picking Custom changes nothing - it is the name for settings that match no preset,
    not a setting of its own.
    """
    spec = by_key(presets).get(key)
    if not spec:
        return dict(current)
    values = dict(spec.values())
    if follows_real_sky(current):  # picking a preset keeps the real sky on
        values.update(dict.fromkeys(SKY, "auto"))
    return values

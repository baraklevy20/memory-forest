"""Presets: the ready-made scenes the settings dialog offers.

A preset is not a setting of its own - it is a shortcut that fills the five that matter
(environment, landscape, landmark, weather, time of day) in one go. Everything downstream
still reads those five, so nothing else in the add-on has to know presets exist, and the
Fine-tuning tab always shows exactly what is being drawn.

A preset pins its own weather and hour. "Follow the real weather and time" sets those two
to Automatic instead, and the preset still counts as chosen. Surprise me daily sets all
five to `daily`, which takes them from a different preset each day, in turn.

Nothing here imports aqt, so it also runs in the tests and the dev scripts.
"""

from __future__ import annotations

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

    def values(self) -> dict:
        """The five settings this preset stands for."""
        return {"environment": self.environment, "landscape": self.landscape,
                "landmark": self.landmark, "weather": self.weather, "time_of_day": self.time}


try:
    from . import catalog
except ImportError:  # tests and dev scripts import these files as top-level modules
    import catalog


def _catalogue() -> tuple:
    """One preset per environment, from the JSON beside its file, in their `order`."""
    out = []
    for env, spec in catalog.entries("envs").items():
        p = spec.get("preset")
        if p:
            out.append(Preset(p.get("key", env), p["label"], env, p["landscape"], p.get("landmark", "none"),
                              p.get("weather", "clear"), p.get("time", "day"), p.get("note", "")))
    # not a scene of its own: a different one of the above each day
    out.append(Preset("daily", "Surprise me daily", DAILY, DAILY, DAILY, DAILY, DAILY,
                      "A different scenery every day, taking turns so each one comes round in order."))
    return tuple(out)


#: The catalogue, in the order the dropdown shows it. The first is the default.
FOREST_PRESETS: tuple = _catalogue()

CUSTOM = "custom"  # what the dropdown shows when the settings match no preset


def by_key(presets=FOREST_PRESETS) -> dict:
    return {p.key: p for p in presets}


def of_the_day(date, presets=FOREST_PRESETS) -> Preset:
    """Today's preset for Surprise me daily: they take turns, one a day, so a new one
    comes every day and each comes round again after as many days as there are."""
    turn = [p for p in presets if p.environment != DAILY]
    return turn[date.toordinal() % len(turn)]


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

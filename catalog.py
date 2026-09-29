"""What this copy of the add-on can draw, read from the files that are actually here.

Every environment, landscape and landmark is a pair of files under web/: the JS that draws
it and a small JSON beside it with its label (and, for an environment, the preset that
shows it off). Nothing else in the add-on lists them, so an edition is simply a set of
files: leave one out and it is gone from the dialog, the presets and the checks alike.

Nothing here imports aqt, so it also runs in the tests and the dev scripts.
"""

from __future__ import annotations

import json
import os

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
KINDS = ("envs", "landscapes", "landmarks")
# The scripts every forest loads, in this order, before its own environment, landscape and
# landmark: util.js makes window.AnkiForest, the rest add to it, and each part of the pixel
# engine uses the parts before it. The panel, the render checks and the gallery all load these.
SCRIPTS = (
    "util.js", "layout.js", "scenery.js", "theme.js", "visitors.js", "ponds.js", "tooltips.js",
    "caption.js", "hover.js", "core.js", "effects.js", "effects/weather.js", "effects/ambience.js",
    "engines/pixel/trees.js", "engines/pixel/sky.js", "engines/pixel/ground.js",
    "engines/pixel/water.js", "engines/pixel/engine.js",
    # the events, each drawing in the order it loads (see web/events.js)
    "events.js", "events/crows.js", "events/grass.js", "events/flowers.js", "events/asteroid.js",
)


def entries(kind: str) -> dict:
    """key -> its JSON, in the order the JSON asks for (then by key)."""
    folder = os.path.join(WEB, kind)
    found = {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                found[name[:-len(".json")]] = json.load(f)

    def order(item):
        key, spec = item
        return ((spec.get("preset") or spec).get("order", 0), key)
    return dict(sorted(found.items(), key=order))


def labels(kind: str) -> dict:
    """key -> label, for the dropdowns."""
    return {key: spec["label"] for key, spec in entries(kind).items()}

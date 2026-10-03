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
    "events.js", "events/crows.js", "events/robins.js", "events/grass.js", "events/tumbleweeds.js",
    "events/flowers.js", "events/asteroid.js", "events/fire.js",
)

# Experiments only the private copy has, in web/drafts/: its deck list loads them after SCRIPTS
# (the phone does not), no edition ships them and the public repo never gets them (dev/editions.py).
DRAFTS = "drafts"

# A release ships SCRIPTS joined into this one file (dev/package.py): a page that loads one
# script rather than thirty is lighter on the web view, which keeps something of every
# script it ever loaded, at every redraw of the deck list. This copy has none, and loads the
# files one by one, as they are edited.
BUNDLE = "forest.bundle.js"


def core_scripts(web: str = WEB) -> tuple:
    """What a forest loads before its own scenery: the bundle where there is one, or SCRIPTS."""
    return (BUNDLE,) if os.path.exists(os.path.join(web, BUNDLE)) else SCRIPTS


def draft_scripts(web: str = WEB) -> tuple:
    """The scripts in web/drafts/, if this copy has any: none in a release."""
    folder = os.path.join(web, DRAFTS)
    if not os.path.isdir(folder):
        return ()
    return tuple(f"{DRAFTS}/{n}" for n in sorted(os.listdir(folder)) if n.endswith(".js"))


def scenery_files(mood: dict, web: str = WEB) -> list:
    """The files a scene's environment, landscape and landmark are drawn with (as
    "envs/aurora.js"), those this copy has: the deck list and the phone load these."""
    out = []
    for kind, key in zip(KINDS, (mood.get("special"), mood.get("landscape"), mood.get("landmark"))):
        rel = f"{kind}/{key}.js"
        if key and os.path.exists(os.path.join(web, rel)):
            out.append(rel)
    return out


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

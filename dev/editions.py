"""The editions built from this folder, as listed in editions.json.

An edition is a set of environments. It ships their files, and the landscapes and landmarks
its presets use, so it never carries scenery nothing in it can show. The public repo has
no editions.json: there, everything present is the edition.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
EDITIONS = os.path.join(ADDON, "editions.json")
SCENERY = ("envs", "landscapes", "landmarks")
ALL = "*"


def available() -> dict:
    """name -> spec, or {} where there is no editions.json."""
    if not os.path.exists(EDITIONS):
        return {}
    with open(EDITIONS, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def spec(name: str) -> dict:
    editions = available()
    if name not in editions:
        raise SystemExit(f"no edition {name!r}; editions.json has: {', '.join(editions) or 'none'}")
    return editions[name]


def scenery(name: str) -> dict:
    """kind -> the keys of that kind this edition ships, and "presets" -> its preset keys."""
    import sys
    sys.path.insert(0, ADDON)
    import catalog
    envs = catalog.entries("envs")
    wanted = spec(name)["envs"]
    if wanted == ALL:
        wanted = list(envs)
        return {**{kind: set(catalog.entries(kind)) for kind in SCENERY},
                "presets": {envs[k]["preset"].get("key", k) for k in wanted if envs[k].get("preset")}}
    missing = set(wanted) - set(envs)
    if missing:
        raise SystemExit(f"edition {name!r} lists environments with no files: {', '.join(sorted(missing))}")
    presets = {k: envs[k]["preset"] for k in wanted if envs[k].get("preset")}
    return {"envs": set(wanted),
            "landscapes": {p["landscape"] for p in presets.values()},
            "landmarks": {p.get("landmark", "none") for p in presets.values()},
            "presets": {p.get("key", k) for k, p in presets.items()}}


def keeps(rel: str, keep: dict) -> bool:
    """Whether a path relative to the add-on belongs in an edition with this scenery."""
    parts = rel.replace(os.sep, "/").split("/")
    if len(parts) == 3 and parts[0] == "web" and parts[1] in SCENERY:
        return os.path.splitext(parts[2])[0] in keep[parts[1]]
    # a preset's animated preview (docs/animated/<preset>.gif) goes wherever the preset does
    if len(parts) == 3 and parts[:2] == ["docs", "animated"]:
        return os.path.splitext(parts[2])[0] in keep["presets"]
    return True


def manifest(name: str) -> str:
    """manifest.json for an edition: its own name, package and conflicts."""
    with open(os.path.join(ADDON, "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    s = spec(name)
    m.update(name=s["name"], package=s["package"], conflicts=s.get("conflicts", []))
    return json.dumps(m, indent=2) + "\n"

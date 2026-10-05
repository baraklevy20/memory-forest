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
# the sceneries Plus has and the base does not, which the base edition's picker shows locked
# (settings/scenery_picker.py); dev/thumbnails.py writes it, from editions.json
PLUS_LIST = os.path.join(ADDON, "settings", "plus.json")


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
    # every edition's presets, so the docs can show off Plus scenery wherever they go
    shown = set()
    for other in available().values():
        keys = list(envs) if other["envs"] == ALL else [k for k in other["envs"] if k in envs]
        shown |= {envs[k]["preset"].get("key", k) for k in keys if envs[k].get("preset")}
    wanted = spec(name)["envs"]
    if wanted == ALL:
        wanted = list(envs)
        return {**{kind: set(catalog.entries(kind)) for kind in SCENERY},
                "presets": {envs[k]["preset"].get("key", k) for k in wanted if envs[k].get("preset")},
                "shown": shown}
    missing = set(wanted) - set(envs)
    if missing:
        raise SystemExit(f"edition {name!r} lists environments with no files: {', '.join(sorted(missing))}")
    presets = {k: envs[k]["preset"] for k in wanted if envs[k].get("preset")}
    return {"envs": set(wanted),
            "landscapes": {p["landscape"] for p in presets.values()},
            "landmarks": {p.get("landmark", "none") for p in presets.values()},
            "presets": {p.get("key", k) for k, p in presets.items()},
            "shown": shown}


def keeps(rel: str, keep: dict) -> bool:
    """Whether a path relative to the add-on belongs in an edition with this scenery."""
    parts = rel.replace(os.sep, "/").split("/")
    # experiments (web/drafts/, see catalog.DRAFTS) stay in this copy: no edition, and so not the public repo
    if len(parts) > 2 and parts[:2] == ["web", "drafts"]:
        return False
    if len(parts) == 3 and parts[0] == "web" and parts[1] in SCENERY:
        return os.path.splitext(parts[2])[0] in keep[parts[1]]
    # a preset's animated preview (docs/animated/<preset>.gif) goes wherever any edition has
    # the preset, so the public docs can show what Plus has now; only drafts stay behind
    if len(parts) == 3 and parts[:2] == ["docs", "animated"]:
        return os.path.splitext(parts[2])[0] in keep["shown"]
    # and so does its picker tile (settings/scenery/<preset>.png, and scenery_anim/<preset>.gif),
    # which the base edition shows locked
    if len(parts) == 3 and parts[:2] in (["settings", "scenery"], ["settings", "scenery_anim"]):
        return os.path.splitext(parts[2])[0] in keep["shown"]
    return True


def plus_only() -> list:
    """What settings/plus.json lists: each preset Plus has and the base does not, as {key,
    label, note}, in the catalogue's order; none in the public repo, which has no editions.
    One kept to its holiday week is left out: it shows nowhere outside that week."""
    editions = available()
    if "plus" not in editions or "base" not in editions:
        return []
    import sys
    sys.path.insert(0, ADDON)
    import catalog
    base = scenery("base")["presets"]
    out = []
    for key, spec in catalog.entries("envs").items():
        preset = spec.get("preset")
        if not preset or preset.get("season") or (editions["plus"]["envs"] != ALL and key not in editions["plus"]["envs"]):
            continue
        k = preset.get("key", key)
        if k not in base:
            out.append({"key": k, "label": preset["label"], "note": preset.get("note", "")})
    return out


def plus_list_text() -> str:
    return json.dumps(plus_only(), indent=2, ensure_ascii=False) + "\n"


def manifest(name: str) -> str:
    """manifest.json for an edition: its own name, package and conflicts."""
    with open(os.path.join(ADDON, "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    s = spec(name)
    m.update(name=s["name"], package=s["package"], conflicts=s.get("conflicts", []))
    return json.dumps(m, indent=2) + "\n"

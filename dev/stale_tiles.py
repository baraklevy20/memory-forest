"""Which picker tiles are older than their scenery: each preset's still picture (dev/thumbnails.py)
and moving one (dev/tile_gifs.py) is drawn from its environment, landscape and landmark, and
those scripts note a fingerprint of their files here as they draw it. The tests compare the
fingerprints with the files as they are now, so an edited scenery asks for its tiles again.

    python3 dev/stale_tiles.py   # the tiles to draw again, and the commands that do it

Only the files a preset itself is drawn from count: a change to the engine everyone shares
(trees.js, sky.js) would mark every tile at once. dev/render_check.py compare names the
presets whose scenes drew differently instead, which is where such a change shows.

Only the sceneries some edition ships are noted, so the file names nothing private (drafts
go unchecked). In the public repo, a Plus scenery has no files to compare and is left alone.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

import editions

import catalog
import presets

SOURCES = os.path.join(HERE, "tile_sources.json")
# what draws each picture, as the fingerprint file names them
KINDS = {"png": "npm run thumbs --", "gif": "python3 dev/tile_gifs.py"}


def fingerprint(preset) -> str | None:
    """A short hash of the files `preset` is drawn from, or None if this copy lacks them."""
    files = []
    for kind, key in zip(catalog.KINDS, (preset.environment, preset.landscape, preset.landmark)):
        for ext in ("js", "json"):
            path = os.path.join(catalog.WEB, kind, f"{key}.{ext}")
            if os.path.exists(path):
                files.append(path)
    # every environment has its JSON (the plain forest has no script: the engine draws it)
    if not os.path.exists(os.path.join(catalog.WEB, "envs", f"{preset.environment}.json")):
        return None
    h = hashlib.sha1()
    for path in files:
        h.update(os.path.relpath(path, catalog.WEB).replace(os.sep, "/").encode())
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:12]


def noted() -> dict:
    """kind ("png", "gif") -> preset key -> the fingerprint it was drawn from."""
    try:
        with open(SOURCES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def tracked() -> set | None:
    """The preset keys to note: those some edition ships (None: every one, where there are no editions)."""
    if not editions.available():
        return None
    shown = set()
    for name in editions.available():
        shown |= editions.scenery(name)["presets"]
    return shown


def note(kind: str, keys) -> None:
    """Note what these presets' `kind` pictures were just drawn from."""
    keep = tracked()
    data = noted()
    mine = data.setdefault(kind, {})
    for p in presets.FOREST_PRESETS:
        if p.key in keys and (keep is None or p.key in keep):
            now = fingerprint(p)
            if now:
                mine[p.key] = now
    data[kind] = dict(sorted(mine.items()))
    with open(SOURCES, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")


def stale() -> dict:
    """kind -> the preset keys whose `kind` picture is older than their files (or never noted)."""
    keep = tracked()
    data = noted()
    out = {}
    for kind in KINDS:
        mine = data.get(kind, {})
        out[kind] = [p.key for p in presets.FOREST_PRESETS
                     if p.key != presets.DAILY and (keep is None or p.key in keep)
                     and (now := fingerprint(p)) is not None and mine.get(p.key) != now]
    return out


def advice(found: dict) -> str:
    """The commands that draw these again, one line each."""
    return "\n".join(f"  {KINDS[kind]} {' '.join(keys)}" for kind, keys in found.items() if keys)


def main() -> None:
    found = stale()
    if not any(found.values()):
        print("every tile is up to date")
        return
    print("tiles older than their scenery; draw them again with:\n" + advice(found))
    sys.exit(1)


if __name__ == "__main__":
    main()

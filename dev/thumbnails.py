"""Draw the two pictures of each preset the settings show: the real scene, rendered in headless
Chrome on a young test forest, a piece of it (sky, horizon and the first trees) in the
scene's own pixels. settings/scenery/<preset>.png is the picker's tile; settings/scenery_small/
<preset>.png the Scenery card's, from the scene drawn as small as the engine draws it.

    python3 dev/thumbnails.py              # every preset
    python3 dev/thumbnails.py aurora bamboo  # just these presets, by key

Run it for a new preset, or after changing how one looks; the tests fail while a preset has
no picture. Each edition ships only its own presets' pictures (dev/editions.py). Needs Chrome.
"""

from __future__ import annotations

import base64
import concurrent.futures
import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

import render_check
from render_check import WORKERS, render

import catalog
import presets

# Each picture, in the scene's own pixels (16:9): a piece of the scene rather than all of it
# shrunk, so every pixel of the art is kept, and the settings show it a pixel a point. The
# big one is cut from the scene at the panel's usual width; the small one from the scene at
# the narrowest panel the engine draws (120x60 pixels), so it holds nearly all of it.
# (folder, width, height, panel width in CSS pixels)
SIZES = (
    (os.path.join(ADDON, "settings", "scenery"), 192, 108, 700),
    (os.path.join(ADDON, "settings", "scenery_small"), 96, 54, 240),
)
# A young forest: enough trees to show the scenery's own kind (bamboo, say, or mushrooms),
# few enough that the land and its landmark still show between them.
TREES = 30
# Where the piece is cut, as a share of the room left either side and above and below: the
# middle across, a little above the middle down (the sky, where most presets' signature
# is), unless a preset's signature lies elsewhere: its JSON then says where, as
# "picture": [across, down] (a landmark low on the water, say, or one on the far horizon).
ACROSS, DOWN = 0.5, 0.35


def framing() -> dict:
    """preset key -> (across, down), for the presets whose JSON places their picture."""
    out = {}
    for env, spec in catalog.entries("envs").items():
        preset = spec.get("preset") or {}
        if preset.get("picture"):
            out[preset.get("key", env)] = tuple(preset["picture"])
    return out


FRAMING = framing()


def thumbnail(png: bytes, key: str, width: int, height: int) -> Image.Image:
    scene = Image.open(io.BytesIO(png)).convert("RGB")
    if scene.width < width or scene.height < height:
        raise SystemExit(f"{key}: the scene is {scene.width}x{scene.height}, smaller than its picture")
    across, down = FRAMING.get(key, (ACROSS, DOWN))
    left, top = round((scene.width - width) * across), round((scene.height - height) * down)
    return scene.crop((left, top, left + width, top + height))


def main() -> None:
    wanted = set(sys.argv[1:])
    chosen = [p for p in presets.FOREST_PRESETS if p.key != presets.DAILY and (not wanted or p.key in wanted)]
    unknown = wanted - {p.key for p in chosen}
    if unknown:
        raise SystemExit(f"no preset {', '.join(sorted(unknown))}")
    cases = [(p.key, dict(p.values()), TREES) for p in chosen]
    failed = []
    for out, width, height, panel in SIZES:
        os.makedirs(out, exist_ok=True)
        render_check.PANEL_PX = panel  # (the page is drawn at this width; one size at a time)
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for key, r in pool.map(render, cases):
                if r.get("errors") or not r.get("png"):
                    failed.append(key)
                    print(f"  {key} {width}x{height}: failed {r.get('errors')}")
                    continue
                picture = thumbnail(base64.b64decode(r["png"].split(",", 1)[1]), key, width, height)
                picture.save(os.path.join(out, f"{key}.png"), optimize=True)
                print(f"  {key} {width}x{height}")
    if failed:
        raise SystemExit(f"{len(failed)} failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()

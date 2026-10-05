"""Record each preset's picker tile as a looping GIF: the same piece of the scene as its still
picture (dev/thumbnails.py), moving, a pixel a point. settings/scenery_anim/<preset>.gif; the
picker shows it in place of settings/scenery/<preset>.png where there is one.

    python3 dev/tile_gifs.py              # every preset
    python3 dev/tile_gifs.py aurora bamboo  # just these presets, by key

It records as dev/make_gif.py does (the real files in headless Chrome, the clock driven by
hand) on the young forest the still pictures use. Needs Chrome and ffmpeg.
"""

from __future__ import annotations

import base64
import concurrent.futures
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

import make_gif
import stale_tiles
import thumbnails
from render_check import CHROME, WORKERS

import presets

OUT = os.path.join(ADDON, "settings", "scenery_anim")
# the still picture's piece, from the scene at the still picture's panel width
WIDTH, HEIGHT, PANEL = 192, 108, 700
SECONDS, FPS = 4, 15  # the engine draws ~15 frames a second (web/core.js FRAME_MS)


def record(key: str) -> tuple:
    """(whether it was drawn, the line to print)."""
    cfg = dict(presets.by_key()[key].values())
    frames = SECONDS * FPS
    make_gif.PANEL_PX, make_gif.FPS = PANEL, FPS
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(make_gif.page(cfg, thumbnails.TREES, frames, make_gif.HIDE))
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--window-size={PANEL + 40},600",
                              "--virtual-time-budget=60000", "--dump-dom", "file://" + path],
                             capture_output=True, text=True, timeout=make_gif.CHROME_TIMEOUT_SECS).stdout
        m = re.search(r'<pre id="?o"?>(.*?)</pre>', dom, re.S)
        if not m:
            return False, f"{key}: the page never reported back"
        r = json.loads(html.unescape(m.group(1)))
        if r["errors"]:
            return False, f"{key}: " + r["errors"][0]
        for i, shot in enumerate(r["shots"]):
            png = base64.b64decode(shot.split(",", 1)[1])
            thumbnails.thumbnail(png, key, WIDTH, HEIGHT).save(os.path.join(tmp, f"f{i:04d}.png"))
        out = os.path.join(OUT, f"{key}.gif")
        # one palette for the whole loop, so colours don't flicker between frames
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                        "-vf", "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=none",
                        "-loop", "0", out], check=True)
        return True, f"  {key}: {len(r['shots'])} frames ({os.path.getsize(out) // 1024} KB)"


def main() -> None:
    wanted = set(sys.argv[1:])
    chosen = [p.key for p in presets.FOREST_PRESETS if p.key != presets.DAILY and (not wanted or p.key in wanted)]
    unknown = wanted - set(chosen)
    if unknown:
        raise SystemExit(f"no preset {', '.join(sorted(unknown))}")
    os.makedirs(OUT, exist_ok=True)
    drawn = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for key, (ok, line) in zip(chosen, pool.map(record, chosen)):
            print(line)
            if ok:
                drawn.add(key)
    stale_tiles.note("gif", drawn)
    if len(drawn) < len(chosen):
        raise SystemExit(f"{len(chosen) - len(drawn)} failed")


if __name__ == "__main__":
    main()

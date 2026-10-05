"""Record a preset as an animated GIF, as the README shows them (docs/animated/).

    python3 dev/make_gif.py bamboo             # -> docs/animated/bamboo.gif
    python3 dev/make_gif.py bamboo synthwave   # several at once
    python3 dev/make_gif.py --docs                  # every GIF docs/animated/ already has
    python3 dev/make_gif.py bamboo --trees 150 --seconds 6 --out /tmp
    python3 dev/make_gif.py bamboo --loop 8         # a seamless 8-second loop (the engine's loop mode)

It mounts the real files in headless Chrome on the test forest (no study history of
yours), drives the animation clock by hand so every frame is the same length, and stitches
the frames with ffmpeg: no dithering, each canvas pixel drawn as a SCALE x SCALE block.

Needs Chrome and ffmpeg.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
DOCS = os.path.join(ADDON, "docs", "animated")
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

from render_check import CHROME, NOW, scripts

import fake_forest
import forest_data
import presets
import scene

# the panel is this wide, so the canvas is PANEL_PX / SCALE pixels across (core.js picks the
# scale: one step per 300 CSS pixels): 388 x 194, shown at twice that
PANEL_PX, SCALE = 776, 2
# the test forest's size, as the 1.0 GIFs and the render checks have it: open enough that
# the hills show over the treeline, and a pond from its one long break
TREES = 200
# the animals that take years are left for people to find: not in the GIFs
HIDE = ("bear", "squirrel", "eagle", "cabin")
SECONDS, FPS = 5, 15
# the clock starts here (ms), past the moment a scene first draws, so nothing is mid-appearance
START_MS = 20000
CHROME_TIMEOUT_SECS = 300


def page(cfg: dict, n: int, frames: int, hide: tuple, loop: float | None = None) -> str:
    mood = scene.choose_mood(dict(cfg, landmark=cfg.get("landmark", "none")), NOW)
    f = forest_data.merge_old(fake_forest.make(n))
    visitors = [v for v in f["visitors"] if v["key"] not in hide]
    data = {"trees": f["trees"], "stats": f["stats"], "visitors": visitors, "merged": f.get("merged"),
            "forestSeed": f["forest_seed"], "anniversaries": [], "events": [], "journal": "",
            "mood": mood, "environmentName": "", "animations": True,
            "tooltips": False, "maxWidth": PANEL_PX, "testForest": True}
    if loop:
        data["loop"] = loop  # every motion repeats in this many seconds (AF.LOOP, web/util.js)
    # a loop takes its frames exactly one apart from its first moment, so the frame after the
    # last would be the first again; otherwise a little over a frame apart, so the loop's
    # frame timer never skips one
    step, first = (1000 / FPS, 0) if loop else (1000 / FPS + 0.5, 1)
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0}}.af-panel{{width:{PANEL_PX}px;margin:0;padding:0}}</style>"
            # the clock is ours: animation frames and timers wait in a queue until pump() runs
            # them at a time we choose, and performance.now() says that time too (the loop sleeps
            # between frames on a timer, so timers have to keep our time as well)
            "<script>let NOW_MS = 0, TID = 0; const Q = [], T = [];"
            "window.requestAnimationFrame = cb => { Q.push(cb); return Q.length; };"
            "window.setTimeout = (cb, ms) => { T.push({ id: ++TID, at: NOW_MS + (+ms || 0), cb }); return TID; };"
            "window.clearTimeout = id => { const i = T.findIndex(t => t.id === id); if (i >= 0) T.splice(i, 1); };"
            "window.requestIdleCallback = cb => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 0);"
            "performance.now = () => NOW_MS; window.ERRS = [];"
            "window.onerror = (m, f, l, c, e) => { window.ERRS.push(String((e && e.stack) || m)); };"
            "function pump(ms) { NOW_MS = ms;"
            " for (let due; (due = T.filter(t => t.at <= ms)).length;) due.forEach(t => { T.splice(T.indexOf(t), 1); t.cb(); });"
            " const run = Q.splice(0); run.forEach(cb => cb(ms)); }</script>"
            "<div class='af-panel' id=p></div><pre id=o></pre>"
            f"<script>{scripts()}</script><script>window.D = {json.dumps(data)};</script>"
            f"<script>NOW_MS = {START_MS};"
            "try { AnkiForest.mount(document.getElementById('p'), window.D, { now: true }); }"
            "catch (e) { window.ERRS.push('mount: ' + (e.stack || e)); }"
            "const shots = [], c = document.querySelector('canvas');"
            # each pump is one frame: the loop draws when more than its frame time has passed
            f"for (let i = {first}; i < {first} + {frames}; i++) {{ pump({START_MS} + i * {step}); shots.push(c.toDataURL()); }}"
            "document.getElementById('o').textContent = JSON.stringify({ errors: window.ERRS, w: c.width, h: c.height, shots });"
            "</script>")


def record(key: str, cfg: dict, out: str, n: int, seconds: float, hide: tuple, loop: float | None = None) -> None:
    frames = round((loop or seconds) * FPS)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.html")
        open(path, "w", encoding="utf-8").write(page(cfg, n, frames, hide, loop))
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--window-size={PANEL_PX + 40},600",
                              "--virtual-time-budget=60000", "--dump-dom", "file://" + path],
                             capture_output=True, text=True, timeout=CHROME_TIMEOUT_SECS).stdout
        m = re.search(r'<pre id="?o"?>(.*?)</pre>', dom, re.S)
        if not m:
            sys.exit(f"{key}: the page never reported back")
        r = json.loads(html.unescape(m.group(1)))
        if r["errors"]:
            sys.exit(f"{key}: " + r["errors"][0])
        for i, shot in enumerate(r["shots"]):
            open(os.path.join(tmp, f"f{i:04d}.png"), "wb").write(base64.b64decode(shot.split(",", 1)[1]))
        # one palette for the whole loop, so colours don't flicker between frames
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                        "-vf", f"scale=iw*{SCALE}:ih*{SCALE}:flags=neighbor,split[a][b];[a]palettegen=stats_mode=full[p];"
                        "[b][p]paletteuse=dither=none", "-loop", "0", out], check=True)
    print(f"{key}: {r['w'] * SCALE}x{r['h'] * SCALE}, {len(r['shots'])} frames -> {os.path.relpath(out, ADDON)} "
          f"({os.path.getsize(out) // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Record presets as animated GIFs.")
    ap.add_argument("presets", nargs="*", help="preset keys, e.g. bamboo")
    ap.add_argument("--docs", action="store_true", help="every GIF docs/animated/ already has")
    ap.add_argument("--trees", type=int, default=TREES)
    ap.add_argument("--seconds", type=float, default=SECONDS)
    ap.add_argument("--out", default=DOCS, help="the folder to write to")
    ap.add_argument("--loop", type=float, help="record one seamless loop of this many seconds (overrides --seconds)")
    ap.add_argument("--hide", default=",".join(HIDE), help="animals left out, comma-separated ('' shows every one)")
    a = ap.parse_args()
    by_key = {p.key: p for p in presets.FOREST_PRESETS}
    keys = list(a.presets)
    if a.docs:
        keys += sorted(f[:-4] for f in os.listdir(DOCS) if f.endswith(".gif"))
    if not keys:
        ap.error("name a preset, or pass --docs")
    unknown = [k for k in keys if k not in by_key]
    if unknown:
        sys.exit(f"no preset called {', '.join(unknown)}; there are: {', '.join(by_key)}")
    os.makedirs(a.out, exist_ok=True)
    for k in dict.fromkeys(keys):
        record(k, dict(by_key[k].values()), os.path.join(a.out, k + ".gif"), a.trees, a.seconds, tuple(filter(None, a.hide.split(","))), a.loop)


if __name__ == "__main__":
    main()

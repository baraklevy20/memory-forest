"""Record what each Nature level does to a forest as a short looping GIF, for the Forest tab:
settings/nature/<level>.gif, a pixel a point. The real engine in headless Chrome, on a small
made-up forest studied every day, then days go by:

    Peaceful   a month away changes nothing; back again, a pond marks the break and the forest
               carries on (by day, so the water reads as water)
    Wild       two days away and smoke rises, from the third a fire spreads; back to study, it
               dies down day by day and is out after seven
    Merciless  the asteroid waits in the sky, a day missed and it strikes, the forest is a
               crater, and a new one grows from it

Each day is the forest as events.py makes it for those days studied, as the Debug tab's
timeline does. A row of day marks in the top left corner counts the days: green for a day
studied, red for a day missed (the bottom left holds the tile's name, settings/forest_tab.py).

    python3 dev/nature_gifs.py            (npm run nature-gifs)
    python3 dev/nature_gifs.py wild       just this level

Needs Chrome, ffmpeg and gifsicle.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "e2e"))  # (the render check's page and Chrome)

from make_gif import CLOCK_JS
from render_page import CHROME, NOW, scripts

import events
import fake_forest
import forest_data
import presets
import scene

OUT = os.path.join(ADDON, "settings", "nature")
# the panel's CSS width: core.js draws it at 2 CSS pixels a canvas pixel, so the canvas (and the
# GIF) is half of it across and half that high (settings/forest_tab.py NATURE_GIF_W, _H)
PANEL_PX = 300
TREES = 48  # few enough that the fire and the new forest's first trees can be made out at this size
# Peaceful's break: a month, so its pond is as big as a pond gets (web/layout.js POND_SLOTS), in a
# forest small enough that the pond lands near the front and the middle, by day (at the golden
# hour the water takes the sky's sand colour and reads as a rug). A pond in the front row lies
# flat (web/ponds.js); from the third day back there is a row in front of it and it is whole,
# so the first two days back go by quickly
PEACEFUL_AWAY, PEACEFUL_TREES, PEACEFUL_TIME = 30, 26, "day"
# at most this many day marks: past it, the oldest scroll out of the corner
MAX_MARKS = 18
SCENERY = "golden_lake"
FPS = 15
START_MS = 20000  # past the moment a scene first draws
HOLD = 2 * FPS  # the last day shown this long before the loop starts again
STUDIED_BEFORE = 3  # day marks for the days studied before the first one shown
# the day marks: squares MARK px wide, GAP apart, on a backing PAD px around them, in the
# top left corner, INSET from the edges
MARK, GAP, PAD, INSET = 3, 1, 2, 3
STUDIED, MISSED, BACKING = "#7cc85a", "#e0705a", "rgba(0,0,0,0.55)"


def _iso(ago: int) -> str:
    return (NOW.date() - dt.timedelta(days=ago)).isoformat()


def forest_after(level: str, away: int, back: int) -> tuple:
    """The made-up forest after `away` days missed in a row and then `back` days studied (the
    last of them today), as Nature leaves it: (forest, the page's extras). With back = 0, today
    has no reviews yet (it isn't missed until it ends)."""
    base = fake_forest.make(PEACEFUL_TREES if level == "peaceful" else TREES)
    if back:
        shift, studied = back + away, set(range(back))
    else:
        shift, studied = away + 1, set()
    trees = [dict(t, ago=t["ago"] + shift, date=_iso(t["ago"] + shift)) for t in base["trees"]]
    days = set(range(shift, max(t["ago"] for t in trees) + 1)) | studied
    today = fake_forest.FAKE_TODAY + shift
    r = random.Random(fake_forest.FAKE_SEED + 1)  # the same new trees, day after day
    for ago in sorted(studied, reverse=True):
        trees.append(fake_forest.tree(r, today - ago, ago, NOW.date()))
    for resumed, length in forest_data._breaks(days, trees[0]["ago"]):
        after = next((t for t in trees if t["ago"] <= resumed and not t.get("gap")), None)
        if after is not None:
            after.update(gap=length, gap_from=_iso(resumed + length), gap_to=_iso(resumed + 1))
    extras = {"nature": level, "craters": [], "strike": None, "doom": None, "fire": None}
    reviews = None
    if level == "merciless":
        out = events.merciless(trees, days)
        latest = out["latest"]
        if latest:
            extras["craters"] = [dict(c, date=_iso(c["ago"]), spot="nature") for c in out["craters"]]
            extras["strike"] = {"date": _iso(latest["ago"]), "lost": latest["lost"], "seen": "nature", "fresh": False,
                                "news": False, "told": False, "before": latest["before"]}
        if out["hits"]:
            days = {d for d in days if d < out["hits"][-1]}
            reviews = len(days) * fake_forest.FAKE_TODAY_REVIEWS
        trees, extras["doom"] = out["trees"], out["doom"]
    elif level == "wild":
        trees, extras["fire"] = events.set_fire(trees, days, forest_data.MAX_INDIVIDUAL_TREES)
    else:
        trees = events.calm_trees(trees)
    return forest_data.rebuild(dict(base, review_days=days), trees, days, reviews), extras


def story(level: str) -> list:
    """The days the GIF shows, in order: (away, back, frames, marks, play the strike)."""
    days = []
    if level == "peaceful":
        away = PEACEFUL_AWAY
        days.append((0, 0, 12, "", False))
        days += [(n, 0, 4, "n" * n, False) for n in (*range(1, away, 3), away)]  # (three days a step)
        days += [(away, b, 4, "n" * away + "y" * b, False) for b in (1, 2)]
        days.append((away, 3, 24, "n" * away + "yyy", False))
        days += [(away, b, 8, "n" * away + "y" * b, False) for b in range(4, 7)]
    elif level == "wild":
        days.append((0, 0, 12, "", False))
        days.append((1, 0, 8, "n", False))
        days.append((2, 0, 15, "nn", False))
        days += [(n, 0, 8, "n" * n, False) for n in range(3, 8)]
        days += [(7, b, 6, "n" * 7 + "y" * b, False) for b in range(1, 8)]
    else:
        days.append((0, 0, 18, "", False))
        days.append((1, 0, 0, "n", True))  # its frames: as long as the strike plays
        days.append((1, 0, 12, "n", False))
        days += [(1, b, 8, "n" + "y" * b, False) for b in range(1, 6)]
    last = days[-1]
    days[-1] = last[:2] + (last[2] + HOLD,) + last[3:]
    return days


def page(level: str) -> str:
    p = presets.by_key()[SCENERY]
    mood = scene.choose_mood(dict(p.values(), **({"time_of_day": PEACEFUL_TIME} if level == "peaceful" else {})), NOW)
    steps = []
    for away, back, frames, marks, strike in story(level):
        forest, extras = forest_after(level, away, back)
        data = {"trees": forest["trees"], "stats": forest["stats"], "visitors": [], "merged": None,
                "forestSeed": forest["forest_seed"], "anniversaries": [], "events": [], "journal": "",
                "mood": mood, "environmentName": "", "animations": True, "tooltips": False,
                "maxWidth": PANEL_PX, "testForest": True, "channel": "nature", **extras}
        if strike:
            data["strike"] = dict(data["strike"], fresh=True)
        elif data.get("strike"):
            data["strike"] = None  # (only the crater: the strike plays once)
        steps.append({"data": data, "frames": frames, "marks": ("y" * STUDIED_BEFORE + marks)[-MAX_MARKS:], "strike": strike})
    # the strike plays at twice its speed: its shower and blast take a few seconds as it is
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0}}.af-panel{{width:{PANEL_PX}px;margin:0;padding:0}}"
            ".af-caption{{display:none}}</style>"
            f"<script>{CLOCK_JS}window.pycmd = () => false;</script>"
            "<div class='af-panel' id=p></div><pre id=o></pre>"
            f"<script>{scripts()}</script><script>window.S = {json.dumps(steps)};</script>"
            f"<script>const FPS = {FPS}, M = {MARK}, G = {GAP}, PAD = {PAD}, IN = {INSET};"
            f"const COL = {{ y: '{STUDIED}', n: '{MISSED}' }}, BACK = '{BACKING}';"
            f"let t = {START_MS}; const shots = [], root = document.getElementById('p');"
            "function shot(marks) {"
            " const main = root.querySelector('canvas.af-canvas'), c = document.createElement('canvas');"
            " c.width = main.width; c.height = main.height; const g = c.getContext('2d');"
            " g.drawImage(main, 0, 0); root.querySelectorAll('canvas.af-strike').forEach(o => g.drawImage(o, 0, 0));"
            " const w = marks.length * (M + G) - G + 2 * PAD, h = M + 2 * PAD, x = IN, y = IN;"
            " g.fillStyle = BACK; g.fillRect(x, y, w, h);"
            " [...marks].forEach((k, i) => { g.fillStyle = COL[k]; g.fillRect(x + PAD + i * (M + G), y + PAD, M, M); });"
            " shots.push(c.toDataURL()); }"
            "try { for (const s of S) {"
            "  AnkiForest.mount(root, s.data, { now: true });"
            "  if (s.strike) { let n = 0; do { t += 2000 / FPS; pump(t); shot(s.marks); } while (root.afPlaying && ++n < 400); }"
            "  for (let i = 0; i < s.frames; i++) { t += 1000 / FPS + 0.5; pump(t); shot(s.marks); }"
            "} } catch (e) { window.ERRS.push('page: ' + (e.stack || e)); }"
            "const c0 = root.querySelector('canvas.af-canvas');"
            "document.getElementById('o').textContent = JSON.stringify({ errors: window.ERRS, w: c0.width, h: c0.height, shots });"
            "</script>")


def record(level: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page(level))
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--window-size={PANEL_PX + 40},600",
                              "--virtual-time-budget=120000", "--dump-dom", "file://" + path],
                             capture_output=True, text=True, timeout=300).stdout
        m = re.search(r'<pre id="?o"?>(.*?)</pre>', dom, re.S)
        if not m:
            sys.exit(f"{level}: the page never reported back")
        r = json.loads(html.unescape(m.group(1)))
        if r["errors"]:
            sys.exit(f"{level}: " + r["errors"][0])
        for i, s in enumerate(r["shots"]):
            with open(os.path.join(tmp, f"f{i:04d}.png"), "wb") as f:
                f.write(base64.b64decode(s.split(",", 1)[1]))
        out = os.path.join(OUT, f"{level}.gif")
        # one palette for the whole loop, so colours don't flicker between frames; then only
        # what changes from frame to frame is kept
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
                        "-vf", "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none",
                        "-loop", "0", out], check=True)
        subprocess.run(["gifsicle", "-b", "-O3", out], check=True)
    print(f"{level}: {r['w']}x{r['h']}, {len(r['shots'])} frames ({os.path.getsize(out) // 1024} KB)")


def main() -> None:
    levels = sys.argv[1:] or list(events.NATURE_LABELS)
    unknown = [k for k in levels if k not in events.NATURE_LABELS]
    if unknown:
        sys.exit(f"no Nature level {', '.join(unknown)}; there are: {', '.join(events.NATURE_LABELS)}")
    for level in levels:
        record(level)


if __name__ == "__main__":
    main()

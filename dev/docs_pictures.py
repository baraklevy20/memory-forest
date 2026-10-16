"""Draw the README's heatmap pictures, docs/calendar.png and docs/calendar_sceneries.png, from this
copy's scripts with a made-up forest and history (never anyone's own reviews), in headless Chrome.

    python3 dev/docs_pictures.py      (npm run docs-pictures)

calendar.png: the forest by the lake with its heatmap under it, the pointer on a day of the
current streak (its tooltip), the trophies and the goal's flag, and one important day ahead.
calendar_sceneries.png: one heatmap in four base sceneries, each beside its picker picture, with
its trophies and flag and no other marks. Needs Chrome, and node with the dev packages.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ADDON, "tests"))
sys.path.insert(0, os.path.join(ADDON, "e2e"))

import fake_anki  # (the add-on as a package, without Anki: heatmap_look's imports are relative)
from render_page import CHROME

PK = fake_anki.PACKAGE
catalog = importlib.import_module(PK + ".catalog")
presets = importlib.import_module(PK + ".presets")
scene = importlib.import_module(PK + ".scene")
fake_forest = importlib.import_module(PK + ".fake_forest")
HL = importlib.import_module(PK + ".heatmap_look")

DOCS = os.path.join(ADDON, "docs")
PUPPETEER = os.path.join(ADDON, "node_modules", "puppeteer-core", "lib", "esm", "puppeteer", "puppeteer-core.js")
EVENING = dt.datetime(2026, 6, 1, 17, 0)  # (the lake in its golden hour)
PAGE_BG, PAGE_FG = "#2c2c2c", "#ddd"  # (Anki's dark page)
# the made-up history, in days ago: the current streak (the second-longest: silver under today),
# a shorter one (bronze), and an older, longer one (gold, so the flag waits ahead), with scattered
# days between and before. No start date: its day would wear the first seedling, one mark too many
HISTORY = 520
STREAKS = ((0, 139), (150, 209), (230, 409))
SCATTER = 0.35  # (the share of the days studied outside a streak)
SEED = 20261016
MARK_AHEAD = 18  # (an exam this many days ahead, its countdown in the tooltip)
SCENERIES = ("golden_lake", "aurora", "lanterns", "synthwave")  # (base sceneries only: the README is the base edition's)


def history() -> dict:
    """The calendar's made-up days: reviews and time, oldest first, and the cards due ahead."""
    r = random.Random(SEED)
    today = dt.date.today()
    days, time = [], []
    for ago in range(HISTORY - 1, -1, -1):
        studied = any(a <= ago <= b for a, b in STREAKS) or (ago > STREAKS[0][1] + 10 and r.random() < SCATTER)
        if not studied:
            days.append(0)
            time.append(0)
            continue
        weekday = (today - dt.timedelta(days=ago)).weekday()
        n = r.randint(90, 300) * (0.6 if weekday >= 5 else 1.0) * (1.8 if r.random() < 0.08 else 1.0)
        days.append(int(n))
        time.append(int(n * r.uniform(6, 11)))
    due = [260] + [max(8, int(240 * 0.993 ** k + r.randint(-25, 25))) for k in range(1, 366)]
    return {"start": (today - dt.timedelta(days=HISTORY - 1)).isoformat(), "days": days, "time": time, "due": due}


def mood_of(key: str) -> dict:
    p = presets.by_key()[key]
    return scene.choose_mood({"environment": p.environment, "landscape": p.landscape, "landmark": p.landmark,
                              "weather": p.weather, "time_of_day": p.time}, EVENING)


def calendar(mood: dict, marks: list) -> dict:
    look = HL.page_look({}, mood)
    return dict(history(), view="timeline", weekStart=1, shadeBy="reviews", animals=[], breakDays=7, browse=False,
                marks=marks, free=[], daysOff=[], streakFromStart=False, look=look)


def page(mood: dict, data: dict, width: int, extra_css: str = "") -> str:
    css = open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8").read()
    files = [os.path.join(catalog.WEB, s) for s in catalog.SCRIPTS]
    files += [os.path.join(catalog.WEB, f) for f in catalog.scenery_files(mood)]
    files += [os.path.join(catalog.WEB, f) for f in data["calendar"]["look"].get("files", [])]
    tags = "".join(f'<script src="file://{f}"></script>' for f in dict.fromkeys(files))
    return f"""<!doctype html><meta charset="utf-8"><style>body {{ margin: 0; padding: 0; background: {PAGE_BG}; color: {PAGE_FG};
--fg: {PAGE_FG}; --fg-subtle: #999 }} #p {{ width: {width}px; padding: 24px 22px 10px }} {css} {extra_css}</style>
<div class="af-panel" id="p"></div><script>window.pycmd = () => false;</script>{tags}
<script>AnkiForest.mount(document.getElementById('p'), {json.dumps(data)});</script>"""


def forest_data(mood: dict) -> dict:
    """The dev payload's settings with a made-up forest: its trees, and a caption that agrees with
    the history (the current streak, the longest)."""
    raw = open(os.path.join(HERE, "payload.js"), encoding="utf-8").read()
    data = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
    forest = fake_forest.make(150)
    stats = dict(forest["stats"], streak=STREAKS[0][1] + 1, longest_streak=STREAKS[2][1] - STREAKS[2][0] + 1)
    return dict(data, trees=forest["trees"], stats=stats, visitors=[], anniversaries=[], events=[], journal="",
                forestSeed=forest["forest_seed"], mood=mood, animations=False, inAnki=True, maxWidth=756)


SHOOT = r"""
import puppeteer from '%(puppeteer)s';
const jobs = %(jobs)s;
const b = await puppeteer.launch({ executablePath: %(chrome)s, headless: 'new', args: ['--disable-gpu', '--allow-file-access-from-files'] });
const p = await b.newPage();
p.on('pageerror', e => console.log('ERR', e.message));
for (const j of jobs) {
  await p.setViewport({ width: j.width, height: 1000, deviceScaleFactor: 1 });
  await p.goto('file://' + j.page);
  await p.waitForSelector('.af-cal-canvas', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 1500));
  if (j.point) {  // (a day of the current streak, some weeks back: its tooltip between the trophies)
    const box = await p.$eval('.af-cal-canvas', e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; });
    let tip = '';
    for (let x = box[0] + box[2] * j.point[0]; x < box[0] + box[2] * j.point[1] && !/of your/.test(tip); x += 3) {
      await p.mouse.move(x, box[1] + box[3] * 0.12);
      await new Promise(r => setTimeout(r, 450));  // (the tooltip waits a moment, calendar.js TIP_WAIT)
      tip = await p.$eval('.af-cal-tip', e => e.hidden ? '' : e.innerText);
    }
    console.log(j.out, '|', tip.replace(/\n/g, ' / '));
  }
  const el = await p.$(j.shoot);
  await el.screenshot({ path: j.out });
}
await b.close();
"""


def shoot(jobs: list) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(SHOOT % {"puppeteer": PUPPETEER, "jobs": json.dumps(jobs), "chrome": json.dumps(CHROME)})
    try:
        run = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(f.name)
    print(run.stdout + run.stderr, end="")
    if run.returncode:
        raise SystemExit(run.returncode)


def label_font(size: int):
    from PIL import ImageFont
    for path in ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sceneries_picture(shots: dict, out: str) -> None:
    """Each scenery's picker picture and name beside its heatmap, one under the other."""
    from PIL import Image, ImageDraw
    thumb_w, gap, pad, label_h = 192, 16, 10, 22
    cals = [Image.open(shots[k]) for k in SCENERIES]
    row_h = max(max(c.height for c in cals), 108 + label_h)
    width = pad + thumb_w + gap + max(c.width for c in cals) + pad
    sheet = Image.new("RGB", (width, pad + len(cals) * (row_h + pad)), PAGE_BG)
    draw, font = ImageDraw.Draw(sheet), label_font(12)
    for i, key in enumerate(SCENERIES):
        y = pad + i * (row_h + pad)
        thumb = Image.open(os.path.join(ADDON, "settings", "scenery", f"{key}.png")).convert("RGB").resize((thumb_w, 108), Image.NEAREST)
        mask = Image.new("L", thumb.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, thumb_w - 1, 107), radius=6, fill=255)
        sheet.paste(thumb, (pad, y), mask)
        draw.text((pad, y + 112), presets.by_key()[key].label, fill="#bbbbbb", font=font)
        sheet.paste(cals[i], (pad + thumb_w + gap, y))
    sheet.save(out, optimize=True)


def main() -> None:
    lake = mood_of("golden_lake")
    exam = [{"day": (dt.date.today() + dt.timedelta(days=MARK_AHEAD)).isoformat(), "icon": "exam", "name": "Exam"}]
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        # the big picture: the forest and its heatmap, the pointer on a day of the streak
        big = dict(forest_data(lake), calendar=calendar(lake, exam), showForest=True)
        path = os.path.join(tmp, "big.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page(lake, big, 756, ".af-cog { display: none !important }"))
        jobs.append({"page": path, "width": 800, "shoot": "#p", "point": [0.52, 0.6], "out": os.path.join(DOCS, "calendar.png")})
        # the sceneries: the heatmap alone, its trophies and flag shown as the pointer shows them
        shots = {}
        for key in SCENERIES:
            mood = mood_of(key)
            data = dict(forest_data(mood), calendar=calendar(mood, []), showForest=False, maxWidth=560)
            path = os.path.join(tmp, f"{key}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(mood, data, 560, ".af-cal .af-cal-above { opacity: 1 } .af-cal-foot, .af-cal-notes { display: none }"))
            shots[key] = os.path.join(tmp, f"{key}.png")
            jobs.append({"page": path, "width": 620, "shoot": ".af-cal", "out": shots[key]})
        shoot(jobs)
        sceneries_picture(shots, os.path.join(DOCS, "calendar_sceneries.png"))
    print("docs/calendar.png, docs/calendar_sceneries.png")


if __name__ == "__main__":
    main()

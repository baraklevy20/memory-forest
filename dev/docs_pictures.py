"""Draw the README's heatmap pictures, docs/heatmap.png and docs/heatmap_sceneries.png, from this
copy's scripts in headless Chrome. Uses made-up history unless --collection is supplied.

    python3 dev/docs_pictures.py      (npm run docs-pictures)
    python3 dev/docs_pictures.py --collection /path/to/collection.anki2

heatmap.png: the forest by the lake with its heatmap under it, visible streak labels,
the current streak's silver trophy, its next goal's flag, and an upcoming exam note.
heatmap_sceneries.png: one heatmap in four sceneries, each beside its picker picture, with
its current trophy and flag and no other streak markers. Needs Chrome, and node with the dev packages.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

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
# each row: its scenery, the tile style (None: the scenery's own) and the view, all Timeline so the
# rows line up and show the same days, cropped to eight months, May to December (2026-10-17). A
# fifth row showing Contours (Aurora, By year) was tried and dropped: a whole year shifted and
# squeezed against the others, Timeline chopped the shape at the month gaps, and a wider By year made
# a taller row.
ROWS = (("golden_lake", None, "timeline"), ("starry_night", None, "timeline"), ("lanterns", None, "timeline"),
        ("synthwave", None, "timeline"))
SCENERIES = tuple(key for key, _tiles, _view in ROWS)


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
    # the cards due ahead, over the whole range the soil's four shades split (calendar.js dueShade,
    # by the log of the busiest day ahead): a backlog thinning out, light weekends, a heavy day now
    # and then, a near-empty one here and there
    due = [260]
    for k in range(1, 366):
        base = 24 + 110 * 0.96 ** k
        if (today + dt.timedelta(days=k)).weekday() >= 5:
            base *= 0.25
        if k % 9 == 4:
            base *= 3.2
        n = r.randint(1, 3) if r.random() < 0.08 else int(base * r.uniform(0.6, 1.4))
        due.append(max(1, n))
    return {"start": (today - dt.timedelta(days=HISTORY - 1)).isoformat(), "days": days, "time": time, "due": due}


REAL_DATA = None
REAL_HISTORY = None


def collection_data(path: str) -> None:
    """Read a consistent snapshot; never write to the user's collection."""
    global REAL_DATA, REAL_HISTORY
    import export_payload as export

    db = export.DB(":memory:")
    with closing(sqlite3.connect(Path(path).expanduser().resolve().as_uri() + "?mode=ro", uri=True)) as source:
        source.backup(db.con)
    try:
        rollover = int(db.scalar("select val from config where key = 'rollover'") or 4)
        cutoff = export.day_cutoff(rollover)
        today = export.sched_today(int(db.scalar("select crt from col")), cutoff, rollover)
        rows = export.study_log.load_rows(db, cutoff)
        forest = export.forest_data.merge_old(export.forest_data.build_forest(rows, cutoff, today, dt.datetime.now().timestamp()))
        REAL_DATA = {"trees": forest["trees"], "stats": forest["stats"], "merged": forest.get("merged"), "forestSeed": forest["forest_seed"]}
        reviews = export.study_log.load_day_reviews(db, cutoff, None)
        times = export.study_log.load_day_time(db, cutoff, None)
        oldest = max(reviews, default=0)
        REAL_HISTORY = {"start": export.study_log.day_date(oldest, cutoff).isoformat(),
                        "days": [reviews.get(a, 0) for a in range(oldest, -1, -1)],
                        "time": [times.get(a, 0) for a in range(oldest, -1, -1)],
                        "due": export.study_log.load_due(db, today, 366)}
    finally:
        db.con.close()


def mood_of(key: str) -> dict:
    p = presets.by_key()[key]
    return scene.choose_mood({"environment": p.environment, "landscape": p.landscape, "landmark": p.landmark,
                              "weather": p.weather, "time_of_day": p.time}, EVENING)


def calendar(mood: dict, marks: list, tiles: str | None = None, view: str = "timeline") -> dict:
    look = HL.page_look({"calendar_tiles": tiles} if tiles else {}, mood)
    return dict(REAL_HISTORY or history(), view=view, weekStart=1, shadeBy="reviews", animals=[], browse=False,
                marks=marks, free=[], daysOff=[], streakFromStart=False, look=look)


def page(mood: dict, data: dict, width: int, extra_css: str = "") -> str:
    css = open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8").read()
    files = [os.path.join(catalog.WEB, s) for s in catalog.SCRIPTS]
    files += [os.path.join(catalog.WEB, f) for f in catalog.scenery_files(mood)]
    files += [os.path.join(catalog.WEB, f) for f in data["calendar"]["look"].get("files", [])]
    tags = ""
    for f in dict.fromkeys(files):
        if os.path.basename(f) == "calendar.js":
            # Screenshot presentation only: keep the real ranking, show just the current streak.
            script = Path(f).read_text()
            script = script.replace("for (const r of H.runs) {", "for (const r of [H.current].filter(Boolean)) {")
            script = script.replace("for (const [run, i] of H.podium) lane.push", "for (const [run, i] of H.podium) if (run === H.current) lane.push")
            tags += f"<script>{script}</script>"
        else:
            tags += f'<script src="file://{f}"></script>'
    return f"""<!doctype html><meta charset="utf-8"><style>body {{ margin: 0; padding: 0; background: {PAGE_BG}; color: {PAGE_FG};
--fg: {PAGE_FG}; --fg-subtle: #999 }} #p {{ width: {width}px; padding: 24px 22px 10px }} {css} .af-cal-tip {{ display: none !important }} .af-cal .af-cal-above {{ opacity: 1 }} {extra_css}</style>
<div class="af-panel" id="p"></div><script>window.pycmd = () => false;</script>{tags}
<script>AnkiForest.mount(document.getElementById('p'), {json.dumps(data)});</script>"""


def forest_data(mood: dict) -> dict:
    """Preview settings with the chosen forest and matching study statistics."""
    raw = open(os.path.join(HERE, "payload.js"), encoding="utf-8").read()
    data = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
    forest = fake_forest.make(150)
    stats = dict(forest["stats"], streak=STREAKS[0][1] + 1, longest_streak=STREAKS[2][1] - STREAKS[2][0] + 1)
    data.update(REAL_DATA or {"trees": forest["trees"], "stats": stats, "forestSeed": forest["forest_seed"]})
    return dict(data, visitors=[], anniversaries=[], events=[], journal="",
                mood=mood, animations=False, inAnki=True, maxWidth=756)


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
  const el = await p.$(j.shoot);
  if (j.fromMonth !== undefined) {
    const clip = await el.evaluate((e, month) => {
      const r = e.getBoundingClientRect();
      const start = e.querySelector(`.af-cal-months span[data-m="${month}"]`);
      if (!start) throw new Error('Comparison start month is outside the timeline');
      const x = Math.max(r.left, Math.floor(start.getBoundingClientRect().left) - 2);
      return { x, y: r.top, width: r.right - x, height: r.height };
    }, j.fromMonth);
    await p.screenshot({ path: j.out, clip });
  } else {
    await el.screenshot({ path: j.out });
  }
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", help="Use your own review history and forest (read-only)")
    args = parser.parse_args()
    if args.collection:
        collection_data(args.collection)
    lake = mood_of("golden_lake")
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        # the big picture: the forest and its heatmap, with the streak labels unobstructed
        note = {"day": (dt.date.today() + dt.timedelta(days=18)).isoformat(), "icon": "exam", "name": "Exam"}
        big = dict(forest_data(lake), calendar=calendar(lake, [note]), showForest=True)
        path = os.path.join(tmp, "big.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page(lake, big, 756, ".af-cog { display: none !important }"))
        jobs.append({"page": path, "width": 800, "shoot": "#p", "out": os.path.join(DOCS, "heatmap.png")})
        # the sceneries: the heatmap alone, with only the current trophy and flag revealed
        shots = {}
        for key, tiles, view in ROWS:
            mood = mood_of(key)
            data = dict(forest_data(mood), calendar=calendar(mood, [], tiles, view), showForest=False, maxWidth=756)
            path = os.path.join(tmp, f"{key}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(mood, data, 756, ".af-cal .af-cal-above { opacity: 1 } .af-cal-foot, .af-cal-notes { display: none }"))
            shots[key] = os.path.join(tmp, f"{key}.png")
            # (from May's label, eight months; By year's January: the weekday labels left out)
            jobs.append({"page": path, "width": 800, "shoot": ".af-cal", "fromMonth": 0 if view == "by_year" else 4, "out": shots[key]})
        shoot(jobs)
        sceneries_picture(shots, os.path.join(DOCS, "heatmap_sceneries.png"))
    print("docs/heatmap.png, docs/heatmap_sceneries.png")


if __name__ == "__main__":
    main()

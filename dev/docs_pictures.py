"""Draw the README's heatmap and layout pictures, docs/heatmap.png, docs/heatmap_sceneries.png and
docs/layout.png, from this copy's scripts in headless Chrome. Uses made-up history unless
--collection is supplied.

    python3 dev/docs_pictures.py      (npm run docs-pictures)
    python3 dev/docs_pictures.py --only layout
    python3 dev/docs_pictures.py --collection /path/to/collection.anki2

heatmap.png: the forest by the lake with its heatmap under it, visible streak labels,
the current streak's silver trophy, its next goal's flag, and an upcoming exam note.
heatmap_sceneries.png: one heatmap in five sceneries, each beside its picker picture, with
its current trophy and flag and no other streak markers.
layout.png: Anki's deck list with a made-up Japanese deck (made up with --collection too), Chalkboard beside it
on the right and the heatmap Full width under them (Layout: One beside), arranged by the add-on's own web/core.js AF.arrange, at
twice the pixels (a Retina screen). Needs Chrome, and node with the dev packages.
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
# rows line up and show the same days, cropped to eight months, May to December (2026-10-17). Aurora
# shows Contours here only, in Timeline like the rest (2026-10-19), not its own tiles: By year shifted
# and squeezed a whole year against the others, and a wider By year made a taller row.
# (Aurora's blue apart from Starry night's)
ROWS = (("golden_lake", None, "timeline"), ("starry_night", None, "timeline"), ("lanterns", None, "timeline"),
        ("aurora", "contours", "timeline"), ("synthwave", None, "timeline"))
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


def script_tags(mood: dict, data: dict) -> str:
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
    return tags


def page(mood: dict, data: dict, width: int, extra_css: str = "") -> str:
    css = open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8").read()
    tags = script_tags(mood, data)
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


# the layout picture: a made-up deck list (name, indent, new, learn, due), the window's width in css
# px and its Forest width (the side column's)
# (long enough to stand about 80% of the forest's height beside it)
DECKS = (("Japanese", 0, 25, 7, 177), ("Kana", 1, 0, 0, 12), ("Kanji", 1, 10, 4, 63), ("Vocabulary", 1, 10, 2, 51),
         ("Grammar", 1, 5, 1, 14), ("Particles", 1, 0, 0, 6), ("Reading", 1, 0, 0, 11), ("Listening", 1, 0, 0, 8),
         ("Writing", 1, 0, 0, 12))
LAYOUT_WINDOW, LAYOUT_FOREST = 1440, 800
# its forest, as (first, last, every) in days ago: a tree only on the days new cards were learned,
# every few days lately (so the trees in front are grown, as in a real forest: a tree every day
# made a front row of saplings), more often a year and more back (old and ancient), and a break
# between (a pond)
LAYOUT_DAYS = ((1, 79, 7), (95, 330, 3), (430, 600, 2))
LAYOUT_STREAK = 146
# its caption's journal line (an animal of the forest's own) and its heatmap's view, as in the add-on
LAYOUT_JOURNAL = "A family of squirrels wandered in: you knew 10,000 cards well."
LAYOUT_VIEW = "by_year"
# where Anki's own stylesheets are, to look as it does (without them, plain stand-ins)
AQT_WEB = os.path.expanduser("~/Library/Application Support/AnkiProgramFiles/.venv/lib/python3.13/site-packages/_aqt/data/web")


def layout_forest() -> dict:
    """The layout picture's forest: a couple of years of made-up days (LAYOUT_DAYS), so some trees
    are old and ancient as in a real one, with the animals its numbers bring."""
    r = random.Random(SEED)
    ages = [ago for a, b, every in LAYOUT_DAYS for ago in range(a, b + 1, every)]
    trees, prev = [], None
    for ago in sorted(ages, reverse=True):
        t = fake_forest.tree(r, fake_forest.FAKE_TODAY - ago, ago)
        if prev is not None and prev - ago > fake_forest.BREAK_DAYS:
            t["gap"] = prev - ago - 1
        prev = ago
        trees.append(t)
    forest = fake_forest.make_forest(trees, LAYOUT_STREAK, LAYOUT_STREAK, len(trees) * fake_forest.FAKE_REVIEWS_PER_TREE, 186)
    stats = forest["stats"]
    stats["mature_cards"] = max(stats["mature_cards"], fake_forest.SQUIRREL_MATURE)
    return {"trees": forest["trees"], "stats": stats, "forestSeed": forest["forest_seed"], "visitors": fake_forest.visitors(stats)}


def layout_page(mood: dict, data: dict) -> str:
    """Anki's deck list as aqt/deckbrowser.py builds it (<center><table>decks</table><br>stats</center>),
    on its dark page in its card style (body.fancy), the panel first among the stats as panel.py puts it."""
    rows = "<tr><th colspan=5 align=start>Deck</th><th class=count>New</th><th class=count>Learn</th><th class=count>Due</th><th class=optscol></th></tr>"
    for i, (name, level, new, learn, due) in enumerate(DECKS):
        num = lambda n, cls: f"<td align=end>{f'<span class={cls}>{n}</span>' if n else ''}</td>"  # noqa: E731
        fold = "<a class=collapse>-</a>" if level == 0 and i == 0 else ""
        rows += (f"<tr class='deck' id='{i + 1}'><td class=decktd colspan=5>{'&nbsp;' * 6 * level}<span class=collapse>{fold}</span>"
                 f'<a class="deck" href=#>{name}</a></td>{num(new, "new-count")}{num(learn, "learn-count")}{num(due, "review-count")}'
                 "<td align=center class=opts></td></tr>")
    css = "".join(open(os.path.join(AQT_WEB, "css", f), encoding="utf-8").read() for f in ("webview.css", "deckbrowser.css")
                  if os.path.exists(os.path.join(AQT_WEB, "css", f)))
    forest_css = open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8").read()
    return f"""<!doctype html><html class="night-mode"><head><meta charset="utf-8"><style>{css}</style>
<style>body {{ margin: 0; padding: 28px 0 24px; background: {PAGE_BG}; color: {PAGE_FG}; font: 14px -apple-system, system-ui, sans-serif;
--fg: {PAGE_FG}; --fg-subtle: #999 }} td, th {{ padding: 4px 8px }} .new-count {{ color: #6ca3f4 }} .learn-count {{ color: #e57373 }}
.review-count {{ color: #63c463 }} {forest_css}</style></head>
<body class="nightMode night_mode fancy isMac"><center>
<table cellspacing=0 cellpadding=3>{rows}<tr class='top-level-drag-row'><td colspan='6'>&nbsp;</td></tr></table>
<br>
<div class="af-panel" id="p"></div><div id="studiedToday"><span>Studied 186 cards in 24 minutes today (7.7s/card)</span></div>
</center><script>window.pycmd = () => false;</script>{script_tags(mood, data)}
<script>AnkiForest.mount(document.getElementById('p'), {json.dumps(data)});</script></body></html>"""


SHOOT = r"""
import puppeteer from '%(puppeteer)s';
const jobs = %(jobs)s;
const b = await puppeteer.launch({ executablePath: %(chrome)s, headless: 'new', args: ['--disable-gpu', '--allow-file-access-from-files'] });
const p = await b.newPage();
p.on('pageerror', e => console.log('ERR', e.message));
for (const j of jobs) {
  await p.setViewport({ width: j.width, height: 1000, deviceScaleFactor: j.scale || 1 });
  await p.goto('file://' + j.page);
  await p.waitForSelector('.af-cal-canvas', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 1500));
  const el = await p.$(j.shoot);
  if (j.fromMonth !== undefined) {
    const clip = await el.evaluate((e, month, pad) => {
      const r = e.getBoundingClientRect();
      const start = e.querySelector(`.af-cal-months span[data-m="${month}"]`);
      if (!start) throw new Error('Comparison start month is outside the timeline');
      const x = Math.max(r.left, Math.floor(start.getBoundingClientRect().left) - pad);
      return { x, y: r.top, width: r.right - x, height: r.height };
    }, j.fromMonth, j.pad === undefined ? 2 : j.pad);
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
    parser.add_argument("--only", choices=("heatmap", "layout"), help="Draw only the heatmap pictures, or only the layout one")
    args = parser.parse_args()
    if args.collection:
        collection_data(args.collection)
    lake = mood_of("golden_lake")
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        if args.only != "heatmap":
            # the layout: Chalkboard beside the deck list and its heatmap Full width under it (One beside), the page shot whole
            # with its margins, down to Anki's studied-today line
            board = mood_of("chalkboard")
            # (with --collection, your own forest and the animals its numbers bring; the decks stay made up)
            trees = layout_forest() if REAL_DATA is None else {"visitors": fake_forest.visitors(REAL_DATA["stats"])}
            lay = dict(forest_data(board), **trees, calendar=dict(calendar(board, [], view=LAYOUT_VIEW), size={"width": "full", "fill": "more"}), showForest=True, maxWidth=LAYOUT_FOREST,
                       journal=LAYOUT_JOURNAL, sceneName=presets.by_key()["chalkboard"].label,
                       layout={"forest": "right", "heatmap": "below", "first": "forest"})
            path = os.path.join(tmp, "layout.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(layout_page(board, lay))
            jobs.append({"page": path, "width": LAYOUT_WINDOW, "scale": 2, "shoot": "body", "out": os.path.join(DOCS, "layout.png")})
        if args.only == "layout":
            shoot(jobs)
            print("docs/layout.png")
            return
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
            # (Contours outlines the month before right up to the cut: none of it shown)
            jobs.append({"page": path, "width": 800, "shoot": ".af-cal", "fromMonth": 0 if view == "by_year" else 4,
                         "pad": 0 if tiles == "contours" else 2, "out": shots[key]})
        shoot(jobs)
        sceneries_picture(shots, os.path.join(DOCS, "heatmap_sceneries.png"))
    print("docs/heatmap.png, docs/heatmap_sceneries.png" + ("" if args.only else ", docs/layout.png"))


if __name__ == "__main__":
    main()

"""The deck list's layouts (Forest tab, Layout): the forest and the heatmap stand where each layout
puts them round Anki's deck list - under it, both or one of them beside it in a wide window and under
it in a narrow one, or the First above it and the other under it - in the First order, and both draw,
as wide as they should be at each Heatmap width and Fill it with, in Timeline and By year; and with
one of them switched off on the deck list, the other stands where its own place is. Run: python3 e2e/layout_check.py (npm run test:layout); `npm test` runs it with --if-changed:
only when the files it goes through changed.

For each layout (state.LAYOUTS), First and, beside the list, each side, and each layout at each
Heatmap width and fill in each view, it runs this copy's panel.on_deck_browser on the
tests' stand-in Anki (tests/fake_anki.py) with that layout, puts the HTML in a page built as Anki
builds its deck list (aqt/deckbrowser.py: <center><table>decks</table><br>stats</center>, with a
stand-in for Anki's "Studied today" line), opens it in headless Chrome (e2e/layout_check.mjs) at a
wide and a narrow width, and checks where the deck table, the forest and the heatmap stand, how wide
they are (the forest its Forest width, the heatmap as wide as what stands above or below it), that
nothing reaches past the window, and that both canvases drew, with no error, not even as the window is
then resized across the breakpoint and back (a ResizeObserver's loop). `--shots DIR` saves a
picture of each page too. Needs Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from importlib import import_module

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, HERE)
from phone_check import CHROME, phone_changed

# the files the layouts go through: a change to one runs this
LAYOUT_FILES = ("panel.py", "payload.py", "state.py", "web/core.js", "web/caption.js", "web/calendar.js",
                "web/forest.css", "e2e/layout_check.py", "e2e/layout_check.mjs")
WIDE, NARROW = 1400, 720  # css px: a window with room beside the list, and one without
# (and one without that still has room for more than the forest: a heatmap at Full width fallen under
# the list there is wider than the forest, as it is under the list)
MID = 900
CARDS = [(i, 10, i % 90) for i in range(1, 400)]  # (a forest, and three months of heatmap)
FOREST_W = 800  # the Forest width (config.json's max_width)
FIXED_W = 680  # the heatmap's Fixed width (calendar.js FIXED_W); Follow the forest and Full width are 85% of the forest and of the room
# Anki's deck list, in its own markup (a header, decks, the drag row), with made-up decks
DECKS = [("Default", 0), ("German", 0), ("Verbs", 1), ("Vocabulary", 1), ("Japanese", 0), ("Kanji", 1), ("Geography", 0)]
# where Anki's own stylesheets are, to look as it does when they are at hand (never needed)
AQT_WEB = os.path.expanduser("~/Library/Application Support/AnkiProgramFiles/.venv/lib/python3.13/site-packages/_aqt/data/web")


def panel_html(cfg: dict) -> str:
    """The deck list's stats as this copy makes them with config `cfg`: the panel first."""
    import fake_anki
    fake_anki.reset(cards=CARDS, config=cfg)
    from importlib import import_module
    panel = import_module(f"{fake_anki.PACKAGE}.panel")

    class Content:
        tree, stats = "", '<div id="studiedToday"><span>Studied 212 cards in 23 minutes today</span></div>'
    content = Content()
    panel.on_deck_browser(None, content)
    return content.stats.replace(f"/_addons/{fake_anki.PACKAGE}/", f"file://{ROOT}/")


def page(stats: str, dark: bool) -> str:
    rows = "<tr><th colspan=5 align=start>Deck</th><th class=count>New</th><th class=count>Learn</th><th class=count>Due</th><th class=optscol></th></tr>"
    for i, (name, level) in enumerate(DECKS):
        rows += (f"<tr class='deck' id='{i + 1}'><td class=decktd colspan=5>{'&nbsp;' * 6 * level}<span class=collapse></span>"
                 f'<a class="deck" href=#>{name}</a></td><td align=end>{i * 3}</td><td align=end>{i}</td><td align=end>{i * 17}</td>'
                 "<td align=center class=opts></td></tr>")
    css = "".join(open(os.path.join(AQT_WEB, "css", f), encoding="utf-8").read() for f in ("webview.css", "deckbrowser.css")
                  if os.path.exists(os.path.join(AQT_WEB, "css", f)))
    return f"""<!doctype html><html class="{'night-mode' if dark else ''}"><head><meta charset="utf-8">
<script>window.pycmd = (m, cb) => {{ if (cb) cb(null); return false; }};</script>
<style>{css}</style><style>body {{ font: 13px -apple-system, system-ui, sans-serif; margin: 0; padding: 12px 0;
  background: {'#2c2c2c' if dark else '#f5f5f5'}; color: {'#ddd' if dark else '#222'} }} td, th {{ padding: 2px 6px }}</style></head>
<body class="{'nightMode night_mode' if dark else ''}">
<center>
<table cellspacing=0 cellpadding=3>
{rows}<tr class='top-level-drag-row'><td colspan='6'>&nbsp;</td></tr>
</table>

<br>
{stats}
</center></body></html>"""


def state():
    """This copy's state.py, loaded on the stand-in Anki."""
    import fake_anki
    return import_module(f"{fake_anki.PACKAGE}.state")


def cases() -> list:
    """(name, config): each layout with each First and, beside the list, each Side, as it ships (the
    heatmap the forest's width, more days, Timeline); and each layout (forest first, on the right) at
    each Width (fixed, the forest's, full), filled with more days or bigger days, in
    Timeline and By year (One beside with the heatmap beside the list in By year, the forest in Timeline);
    and each layout with each First, the forest or the heatmap switched off on the deck list (the
    other alone in its own place: over the list, beside it, or under it), the heatmap Full width."""
    out, st = [], state()
    for key, places in st.LAYOUTS.items():
        sides = ("right", "left") if "side" in places else ("right",)
        out += [(f"{key}_{side}_{first}", {"layout": key, "layout_side": side, "layout_first": first})
                for side in sides for first in st.LAYOUT_FIRST]
        out += [(f"{key}_{width}_{fill}_{view}", {"layout": key, "calendar_width": width, "calendar_fill": fill, "calendar": view,
                                                      "layout_first": "heatmap" if key == "one_beside" and view == "by_year" else "forest"})
                for width in st.CALENDAR_WIDTHS for fill in st.CALENDAR_FILLS for view in ("timeline", "by_year")
                if (width, fill, view) != ("forest", "more", "timeline")]
        out += [(f"{key}_{first}_no_{off}", {"layout": key, "layout_first": first, "calendar_width": "full", OFF[off]: False})
                for first in st.LAYOUT_FIRST for off in OFF]
    return out


# the switch that takes each one off the deck list
OFF = {"forest": "main_forest", "heatmap": "calendar_main"}


def shown(cfg: dict) -> dict:
    """Which of the two the deck list shows with config `cfg`."""
    return {what: cfg.get(key, True) is not False for what, key in OFF.items()}


def expect(cfg: dict, wide: bool, got: dict) -> list:
    """What is wrong with where they stand (got: each box's [left, top, right, bottom])."""
    t, f, h, win = got["table"], got["forest"], got["heatmap"], got["window"]
    fails, lay, on = [], state().layout(cfg), shown(cfg)
    side, first_ = lay["forest"] if lay["forest"] in ("left", "right") else lay["heatmap"], lay["first"]
    if not all(on.values()):
        return alone(cfg, wide, got)

    def beside(b):
        return b[0] >= t[2] + 8 if side == "right" else b[2] <= t[0] - 8

    def under(b, above):
        return b[1] >= above[3] - 1

    # (in a narrow window a side column falls under the list)
    places = {what: "below" if lay[what] in ("left", "right") and not wide else lay[what] for what in ("forest", "heatmap")}
    for what, box in (("forest", f), ("heatmap", h)):
        if places[what] in ("left", "right"):
            if not beside(box):
                fails.append(f"the {what} should stand {side} of the deck list: {box}, the list {t}")
            # (the side column's first starts level with the list; the second stands under it)
            if (what == first_ or places["forest"] != places["heatmap"]) and box[1] > t[1] + 40:
                fails.append(f"the {what} should start level with the deck list: {box}, the list {t}")
        if places[what] == "below" and not under(box, t):
            fails.append(f"the {what} should be under the deck list: {box}, the list {t}")
        if places[what] == "above" and not under(t, box):
            fails.append(f"the {what} should be over the deck list: {box}, the list {t}")
    if places["forest"] == places["heatmap"]:
        first, second = (h, f) if first_ == "heatmap" else (f, h)
        if not under(second, first):
            fails.append(f"the two should stand one above the other, {first_} first: forest {f}, heatmap {h}")
    if lay["forest"] == lay["heatmap"] == "below" and got["arranged"]:
        fails.append("under the list should leave Anki's deck list as it is (body.af-lay)")
    for what, box in (("forest", f), ("heatmap", h), ("table", t)):
        if box[2] > win + 1 or box[0] < -1:
            fails.append(f"the {what} reaches past the window ({win} px): {box}")
    fails += widths(places, cfg, got)
    # (in a narrow window, the first under the list starts 28px under it, as under the list: the
    # forest's top, or the heatmap's months under the band its controls stand in)
    if got["arranged"] and not wide:
        tops = [got["scene"][1]] + [got["cal"][1] + got["calPad"]]
        top = min(y for y in tops if y >= t[3])
        if abs(top - (t[3] + 28)) > 1:
            fails.append(f"the first under the deck list should start 28px under it: {top - t[3]}px")
    if got["studied"][1] < max(f[3], h[3], t[3]) - 1:
        fails.append(f"Anki's studied-today line should stay under everything: {got['studied']}")
    return fails


def alone(cfg: dict, wide: bool, got: dict) -> list:
    """What is wrong with the one part the deck list shows (the other switched off): in its own place
    (over the list, beside it in a wide window and under it in a narrow one, or under it), the forest
    its Forest width, the heatmap (Full width) 85% of the room it has (beside the list, of the panel's
    column), in its row's middle."""
    lay, on = state().layout(cfg), shown(cfg)
    what = "forest" if on["forest"] else "heatmap"
    t, win = got["table"], got["window"]
    box = got["scene"] if what == "forest" else got["cal"]
    place = "below" if lay[what] in ("left", "right") and not wide else lay[what]
    fails = []
    if place in ("left", "right"):
        if not (box[0] >= t[2] + 8 if place == "right" else box[2] <= t[0] - 8):
            fails.append(f"the {what} alone should stand {place} of the deck list: {box}, the list {t}")
    elif place == "below" and box[1] < t[3] - 1:
        fails.append(f"the {what} alone should be under the deck list: {box}, the list {t}")
    elif place == "above" and t[1] < box[3] - 1:
        fails.append(f"the {what} alone should be over the deck list: {box}, the list {t}")
    if box[2] > win + 1 or box[0] < -1:
        fails.append(f"the {what} reaches past the window ({win} px): {box}")
    room, column = win - 24, win - 24 - (t[2] - t[0]) - 32
    # (beside the list, the panel's column is the Forest width at most, the heatmap alone in it 85% of it, as stacked)
    area = min(FOREST_W, column) if place in ("left", "right") else room
    want = min(FOREST_W, area) if what == "forest" else 0.85 * area
    if abs(box[2] - box[0] - want) > 3:
        fails.append(f"the {what} alone should be {round(want)} px wide: it is {box[2] - box[0]}")
    if place in ("below", "above") and abs((box[0] + box[2]) / 2 - win / 2) > 1:
        fails.append(f"the {what} alone in a row should stand in its middle ({win / 2}): {box}")
    if got["studied"][1] < max(box[3], t[3]) - 1:
        fails.append(f"Anki's studied-today line should stay under everything: {got['studied']}")
    return fails


def widths(places: dict, cfg: dict, got: dict) -> list:
    """What is wrong with their widths: the forest its Forest width, or the room it has; the heatmap
    its Width (680 px, 85% of the forest, or 85% of the room its place has) - stacked, the forest's
    panel (under the list, or fallen under it from beside it, Full width's is the window's room); apart, the row under or over the list,
    or its column beside it - in both views."""
    t, s, c, win = got["table"], got["scene"], got["cal"], got["window"]
    forest, heat = s[2] - s[0], c[2] - c[0]
    width = cfg.get("calendar_width", "forest")  # (By year fits its year to it, as Timeline does)
    fails = []

    def near(have, want, what):
        if abs(have - want) > 3:
            fails.append(f"the {what} should be {round(want)} px wide: it is {have}")
    room, column = win - 24, win - 24 - (t[2] - t[0]) - 32  # (the window's room, and the room beside the list)
    near(forest, min(FOREST_W, column if places["forest"] in ("left", "right") else room), "forest")

    def asked(area, stacked=False):  # (in the room `area`: Follow the forest 85% of the forest (of the panel, stacked), Full width 85% of the room)
        if width == "full":
            return 0.85 * area
        return min(area, FIXED_W if width == "fixed" else 0.85 * (area if stacked else FOREST_W))
    lay = state().layout(cfg)
    stacked = lay["forest"] == lay["heatmap"]
    if stacked:  # (stacked in the panel: under the list, Full width's panel is the window's room)
        panel = room if width == "full" and places["forest"] == "below" else forest
        area, want = panel, asked(panel, stacked=True)
    elif places["heatmap"] in ("left", "right"):  # (its own column beside the list: 85% of its room for Full width)
        want = 0.85 * column if width == "full" else min(column, FIXED_W if width == "fixed" else 0.85 * FOREST_W)
        area = want
    else:  # (its own row, under or over the list)
        row = places["forest"] in ("left", "right")
        area = max(t[2], s[2]) - min(t[0], s[0]) if row else room
        want = asked(area)
    near(heat, want, "heatmap")
    # (alone in a row under or over the list, the heatmap or the forest: in the row's middle, as
    # everything on the page is; stacked in the panel and narrower than it: in its middle too)
    row_mid = (min(t[0], s[0]) + max(t[2], s[2])) / 2 if places["forest"] in ("left", "right") else win / 2
    if not stacked:
        for what, box in (("heatmap", c), ("forest", s)):
            if places[what] in ("below", "above") and abs((box[0] + box[2]) / 2 - row_mid) > 1:
                fails.append(f"the {what} alone in a row should stand in its middle ({row_mid}): {box}")
    elif heat < area - 3 and abs((c[0] + c[2]) / 2 - (s[0] + s[2]) / 2) > 1:
        fails.append(f"a heatmap narrower than its panel should stand in the middle, under the forest: {c}, the forest {s}")
    return fails


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--if-changed", action="store_true", help="only if the files it goes through changed (LAYOUT_FILES)")
    args.add_argument("--shots", help="save a picture of each page in this folder")
    args.add_argument("--dark", action="store_true", help="on Anki's dark page (light otherwise)")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed(LAYOUT_FILES):
        print("layout check skipped: no files it goes through changed")
        return 0
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        for name, cfg in cases():
            path = os.path.join(tmp, name + ".html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(page(panel_html(cfg), opts.dark))
            jobs += [{"name": name, "cfg": cfg, **shown(cfg), "wide": w == WIDE, "width": w, "other": NARROW if w == WIDE else WIDE, "html": path,
                      "shot": os.path.join(os.path.abspath(opts.shots), f"{name}_{w}.png") if opts.shots else None}
                     for w in (WIDE, NARROW) + ((MID,) if cfg.get("calendar_width") == "full" and "beside" in cfg["layout"] else ())]
        if opts.shots:
            os.makedirs(opts.shots, exist_ok=True)
        jobs_path = os.path.join(tmp, "jobs.json")
        with open(jobs_path, "w", encoding="utf-8") as fh:
            json.dump(jobs, fh)
        run = subprocess.run(["node", os.path.join(HERE, "layout_check.mjs"), jobs_path, CHROME],
                             capture_output=True, text=True, cwd=ROOT, timeout=600)
    if not run.stdout.strip().startswith("["):
        print(run.stdout + run.stderr)
        return 1
    for job, got in zip(jobs, json.loads(run.stdout)):
        where = f"{job['name']} at {job['width']} px"
        if got.get("missing"):
            fails.append(f"{where}: {got['missing']}")
            continue
        for what in ("forestColours", "heatmapColours"):
            if got[what] is not None and got[what] < 8:
                fails.append(f"{where}: the {what[:-7]} drew nothing ({got[what]} colours)")
        fails += [f"{where}: {f}" for f in expect(job["cfg"], job["wide"], got)]
        fails += [f"{where}: error: {e}" for e in got["errors"]]
    for f in fails:
        print("FAIL", f)
    print(f"layout check: {len(jobs)} pages, " + ("ok" if not fails else f"{len(fails)} failed"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

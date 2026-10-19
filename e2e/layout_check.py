"""The deck list's layouts (Forest tab, Layout): the forest and the heatmap stand where each preset
puts them round Anki's deck list, beside it in a wide window and under it in a narrow one, and both
draw. Run: python3 e2e/layout_check.py (npm run test:layout); `npm test` runs it with --if-changed:
only when the files it goes through changed.

For each preset (state.LAYOUTS), on each side, it runs this copy's panel.on_deck_browser on the
tests' stand-in Anki (tests/fake_anki.py) with that layout, puts the HTML in a page built as Anki
builds its deck list (aqt/deckbrowser.py: <center><table>decks</table><br>stats</center>, with a
stand-in for Anki's "Studied today" line), opens it in headless Chrome (e2e/layout_check.mjs) at a
wide and a narrow width, and checks where the deck table, the forest and the heatmap stand, how wide
they are (the forest its Forest width, the heatmap 85% of what stands above or below it), that
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
CARDS = [(i, 10, i % 90) for i in range(1, 400)]  # (a forest, and three months of heatmap)
FOREST_W, SHARE = 800, 0.85  # the Forest width (config.json's max_width) and the heatmap's share of what it stands with
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


def layouts() -> dict:
    """This copy's presets (state.LAYOUTS), loaded on the stand-in Anki."""
    import fake_anki
    return import_module(f"{fake_anki.PACKAGE}.state").LAYOUTS


def cases() -> list:
    """(name, config, layout key, side)"""
    out = []
    for key, (forest, heatmap, _first) in layouts().items():
        sides = ("right", "left") if "side" in (forest, heatmap) else ("right",)
        out += [(f"{key}_{side}", {"layout": key, "layout_side": side}, key, side) for side in sides]
    return out


def expect(key: str, side: str, wide: bool, got: dict) -> list:
    """What is wrong with where they stand (got: each box's [left, top, right, bottom])."""
    t, f, h, win = got["table"], got["forest"], got["heatmap"], got["window"]
    fails, LAYOUTS = [], layouts()

    def beside(b):
        return b[0] >= t[2] + 8 if side == "right" else b[2] <= t[0] - 8

    def under(b, above):
        return b[1] >= above[3] - 1

    places = dict(zip(("forest", "heatmap"), LAYOUTS[key][:2]))
    if wide:
        for what, box in (("forest", f), ("heatmap", h)):
            if places[what] == "side" and not beside(box):
                fails.append(f"the {what} should stand {side} of the deck list: {box}, the list {t}")
            # (the side column's first starts level with the list; the second stands under it)
            top = places["forest"] != places["heatmap"] or what == LAYOUTS[key][2]
            if places[what] == "side" and top and box[1] > t[1] + 40:
                fails.append(f"the {what} should start level with the deck list: {box}, the list {t}")
            if places[what] == "below" and not under(box, t):
                fails.append(f"the {what} should be under the deck list: {box}, the list {t}")
    else:
        for what, box in (("forest", f), ("heatmap", h)):
            if not under(box, t):
                fails.append(f"in a narrow window the {what} should fall under the list: {box}, the list {t}")
    if places["forest"] == places["heatmap"] or not wide:
        first, second = (h, f) if LAYOUTS[key][2] == "heatmap" else (f, h)
        if not under(second, first):
            fails.append(f"the two should stand one above the other, {LAYOUTS[key][2]} first: forest {f}, heatmap {h}")
    if wide and places["forest"] == "below" and places["heatmap"] == "below" and got["arranged"]:
        fails.append("a stacked layout should leave Anki's deck list as it is (body.af-lay)")
    for what, box in (("forest", f), ("heatmap", h), ("table", t)):
        if box[2] > win + 1 or box[0] < -1:
            fails.append(f"the {what} reaches past the window ({win} px): {box}")
    fails += widths(places, wide, got)
    if got["studied"][1] < max(f[3], h[3], t[3]) - 1:
        fails.append(f"Anki's studied-today line should stay under everything: {got['studied']}")
    return fails


def widths(places: dict, wide: bool, got: dict) -> list:
    """What is wrong with their widths: the forest its Forest width, or the room it has; the heatmap
    85% of what stands above or below it (the forest, or under the list the row of the list and its
    side column), and beside the list alone, 85% of the Forest width."""
    t, s, c, win = got["table"], got["scene"], got["cal"], got["window"]
    forest, heat = s[2] - s[0], c[2] - c[0]
    fails = []

    def near(have, want, what):
        if abs(have - want) > 3:
            fails.append(f"the {what} should be {round(want)} px wide: it is {have}")
    if wide and places["forest"] == "side" or not wide or places["forest"] == places["heatmap"]:
        # (stacked under the list as ever, inside the panel's 12 px padding)
        most = FOREST_W - 24 if wide and places["forest"] == places["heatmap"] == "below" else FOREST_W
        near(forest, min(most, win - 24 - (t[2] - t[0]) - 32 if wide and places["forest"] == "side" else win - 24), "forest")
    if not wide or places["forest"] == places["heatmap"]:
        near(heat, SHARE * forest, "heatmap (85% of the forest's)")
    elif places["heatmap"] == "side":
        near(heat, SHARE * FOREST_W, "heatmap beside the list (85% of the Forest width)")
    elif places["forest"] == "side":
        row = max(t[2], s[2]) - min(t[0], s[0])
        near(heat, SHARE * row, "heatmap under the list (85% of the list and the forest beside it)")
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
        for name, cfg, key, side in cases():
            path = os.path.join(tmp, name + ".html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(page(panel_html(cfg), opts.dark))
            jobs += [{"name": name, "key": key, "side": side, "wide": w == WIDE, "width": w, "other": NARROW if w == WIDE else WIDE, "html": path,
                      "shot": os.path.join(os.path.abspath(opts.shots), f"{name}_{w}.png") if opts.shots else None} for w in (WIDE, NARROW)]
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
            if got[what] < 8:
                fails.append(f"{where}: the {what[:-7]} drew nothing ({got[what]} colours)")
        fails += [f"{where}: {f}" for f in expect(job["key"], job["side"], job["wide"], got)]
        fails += [f"{where}: error: {e}" for e in got["errors"]]
    for f in fails:
        print("FAIL", f)
    print(f"layout check: {len(jobs)} pages, " + ("ok" if not fails else f"{len(fails)} failed"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

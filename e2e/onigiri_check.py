"""Memory Forest in Onigiri: the add-on Onigiri lists in its widget gallery draws the forest and
the heatmap under it, in a tile of Onigiri's grid. Run: python3 e2e/onigiri_check.py (npm run
test:onigiri); `npm test` runs it with --if-changed: only when the files it goes through changed.

Onigiri (AnkiWeb 1011095603) draws the deck list as a grid of widgets. It lists every callback on
deck_browser_will_render_content as a widget named after its add-on, keeps a placed one as
"<module>.<name>" (the calendar's under a name of its own, panel.CALENDAR_TILE), offers one widget of
a name at a time in its gallery, calls each placed one with an object holding nothing but `stats`, and leaves out a
tile whose HTML is empty (1.3.0's blank tile: a second callback that drew nothing came first). This
does the same with this copy run on the tests' stand-in Anki (tests/fake_anki.py), puts the HTML in
a 4 x 4 tile as Onigiri does, opens it in headless Chrome (e2e/onigiri_check.mjs) and checks both
canvases drew, inside the tile, with no error; then again with the second callback placed too, the
study calendar's own tile: the forest alone in the first tile, the heatmap alone in its own. Needs
Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import types
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, HERE)
from phone_check import CALENDAR_FILES, CHROME, phone_changed

# the files the tile goes through: a change to one runs this
ONIGIRI_FILES = ("__init__.py", "panel.py", "onigiri.py", "payload.py", "web/forest.js", "web/core.js", *CALENDAR_FILES,
                 "web/forest.css", "e2e/onigiri_check.py", "e2e/onigiri_check.mjs")
# Onigiri 2.0.2's grid: 4 columns of 250 px, rows of 150, 15 apart; Memory Forest with the heatmap in it
# in 4 x 4, or each in a tile of its own, the forest's 4 x SPLIT_ROWS and the heatmap's 4 x HEAT_ROWS (its how-to)
COLS, COL_W, ROW_H, GAP, SPAN, SPLIT_ROWS, HEAT_ROWS = 4, 250, 150, 15, 4, 3, 2
CARDS = [(i, 10, i % 90) for i in range(1, 400)]  # (a forest, and three months of heatmap)


class OnigiriContent:
    """What Onigiri hands each callback: nothing but `stats`."""
    stats = ""


def tile_html(config: dict | None = None, split: bool = False) -> tuple[list, list]:
    """(the gallery's entries for this add-on, as "<module>.<name>"; the HTML of each tile drawn: the
    first callback's, the one the gallery offers first, or with `split` both, each placed on the grid)"""
    import fake_anki
    fake_anki.reset(cards=CARDS, config=config)
    ours = [cb for cb in list.__iter__(fake_anki.hooks.deck_browser_will_render_content)
            if cb.__globals__["__name__"].split(".")[0] == fake_anki.PACKAGE]  # (whatever Onigiri is told: panel.CALENDAR_TILE)
    names = [f"{cb.__module__}.{cb.__name__}" for cb in ours]
    if not ours:
        return names, []
    # Onigiri's settings, read by the add-on (onigiri.py): its grid, with what is placed on it
    settings = types.ModuleType("onigiri_check.core.config")
    grid = {n: {"grid_position": 0, "row_span": SPAN, "column_span": SPAN} for n in (names if split else names[:1])}
    settings.get_config_readonly = lambda: {"externalWidgetLayout": {"grid": grid, "archive": {}}}
    settings._place_external_widgets = lambda *a: None
    htmls = []
    with mock.patch.dict(sys.modules, {settings.__name__: settings}):
        for cb in ours if split else ours[:1]:
            content = OnigiriContent()
            cb(None, content)
            # the add-on's files as Anki serves them (/_addons/<folder>/...), from this copy
            htmls.append(content.stats.replace(f"/_addons/{fake_anki.PACKAGE}/", f"file://{ROOT}/"))
    return names, htmls


def page(htmls: list) -> str:
    """An Onigiri deck list: the tiles in its grid, on Anki's dark page, with Onigiri's wrapper on
    canvas.getContext (its WebGL tracker) in place before anything else."""
    w = SPAN * COL_W + (SPAN - 1) * GAP

    def size(rows: int) -> int:
        return rows * ROW_H + (rows - 1) * GAP
    rows = SPLIT_ROWS if len(htmls) > 1 else SPAN
    tiles = f'<div class="external-widget-container" id="tile" style="grid-area: 1 / 1 / span {rows} / span {SPAN}; width: {w}px; height: {size(rows)}px">{htmls[0]}</div>'
    if len(htmls) > 1:
        tiles += (f'<div class="external-widget-container" id="tile2" style="grid-area: {rows + 1} / 1 / span {HEAT_ROWS} / span {SPAN};'
                  f' width: {w}px; height: {size(HEAT_ROWS)}px">{htmls[1]}</div>')
    return f"""<!doctype html><html class="night-mode"><head><meta charset="utf-8">
<script>(function () {{ const o = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (k, ...a) {{ return o.call(this, k, ...a); }}; }})();
window.pycmd = (m, cb) => {{ if (cb) cb(null); return false; }};</script>
<style>body {{ margin: 0; background: #2c2c2c; color: #ddd; font-family: sans-serif }}
.unified-grid {{ display: grid; gap: {GAP}px; grid-auto-rows: {ROW_H}px; grid-template-columns: repeat({COLS}, {COL_W}px);
  justify-content: center; padding: 24px }}
.external-widget-container {{ width: 100%; height: 100%; display: flex; flex-direction: column; overflow: hidden; position: relative }}
</style></head><body class="nightMode"><div class="unified-grid">
{tiles}
</div></body></html>"""


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--if-changed", action="store_true", help="only if the files it goes through changed (ONIGIRI_FILES)")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed(ONIGIRI_FILES):
        print("onigiri check skipped: no files it goes through changed")
        return 0
    fails = []
    # (as it ships, and with a layout beside the deck list, which the tile keeps stacked: Onigiri's
    # grid places it, web/core.js AF.arrange)
    for config in (None, {"layout": "beside", "layout_side": "left"}):
        fails += check(config)
    fails += check(None, split=True)  # (the study calendar in its own tile)
    for f in fails:
        print("FAIL", f)
    print("onigiri check: " + ("ok" if not fails else f"{len(fails)} failed"))
    return 1 if fails else 0


def check(config: dict | None, split: bool = False) -> list:
    """What is wrong with the tile, made with `config` over the defaults; with `split`, the forest's
    tile and the study calendar's own."""
    names, htmls = tile_html(config, split)
    fails = []
    where = (f" (with {config})" if config else "") + (" (the calendar in its own tile)" if split else "")
    if len(names) != 2 or not names[0].endswith(".panel.on_deck_browser") or names[1] != "Memory Forest Heatmap.on_deck_browser_calendar":
        # (those names: a tile placed by one stays; the second under a name of its own in the gallery)
        fails.append(f"Onigiri's gallery should list panel.on_deck_browser, then Memory Forest Heatmap.on_deck_browser_calendar: it lists {names}")
    if not htmls or not all(htmls):
        fails.append("a widget Onigiri draws has nothing in it: a blank tile")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "onigiri.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(htmls))
            run = subprocess.run(["node", os.path.join(HERE, "onigiri_check.mjs"), path, CHROME] + (["split"] if split else []),
                                 capture_output=True, text=True, cwd=ROOT, timeout=120)
        if not run.stdout.strip().startswith("{"):
            return [f"the page didn't run{where}: {run.stdout + run.stderr}"]
        got = json.loads(run.stdout)
        for what in ("forest", "heatmap"):
            box = got[what]
            if not box:
                fails.append(f"no {what} in its tile")
            elif box["colours"] < 8:
                fails.append(f"the {what} drew nothing ({box['colours']} colours on its canvas)")
            elif not box["inTile"]:
                fails.append(f"the {what} lies outside its tile: {box['rect']} in {got['tile2'] if split and what == 'heatmap' else got['tile']}")
        if not split and got["forest"] and got["heatmap"] and got["heatmap"]["rect"][1] < got["forest"]["rect"][3]:
            fails.append(f"the heatmap should stand under the forest: {got['heatmap']['rect']}, the forest {got['forest']['rect']}")
        if split and any(px > 0 for px in got.get("overflow", [])):
            # (each tile as the how-to sizes it: all of it in view, no scroll bar)
            fails.append(f"a tile's content runs past its bottom: {got['overflow']} px")
        if got.get("strays"):
            fails.append(f"{got['strays']} forest or heatmap in the other's tile")
        fails += [f"error: {e}" for e in got["errors"]]
    return [f + where for f in fails]


if __name__ == "__main__":
    sys.exit(main())

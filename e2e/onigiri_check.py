"""Memory Forest in Onigiri: the add-on Onigiri lists in its widget gallery draws the forest and
the heatmap under it, in a tile of Onigiri's grid. Run: python3 e2e/onigiri_check.py (npm run
test:onigiri); `npm test` runs it with --if-changed: only when the files it goes through changed.

Onigiri (AnkiWeb 1011095603) draws the deck list as a grid of widgets. It lists every callback on
deck_browser_will_render_content as a widget named after its add-on, keeps a placed one as
"<module>.<name>", offers only an add-on's first callback in its gallery, calls each with an object
holding nothing but `stats`, and leaves out a tile whose HTML is empty (1.3.0's blank tile: a
second callback that drew nothing came first). This does the same with this copy run on the tests'
stand-in Anki (tests/fake_anki.py), puts the HTML in a 4 x 4 tile as Onigiri does, opens it in
headless Chrome (e2e/onigiri_check.mjs) and checks both canvases drew, inside the tile, with no
error. Needs Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, HERE)
from phone_check import CHROME, phone_changed

# the files the tile goes through: a change to one runs this
ONIGIRI_FILES = ("__init__.py", "panel.py", "payload.py", "web/forest.js", "web/core.js", "web/calendar.js",
                 "web/forest.css", "e2e/onigiri_check.py", "e2e/onigiri_check.mjs")
# Onigiri 2.0.2's grid: 4 columns of 250 px, rows of 150, 15 apart; Memory Forest in 4 x 4 (its how-to)
COLS, COL_W, ROW_H, GAP, SPAN = 4, 250, 150, 15, 4
CARDS = [(i, 10, i % 90) for i in range(1, 400)]  # (a forest, and three months of heatmap)


class OnigiriContent:
    """What Onigiri hands each callback: nothing but `stats`."""
    stats = ""


def tile_html(config: dict | None = None) -> tuple[list, str]:
    """(the gallery's entries for this add-on, as "<module>.<name>"; the HTML of the one it offers)"""
    import fake_anki
    fake_anki.reset(cards=CARDS, config=config)
    ours = [cb for cb in list.__iter__(fake_anki.hooks.deck_browser_will_render_content)
            if cb.__module__.split(".")[0] == fake_anki.PACKAGE]
    names = [f"{cb.__module__}.{cb.__name__}" for cb in ours]
    if not ours:
        return names, ""
    content = OnigiriContent()
    ours[0](None, content)  # (the first: the one the gallery offers)
    # the add-on's files as Anki serves them (/_addons/<folder>/...), from this copy
    return names, content.stats.replace(f"/_addons/{fake_anki.PACKAGE}/", f"file://{ROOT}/")


def page(html: str) -> str:
    """An Onigiri deck list: the tile in its grid, on Anki's dark page, with Onigiri's wrapper on
    canvas.getContext (its WebGL tracker) in place before anything else."""
    w, h = SPAN * COL_W + (SPAN - 1) * GAP, SPAN * ROW_H + (SPAN - 1) * GAP
    return f"""<!doctype html><html class="night-mode"><head><meta charset="utf-8">
<script>(function () {{ const o = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (k, ...a) {{ return o.call(this, k, ...a); }}; }})();
window.pycmd = (m, cb) => {{ if (cb) cb(null); return false; }};</script>
<style>body {{ margin: 0; background: #2c2c2c; color: #ddd; font-family: sans-serif }}
.unified-grid {{ display: grid; gap: {GAP}px; grid-auto-rows: {ROW_H}px; grid-template-columns: repeat({COLS}, {COL_W}px);
  justify-content: center; padding: 24px }}
.external-widget-container {{ width: 100%; height: 100%; display: flex; flex-direction: column; overflow: hidden; position: relative }}
</style></head><body class="nightMode"><div class="unified-grid">
<div class="external-widget-container" id="tile" style="grid-area: 1 / 1 / span {SPAN} / span {SPAN}; width: {w}px; height: {h}px">{html}</div>
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
    for config in (None, {"layout": "both_side", "layout_side": "left"}):
        fails += check(config)
    for f in fails:
        print("FAIL", f)
    print("onigiri check: " + ("ok" if not fails else f"{len(fails)} failed"))
    return 1 if fails else 0


def check(config: dict | None) -> list:
    """What is wrong with the tile, made with `config` over the defaults."""
    names, html = tile_html(config)
    fails = []
    where = f" (with {config})" if config else ""
    if len(names) != 1 or not names[0].endswith(".panel.on_deck_browser"):
        # (one: each is a widget there; and that name: a tile placed by it stays)
        fails.append(f"Onigiri's gallery should list one Memory Forest, panel.on_deck_browser: it lists {names}")
    if not html:
        fails.append("the widget Onigiri offers draws nothing: a blank tile")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "onigiri.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(html))
            run = subprocess.run(["node", os.path.join(HERE, "onigiri_check.mjs"), path, CHROME],
                                 capture_output=True, text=True, cwd=ROOT, timeout=120)
        if not run.stdout.strip().startswith("{"):
            return [f"the page didn't run{where}: {run.stdout + run.stderr}"]
        got = json.loads(run.stdout)
        for what in ("forest", "heatmap"):
            box = got[what]
            if not box:
                fails.append(f"no {what} in the tile")
            elif box["colours"] < 8:
                fails.append(f"the {what} drew nothing ({box['colours']} colours on its canvas)")
            elif not box["inTile"]:
                fails.append(f"the {what} lies outside the tile: {box['rect']} in {got['tile']}")
        if got["forest"] and got["heatmap"] and got["heatmap"]["rect"][1] < got["forest"]["rect"][3]:
            fails.append(f"the heatmap should stand under the forest: {got['heatmap']['rect']}, the forest {got['forest']['rect']}")
        fails += [f"error: {e}" for e in got["errors"]]
    return [f + where for f in fails]


if __name__ == "__main__":
    sys.exit(main())

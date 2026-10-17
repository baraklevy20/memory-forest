"""One scene of e2e/render_check.py, drawn: the page that mounts the real files in headless Chrome
with the clock stubbed and reports back (nothing threw, the canvas painted, its pixels; and for
the heatmap's scenes what its probes found), and the Chrome that runs it."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
WEB = os.path.join(ADDON, "web")
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

from render_heatmap import HEATMAP_PROBES

import catalog
import fake_forest
import forest_data
import scene

# $CHROME points elsewhere, as on the CI runners
CHROME = os.environ.get("CHROME") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NOW = dt.datetime(2026, 9, 19, 12)
PANEL_PX, MAX_WIDTH = 700, 900
CHROME_TIMEOUT_SECS = 120
VIRTUAL_TIME_MS = 60000
# the page polls until the canvas has drawn the same pixels twice, this often, this many times
SETTLE_MS, SETTLE_TRIES = 300, 60


def script_files() -> list:
    """Every script a scene can need, core first (as "envs/aurora.js")."""
    files = list(catalog.SCRIPTS)
    for kind in ("envs", "landscapes", "landmarks"):
        d = os.path.join(WEB, kind)
        if os.path.isdir(d):  # a kind can be removed wholesale by deleting its folder
            files += [f"{kind}/{n}" for n in sorted(os.listdir(d)) if n.endswith(".js")]
    return files


def scripts() -> str:
    return "\n".join(open(os.path.join(WEB, f), encoding="utf-8").read() for f in script_files())


def page(name: str, cfg: dict, n: int) -> str:
    heatmap, paper = cfg.pop("heatmap", None), cfg.pop("page", "dark")
    if heatmap:
        cfg = {"environment": "natural", "landscape": "lake", "weather": "clear", "time_of_day": "day"}
    cfg.setdefault("landmark", "none")
    mood = scene.choose_mood(cfg, NOW)
    f = forest_data.merge_old(fake_forest.make(n))
    data = {"trees": f["trees"], "stats": f["stats"], "visitors": f["visitors"], "merged": f.get("merged"),
            "forestSeed": f["forest_seed"], "anniversaries": [0] if n > 2 else [], "events": [], "journal": "",
            "mood": mood, "environmentName": name, "animations": False,
            "tooltips": True, "maxWidth": MAX_WIDTH, "testForest": True}
    if heatmap:
        data.update(calendar=heatmap, showForest=True, inAnki=True, journal=heatmap.pop("_journal", "Your forest grew its 300th tree today."))
    body = "body{margin:0;background:#f5f5f5;color:#222}" if paper == "light" else "body{margin:0;background:#2c2c2c;color:#ddd}"
    # (the heatmap is laid out by the add-on's stylesheet; the forest, a canvas, needs none)
    style = open(os.path.join(WEB, "forest.css"), encoding="utf-8").read() if heatmap else ""
    return (f"<!doctype html><meta charset=utf-8><style>{style}{body}.af-panel{{width:{PANEL_PX}px}}</style>"
            # The panel defers its build to an animation frame and then an idle callback.
            # Headless Chrome composites nothing, so the animation frame sometimes never
            # arrives and the scene is never built at all: run both on the next tick so
            # every scene builds, and builds the same way.
            "<script>window.requestAnimationFrame = cb => setTimeout(() => cb(12345), 0);"
            "window.requestIdleCallback = cb => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 0);"
            "performance.now = () => 12345; window.ERRS = [];"
            "window.onerror = (m, f, l, c, e) => { window.ERRS.push(String((e && e.stack) || m)); };</script>"
            "<div class='af-panel' id=p></div><pre id=o></pre>"
            + (f"<script>{HEATMAP_PROBES}</script>" if heatmap else "<script>async function probes() {}</script>") +
            f"<script>{scripts()}</script><script>window.D = {json.dumps(data)};</script>"
            "<script>try { AnkiForest.mount(document.getElementById('p'), window.D); }"
            "catch (e) { window.ERRS.push('mount: ' + (e.stack || e)); }</script>"
            # The panel builds on an idle callback, and if it is measured before the page
            # has laid out it builds once at the fallback width and again 200ms after the
            # resize observer notices the real one. Reading once caught whichever of the
            # two happened to be on screen, which is why this harness used to disagree with
            # itself run to run. Report only a canvas that has drawn the same pixels twice.
            "<script>let tries = 0, prev = null;"
            "function alpha(c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;"
            "  let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; }"
            "function report(c, r) {"
            "  if (!c) { r.canvas = 'missing'; r.painted = 0; }"
            "  else { r.painted = +(100 * alpha(c) / (c.width * c.height)).toFixed(1);"
            "    r.png = c.toDataURL(); r.w = c.width; r.h = c.height; }"
            "  document.getElementById('o').textContent = JSON.stringify(r);"
            "}"
            "(function wait() {"
            "  const c = document.querySelector('canvas'), r = { errors: window.ERRS };"
            "  if (window.ERRS.length) return report(c, r);"
            # a canvas nobody has sized yet is 300x150 and fully transparent, so an
            # untouched panel looks exactly as settled as a finished one. Painted pixels
            # are the gate: wait for the scene to exist, then for it to stop changing.
            "  const png = c && alpha(c) ? c.toDataURL() : null;"
            f"  if ((!png || png !== prev) && ++tries < {SETTLE_TRIES}) {{ prev = png; return setTimeout(wait, {SETTLE_MS}); }}"
            "  if (window.D.calendar && !document.querySelector('.af-cal-canvas') && ++tries < " + str(SETTLE_TRIES) + ") return setTimeout(wait, " + str(SETTLE_MS) + ");"
            "  probes(r).catch(e => r.errors.push('probes: ' + (e.stack || e))).then(() => {"
            "    report(c, r); if (r.heatmap) { r.png = r.heatmap; delete r.heatmap; } document.getElementById('o').textContent = JSON.stringify(r); });"
            "})();</script>")


def render(case) -> tuple:
    name, cfg, n = case
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(page(name, dict(cfg), n))
        path = fh.name
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--virtual-time-budget={VIRTUAL_TIME_MS}",
                              "--dump-dom", "file://" + path], capture_output=True, text=True, timeout=CHROME_TIMEOUT_SECS).stdout
    except subprocess.TimeoutExpired:
        return name, {"errors": ["chrome timed out"], "painted": 0}
    finally:
        os.unlink(path)
    m = re.search(r'<pre id="?o"?>(.*?)</pre>', dom, re.S)
    if not m:
        return name, {"errors": ["the page never reported back"], "painted": 0}
    return name, json.loads(html.unescape(m.group(1)))

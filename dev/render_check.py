"""Render the forest in every combination that exists and check it actually drew.

The unit tests cover the Python; this covers the half that only a browser can run. It
mounts the real files in headless Chrome with the clock stubbed, then asserts, for each
scene, that nothing threw and that the canvas is not blank. With a baseline it also
checks that the pixels have not changed.

    python3 dev/render_check.py smoke          # every combination: errors + blank canvas
    python3 dev/render_check.py smoke --quick  # a representative subset, for a fast loop
    python3 dev/render_check.py baseline       # record hashes of every scene
    python3 dev/render_check.py compare        # ... and check them later
    python3 dev/render_check.py compare --quick  # a subset, when you are in a hurry

Needs Chrome. Scenes render three at a time; the full sweep takes a few minutes.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
WEB = os.path.join(ADDON, "web")
sys.path.insert(0, ADDON)

import datetime as dt

import catalog
import fake_forest
import forest_data
import presets
import scene

# $CHROME points elsewhere, as on the CI runners
CHROME = os.environ.get("CHROME") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASELINE = os.path.join(HERE, "render_baseline.json")
NOW = dt.datetime(2026, 9, 19, 12)
SCENE_TREES = 200  # the forest every scene is drawn on, unless it is about forest size
# the forest sizes tried, either side of the deep-forest cutoff
SIZES = (0, 1, 2, 30, forest_data.MAX_INDIVIDUAL_TREES - 1, forest_data.MAX_INDIVIDUAL_TREES,
         forest_data.MAX_INDIVIDUAL_TREES + 1, 1000, 5000)
# --quick keeps every this-many-th environment and preset, and the first few of the rest
QUICK_ENV_EVERY, QUICK_PRESET_EVERY, QUICK_WEATHERS, QUICK_TIMES, QUICK_LANDMARKS = 4, 5, 3, 2, 2
PANEL_PX, MAX_WIDTH = 700, 900
WORKERS = 3  # headless Chromes at once
CHROME_TIMEOUT_SECS = 120
VIRTUAL_TIME_MS = 60000
# the page polls until the canvas has drawn the same pixels twice, this often, this many times
SETTLE_MS, SETTLE_TRIES = 300, 60


def scripts() -> str:
    files = list(catalog.SCRIPTS)
    for kind in ("envs", "landscapes", "landmarks"):
        d = os.path.join(WEB, kind)
        if os.path.isdir(d):  # a kind can be removed wholesale by deleting its folder
            files += [f"{kind}/{n}" for n in sorted(os.listdir(d)) if n.endswith(".js")]
    return "\n".join(open(os.path.join(WEB, f), encoding="utf-8").read() for f in files)


def scenes(quick: bool) -> list:
    """Every preset, and every environment against every landscape, hour and weather.

    The bug that prompted this file was a landscape nobody rendered; the one after it was
    a sun nobody had drawn at dusk, because weather and time of day were only ever tried
    on the plain forest. The matrix is the point, not the count.
    """
    out, envs = [], list(scene.ENVIRONMENTS)
    lands, marks = list(scene.LANDSCAPES), list(scene.LANDMARKS)
    weathers, times = list(scene.WEATHERS), list(scene.TIMES)
    if quick:
        envs = list(dict.fromkeys(envs[::QUICK_ENV_EVERY] + ["natural"]))  # natural is often already in the slice
        weathers, times, marks = weathers[:QUICK_WEATHERS], times[:QUICK_TIMES], marks[:QUICK_LANDMARKS]

    for env in envs:  # every environment on every landscape
        for land in lands:
            out.append((f"{env}-{land}", {"environment": env, "landscape": land, "weather": "clear", "time_of_day": "day"}, SCENE_TREES))
    for env in envs:  # every environment at every hour of the day, and in every weather
        for t in times:
            out.append((f"{env}-at-{t}", {"environment": env, "landscape": "meadow", "weather": "clear", "time_of_day": t}, SCENE_TREES))
        for w in weathers:
            out.append((f"{env}-in-{w}", {"environment": env, "landscape": "meadow", "weather": w, "time_of_day": "day"}, SCENE_TREES))
    for land in lands:  # every landscape in every weather, and at night
        for w in weathers:
            out.append((f"{land}-{w}", {"environment": "natural", "landscape": land, "weather": w, "time_of_day": "day"}, SCENE_TREES))
        for t in times:
            out.append((f"{land}-{t}", {"environment": "natural", "landscape": land, "weather": "clear", "time_of_day": t}, SCENE_TREES))
    for mark in marks:  # every landmark
        for land in lands:
            out.append((f"{mark}-{land}", {"environment": "natural", "landscape": land, "landmark": mark, "weather": "clear", "time_of_day": "day"}, SCENE_TREES))
    # the catalogue the settings dialog offers, drawn exactly as it ships
    for p in (presets.FOREST_PRESETS[::QUICK_PRESET_EVERY] if quick else presets.FOREST_PRESETS):
        out.append((f"preset-{p.key}", dict(p.values()), SCENE_TREES))
    for n in SIZES:
        out.append((f"trees-{n}", {"environment": "natural", "landscape": "lake", "weather": "clear", "time_of_day": "day"}, n))
    # two scenes sharing a name would quietly become one, which is how coverage is lost
    names = [c[0] for c in out]
    assert len(set(names)) == len(names), "duplicate scene names: " + str(sorted({n for n in names if names.count(n) > 1}))
    return out


def page(name: str, cfg: dict, n: int) -> str:
    cfg.setdefault("landmark", "none")
    mood = scene.choose_mood(cfg, NOW)
    f = forest_data.merge_old(fake_forest.make(n))
    data = {"trees": f["trees"], "stats": f["stats"], "visitors": f["visitors"], "merged": f.get("merged"),
            "forestSeed": f["forest_seed"], "anniversaries": [0] if n > 2 else [], "events": [], "journal": "",
            "mood": mood, "environmentName": name, "animations": False,
            "tooltips": True, "maxWidth": MAX_WIDTH, "testForest": True}
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0}}.af-panel{{width:{PANEL_PX}px}}</style>"
            # The panel defers its build to an animation frame and then an idle callback.
            # Headless Chrome composites nothing, so the animation frame sometimes never
            # arrives and the scene is never built at all: run both on the next tick so
            # every scene builds, and builds the same way.
            "<script>window.requestAnimationFrame = cb => setTimeout(() => cb(12345), 0);"
            "window.requestIdleCallback = cb => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 0);"
            "performance.now = () => 12345; window.ERRS = [];"
            "window.onerror = (m, f, l, c, e) => { window.ERRS.push(String((e && e.stack) || m)); };</script>"
            "<div class='af-panel' id=p></div><pre id=o></pre>"
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
            "  report(c, r);"
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
    import html as H
    return name, json.loads(H.unescape(m.group(1)))


def failed(r: dict) -> bool:
    return bool(r.get("errors")) or r.get("painted", 0) < 1


def clock(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    return f"{m}:{s:02d}"


def run(cases: list) -> dict:
    """Render in parallel, then give anything that failed a second, unhurried try.

    Three headless Chromes competing for the CPU can miss a slow scene, and a harness
    that cries wolf is worse than no harness: only a scene that fails on its own counts.
    """
    out, retry, start = {}, [], time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for done, (name, r) in enumerate(pool.map(render, cases), 1):
            out[name] = r
            if failed(r):
                retry.append(name)
            # how far along, and at this pace how long is left
            took = time.monotonic() - start
            progress = f"[{done}/{len(cases)} {clock(took)} in, ~{clock(took / done * (len(cases) - done))} left]"
            print(f"ok   {name:<28} painted {r.get('painted', 0):>5}%  {progress}" if not failed(r)
                  else f"...  {name:<28} will retry  {progress}", flush=True)
    by_name = {c[0]: c for c in cases}
    for name in retry:
        _n, r = render(by_name[name])
        out[name] = r
        print(("FAIL " if failed(r) else "ok   ") + f"{name:<28} painted {r.get('painted', 0):>5}%"
              + (f"  {r['errors'][0].splitlines()[0][:90]}" if r.get("errors") else " (passed on retry)"))
    return out


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    quick = "--quick" in sys.argv
    # The baseline used to cover a fifth of the environments, so a change to synthwave's
    # sun could be reported as "75/75 unchanged". It records the whole matrix now.
    cases = scenes(quick)
    print(f"{len(cases)} scenes\n")
    results = run(cases)
    bad = {k: v for k, v in results.items() if failed(v)}
    changed = []

    if what in ("baseline", "compare"):
        hashes = {k: hashlib.sha1(v["png"].encode()).hexdigest()[:12] for k, v in results.items() if v.get("png")}
        if what == "baseline":
            json.dump(hashes, open(BASELINE, "w"), indent=1, sort_keys=True)
            print(f"\nwrote {len(hashes)} hashes to {os.path.relpath(BASELINE, ADDON)}")
        else:
            old = json.load(open(BASELINE))
            # only scenes both runs drew can be compared: a scene missing from either side
            # (a different --quick sample, a new environment) is not a change
            both = [k for k in old if k in hashes]
            changed = [k for k in both if old[k] != hashes[k]]
            print(f"\nunchanged: {len(both) - len(changed)}/{len(both)}"
                  f" ({len(old) - len(both)} only in the baseline, {len(hashes) - len(both)} only in this run)")
            for k in changed:
                print(f"  CHANGED {k}")
    print(f"\n{len(results) - len(bad)}/{len(results)} scenes drew cleanly")
    if bad:
        print("failed: " + ", ".join(sorted(bad)))
    if changed:
        print(f"{len(changed)} scenes drew differently than the baseline: " + ", ".join(sorted(changed)))
    if bad or changed:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Render the forest in every combination that exists and check it actually drew.

The unit tests cover the Python; this covers the half that only a browser can run. It
mounts the real files in headless Chrome with the clock stubbed, then asserts, for each
scene, that nothing threw and that the canvas is not blank. With a baseline it also
checks that the pixels have not changed.

    python3 e2e/render_check.py smoke          # every combination: errors + blank canvas
    python3 e2e/render_check.py smoke --quick  # a representative subset, for a fast loop
    python3 e2e/render_check.py baseline       # record hashes of every scene
    python3 e2e/render_check.py compare        # ... and check them later
    python3 e2e/render_check.py compare --quick  # a subset, when you are in a hurry
    python3 e2e/render_check.py baseline --only bamboo  # just the scenes that use it

--only takes one or more environments, landscapes or landmarks, or heatmap (comma-separated), and keeps
the scenes that use any of them: `--only bamboo` is its preset and every hour,
weather and landscape it is drawn in. A baseline made with --only updates those scenes'
hashes and keeps everyone else's.

The study heatmap under the forest has scenes of its own ("heatmap-*", `--only heatmap`): each
view, By year with its earlier years hidden, shown and all, on a dark and a light page. Beyond
drawing, each one checks what broke in October 2026 without a picture changing: the room kept
before it draws is the room it takes (else the panel jumps), and a day, a shade in the key and a
trophy each answer the pointer with their tooltip.

Needs Chrome. Scenes render three at a time; the full sweep takes a few minutes.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ADDON, "dev"))  # (stale_tiles)

from render_page import render
from render_scenes import scenes

import presets

BASELINE = os.path.join(HERE, "render_baseline.json")
WORKERS = 3  # headless Chromes at once


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
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    # The baseline used to cover a fifth of the environments, so a change to synthwave's
    # sun could be reported as "75/75 unchanged". It records the whole matrix now.
    cases = scenes(quick)
    if only:
        cases = [c for c in cases if only & {c[1].get("environment"), c[1].get("landscape"), c[1].get("landmark")}
                 or ("heatmap" in only and "heatmap" in c[1])]
        if not cases:
            sys.exit(f"no scene uses {', '.join(sorted(only))}")
    print(f"{len(cases)} scenes\n")
    results = run(cases)
    bad = {k: v for k, v in results.items() if failed(v)}
    changed = []

    if what in ("baseline", "compare"):
        hashes = {k: hashlib.sha1(v["png"].encode()).hexdigest()[:12] for k, v in results.items() if v.get("png")}
        if what == "baseline":
            # a partial run only refreshes its own scenes
            kept = json.load(open(BASELINE)) if only and os.path.exists(BASELINE) else {}
            json.dump({**kept, **hashes}, open(BASELINE, "w"), indent=1, sort_keys=True)
            print(f"\nwrote {len(hashes)} hashes to {os.path.relpath(BASELINE, ADDON)}" + (f", kept {len(kept.keys() - hashes.keys())} others" if only else ""))
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
        # the presets drawn in a changed environment may have picker tiles that no longer match
        # (dev/stale_tiles.py only notices a preset's own files changing, not the engine's)
        import stale_tiles
        envs = {cfg.get("environment") for name, cfg, _n in cases if name in changed}
        keep = stale_tiles.tracked()
        keys = [p.key for p in presets.FOREST_PRESETS
                if p.environment in envs and p.key != presets.DAILY and (keep is None or p.key in keep)]
        if keys:
            print("their presets' picker tiles may be out of date too; if they look different, draw them again with:\n"
                  + stale_tiles.advice(dict.fromkeys(stale_tiles.KINDS, keys)))
    if bad or changed:
        sys.exit(1)


if __name__ == "__main__":
    main()

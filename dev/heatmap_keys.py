"""Write settings/heatmap_keys.json: each shipped scenery's own heatmap colour, as web/calendar.js
finds it (the scenery's `calendar` colour or colours, or its most colourful crown colour), read
off the real scripts in headless Chrome. The Heatmap tab draws its pictures with these (the strips
on the scenery tiles, Taken as, the tile samples); the heatmap itself reads the scenery.

    python3 dev/heatmap_keys.py      (npm run heatmap-keys)

Run it after adding a scenery to an edition, or after changing its trees' or its calendar's
colours; the tests fail while a shipped scenery has no colour here. Needs Chrome.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ADDON, "e2e"))  # (render_page)

import render_page

import catalog
import presets
import scene

OUT = os.path.join(ADDON, "settings", "heatmap_keys.json")
NOON = _dt.datetime(2026, 6, 1, 12, 0)  # (the scene in plain light: calendar.js takes the hour's tint off anyway)

SCRIPT = r"""
import puppeteer from '%(puppeteer)s';
const b = await puppeteer.launch({ executablePath: %(chrome)s, headless: 'new', args: ['--disable-gpu'] });
const p = await b.newPage();
await p.goto('file://%(page)s');
await p.waitForFunction('window.__keys');
console.log(JSON.stringify(await p.evaluate(() => window.__keys)));
await b.close();
"""


def shipped_envs() -> list:
    """Every environment an edition ships (natural first), that this copy has."""
    try:
        with open(os.path.join(ADDON, "editions.json"), encoding="utf-8") as f:
            eds = json.load(f)
    except OSError:  # (the public copy: every scenery it has is the edition)
        eds = {"base": {"envs": ["natural", *catalog.entries("envs")]}, "plus": {"envs": []}}
    out = []
    for ed in ("base", "plus"):
        out += [e for e in eds[ed]["envs"] if e not in out]
    return [e for e in out if e == "natural" or os.path.exists(os.path.join(catalog.WEB, "envs", f"{e}.js"))]


def main() -> None:
    envs = shipped_envs()
    moods = {}
    for env in envs:
        p = next(p for p in presets.FOREST_PRESETS if p.environment == env)
        moods[env] = scene.choose_mood({"environment": p.environment, "landscape": p.landscape, "landmark": p.landmark,
                                        "weather": p.weather, "time_of_day": p.time}, NOON)
    scripts = [os.path.join(catalog.WEB, s) for s in catalog.SCRIPTS]
    scripts += [os.path.join(catalog.WEB, "envs", f"{e}.js") for e in envs if e != "natural"]
    tags = "".join(f'<script src="file://{s}"></script>' for s in scripts)
    probe = """<script>
const AF = window.AnkiForest, MOODS = MOODS_JSON, out = {};
const hx = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
const chroma = c => Math.max(...c) - Math.min(...c);
for (const [env, mood] of Object.entries(MOODS)) {
  const sp = { mood, theme: Object.assign({}, AF.theme(mood, {}, []), { tint: null, tintAmt: 0 }), data: {} };
  const own = AF.envOf(sp).calendar;
  out[env] = own || hx(AF.foliage(sp).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a));
}
window.__keys = out;
</script>""".replace("MOODS_JSON", json.dumps(moods))
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "keys.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(f'<!doctype html><meta charset="utf-8"><script>window.pycmd = () => false;</script>{tags}{probe}')
        mjs = os.path.join(tmp, "keys.mjs")
        with open(mjs, "w", encoding="utf-8") as f:
            f.write(SCRIPT % {"puppeteer": os.path.join(ADDON, "node_modules", "puppeteer-core", "lib", "esm", "puppeteer", "puppeteer-core.js"),
                              "chrome": json.dumps(render_page.CHROME), "page": page})
        keys = json.loads(subprocess.run(["node", mjs], check=True, capture_output=True, text=True).stdout)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=1)
        f.write("\n")
    print(f"{len(keys)} sceneries: {OUT}")


if __name__ == "__main__":
    main()

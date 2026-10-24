"""Write settings/heatmap_keys.json: each shipped scenery's own heatmap colour, as web/calendar.js
finds it (the scenery's `calendar` colour or colours, or its most colourful crown colour), read
off the real scripts in headless Chrome. The Heatmap tab draws its pictures with these (the strips
on the scenery tiles, Taken as, the tile samples); the heatmap itself reads the scenery.

    python3 dev/heatmap_keys.py      (npm run heatmap-keys)

Run it after adding a scenery to an edition, or after changing its trees' or its calendar's
colours; the tests fail while a shipped scenery has no colour here. Needs Chrome.

It writes settings/heatmap_hours.json too: what the forest's hour does to each scenery's colours
(calendar.js hourOf), so the Heatmap tab's pictures follow the hour as the heatmap does: its day
colours (`calendarDay`), its colours for each hour (`calendarHours`) and its night tint (the
night sky's, which a day scenery's colours turn towards after dark), each only where it has one.
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
HOURS_OUT = os.path.join(ADDON, "settings", "heatmap_hours.json")
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
const AF = window.AnkiForest, MOODS = MOODS_JSON, out = {}, hours = {};
const hx = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
const chroma = c => Math.max(...c) - Math.min(...c);
for (const [env, mood] of Object.entries(MOODS)) {
  const sp = { mood, theme: Object.assign({}, AF.theme(mood, {}, []), { tint: null, tintAmt: 0 }), data: {} };
  const own = AF.envOf(sp).calendar;
  out[env] = own || hx(AF.foliage(sp).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a));
  // (what the hour does to them, as calendar.js hourOf finds it: the night tint as it asks for it)
  const spec = AF.envOf(sp), at = {};
  if (spec.calendarDay) at.day = spec.calendarDay;
  if (spec.calendarHours) at.hours = spec.calendarHours;
  try {
    const tint = AF.theme(Object.assign({}, mood, { time: 'night', weather: 'clear' }), {}, []).tint;
    if (tint) at.tint = tint;
  } catch { /* no night tint: its colours stay as they are after dark */ }
  if (Object.keys(at).length) hours[env] = at;
}
window.__keys = { keys: out, hours };
</script>""".replace("MOODS_JSON", json.dumps(moods))
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "keys.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(f'<!doctype html><meta charset="utf-8"><script>window.pycmd = () => false;</script>{tags}{probe}')
        mjs = os.path.join(tmp, "keys.mjs")
        with open(mjs, "w", encoding="utf-8") as f:
            f.write(SCRIPT % {"puppeteer": os.path.join(ADDON, "node_modules", "puppeteer-core", "lib", "esm", "puppeteer", "puppeteer-core.js"),
                              "chrome": json.dumps(render_page.CHROME), "page": page})
        found = json.loads(subprocess.run(["node", mjs], check=True, capture_output=True, text=True).stdout)
    keys = found["keys"]
    for path, data in ((OUT, keys), (HOURS_OUT, found["hours"])):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
            f.write("\n")
    print(f"{len(keys)} sceneries: {OUT}, {HOURS_OUT}")


if __name__ == "__main__":
    main()

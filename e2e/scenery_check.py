"""Every shipped scenery draws in every sky, on every landscape, with every landmark, at every
forest size and with everything Nature brings, without an error, the same way every time, and
without moving a tree. Run: python3 e2e/scenery_check.py (npm run test:scenery); --quick for a
few scenes a scenery, --only aurora,bamboo for some of them; `npm test` runs it --quick --if-changed:
only when a file a scene goes through changed.

e2e/render_check.py draws one Chrome per scene and compares pictures with a baseline; this one
asks what a picture can't show and needs no baseline. Each scene is the add-on's own payload
(payload.payload() in a stand-in Anki, tests/fake_anki.py, on the test forest: fake data only),
mounted in turn on one page of one headless Chrome (e2e/scenery_check.mjs). For each it checks:

- nothing threw and nothing was logged as an error, while it was built and as it animates;
- the canvas is painted edge to edge, with more than a handful of colours;
- drawn again on a fresh page, in the opposite order and with Math.random giving other numbers,
  it is the same picture (a scenery that reads randomness, or the scenes drawn before it,
  changes when Anki redraws the deck list);
- made narrower once drawn, it draws as a forest drawn at that width does;
- swapped in for the forest before it, as a settings change does (loading its scenery's files
  then), it draws as it does on a fresh page;
- the trees stand in the same place whatever the hour and the weather (the tooltips, the zoom
  and the timelapse all go by where a tree stands);
- each weather, the night, the trees, the fire, the smoke, the craters and the crows each
  change the picture: a scenery that draws over one of them hides it;
- animated, it keeps drawing (and something in it keeps moving) an hour on;
- zoomed in among the old trees, walked along and a tree picked, it draws, and back out it is the
  forest it was.

Only the sceneries an edition ships, on the landscapes and with the landmarks it ships (editions.json;
every one here in the public repo), never the drafts. Needs Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import catalog
import presets
import scene

CHROME = os.environ.get("CHROME") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TREES = 200  # the test forest of most scenes
SIZES = (0, 1, 2, 729, 730, 731, 1500, 5000)  # either side of the deep-forest cutoff (forest_data.MAX_INDIVIDUAL_TREES)
# an animated scene's clock, in seconds from its mount: the first frames, and an hour on
FRAMES = (0, 1.5, 4, 3600, 3602.5)
QUICK_FRAMES = (0, 4, 3600)
# a painted canvas: (nearly) every pixel opaque, and more colours than a blank or a flat fill
MIN_OPAQUE, MIN_COLOURS = 0.98, 12
# Nature's timelines (the Debug tab's, events.timeline_steps), each against the same days on
# Peaceful, where none of it happens: the picture must differ
NATURE = {
    "smoke": ("wild", [["away", 2]]),
    "fire": ("wild", [["away", 3]]),
    "fire-out": ("wild", [["away", 3], ["study", 7]]),
    "crater": ("merciless", [["study", 2], ["away", 1], ["study", 2]]),
    "struck": ("merciless", [["study", 3], ["away", 1]]),
    "crows": ("wild", [["study", 2], ["leech", 3]]),
    "grass": ("wild", [["study", 1], ["review", 8]]),
}
NATURE_SHOWN = ("smoke", "fire", "crater", "crows", "grass")  # what Peaceful takes away
# what the page loads before the sceneries
PREAMBLE = """<script>
window.__T0 = 12345; window.__now = window.__T0;
performance.now = () => window.__now;  // the forest's clock, moved on by hand (scenery_check.mjs)
window.requestAnimationFrame = cb => setTimeout(() => cb(performance.now()), 16);
window.requestIdleCallback = cb => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 0);
window.pycmd = (msg, cb) => { if (msg.includes(':deep:') && cb) setTimeout(() => cb(window.__behind || []), 0); return false; };
window.__snap = () => {
  const c = document.querySelector('#p canvas');
  if (!c || !c.width) return { hash: null, opaque: 0, colours: 0, w: 0, h: 0 };
  const d = new Uint32Array(c.getContext('2d').getImageData(0, 0, c.width, c.height).data.buffer);
  let h = 0x811c9dc5, opaque = 0; const cols = new Set();
  for (let i = 0; i < d.length; i++) {
    const v = d[i]; h = Math.imul(h ^ v, 16777619);
    if ((v >>> 24) === 255) opaque++;
    if (cols.size < 4096) cols.add(v);
  }
  return { hash: (h >>> 0).toString(16), opaque: opaque / d.length, colours: cols.size, w: c.width, h: c.height };
};
window.__mount = (data, seed) => {  // (data._width: the panel's, in css pixels)
  const errors = [];
  let s = seed >>> 0;  // (mulberry32: a Math.random of its own for each pass)
  Math.random = () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  window.__now = window.__T0;
  window.__behind = data._behind;
  const old = document.getElementById('p');
  if (old) { old.afToken = {}; old.remove(); }  // (retired: its timers stop at their next tick)
  const root = document.createElement('div');
  root.id = 'p'; root.className = 'af-panel'; root.style.width = (data._width || 700) + 'px';
  document.body.append(root);
  try { (window.__AF || AnkiForest).mount(root, data, { now: true }); } catch (e) { errors.push('mount: ' + (e.stack || e)); }
  const shot = window.__snap();
  shot.errors = errors;
  const env = root.afEnv;
  shot.placed = env && env.placed ? env.placed.filter(q => !q.it.pond)
    .map(q => [q.it.index, Math.round(q.x * 100), Math.round(q.y * 100), Math.round(q.s * 1000)]) : null;
  return shot;
};
// a settings change, as the panel makes it (panel.py): the forest on the page swapped for the new
// one, which first loads the scenery files this page lacks (core.js AF.swap); the first, mounted
window.__swap = async (data, srcs, seed) => {
  const root = document.getElementById('p');
  if (!root) {
    await window.__AF.loadScripts(srcs);
    return window.__mount(data, seed);
  }
  let s = seed >>> 0;
  Math.random = () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  window.__now = window.__T0;
  const errors = [], before = root.afEnv;
  if (!root.afSwap(data, srcs)) errors.push('the forest refused the swap');
  for (let i = 0; i < 300 && root.afEnv === before; i++) await new Promise(r => setTimeout(r, 10));
  if (root.afEnv === before) errors.push('the swapped forest never drew');
  const shot = window.__snap();
  shot.errors = errors;
  return shot;
};
</script>"""

# Scenes known to fail a check, with why: reported as expected failures, not as failures, until
# fixed (then the check says so, and the line goes). {(scene name, check): "BUG: ..."}
KNOWN: dict = {}


def shipped(kind: str = "envs") -> list:
    """The environments (or landscapes, or landmarks) an edition ships, in the catalogue's
    order: dev/editions.py, from editions.json; every one here where there is none, as in the
    public repo, which is one edition."""
    sys.path.insert(0, os.path.join(ROOT, "dev"))
    import editions
    every = list(catalog.entries(kind))
    if not editions.available():
        return every
    keys = set().union(*(editions.scenery(name)[kind] for name in editions.available()))
    return [k for k in every if k in keys]


def own_preset(env: str) -> presets.Preset:
    return next(p for p in presets.FOREST_PRESETS if p.environment == env)


_payload = None


def payload(look: dict, trees: int = TREES, nature: str = "peaceful", timeline=(), animations: bool = False,
            deck: int | None = None, **cfg) -> dict:
    """What the add-on would send the page for this look, on a test forest of `trees` trees; or
    with a `deck`, that deck's own forest of a made-up collection (CARDS), its cards lit."""
    global _payload
    if _payload is None:
        from fake_anki import addon, reset
        _payload = (addon, reset)
    addon, reset = _payload
    reset(CARDS if deck else (), dict({"debug": True, "test_forest": not deck, "test_trees": trees, "nature": nature,
                                       "debug_timeline": [list(s) for s in timeline],
                                       "animations": "on" if animations else "off"}, **look, **cfg))
    data = addon.payload.payload(deck, highlight=bool(deck))
    data.update(calendar=None, news=None, animations=animations)  # (the forest only: the heatmap has checks of its own)
    data["_behind"] = addon.payload.deep_trees(str(deck) if deck else "")  # what Anki answers the zoom's ask for the old trees
    return data


# a made-up collection for the deck forests: two decks (tests/fake_anki.py's French and German),
# studied most days of the last 90, a break of ten days in the middle: (card id, deck, days ago)
CARDS = [(1000 + i, 10 if i % 3 else 20, 90 - i // 2) for i in range(180) if not 80 <= i < 100]


def scenes(envs: list, quick: bool) -> list:
    """name, the payload, the stillness group (the scenes whose trees must stand alike), whether
    it is drawn again for determinism, and the clock of an animated one."""
    out = []

    def add(name, look, group=None, again=False, frames=None, zoom=False, swap=False, **kw):
        page_keys = {k: kw.pop(k) for k in ("_width", "_resize") if k in kw}
        data = dict(payload(look, **kw), **page_keys)
        behind = data.pop("_behind")
        if zoom:
            data.update(zoom=True, _behind=behind)
        srcs = ["file://" + os.path.join(catalog.WEB, f) for f in catalog.scenery_files(data["mood"])]
        out.append({"name": name, "data": data, "group": group, "again": again, "frames": frames, "zoom": zoom,
                    "swap": swap, "srcs": srcs})

    for env in envs:
        p = own_preset(env)
        base = p.values()
        here = f"{env}|{p.landscape}|{p.landmark}"
        add(f"{env}-preset", base, here, again=True, swap=True)
        times = [t for t in scene.TIMES if t != p.time]
        if quick:
            times = ["night" if p.time != "night" else "day"]
        for t in times:
            add(f"{env}-at-{t}", dict(base, time_of_day=t), here, again=not quick)
        weathers = [w for w in (("rain", "snow") if quick else scene.WEATHERS) if w != p.weather]
        for w in weathers:
            add(f"{env}-in-{w}", dict(base, weather=w), here, again=not quick)
        if not quick:
            for land in shipped("landscapes"):
                if land != p.landscape:
                    add(f"{env}-on-{land}", dict(base, landscape=land), f"{env}|{land}|{p.landmark}", again=True, swap=True)
                    add(f"{env}-on-{land}-storm-night", dict(base, landscape=land, weather="storm", time_of_day="night"),
                        f"{env}|{land}|{p.landmark}")
            for mark in shipped("landmarks"):
                if mark != p.landmark:
                    add(f"{env}-with-{mark}", dict(base, landmark=mark), again=True, swap=True)
        for n in ((0, 1500) if quick else SIZES):
            add(f"{env}-trees-{n}", base, f"{here}|{n}", trees=n, again=n in (0, 1500))
        for key, (level, steps) in NATURE.items():
            if quick and key not in ("fire", "crater"):
                continue
            add(f"{env}-{key}", base, again=True, nature=level, timeline=steps)
            if key in NATURE_SHOWN:
                add(f"{env}-{key}-peaceful", base, nature="peaceful", timeline=steps)
        if not quick:
            add(f"{env}-backlog-big-days", base, nature="wild", debug_backlog=60, debug_big_days=True, again=True)
            add(f"{env}-pond", base, timeline=[["study", 5], ["away", 12], ["study", 3]], again=True)
            sky = payload(dict(base, time_of_day="night", weather="clear"))
            out.append({"name": f"{env}-meteors-harvest-moon", "data": dict(sky, events=["meteor_shower", "harvest_moon", "new_ancient"]),
                        "group": None, "again": True, "frames": None})
        # zoomed in among the old trees (web/visit.js): walked in and along, a tree picked and the
        # day before it, then back out to the forest as it was
        add(f"{env}-zoomed-in", base, zoom=True, trees=800 if quick else 1500)
        if not quick:
            add(f"{env}-zoomed-in-small", dict(base, weather="snow", time_of_day="night"), zoom=True, trees=30)
        if not quick:
            # the panel at its narrowest and widest, and made narrower once drawn (core.js rebuilds it)
            add(f"{env}-narrow", base, _width=250)
            add(f"{env}-wide", base, _width=1200)
            add(f"{env}-resized", base, _resize=300)
            add(f"{env}-at-300px", base, _width=300)
            # a deck's own forest (the deck screen), its trees lit: two decks
            add(f"{env}-deck", base, deck=10, again=True)
            add(f"{env}-deck-german", base, deck=20)
            add(f"{env}-fire-old-trees", base, trees=1500, nature="wild", timeline=[["away", 5]], again=True)
            add(f"{env}-crater-old-trees", base, trees=1500, nature="merciless", timeline=[["study", 3], ["away", 1], ["study", 1]])
        add(f"{env}-animated", base, frames=list(QUICK_FRAMES if quick else FRAMES), animations=True)
        if not quick:
            add(f"{env}-animated-storm", dict(base, weather="storm"), frames=list(FRAMES), animations=True)
            add(f"{env}-animated-fire", base, frames=list(FRAMES), animations=True, nature="wild", timeline=[["away", 4]])
            # the asteroid's strike, played on mount (web/events/asteroid.js), and the forest after it
            add(f"{env}-animated-strike", base, frames=[0, 1, 2, 4, 8, 16, 3600], animations=True,
                nature="merciless", timeline=[["study", 3], ["away", 1]])
    names = [s["name"] for s in out]
    assert len(set(names)) == len(names), "two scenes share a name"
    return out


def scenery_files() -> tuple:
    """The files a scene goes through (paths from this folder): a change to one runs --if-changed."""
    web = [f"web/{f}" for f in catalog.SCRIPTS]
    for kind in ("envs", "landscapes", "landmarks", "engines/pixel", "effects", "events"):
        folder = os.path.join(catalog.WEB, kind)
        web += [f"web/{kind}/{n}" for n in sorted(os.listdir(folder))] if os.path.isdir(folder) else []
    return tuple(web) + ("payload.py", "scene.py", "presets.py", "catalog.py", "events.py", "events_state.py",
                         "debug_events.py", "forest_data.py", "fake_forest.py", "milestones.py", "editions.json",
                         "e2e/scenery_check.py", "e2e/scenery_check.mjs")


def page(envs: list, swapping: bool = False) -> str:
    """The page every scene is mounted on: the forest's scripts and every shipped scenery's. One
    `swapping` has only the forest's own, and lets its name go, as the deck list does (forest.js):
    each scene's scenery files are loaded as a swap asks for them."""
    files = list(catalog.SCRIPTS)
    if not swapping:
        files += [f"envs/{e}.js" for e in envs if os.path.exists(os.path.join(catalog.WEB, "envs", e + ".js"))]
        for kind in ("landscapes", "landmarks"):  # (only what an edition ships: none of the drafts)
            files += [f"{kind}/{k}.js" for k in shipped(kind) if os.path.exists(os.path.join(catalog.WEB, kind, k + ".js"))]
    tags = "".join(f'<script src="file://{os.path.join(catalog.WEB, f)}"></script>' for f in files)
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0;background:#2c2c2c;color:#ddd}}</style>"
            f"{PREAMBLE}{tags}<script>{'window.__AF = window.AnkiForest; window.AnkiForest = undefined; ' if swapping else ''}"
            "window.__ready = true;</script>")


def check(cases: list, got: dict) -> list:
    """(scene, check, what went wrong) for everything that failed."""
    first, again = got["first"], got["again"]
    bad = []

    def fail(name, what, why):
        bad.append((name, what, why))

    for c in cases:
        name, r = c["name"], first.get(c["name"]) or {"errors": ["never drawn"]}
        if r.get("errors"):
            fail(name, "errors", r["errors"][0].splitlines()[0][:160])
        if r.get("opaque", 0) < MIN_OPAQUE or r.get("colours", 0) < MIN_COLOURS:
            fail(name, "painted", f"{100 * r.get('opaque', 0):.0f}% painted, {r.get('colours', 0)} colours")
        if c["again"] and name in again and again[name].get("hash") != r.get("hash"):
            fail(name, "same twice", "drew differently on a fresh page, after other scenes, with other random numbers")
        if c["data"].get("_resize") and not r.get("errors"):
            fresh = first.get(name.replace("-resized", f"-at-{c['data']['_resize']}px"), {}).get("hash")
            if r.get("resized") in (None, r.get("hash")):
                fail(name, "resizes", "made narrower, it was not drawn again")
            elif fresh and r["resized"] != fresh:
                fail(name, "resizes", "made narrower, it draws otherwise than a forest drawn at that width")
        swapped = got.get("swapped", {}).get(name)
        if swapped is not None:
            if swapped.get("errors"):
                fail(name, "swaps", swapped["errors"][0].splitlines()[0][:160])
            elif swapped.get("hash") != r.get("hash"):
                fail(name, "swaps", "swapped in after a settings change, it draws otherwise than on a fresh page")
        frames = r.get("frames")
        if frames is not None:
            if None in frames:
                fail(name, "animates", "a frame drew nothing")
            elif len(set(frames[:-1])) < 2 and frames[-1] == frames[-2]:
                fail(name, "animates", "nothing moved between its frames")
            elif len(frames) > 3 and frames[-1] == frames[-2]:
                fail(name, "animates", "nothing moves an hour on")
        zoom = r.get("zoom")
        if c.get("zoom") and not r.get("errors"):
            if not zoom:
                fail(name, "zooms", "it has no zoom button")
            elif zoom["in"] in (None, r.get("hash")):
                fail(name, "zooms", "zooming in changed nothing")
            elif zoom["out"] != r.get("hash"):
                fail(name, "zooms", "back out, the forest is not as it was")
            elif not zoom.get("picked"):
                fail(name, "zooms", "a click among the trees picked none")
    # the trees stand where they stood, whatever the hour and the weather
    groups: dict = {}
    for c in cases:
        if c["group"] and first.get(c["name"], {}).get("placed") is not None:
            groups.setdefault(c["group"], []).append(c["name"])
    for names in groups.values():
        ref = first[names[0]]["placed"]
        for name in names[1:]:
            if first[name]["placed"] != ref:
                fail(name, "trees stay put", f"its trees stand elsewhere than in {names[0]}")
    # what each change of sky or forest brings shows in the picture
    by = {c["name"]: first.get(c["name"], {}).get("hash") for c in cases}

    def differs(name, other, what):
        if name in by and other in by and by[name] and by[name] == by[other]:
            fail(name, "shows", f"looks just like {other}: {what} is not drawn")

    for c in cases:
        name = c["name"]
        env = name.split("-")[0]
        if "-in-" in name:
            differs(name, f"{env}-preset", "the weather")
        if "-at-" in name and "night" in (name.split("-at-")[1], own_preset(env).time):  # night against day, either way
            differs(name, f"{env}-preset", "the hour")
        if name.endswith("-trees-0"):
            differs(name, f"{env}-preset", "the forest")
        if name.endswith("-peaceful"):
            differs(name[:-len("-peaceful")], name, name[len(env) + 1:-len("-peaceful")])
    return bad


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--quick", action="store_true", help="a few scenes a scenery")
    args.add_argument("--only", help="comma-separated environments (default: every shipped one)")
    args.add_argument("--if-changed", action="store_true", help="only if a file a scene goes through changed (scenery_files)")
    opts = args.parse_args()
    if opts.if_changed:
        sys.path.insert(0, HERE)
        from phone_check import phone_changed
        if not phone_changed(scenery_files()):
            print("scenery check skipped: no scenery files changed")
            return 0
    envs = shipped()
    if opts.only:
        wanted = opts.only.split(",")
        unknown = set(wanted) - set(scene.ENVIRONMENTS)
        if unknown:
            sys.exit(f"no such environment: {', '.join(sorted(unknown))}")
        envs = list(wanted)
    start = time.monotonic()
    cases = scenes(envs, opts.quick)
    print(f"{len(cases)} scenes of {len(envs)} sceneries ({time.monotonic() - start:.1f}s to make up)", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        html, swap, data, out = (os.path.join(tmp, n) for n in ("page.html", "swap.html", "scenes.json", "out.json"))
        with open(html, "w", encoding="utf-8") as f:
            f.write(page(envs))
        with open(swap, "w", encoding="utf-8") as f:
            f.write(page(envs, swapping=True))
        with open(data, "w", encoding="utf-8") as f:
            json.dump([{k: c.get(k) for k in ("name", "data", "again", "frames", "zoom", "swap", "srcs")} for c in cases], f)
        run = subprocess.run(["node", os.path.join(HERE, "scenery_check.mjs"), html, swap, data, CHROME, out],
                             capture_output=True, text=True, cwd=ROOT, timeout=1800)
        if run.returncode or not os.path.exists(out):
            print(run.stdout + run.stderr)
            return 1
        with open(out, encoding="utf-8") as f:
            got = json.load(f)
    bad = check(cases, got)
    failed = [b for b in bad if (b[0], b[1]) not in KNOWN]
    expected = [b for b in bad if (b[0], b[1]) in KNOWN]
    for name, what, why in failed:
        print(f"FAIL {name:<36} {what}: {why}")
    for name, what, _why in expected:
        print(f"xfail {name:<35} {what}: {KNOWN[(name, what)]}")
    fixed = [k for k in KNOWN if k[0] in got["first"] and k not in {(b[0], b[1]) for b in bad}]
    for name, what in fixed:
        print(f"FIXED {name:<35} {what}: passes now; take it out of KNOWN")
    print(f"\n{len(cases) - len({b[0] for b in failed})}/{len(cases)} scenes passed every check"
          f" ({len(got['again'])} drawn twice, {len(got.get('swapped', {}))} swapped in) in {time.monotonic() - start:.0f}s")
    return 1 if failed or fixed else 0


if __name__ == "__main__":
    sys.exit(main())

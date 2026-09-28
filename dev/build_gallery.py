"""Build a single self-contained HTML gallery of every environment, weather and time, drawn from
dev/payload.js (run export_payload.py first).

    python anki_forest/dev/build_gallery.py [output.html]

All add-on JS/CSS is inlined, so the file opens anywhere (and can be published).
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), "web")
sys.path.insert(0, os.path.dirname(HERE))
import catalog
import presets as presets_mod
import scene

BIG_FOREST = 1000  # trees in the second run of presets
MAX_WIDTH = 1000


def env_scripts() -> list:
    """Every environment, landscape and landmark still installed."""
    out = []
    for kind in ("envs", "landscapes", "landmarks"):
        d = os.path.join(WEB, kind)
        if os.path.isdir(d):
            out += [os.path.join(kind, n) for n in sorted(os.listdir(d)) if n.endswith(".js")]
    return out

GALLERY = """
const P = window.PAYLOAD;
const list = document.getElementById('gallery');
for (const [group, items] of window.SCENE_LIST) {
  const h = document.createElement('h2'); h.className = 'group'; h.textContent = group; list.append(h);
  items.forEach(([title, cfg, mood, envName, extra]) => {
    const sec = document.createElement('section'); sec.className = 'item';
    sec.innerHTML = `<div class="head"><h3>${title}</h3><code>${cfg}</code></div>${extra && extra.note ? `<p class="note">${extra.note}</p>` : ''}<div class="af-panel"></div>`;
    list.append(sec);
    AnkiForest.mount(sec.querySelector('.af-panel'), Object.assign({}, P, {mood, environmentName: envName, journal: '', maxWidth: %MAXWIDTH%}, extra || {}));
  });
}
"""


def scene_list() -> list:
    import datetime as dt

    import fake_forest
    import forest_data
    now = dt.datetime(2026, 9, 19, 12)

    def item(title, extra=None, **cfg):
        cfg.setdefault("landscape", "meadow"); cfg.setdefault("landmark", "none")
        mood = scene.choose_mood(cfg, now)
        label = " · ".join(f"{k}: {v}" for k, v in cfg.items() if not (k in ("landscape", "landmark") and v in ("meadow", "none")))
        return [title, label, mood, scene.ENVIRONMENTS[mood["environment"]], extra or {}]

    def fake(n, **cfg):
        f = forest_data.merge_old(fake_forest.make(n))
        return item(f"{n} trees (test forest)", {"trees": f["trees"], "stats": f["stats"], "visitors": f["visitors"],
                                                 "merged": f.get("merged"), "forestSeed": f["forest_seed"], "testForest": True}, **cfg)

    # the catalogue the settings dialog offers: each preset on your forest, then on a big one
    shown = [p for p in presets_mod.FOREST_PRESETS if p.environment != presets_mod.DAILY]
    sheet = [item(p.label, {"note": p.note}, **p.values()) for p in shown]
    big = [fake(BIG_FOREST, **p.values()) for p in shown]
    for row, p in zip(big, shown):
        row[0] = f"{p.label} · {BIG_FOREST} trees"
    # each landmark on the landscape its JSON names as its best (a bridge wants water)
    marks = [item(spec["label"], environment="natural", weather="clear", time_of_day="dusk",
                  landscape=spec.get("landscape", "meadow"), landmark=key)
             for key, spec in catalog.entries("landmarks").items() if key != "none"]
    return [["Presets", sheet], ["Presets with a big forest", big], ["Landmarks", marks]]


PAGE = """<title>Memory Forest Preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@500&family=Karla:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#eef1ea;--ink:#1d2820;--muted:#57665b;--line:#d3dace;--accent:#3d6b4a;--fg-subtle:#6b776e}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121815;--ink:#e3eae0;--muted:#97a69a;--line:#29342d;--accent:#8fc39c;--fg-subtle:#97a69a}}
:root[data-theme="dark"]{--bg:#121815;--ink:#e3eae0;--muted:#97a69a;--line:#29342d;--accent:#8fc39c;--fg-subtle:#97a69a}
body{background:var(--bg);color:var(--ink);font:16px/1.55 Karla,system-ui,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding-inline:20px;padding-block:44px 72px}
.eyebrow{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.09em;text-transform:uppercase;color:var(--accent);margin:0 0 14px}
h1{font-family:"Pixelify Sans",Karla,sans-serif;font-weight:500;font-size:clamp(32px,4.6vw,48px);line-height:1.05;margin:0 0 14px}
.lede{max-width:68ch;color:var(--muted);margin:0}
.lede strong{color:var(--ink)}
h2.group{font:500 13px/1.3 "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:56px 0 0;padding-bottom:12px;border-bottom:1px solid var(--line)}
.item{margin-top:34px}
.head{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 16px;padding:0 12px}
.head h3{font-family:"Pixelify Sans",Karla,sans-serif;font-weight:500;font-size:24px;margin:0}
.head code{font:12px "IBM Plex Mono",monospace;color:var(--muted)}
.note{margin:4px 12px 0;color:var(--muted)}
.af-panel{margin-top:10px !important}
@media (max-width:520px){.wrap{padding-inline:16px}}
%CSS%
</style>
<div class="wrap">
  <p class="eyebrow">Memory Forest · preset review</p>
  <h1>Every preset, side by side</h1>
  <p class="lede">The add-on's own drawing code, running live. The first section draws each preset on <strong>your real review history</strong>: %TREES% trees from %CARDS% cards. The second draws the same presets on a made-up forest of 1000 trees, to check they hold up when the far treeline rises. Everything animates as it would in Anki. Hover over a tree to see its day.</p>
  <div id="gallery"></div>
</div>
<script>%PAYLOAD%</script>
<script>%JS%</script>
<script>window.SCENE_LIST = %SCENES%;</script>
<script>%GALLERY%</script>
"""


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "gallery.html")
    with open(os.path.join(HERE, "payload.js"), encoding="utf-8") as f:
        payload = f.read()
    js = "\n".join(open(os.path.join(WEB, s), encoding="utf-8").read() for s in list(catalog.SCRIPTS) + env_scripts())
    css = open(os.path.join(WEB, "forest.css"), encoding="utf-8").read()
    data = json.loads(re.match(r"window\.PAYLOAD = (.*);\s*$", payload, re.S).group(1))
    html = (PAGE.replace("%CSS%", css).replace("%TREES%", str(data["stats"]["trees"]))
            .replace("%CARDS%", f"{data['stats']['cards']:,}")
            .replace("%PAYLOAD%", payload.replace("</", "<\\/")).replace("%JS%", js).replace("%GALLERY%", GALLERY.replace("%MAXWIDTH%", str(MAX_WIDTH)))
            .replace("%SCENES%", json.dumps(scene_list())))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", out, f"({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()

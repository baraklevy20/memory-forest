"""The page dev/profile.mjs profiles: one animated forest, as the deck list draws it.

    python3 dev/profile_page.py aurora 730 > page.html
    python3 dev/profile_page.py aurora 730 weather=rain time_of_day=day > page.html  # the preset, otherwise

Unlike render_check's pages the clock is real and animations are on, so the forest runs its
frame loop exactly as it does in Anki.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from render_check import MAX_WIDTH, NOW, PANEL_PX, WEB, script_files

import fake_forest
import forest_data
import presets
import scene


def page(preset: str, n: int, overrides: dict | None = None) -> str:
    p = next((p for p in presets.FOREST_PRESETS if p.key == preset), None)
    if not p:
        sys.exit(f"no preset {preset}: one of {', '.join(p.key for p in presets.FOREST_PRESETS)}")
    cfg = dict(p.values(), **(overrides or {}))
    cfg.setdefault("landmark", "none")
    mood = scene.choose_mood(cfg, NOW)
    f = forest_data.merge_old(fake_forest.make(n))
    data = {"trees": f["trees"], "stats": f["stats"], "visitors": f["visitors"], "merged": f.get("merged"),
            "forestSeed": f["forest_seed"], "anniversaries": [0] if n > 2 else [], "events": [], "journal": "",
            "mood": mood, "environmentName": preset, "animations": True,
            "tooltips": True, "maxWidth": MAX_WIDTH, "testForest": True}
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0}}.af-panel{{width:{PANEL_PX}px}}</style>"
            "<div class='af-panel' id=p></div>"
            # one tag a file, each named, so a profile says which file a hot function is in
            + "".join(f"<script>{open(os.path.join(WEB, f), encoding='utf-8').read()}\n//# sourceURL=web/{f}</script>"
                      for f in script_files())
            + f"<script>window.D = {json.dumps(data)};</script>")


if __name__ == "__main__":
    sys.stdout.write(page(sys.argv[1] if len(sys.argv) > 1 else "aurora", int(sys.argv[2]) if len(sys.argv) > 2 else 730,
                          dict(a.split("=", 1) for a in sys.argv[3:])))

"""The page dev/profile.mjs profiles: one animated forest, as the deck list draws it.

    python3 dev/profile_page.py aurora 730 > page.html
    python3 dev/profile_page.py aurora 730 weather=rain time_of_day=day > page.html  # the preset, otherwise
    python3 dev/profile_page.py aurora 730 calendar=off > page.html  # without the study calendar under it
    python3 dev/profile_page.py --shipped  # the presets some edition ships, as JSON (dev/perf_check.mjs)

Unlike render_check's pages the clock is real and animations are on, so the forest runs its
frame loop exactly as it does in Anki. The study calendar is under it, as it is unless switched
off (calendar=off; calendar=by_year for the other view), with a day's reviews for each of the
forest's days and cards due ahead.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from render_check import MAX_WIDTH, NOW, PANEL_PX, WEB, script_files

import fake_forest
import forest_data
import milestones
import presets
import scene

CAL_AHEAD = 30  # days of cards due shown ahead (payload.CALENDAR_DUE_DAYS)


def calendar(f: dict, n: int, view: str) -> dict:
    """A made-up study calendar for the forest `f`: one studied day for each of its `n` days, but
    for every ninth, some days busier than others, and cards due ahead."""
    days = [0 if i % 9 == 4 else 20 + (i * 37) % 300 for i in range(n)]
    reviews = {n - 1 - i: r for i, r in enumerate(days)}
    return {"view": view, "weekStart": 1, "start": (dt.date.today() - dt.timedelta(days=n - 1)).isoformat(),
            "days": days, "due": [60] + [max(0, 250 - 8 * i) for i in range(1, CAL_AHEAD)],
            "animals": milestones.animal_days(f["visitors"], f["trees"], reviews, 0, True),
            "breakDays": forest_data.BREAK_DAYS, "forestStart": None, "streakFromStart": False, "marks": [], "browse": False}


def page(preset: str, n: int, overrides: dict | None = None) -> str:
    p = next((p for p in presets.FOREST_PRESETS if p.key == preset), None)
    if not p:
        sys.exit(f"no preset {preset}: one of {', '.join(p.key for p in presets.FOREST_PRESETS)}")
    overrides = dict(overrides or {})
    view = overrides.pop("calendar", "timeline")
    cfg = dict(p.values(), **overrides)
    cfg.setdefault("landmark", "none")
    mood = scene.choose_mood(cfg, NOW)
    f = forest_data.merge_old(fake_forest.make(n))
    data = {"trees": f["trees"], "stats": f["stats"], "visitors": f["visitors"], "merged": f.get("merged"),
            "forestSeed": f["forest_seed"], "anniversaries": [0] if n > 2 else [], "events": [], "journal": "",
            "mood": mood, "environmentName": preset, "animations": True,
            "tooltips": True, "maxWidth": MAX_WIDTH, "testForest": True, "inAnki": True}
    if view != "off":
        data["calendar"] = calendar(f, max(n, 1), view)
    return (f"<!doctype html><meta charset=utf-8><style>body{{margin:0}}.af-panel{{width:{PANEL_PX}px}}</style>"
            "<div class='af-panel' id=p></div>"
            # one tag a file, each named, so a profile says which file a hot function is in
            + "".join(f"<script>{open(os.path.join(WEB, f), encoding='utf-8').read()}\n//# sourceURL=web/{f}</script>"
                      for f in script_files())
            + f"<script>window.D = {json.dumps(data)};</script>")


def shipped() -> list:
    """The presets some edition ships, in the picker's order (every one, where there are no
    editions: the public repo is one edition), but Surprise me daily, which is one of the others."""
    import editions
    keys = None
    if editions.available():
        keys = set()
        for name in editions.available():
            keys |= editions.scenery(name)["presets"]
    return [p.key for p in presets.FOREST_PRESETS if p.key != presets.DAILY and (keys is None or p.key in keys)]


if __name__ == "__main__":
    if sys.argv[1:] == ["--shipped"]:
        sys.exit(print(json.dumps(shipped())))
    sys.stdout.write(page(sys.argv[1] if len(sys.argv) > 1 else "aurora", int(sys.argv[2]) if len(sys.argv) > 2 else 730,
                          dict(a.split("=", 1) for a in sys.argv[3:])))

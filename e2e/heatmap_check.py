"""The study heatmap's hover layer (its animals, trophies and goal: calendar.js paint, the layer
shown while the pointer is on the heatmap) sits on its own year's weeks: in By year, with the
earlier years shown above the year in view, and again once they are hidden. Run: python3
e2e/heatmap_check.py; `npm test` runs it with --if-changed: only when the heatmap's files changed.

It builds a desktop heatmap from this copy's scripts (catalog.SCRIPTS) with a made-up history of a
few years, opens it in headless Chrome (e2e/heatmap_check.mjs) and compares each year's weeks with
its layer: same place, same size. Needs Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from phone_check import CHROME, forest_page, phone_changed

import catalog

YEARS = 3  # (of made-up history: two earlier years for Streak view to show)
# the files the heatmap's layers go through: a change to one runs this
HEATMAP_FILES = ("web/calendar.js", "web/hover.js", "web/core.js", "web/engines/pixel/ground.js", "web/visit.js", "web/forest.css", "web/util.js", "payload.py", "e2e/heatmap_check.py", "e2e/heatmap_check.mjs")


def calendar() -> dict:
    """YEARS years of days, most studied, a streak of about two years running to today, so each year
    has its animals' and the streak's marks, and Streak view opens on all three; By year."""
    today = dt.date.today()
    n = YEARS * 366
    days = [0 if (i % 11 == 3 and i < n - 700) else 15 + (i * 37) % 200 for i in range(n)]
    return {"view": "by_year", "weekStart": 1, "start": (today - dt.timedelta(days=n - 1)).isoformat(), "days": days,
            "due": [40] + [max(0, 200 - 2 * i) for i in range(1, 120)], "animals": [], "browse": False,
            "answerTime": [1 + i % 12 if count else None for i, count in enumerate(days)],
            "time": [], "shadeBy": "reviews", "marks": [], "width": 85}


def page(show_forest=False, deep=False) -> str:
    data = dict(forest_page(), calendar=calendar(), showForest=show_forest, inAnki=True, maxWidth=820, animations=False)
    behind = []
    if deep:
        import fake_forest
        import forest_data
        forest = fake_forest.make(5000)
        data.update(forest_data.merge_old(forest))
        behind = forest["trees"][:-len(data["trees"])]
        ages = {t["ago"]: t["n"] for t in forest["trees"]}
        oldest = max(ages)
        data["calendar"].update(days=[ages.get(ago, 0) * 4 for ago in range(oldest, -1, -1)], planted=[[ago, n] for ago, n in ages.items()])
        data.update(zoom=True, channel='test')
    if show_forest and data["trees"]:
        # Saved trees keep their original dates and ages; date the calendar to the same day.
        tree = data["trees"][-1]
        today = dt.date.fromisoformat(tree["date"]) + dt.timedelta(days=tree["ago"])
        data["calendar"]["start"] = (today - dt.timedelta(days=len(data["calendar"]["days"]) - 1)).isoformat()
        data["calendar"]["browse"] = True  # (a stretch picked opens in the browser)
    with open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8") as f:
        css = f.read()
    tags = "".join(f'<script src="file://{os.path.join(catalog.WEB, s)}"></script>' for s in catalog.SCRIPTS)
    return f"""<!doctype html><meta charset="utf-8"><style>body {{ margin: 0; padding: 20px; background: #2c2c2c; color: #ddd }}
{css}</style><div class="af-panel" id="p"></div><script>window.pycmd = () => false;</script>{tags}
<script>window.TEST_BEHIND = {json.dumps(behind)};
window.pycmd = (msg, cb) => {{ if (msg.includes(':deep:') && cb) cb(window.TEST_BEHIND); }};
AnkiForest.mount(document.getElementById('p'), {json.dumps(data)});</script>"""


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--if-changed", action="store_true", help="only if the heatmap's files changed (HEATMAP_FILES)")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed(HEATMAP_FILES):
        print("heatmap check skipped: no heatmap files changed")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "heatmap.html")
        with open(html, "w", encoding="utf-8") as f:
            f.write(page())
        forest = os.path.join(tmp, "forest.html")
        with open(forest, "w", encoding="utf-8") as f:
            f.write(page(True))
        deep = os.path.join(tmp, "deep.html")
        with open(deep, "w", encoding="utf-8") as f:
            f.write(page(True, True))
        run = subprocess.run(["node", os.path.join(HERE, "heatmap_check.mjs"), html, CHROME, forest, deep],
                             capture_output=True, text=True, cwd=ROOT, timeout=300)
    if not run.stdout.strip().startswith("{"):
        print(run.stdout + run.stderr)
        return 1
    got = json.loads(run.stdout)
    failed = 0
    for state, years in got["states"].items():
        if not years:
            print(f"FAIL {state}: no years drawn")
            failed += 1
        for y in years:
            if y["off"]:
                failed += 1
                print(f"FAIL {state}, {y['name']}: its hover layer is {y['off']} from its weeks")
        if all(not y["off"] for y in years) and years:
            print(f"ok   {state}: {len(years)} row(s) of weeks, each layer on its own")
    for e in got.get("errors", []):
        print("FAIL page error:", e)
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

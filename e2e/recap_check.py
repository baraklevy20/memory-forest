"""The year's recap in a real page (web/recap.js): its card on the forest, the dialog opened, every card
reached with the keys pressed in the page (→ and Space on, ← back, Esc out), Skip to summary, the
summary's picture sent to Anki as a 1080 x 1350 PNG, and the link left in the caption; a short year
going straight from its title to its summary. Run: python3 e2e/recap_check.py [--shots DIR] (pictures of
each card, in both themes, for looking at); `npm test` runs it with --if-changed.

The pages are the deck list's panel with this copy's scripts (catalog.SCRIPTS) and the made-up forest of
e2e/phone_check.forest_page, the recap's numbers worked out by recap.numbers from a made-up year."""

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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import importlib

import fake_anki  # (the add-on as a package: heatmap_look's imports are relative)
from page_check import desk
from phone_check import CHROME, forest_page, phone_changed

recap = importlib.import_module(fake_anki.PACKAGE + ".recap")
heatmap_look = importlib.import_module(fake_anki.PACKAGE + ".heatmap_look")
RECAP_FILES = ("web/recap.js", "recap.py", "web/news.js", "web/visitors.js", "web/calendar/draw.js", "e2e/recap_check.py", "e2e/recap_check.mjs")
END = dt.date(2026, 12, 31)


def heavy_days() -> dict:
    """A made-up year: a few January days, away until May, then every day but a few."""
    out = {}
    for i in range(365):
        d = dt.date(2026, 1, 1) + dt.timedelta(days=i)
        if (d.month == 1 and d.day < 12) or (d >= dt.date(2026, 5, 12) and i % 41 != 3):
            out[d] = 40 + (i * 37) % 260
    return out


def light_days() -> dict:
    return {dt.date(2026, 11, 24) + dt.timedelta(days=i): 30 + i for i in (0, 1, 2, 3, 9, 20)}


def recap_data(reviews: dict, trees: list, animals: list, mood: dict, finished: list = ()) -> dict:
    """data.recap as payload.py sends it (recap.for_page), worked out from `reviews` {date: n}."""
    seconds = {d: n * 9 for d, n in reviews.items()}
    out = recap.numbers(2026, reviews, seconds, trees, set(), END, animals)
    names = {"rabbit": "A rabbit", "deer": "A deer", "fox": "A fox", "heron": "A heron"}
    out["animals"] = [dict(a, name=names.get(a["key"], a["key"]), came="") for a in out["animals"]]
    start = dt.date(2026, 1, 1)
    cal = {"view": "by_year", "shadeBy": "reviews", "weekStart": 1, "start": start.isoformat(),
           "days": [reviews.get(start + dt.timedelta(days=i), 0) for i in range(365)], "due": [], "planted": [], "animals": [],
           "ponds": [], "marks": [], "gone": [], "browse": False, "free": [], "daysOff": [],
           "look": heatmap_look.page_look({}, mood), "size": {"width": "forest", "fill": "more"}}
    # the decks learned to their last card (recap.finished), made up
    out["finished"] = [{"name": n.split("::")[-1], "full": n, "date": d} for n, d in finished]
    return dict(out, calendar=cal, entry="card")


def data(light: bool) -> dict:
    page = forest_page(120)
    reviews = light_days() if light else heavy_days()
    trees = [{"date": d.isoformat(), "n": 5} for d in sorted(reviews)][:120]
    animals = [] if light else [("rabbit", dt.date(2026, 6, 3)), ("fox", dt.date(2026, 8, 1)), ("heron", dt.date(2026, 9, 9))]
    vis = [{"key": k, "name": k} for k in ("rabbit", "fox", "heron", "deer")]
    finished = [] if light else [("Languages::German A1", "2026-04-12"), ("Kanji N5", "2026-09-30")]
    return dict(page, visitors=vis, recap=recap_data(reviews, trees, animals, page["mood"], finished), inAnki=True, channel="forest",
                maxWidth=820, animations=True, showForest=True)


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--if-changed", action="store_true", help="only if the recap's files changed")
    args.add_argument("--shots", help="a folder for pictures of each card")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed(RECAP_FILES):
        print("recap check skipped: no recap files changed")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        files = {}
        # (and two pages for its way in: the heatmap alone, the forest switched off, and a note of what's new waiting)
        for name, light, bg in (("heavy", False, "#2c2c2c"), ("light", True, "#2c2c2c"), ("heavy_day", False, "#f5f5f5"),
                                ("heatmap_only", False, "#2c2c2c"), ("with_news", False, "#2c2c2c")):
            files[name] = os.path.join(tmp, name + ".html")
            fg = "#fcfcfc" if bg == "#2c2c2c" else "#020202"
            page = data(light)
            if name == "heatmap_only":
                page = dict(page, showForest=False, calendar=dict(page["recap"]["calendar"], view="timeline"))
            if name == "with_news":
                page = dict(page, news={"id": "x", "title": "Something new", "text": "A note.", "action": ""})
            html = desk(page, bg).replace("<style>", f"<style>body {{ --canvas: {bg}; --fg: {fg}; --fg-subtle: #8a8a8a; }} ", 1)
            with open(files[name], "w", encoding="utf-8") as f:
                f.write(html)
        manifest = os.path.join(tmp, "pages.json")
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump({"pages": files, "shots": opts.shots or ""}, f)
        run = subprocess.run(["node", os.path.join(HERE, "recap_check.mjs"), manifest, CHROME], capture_output=True, text=True, cwd=ROOT, timeout=600)
    print(run.stdout + run.stderr)
    return 0 if run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

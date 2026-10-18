"""The panel's behaviour in a real page: the study heatmap's views, paging, tooltips, shades, marks
and clicks, the caption, what's new, the scene runner's loop, and the phone card's full screen and
its lines. Run: python3 e2e/page_check.py (npm run test:page); `npm test` runs it with --if-changed:
only when the page's files changed (PAGE_FILES).

It builds pages from this copy's scripts (catalog.SCRIPTS, the phone's bundle) with made-up data (a
calendar of its own, the fake forest of e2e/phone_check.forest_page), opens them one at a time in
one headless Chrome (e2e/page_check.mjs) and runs each check on them: a check fails on what it
looks for, and on any console error or uncaught exception on its page (but those it causes on
purpose). A check marked as a known bug (`bug` in page_check.mjs) fails as expected until it is
fixed. Needs Chrome, and node with the dev packages (npm install)."""

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
import phone_check
from phone_check import CHROME, SIM, forest_page, phone_changed

import catalog

TODAY = dt.date(2026, 10, 18)  # (the fake forest's today: its trees and the calendar's days agree)
FIRST = dt.date(2023, 3, 15)  # the made-up history's first day
# the files the page's behaviour goes through: a change to one runs this
PAGE_FILES = ("web/calendar.js", "web/caption.js", "web/core.js", "web/hover.js", "web/news.js", "web/phone.js",
              "web/tooltips.js", "web/util.js", "web/forest.css", "phone.py", "phone_data.py",
              "e2e/page_check.py", "e2e/page_check.mjs", "e2e/phone_check.py")


def ago_of(day: dt.date) -> int:
    return (TODAY - day).days


def reviews(ago: int) -> int:
    """The made-up history, by days ago: a 43-day streak to today (a day with nothing due 10 days ago,
    a day off 20 days ago, missed 45 days ago), short runs before it, a pond in August, and a 60-day
    streak in the summer of 2025 (its trophy the longest's, so the goal is to beat it)."""
    n = 15 + (ago * 37) % 200
    if ago in (10, 20, 45) or ago_of(dt.date(2026, 8, 5)) <= ago <= ago_of(dt.date(2026, 8, 1)):
        return 0
    if ago <= 44:
        return n
    if 46 <= ago <= 120:
        return 0 if ago % 7 == 3 else n
    if 400 <= ago <= 459:
        return n
    if ago in (399, 460):
        return 0
    return 0 if ago % (11 if ago < 400 else 9) == 4 else n


def calendar(first: dt.date = FIRST, **more) -> dict:
    """data.calendar as payload.py sends it, for the made-up history from `first` to TODAY."""
    span = ago_of(first)
    days = [reviews(a) for a in range(span, -1, -1)]
    cal = {"view": "timeline", "weekStart": 1, "start": first.isoformat(), "days": days,
           "due": [12] + [max(0, 200 - 2 * i) for i in range(1, 121)],
           "animals": [{"key": "deer", "ago": 30, "label": "a deer", "why": "you studied 14 days in a row"}],
           "browse": True, "shadeBy": "reviews", "width": 85,
           "time": [n * 8 if n else 0 for n in days],
           "answerTime": [round(2 + (i % 30) / 10, 1) if n else None for i, n in enumerate(days)],
           "ponds": [["2026-08-01", "2026-08-05"]], "free": [[10, 10]], "daysOff": [20],
           "gone": [[3, 2, 5], [5, 4, 4]],
           "marks": [{"day": "2026-10-25", "icon": "exam", "name": "Final exam"}, {"day": "2026-10-12", "icon": "star", "name": ""}],
           "planted": [], "forestStart": None, "streakFromStart": False}
    cal.update(more)
    return cal


# a spy on the page's listeners, before any script: how many 'visibilitychange' listeners the
# document holds (a remount must let go of the forest before), and every message sent to Anki
SPY = """<script>window.__sent = []; window.pycmd = (msg, cb) => { window.__sent.push(msg); };
window.__vis = 0;
const _add = document.addEventListener.bind(document), _rm = document.removeEventListener.bind(document);
document.addEventListener = (t, f, o) => { if (t === 'visibilitychange') window.__vis++; return _add(t, f, o); };
document.removeEventListener = (t, f, o) => { if (t === 'visibilitychange') window.__vis--; return _rm(t, f, o); };</script>"""


def desk(data: dict, bg: str = "#2c2c2c") -> str:
    """The deck list's panel with `data`, its scripts one by one from web/ (catalog.SCRIPTS), on a
    page of colour `bg` (Anki's dark one by default)."""
    with open(os.path.join(catalog.WEB, "forest.css"), encoding="utf-8") as f:
        css = f.read()
    tags = "".join(f'<script src="file://{os.path.join(catalog.WEB, s)}"></script>' for s in catalog.SCRIPTS)
    return f"""<!doctype html><meta charset="utf-8"><style>body {{ margin: 0; padding: 20px; background: {bg}; color: #ddd; font-family: sans-serif }}
{css}</style>{SPY}<div class="af-panel" id="p"></div>{tags}
<script>window.TEST_DATA = {json.dumps(data)};
AnkiForest.mount(document.getElementById('p'), JSON.parse(JSON.stringify(window.TEST_DATA)));</script>"""


def calendar_only(**more) -> dict:
    """The heatmap alone (the forest switched off on this screen), in Anki."""
    return dict(forest_page(), calendar=calendar(**more), showForest=False, inAnki=True, maxWidth=820, channel="forest")


def with_forest(animations: bool) -> dict:
    """The fake forest and the heatmap under it, in Anki, with what's new to show."""
    return dict(forest_page(), calendar=calendar(), showForest=True, inAnki=True, maxWidth=820, channel="forest",
                animations=animations, newDot="scenery",
                news={"id": "heatmap2", "title": "A new heatmap", "text": "Try the new heatmap.", "action": "Show me"})


def phone_note(**more) -> dict:
    note = phone_check.note()
    note.update(more)
    return note


# the full screen refused, as an app's web view may
DENIED_STUB = phone_check.FULLSCREEN_STUB.replace(
    "Element.prototype.requestFullscreen = function () {",
    "Element.prototype.requestFullscreen = function () { return Promise.reject(new Error('denied'));")


def pages() -> dict:
    """name -> the page's HTML"""
    web = catalog.WEB
    synced_long_ago = (dt.datetime.now() - dt.timedelta(days=3)).isoformat(timespec="minutes")
    return {
        "calendar": desk(calendar_only()),
        "fresh": desk(calendar_only(days=calendar()["days"][:-1] + [0], due=[40] + calendar()["due"][1:])),
        "sunday": desk(calendar_only(weekStart=0)),
        "old": desk(calendar_only(first=dt.date(2011, 6, 1), view="by_year")),
        "light": desk(calendar_only(), bg="#f5f5f5"),
        "forest": desk(with_forest(False)),
        "live": desk(with_forest(True)),
        "phone": phone_check.page(web),
        "phone-stale": phone_check.page(web, phone_note(updated=synced_long_ago)),
        "phone-denied": phone_check.page(web, stub=DENIED_STUB),
        "phone-empty": phone_check.page(web, {"days": []}),
    }


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--if-changed", action="store_true", help="only if the page's files changed (PAGE_FILES)")
    args.add_argument("--only", help="run only the checks whose names hold this text")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed(PAGE_FILES):
        print("page check skipped: no page files changed")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        files = {}
        for name, html in pages().items():
            files[name] = os.path.join(tmp, name + ".html")
            with open(files[name], "w", encoding="utf-8") as f:
                f.write(html)
        manifest = os.path.join(tmp, "pages.json")
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump({"pages": files, "sim": SIM, "only": opts.only or ""}, f)
        run = subprocess.run(["node", os.path.join(HERE, "page_check.mjs"), manifest, CHROME],
                             capture_output=True, text=True, cwd=ROOT, timeout=600)
    if not run.stdout.strip().startswith("{"):
        print(run.stdout + run.stderr)
        return 1
    got = json.loads(run.stdout)
    failed = 0
    for check in got["checks"]:
        name, fails, bug = check["name"], check["failures"], check.get("bug")
        if bug:
            print(f"{'xfail' if fails else 'XPASS'} {name} (known bug: {bug})" + (f": {fails[0]}" if fails else ", fixed? drop its `bug`"))
            continue
        if fails:
            failed += 1
            print(f"FAIL {name}")
            for f in fails[:6]:
                print(f"     {f}")
        else:
            print(f"ok   {name}")
    for e in got.get("errors", []):
        print("FAIL", e)
        failed += 1
    print(f"{len(got['checks'])} checks, {failed} failed, in {got.get('seconds', 0):.0f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

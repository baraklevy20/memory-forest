"""Taps on the phone card land where the finger is: the forest's trees and the study calendar's
days answer a tap with their own tooltip, upright or turned sideways (the full screen), and on a
page the app zooms (AnkiDroid's card zoom). Run: python3 dev/phone_check.py (npm run test:phone);
`npm test` runs it with --if-changed: only when the phone's files changed (PHONE_FILES), uncommitted
or in the last commit.

It builds the phone card from this copy's files (phone_data.bundle, phone.CSS) with a made-up
forest and calendar, opens it in headless Chrome (dev/phone_check.mjs) as a phone, and taps the
same trees and days in each set-up: each tooltip must be the one an upright, unzoomed card
shows. Needs Chrome, and node with the dev packages (npm install)."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import catalog
import phone_data

CHROME = os.environ.get("CHROME") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIM = "af-fs-sim"  # headless Chrome has no full screen: a class stands in for :fullscreen
CAL_DAYS, CAL_AHEAD = 240, 120
# the files a phone card's taps go through (paths from this folder): a change to one runs this
PHONE_FILES = ("phone.py", "phone_data.py", "phone_note.py", "web/phone.js", "web/calendar.js", "web/hover.js",
               "web/util.js", "web/forest.css", "dev/phone_check.py", "dev/phone_check.mjs")  # the made-up calendar: days of history, days ahead
# the browser's full screen, stubbed: the phone card's own full-screen code runs as on a phone
FULLSCREEN_STUB = """<script>
Object.defineProperty(document, 'fullscreenEnabled', { value: true });
window.__fs = null;
Object.defineProperty(document, 'fullscreenElement', { get() { return window.__fs; } });
Element.prototype.requestFullscreen = function () { window.__fs = this; this.classList.add('%(sim)s');
  document.dispatchEvent(new Event('fullscreenchange')); return Promise.resolve(); };
document.exitFullscreen = function () { if (window.__fs) window.__fs.classList.remove('%(sim)s'); window.__fs = null;
  document.dispatchEvent(new Event('fullscreenchange')); return Promise.resolve(); };
</script>""".replace("%(sim)s", SIM)


def card_css() -> str:
    tree = ast.parse(open(os.path.join(ROOT, "phone.py"), encoding="utf-8").read())
    return next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CSS")


def note() -> dict:
    """The note's data: the dev payload's forest, still (so the animals stay put), and a calendar
    of CAL_DAYS days studied most days, with cards due ahead."""
    raw = open(os.path.join(HERE, "payload.js"), encoding="utf-8").read()
    page = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
    today = dt.date.today()
    days = [0 if i % 9 == 4 else 20 + (i * 37) % 300 for i in range(CAL_DAYS)]
    cal = {"view": "timeline", "weekStart": 1, "start": (today - dt.timedelta(days=CAL_DAYS - 1)).isoformat(),
           "days": days, "due": [60] + [max(0, 250 - 2 * i) for i in range(1, CAL_AHEAD)], "animals": [],
           "breakDays": 7, "browse": False}
    return dict(page, calendar=cal, inAnki=False, tooltips=True, zoom=False, animations=False, maxWidth=1200,
                updated=dt.datetime.now().isoformat(timespec="minutes"), parts={}, script="x",
                days=[{"date": today.isoformat(), "mood": page["mood"], "dayNumber": page.get("dayNumber", 1)}],
                sun={"rise": "06:30", "set": "18:30", "twilight": 30})


def page(web: str) -> str:
    """The phone card as AnkiDroid shows it (a transparent page on the app's white), its scripts
    from `web`."""
    bundle = phone_data.bundle(web=web).replace(":fullscreen", "." + SIM)
    css = card_css().replace(":fullscreen", "." + SIM)
    data = json.dumps(note()).replace("</", "<\\/")
    script = bundle.replace("</script", "<\\/script")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body {{ margin: 0; background: transparent; font-family: sans-serif }}
.{SIM} {{ position: fixed !important; left: 0; top: 0; width: 100vw; height: 100vh; z-index: 9 }}
{css}</style>{FULLSCREEN_STUB}</head>
<body class="card card1"><div id="content"><div id="qa">
<div id="memory-forest-phone" class="af-panel"></div>
<script type="application/json" id="memory-forest-phone-data">{data}</script>
<script data-root="memory-forest-phone">{script}</script>
</div></div></body></html>"""


def phone_changed() -> bool:
    """Whether any of PHONE_FILES has changed: in the working tree or the index (untracked too),
    or, with nothing uncommitted, in the last commit (as CI sees a push)."""
    def names(*cmd):
        run = subprocess.run(["git", *cmd], capture_output=True, text=True, cwd=ROOT)
        return {line[3:] if cmd[0] == "status" else line for line in run.stdout.splitlines()}
    changed = names("status", "--porcelain", "--untracked-files=all", "--", ".")
    if not changed:
        changed = names("diff", "--name-only", "--relative", "HEAD~1", "HEAD")
    here = os.path.relpath(ROOT, subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                                                 cwd=ROOT).stdout.strip())
    strip = lambda p: p[len(here) + 1:] if here != "." and p.startswith(here + "/") else p  # noqa: E731
    return any(strip(p.strip('"')) in PHONE_FILES for p in changed)


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--web", default=catalog.WEB, help="the scripts to test (default: this copy's web/)")
    args.add_argument("--if-changed", action="store_true", help="only if the phone's files changed (PHONE_FILES)")
    opts = args.parse_args()
    if opts.if_changed and not phone_changed():
        print("phone check skipped: no phone files changed")
        return 0
    web = opts.web
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "card.html")
        with open(html, "w", encoding="utf-8") as f:
            f.write(page(web))
        run = subprocess.run(["node", os.path.join(HERE, "phone_check.mjs"), html, CHROME],
                             capture_output=True, text=True, cwd=ROOT, timeout=300)
    if run.returncode != 0 and not run.stdout.strip().startswith("{"):
        print(run.stdout + run.stderr)
        return 1
    got = json.loads(run.stdout)
    failed = 0
    for target in ("forest", "calendar"):
        base = got[target]["upright"]
        answered = sum(1 for tip in base.values() if tip)
        if answered < 3:
            print(f"FAIL {target}: only {answered} of its taps answered upright, unzoomed: nothing to compare")
            failed += 1
            continue
        for setup, taps in got[target].items():
            wrong = {k: (base[k], tip) for k, tip in taps.items() if k in base and tip != base[k]}
            if wrong:
                failed += 1
                print(f"FAIL {target}, {setup}: {len(wrong)} of {len(taps)} taps answered otherwise")
                for k, (want, tip) in list(wrong.items())[:3]:
                    print(f"     at {k}: wanted {want or '(nothing)'!r}, got {tip or '(nothing)'!r}")
            else:
                print(f"ok   {target}, {setup}: {len(taps)} taps, {sum(1 for t in taps.values() if t)} with a tooltip")
    for e in got.get("errors", []):
        print("FAIL page error:", e)
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Open an old Anki version on a throwaway profile, with this add-on in it, to check it still works there.

    python3 dev/old_anki.py                           # /Applications/Anki 2.app
    python3 dev/old_anki.py "/Applications/Anki 2.1.55.app"
    python3 dev/old_anki.py --keep                    # reuse the last throwaway profile
    python3 dev/old_anki.py --check                   # check it by itself, then quit

It copies this folder (without your meta.json, user_files or caches) into a fresh base
folder under the temp dir and starts that Anki with -b, so your own collection and your
dev config are never touched. The new profile has no study history: turn on test_forest
in the add-on's config there to see a forest.

--check needs no hands: the profile starts in English and the dark theme, with no update
check, and dev/old_anki_check.py goes in beside the add-on. Once the profile is open it
turns the test forest on, measures the cog in the deck list, opens the settings, each of
their tabs and the scenery picker, and quits; this prints what went wrong, if anything,
and exits 1 then. Anki runs one copy per user, so the check runs under a user name of its
own and leaves an Anki you have open alone.
"""

from __future__ import annotations

import json
import os
import pickle
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
APP = "/Applications/Anki 2.app"
BASE = os.path.join(tempfile.gettempdir(), "memory-forest-try-anki")
SKIP = shutil.ignore_patterns("meta.json", "user_files", "__pycache__", "node_modules", "*.ankiaddon", ".*")
CHECK_ADDON = "memory_forest_check"
CHECK_TIMEOUT_SECS = 120
DARK = 2  # aqt.theme.Theme.DARK: where 2.1.50's own button styles squeezed the cog
# Anki's one-copy-per-user key comes from the user name (getpass, from these variables): a
# name of its own lets the check run beside the Anki you have open
CHECK_USER = "memory-forest-check"


def no_first_run(base: str) -> None:
    """The global settings Anki would ask for on its very first run (the language, in a
    dialog that waits for a click), so the profile opens by itself: with none in it, Anki
    makes "User 1" and opens that."""
    meta = {"ver": 0, "updates": False, "created": int(time.time()), "id": random.randrange(0, 2**63), "lastMsg": -1,
            "suppressUpdate": True, "firstRun": True, "defaultLang": "en_US", "theme": DARK}
    db = sqlite3.connect(os.path.join(base, "prefs21.db"))
    db.execute("create table if not exists profiles (name text primary key, data blob not null)")
    db.execute("insert or replace into profiles values ('_global', ?)", (pickle.dumps(meta, protocol=4),))
    db.commit()
    db.close()


def progress() -> str:
    """dev/old_anki_check.py's log of how far it got."""
    path = os.path.join(BASE, "check.log")
    return ("check.log:\n" + open(path, encoding="utf-8").read()) if os.path.exists(path) else "(no check.log: the check add-on never loaded)\n"


def check(binary: str) -> None:
    os.makedirs(BASE, exist_ok=True)
    no_first_run(BASE)
    dest = os.path.join(BASE, "addons21", CHECK_ADDON)
    os.makedirs(dest, exist_ok=True)
    shutil.copy(os.path.join(HERE, "old_anki_check.py"), os.path.join(dest, "__init__.py"))
    out = os.path.join(BASE, "check.json")
    if os.path.exists(out):
        os.remove(out)
    env = dict(os.environ, MEMORY_FOREST_FOLDER=os.path.basename(ADDON), USER=CHECK_USER, LOGNAME=CHECK_USER)
    try:
        run = subprocess.run([binary, "-b", BASE, "-l", "en"], env=env, capture_output=True, text=True,
                             timeout=CHECK_TIMEOUT_SECS)
        log = run.stdout + run.stderr
    except subprocess.TimeoutExpired as e:
        log = (e.stdout or b"").decode() + (e.stderr or b"").decode()
        sys.exit(f"Anki did not finish within {CHECK_TIMEOUT_SECS} s (a dialog waiting for a click?)\n{progress()}{log[-2000:]}")
    if "Already running" in log:
        sys.exit("another check's Anki is still open: close it and run this again")
    if not os.path.exists(out):
        sys.exit(f"the check never reported back\n{progress()}{log[-3000:]}")
    with open(out, encoding="utf-8") as f:
        r = json.load(f)
    print(f"Anki {r.get('anki')}: " + ", ".join(r["steps"]))
    js = [line for line in log.splitlines() if "JS" in line or "error" in line.lower()]
    if js:
        print("Anki's console:\n  " + "\n  ".join(js[-20:]))
    if r.get("deck_list"):
        print("deck list: " + json.dumps(r["deck_list"]))
    for line in r.get("console", []):
        print("console: " + line)
    for problem in r["problems"]:
        print("PROBLEM " + problem)
    for error in r["errors"]:
        print("ERROR " + error)
    if r["problems"] or r["errors"]:
        sys.exit(1)
    print("ok")


def main() -> None:
    args = sys.argv[1:]
    keep, checking = "--keep" in args, "--check" in args
    args = [a for a in args if a not in ("--keep", "--check")]
    app = args[0] if args else APP
    binary = os.path.join(app, "Contents", "MacOS", "anki")
    if not os.path.exists(binary):
        sys.exit(f"no Anki at {app}")
    if (checking or not keep) and os.path.exists(BASE):
        shutil.rmtree(BASE)
    dest = os.path.join(BASE, "addons21", os.path.basename(ADDON))
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(ADDON, dest, ignore=SKIP)
    print(f"{app} on {BASE}")
    if checking:
        check(binary)
    else:
        subprocess.run([binary, "-b", BASE])


if __name__ == "__main__":
    main()

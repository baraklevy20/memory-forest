# Copied from addon_libs/anki_builds.py by addon_libs/sync.py: edit it there, not here.
"""Real Ankis to check an add-on in: downloaded from Anki's GitHub releases the first time and kept in CACHE, so no
add-on downloads one twice. The Qt5 builds (every Anki before 2.1.50, and the builds for older computers after it) are
Intel-only and run under Rosetta: the first start of each is slow. Each add-on's e2e/old_anki.py says which it checks."""

from __future__ import annotations

import os
import pickle
import plistlib
import random
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

DARK = 2  # aqt.theme.Theme.DARK: where 2.1.50's own button styles squeezed the cog
CACHE = os.path.expanduser("~/Library/Caches/memory-forest/anki")
RELEASES = "https://github.com/ankitects/anki/releases/download"

# key -> the macOS download on Anki's GitHub releases
ANKIS = {
    "2.1.45": "2.1.45/anki-2.1.45-mac.dmg",
    "2.1.49": "2.1.49/anki-2.1.49-mac.dmg",
    "2.1.50": "2.1.50/anki-2.1.50-mac-apple-qt6.dmg",
    "2.1.50-qt5": "2.1.50/anki-2.1.50-mac-intel-qt5.dmg",
    "2.1.54": "2.1.54/anki-2.1.54-mac-apple-qt6.dmg",
    "2.1.54-qt5": "2.1.54/anki-2.1.54-mac-intel-qt5.dmg",
    "2.1.66-qt5": "2.1.66/anki-2.1.66-mac-intel-qt5.dmg",
    "26.09.3": "26.09.3/anki-26.09.3-mac-apple.dmg",
    "26.09.2": "26.09.2/anki-26.09.2-mac-apple.dmg",
}


def fetch(key: str) -> str:
    """The Anki.app for `key` in ANKIS, downloaded and unpacked into CACHE the first time."""
    app = os.path.join(CACHE, key + ".app")
    if os.path.exists(app):
        return app
    os.makedirs(CACHE, exist_ok=True)
    url = f"{RELEASES}/{ANKIS[key]}"
    print(f"downloading Anki {key} from {url}")
    with tempfile.TemporaryDirectory() as tmp:
        dmg, mount = os.path.join(tmp, "anki.dmg"), os.path.join(tmp, "mount")
        urllib.request.urlretrieve(url, dmg)
        subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mount, dmg],
                       check=True, capture_output=True)
        try:
            found = [n for n in os.listdir(mount) if n.endswith(".app")]
            if not found:
                sys.exit(f"no .app in {url}")
            # ditto keeps the app's symlinks and signature as they are; into a temp name
            # first, so a download cut short never looks like a finished one
            subprocess.run(["ditto", os.path.join(mount, found[0]), app + ".part"], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", mount], check=False, capture_output=True)
    os.rename(app + ".part", app)
    return app


def resolve(name: str) -> tuple:
    """(label, Anki.app) for a key of ANKIS or a path to an Anki.app."""
    if name in ANKIS:
        return name, fetch(name)
    if os.path.isdir(name):
        return os.path.basename(name.rstrip("/")).removesuffix(".app"), name
    sys.exit(f"no Anki {name!r}: name one of {', '.join(ANKIS)} or the path to an Anki.app")


def executable(app: str) -> str:
    """The program inside an Anki.app (anki, or AnkiMac before 2.1.50), from its Info.plist."""
    with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
        return os.path.join(app, "Contents", "MacOS", os.path.basename(plistlib.load(f)["CFBundleExecutable"]))


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

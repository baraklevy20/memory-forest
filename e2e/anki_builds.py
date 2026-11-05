# Copied from addon_libs/anki_builds.py by addon_libs/sync.py: edit it there, not here.
"""Real Ankis to check an add-on in: downloaded from Anki's GitHub releases the first time and kept in CACHE, so no
add-on downloads one twice. On macOS the Qt5 builds (every Anki before 2.1.50, and the builds for older computers after
it) are Intel-only and run under Rosetta: the first start of each is slow. On Windows each is unpacked rather than
installed, so nothing on the computer changes (7-Zip for an .exe, msiexec's administrative install for an .msi). Each
add-on's e2e/old_anki.py says which it checks."""

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
CACHE = os.path.normpath(os.path.expanduser("~/Library/Caches/memory-forest/anki"))  # (one kind of slash: msiexec needs it)
RELEASES = "https://github.com/ankitects/anki/releases/download"

# key -> the macOS download on Anki's GitHub releases
MAC_ANKIS = {
    "2.1.45": "2.1.45/anki-2.1.45-mac.dmg",
    "2.1.49": "2.1.49/anki-2.1.49-mac.dmg",
    "2.1.50": "2.1.50/anki-2.1.50-mac-apple-qt6.dmg",
    "2.1.50-qt5": "2.1.50/anki-2.1.50-mac-intel-qt5.dmg",
    "2.1.54": "2.1.54/anki-2.1.54-mac-apple-qt6.dmg",
    "2.1.54-qt5": "2.1.54/anki-2.1.54-mac-intel-qt5.dmg",
    "2.1.66-qt5": "2.1.66/anki-2.1.66-mac-intel-qt5.dmg",
    "26.09.4": "26.09.4/anki-26.09.4-mac-apple.dmg",
}
# and the Windows one
WINDOWS_ANKIS = {
    "2.1.45": "2.1.45/anki-2.1.45-windows.exe",
    "2.1.49": "2.1.49/anki-2.1.49-windows.exe",
    "2.1.50": "2.1.50/anki-2.1.50-windows-qt6.exe",
    "2.1.50-qt5": "2.1.50/anki-2.1.50-windows-qt5.exe",
    "2.1.54": "2.1.54/anki-2.1.54-windows-qt6.exe",
    "2.1.54-qt5": "2.1.54/anki-2.1.54-windows-qt5.exe",
    "2.1.66-qt5": "2.1.66/anki-2.1.66-windows-qt5.exe",
    "26.09.4": "26.09.4/anki-26.09.4-win-x64.msi",
}
WINDOWS = os.name == "nt"
ANKIS = WINDOWS_ANKIS if WINDOWS else MAC_ANKIS
# the program in a Windows build: the console one where there is one, whose output (tracebacks too) can be read
WINDOWS_PROGRAMS = ("anki-console.exe", "anki.exe")


def unpack_windows(file: str, into: str) -> None:
    """A Windows build's files in the folder `into`, without installing it."""
    if file.endswith(".msi"):
        subprocess.run(["msiexec", "/a", file, "/qn", f"TARGETDIR={into}"], check=True)
    else:
        subprocess.run(["7z", "x", "-y", f"-o{into}", file], check=True, stdout=subprocess.DEVNULL)


def fetch_windows(key: str) -> str:
    """The folder of Anki `key`, downloaded and unpacked into CACHE the first time."""
    folder = os.path.join(CACHE, key)
    if os.path.exists(folder):
        return folder
    os.makedirs(CACHE, exist_ok=True)
    url = f"{RELEASES}/{ANKIS[key]}"
    print(f"downloading Anki {key} from {url}")
    with tempfile.TemporaryDirectory() as tmp:
        file = os.path.join(tmp, os.path.basename(ANKIS[key]))
        urllib.request.urlretrieve(url, file)
        unpack_windows(file, folder + ".part")  # (a temp name: one cut short never looks finished)
    os.rename(folder + ".part", folder)
    return folder


def fetch(key: str) -> str:
    """The Anki.app (on Windows, the folder) for `key` in ANKIS, downloaded and unpacked into CACHE the first time."""
    if WINDOWS:
        return fetch_windows(key)
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
        return os.path.basename(name.rstrip("/\\")).removesuffix(".app"), name
    sys.exit(f"no Anki {name!r}: name one of {', '.join(ANKIS)} or the path to an Anki")


def windows_program(folder: str) -> str:
    """The program in a Windows build's folder, "" if it has none."""
    found = {name.lower(): os.path.join(root, name) for root, _dirs, names in os.walk(folder) for name in names}
    return next((found[p] for p in WINDOWS_PROGRAMS if p in found), "")


def executable(app: str) -> str:
    """The program inside an Anki.app (anki, or AnkiMac before 2.1.50), from its Info.plist; on Windows, in its folder."""
    if WINDOWS:
        return windows_program(app)
    with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
        return os.path.join(app, "Contents", "MacOS", os.path.basename(plistlib.load(f)["CFBundleExecutable"]))


def needs_window(program: str) -> bool:
    """Whether this Anki can't use Qt's offscreen platform: on Windows, a Qt5 build crashes on it at startup, so its
    check opens a real window (on a CI runner, nobody's desktop)."""
    return os.name == "nt" and any(os.path.isdir(os.path.join(os.path.dirname(program), *p)) for p in (("PyQt5",), ("lib", "PyQt5")))


def windows_env(env: dict) -> None:
    """Keep the web view off the GPU on Windows: a CI runner has none, and its older Chromiums crash reaching for one."""
    if os.name == "nt":
        env["QT_OPENGL"] = "software"
        flags = "--disable-gpu --disable-gpu-compositing --no-sandbox"
        env["QTWEBENGINE_CHROMIUM_FLAGS"] = (env.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " " + flags).strip()


def no_first_run(base: str) -> None:
    """The global settings Anki would ask for on its very first run (the language, in a
    dialog that waits for a click), so the profile opens by itself: with none in it, Anki
    makes "User 1" and opens that."""
    meta = {"ver": 0, "updates": False, "created": int(time.time()), "id": random.randrange(0, 2**63), "lastMsg": -1,
            "suppressUpdate": True, "check_for_updates": False, "firstRun": True, "defaultLang": "en_US", "theme": DARK}
    db = sqlite3.connect(os.path.join(base, "prefs21.db"))
    db.execute("create table if not exists profiles (name text primary key, data blob not null)")
    db.execute("insert or replace into profiles values ('_global', ?)", (pickle.dumps(meta, protocol=4),))
    db.commit()
    db.close()

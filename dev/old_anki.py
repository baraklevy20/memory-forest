"""Open an old Anki version on a throwaway profile, with this add-on in it, to check it still works there.

    python3 dev/old_anki.py                                # Anki 2.1.45, to look around by hand
    python3 dev/old_anki.py 2.1.54-qt5                     # any Anki in ANKIS, or the path to an Anki.app
    python3 dev/old_anki.py --keep                         # reuse the last throwaway profile
    python3 dev/old_anki.py --check [ANKI ...]             # check it (built, as it ships) by itself, then quit
    python3 dev/old_anki.py --check --all                  # in every Anki in RELEASE_ANKIS (what a release runs)
    python3 dev/old_anki.py --check --all --package x.ankiaddon   # the built add-on rather than this folder

An Anki named by its key in ANKIS is downloaded from Anki's GitHub releases the first time
and kept in CACHE. The Qt5 builds (every Anki before 2.1.50, and the builds for older
computers after it) are Intel-only and run under Rosetta; their web view is an old
Chromium (Qt 5.14's), the oldest any supported Anki draws the forest with.

To look around it copies this folder (without your meta.json, user_files or caches); a
check builds it first (dev/package.py, the base edition) or takes --package's .ankiaddon,
and unpacks that into a fresh base folder under the temp dir and starts that Anki
with -b, so your own collection and your dev config are never touched.

--check needs no hands: the profile starts in English and the dark theme, with no update
check, and dev/old_anki_check.py goes in beside the add-on. Once the profile is open it
fills the collection with made-up reviews, checks the forest built from them, measures the
cog in the deck list, opens the settings, each of their tabs and the scenery picker, picks
another scenery and checks the forest was built again, and quits; this prints what went
wrong, if anything (a console error in the page counts), and exits 1 then. Screenshots of
the deck list are kept in RESULTS. Anki runs one copy per user, so the check runs under a
user name of its own and leaves an Anki you have open alone.
"""

from __future__ import annotations

import json
import os
import pickle
import plistlib
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
BASE = os.path.join(tempfile.gettempdir(), "memory-forest-try-anki")
RESULTS = os.path.join(tempfile.gettempdir(), "memory-forest-old-anki")  # screenshots, one folder per Anki
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
}
# what a release is checked in: the oldest Anki it claims (manifest.json's
# min_point_version), the oldest with Qt6 (PyQt6 and a new build), the Qt5 build a report
# came from (the oldest web view since 2.1.50), and the newest
RELEASE_ANKIS = ("2.1.45", "2.1.50", "2.1.54-qt5", "26.09.3")
DEFAULT_ANKI = "2.1.45"
SKIP = shutil.ignore_patterns("meta.json", "user_files", "__pycache__", "node_modules", "dist", "*.ankiaddon", ".*")
CHECK_ADDON = "0_memory_forest_check"  # Anki loads add-ons in folder order: this one first
CHECK_TIMEOUT_SECS = 180  # a first start under Rosetta translates the whole app
QUIT_GRACE_SECS = 20  # after the check reported: some old Ankis never quit by themselves
DARK = 2  # aqt.theme.Theme.DARK: where 2.1.50's own button styles squeezed the cog
# Anki's one-copy-per-user key comes from the user name (getpass, from these variables): a
# name of its own lets the check run beside the Anki you have open
CHECK_USER = "memory-forest-check"


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


def install(package: str | None) -> str:
    """This folder, or the built `package`, into a fresh BASE; the add-on's folder name."""
    if os.path.exists(BASE):
        shutil.rmtree(BASE)
    if package:
        with zipfile.ZipFile(package) as z:
            folder = json.loads(z.read("manifest.json"))["package"]
            z.extractall(os.path.join(BASE, "addons21", folder))
    else:
        folder = os.path.basename(ADDON)
        shutil.copytree(ADDON, os.path.join(BASE, "addons21", folder), ignore=SKIP)
    return folder


def progress() -> str:
    """dev/old_anki_check.py's log of how far it got."""
    path = os.path.join(BASE, "check.log")
    return ("check.log:\n" + open(path, encoding="utf-8").read()) if os.path.exists(path) else "(no check.log: the check add-on never loaded)\n"


def run_check(binary: str, folder: str) -> tuple:
    """Run Anki with the check add-on until it reports, or CHECK_TIMEOUT_SECS go by:
    (what it reported or None, Anki's own output, whether Anki quit by itself)."""
    no_first_run(BASE)
    dest = os.path.join(BASE, "addons21", CHECK_ADDON)
    os.makedirs(dest, exist_ok=True)
    shutil.copy(os.path.join(HERE, "old_anki_check.py"), os.path.join(dest, "__init__.py"))
    out, log = os.path.join(BASE, "check.json"), os.path.join(BASE, "anki.log")
    env = dict(os.environ, MEMORY_FOREST_FOLDER=folder, USER=CHECK_USER, LOGNAME=CHECK_USER)
    with open(log, "w") as f:
        anki = subprocess.Popen([binary, "-b", BASE, "-l", "en"], env=env, stdout=f, stderr=subprocess.STDOUT)
    deadline, reported = time.time() + CHECK_TIMEOUT_SECS, None
    while anki.poll() is None and time.time() < deadline:
        if reported is None and os.path.exists(out):
            reported = time.time()
        if reported and time.time() > reported + QUIT_GRACE_SECS:
            break
        time.sleep(0.5)
    quit_by_itself = anki.poll() is not None
    if not quit_by_itself:
        anki.kill()
        anki.wait()
    with open(log, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not os.path.exists(out):
        return None, text, quit_by_itself
    with open(out, encoding="utf-8") as f:
        return json.load(f), text, quit_by_itself


def check(label: str, app: str, package: str | None) -> bool:
    """Check the add-on in one Anki; prints what it found, and whether it all went well."""
    binary = executable(app)
    if not os.path.exists(binary):
        sys.exit(f"no Anki at {app}")
    folder = install(package)
    print(f"== Anki {label} ({app}), {os.path.basename(package) if package else 'this folder'}")
    r, log, quit_by_itself = run_check(binary, folder)
    if "Already running" in log:
        sys.exit("another check's Anki is still open: close it and run this again")
    if r is None:
        print(f"FAILED: the check never reported back\n{progress()}{log[-3000:]}")
        return False
    shots = os.path.join(RESULTS, label)
    shutil.rmtree(shots, ignore_errors=True)
    os.makedirs(shots)
    for name in os.listdir(BASE):
        if name.endswith(".png"):
            shutil.copy(os.path.join(BASE, name), shots)
    deck = r.get("deck_list") or {}
    print(f"Anki {r.get('anki')}, Qt {r.get('qt')}, {deck.get('agent', 'no web view')}")
    print("  " + ", ".join(r["steps"]))
    print(f"  forest: {deck.get('trees')} trees, {deck.get('painted')}% painted; screenshots in {shots}")
    if not quit_by_itself:
        print(f"  (Anki did not quit within {QUIT_GRACE_SECS} s of reporting: stopped)")
    for line in r.get("console", []):
        print("  console: " + line)
    for problem in r["problems"]:
        print("  PROBLEM " + problem)
    for error in r["errors"]:
        print("  ERROR " + error)
    # what the add-on caught and only printed (state.log): the forest's own failures, which
    # leave no trace in the page or in a dialog
    logged = [chunk.split("\n\n")[0] for chunk in log.split("[anki_forest] ")[1:] if "Traceback" in chunk]
    for chunk in dict.fromkeys(logged):
        print("  LOGGED " + chunk.strip().replace("\n", "\n    "))
    ok = not (r["problems"] or r["errors"] or logged)
    print("  ok" if ok else "  FAILED")
    return ok


def built() -> str:
    """This folder built the way it ships (minified, for the oldest browser): what is checked
    when no --package is given, since the readable source is never what anyone runs."""
    out = os.path.join(tempfile.gettempdir(), "memory-forest-check.ankiaddon")
    edition = ["--edition", "base"] if os.path.exists(os.path.join(ADDON, "editions.json")) else []
    subprocess.run([sys.executable, os.path.join(HERE, "package.py"), *edition, out], check=True, stdout=subprocess.DEVNULL)
    return out


def main() -> None:
    args = sys.argv[1:]
    keep, checking, every = "--keep" in args, "--check" in args, "--all" in args
    package = None
    if "--package" in args:
        i = args.index("--package")
        package = os.path.abspath(args[i + 1]) if i + 1 < len(args) else sys.exit("--package needs a .ankiaddon")
        del args[i:i + 2]
    names = [a for a in args if a not in ("--keep", "--check", "--all")]
    if every:
        names = list(RELEASE_ANKIS)
    names = names or [DEFAULT_ANKI]
    if checking:
        package = package or built()
        failed = [name for name in names if not check(*resolve(name), package)]
        if failed:
            sys.exit(f"\nfailed in Anki {', '.join(failed)}")
        print(f"\nok in Anki {', '.join(names)}")
        return
    if len(names) > 1:
        sys.exit("name one Anki to open")
    label, app = resolve(names[0])
    if keep and os.path.exists(BASE):
        folder = os.path.basename(ADDON)
        dest = os.path.join(BASE, "addons21", folder)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(ADDON, dest, ignore=SKIP)
    else:
        install(package)
    print(f"Anki {label} ({app}) on {BASE}")
    subprocess.run([executable(app), "-b", BASE])


if __name__ == "__main__":
    main()

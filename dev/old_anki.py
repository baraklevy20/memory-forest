"""Open an old Anki version on a throwaway profile, with this add-on in it, to check it still works there.

    python3 dev/old_anki.py                           # /Applications/Anki 2.app
    python3 dev/old_anki.py "/Applications/Anki 2.1.55.app"
    python3 dev/old_anki.py --keep                    # reuse the last throwaway profile

It copies this folder (without your meta.json, user_files or caches) into a fresh base
folder under the temp dir and starts that Anki with -b, so your own collection and your
dev config are never touched. The new profile has no study history: turn on test_forest
in the add-on's config there to see a forest.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
APP = "/Applications/Anki 2.app"
BASE = os.path.join(tempfile.gettempdir(), "memory-forest-try-anki")
SKIP = shutil.ignore_patterns("meta.json", "user_files", "__pycache__", "node_modules", "*.ankiaddon", ".*")


def main() -> None:
    args = sys.argv[1:]
    keep = "--keep" in args
    args = [a for a in args if a != "--keep"]
    app = args[0] if args else APP
    binary = os.path.join(app, "Contents", "MacOS", "anki")
    if not os.path.exists(binary):
        sys.exit(f"no Anki at {app}")
    if not keep and os.path.exists(BASE):
        shutil.rmtree(BASE)
    dest = os.path.join(BASE, "addons21", os.path.basename(ADDON))
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(ADDON, dest, ignore=SKIP)
    print(f"{app} on {BASE}")
    subprocess.run([binary, "-b", BASE])


if __name__ == "__main__":
    main()

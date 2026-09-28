"""Build the .ankiaddon to upload, with none of this machine's own data in it.

    python anki_forest/dev/package.py [--edition NAME] [out.ankiaddon]

With editions.json present an edition must be named (see dev/editions.py); it ships only
that edition's scenery, under its own name and package. The public repo has no
editions.json and ships everything it has.

A plain `zip -r` of the add-on folder would ship meta.json (your config, including the
city you set), user_files/ (your weather cache and state), dev/payload.js (your own
study history) and __pycache__ - the first two of which AnkiWeb rejects outright.
"""

from __future__ import annotations

import json
import os
import sys
import zipfile

import editions

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)

# Everything the add-on needs at runtime, and nothing else. The Python is taken as
# whatever sits beside __init__.py rather than listed by hand: a new module that the
# add-on imports but the list forgot would only show up as a crash on someone else's
# machine, after upload.
INCLUDE_FILES = tuple(sorted(n for n in os.listdir(ADDON) if n.endswith(".py"))) + (
    "config.json", "manifest.json")
INCLUDE_DIRS = ("settings", "web")  # walked, so web/envs, web/landscapes and web/landmarks come too

# The shipped defaults: the debug tools (the made-up test forest) stay on this machine.
RELEASE_CONFIG = {"debug": False, "test_forest": False}


def release_config(text: str | None = None) -> str:
    """The config to ship: this folder's, or `text` when given, with the debug tools off."""
    if text is None:
        with open(os.path.join(ADDON, "config.json"), encoding="utf-8") as f:
            text = f.read()
    cfg = json.loads(text)
    cfg.update(RELEASE_CONFIG)
    return json.dumps(cfg, indent=4) + "\n"


def files(keep: dict | None = None) -> list:
    """(path, name in the zip) for everything to ship; `keep` narrows the scenery to an edition's."""
    out = [(os.path.join(ADDON, f), f) for f in INCLUDE_FILES]
    for d in INCLUDE_DIRS:
        for root, _dirs, names in os.walk(os.path.join(ADDON, d)):
            if "__pycache__" in root:
                continue
            for n in sorted(names):
                if n.startswith("."):
                    continue
                path = os.path.join(root, n)
                rel = os.path.relpath(path, ADDON)
                if keep is None or editions.keeps(rel, keep):
                    out.append((path, rel))
    return out


def main() -> None:
    args = sys.argv[1:]
    edition = None
    if "--edition" in args:
        i = args.index("--edition")
        edition = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    if editions.available() and not edition:
        sys.exit("name an edition: --edition " + "|".join(editions.available()))
    keep = editions.scenery(edition) if edition else None
    package = editions.spec(edition)["package"] if edition else "memory_forest"
    out = args[0] if args else os.path.join(HERE, package + ".ankiaddon")
    shipping = files(keep)
    missing = [name for path, name in shipping if not os.path.exists(path)]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in shipping:
            if name == "config.json":
                z.writestr(name, release_config())
            elif name == "manifest.json" and edition:
                z.writestr(name, editions.manifest(edition))
            else:
                z.write(path, name)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # the whole point of this script: prove none of it got in
    banned = [n for n in names if "meta.json" in n or "user_files" in n or "__pycache__" in n
              or n.startswith("dev/") or n.startswith("tests/")]
    if banned:
        sys.exit("refusing to ship: " + ", ".join(banned))
    with zipfile.ZipFile(out) as z:
        shipped = json.loads(z.read("config.json"))
    if any(shipped.get(k) != v for k, v in RELEASE_CONFIG.items()):
        sys.exit("refusing to ship: debug settings are still on in config.json")
    print(f"wrote {out} ({os.path.getsize(out) // 1024} KB, {len(names)} files)")
    print("contents:", ", ".join(sorted({n.split('/')[0] for n in names})))


if __name__ == "__main__":
    main()

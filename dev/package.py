"""Build the .ankiaddon to upload, with none of this machine's own data in it.

    python anki_forest/dev/package.py [--edition NAME] [--version X.Y.Z] [out.ankiaddon]

With editions.json present an edition must be named (see dev/editions.py); it ships only
that edition's scenery, under its own name and package. The public repo has no
editions.json and ships everything it has. --version sets the version Anki shows for it,
in place of manifest.json's (a release is built from a tag, not from a commit that bumps it).

A plain `zip -r` of the add-on folder would ship meta.json (your config, including the
city you set), user_files/ (your weather cache and state), dev/payload.js (your own
study history) and __pycache__ - the first two of which AnkiWeb rejects outright.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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

# The page's scripts ship minified: half the size, both in the add-on and in the script the
# phone card loads from the collection's media, which is put together from them at each sync
# (phone_data.bundle). Each file is minified on its own: each is one self-contained function
# that shares nothing but window.AnkiForest. This copy (and the public repo) keeps them readable.
ESBUILD = os.path.join(ADDON, "node_modules", ".bin", "esbuild")

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


def minified(shipping: list) -> dict:
    """Name in the zip -> minified text, for every script under web/ that ships."""
    scripts = [(path, name) for path, name in shipping if name.startswith("web/") and name.endswith(".js")]
    if not scripts:
        return {}
    if not os.path.exists(ESBUILD):
        sys.exit("esbuild is missing: run npm install in this folder")
    web = os.path.join(ADDON, "web")
    with tempfile.TemporaryDirectory() as out:
        subprocess.run([ESBUILD, *(path for path, _name in scripts), "--minify", f"--outbase={web}",
                        f"--outdir={out}", "--log-level=warning"], check=True)
        texts = {}
        for path, name in scripts:
            with open(os.path.join(out, os.path.relpath(path, web)), encoding="utf-8") as f:
                texts[name] = f.read()
    return texts


def manifest(edition: str | None, version: str | None) -> str:
    """manifest.json to ship: the edition's own, and the release's version when given."""
    if edition:
        text = editions.manifest(edition)
    else:
        with open(os.path.join(ADDON, "manifest.json"), encoding="utf-8") as f:
            text = f.read()
    m = json.loads(text)
    if version:
        m["human_version"] = version
    return json.dumps(m, indent=2) + "\n"


def main() -> None:
    args = sys.argv[1:]
    edition = None
    if "--edition" in args:
        i = args.index("--edition")
        edition = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    version = None
    if "--version" in args:
        i = args.index("--version")
        version = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
        if not version:
            sys.exit("--version needs a value, e.g. 1.2.0")
    if editions.available() and not edition:
        sys.exit("name an edition: --edition " + "|".join(editions.available()))
    keep = editions.scenery(edition) if edition else None
    package = editions.spec(edition)["package"] if edition else "memory_forest"
    out = args[0] if args else os.path.join(HERE, package + ".ankiaddon")
    shipping = files(keep)
    missing = [name for path, name in shipping if not os.path.exists(path)]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    small = minified(shipping)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in shipping:
            if name == "config.json":
                z.writestr(name, release_config())
            elif name == "manifest.json" and (edition or version):
                z.writestr(name, manifest(edition, version))
            elif name in small:
                z.writestr(name, small[name])
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

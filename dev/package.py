"""Build the .ankiaddon to upload, with none of this machine's own data in it.

    python anki_forest/dev/package.py [--edition NAME] [--version X.Y.Z] [out.ankiaddon]

Without a path it goes to dist/<package>-<version>.ankiaddon (dist/ is gitignored), so
every version built stays there.

With editions.json present an edition must be named (see dev/editions.py); it ships only
that edition's scenery, under its own name and package. The public repo has no
editions.json and ships everything it has. --version sets the version Anki shows for it,
in place of manifest.json's (a release is built from a tag, not from a commit that bumps it).

A plain `zip -r` of the add-on folder would ship meta.json (your config, including the
city you set), user_files/ (your weather cache and state), dev/payload.js (your own
study history) and __pycache__ - the first two of which AnkiWeb rejects outright.
"""

from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import tokenize
import zipfile

import editions

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
DIST = os.path.join(ADDON, "dist")  # where builds go: gitignored
sys.path.insert(0, ADDON)
import catalog

# Everything the add-on needs at runtime, and nothing else. The Python is taken as
# whatever sits beside __init__.py rather than listed by hand: a new module that the
# add-on imports but the list forgot would only show up as a crash on someone else's
# machine, after upload.
INCLUDE_FILES = tuple(sorted(n for n in os.listdir(ADDON) if n.endswith(".py"))) + (
    "config.json", "manifest.json", "goats.json")
INCLUDE_DIRS = ("settings", "web")  # walked, so web/envs, web/landscapes and web/landmarks come too
# The developer's debug tools: the add-on runs without them (payload.debug_tools and the
# settings' debug_tab stand in), and a release ships with debug off.
DEBUG_ONLY = ("debug_events.py", "fake_forest.py", "settings/debug.py")

# The page's scripts ship minified: half the size, both in the add-on and in the script the
# phone card loads from the collection's media, which is put together from them at each sync
# (phone_data.bundle). Each file is minified on its own: each is one self-contained function
# that shares nothing but window.AnkiForest. This copy (and the public repo) keeps them readable.
ESBUILD = os.path.join(ADDON, "node_modules", ".bin", "esbuild")
# The oldest browser that draws the forest: the Qt5 builds of Anki 2.1.50 to 2.1.66 (for
# older Macs) have Qt 5.14's web view, Chromium 77. esbuild rewrites newer syntax (`??`,
# `?.`) into what it knows, and refuses what it cannot rewrite; newer built-in functions
# it leaves alone, so dev/old_anki.py --check in that Anki is still what proves it runs.
OLDEST_BROWSER = "chrome77"

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
    out = [(os.path.join(ADDON, f), f) for f in INCLUDE_FILES if f not in DEBUG_ONLY]
    for d in INCLUDE_DIRS:
        for root, _dirs, names in os.walk(os.path.join(ADDON, d)):
            if "__pycache__" in root:
                continue
            for n in sorted(names):
                if n.startswith("."):
                    continue
                path = os.path.join(root, n)
                rel = os.path.relpath(path, ADDON)
                if rel in DEBUG_ONLY:
                    continue
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
        subprocess.run([ESBUILD, *(path for path, _name in scripts), "--minify", f"--target={OLDEST_BROWSER}", f"--outbase={web}",
                        f"--outdir={out}", "--log-level=warning"], check=True)
        texts = {}
        for path, name in scripts:
            with open(os.path.join(out, os.path.relpath(path, web)), encoding="utf-8") as f:
                texts[name] = f.read()
    return texts


def _docstrings(tree) -> list:
    """The docstring expressions of a module and of every class and function in it."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                out.append(first)
    return out


def _shape(text: str) -> tuple:
    """What running `text` does, and where: its syntax tree with every docstring emptied, and
    the line each statement starts on (what a traceback reports)."""
    tree = ast.parse(text)
    for doc in _docstrings(tree):
        doc.value.value = ""
    return ast.dump(tree), [(type(n).__name__, n.lineno) for n in ast.walk(tree) if isinstance(n, ast.stmt)]


def stripped(text: str) -> str:
    """Python without its comments and docstrings, each line where it was: a traceback from
    someone's machine still names the line it means in this copy. The readable source stays
    here and in the public repo."""
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def at(row: int, col: int, byte_col: bool = False) -> int:
        line = lines[row - 1]
        if byte_col:  # ast counts columns in UTF-8 bytes
            col = len(line.encode("utf-8")[:col].decode("utf-8"))
        return starts[row - 1] + col

    edits = []  # (start, end, replacement) in characters
    for doc in _docstrings(ast.parse(text)):
        edits.append((at(doc.lineno, doc.col_offset, True), at(doc.end_lineno, doc.end_col_offset, True),
                      '""' + "\n" * (doc.end_lineno - doc.lineno)))
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            edits.append((at(*tok.start), at(*tok.end), ""))
    out = text
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    out = "".join(line.rstrip() + "\n" for line in out.splitlines())
    if _shape(out) != _shape(text):
        sys.exit("stripping comments changed what the code does or where it stands")
    return out


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
    shipped = json.loads(manifest(edition, version))["human_version"]
    out = args[0] if args else os.path.join(DIST, f"{package}-{shipped}.ankiaddon")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    shipping = files(keep)
    missing = [name for path, name in shipping if not os.path.exists(path)]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    small = minified(shipping)
    # the page's own scripts go as one file (catalog.BUNDLE), in the order they load
    core = {f"web/{rel}" for rel in catalog.SCRIPTS}
    bundled = "\n".join(small[f"web/{rel}"] for rel in catalog.SCRIPTS)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"web/{catalog.BUNDLE}", bundled)
        for path, name in shipping:
            if name in core:
                continue
            if name == "config.json":
                z.writestr(name, release_config())
            elif name == "manifest.json" and (edition or version):
                z.writestr(name, manifest(edition, version))
            elif name in small:
                z.writestr(name, small[name])
            elif name.endswith(".py"):
                with open(path, encoding="utf-8") as f:
                    z.writestr(name, stripped(f.read()))
            else:
                z.write(path, name)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    # the whole point of this script: prove none of it got in
    banned = [n for n in names if "meta.json" in n or "user_files" in n or "__pycache__" in n
              or n.startswith("dev/") or n.startswith("tests/") or n in DEBUG_ONLY]
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

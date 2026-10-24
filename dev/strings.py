"""The add-on's words and their translations (i18n.py, web/i18n.js).

    npm run strings                     collect every id the code uses into locales/catalog.json, and
                                        the English the page needs into web/strings_en.js
    npm run strings -- check            both are up to date, every id the code uses has its English in
                                        locales/en.json (and en.json none it doesn't), and every
                                        translation fits: the same {placeholders} and tags, every
                                        plural form the language has, no ids the code no longer uses
    npm run strings -- prune he         drop the ids the code no longer uses from locales/he.json

Where the ids come from: calls with a literal id (t, tn, N_; AF.t, AF.tn, AF.N_ on the page) in web/
(not web/drafts/) and the Python files (not dev/, e2e/ or tests/); the scenery's own (i18n.py
scenery_english) for every scenery an edition ships; and the dates i18n.py writes.

A language's file keeps each translation with the English it was translated from,
{"text": ..., "en": ...}: the English changed since is still shown in the old translation, and check
lists it to translate again. A translation added by hand needs only its "text": collecting stamps
its "en".
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
import i18n

SKIP_DIRS = {"dev", "e2e", "tests", "node_modules", "dist", "user_files", "__pycache__", "drafts", "locales", "docs"}
FUNCS = ("t", "tn", "N_")
ID = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
TAG = re.compile(r"</?\w+[^>]*>")
STRINGS_EN = os.path.join(ADDON, "web", "strings_en.js")


def _files(ext: str):
    for root, dirs, names in os.walk(ADDON):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for n in sorted(names):
            if n.endswith(ext):
                yield os.path.join(root, n)


def _read(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def _write(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=1)
        f.write("\n")


# ---------- finding the ids ----------

JS_CALL = re.compile(r"(?<![\w.$])AF\.(t|tn|N_)\(\s*(['\"])([^'\"]*)\2")
JS_ANY = re.compile(r"(?<![\w.$])AF\.(t|tn|N_)\(")


def js_ids(path: str):
    """(id, line) for each AF.t / tn / N_ call in a script; a call whose id isn't literal is an error."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    found = {m.start(): m for m in JS_CALL.finditer(src)}
    for m in JS_ANY.finditer(src):
        line = src.count("\n", 0, m.start()) + 1
        if m.start() not in found:
            raise SystemExit(f"{os.path.relpath(path, ADDON)}:{line}: AF.{m.group(1)}() needs a literal id (AF.tx for one found at run time)")
        yield found[m.start()].group(3), line


def py_ids(path: str):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if name not in FUNCS or (isinstance(f, ast.Attribute) and not (isinstance(f.value, ast.Name) and f.value.id == "i18n")):
            continue
        arg = node.args[0] if node.args else None
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            raise SystemExit(f"{os.path.relpath(path, ADDON)}:{node.lineno}: {name}() needs a literal id (tx for one found at run time)")
        yield arg.value, node.lineno


def _shipped():
    """The environments, landscapes, landmarks and presets some edition ships (None: every one, as in
    the public repo)."""
    if not os.path.exists(os.path.join(ADDON, "editions.json")):
        return None
    sys.path.insert(0, HERE)
    import editions
    out = {"envs": set(), "landscapes": set(), "landmarks": set(), "presets": set()}
    for name in editions.available():
        got = editions.scenery(name)
        for k in out:
            out[k] |= set(got[k])
    return out


def scenery_ids() -> dict:
    """id -> where, for the scenery words an edition ships (i18n.scenery_english)."""
    shipped = _shipped()
    kinds = {"env": "envs", "landscape": "landscapes", "landmark": "landmarks"}
    plus = {p["key"] for p in _read(os.path.join(ADDON, "settings", "plus.json"), [])}
    out = {}
    for key in i18n.scenery_english():
        kind, name = key.split(".")[:2]
        if kind in kinds:
            if shipped is None or name in shipped[kinds[kind]]:
                out[key] = f"web/{kinds[kind]}/{name}.json"
        elif kind == "preset":
            if shipped is None or name in shipped["presets"]:
                out[key] = "presets"
            elif name in plus:
                out[key] = "settings/plus.json"
        elif os.path.exists(os.path.join(ADDON, "web", "heatmap", f"{name}.json")):  # (not a draft's)
            out[key] = f"web/heatmap/{name}.json"
    return out


def collect() -> dict:
    """id -> {"web": whether a page script uses it, "where": the files that do (no lines: a line
    added above one leaves the catalog as it is)}."""
    out = {}

    def add(key, where, web):
        if not ID.match(key):
            raise SystemExit(f"{where}: {key!r} is not an id (lower-case words joined by . and _)")
        e = out.setdefault(key, {"web": False, "where": []})
        e["web"] = e["web"] or web
        if where not in e["where"]:
            e["where"].append(where)

    for path in _files(".js"):
        rel = os.path.relpath(path, ADDON).replace(os.sep, "/")
        if rel.startswith("web/") and rel not in ("web/i18n.js", "web/strings_en.js"):
            for key, _line in js_ids(path):
                add(key, rel, True)
    for path in _files(".py"):
        rel = os.path.relpath(path, ADDON).replace(os.sep, "/")
        if rel != "i18n.py":
            for key, _line in py_ids(path):
                add(key, rel, False)
    # the dates and months i18n.py writes
    for m in i18n.MONTHS:
        add(f"month.{m}", "i18n.py", False)
        add(f"month_short.{m[:3]}", "i18n.py", False)
    for d in ("day_month", "day_month_year", "month_year"):
        add(f"date.{d}", "i18n.py", False)
    # the scenery's: shown by the dialog, and named on the page
    for key, where in scenery_ids().items():
        add(key, where, False)
    return dict(sorted(out.items()))


def strings_en(cat: dict) -> str:
    """web/strings_en.js: the English of every id a page script uses."""
    en = i18n.english()
    words = {k: en[k] for k in cat if cat[k]["web"] and k in en}
    return ("/* Memory Forest — the page's words in English, by id: made from locales/en.json by\n"
            " * dev/strings.py (npm run strings), never by hand. */\n"
            "window.AnkiForest.EN = " + json.dumps(dict(sorted(words.items())), ensure_ascii=False, indent=1) + ";\n")


# ---------- checking ----------

def _shape(text: str):
    return sorted(set(PLACEHOLDER.findall(text))), sorted(m.group(0).split()[0].rstrip(">") for m in TAG.finditer(text))


def english_problems(cat: dict) -> list:
    en_file = _read(i18n.ENGLISH)
    en = i18n.english()
    out = [f"{k}: used in {cat[k]['where'][0]}, but locales/en.json has no English for it" for k in cat if k not in en]
    out += [f"{k}: in locales/en.json, but the code no longer uses it" for k in en_file if k not in cat]
    for k, v in en_file.items():
        if isinstance(v, dict) and (set(v) != {"one", "other"} or _shape(v["one"])[1] != _shape(v["other"])[1]):
            out.append(f"{k}: an English plural is {{\"one\", \"other\"}}, with the same tags")
    return out


def problems(tag: str, table: dict, cat: dict) -> list:
    """What is wrong with a language's file, as lines."""
    out = []
    en = i18n.english()
    forms = i18n.PLURAL_FORMS[i18n.plural_rule(tag)]
    for key, entry in table.items():
        if key.startswith("_"):
            continue
        if key not in cat or key not in en:
            out.append(f"{key}: the code no longer uses it (npm run strings -- prune {tag})")
            continue
        value = entry.get("text") if isinstance(entry, dict) else None
        if value is None:
            out.append(f"{key}: should be {{\"text\": ..., \"en\": ...}}")
            continue
        english = en[key]
        if isinstance(english, dict):
            if not isinstance(value, dict):
                out.append(f"{key}: a plural needs its forms ({', '.join(forms)})")
                continue
            missing = [f for f in forms if not value.get(f)]
            if missing:
                out.append(f"{key}: missing plural forms: {', '.join(missing)}")
            want = _shape(english["other"])
            for form, text in value.items():
                got = _shape(text)
                # (a form may leave out the number: "יומיים" for 2 days)
                if got[1] != want[1] or not set(got[0]) <= set(want[0]):
                    out.append(f"{key} ({form}): placeholders or tags differ from the English: {text!r}")
        elif not isinstance(value, str):
            out.append(f"{key}: should be a string")
        elif _shape(value) != _shape(english):
            out.append(f"{key}: placeholders or tags differ from the English: {value!r}")
    return out


def outdated(table: dict) -> list:
    """The ids whose English changed since they were translated."""
    en = i18n.english()
    return [k for k, e in table.items() if isinstance(e, dict) and k in en and e.get("en") != en[k]]


def _table(tag: str) -> dict:
    return _read(os.path.join(i18n.LOCALES, f"{tag}.json"))


def check() -> int:
    found = collect()
    bad = 0
    if found != i18n.catalog():
        print("locales/catalog.json is out of date: run npm run strings")
        bad += 1
    try:
        with open(STRINGS_EN, encoding="utf-8") as f:
            current = f.read()
    except OSError:
        current = ""
    if current != strings_en(found):
        print("web/strings_en.js is out of date: run npm run strings")
        bad += 1
    for line in english_problems(found):
        print(line)
        bad += 1
    for tag in i18n.available()[1:]:
        table = _table(tag)
        lines = problems(tag, table, found)
        old = outdated(table)
        done = sum(1 for k in found if k in table and k not in old)
        print(f"{tag}: {done} of {len(found)} translated ({100 * done // max(1, len(found))}%)"
              + (f", {len(old)} to translate again (English changed)" if old else "")
              + (f", {len(lines)} problems" if lines else ""))
        for line in lines:
            print("  " + line)
        bad += len(lines)
    return 1 if bad else 0


# ---------- for a copy with fewer files (the public repo, the base edition) ----------

def for_edition(cat: dict, published) -> dict:
    """The catalog as a copy with fewer files has it: only the ids some file it has uses, where it
    uses them. `published(rel)`: whether it has the file."""
    out = {}
    for key, e in cat.items():
        where = [w for w in e.get("where", []) if w in ("i18n.py", "presets") or published(w)]
        if where:
            out[key] = dict(e, where=where)
    return out


def edition_file(rel: str, text: str, cat: dict, published) -> str:
    """A file under locales/ as that copy has it: the catalog for_edition, and en.json and each
    language without the ids it no longer has."""
    keep = for_edition(cat, published)
    data = json.loads(text)
    data = keep if rel.endswith("catalog.json") else {k: v for k, v in data.items() if k in keep or k.startswith("_")}
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def stamp() -> None:
    """Each translation added by hand, with no "en" yet, marked as made from today's English."""
    en = i18n.english()
    for tag in i18n.available()[1:]:
        table = _table(tag)
        new = {k: v for k, v in table.items() if isinstance(v, dict) and "en" not in v and k in en}
        if new:
            table.update({k: dict(v, en=en[k]) for k, v in new.items()})
            _write(os.path.join(i18n.LOCALES, f"{tag}.json"), table)
            print(f"{tag}: {len(new)} new translations marked")


def prune(tag: str) -> str:
    cat = i18n.catalog()
    table = _table(tag)
    kept = {k: v for k, v in table.items() if k in cat or k.startswith("_")}
    _write(os.path.join(i18n.LOCALES, f"{tag}.json"), kept)
    return f"{len(table) - len(kept)} unused strings dropped from locales/{tag}.json"


def main(argv: list) -> int:
    cmd = argv[0] if argv else "collect"
    if cmd == "collect":
        old, new = i18n.catalog(), collect()
        _write(i18n.CATALOG, new)
        stamp()
        with open(STRINGS_EN, "w", encoding="utf-8") as f:
            f.write(strings_en(new))
        added, gone = sorted(set(new) - set(old)), sorted(set(old) - set(new))
        print(f"locales/catalog.json: {len(new)} ids ({len(added)} new, {len(gone)} gone)")
        for line in english_problems(new):
            print("  " + line)
        return 0
    if cmd == "check":
        return check()
    if cmd == "prune" and len(argv) == 2:
        print(prune(argv[1]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""The AnkiWeb page's What's new, made from release_notes.json (release_notes.py).

    python3 dev/notes.py           rewrite it in docs/ankiweb.html (npm run notes)
    python3 dev/notes.py --check   only say whether it is up to date (exit 1 if not)

The page is the public one, so it lists what the base edition has: an item that `needs` a
Plus scenery is left out of it, as it is of the base edition's own copy of
release_notes.json (dev/export_public.py, dev/package.py: edition_json).
"""

from __future__ import annotations

import json
import os
import sys

import editions

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
PAGE = os.path.join(ADDON, "docs", "ankiweb.html")
PUBLIC = "base"
sys.path.insert(0, ADDON)
import release_notes


def view(edition: str | None) -> dict:
    """What an edition has, as release_notes.has takes it; where there is no editions.json
    (the public repo), everything here is the edition."""
    if not edition or edition not in editions.available():
        return {"scenery": None}
    shipped = editions.scenery(edition)
    return {"scenery": shipped["presets"]}


def versions(edition: str | None = PUBLIC) -> list:
    return release_notes.for_edition(release_notes.load(), view(edition))


def edition_json(edition: str | None, text: str) -> str:
    """release_notes.json as `edition` ships it: without what it lacks."""
    data = json.loads(text)
    data["versions"] = release_notes.for_edition(data.get("versions", []), view(edition))
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def page() -> str:
    """docs/ankiweb.html with its What's new made afresh."""
    with open(PAGE, encoding="utf-8") as f:
        return release_notes.in_page(f.read(), versions())


def main() -> None:
    fresh = page()
    with open(PAGE, encoding="utf-8") as f:
        current = f.read()
    if "--check" in sys.argv[1:]:
        if fresh != current:
            sys.exit("docs/ankiweb.html is out of date with release_notes.json: run npm run notes")
        print("docs/ankiweb.html is up to date")
        return
    if fresh != current:
        with open(PAGE, "w", encoding="utf-8") as f:
            f.write(fresh)
        print("rewrote docs/ankiweb.html's What's new")
    else:
        print("docs/ankiweb.html was already up to date")


if __name__ == "__main__":
    main()

"""The release notes, kept in one place: release_notes.json. Everything else is made from it:
the AnkiWeb page's "What's new" (docs/ankiweb.html, by dev/notes.py), the GitHub release's
notes (dev/release.py), the About tab's What's new, and what an update announces in the
forest (news.py). Nothing here touches Anki, so the dev scripts and the tests use it too.

A version is {"version", and its lists: "new", "improved", "fixed" (each under its heading),
or "notes" (no heading)}. An item is its line, or {"text": its line, and maybe:
  "needs": what an edition must have to hear of it, each word "<kind>:<key>" (one of the
           kind, e.g. "scenery:aurora") or "<kind>" (any of it) - an edition without it
           never lists it (the public page is the base edition's);
  "announce": {"id", "kind": "note" (a card on the forest, once: "title", "text", and maybe a
              button, "action", that opens the settings where "opens" says) or "dot" (the
              cog's dot, and NEW on the tile of the scenery it `needs`)}}."""

from __future__ import annotations

import html
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_notes.json")
SECTIONS = (("new", "New"), ("improved", "Improved"), ("fixed", "Fixed"), ("notes", ""))
# what docs/ankiweb.html's What's new sits between
HTML_START = "<div><b>What's new</b></div>\n"
HTML_END = "<div><b>Support</b></div>"


def load(path: str = PATH) -> list:
    """The versions, newest first (none if the file is missing or broken)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    versions = data.get("versions") if isinstance(data, dict) else None
    return versions if isinstance(versions, list) else []


def item(entry) -> dict:
    """An item as a dict, whichever way it is written."""
    return entry if isinstance(entry, dict) else {"text": entry}


def has(entry, have: dict) -> bool:
    """Whether an edition has what the item needs. `have`: kind -> the keys of it the edition
    has (None: every one there is), e.g. {"scenery": its preset keys}."""
    for need in (item(entry).get("needs") or "").split():
        kind, _, key = need.partition(":")
        got = have.get(kind, set())
        if got is not None and not (key in got if key else got):
            return False
    return True


def for_edition(versions: list, have: dict) -> list:
    """The notes as an edition sees them: without the items it lacks (an emptied list goes)."""
    out = []
    for v in versions:
        kept = {"version": v["version"]}
        for key, _head in SECTIONS:
            items = [e for e in v.get(key, []) if has(e, have)]
            if items:
                kept[key] = items
        out.append(kept)
    return out


def items(version: dict, sections=tuple(k for k, _h in SECTIONS)) -> list:
    """Every item of a version, as dicts, in the order of its lists."""
    return [item(e) for key in sections for e in version.get(key, [])]


def to_html(versions: list) -> str:
    """The AnkiWeb page's What's new, between HTML_START and HTML_END."""
    out = []
    for v in versions:
        out.append(f"<i>{v['version']}</i>")
        for key, head in SECTIONS:
            if v.get(key):
                if head:
                    out.append(f"<div><b>{head}</b></div>")
                out.append("<ul>")
                out += [f"<li>{item(e)['text']}</li>" for e in v[key]]
                out.append("</ul>")
    return "\n".join(out) + "\n"


def in_page(page: str, versions: list) -> str:
    """The AnkiWeb page with its What's new made afresh from `versions`."""
    start = page.index(HTML_START) + len(HTML_START)
    return page[:start] + to_html(versions) + page[page.index(HTML_END, start):]


def _markdown(fragment: str) -> str:
    """A line's HTML as Markdown."""
    fragment = re.sub(r"</?b>", "**", fragment)
    fragment = re.sub(r'<a href="([^"]*)">(.*?)</a>', r"[\2](\1)", fragment)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def to_markdown(versions: list, version: str) -> str | None:
    """One version's notes for its GitHub release: each heading a ###, each item a bullet;
    None if there is no such version."""
    v = next((v for v in versions if v.get("version") == version), None)
    if v is None:
        return None
    lines = []
    for key, head in SECTIONS:
        if v.get(key):
            if head:
                lines += ([""] if lines else []) + [f"### {head}", ""]
            lines += ["- " + _markdown(item(e)["text"]) for e in v[key]]
    return "\n".join(lines) + "\n"

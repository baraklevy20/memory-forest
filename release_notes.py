"""The release notes, kept in one place: release_notes.json. Everything else is made from it:
the AnkiWeb page's "What's new" (docs/ankiweb.html, by dev/notes.py), the GitHub release's
notes (dev/release.py), the About tab's What's new, and what an update announces in the
forest (news.py). Nothing here touches Anki, so the dev scripts and the tests use it too.

A version is {"version", maybe "summary" (one line on what the update is about, before its
lists, from 1.3.0 on), and its lists: "new", "improved", "fixed" (each under its heading), or
"notes" (no heading)}. An item is its line, or {"text": its line, and maybe:
  "needs": what an edition must have to hear of it, each word "<kind>:<key>" (one of the
           kind, e.g. "scenery:aurora") or "<kind>" (any of it) - an edition without it
           never lists it (the public page is the base edition's); "edition:<name>" keeps it to
           that edition alone, e.g. "edition:base" for news of the free edition only;
  "plus": its name in the line that closes the version's notes in an edition without it, "Also
          new in Memory Forest Plus: Chalkboard and a new seaside landscape." (for_edition keeps those
          names as the version's "plus"; the AnkiWeb page leaves the line out, its own "New in
          Memory Forest Plus" pictures saying it);
  "announce": {"id", "kind": "note" (a card on the forest, once: "title", "text", and maybe a
              button, "action", that opens the settings where "opens" says, and "settings":
              the settings that wear NEW for two weeks, by the tabs' news_targets keys) or "dot" (the
              cog's dot, and NEW on the tile of the scenery it `needs`, if it needs one) or
              "improved" (IMPROVED on the tiles of its "sceneries", with no dot). A tile's NEW or
              IMPROVED stays until that scenery is picked or two weeks pass}}."""

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
    has (None: every one there is), e.g. {"scenery": its preset keys, "edition": {"base"}}."""
    for need in (item(entry).get("needs") or "").split():
        kind, _, key = need.partition(":")
        got = have.get(kind, set())
        if got is not None and not (key in got if key else got):
            return False
    return True


def for_edition(versions: list, have: dict) -> list:
    """The notes as an edition sees them: without the items it lacks (an emptied list goes), the
    names of those Plus has kept as the version's "plus" (with any it had already)."""
    out = []
    for v in versions:
        kept = {"version": v["version"]}
        if v.get("summary"):
            kept["summary"] = v["summary"]
        plus = list(v.get("plus", []))
        for key, _head in SECTIONS:
            items = [e for e in v.get(key, []) if has(e, have)]
            plus += [item(e)["plus"] for e in v.get(key, []) if not has(e, have) and item(e).get("plus")]
            if items:
                kept[key] = items
        if plus:
            kept["plus"] = list(dict.fromkeys(plus))
        out.append(kept)
    return out


def plus_line(version: dict) -> str:
    """The line that closes a version's notes where Plus got more: "Also new in Memory Forest
    Plus: Chalkboard and a new seaside landscape." ("" where it got nothing more)."""
    names = version.get("plus") or []
    if not names:
        return ""
    said = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"Also new in Memory Forest Plus: {said}."


def items(version: dict, sections=tuple(k for k, _h in SECTIONS)) -> list:
    """Every item of a version, as dicts, in the order of its lists."""
    return [item(e) for key in sections for e in version.get(key, [])]


def to_html(versions: list) -> str:
    """The AnkiWeb page's What's new, between HTML_START and HTML_END, each version closing with
    what Plus got more (plus_line), as the add-on's own notes do."""
    out = []
    for v in versions:
        out.append(f"<i>{v['version']}</i>")
        if v.get("summary"):
            out.append(f"<div>{v['summary']}</div>")
        for key, head in SECTIONS:
            if v.get(key):
                if head:
                    out.append(f"<div><b>{head}</b></div>")
                out.append("<ul>")
                out += [f"<li>{item(e)['text']}</li>" for e in v[key]]
                out.append("</ul>")
        if plus_line(v):
            out.append(f"<div>{plus_line(v)}</div>")
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
    lines = [_markdown(v["summary"])] if v.get("summary") else []
    for key, head in SECTIONS:
        if v.get(key):
            if head:
                lines += ([""] if lines else []) + [f"### {head}", ""]
            lines += ["- " + _markdown(item(e)["text"]) for e in v[key]]
    if plus_line(v):
        lines += ([""] if lines else []) + [_markdown(plus_line(v))]
    return "\n".join(lines) + "\n"

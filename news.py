"""What's new: how an update tells people about itself, without a patch-notes dialog.

Most changes say nothing (fixes, speed, where the weather comes from). A new scenery puts a
dot on the forest's cog, and a NEW tag on its tile for the visit that clears it. A real
feature gets a note: one card on the forest, shown once. The About tab lists the newest
version's new and improved lines. All of it comes from release_notes.json (an item's
"announce"), and each person only hears about what their edition has; a fresh install
hears about nothing: it is all new to them.

What has been seen is kept in user_files/news.json (for the whole install, not per profile)."""

from __future__ import annotations

import datetime as _dt
import os

from . import presets, release_notes, state
from .state import USER_FILES, debug_available, debug_edition, edition_presets, log
from .store import load_json, save_json

NEWS_PATH = os.path.join(USER_FILES, "news.json")
NOTE_DAYS = 3  # a note nobody answers goes by itself after this many days

NOTE, DOT = "note", "dot"
# made up, to try the note and the dot with the Debug tab's replays (only while debug is on).
# The Debug tab's "Show it as new" points the note at any setting (debug_show).
DEBUG_NOTE = "debug_note"
DEBUG_NEWS = (
    {"needs": "", "announce": {"id": DEBUG_NOTE, "kind": NOTE, "title": "New: a test note",
                               "text": "Made up, and only here while debug is on. The button opens the About tab.",
                               "action": "Open the About tab", "opens": "about"}},
    {"needs": "scenery:bamboo", "announce": {"id": "debug_scenery", "kind": DOT}},
)

def _versions() -> list:
    return release_notes.load()


def view(cfg: dict) -> dict:
    """What this copy has (or the edition the Debug tab pretends it is), as release_notes.has takes it."""
    here = set(presets.by_key())
    ships = edition_presets(debug_edition(cfg))
    return {"scenery": here if ships is None else here & ships}


def _items(cfg: dict | None = None) -> list:
    """Every item that announces something, newest first (the debug ones last), and only
    those the edition has when `cfg` is given."""
    found = [e for v in _versions() for e in release_notes.items(v)]
    if cfg is None or debug_available(cfg):
        found += list(DEBUG_NEWS)
    found = [e for e in found if isinstance(e.get("announce"), dict) and e["announce"].get("id")]
    return found if cfg is None else [e for e in found if release_notes.has(e, view(cfg))]


def _scenery(entry: dict) -> str:
    """The preset key a dot announces: the scenery its item needs."""
    return next((n.split(":", 1)[1] for n in (entry.get("needs") or "").split() if n.startswith("scenery:")), "")


def offered(cfg: dict) -> list:
    """What this edition can hear of: each announcement, with the scenery a dot is for."""
    return [dict(e["announce"], scenery=_scenery(e)) for e in _items(cfg)]


def _all_ids() -> list:
    return [e["announce"]["id"] for e in _items()]


def _load() -> dict:
    """{"seen": [ids], "shown": {id: the day its note first showed}}. With no file yet, a copy
    that has kept nothing of its own (no state.json) is a fresh install: it has seen it all."""
    if not os.path.exists(NEWS_PATH):
        fresh = not load_json(state.STATE_PATH)
        record = {"seen": _all_ids() if fresh else [], "shown": {}}
        _save(record)
        return record
    record = load_json(NEWS_PATH)
    seen = record.get("seen")
    shown = record.get("shown")
    return {"seen": [s for s in seen if isinstance(s, str)] if isinstance(seen, list) else [],
            "shown": shown if isinstance(shown, dict) else {},
            "debug": record.get("debug") if isinstance(record.get("debug"), dict) else None}


def _save(record: dict) -> None:
    try:
        save_json(NEWS_PATH, record)
    except OSError:
        log(f"could not save {NEWS_PATH}")


def mark_seen(ids) -> None:
    record = _load()
    known = set(_all_ids())
    new = [i for i in ids if i in known and i not in record["seen"]]
    if new:
        record["seen"] += new
        _save(record)


def note(cfg: dict, day: _dt.date) -> dict | None:
    """The note for the forest on the deck list: the newest one not yet seen, or None. Only
    one at a time; one nobody answers goes after NOTE_DAYS, and an older one waiting behind a
    newer one is only ever listed in the About tab."""
    notes = [e for e in offered(cfg) if e["kind"] == NOTE]
    record = _load()
    entry = _debug_pick(notes, record) or next((e for e in notes if e["id"] != DEBUG_NOTE), None)
    if entry is None:
        entry = next((e for e in notes if e["id"] == DEBUG_NOTE), None)  # (only while debug is on)
    if entry is None or entry["id"] in record["seen"]:
        return None
    try:
        first = _dt.date.fromisoformat(record["shown"].get(entry["id"]) or "")
    except (TypeError, ValueError):
        first = None
    if first is None or first > day:  # (a debug date moved back starts it over)
        record["shown"][entry["id"]] = day.isoformat()
        _save(record)
    elif (day - first).days >= NOTE_DAYS:
        mark_seen([entry["id"]])
        return None
    return {"id": entry["id"], "title": entry.get("title", ""), "text": entry.get("text", ""), "action": entry.get("action", "")}


def _debug_pick(notes: list, record: dict) -> dict | None:
    """The note the Debug tab's "Show it as new" asked for, if debug is on (the debug note
    is only offered then): a real one again, or the made-up one pointing at a setting."""
    pick = record.get("debug")
    if not isinstance(pick, dict) or not any(e["id"] == DEBUG_NOTE for e in notes):
        return None
    if pick.get("show"):
        return next((e for e in notes if e["id"] == pick["show"]), None)
    if pick.get("opens"):
        return {"id": DEBUG_NOTE, "kind": NOTE, "title": f"New: {pick.get('name') or pick['opens']}",
                "text": "Made up, while debug is on. The button opens that setting, tagged NEW.",
                "action": "Show me", "opens": pick["opens"]}
    return None


def dots(cfg: dict) -> list:
    """The preset keys of the new sceneries this edition has, not yet seen: the cog's dot."""
    seen = set(_load()["seen"])
    return [e["scenery"] for e in offered(cfg) if e["kind"] == DOT and e["scenery"] and e["id"] not in seen]


def settings_opened(cfg: dict) -> list:
    """The settings are open: the cog's dot is answered. The sceneries it was for wear their
    NEW tag for this visit only (returned)."""
    keys = dots(cfg)
    if keys:
        mark_seen([e["id"] for e in offered(cfg) if e["kind"] == DOT and e["scenery"] in keys])
    return keys


def opens(news_id: str) -> str:
    """Where a note's button opens the settings: a tab ("general", "fine", "history",
    "about"), a setting one of them names (their news_targets, e.g. "animations"), or ""."""
    pick = _load().get("debug")
    if news_id == DEBUG_NOTE and isinstance(pick, dict) and pick.get("opens"):
        return pick["opens"]
    return next((e["announce"].get("opens", "") for e in _items() if e["announce"]["id"] == news_id), "")


def about(cfg: dict) -> list:
    """(version, [lines]) for the About tab, newest first: each version's new and improved
    lines this edition has (its fixes stay in the release notes)."""
    out = []
    for v in release_notes.for_edition(_versions(), view(cfg)):
        lines = [e["text"] for e in release_notes.items(v, ("new", "improved"))]
        if lines:
            out.append((v["version"], lines))
    return out


def unseen(cfg: dict) -> list:
    """The notes and dots this edition still has to show (the Debug tab says which)."""
    seen = set(_load()["seen"])
    return [e for e in offered(cfg) if e["id"] not in seen]


# the Debug tab's replays
def replay_update() -> None:
    """As someone who just updated: nothing seen yet."""
    _save({"seen": [], "shown": {}})


def replay_fresh() -> None:
    """As a fresh install: everything seen."""
    _save({"seen": _all_ids(), "shown": {}})


def debug_show(show: str = "", opens: str = "", name: str = "") -> None:
    """Show one note as new again, ahead of any other: a real one by its id (`show`), or the
    made-up one pointing at a setting (`opens`, called `name`)."""
    record = _load()
    shown_id = show or DEBUG_NOTE
    record["seen"] = [i for i in record["seen"] if i != shown_id]
    record["shown"].pop(shown_id, None)
    record["debug"] = {"show": show} if show else {"opens": opens, "name": name}
    _save(record)

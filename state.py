"""The add-on's config, and what it remembers between sessions: the settings as the user
set them, the per-profile state file, and which decks and days the forest counts."""

from __future__ import annotations

import datetime as _dt
import os

from aqt import mw

from . import study_log
from .store import load_json, save_json

ADDON_DIR = os.path.dirname(__file__)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
STATE_PATH = os.path.join(USER_FILES, "state.json")
MODULE = mw.addonManager.addonFromModule(__name__)

# The numbers a config can hold, however it was edited; the settings dialog offers the same ranges.
MAX_WIDTH_DEFAULT, MAX_WIDTH_MIN, MAX_WIDTH_MAX = 800, 400, 2000
TEST_TREES_DEFAULT, TEST_TREES_MAX = 150, 5000
# a hand-edited "false" (or 0) turns a switch off too
OFF_VALUES = (False, "false", "False", 0, "0")
# the note type of the note that takes the forest to your phone (phone.py)
PHONE_NOTETYPE = "Memory Forest"


def config() -> dict:
    return mw.addonManager.getConfig(MODULE) or {}


def save_config(cfg: dict) -> None:
    """Write the config, leaving out anything at its default (or no longer an option), so a
    better default in a later version still reaches people who never changed it."""
    known = mw.addonManager.addonConfigDefaults(MODULE) or {}
    mw.addonManager.writeConfig(MODULE, {k: v for k, v in cfg.items() if k in known and known[k] != v})


def log(msg: str) -> None:
    print(f"[anki_forest] {msg}")


def clamp_int(value, default: int, low: int, high: int) -> int:
    """A number from the config, however badly it was hand-edited."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _profile() -> str:
    """Anki day numbers and 'already planted today' only mean something within one
    collection, so the state file keeps a section per profile."""
    return getattr(getattr(mw, "pm", None), "name", None) or "User 1"


def load_state() -> dict:
    whole = load_json(STATE_PATH)
    mine = whole.get(_profile())
    return mine if isinstance(mine, dict) else {}


def save_state(state: dict) -> None:
    try:
        whole = load_json(STATE_PATH)
        whole[_profile()] = state
        save_json(STATE_PATH, whole)
    except OSError:
        pass


def excluded_decks(cfg: dict | None = None) -> set:
    """Every deck left out of the forest: the ones unticked in the settings and all their
    subdecks, found afresh each time, so a deck made or moved under one later is out too.
    The deck the add-on keeps for the note that takes the forest to your phone is always out
    (the note's cards themselves are left out wherever they are: see phone_cards)."""
    out = phone_decks()
    for did in (cfg if cfg is not None else config()).get("excluded_decks") or []:
        try:
            out.update(mw.col.decks.deck_and_child_ids(int(did)))
        except Exception:  # a hand edit, or a deck deleted since
            continue
    return out


# the deck phone.py makes for the note that takes the forest to your phone
PHONE_DECK = "Memory Forest"
# phone_decks' and phone_cards' last answers, and the collection and modification time they were for
_phone_decks: tuple = (None, None, frozenset())
_phone_cards: tuple = (None, None, frozenset())


def phone_decks() -> set:
    """The add-on's own deck for the note that carries the forest to your phone (phone.py),
    found by its name: the settings and the gear menu don't offer it, and it grows no forest.
    Never the deck its card happens to be in, which may be one of yours."""
    global _phone_decks
    try:
        col = mw.col
        mod = col.mod
        if _phone_decks[0] is col and _phone_decks[1] == mod:
            return set(_phone_decks[2])
        did = col.decks.id_for_name(PHONE_DECK)
        found = {did} if did else set()
    except Exception:  # no collection yet
        return set()
    _phone_decks = (col, mod, frozenset(found))
    return found


def phone_cards() -> set:
    """The cards of the note that carries the forest to your phone, wherever they are now,
    and every one it ever had here (remembered per profile once seen, since Anki keeps the
    reviews of a deleted card, and another computer's sync may be what deletes it): answering one is looking at the forest,
    not studying, so no review of theirs ever counts. Asked several times a redraw, so the
    answer is kept until the collection next changes."""
    global _phone_cards
    try:
        col = mw.col
        mod = col.mod
        if _phone_cards[0] is col and _phone_cards[1] == mod:
            return set(_phone_cards[2])
        m = col.models.by_name(PHONE_NOTETYPE)
        found = set(col.db.list("select id from cards where nid in (select id from notes where mid = ?)", m["id"])) if m else set()
    except Exception:  # no collection yet
        return set()
    if found:  # remembered as soon as seen, so a note deleted by a sync from elsewhere is too
        remember_phone_cards(found)
    found |= {c for c in load_state().get("phone_cards") or [] if isinstance(c, int)}
    _phone_cards = (col, mod, frozenset(found))
    return found


def remember_phone_cards(cids) -> None:
    """Keep leaving out the reviews of these cards once they are gone (see phone_cards)."""
    global _phone_cards
    state = load_state()
    known = {c for c in state.get("phone_cards") or [] if isinstance(c, int)}
    if set(cids) - known:
        state["phone_cards"] = sorted(known | set(cids))
        save_state(state)
    _phone_cards = (None, None, frozenset())


def since(cfg: dict) -> int | None:
    """When the forest begins (the Ignore before setting), as a timestamp, or None."""
    try:
        date = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
    except ValueError:
        return None
    return study_log.day_start(date, mw.col.sched.day_cutoff)


def keeps_suspended(cfg: dict | None = None) -> bool:
    """Whether suspended cards keep their trees (they do unless switched off)."""
    return (cfg if cfg is not None else config()).get("keep_suspended", True) not in OFF_VALUES


def deck_ids(did: int, excluded: set) -> list:
    """A deck and its subdecks, less those left out of the forest."""
    return [d for d in mw.col.decks.deck_and_child_ids(did) if d not in excluded]

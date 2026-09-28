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
    subdecks, found afresh each time, so a deck made or moved under one later is out too."""
    out = set()
    for did in (cfg if cfg is not None else config()).get("excluded_decks") or []:
        try:
            out.update(mw.col.decks.deck_and_child_ids(int(did)))
        except Exception:  # a hand edit, or a deck deleted since
            continue
    return out


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

"""The add-on's config, and what it remembers between sessions: the settings as the user
set them, and the per-profile state file."""

from __future__ import annotations

import os

from aqt import mw

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


# whether the settings dialog is up (settings sets it): what it previews is not a real change,
# so nothing in it is remembered as shown
_settings_open = False


def settings_open() -> bool:
    return _settings_open


def set_settings_open(is_open: bool) -> None:
    global _settings_open
    _settings_open = is_open


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


# answers kept until what they were worked out from changes: {name: (key, answer)}
_remembered: dict = {}


def remembered(name: str, key, work):
    """work(), or the answer it gave last time for `name` if `key` is the same (and not None:
    then it is worked out afresh). One answer is kept per name."""
    hit = _remembered.get(name)
    if key is not None and hit and hit[0] == key:
        return hit[1]
    answer = work()
    _remembered[name] = (key, answer)
    return answer


def forget_remembered() -> None:
    _remembered.clear()


# "Animate the forest": the config holds true, false or "system" (still while the system asks
# for reduced motion), and the page gets the same
ANIMATION_VALUES = {"on": True, "off": False, "system": "system"}


def animation_mode(cfg: dict | None = None) -> str:
    """"on", "off" or "system": how the forest animates (on unless set otherwise)."""
    value = (cfg if cfg is not None else config()).get("animations", True)
    return "system" if value == "system" else "off" if value in OFF_VALUES else "on"


def keeps_suspended(cfg: dict | None = None) -> bool:
    """Whether suspended cards keep their trees (they do unless switched off)."""
    return (cfg if cfg is not None else config()).get("keep_suspended", True) not in OFF_VALUES


def shows_on_deck_list(cfg: dict | None = None) -> bool:
    """Whether the forest is drawn on the deck list (it is unless switched off); a deck's
    own screen goes by the Deck screens setting instead."""
    return (cfg if cfg is not None else config()).get("main_forest", True) not in OFF_VALUES



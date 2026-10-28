"""The add-on's config, and what it remembers between sessions: the settings as the user
set them, and the per-profile state file."""

from __future__ import annotations

import datetime as _dt
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
# where the forest and the heatmap sit round the deck list (Forest tab, Layout): both under it (as it
# has always been), both beside it (on Layout's Side), one beside it and the other under it, or one
# above it and the other under it. First (layout_first, the forest unless chosen) is the one that gets
# the place: beside the list or above it; and their order wherever they stand together (under or
# beside the list, a deck's screen, a window too narrow to put them beside it). Each layout's places
# for (the first, the other), "side" being Side.
LAYOUTS = {
    "under": ("below", "below"),
    "beside": ("side", "side"),
    "one_beside": ("side", "below"),
    "above": ("above", "below"),
}
LAYOUT_DEFAULT, LAYOUT_SIDES, LAYOUT_FIRST = "under", ("right", "left"), ("forest", "heatmap")
# the heatmap's size (Heatmap tab, Layout: Width and Fill it with). Width: fixed (680 px, 85% of the
# default Forest width), the forest's (the default), or full (all the room its place has); never wider
# than its room. Fill it with: more days (its days one size, Timeline showing as many months as its
# width holds) or bigger days (ten months, or the year, stretched over its width)
CALENDAR_WIDTHS = ("fixed", "forest", "full")
CALENDAR_FILLS = ("more", "bigger")
# a hand-edited "false" (or 0) turns a switch off too
OFF_VALUES = (False, "false", "False", 0, "0")


def config() -> dict:
    return mw.addonManager.getConfig(MODULE) or {}


def storage_writable() -> bool:
    """Whether the add-on can keep anything. Under Nix its folder, user_files and all, is in the
    read-only store, and Anki warns instead of saving the config: there what changes on its own
    (a holiday's scenery) is applied in memory on each build, never saved."""
    return os.access(USER_FILES if os.path.isdir(USER_FILES) else ADDON_DIR, os.W_OK)


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


# the study calendar (web/calendar.js): its view, and the screens it shows on, each its own setting
# (with or without the forest above it)
CALENDAR_VIEWS = ("timeline", "by_year", "streak")
CALENDAR_SCREENS = {"main": "calendar_main", "decks": "calendar_decks"}
CALENDAR_SHADES = ("reviews", "time", "median")


def calendar_shade(cfg: dict | None = None) -> str:
    """Heatmap shading: review count, total time, or median seconds per answer (Pace)."""
    value = (cfg if cfg is not None else config()).get("calendar_shade", "reviews")
    return value if value in CALENDAR_SHADES else "reviews"


def calendar_view(cfg: dict | None = None) -> str:
    """The study calendar's view: Timeline ("timeline": a year with this month most of the way
    along), By year ("by_year": January to December) or Streak ("streak": every year of your
    streak, the arrows stepping to the streaks before it)."""
    value = (cfg if cfg is not None else config()).get("calendar", "timeline")
    return value if value in CALENDAR_VIEWS else "timeline"


def shows_on_finished(cfg: dict | None = None) -> bool:
    """Whether a deck you have finished (Anki's congratulations page) shows what the deck
    screens do (panel.on_page_loaded). It does unless switched off."""
    return (cfg if cfg is not None else config()).get("finished_decks", True) not in OFF_VALUES


def shows_record(cfg: dict | None = None) -> bool:
    """Whether the study calendar shows your reviews from before the start date too (Heatmap tab:
    "Start date: Show the reviews from before it"). It does unless switched off."""
    return (cfg if cfg is not None else config()).get("calendar_record", True) not in OFF_VALUES


def keeps_earlier_trees(cfg: dict | None = None) -> bool:
    """Whether the trees from before the start date grow all the same, and only the ponds, Nature
    and the animals count from it (Decks tab: "Keep the trees from before it"). Off unless
    switched on: a start date leaves the days before it out."""
    value = (cfg if cfg is not None else config()).get("keep_earlier_trees", False)
    return bool(value) and value not in OFF_VALUES


def streak_from_start(cfg: dict | None = None) -> bool:
    """Whether the streak starts again at the start date (Heatmap tab: "Count your
    streak from: The start date"); off unless switched on, so a start date leaves your streak whole."""
    value = (cfg if cfg is not None else config()).get("streak_from_start", False)
    return bool(value) and value not in OFF_VALUES


# how many days a week the streak counts (the Heatmap tab): every day, or 6 or 5, the rest of a
# week's missed days passed over (forest_data.days_off), from the day it was chosen
# (`streak_week_since`, kept by the dialog), never back in time
STREAK_WEEKS = (7, 6, 5)


def streak_week(cfg: dict | None = None) -> int:
    """The days a week your streak counts: 7 (every day, the default), 6 or 5."""
    value = (cfg if cfg is not None else config()).get("streak_week", 7)
    return value if value in STREAK_WEEKS and not isinstance(value, bool) else 7


def streak_week_since(cfg: dict | None = None) -> _dt.date | None:
    """The day a streak of fewer than 7 days a week was chosen (its first day off), or None."""
    try:
        return _dt.date.fromisoformat(str((cfg if cfg is not None else config()).get("streak_week_since") or ""))
    except ValueError:
        return None


# the day the study calendar's weeks start on: the system's own (its region's), or one chosen,
# by the day as the page counts them (Sunday 0)
WEEK_START_DAYS = {"monday": 1, "sunday": 0, "saturday": 6}
WEEK_STARTS = ("system", *WEEK_START_DAYS)


def week_start(cfg: dict | None = None) -> str:
    """The study calendar's week start setting: "system" unless one of WEEK_STARTS is chosen."""
    value = (cfg if cfg is not None else config()).get("calendar_week_start", "system")
    return value if value in WEEK_STARTS else "system"


def calendar_on(screen: str, cfg: dict | None = None) -> bool:
    """Whether the study calendar shows on the main screen (`screen` "main") or the deck
    screens ("decks"). It does unless switched off."""
    return (cfg if cfg is not None else config()).get(CALENDAR_SCREENS[screen], True) not in OFF_VALUES


def layout_key(cfg: dict | None = None) -> str:
    """The Layout chosen (LAYOUTS), or the default for anything else a hand edit left."""
    key = (cfg if cfg is not None else config()).get("layout", LAYOUT_DEFAULT)
    return key if isinstance(key, str) and key in LAYOUTS else LAYOUT_DEFAULT


def layout_side(cfg: dict | None = None) -> str:
    """The side Beside's column stands on: right (the default) or left."""
    side = (cfg if cfg is not None else config()).get("layout_side", "right")
    return side if side in LAYOUT_SIDES else "right"


def layout_first(cfg: dict | None = None) -> str:
    """Layout's First: the forest (the default) or the heatmap, first where the two stand together,
    and the one over the deck list with Above the list."""
    first = (cfg if cfg is not None else config()).get("layout_first", "forest")
    return first if first in LAYOUT_FIRST else "forest"


def layout(cfg: dict | None = None, deck_screen: bool = False) -> dict:
    """Where the page puts the forest and the heatmap (web/core.js AF.arrange): each one's place
    round the deck list ("below", "above", "left" or "right"), the First's from the layout's first
    place, and which comes first where they stand together. Their widths come from the Forest width
    and the Heatmap tab's Width (web/core.js). A deck's screen, the finished-deck page, Onigiri's tile
    and the phone keep them stacked under what they have, in the First order, so a deck screen is sent
    no other place."""
    cfg = cfg if cfg is not None else config()
    first = layout_first(cfg)
    if deck_screen:
        return {"forest": "below", "heatmap": "below", "first": first}
    places = [layout_side(cfg) if p == "side" else p for p in LAYOUTS[layout_key(cfg)]]
    forest, heatmap = places if first == "forest" else places[::-1]
    return {"forest": forest, "heatmap": heatmap, "first": first}


def calendar_width(cfg: dict | None = None) -> str:
    """The heatmap's Width: fixed, forest (the default) or full."""
    width = (cfg if cfg is not None else config()).get("calendar_width", "forest")
    return width if width in CALENDAR_WIDTHS else "forest"


def calendar_fill(cfg: dict | None = None) -> str:
    """What fills the heatmap's width: more days (the default) or bigger days."""
    fill = (cfg if cfg is not None else config()).get("calendar_fill", "more")
    return fill if fill in CALENDAR_FILLS else "more"


def shows_on_deck_list(cfg: dict | None = None) -> bool:
    """Whether the forest is drawn on the deck list (it is unless switched off); a deck's
    own screen goes by the Deck screens setting instead."""
    return (cfg if cfg is not None else config()).get("main_forest", True) not in OFF_VALUES

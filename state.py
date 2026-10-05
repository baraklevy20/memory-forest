"""The add-on's config, and what it remembers between sessions: the settings as the user
set them, the per-profile state file, and which decks and days the forest counts."""

from __future__ import annotations

import datetime as _dt
import json
import os

from aqt import mw

from . import events, presets, study_log
from .store import load_json, save_json

ADDON_DIR = os.path.dirname(__file__)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
STATE_PATH = os.path.join(USER_FILES, "state.json")
# the seasonal scenery's record: shared by every profile, as the look settings are
SEASON_PATH = os.path.join(USER_FILES, "season.json")
MODULE = mw.addonManager.addonFromModule(__name__)

# The numbers a config can hold, however it was edited; the settings dialog offers the same ranges.
MAX_WIDTH_DEFAULT, MAX_WIDTH_MIN, MAX_WIDTH_MAX = 800, 400, 2000
TEST_TREES_DEFAULT, TEST_TREES_MAX = 150, 5000
# a hand-edited "false" (or 0) turns a switch off too
OFF_VALUES = (False, "false", "False", 0, "0")
# the note type of the note that takes the forest to your phone (phone.py)
PHONE_NOTETYPE = "Memory Forest"
# the "Show my forest on my phone" switch, in the collection's own config: one per profile,
# synced with it, so every computer (and both editions) sees the same
PHONE_SWITCH = "memoryForestPhone"


def config() -> dict:
    return mw.addonManager.getConfig(MODULE) or {}


def phone_on(col=None) -> bool:
    """Whether the forest goes to the phone in this collection."""
    col = mw.col if col is None else col
    return col is not None and col.get_config(PHONE_SWITCH, False) not in OFF_VALUES


def set_phone_on(on: bool, col=None) -> None:
    col = mw.col if col is None else col
    if col is not None:
        col.set_config(PHONE_SWITCH, bool(on))


def save_config(cfg: dict) -> None:
    """Write the config, leaving out anything at its default (or no longer an option), so a
    better default in a later version still reaches people who never changed it."""
    known = mw.addonManager.addonConfigDefaults(MODULE) or {}
    mw.addonManager.writeConfig(MODULE, {k: v for k, v in cfg.items() if k in known and known[k] != v})


def debug_available(cfg: dict | None = None) -> bool:
    """Whether debug is on and this copy has the debug tools to go with it: a release ships
    without them (dev/package.py), and debug turned on by hand there changes nothing."""
    cfg = config() if cfg is None else cfg
    return bool(cfg.get("debug", False)) and os.path.exists(os.path.join(ADDON_DIR, "debug_events.py"))


# the editions the Debug tab can pretend this copy is (editions.json, which only this copy has)
EDITIONS_FILE = os.path.join(ADDON_DIR, "editions.json")
DEBUG_EDITIONS = ("base", "plus")


def debug_edition(cfg: dict | None = None) -> str:
    """While debug is on, the edition this copy pretends to be ("base" or "plus"), or "" for
    itself: every scenery here, and its own manifest's say on whether it is Plus."""
    cfg = config() if cfg is None else cfg
    edition = cfg.get("debug_edition") or ""
    return edition if edition in DEBUG_EDITIONS and debug_available(cfg) else ""


def edition_presets(edition: str) -> set | None:
    """The preset keys `edition` ships, from editions.json, or None for every one here (no
    edition, or no editions.json to read it from)."""
    if not edition:
        return None
    try:
        with open(EDITIONS_FILE, encoding="utf-8") as f:
            envs = json.load(f)[edition]["envs"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {p.key for p in presets.FOREST_PRESETS
            if envs == "*" or p.environment in envs or p.key == presets.DAILY}


def today(cfg: dict | None = None) -> _dt.date:
    """The date the scenery is chosen for: today, or while debug is on, the debug date
    (if one is set) moved on by the days passed on the test forest's timeline - so passing
    a week there also carries a holiday's week over, as it would in real days."""
    cfg = config() if cfg is None else cfg
    day = _dt.date.today()
    if not debug_available(cfg):
        return day
    try:
        day = _dt.date.fromisoformat(cfg.get("debug_date") or "") or day
    except (TypeError, ValueError):
        pass
    if cfg.get("test_forest"):  # the timeline passes days only on the test forest
        day += _dt.timedelta(days=events.timeline_days(events.timeline_steps(cfg.get("debug_timeline")))[0])
    return day


def follow_season(cfg: dict, day: _dt.date | None = None) -> dict:
    """The config, changed to a seasonal preset in its week and back after it (see
    presets.follow_season), and saved if it changed."""
    day = day or today(cfg)
    record = load_json(SEASON_PATH)
    change, kept = presets.follow_season(cfg, record, day)
    if kept != record:
        try:
            save_json(SEASON_PATH, kept)
        except OSError:
            log(f"could not save {SEASON_PATH}")
    if change and any(cfg.get(k) != v for k, v in change.items()):
        cfg = dict(cfg, **change)
        save_config(cfg)
    return cfg


def forget_seasons() -> None:
    """Let every holiday's week change the scenery again (the Debug tab's replay)."""
    try:
        save_json(SEASON_PATH, {})
    except OSError:
        log(f"could not save {SEASON_PATH}")


def season_returns(cfg: dict, today: _dt.date) -> _dt.date | None:
    """The day the scenery from before comes back, while a seasonal preset stands in for it."""
    active = load_json(SEASON_PATH).get("active")
    now = presets.in_season(today)
    if not (now and isinstance(active, dict) and active.get("tag") == f"{now.key}:{today.year}"):
        return None
    if {k: cfg.get(k) for k in presets.LOOK} != active.get("applied") or active.get("before") == active.get("applied"):
        return None
    return presets.season_ends(now, today)


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


def changes():
    """Where the study data stands, read cheaply (a few ms on a big collection): the newest
    review, and the latest change to any card or note - but the note that carries the forest
    to your phone and its cards, which the add-on rewrites itself at every sync. What the
    forest is built from can only have changed if this has. (The collection's own modified
    time changes far more often - picking a deck, the phone's note - and each change used to
    cost a whole rebuild.) None when the collection can't say."""
    col = mw.col
    if col is None:
        return None
    cids = ",".join(str(int(c)) for c in phone_cards())
    not_phone = f" where id not in ({cids})" if cids else ""
    not_phone_note = f" where id not in (select nid from cards where id in ({cids}))" if cids else ""
    try:
        return (getattr(col, "path", None) or id(col), col.db.scalar("select max(id) from revlog"),
                *col.db.all(f"select max(mod), count() from cards{not_phone}")[0],
                col.db.scalar(f"select max(mod) from notes{not_phone_note}"))
    except Exception:  # an older or unusual collection: rebuild every time, as before
        return None


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


def remember_phone_cards(cids) -> None:
    """Keep leaving out the reviews of these cards once they are gone (see phone_cards)."""
    global _phone_cards
    state = load_state()
    known = {c for c in state.get("phone_cards") or [] if isinstance(c, int)}
    if set(cids) - known:
        state["phone_cards"] = sorted(known | set(cids))
        save_state(state)
    _phone_cards = (None, None, frozenset())


def day_cutoff(col) -> int:
    """When the collection's day ends, as a timestamp: the scheduler's day_cutoff, which
    Anki before 2.1.50 calls dayCutoff."""
    sched = col.sched
    return sched.day_cutoff if hasattr(sched, "day_cutoff") else sched.dayCutoff


def since(cfg: dict) -> int | None:
    """When the forest begins (the Ignore before setting), as a timestamp, or None."""
    try:
        date = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
    except ValueError:
        return None
    return study_log.day_start(date, day_cutoff(mw.col))


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


def deck_ids(did: int, excluded: set) -> list:
    """A deck and its subdecks, less those left out of the forest."""
    return [d for d in mw.col.decks.deck_and_child_ids(did) if d not in excluded]

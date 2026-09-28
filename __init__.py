"""
Memory Forest - a passive forest that grows from your study history.

Each day you learn new cards plants one tree below the deck list. Trees grow as
those cards settle into long-term memory, and yellow a little when some of them are
forgotten. Nothing to click: the forest just grows.
"""

from __future__ import annotations

import datetime as _dt
import inspect
import json
import os
import time
import traceback

from anki.collection import SearchNode
from aqt import dialogs, gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.utils import tooltip

from . import forest_data, presets, scene
from .store import load_json, save_json
from .weather import WeatherCache

ADDON_DIR = os.path.dirname(__file__)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
STATE_PATH = os.path.join(USER_FILES, "state.json")
MODULE = mw.addonManager.addonFromModule(__name__)
WEB = f"/_addons/{MODULE}/web"
SCRIPTS = ("core.js", "effects.js", "engines/pixel.js")
BOOT = "forest.js"  # mounts straight away, so it goes last of all
WEB_DIR = os.path.join(ADDON_DIR, "web")

# The numbers a config can hold, however it was edited; the settings dialog offers the same ranges.
MAX_WIDTH_DEFAULT, MAX_WIDTH_MIN, MAX_WIDTH_MAX = 800, 400, 2000
TEST_TREES_DEFAULT, TEST_TREES_MAX = 150, 5000
# a hand-edited "false" (or 0) turns a switch off too
OFF_VALUES = (False, "false", "False", 0, "0")
# on a deck screen the test forest lights every this-many-th tree, having no real decks
TEST_LIT_EVERY = 5
PLANTING_TOOLTIP_MS = 3500

mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css)")

_weather = WeatherCache(os.path.join(USER_FILES, "weather.json"))
_forest_cache: dict = {}
_refreshing = False
_planted_today: str | None = None


def config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


def _log(msg: str) -> None:
    print(f"[anki_forest] {msg}")


def _int(value, default: int, low: int, high: int) -> int:
    """A number from the config, however badly it was hand-edited."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _profile() -> str:
    """Anki day numbers and 'already planted today' only mean something within one
    collection, so the state file keeps a section per profile."""
    return getattr(getattr(mw, "pm", None), "name", None) or "User 1"


def _load_state() -> dict:
    whole = load_json(STATE_PATH)
    mine = whole.get(_profile())
    return mine if isinstance(mine, dict) else {}


def _save_state(state: dict) -> None:
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


def _since(cfg: dict) -> int | None:
    """When the forest begins (the Ignore before setting), as a timestamp, or None."""
    try:
        date = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
    except ValueError:
        return None
    return forest_data.day_start(date, mw.col.sched.day_cutoff)


def keeps_suspended(cfg: dict | None = None) -> bool:
    """Whether suspended cards keep their trees (they do unless switched off)."""
    return (cfg if cfg is not None else config()).get("keep_suspended", True) not in OFF_VALUES


def _deck_ids(did: int, excluded: set) -> list:
    """A deck and its subdecks, less those left out of the forest."""
    return [d for d in mw.col.decks.deck_and_child_ids(did) if d not in excluded]


def _forest(did: int | None = None) -> dict:
    """Forest data for the whole collection, or one deck and its subdecks. Recomputed
    only when the collection, the day or the decks and dates it counts change."""
    col = mw.col
    cfg = config()
    cutoff = col.sched.day_cutoff
    excluded, since, suspended = excluded_decks(cfg), _since(cfg), keeps_suspended(cfg)
    mod = getattr(col, "mod", None)
    key = (mod, cutoff, frozenset(excluded), since, suspended)
    cached = _forest_cache.get(did)
    if mod is not None and cached and cached[0] == key:
        return cached[1]
    started = time.perf_counter()
    dids = _deck_ids(did, excluded) if did else None
    rows = forest_data.load_rows(col.db, cutoff, dids, excluded=excluded, since=since, suspended=suspended)
    value = forest_data.build_forest(rows, cutoff, col.sched.today, time.time())
    _log(f"built {len(value['trees'])} trees{f' for deck {did}' if did else ''} in {(time.perf_counter() - started) * 1000:.0f} ms")
    _forest_cache[did] = (key, value)
    return value


def _maybe_refresh_weather(city: str) -> None:
    global _refreshing
    if _refreshing or not _weather.needs_refresh(city):
        return
    _refreshing = True

    def done(future) -> None:
        global _refreshing
        _refreshing = False
        try:
            result = future.result()
        except Exception:
            return
        if result is not None and mw.state == "deckBrowser":
            refresh()

    # the weather needs no collection, so it need not wait for one - where this Anki can
    # be told so (older ones take no `uses_collection`)
    extra = {"uses_collection": False} if "uses_collection" in inspect.signature(mw.taskman.run_in_background).parameters else {}
    mw.taskman.run_in_background(lambda: _weather.refresh(city), done, **extra)


def _new_ancient_today(forest: dict, today: _dt.date) -> bool:
    """True on the day a tree first turns ancient (remembered across restarts in user_files)."""
    state = _load_state()
    days = sorted(t["day"] for t in forest["trees"] if t["stage"] == forest_data.ANCIENT)
    known = state.get("ancient_days")
    if known is None:  # first run: remember what exists, don't celebrate all of it at once
        state["ancient_days"] = days
        _save_state(state)
        return False
    if set(days) - set(known):
        # the ones known before stay known: a deck left out and brought back again, or an
        # earlier start date, must not celebrate its old ancient trees a second time
        state.update(ancient_days=sorted(set(days) | set(known)), ancient_event=today.isoformat())
        _save_state(state)
    return state.get("ancient_event") == today.isoformat()


def _lit_by_deck(forest: dict, did: int, test: bool) -> dict:
    """The main forest with each tree marked dim unless it holds some of this deck's cards."""
    if test:
        lit = {t["ago"] for t in forest["trees"][::TEST_LIT_EVERY]}
    else:
        dids = _deck_ids(did, excluded_decks())
        lit = forest_data.load_deck_days(mw.col.db, mw.col.sched.day_cutoff, dids, keeps_suspended())
    trees = [dict(t, dim=t["ago"] not in lit) for t in forest["trees"]]
    return dict(forest, trees=trees, lit_count=sum(1 for t in trees if not t["dim"]))


def _payload(did: int | None = None, highlight: bool = False) -> dict:
    cfg = config()
    # the test forest is a developer's tool, so it only exists while debug is on
    test = bool(cfg.get("debug", False)) and bool(cfg.get("test_forest", False))
    forest = forest_data.fake_forest(_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX)) if test else _forest(None if highlight else did)
    if highlight and did:
        forest = _lit_by_deck(forest, did, test)
    now = _dt.datetime.now()
    today = now.date()
    all_trees = forest["trees"]
    ann_all = forest_data.anniversaries(all_trees, today)
    new_ancient = False if test or (did and not highlight) else _new_ancient_today(forest, today)

    forest = forest_data.merge_old(forest)  # the oldest trees become one deep-forest band
    drawn = len(forest["trees"])
    merged_count = len(all_trees) - drawn
    # the page can only glow trees it draws; the journal still names any of them
    ann = [i - merged_count for i in ann_all if i >= merged_count]

    city = (cfg.get("city") or "").strip()
    real = place = None
    weather_error = ""
    if city and (cfg.get("weather") or "auto") == "auto":
        real, place = _weather.current(city), _weather.place(city)
        if real is None:  # say so, instead of quietly looking like no city was ever set
            weather_error = _weather.failing(city)
        _maybe_refresh_weather(city)

    mood = scene.choose_mood(cfg, now, real, place)
    evs = scene.events(forest["stats"], today, new_ancient)

    return {
        "trees": forest["trees"],
        "stats": forest["stats"],
        "visitors": forest["visitors"],
        "anniversaries": ann,
        "mood": mood,
        "journal": scene.journal(dict(forest, trees=all_trees), mood, today, ann_all, evs),
        "events": evs,
        "merged": forest.get("merged"),
        "forestSeed": forest["forest_seed"],
        "dayNumber": today.toordinal(),  # the animals take new places each day
        "testForest": test,
        "animations": cfg.get("animations", True) not in OFF_VALUES,
        "tooltips": True,
        "maxWidth": _int(cfg.get("max_width"), MAX_WIDTH_DEFAULT, MAX_WIDTH_MIN, MAX_WIDTH_MAX),
        "credit": mood.get("source") == "real",
        "weatherError": weather_error,
        "environmentName": scene.ENVIRONMENTS[mood["environment"]],
        **_scene_name(cfg, today),
        "inAnki": True,
        "channel": MODULE,  # clicks go back as "<channel>:...", so only this add-on answers them
        "deckId": did,
        "deckName": mw.col.decks.name_if_exists(did) if did else None,
        "highlight": bool(highlight and did),
        "litCount": forest.get("lit_count"),
    }


def _scene_name(cfg: dict, today: _dt.date) -> dict:
    """What the caption calls the scene: the preset's name, today's pick for Surprise me
    daily, or nothing for the plain default."""
    key = presets.match(cfg)
    if key == presets.FOREST_PRESETS[0].key:
        return {}
    if key == "daily":
        pick = presets.of_the_day(today)
        return {"sceneName": pick.label, "sceneTip": "Today's preset, from Surprise me daily. Tomorrow brings the next one."}
    if key == presets.CUSTOM:
        name = scene.ENVIRONMENTS.get(cfg.get("environment"), "")
        return {"sceneName": name, "sceneTip": "Your own mix, from Fine-tuning in the forest settings."} if name else {}
    return {"sceneName": presets.by_key()[key].label}


def _part(kind: str, key: str | None) -> str | None:
    """envs/aurora.js, landscapes/lake.js, landmarks/peak.js - if that file still exists."""
    rel = f"{kind}/{key}.js"
    return rel if key and os.path.exists(os.path.join(WEB_DIR, kind, f"{key}.js")) else None


def _panel_parts(did: int | None = None, highlight: bool = False) -> tuple:
    """(element id, data as JSON, scripts before the boot script) for one forest panel."""
    payload = _payload(did, highlight)
    mood_special = payload["mood"]["special"]
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    # only the pieces this scene actually needs are loaded, and each lives in one file of its own
    parts = [_part("envs", mood_special), _part("landscapes", payload["mood"]["landscape"]),
             _part("landmarks", payload["mood"]["landmark"])]
    srcs = [f"{WEB}/{s}" for s in SCRIPTS] + [f"{WEB}/{rel}" for rel in parts if rel] + [f"{WEB}/{BOOT}"]
    # the panel and its data are named after this add-on's folder, so a second copy of it
    # (the public edition installed beside this one) draws its own forest, not over this one
    root = f"memory-forest-{MODULE}"
    srcs.pop()  # the boot script: the page adds it last, and a swap has no need of it
    return root, data, srcs


def _panel_html(did: int | None = None, highlight: bool = False) -> str:
    root, data, srcs = _panel_parts(did, highlight)
    boot = f"{WEB}/{BOOT}"
    return (
        f'<link rel="stylesheet" href="{WEB}/forest.css">'
        + f'<div id="{root}" class="af-panel"></div>'
        + f'<script type="application/json" id="{root}-data">{data}</script>'
        + "".join(f'<script src="{src}"></script>' for src in srcs)
        + f'<script src="{boot}" data-root="{root}"></script>'
    )


def on_deck_browser(deck_browser, content) -> None:
    try:
        # content.tree renders inside a <table>, so a block there would be hoisted above
        # the decks; the start of the stats section sits directly below the deck list.
        content.stats = _panel_html() + content.stats
    except Exception:
        _log("could not render the forest:\n" + traceback.format_exc())


def on_overview(overview, content) -> None:
    """A forest on a deck's own screen: grown from that deck and its subdecks, or the main
    forest with that deck's trees lit (the Deck screens setting)."""
    cfg = config()
    mode = cfg.get("deck_forest_mode", "highlight")
    if mode not in ("highlight", "own"):
        if mode != "off":
            _log(f"unknown deck_forest_mode {mode!r}; showing no deck forest")
        return
    try:
        deck = mw.col.decks.current()
        if deck.get("dyn"):  # filtered decks borrow cards from elsewhere; skip them
            return
        if deck["id"] in excluded_decks(cfg):  # left out of the forest: it has none
            return
        content.table += _panel_html(deck["id"], highlight=mode == "highlight")
    except Exception:
        _log("could not render the deck forest:\n" + traceback.format_exc())


def on_answer(reviewer, card, ease) -> None:
    """A small tooltip the first time a new card is studied each day."""
    cfg = config()
    if not cfg.get("planting_tooltip", True):
        return
    global _planted_today
    # the Anki day, not the calendar day: studying at 00:30 still joins yesterday's tree
    today = forest_data.day_date(0, mw.col.sched.day_cutoff).isoformat()
    if _planted_today == today:  # already shown this session, no need to touch the disk
        return
    try:
        if mw.col.db.scalar("select count() from revlog where cid = ?", card.id) != 1:
            return
        if (card.odid or card.did) in excluded_decks(cfg):  # plants nothing in the forest
            return
        state = _load_state()
        if state.get("last_planted") == today:
            _planted_today = today
            return
        state["last_planted"] = today
        _save_state(state)
        _planted_today = today
        tooltip("🌱 A new tree was planted in your forest today.", period=PLANTING_TOOLTIP_MS)
    except Exception:
        _log("planting tooltip failed:\n" + traceback.format_exc())


def refresh() -> None:
    """Redraw the forest with the current config (no restart needed).

    The forest is swapped in place, inside the page that is already showing: reloading
    the whole deck list would blank the screen for a moment on every change. Only when
    there is no forest there to swap (or it should now be gone) does the page reload.
    """
    if mw.col is None:  # still starting up, or between profiles
        return
    if mw.state == "deckBrowser":
        _swap_or_reload(mw.deckBrowser.web, mw.deckBrowser.refresh)
    elif mw.state == "overview":
        mode = config().get("deck_forest_mode", "highlight")
        deck = mw.col.decks.current()
        if mode in ("highlight", "own") and not deck.get("dyn") and deck["id"] not in excluded_decks():
            _swap_or_reload(mw.overview.web, mw.overview.refresh, deck["id"], mode == "highlight")
        else:
            mw.overview.refresh()


def _swap_or_reload(web, reload, did: int | None = None, highlight: bool = False) -> None:
    try:
        root, data, srcs = _panel_parts(did, highlight)
    except Exception:
        _log("could not rebuild the forest:\n" + traceback.format_exc())
        return
    js = (f"(window.AnkiForest && window.AnkiForest.swap) ? "
          f"window.AnkiForest.swap({json.dumps(root)}, {data}, {json.dumps(srcs)}) : false")
    web.evalWithCallback(js, lambda swapped: None if swapped else reload())


def city_problem(city: str) -> str:
    """Why the live weather for `city` is missing, for the settings dialog, or ""."""
    return _weather.failing(city) if city.strip() else ""


def save_config(cfg: dict) -> None:
    """Write the config, leaving out anything at its default (or no longer an option), so a
    better default in a later version still reaches people who never changed it."""
    known = mw.addonManager.addonConfigDefaults(__name__) or {}
    mw.addonManager.writeConfig(__name__, {k: v for k, v in cfg.items() if k in known and known[k] != v})


def on_deck_options_menu(menu, did: int) -> None:
    """Leave a deck out of the forest, or bring it back, from its gear menu in the deck list."""
    try:
        deck = mw.col.decks.get(did, default=False)
        if not deck or deck.get("dyn"):
            return
        cfg = config()
        mine = [int(d) for d in cfg.get("excluded_decks") or [] if str(d).lstrip("-").isdigit()]
        if did in mine:
            action = menu.addAction("Bring back into Memory Forest")
            action.triggered.connect(lambda: _set_excluded([d for d in mine if d != did]))
        elif did in excluded_decks(cfg):
            action = menu.addAction("Left out of Memory Forest with its parent deck")
            action.setEnabled(False)
        else:
            action = menu.addAction("Leave out of Memory Forest")
            action.triggered.connect(lambda: _set_excluded(mine + [did]))
    except Exception:
        _log("could not add to the deck menu:\n" + traceback.format_exc())


def _set_excluded(dids: list) -> None:
    cfg = config()
    cfg["excluded_decks"] = sorted(set(dids))
    save_config(cfg)
    refresh()


def open_settings() -> None:
    from .settings import open_settings as _open

    _open(__name__, refresh)


def browse_day(days_ago: int, did: int | None = None, until_days_ago: int | None = None) -> None:
    """Open the browser on the cards first studied on that day (same rule as the trees), or
    on everything from that day up to `until_days_ago` when the deep forest is clicked."""
    terms = forest_data.day_search(days_ago, until_days_ago, keeps_suspended())
    name = mw.col.decks.name_if_exists(did) if did else None
    if name:  # deck names can hold quotes and colons, so let Anki quote it
        terms.insert(0, mw.col.build_search_string(SearchNode(deck=name)))
    # the decks left out of the forest planted none of its trees (a deck: search takes
    # their subdecks with them)
    for out in config().get("excluded_decks") or []:
        try:
            out_name = mw.col.decks.name_if_exists(int(out))
        except (TypeError, ValueError):
            continue
        if out_name:
            terms.append(mw.col.build_search_string(SearchNode(negated=SearchNode(deck=out_name))))
    browser = dialogs.open("Browser", mw)
    browser.search_for(" ".join(terms))


def on_js_message(handled, message, context):
    if not isinstance(context, (DeckBrowser, Overview)) or not isinstance(message, str) or not message.startswith(MODULE + ":"):
        return handled
    cmd = message.split(":")[1:]
    try:
        if cmd[0] == "settings":
            open_settings()
        elif cmd[0] == "browse":
            browse_day(int(cmd[1]),
                       int(cmd[2]) if len(cmd) > 2 and cmd[2] else None,
                       int(cmd[3]) if len(cmd) > 3 and cmd[3] else None)
    except Exception:
        _log(f"could not handle {message}:\n" + traceback.format_exc())
    return (True, None)


gui_hooks.deck_browser_will_render_content.append(on_deck_browser)
gui_hooks.overview_will_render_content.append(on_overview)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_menu)
mw.addonManager.setConfigAction(__name__, open_settings)
mw.addonManager.setConfigUpdatedAction(__name__, lambda _cfg: refresh())

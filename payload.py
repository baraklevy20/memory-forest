"""Everything one forest panel is drawn from: the trees (cached until the collection
changes), the day's scene and weather, and the numbers the page shows."""

from __future__ import annotations

import datetime as _dt
import inspect
import os
import time

from aqt import mw

from . import fake_forest, forest_data, milestones, presets, scene, study_log
from .state import (
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    MODULE,
    OFF_VALUES,
    TEST_TREES_DEFAULT,
    TEST_TREES_MAX,
    USER_FILES,
    clamp_int,
    config,
    deck_ids,
    excluded_decks,
    keeps_suspended,
    load_state,
    log,
    save_state,
    since,
)
from .weather import WeatherCache

# on a deck screen the test forest lights every this-many-th tree, having no real decks
TEST_LIT_EVERY = 5

_weather = WeatherCache(os.path.join(USER_FILES, "weather.json"))
_forest_cache: dict = {}
_refreshing = False


def _forest(did: int | None = None) -> dict:
    """Forest data for the whole collection, or one deck and its subdecks. Recomputed
    only when the collection, the day or the decks and dates it counts change."""
    col = mw.col
    cfg = config()
    cutoff = col.sched.day_cutoff
    excluded, start, suspended = excluded_decks(cfg), since(cfg), keeps_suspended(cfg)
    mod = getattr(col, "mod", None)
    key = (mod, cutoff, frozenset(excluded), start, suspended)
    cached = _forest_cache.get(did)
    if mod is not None and cached and cached[0] == key:
        return cached[1]
    started = time.perf_counter()
    dids = deck_ids(did, excluded) if did else None
    rows = study_log.load_rows(col.db, cutoff, dids, excluded=excluded, since=start, suspended=suspended)
    value = forest_data.build_forest(rows, cutoff, col.sched.today, time.time())
    log(f"built {len(value['trees'])} trees{f' for deck {did}' if did else ''} in {(time.perf_counter() - started) * 1000:.0f} ms")
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
            from .panel import refresh  # the panel draws from this module, so it is imported late
            refresh()

    # the weather needs no collection, so it need not wait for one - where this Anki can
    # be told so (older ones take no `uses_collection`)
    extra = {"uses_collection": False} if "uses_collection" in inspect.signature(mw.taskman.run_in_background).parameters else {}
    mw.taskman.run_in_background(lambda: _weather.refresh(city), done, **extra)


def city_problem(city: str) -> str:
    """Why the live weather for `city` is missing, for the settings dialog, or ""."""
    return _weather.failing(city) if city.strip() else ""


def _new_ancient_today(forest: dict, today: _dt.date) -> bool:
    """True on the day a tree first turns ancient (remembered across restarts in user_files)."""
    state = load_state()
    days = sorted(t["day"] for t in forest["trees"] if t["stage"] == forest_data.ANCIENT)
    known = state.get("ancient_days")
    if known is None:  # first run: remember what exists, don't celebrate all of it at once
        state["ancient_days"] = days
        save_state(state)
        return False
    if set(days) - set(known):
        # the ones known before stay known: a deck left out and brought back again, or an
        # earlier start date, must not celebrate its old ancient trees a second time
        state.update(ancient_days=sorted(set(days) | set(known)), ancient_event=today.isoformat())
        save_state(state)
    return state.get("ancient_event") == today.isoformat()


def _lit_by_deck(forest: dict, did: int, test: bool) -> dict:
    """The main forest with each tree marked dim unless it holds some of this deck's cards."""
    if test:
        lit = {t["ago"] for t in forest["trees"][::TEST_LIT_EVERY]}
    else:
        dids = deck_ids(did, excluded_decks())
        lit = study_log.load_deck_days(mw.col.db, mw.col.sched.day_cutoff, dids, keeps_suspended())
    trees = [dict(t, dim=t["ago"] not in lit) for t in forest["trees"]]
    return dict(forest, trees=trees, lit_count=sum(1 for t in trees if not t["dim"]))


def payload(did: int | None = None, highlight: bool = False) -> dict:
    cfg = config()
    # the test forest is a developer's tool, so it only exists while debug is on
    test = bool(cfg.get("debug", False)) and bool(cfg.get("test_forest", False))
    forest = fake_forest.make(clamp_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX)) if test else _forest(None if highlight else did)
    if highlight and did:
        forest = _lit_by_deck(forest, did, test)
    now = _dt.datetime.now()
    today = now.date()
    all_trees = forest["trees"]
    ann_all = milestones.anniversaries(all_trees, today)
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
        "maxWidth": clamp_int(cfg.get("max_width"), MAX_WIDTH_DEFAULT, MAX_WIDTH_MIN, MAX_WIDTH_MAX),
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

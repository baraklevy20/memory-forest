"""Everything one forest panel is drawn from: the trees (cached until the collection
changes), the day's scene and weather (live_weather.py), and the numbers the page shows."""

from __future__ import annotations

import datetime as _dt
import time
from types import SimpleNamespace

from aqt import mw

from . import events_state, forest_data, journal, live_weather, milestones, presets, scene, study_log
from .state import (
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    MODULE,
    OFF_VALUES,
    TEST_TREES_DEFAULT,
    TEST_TREES_MAX,
    changes,
    clamp_int,
    config,
    debug_available,
    deck_ids,
    excluded_decks,
    follow_season,
    forget_remembered,
    keeps_suspended,
    load_state,
    log,
    phone_cards,
    remembered,
    save_state,
    season_returns,
    since,
)
from .state import today as scenery_day

# what each tree holds that the page never reads (it goes to the phone as well, at every sync)
PAGE_LEAVES_OUT = ("mature", "day")
# on a deck screen the test forest lights every this-many-th tree, having no real decks
TEST_LIT_EVERY = 5

_forest_cache: dict = {}
# each forest's review log, read whole once and then only what was added (study_log.ReviewLog)
_logs: dict = {}


def after_sync() -> None:
    """After a sync, read everything afresh next time: it may have brought in old reviews,
    moved cards between decks or taken reviews away, none of which state.changes sees (as a
    review deleted by hand, or by Check Database, isn't seen before the next sync, restart or
    new day)."""
    _logs.clear()
    _forest_cache.clear()
    forget_remembered()


def _forest(did: int | None = None, cfg: dict | None = None, changed=None) -> dict:
    """Forest data for the whole collection, or one deck and its subdecks. Recomputed only
    when the study data (state.changes, `changed` if already read), the day or the decks and
    dates it counts change."""
    col = mw.col
    cfg = config() if cfg is None else cfg
    cutoff = col.sched.day_cutoff
    excluded, start, suspended, skip = excluded_decks(cfg), since(cfg), keeps_suspended(cfg), phone_cards()
    changed = changes() if changed is None else changed
    key = (changed, cutoff, frozenset(excluded), start, suspended, frozenset(skip))
    cached = _forest_cache.get(did)
    if changed is not None and cached and cached[0] == key:
        return cached[1]
    started = time.perf_counter()
    dids = deck_ids(did, excluded) if did else None
    owner, log_ = _logs.get(did, (None, None))
    here = getattr(col, "path", None) or id(col)  # which collection, without keeping it alive
    if owner != here:
        log_ = study_log.ReviewLog()
    rows = study_log.load_rows(col.db, cutoff, dids, excluded=excluded, since=start, suspended=suspended, skip=skip, log=log_)
    value = forest_data.build_forest(rows, cutoff, col.sched.today, time.time())
    log(f"built {len(value['trees'])} trees{f' for deck {did}' if did else ''} in {(time.perf_counter() - started) * 1000:.0f} ms")
    # the whole collection's, and the last deck screen's: one per deck ever opened adds up
    for kept in (_forest_cache, _logs):
        for other in [d for d in kept if d is not None and d != did]:
            del kept[other]
    _forest_cache[did] = (key, value)
    _logs[did] = (here, log_)
    return value


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


def _lit_by_deck(forest: dict, did: int, test: bool, cfg: dict, changed=None) -> dict:
    """The main forest with each tree marked dim unless it holds some of this deck's cards."""
    if test:
        lit = {t["ago"] for t in forest["trees"][::TEST_LIT_EVERY]}
    else:
        col = mw.col
        dids, suspended, skip = deck_ids(did, excluded_decks(cfg)), keeps_suspended(cfg), phone_cards()
        lit = remembered("deck_days", changed and (changed, col.sched.day_cutoff, tuple(dids), suspended, frozenset(skip)),
                         lambda: study_log.load_deck_days(col.db, col.sched.day_cutoff, dids, suspended, skip))
    trees = [dict(t, dim=t["ago"] not in lit) for t in forest["trees"]]
    return dict(forest, trees=trees, lit_count=sum(1 for t in trees if not t["dim"]))


def debug_tools(cfg: dict):
    """The debug tools (the made-up test forest, the timeline of events) while debug is on;
    None otherwise - and in a release, which ships without them (state.debug_available)."""
    if not debug_available(cfg):
        return None
    from . import debug_events, fake_forest
    return SimpleNamespace(debug_events=debug_events, fake_forest=fake_forest)


def payload(did: int | None = None, highlight: bool = False) -> dict:
    cfg = follow_season(config())
    # the test forest is a developer's tool, so it only exists while debug is on
    tools = debug_tools(cfg)
    test = bool(tools) and bool(cfg.get("test_forest", False))
    changed = None if test else changes()  # read once: everything below that is kept goes by it
    forest = (dict(tools.fake_forest.make(clamp_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX)), test=True) if test
              else _forest(None if highlight else did, cfg, changed))
    if highlight and did:
        forest = _lit_by_deck(forest, did, test, cfg, changed)
    # Nature and the other study events; a deck's own forest shows the trees alone
    extras = {}
    if not (did and not highlight):
        forest, extras = events_state.apply(forest, cfg, test, changed)
        if tools:
            forest, extras = tools.debug_events.apply(forest, extras, cfg)
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

    real, place, weather_error = live_weather.for_config(cfg)

    day = scenery_day(cfg)  # today, or the debug date: the scenery is chosen for it
    mood = scene.choose_mood(cfg, _dt.datetime.combine(day, now.time()), real, place)
    evs = scene.events(forest["stats"], today, new_ancient)

    return {
        # each tree's count of cards known well only adds up to the animals' milestones, and
        # its day number is only for remembering ancient trees: the page needs neither
        "trees": [{k: v for k, v in t.items() if k not in PAGE_LEAVES_OUT} for t in forest["trees"]],
        "stats": forest["stats"],
        "visitors": forest["visitors"],
        "anniversaries": ann,
        "mood": mood,
        "journal": events_state.news_line(extras) or journal.journal(dict(forest, trees=all_trees), mood, today, ann_all, evs),
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
        **_scene_name(cfg, day),
        "inAnki": True,
        "channel": MODULE,  # clicks go back as "<channel>:...", so only this add-on answers them
        "deckId": did,
        "deckName": mw.col.decks.name_if_exists(did) if did else None,
        "highlight": bool(highlight and did),
        "litCount": forest.get("lit_count"),
        **extras,
    }


def _scene_name(cfg: dict, today: _dt.date) -> dict:
    """What the caption calls the scene: the preset's name, today's pick for Surprise me
    daily, or nothing for the plain default."""
    key = presets.match(cfg)
    if key == presets.FOREST_PRESETS[0].key:
        return {}
    if key == "daily":
        pick = presets.of_the_day(today)
        return {"sceneName": pick.label, "sceneTip": "Today's scenery, from Surprise me daily. Tomorrow brings the next one."}
    if key == presets.CUSTOM:
        name = scene.ENVIRONMENTS.get(cfg.get("environment"), "")
        return {"sceneName": name, "sceneTip": "Your own mix, from Fine-tuning in the forest settings."} if name else {}
    spec = presets.by_key()[key]
    back = season_returns(cfg, today)
    if back:
        return {"sceneName": spec.label,
                "sceneTip": f"Seasonal scenery, for this week only. Yours comes back on {back.day} {back.strftime('%B')}."}
    if spec.season:  # picked by hand in its week: it goes with the week all the same
        last = presets.season_ends(spec, today) - _dt.timedelta(days=1)
        return {"sceneName": spec.label, "sceneTip": f"Seasonal scenery, here until {last.day} {last.strftime('%B')}."}
    return {"sceneName": spec.label}

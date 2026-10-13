"""Everything one forest panel is drawn from: the trees (cached until the collection
changes), the day's scene and weather (live_weather.py), and the numbers the page shows."""

from __future__ import annotations

import datetime as _dt
import time
from types import SimpleNamespace

from aqt import mw

from . import events_state, forest_data, journal, live_weather, marks, milestones, news, presets, scene, study_log
from .edition import debug_available, debug_edition
from .phone_note import phone_cards
from .scope import changes, day_cutoff, deck_ids, excluded_decks, since
from .seasons import follow_season, season_returns
from .seasons import today as scenery_day
from .state import (
    ANIMATION_VALUES,
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    MODULE,
    TEST_TREES_DEFAULT,
    TEST_TREES_MAX,
    WEEK_START_DAYS,
    animation_mode,
    calendar_on,
    calendar_view,
    clamp_int,
    config,
    forget_remembered,
    keeps_suspended,
    load_state,
    log,
    remembered,
    save_state,
    settings_open,
    shows_record,
    streak_from_start,
    week_start,
)

# what each tree holds that the page never reads (it goes to the phone as well, at every sync)
PAGE_LEAVES_OUT = ("mature", "day")
# zooming in among the trees (web/visit.js): held back from release for now, so on only while
# debugging as this copy itself (not while the Debug tab pretends to be the base or Plus
# edition, which show it as a release does); True lets everyone have it
ZOOM_RELEASED = False
# the study calendar shows the cards due this many days ahead (today first)
CALENDAR_DUE_DAYS = 800  # (time enough for the next whole year)
# the test forest's reviews in the calendar: a few for each card a day learned, or a day's worth
TEST_REVIEWS_PER_CARD, TEST_DAY_REVIEWS = 4, 40
# on a deck screen the test forest lights every this-many-th tree, having no real decks
TEST_LIT_EVERY = 5
# the trees of each forest's deep forest, as last sent (by deck id, "" for the deck list's):
# the page asks for them when zoomed in among the trees (web/visit.js), to draw them one by one
_deep: dict[str, list] = {}


def _for_page(tree: dict) -> dict:
    return {k: v for k, v in tree.items() if k not in PAGE_LEAVES_OUT}


def deep_trees(key: str) -> list:
    """The trees the deep forest of the forest last sent for deck `key` holds, oldest first."""
    return [_for_page(t) for t in _deep.get(key, [])]


_forest_cache: dict = {}
# each forest's review log, read whole once and then only what was added (study_log.ReviewLog)
_logs: dict = {}


def after_sync() -> None:
    """After a sync, read everything afresh next time: it may have brought in old reviews,
    moved cards between decks or taken reviews away, none of which scope.changes sees (as a
    review deleted by hand, or by Check Database, isn't seen before the next sync, restart or
    new day)."""
    _logs.clear()
    _forest_cache.clear()
    forget_remembered()


def collection_loaded(_col=None) -> None:
    """A collection was opened: the profile's, or one put in its place - a .colpkg imported,
    a backup restored, a full sync downloaded. That one has the same path as the one before,
    so the review log kept for it (only read on from where it stopped) and everything worked
    out from it must go, or the totals, streak and ponds stay the old collection's."""
    after_sync()


def _forest(did: int | None = None, cfg: dict | None = None, changed=None) -> dict:
    """Forest data for the whole collection, or one deck and its subdecks. Recomputed only
    when the study data (scope.changes, `changed` if already read), the day or the decks and
    dates it counts change."""
    col = mw.col
    cfg = config() if cfg is None else cfg
    cutoff = day_cutoff(col)
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
    # the whole collection's, and the last deck screen's: one per deck ever opened adds up.
    # Only a deck's own build lets the one before go: the whole collection's leaves it, so
    # going back to the deck list and opening the same deck again reads nothing afresh
    if did is not None:
        for kept in (_forest_cache, _logs):
            for other in [d for d in kept if d is not None and d != did]:
                del kept[other]
    _forest_cache[did] = (key, value)
    _logs[did] = (here, log_)
    return value


def _new_ancient_today(forest: dict, today: _dt.date, start: str | None = None) -> bool:
    """True on the day a tree of this forest first turns ancient (remembered across restarts
    in user_files). Which trees turned that day is remembered too: a start date set later the
    same day, or a deck left out, takes the news away with the tree.

    The ancient trees are remembered for each start date (`start`, None for none) as for the
    animals: the first look at a forest begun on another day takes in the ones it has without
    a word, so unticking a start date announces none of the old forest's long-ancient trees.
    Nothing the settings dialog previews is remembered."""
    state = load_state()
    days = sorted(t["day"] for t in forest["trees"] if t["stage"] == forest_data.ANCIENT)
    every = state.get("ancient") if isinstance(state.get("ancient"), dict) else {}
    key = "all" if start is None else f"from {start}"
    known = every.get(key, state.get("ancient_days") if key == "all" else None)  # (where 1.1 kept them)
    event = state.get("ancient_event") == today.isoformat()
    turned = set() if known is None else set(days) - set(known)
    if not settings_open() and (known is None or turned):
        if turned:
            # the ones known before stay known: a deck left out and brought back again, or an
            # earlier start date, must not celebrate its old ancient trees a second time
            turned |= set(state.get("ancient_event_days") or []) if event else set()
            state.update(ancient_event=today.isoformat(), ancient_event_days=sorted(turned))
            event = True
        # (a tree that turned today is news once, whichever start date shows it later)
        every = {k: sorted(set(v) | turned) for k, v in every.items() if isinstance(v, list)}
        state["ancient"] = dict(every, **{key: sorted(set(days) | set(known or []))})
        state.pop("ancient_days", None)
        save_state(state)
    return event and bool(set(state.get("ancient_event_days") or []) & set(days))


def _lit_by_deck(forest: dict, did: int, test: bool, cfg: dict, changed=None) -> dict:
    """The main forest with each tree marked dim unless it holds some of this deck's cards."""
    if test:
        lit = {t["ago"] for t in forest["trees"][::TEST_LIT_EVERY]}
    else:
        col = mw.col
        dids, suspended, skip = deck_ids(did, excluded_decks(cfg)), keeps_suspended(cfg), phone_cards()
        lit = remembered("deck_days", changed and (changed, day_cutoff(col), tuple(dids), suspended, frozenset(skip)),
                         lambda: study_log.load_deck_days(col.db, day_cutoff(col), dids, suspended, skip))
    trees = [dict(t, dim=t["ago"] not in lit) for t in forest["trees"]]
    return dict(forest, trees=trees, lit_count=sum(1 for t in trees if not t["dim"]))


def debug_tools(cfg: dict):
    """The debug tools (the made-up test forest, the timeline of events) while debug is on;
    None otherwise - and in a release, which ships without them (edition.debug_available)."""
    if not debug_available(cfg):
        return None
    from . import debug_events, fake_forest
    return SimpleNamespace(debug_events=debug_events, fake_forest=fake_forest)


def payload(did: int | None = None, highlight: bool = False, show_forest: bool = True) -> dict:
    cfg = follow_season(config())
    # the test forest is a developer's tool, so it only exists while debug is on
    tools = debug_tools(cfg)
    test = bool(tools) and bool(cfg.get("test_forest", False))
    changed = None if test else changes()  # read once: everything below that is kept goes by it
    forest = (dict(tools.fake_forest.make(clamp_int(cfg.get("test_trees"), TEST_TREES_DEFAULT, 0, TEST_TREES_MAX)), test=True) if test
              else _forest(None if highlight else did, cfg, changed))
    if highlight and did:
        forest = _lit_by_deck(forest, did, test, cfg, changed)
    # Nature and the other study events, on every forest: a deck's screen acts as the main one
    forest, extras = events_state.apply(forest, cfg, test, changed, did if did and not highlight else None)
    if tools:
        forest, extras = tools.debug_events.apply(forest, extras, cfg)
    now = _dt.datetime.now()
    today = now.date()
    all_trees = forest["trees"]
    ann_all = milestones.anniversaries(all_trees, today)
    start = str(cfg.get("ignore_before")) if since(cfg) is not None else None
    new_ancient = False if test or (did and not highlight) else _new_ancient_today(forest, today, start)

    forest = forest_data.merge_old(forest)  # the oldest trees become one deep-forest band
    drawn = len(forest["trees"])
    merged_count = len(all_trees) - drawn
    _deep[str(did or "")] = all_trees[:merged_count]
    # the page can only glow trees it draws; the journal still names any of them
    ann = [i - merged_count for i in ann_all if i >= merged_count]

    real, place, weather_error = live_weather.for_config(cfg)

    day = scenery_day(cfg)  # today, or the debug date: the scenery is chosen for it
    mood = scene.choose_mood(cfg, _dt.datetime.combine(day, now.time()), real, place)
    evs = scene.events(forest["stats"], today, new_ancient)

    return {
        # each tree's count of cards known well only adds up to the animals' milestones, and
        # its day number is only for remembering ancient trees: the page needs neither
        "trees": [_for_page(t) for t in forest["trees"]],
        "stats": _page_stats(forest["stats"], cfg, test, did, highlight, changed),
        "visitors": forest["visitors"],
        "anniversaries": ann,
        "mood": mood,
        "journal": events_state.news_line(extras) or journal.journal(dict(forest, trees=all_trees), mood, today, ann_all, evs,
                                                                     extras.get("stagnation", 0.0)),
        "events": evs,
        "merged": forest.get("merged"),
        "forestSeed": forest["forest_seed"],
        "dayNumber": today.toordinal(),  # the animals take new places each day
        "testForest": test,
        "animations": ANIMATION_VALUES[animation_mode(cfg)],
        "tooltips": True,
        "zoom": ZOOM_RELEASED or (debug_available(cfg) and not debug_edition(cfg)),
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
        # what's new: a note on the deck list's forest only, and the cog's dot on every one
        "news": None if did else news.note(cfg, day),
        "newDot": news.cog_dot(cfg),
        # the forest itself may be switched off on this screen while the study calendar is on
        "showForest": show_forest,
        # the study calendar (web/calendar.js): the whole collection's on the main screen, the
        # deck's own on a deck's screen
        "calendar": _calendar(forest, all_trees, cfg, test, changed, did, highlight),
        **extras,
    }


# a week start as the page counts days (Date.getUTCDay: Sunday 0, Monday 1 .. Saturday 6)


def _week_start_day(cfg: dict) -> int:
    """The day the study calendar's weeks start on, as the page counts days: the chosen one, or
    the system's (Qt's locale: a Mac's Language & Region setting, say), Monday if it can't say."""
    chosen = week_start(cfg)
    if chosen != "system":
        return WEEK_START_DAYS[chosen]
    try:
        from aqt.qt import QLocale
        day = QLocale.system().firstDayOfWeek()  # Qt counts Monday 1 .. Sunday 7
        return int(getattr(day, "value", day)) % 7
    except Exception:
        return WEEK_START_DAYS["monday"]


def _day_reviews(cutoff: int, dids: list | None, excluded, begin: int | None, skip, changed) -> dict:
    """{days ago: reviews} in the `dids` decks (the whole collection for None) but the `excluded`
    ones and the `skip` cards, from `begin` (None: all of them), remembered until the study data
    changes: the days the caption's streak and the study calendar go by when they are not the
    forest's own."""
    name = "day_reviews" if begin is None else "day_reviews_since"  # (one answer is kept per name)
    return remembered(name, changed and (changed, cutoff, tuple(dids or ()), frozenset(excluded), begin, frozenset(skip)),
                      lambda: study_log.load_day_reviews(mw.col.db, cutoff, dids, excluded, begin, skip))


def _page_stats(stats: dict, cfg: dict, test: bool, did: int | None, highlight: bool, changed) -> dict:
    """The numbers the page shows, their streak the study calendar's. With a start date, the
    streak is still your real one, unbroken by it (a young forest is a choice of look, not a
    lapse): only the forest's own milestones (its animals, the journal's) go by the days since it
    began, from `stats` as the forest has them. Unless the Decks tab says to count the streak
    from the start date too, or the calendar on this screen shows nothing before it. Under the
    whole forest on a deck's screen the calendar is the deck's own, and so is the streak. A day
    with nothing due never breaks it (_free_days), as on the calendar."""
    if test:
        return stats
    begin = since(cfg)
    calendar_here = calendar_on("decks" if did else "main", cfg)
    from_start = begin is not None and (streak_from_start(cfg) or (calendar_here and not shows_record(cfg)))
    own = bool(did and highlight and calendar_here)
    cutoff, excluded, skip = day_cutoff(mw.col), excluded_decks(cfg), phone_cards()
    dids = deck_ids(did, excluded) if did and (own or not highlight) else None
    days = set(_day_reviews(cutoff, dids, excluded, begin if from_start else None, skip, changed))
    streak, longest = forest_data._streaks(days, _free_days(cutoff, dids, excluded, skip, changed))
    return dict(stats, streak=streak, longest_streak=longest)


def _free_days(cutoff: int, dids: list | None, excluded, skip, changed) -> frozenset:
    """The days (as `ago`) with no review and nothing due in these decks (study_log.load_free_days),
    remembered until the study data changes: days a streak passes over."""
    runs = _free_runs(cutoff, dids, excluded, skip, changed)
    return frozenset(d for older, newer in runs for d in range(newer, older + 1))


def _free_runs(cutoff: int, dids: list | None, excluded, skip, changed) -> list:
    return remembered("free_days", changed and (changed, cutoff, tuple(dids or ()), frozenset(excluded), frozenset(skip)),
                      lambda: study_log.load_free_days(mw.col.db, cutoff, dids, excluded, skip))


def _calendar(forest: dict, trees: list, cfg: dict, test: bool, changed=None, did: int | None = None,
              highlight: bool = False) -> dict | None:
    """What the study calendar is drawn from: its view, the date of the first day counted, each
    day's reviews from then to today, the cards due on each day from today on, the day each of
    the forest's animals came (milestones.animal_days), and the rule for ponds it shares with the forest;
    None while it is off on this screen. On the main screen the days are the forest's own (its
    decks and start date), so its streak is the caption's; on a deck's screen they are that
    deck's and its subdecks', with the animals of its own forest if it shows one. `trees` are
    all of the forest's, the deep forest's too."""
    if not calendar_on("decks" if did else "main", cfg):
        return None
    col = mw.col
    cutoff = day_cutoff(col)
    excluded, skip = excluded_decks(cfg), phone_cards()
    dids = deck_ids(did, excluded) if did and not test else None
    animals = not did or not highlight  # a lit-up deck screen shows the main forest's animals, not the deck's
    if test:
        # the test forest's days studied: the debug timeline's, or its trees' days and as many
        # days back from today as its streak claims (the day before it missed, so it is no
        # longer); each with a few reviews for each card learned
        studied = forest.get("review_days")
        if studied is None:
            streak = forest["stats"]["streak"]
            studied = ({t["ago"] for t in trees} - {streak}) | set(range(streak))
        learned = {t["ago"]: t["n"] for t in trees}
        day_reviews = {ago: learned.get(ago, 0) * TEST_REVIEWS_PER_CARD or TEST_DAY_REVIEWS for ago in studied}
    elif dids and highlight:  # the main forest above it: the deck's own days, read on their own
        day_reviews = _day_reviews(cutoff, dids, excluded, since(cfg), skip, changed)
    else:
        day_reviews = forest.get("day_reviews") or {}
    # with a start date (Ignore before), the reviews from before it too: the calendar shows your
    # whole record as if there were none, but for the animals, the forest's own (web/calendar.js)
    begin, forest_start, own = since(cfg), None, day_reviews  # (the animals' days stay the forest's own)
    if begin and not test and shows_record(cfg):
        forest_start = study_log.day_date((cutoff - 1 - begin) // study_log.DAY_SECS, cutoff).isoformat()
        day_reviews = _day_reviews(cutoff, dids, excluded, None, skip, changed)
    oldest = max(day_reviews, default=0)
    days = [day_reviews.get(ago, 0) for ago in range(oldest, -1, -1)]
    due = remembered("calendar_due", changed and (changed, cutoff, frozenset(excluded), frozenset(skip), tuple(dids or ())),
                     lambda: study_log.load_due(col.db, col.sched.today, CALENDAR_DUE_DAYS, excluded, skip, dids))
    return {"view": calendar_view(cfg), "weekStart": _week_start_day(cfg), "start": study_log.day_date(oldest, cutoff).isoformat(), "days": days, "due": due,
            "animals": milestones.animal_days(forest.get("visitors") or [], trees, own, col.sched.today, test)
                       if animals else [],
            "breakDays": forest_data.BREAK_DAYS,
            "forestStart": forest_start,
            "streakFromStart": streak_from_start(cfg),  # (else a streak runs on over the start date)
            "marks": marks.important_days(col),
            # the days with nothing due, as [oldest, newest] runs of days ago: a streak passes over them
            "free": [] if test else [r for r in _free_runs(cutoff, dids, excluded, skip, changed) if r[1] <= oldest],
            "browse": not test}  # a day's tile opens its cards (actions.browse_reviews), but not a made-up day


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
        return {"sceneName": name, "sceneTip": "Your own mix, from Customize in the forest settings."} if name else {}
    spec = presets.by_key()[key]
    back = season_returns(cfg, today)
    if back:
        return {"sceneName": spec.label,
                "sceneTip": f"Seasonal scenery, for this week only. Yours comes back on {back.day} {back.strftime('%B')}."}
    if spec.season:  # picked by hand in its week: it goes with the week all the same
        last = presets.season_ends(spec, today) - _dt.timedelta(days=1)
        return {"sceneName": spec.label, "sceneTip": f"Seasonal scenery, here until {last.day} {last.strftime('%B')}."}
    return {"sceneName": spec.label}

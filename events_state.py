"""The events - what the way you study brings to the forest - on Anki's side: what the
page needs to show the Nature setting's asteroid or fire, the big days, the tall grass, the
cured leeches and the backlog of overdue reviews. Nature is read afresh from the days you
studied each time; only what has been shown is remembered (a strike played, the animals
announced). The rules are in events.py, the drawing in web/events/."""

from __future__ import annotations

from aqt import mw

from . import events, forest_data, milestones, study_log
from .state import _profile, day_cutoff, deck_ids, excluded_decks, load_state, phone_cards, phone_decks, remembered, save_state, since

# The profiles a sync has finished for this session, and whether one is under way. Until
# a sync has brought in what you studied elsewhere (on your phone, say), a day you studied
# there looks missed here - so no strike, fire, smoke or doom that hasn't shown yet comes
# before one has, unless the profile doesn't sync at all.
_synced: set = set()
_syncing = False


def nature_level(cfg: dict) -> str:
    return events.nature_level(cfg.get("nature"))


def sync_started() -> None:
    global _syncing
    _syncing = True


def sync_finished() -> None:
    global _syncing
    _syncing = False
    _synced.add(_profile())


def _syncs() -> bool:
    """Whether this profile syncs (is logged in to AnkiWeb)."""
    pm = getattr(mw, "pm", None)
    try:
        auth = getattr(pm, "sync_auth", None)
        if callable(auth):
            return auth() is not None
        return bool((getattr(pm, "profile", None) or {}).get("syncKey"))
    except Exception:  # can't tell: wait for a sync, to be safe
        return True


def settled() -> bool:
    """Whether the review log is all there: a sync has finished this session, or the
    profile doesn't sync; and no sync is under way (the forest written for your phone as
    one starts is made from what is here before it)."""
    return not _syncing and (_profile() in _synced or not _syncs())


def _nature_days(cfg: dict, forest: dict, changed=None, own: bool = False) -> set:
    """The days you studied anything at all (see study_log.load_review_days), but the note
    that carries the forest to your phone: looking at it there is not studying. With no deck
    left out and no start date, those are the main forest's own days, already read (a deck's
    `own` forest has only that deck's)."""
    col = mw.col
    phone, cards = phone_decks(), phone_cards()
    if not own and excluded_decks(cfg) == phone and since(cfg) is None and forest.get("review_days") is not None:
        return forest["review_days"]
    return remembered("nature_days", changed and (changed, day_cutoff(col), frozenset(phone), frozenset(cards)),
                      lambda: study_log.load_review_days(col.db, day_cutoff(col), phone, cards))


# the latest strike the page was told of, (its key, the crater as events.merciless gave it),
# for the forest it took when a click asks to play it again
_strike: tuple = (None, None)


def strike_payload(out: dict, seen_key: str, date, playable: bool = True) -> dict:
    """What the page needs to show the craters (events.merciless's `out`) and play the
    latest strike. It plays by itself once, while it is news and hasn't been seen (and
    `playable`: not while the settings dialog previews it); the journal speaks of it
    (`told`) until it has played, and for the rest of that day. The forest it took comes
    along only to play by itself: a replay asks for it (strike_before), as it is a second
    forest's worth of trees."""
    global _strike
    latest = out["latest"]
    _strike = (seen_key, latest)
    state = load_state()
    news = latest["ago"] <= events.STRIKE_NEWS_DAYS
    fresh = news and playable and state.get("strike_seen") != seen_key
    return {
        "craters": [dict(c, date=date(c["ago"])) for c in out["craters"]],
        "strike": {"date": date(latest["ago"]), "lost": latest["lost"], **(strike_before(seen_key) if fresh else {}),
                   "seen": seen_key, "fresh": fresh, "news": news,
                   "told": news and (fresh or state.get("strike_seen_day") == mw.col.sched.today)},
    }


def strike_before(seen_key: str) -> dict | None:
    """The forest the strike `seen_key` took, to play it: None if the page asks for one it
    is no longer the latest of."""
    key, latest = _strike
    if key != seen_key or latest is None:
        return None
    before = forest_data.merge_old({"trees": latest["before"]})
    return {"before": before["trees"], "merged": before.get("merged")}


def ago_date(ago: int) -> str:
    return study_log.day_date(ago, day_cutoff(mw.col)).isoformat()


def _backlog(cfg: dict, changed=None) -> dict:
    """The overdue reviews, how deep in review hell they put you, and whether today is the
    day you cleared them (and if so, how deep it `was`) - remembering, per profile, the last
    day of review hell, how deep it was then, and the last backlog cleared."""
    col = mw.col
    today = col.sched.today
    excluded, skip, cutoff = excluded_decks(cfg), phone_cards(), day_cutoff(col)
    overdue, counts = remembered("backlog", changed and (changed, today, cutoff, frozenset(excluded), frozenset(skip)),
                                 lambda: study_log.load_backlog(col.db, today, cutoff, events.REVIEW_HELL_USUAL_DAYS, excluded, skip))
    usual = events.usual_reviews(counts)
    hell = events.review_hell(overdue, usual)
    state = load_state()
    day = lambda key: state.get(key) if type(state.get(key)) is int else None  # noqa: E731
    cleared = events.backlog_cleared(overdue, today, day("hell_day"), day("backlog_cleared"))
    remember = {k: today for k, on in (("hell_day", hell > 0), ("backlog_cleared", cleared)) if on and state.get(k) != today}
    if hell and state.get("hell_level") != round(hell, 3):
        remember["hell_level"] = round(hell, 3)
    if remember:
        state.update(remember)
        save_state(state)
    out = {"overdue": overdue, "usual": round(usual), "hell": round(hell, 3), "cleared": cleared}
    if cleared:
        level = state.get("hell_level")
        out["was"] = level if isinstance(level, (int, float)) and 0 < level <= 1 else 0.5
    return out


def _pond_days(cfg: dict, changed=None) -> set:
    """The days the main forest's ponds go by: a review in any deck it grows from."""
    col, excluded, skip = mw.col, excluded_decks(cfg), phone_cards()
    return remembered("pond_days", changed and (changed, day_cutoff(col), frozenset(excluded), frozenset(skip)),
                      lambda: study_log.load_review_days(col.db, day_cutoff(col), excluded, skip))


def _mark_cured(trees: list, cfg: dict, changed=None, dids: list | None = None) -> list:
    """The trees, each holding a leech cured lately copied with `cured` (how many): of the
    whole collection, or of the `dids` decks for a deck's own forest."""
    col, excluded, skip = mw.col, excluded_decks(cfg), phone_cards()
    key = (changed, day_cutoff(col), frozenset(excluded), frozenset(skip), dids and tuple(dids))
    cured = remembered("cured", changed and key,
                       lambda: study_log.load_cured(col.db, day_cutoff(col), events.CURED_DAYS, excluded, skip, dids))
    return [dict(t, cured=cured[t["ago"]]) if cured.get(t["ago"]) else t for t in trees] if cured else trees


def _animals(forest: dict, struck: int | None, did: int | None = None) -> dict:
    """The forest with every animal that has come to it, remembered per profile for each
    forest there has been (the whole of it, and the one that grew since each asteroid -
    `struck`, the day it began again - and the same for each deck's own forest, `did`): once
    come, an animal stays, and is new on the day it came. The first look at a forest
    remembers the animals it already has without announcing them all at once - so changing
    the Nature setting back and forth announces nothing - and nothing the settings dialog
    previews is remembered."""
    from .settings import is_open

    today = mw.col.sched.today
    key = "all" if struck is None else str(struck)
    if did is not None:  # a deck's own forest earns its own
        key = f"deck {did} {key}"
    state = load_state()
    every = state.get("animals")
    every = every if isinstance(every, dict) and all(isinstance(v, dict) for v in every.values()) else {}
    known = every.get(key)
    first = known is None
    known = {k: v for k, v in (known or {}).items() if v is None or type(v) is int}
    arrived = milestones.arrivals(forest["stats"], known, None if first or is_open() else today)
    if not is_open() and arrived != every.get(key):
        state["animals"] = dict(every, **{key: arrived})
        save_state(state)
    return dict(forest, visitors=milestones.visitors(forest["stats"], arrived, today))


def _held(days: set) -> frozenset:
    """The strikes that don't come yet: until the review log is all there (see settled),
    any newer than the last one shown - a day studied on another device looks missed until
    it syncs. The ones shown before stay, each with its own trees."""
    if settled():
        return frozenset()
    last = _last_shown("strike")
    return frozenset(d for d in events.strikes(days) if last is None or ago_date(d) > last)


def _last_shown(kind: str) -> str | None:
    """The day (an ISO date) of the last `kind` shown once the review log was all there:
    a strike (or the strike played, strike_seen), a fire, its smoke, or a doom."""
    state = load_state()
    shown = state.get("shown") if isinstance(state.get("shown"), dict) else {}
    # (dates only: the debug timeline's strikes are seen by keys of their own)
    days = [d for d in (shown.get(kind), state.get("strike_seen") if kind == "strike" else None)
            if isinstance(d, str) and d[:1].isdigit()]
    return max(days, default=None)


def _shows(kind: str, day: str, remember: bool) -> bool:
    """Whether Wild's fire or smoke, or Merciless's doom - `kind`, of `day` (an ISO date) -
    shows. Once the review log is all there (see settled) it does, and is remembered (unless
    not `remember`: the settings dialog's preview); before that, only if it showed so
    already, as a day studied on another device looks missed until it syncs."""
    if not settled():
        return _last_shown(kind) == day
    if remember:
        _remember_shown(kind, day)
    return True


def _remember_shown(kind: str, day: str) -> None:
    state = load_state()
    shown = state.get("shown") if isinstance(state.get("shown"), dict) else {}
    if shown.get(kind) != day:
        state["shown"] = dict(shown, **{kind: day})
        save_state(state)


def _new_cards_left(cfg: dict, changed=None, dids: list | None = None) -> bool:
    """Whether the decks the forest grows from (all of them, or the `dids` decks) have any new
    cards left to learn (suspended ones aside): with none, you have learned them all, and
    only reviewing is no stagnation."""
    col, excluded, skip = mw.col, excluded_decks(cfg), phone_cards()
    return remembered("new_left", changed and (changed, frozenset(excluded), frozenset(skip), dids and tuple(dids)),
                      lambda: study_log.has_new_cards(col.db, excluded, skip, dids))


def apply(forest: dict, cfg: dict, test: bool, changed=None, did: int | None = None) -> tuple:
    """The forest after Nature has had its say, and everything else the way you study
    brings to it: (forest, extras for the page). `did` for a forest of that deck's own: it
    goes through all the same, the trees' own events (crows, robins, flowers, grass) from
    that deck's cards, and the rest (Nature, the ponds, the backlog) from every deck you
    study, as on the main forest. What is read from the collection is kept until `changed`
    (state.changes) is different."""
    from .settings import is_open

    level = nature_level(cfg)
    days = forest.get("review_days") or set()
    dids = deck_ids(did, excluded_decks(cfg)) if did is not None and not test else None
    extras = {"nature": level, "craters": [], "strike": None, "doom": None, "fire": None}
    reviewing = days
    if not test:
        # Nature goes by every deck you study, whichever the forest leaves out
        nature_days = _nature_days(cfg, forest, changed, own=did is not None)
        if did is not None:  # as on the main forest: coasting is reviewing anywhere, a break is from every deck
            reviewing = nature_days
            forest = dict(forest, trees=forest_data.with_ponds(forest["trees"], _pond_days(cfg, changed), ago_date))
        struck = None
        live = not is_open()  # (what the settings dialog previews is not remembered as shown)
        if level == "merciless":
            out = events.merciless(forest["trees"], nature_days, _held(nature_days))
            if out["hits"] and settled() and live:
                _remember_shown("strike", ago_date(out["hits"][-1]))
            if out["latest"]:
                extras.update(strike_payload(out, ago_date(out["latest"]["ago"]), ago_date, live))
            if out["hits"]:
                # the forest now: only what grew since, its streak, reviews and animals counted
                # from there - the animals have to be earned again, as the trees do
                hit = out["hits"][-1]
                struck = mw.col.sched.today - hit
                reviews = sum(n for d, n in (forest.get("day_reviews") or {}).items() if d < hit)
                forest = forest_data.rebuild(forest, out["trees"], {d for d in days if d < hit}, reviews)
            # tonight's asteroid, only once it is sure no review today is still on its way
            if out["doom"] and _shows("doom", ago_date(0), live):
                extras["doom"] = out["doom"]
        elif level == "wild":
            trees, fire = events.set_fire(forest["trees"], nature_days, forest_data.MAX_INDIVIDUAL_TREES)
            # smoke or a fire, only once the days it goes by are sure (the day it goes out is
            # good news: that may come any time)
            kind = "smoke" if fire and fire["smoke"] else "fire" if fire and fire["trees"] else None
            if kind is None or _shows(kind, ago_date(fire["began"]), live):
                forest, extras["fire"] = dict(forest, trees=trees), fire
        forest = _animals(forest, struck, did)
    forest = dict(forest, trees=events.mark_big_days(forest["trees"]))
    extras["stagnation"] = events.stagnation(forest["trees"], reviewing)
    if extras["stagnation"] and not test and not _new_cards_left(cfg, changed, dids):
        extras["stagnation"] = 0.0  # every card learned: reviewing alone is what is left to do
    if not test:
        extras["backlog"] = _backlog(cfg, changed)
        forest = dict(forest, trees=_mark_cured(forest["trees"], cfg, changed, dids))
    return keep_calm(forest, extras, cfg)


def keep_calm(forest: dict, extras: dict, cfg: dict) -> tuple:
    """(forest, extras) with the bad things taken out on Peaceful - the crows, the tall grass,
    the tumbleweeds - whichever forest it is: every forest drawn goes through here."""
    if not events.calm(nature_level(cfg)):
        return forest, extras
    forest = dict(forest, trees=events.calm_trees(forest["trees"]))
    extras = dict(extras)
    if "stagnation" in extras:
        extras["stagnation"] = 0.0
    if extras.get("backlog"):
        extras["backlog"] = dict(extras["backlog"], hell=0.0)
    return forest, extras


def fire_line(extras: dict) -> str:
    """The journal's line for Wild's fire: the smoke that warns of it, the days you come back
    to it (until you have studied), and the day it goes out."""
    fire = extras.get("fire")
    if not fire:
        return ""
    if fire.get("smoke"):
        return "Smoke is rising from your forest after two days without reviews. Study today, or it catches fire."
    if fire["out"]:
        return "The last of the fire is out. Your forest is green again."
    if not fire["news"]:
        return ""
    n = fire["trees"]
    return (f"A fire broke out while you were away: {n} tree{'s are' if n != 1 else ' is'} burning. "
            f"Study on {events.FIRE_HEAL_DAYS} days to put it out.")


def strike_line(extras: dict) -> str:
    """The journal's line after an asteroid struck, until it has played and for the rest of
    that day - then the new forest has its own news (the caption keeps it for the week)."""
    strike = extras.get("strike")
    if not strike or not strike["news"] or not strike.get("told"):
        return ""
    lost = strike["lost"]
    return f"An asteroid took your forest of {lost} tree{'s' if lost != 1 else ''}. A new one grows from here."


def news_line(extras: dict) -> str:
    """The journal's line for what the events brought today, if anything: an asteroid's
    strike, a fire, or a backlog cleared."""
    line = strike_line(extras) or fire_line(extras)
    if line:
        return line
    backlog = extras.get("backlog")
    if backlog and backlog["cleared"]:
        return "You cleared your overdue reviews" + (". The tumbleweeds blew away." if not events.calm(extras["nature"]) else ".")
    return ""


def mark_seen(key: str) -> None:
    """The page has played the strike `key`: it plays once."""
    state = load_state()
    state.update(strike_seen=key, strike_seen_day=mw.col.sched.today)
    save_state(state)

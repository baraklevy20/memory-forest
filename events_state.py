"""The events - what the way you study brings to the forest - on Anki's side: the Stakes
remembered per profile (when they were chosen, every strike so far), and what the page
needs to show them, with the big days, the tall grass, the cured leeches and the backlog
of overdue reviews. The rules are in events.py, the drawing in web/events/."""

from __future__ import annotations

from aqt import mw

from . import events, forest_data, milestones, study_log
from .state import _profile, excluded_decks, load_state, phone_cards, phone_decks, save_state

# The profiles a sync has finished for this session, and whether one is under way. Until
# a sync has brought in what you studied elsewhere (on your phone, say), a day you studied
# there looks missed here - so no new strike comes before one has, unless the profile
# doesn't sync at all. The strikes already remembered stand all the same.
_synced: set = set()
_syncing = False


def stakes_level(cfg: dict) -> str:
    level = cfg.get("stakes")
    return level if isinstance(level, str) and level in events.STAKES else events.DEFAULT_STAKES


def _stakes_since(level: str) -> int:
    """How many days ago these stakes were chosen (0: today), remembered per profile, so a
    break from before choosing them never counts against them. While the settings dialog
    previews a level it counts from today, and only a level kept once the dialog closes is
    remembered (Cancel changes nothing)."""
    from .settings import is_open

    today = mw.col.sched.today
    state = load_state()
    if state.get("stakes") != level or not isinstance(state.get("stakes_since"), int):
        if is_open():
            return 0
        state.update(stakes=level, stakes_since=today)
        save_state(state)
    return max(0, today - state["stakes_since"])


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


def can_strike() -> bool:
    """Whether a new strike may come now: the review log is all there (a sync has finished
    this session, or the profile doesn't sync), no sync is under way (the forest written for
    your phone as one starts is made from what is here before it), and the settings dialog
    isn't previewing (Cancel must undo everything)."""
    from .settings import is_open

    return not _syncing and (_profile() in _synced or not _syncs()) and not is_open()


def _strikes() -> tuple:
    """Every strike remembered, as days ago, oldest first."""
    today = mw.col.sched.today
    days = sorted({d for d in load_state().get("strike_days") or [] if isinstance(d, int)})
    return tuple(today - d for d in days if d <= today)


def _remember_strikes(hits: list) -> None:
    """Add `hits` (days ago) to the strikes remembered, so no later change of level can
    undo one."""
    today = mw.col.sched.today
    state = load_state()
    known = {d for d in state.get("strike_days") or [] if isinstance(d, int)}
    days = known | {today - ago for ago in hits}
    if days != known:
        state["strike_days"] = sorted(days)
        save_state(state)


# the days with reviews, as the Stakes count them, until the collection or the day changes
_days_cache: tuple = (None, set())


def _stakes_days() -> set:
    """The days you studied anything at all (see study_log.load_review_days), but the note
    that carries the forest to your phone: looking at it there is not studying."""
    global _days_cache
    col = mw.col
    phone, cards = phone_decks(), phone_cards()
    # the collection itself is part of the key: another profile's may have the same mod
    key = (col, getattr(col, "mod", None), col.sched.day_cutoff, frozenset(phone), frozenset(cards))
    if key[1] is None or _days_cache[0] != key:
        _days_cache = (key, study_log.load_review_days(col.db, col.sched.day_cutoff, phone, cards))
    return _days_cache[1]


def strike_payload(out: dict, seen_key: str, date) -> dict:
    """What the page needs to show the craters and play the latest strike. The journal
    speaks of it (`told`) until it has played, and for the rest of that day."""
    latest = out["latest"]
    before = forest_data.merge_old({"trees": latest["before"]})
    state = load_state()
    fresh = state.get("strike_seen") != seen_key
    return {
        "craters": [dict({k: v for k, v in c.items() if k != "key"}, date=date(c["ago"])) for c in out["craters"]],
        "strike": {"date": date(latest["ago"]), "lost": latest["lost"], "before": before["trees"], "merged": before.get("merged"),
                   "seen": seen_key, "fresh": fresh,
                   "news": latest["ago"] <= events.STRIKE_NEWS_DAYS,
                   "told": fresh or state.get("strike_seen_day") == mw.col.sched.today},
    }


def ago_date(ago: int) -> str:
    return study_log.day_date(ago, mw.col.sched.day_cutoff).isoformat()


def _backlog(cfg: dict) -> dict:
    """The overdue reviews, how deep in review hell they put you, and whether today is the
    day you cleared them (and if so, how deep it `was`) - remembering, per profile, the last
    day of review hell, how deep it was then, and the last backlog cleared."""
    col = mw.col
    today = col.sched.today
    overdue, counts = study_log.load_backlog(col.db, today, col.sched.day_cutoff, events.REVIEW_HELL_USUAL_DAYS, excluded_decks(cfg),
                                             phone_cards())
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


def _mark_cured(trees: list, cfg: dict) -> list:
    """The trees, each holding a leech cured lately copied with `cured` (how many)."""
    cured = study_log.load_cured(mw.col.db, mw.col.sched.day_cutoff, events.CURED_DAYS, excluded_decks(cfg), phone_cards())
    return [dict(t, cured=cured[t["ago"]]) if cured.get(t["ago"]) else t for t in trees] if cured else trees


def _animals(forest: dict, craters: list) -> dict:
    """The forest with every animal that has come to it since the last asteroid (`craters`),
    remembered per profile: once come, an animal stays, and is new on the day it came. The
    first look at a forest remembers the animals it already has without announcing them all
    at once, and nothing the settings dialog previews is remembered."""
    from .settings import is_open

    today = mw.col.sched.today
    struck = today - craters[-1]["ago"] if craters else None  # the day the forest began again
    state = load_state()
    known = state.get("animals")
    first = not isinstance(known, dict)
    if first or state.get("animals_struck") != struck:
        known = {}  # an asteroid sent them away: they have to be earned again
    known = {k: v for k, v in known.items() if v is None or type(v) is int}
    arrived = milestones.arrivals(forest["stats"], known, None if first or is_open() else today)
    if not is_open() and (arrived != state.get("animals") or state.get("animals_struck") != struck):
        state.update(animals=arrived, animals_struck=struck)
        save_state(state)
    return dict(forest, visitors=milestones.visitors(forest["stats"], arrived, today))


def apply(forest: dict, cfg: dict, test: bool) -> tuple:
    """The forest after the stakes have had their say, and everything else the way you
    study brings to it: (forest, extras for the page)."""
    level = stakes_level(cfg)
    days = forest.get("review_days") or set()
    extras = {"stakes": level, "craters": [], "strike": None, "doom": None}
    if not test:
        since = _stakes_since(level)
        # the Stakes go by every deck you study, whichever the forest leaves out
        new = can_strike()
        out = events.apply_stakes(forest["trees"], _stakes_days(), level, since, _strikes(), new)
        if new:
            _remember_strikes(out["hits"])
        if out["craters"]:
            extras.update(strike_payload(out, ago_date(out["latest"]["ago"]), ago_date))
            # the forest now: only what grew since, its streak, reviews and animals counted from
            # there - the animals have to be earned again, as the trees do
            struck = out["craters"][-1]["ago"]
            reviews = sum(n for d, n in (forest.get("day_reviews") or {}).items() if d < struck)
            forest = forest_data.rebuild(forest, out["trees"], {d for d in days if d < struck}, reviews)
        forest = _animals(forest, out["craters"])
        extras["doom"] = out["doom"]
    forest = dict(forest, trees=events.mark_big_days(forest["trees"]))
    extras["stagnation"] = events.stagnation(forest["trees"], days)
    if not test:
        extras["backlog"] = _backlog(cfg)
        forest = dict(forest, trees=_mark_cured(forest["trees"], cfg))
    if events.calm(level):  # Peaceful: the good things only
        forest = dict(forest, trees=events.calm_trees(forest["trees"]))
        extras["stagnation"] = 0.0
        if extras.get("backlog"):
            extras["backlog"] = dict(extras["backlog"], hell=0.0)
    return forest, extras


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
    strike, or a backlog cleared."""
    if strike_line(extras):
        return strike_line(extras)
    backlog = extras.get("backlog")
    if backlog and backlog["cleared"]:
        return "You cleared your overdue reviews" + (". The tumbleweeds blew away." if not events.calm(extras["stakes"]) else ".")
    return ""


def mark_seen(key: str) -> None:
    """The page has played the strike `key`: it plays once."""
    state = load_state()
    state.update(strike_seen=key, strike_seen_day=mw.col.sched.today)
    save_state(state)

"""The events - what the way you study brings to the forest - on Anki's side: the Stakes
remembered per profile (when they were chosen, every strike so far), and what the page
needs to show them, with the big days and the tall grass. The rules are in events.py, the
drawing in web/events/."""

from __future__ import annotations

from aqt import mw

from . import events, forest_data, study_log
from .state import load_state, save_state


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


def _strikes_seen(hits: list) -> tuple:
    """Every strike so far, as days ago: those remembered, and `hits` (just worked out) added
    to them, so no later change of level can undo one."""
    today = mw.col.sched.today
    state = load_state()
    known = {d for d in state.get("strike_days") or [] if isinstance(d, int)}
    days = known | {today - ago for ago in hits}
    if days != known:
        state["strike_days"] = sorted(days)
        save_state(state)
    return tuple(today - d for d in sorted(days) if d <= today)


def strike_payload(out: dict, seen_key: str, date) -> dict:
    """What the page needs to show the craters and play the latest strike."""
    latest = out["latest"]
    before = forest_data.merge_old({"trees": latest["before"]})
    return {
        "craters": [dict({k: v for k, v in c.items() if k != "key"}, date=date(c["ago"])) for c in out["craters"]],
        "strike": {"date": date(latest["ago"]), "lost": latest["lost"], "before": before["trees"], "merged": before.get("merged"),
                   "seen": seen_key, "fresh": load_state().get("strike_seen") != seen_key,
                   "news": latest["ago"] <= events.STRIKE_NEWS_DAYS},
    }


def ago_date(ago: int) -> str:
    return study_log.day_date(ago, mw.col.sched.day_cutoff).isoformat()


def apply(forest: dict, cfg: dict, test: bool) -> tuple:
    """The forest after the stakes have had their say, and everything else the way you
    study brings to it: (forest, extras for the page)."""
    level = stakes_level(cfg)
    days = forest.get("review_days") or set()
    extras = {"stakes": level, "craters": [], "strike": None, "doom": None}
    if not test:
        since = _stakes_since(level)
        out = events.apply_stakes(forest["trees"], days, level, since, _strikes_seen([]))
        _strikes_seen(out["hits"])
        if out["craters"]:
            extras.update(strike_payload(out, ago_date(out["latest"]["ago"]), ago_date))
            # the forest now: only what grew since, its streak and animals counted from there
            forest = forest_data.rebuild(forest, out["trees"], {d for d in days if d < out["craters"][-1]["ago"]})
        extras["doom"] = out["doom"]
    forest = dict(forest, trees=events.mark_big_days(forest["trees"]))
    extras["stagnation"] = events.stagnation(forest["trees"], days)
    return forest, extras


def strike_line(extras: dict) -> str:
    """The journal's line after an asteroid struck, while it is still news."""
    strike = extras.get("strike")
    if not strike or not strike["news"]:
        return ""
    lost = strike["lost"]
    return f"An asteroid took your forest of {lost} tree{'s' if lost != 1 else ''}. A new one grows from here."


def mark_seen(key: str) -> None:
    """The page has played the strike `key`: it plays once."""
    state = load_state()
    state["strike_seen"] = key
    save_state(state)

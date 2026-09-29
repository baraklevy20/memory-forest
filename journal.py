"""The journal: the one line under the forest, on the days there is something to say.

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt


def _plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def _fmt_date(iso: str) -> str:
    d = _dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


# Counts worth remarking on. A forest passing its hundredth tree is news; its hundred
# and first is not.
TREE_MILESTONES = (1, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000)
STREAK_MILESTONES = (7, 30, 50, 100, 200, 365, 500, 730, 1000)


def journal(forest: dict, mood: dict, today: _dt.date, anniversary_idx: list, evs: list = ()) -> str:
    """One sentence, on the days there is something to say.

    It speaks when something became true today - an animal arrived, a tree turned
    ancient, an anniversary came round, a milestone was passed - and stays quiet
    otherwise, which is most days.
    """
    s = forest["stats"]
    trees = forest["trees"]
    if not trees:
        return "Study some new cards and your first tree will take root here."

    for v in forest.get("visitors", []):
        if v.get("new"):
            if v["key"] == "cabin":
                return "A little cabin now stands at the edge of your forest: a year since your first tree."
            return f"{v['label'].capitalize()} wandered in: {v['why']}."
    night = mood["time"] == "night"
    if "harvest_moon" in evs and night:  # the moon is only drawn at night
        return "A harvest moon rises over your forest's anniversary."
    if "meteor_shower" in evs and night:
        return "Meteors are falling tonight."
    if "new_ancient" in evs:
        return "One of your trees became ancient today." + (" Watch for a shooting star." if night else "")
    if anniversary_idx:
        t = trees[anniversary_idx[0]]
        years = today.year - _dt.date.fromisoformat(t["date"]).year
        span = "a year" if years == 1 else f"{years} years"
        return f"The tree you planted on {_fmt_date(t['date'])} turned {span} old today."

    # milestones, but only on the day they are reached
    if s["planted_today"]:
        if s["trees"] in TREE_MILESTONES:
            if s["trees"] == 1:
                return f"Your first tree. It holds {_plural(s['today_cards'], 'card')}."
            return f"Your {s['trees']}th tree, planted today with {_plural(s['today_cards'], 'new card')}."
        if s["streak"] in STREAK_MILESTONES:
            return f"{s['streak']} days in a row. The forest has not missed one."

    # Nothing happened today that the forest has not already said. A line every day
    # becomes wallpaper; saying nothing is what makes the next line worth reading.
    return ""

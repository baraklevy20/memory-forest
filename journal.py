"""The journal: the one line under the forest, on the days there is something to say.

This module never imports aqt, so it runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt

try:
    from . import i18n
    from .i18n import t, tn, tx
    from .milestones import ARRIVED
except ImportError:  # tests and dev scripts import this as a top-level module
    import i18n
    from i18n import t, tn, tx
    from milestones import ARRIVED


def _fmt_date(iso: str) -> str:
    return i18n.day_month_year(_dt.date.fromisoformat(iso), short=True)


# Counts worth remarking on. A forest passing its hundredth tree is news; its hundred
# and first is not.
TREE_MILESTONES = (1, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000)
STREAK_MILESTONES = (7, 30, 50, 100, 200, 365, 500, 730, 1000)

# the weathers that leave the night sky clear (web/theme.js's clearSky)
CLEAR_SKIES = ("clear", "after_rain")


def journal(forest: dict, mood: dict, today: _dt.date, anniversary_idx: list, evs: list = (), stagnation: float = 0.0) -> str:
    """One sentence, on the days there is something to say.

    It speaks when something became true today - an animal arrived, a tree turned
    ancient, an anniversary came round, a milestone was passed - or, failing that, while
    the grass stands tall, and stays quiet otherwise, which is most days.
    """
    s = forest["stats"]
    trees = forest["trees"]
    if not trees:
        return t("journal.study_some_new_cards_and_your")

    for v in forest.get("visitors", []):
        if v.get("new") and v["key"] in ARRIVED:
            return tx(ARRIVED[v["key"]])
    # the night sky's events are only drawn on a clear night (theme.js): not behind clouds
    starry = mood["time"] == "night" and mood.get("weather") in CLEAR_SKIES
    if "harvest_moon" in evs and starry:
        return t("journal.a_harvest_moon_rises_over_your")
    if "meteor_shower" in evs and starry:
        return t("journal.meteors_are_falling_tonight")
    if "new_ancient" in evs:
        if starry:
            return t("journal.one_of_your_trees_became_ancient_2")
        return t("journal.one_of_your_trees_became_ancient")
    if anniversary_idx:
        tree = trees[anniversary_idx[0]]
        years = today.year - _dt.date.fromisoformat(tree["date"]).year
        date = _fmt_date(tree["date"])
        if years == 1:
            return t("journal.the_tree_you_planted_on_date_2", date=date)
        return tn("journal.the_tree_you_planted_on_date", years, date=date)

    # milestones, but only on the day they are reached
    if s["planted_today"]:
        if s["trees"] in TREE_MILESTONES:
            # ({cards} as written so far: 1234, not 1,234)
            if s["trees"] == 1:
                return tn("journal.your_first_tree_it_holds_n", s["today_cards"], cards=s["today_cards"])
            return tn("journal.your_count_th_tree_planted_today", s["today_cards"], count=s["trees"], cards=s["today_cards"])
        if s["streak"] in STREAK_MILESTONES:
            # ({days} as written so far: 1000, not 1,000)
            return tn("journal.days_days_in_a_row_the", s["streak"], days=s["streak"])

    # the tall grass (`stagnation`, as the page draws it: events_state's, or the Debug tab's)
    # says why it is there for as long as it stands, when there is nothing newer to say
    if stagnation:
        weeks = trees[-1]["ago"] // 7
        if weeks < 2:
            return t("journal.the_grass_is_growing_tall_no_2")
        return tn("journal.the_grass_is_growing_tall_no", weeks)

    # Nothing happened today that the forest has not already said. A line every day
    # becomes wallpaper; saying nothing is what makes the next line worth reading.
    return ""

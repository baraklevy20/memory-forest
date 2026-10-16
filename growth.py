"""Growth, a way to shade the study heatmap (beside Reviews and Time): how much each day's reviews
strengthened your memory, as FSRS models it. A day's score is the median, over the cards you
reviewed that day, of the change in each card's stability from before its first review that day to
after its last: (after - before) / before, as a percentage (20 days to 30 is +50%). Lapses count
(they lower it); a card with no stability before the day (a new one) is left out. A model-based
estimate, not a measurement.

Stability is FSRS's own: the days until recall falls to 90%, whatever retention you asked for. The
values are Anki's, worked out again from each card's review history with its preset's parameters
(Collection.card_stats_data: today's stability alone can't say what it was on a past day). With
FSRS off, or an Anki too old to give them, there is no Growth."""

from __future__ import annotations

from .study_log import DAY_SECS, STUDY_TYPES, _filters

# (the review kinds that are an answer: learning, review, relearning, filtered; not a manual change)
ANSWERS = (0, 1, 2, 3)
# each card's history, kept until it has a newer review or the FSRS parameters change:
# cid -> (its last review's id, the parameters' key, [(time, answered, stability or None)], oldest first)
_cards: dict = {}


def median(values: list) -> float:
    """The middle value (the mean of the two middle ones for an even count). By hand: Anki 2.1.45's
    Python has no statistics module."""
    v = sorted(values)
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def fsrs_on(col) -> bool:
    """Whether the collection schedules with FSRS (so there are stabilities to go by)."""
    try:
        return bool(col.get_config("fsrs", False))
    except Exception:  # (an Anki before FSRS)
        return False


def _params_key(col) -> str:
    """Something that changes when any preset's FSRS parameters do (and so every stability)."""
    try:
        return repr(sorted((c.get("id"), repr(c.get("fsrsParams6") or c.get("fsrsParams5") or c.get("fsrsWeights")))
                           for c in col.decks.all_config()))
    except Exception:
        return ""


def _history(col, cid: int) -> list | None:
    """A card's reviews, oldest first: (epoch seconds, whether it was an answer, the stability after it)."""
    try:
        stats = col.card_stats_data(cid)
    except Exception:
        return None
    out = []
    for e in stats.revlog:
        try:
            s = e.memory_state.stability if e.HasField("memory_state") else None
        except ValueError:  # (an Anki whose card info has no memory states)
            return None
        out.append((e.time, e.button_chosen > 0 and e.review_kind in ANSWERS, s))
    out.sort(key=lambda r: r[0])
    return out


def card_days(history: list, day_cutoff: int) -> dict:
    """{days ago: % change in stability} for one card's history (see the module): each day it was
    answered, from the stability before that day's first answer to the stability after its last;
    none for a day it had no stability before (it was new)."""
    out, prev, day, before, after = {}, None, None, None, None
    for t, answered, s in history:
        ago = (day_cutoff - 1 - t) // DAY_SECS
        if answered and ago != day:
            if day is not None and before and after is not None:
                out[day] = (after - before) / before * 100
            day, before, after = ago, prev, None
        if s is not None:
            prev = s
            if answered and ago == day:
                after = s
    if day is not None and before and after is not None:
        out[day] = (after - before) / before * 100
    return out


def load_day_growth(col, day_cutoff: int, dids: list | None, excluded=None, skip=None) -> dict:
    """{days ago: (the median % change, the cards it is the median of)} for the cards of the `dids`
    decks (None: the whole collection) but the `excluded` decks and `skip` cards; {} without FSRS."""
    if not fsrs_on(col):
        return {}
    _in_decks, only = _filters(dids, excluded, skip)
    key = _params_key(col)
    days: dict = {}
    for cid, last in col.db.all(f"select cid, max(id) from revlog where ease > 0 and type in {STUDY_TYPES} "
                                f"and id < ?{only} group by cid", day_cutoff * 1000):
        hit = _cards.get(cid)
        if hit is None or hit[0] != last or hit[1] != key:
            history = _history(col, cid)
            if history is None:
                continue
            hit = _cards[cid] = (last, key, history)
        for ago, change in card_days(hit[2], day_cutoff).items():
            days.setdefault(ago, []).append(change)
    return {ago: (round(median(v), 1), len(v)) for ago, v in days.items()}

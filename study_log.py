"""What the forest reads from a collection: its cards and review log, fetched once, and
how Anki days map to dates and to searches.

This module never imports aqt, so it runs in unit tests and in the dev export
script against a plain sqlite3 connection.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable
from dataclasses import dataclass

DAY_SECS = 86400

LAPSE_WINDOW_DAYS = 7

# Revlog types 0-3 are real study (learn, review, relearn, filtered). 4+ are manual
# reschedules and resets, which shouldn't plant or date anything.
STUDY_TYPES = "(0, 1, 2, 3)"


@dataclass
class Rows:
    """Everything the forest needs from the database, already fetched."""

    cards: list  # (cid, type, queue, ivl, data_json)
    first_last: dict  # cid -> (first_review_ms, last_review_ms)
    recent_lapses: set  # cids lapsed within LAPSE_WINDOW_DAYS
    review_days: set  # days_ago values that had at least one review
    total_reviews: int
    today_reviews: int


def load_rows(db, day_cutoff: int, dids: list | None = None,
              excluded: Iterable | None = None, since: int | None = None, suspended: bool = False) -> Rows:
    """Fetch rows with a DB object exposing .all(sql, *args) and .scalar(sql, *args).

    With `dids`, only cards in those decks (a deck and its subdecks) and their reviews count.
    With `excluded`, cards whose home deck is one of those don't, and neither do their
    reviews; reviews of deleted cards still do, having no deck left to be excluded by.
    With `since` (a timestamp in seconds), nothing from before it counts: no review, and no
    card first studied before it, since its tree would stand before the forest begins.
    With `suspended`, suspended cards keep their trees (see build_forest for how they count).
    Works with Anki's mw.col.db and with the small sqlite3 wrapper in dev/.
    """
    ids = ",".join(str(int(d)) for d in dids) if dids else ""
    out = ",".join(str(int(d)) for d in excluded) if excluded else ""
    # a card borrowed by a filtered deck has its home deck in odid, which is what
    # Anki's own deck: search follows
    home = "coalesce(nullif(c.odid, 0), c.did)"
    in_decks = (f" and (c.did in ({ids}) or c.odid in ({ids}))" if ids else "") + (f" and {home} not in ({out})" if out else "")
    only = ((f" and cid in (select id from cards c where c.did in ({ids}) or c.odid in ({ids}))" if ids else "")
            + (f" and cid not in (select id from cards c where {home} in ({out}))" if out else ""))
    since_ms = int(since) * 1000 if since else 0
    # every query but the first-and-last one, which needs a card's whole history to date it
    after = only + (f" and id >= {since_ms}" if since_ms else "")
    cards = db.all(
        "select c.id, c.type, c.queue, c.ivl, c.data "
        "from cards c "
        f"where c.type != 0{'' if suspended else ' and c.queue != -1'}{in_decks}"
    )
    first_last = {
        cid: (first, last)
        for cid, first, last in db.all(
            f"select cid, min(id), max(id) from revlog "
            f"where ease > 0 and type in {STUDY_TYPES}{only} group by cid"
        )
    }
    if since_ms:
        cards = [row for row in cards if first_last.get(row[0], (row[0],))[0] >= since_ms]
    lapse_since_ms = (day_cutoff - LAPSE_WINDOW_DAYS * DAY_SECS) * 1000
    recent_lapses = {
        row[0] for row in db.all(f"select distinct cid from revlog where type = 1 and ease = 1 and id > ?{after}", lapse_since_ms)
    }
    review_days = {
        row[0]
        for row in db.all(
            f"select distinct (? - 1 - id / 1000) / {DAY_SECS} from revlog "
            f"where ease > 0 and type in {STUDY_TYPES} and id < ?{after}",
            day_cutoff,
            day_cutoff * 1000,
        )
    }
    total = db.scalar(f"select count() from revlog where ease > 0 and type in {STUDY_TYPES}{after}") or 0
    today = db.scalar(
        f"select count() from revlog where ease > 0 and type in {STUDY_TYPES} and id >= ?{after}",
        (day_cutoff - DAY_SECS) * 1000,
    ) or 0
    return Rows(cards, first_last, recent_lapses, review_days, total, today)


def load_deck_days(db, day_cutoff: int, dids: list, suspended: bool = False) -> set:
    """The `ago` values of the trees a deck would grow, without building its forest.

    Deck screens only need to know which of the main forest's trees hold this deck's
    cards, and that is one query instead of the whole pipeline.
    """
    ids = ",".join(str(int(d)) for d in dids)
    rows = db.all(
        "select distinct (? - 1 - coalesce((select min(r.id) from revlog r "
        f"where r.cid = c.id and r.ease > 0 and r.type in {STUDY_TYPES}), c.id) / 1000) / {DAY_SECS} "
        f"from cards c where c.type != 0{'' if suspended else ' and c.queue != -1'} and (c.did in ({ids}) or c.odid in ({ids}))",
        day_cutoff,
    )
    return {int(row[0]) for row in rows if row[0] is not None and row[0] >= 0}


def day_search(days_ago_from: int, until_days_ago: int | None = None, suspended: bool = False) -> list:
    """Anki search terms for the cards a tree (or the deep forest) holds.

    `introduced:N` means "first studied within the last N days", so one day is the
    difference of two of them. Unless the forest keeps suspended cards (`suspended`), they
    are excluded, because the forest does not count them either - without that the
    tooltip and the browser disagree.
    """
    newest = days_ago_from if until_days_ago is None else until_days_ago
    terms = [f"introduced:{days_ago_from + 1}"] + ([] if suspended else ["-is:suspended"])
    if newest > 0:
        terms.append(f"-introduced:{newest}")
    return terms


def days_ago(ts_seconds: float, day_cutoff: int) -> int:
    """0 for today's Anki day, 1 for yesterday, ... (respects the rollover hour)."""
    return int((day_cutoff - 1 - ts_seconds) // DAY_SECS)


def day_date(days: int, day_cutoff: int) -> _dt.date:
    """Calendar date of an Anki day (the day that ends at the matching cutoff)."""
    return _dt.datetime.fromtimestamp(day_cutoff - days * DAY_SECS - DAY_SECS // 2).date()


def day_start(date: _dt.date, day_cutoff: int) -> int:
    """When the Anki day on this calendar date began: at the rollover hour, not midnight."""
    days = (day_date(0, day_cutoff) - date).days
    return day_cutoff - (days + 1) * DAY_SECS


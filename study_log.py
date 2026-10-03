"""What the forest reads from a collection: its cards and review log, fetched once, and
how Anki days map to dates and to searches.

This module never imports aqt, so it runs in unit tests and in the dev export
script against a plain sqlite3 connection.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable
from dataclasses import dataclass, field

DAY_SECS = 86400

LAPSE_WINDOW_DAYS = 7

# Revlog types 0-3 are real study (learn, review, relearn, filtered). 4+ are manual
# reschedules and resets, which shouldn't plant or date anything.
STUDY_TYPES = "(0, 1, 2, 3)"

# Only cards studied within this many days count as a leech: an abandoned deck's old
# leeches say nothing about how you study now.
ACTIVE_DAYS = 60

# A leech whose interval has grown to this many days (mature, as Anki counts it) is cured:
# it keeps Anki's leech tag, but brings no crow (see events.CURED_DAYS for its songbird).
CURED_IVL = 21


@dataclass
class Rows:
    """Everything the forest needs from the database, already fetched."""

    cards: list  # (cid, type, queue, ivl, data_json)
    first_last: dict  # cid -> (first_review_ms, last_review_ms)
    recent_lapses: set  # cids lapsed within LAPSE_WINDOW_DAYS
    review_days: set  # days_ago values that had at least one review
    total_reviews: int
    today_reviews: int
    leeches: set = field(default_factory=set)  # cids of active cards tagged leech (suspended ones too)
    day_reviews: dict = field(default_factory=dict)  # days_ago -> how many reviews that day


def load_rows(db, day_cutoff: int, dids: list | None = None,
              excluded: Iterable | None = None, since: int | None = None, suspended: bool = False,
              skip: Iterable | None = None, log: ReviewLog | None = None) -> Rows:
    """Fetch rows with a DB object exposing .all(sql, *args) and .scalar(sql, *args).

    With `dids`, only cards in those decks (a deck and its subdecks) and their reviews count.
    With `excluded`, cards whose home deck is one of those don't, and neither do their
    reviews; reviews of deleted cards still do, having no deck left to be excluded by.
    With `since` (a timestamp in seconds), nothing from before it counts: no review, and no
    card first studied before it, since its tree would stand before the forest begins.
    With `suspended`, suspended cards keep their trees (see build_forest for how they count).
    With `skip` (card ids), those cards and their reviews never count, deleted or not: the
    ones that carry the forest to your phone.
    With `log`, the review log's totals come from it, kept from the last call (see
    ReviewLog): on a big collection, reading the whole log is most of the time this takes.
    Works with Anki's mw.col.db and with the small sqlite3 wrapper in dev/.
    """
    in_decks, only = _filters(dids, excluded, skip)
    since_ms = int(since) * 1000 if since else 0
    # every query but the first-and-last one, which needs a card's whole history to date it
    after = only + (f" and id >= {since_ms}" if since_ms else "")
    cards = db.all(
        "select c.id, c.type, c.queue, c.ivl, c.data "
        "from cards c "
        f"where c.type != 0{'' if suspended else ' and c.queue != -1'}{in_decks}"
    )
    first_last, day_reviews = (log or ReviewLog()).read(db, day_cutoff, only, since_ms)
    if since_ms:
        cards = [row for row in cards if first_last.get(row[0], (row[0],))[0] >= since_ms]
    lapse_since_ms = (day_cutoff - LAPSE_WINDOW_DAYS * DAY_SECS) * 1000
    recent_lapses = {
        row[0] for row in db.all(f"select distinct cid from revlog where type = 1 and ease = 1 and id > ?{after}", lapse_since_ms)
    }
    # the totals come from the days' counts: today's is day 0's
    total, today = sum(day_reviews.values()), day_reviews.get(0, 0)
    # leeches only count among cards studied lately (see ACTIVE_DAYS)
    active_ms = (day_cutoff - ACTIVE_DAYS * DAY_SECS) * 1000
    active = {cid for cid, (_first, last) in first_last.items() if last >= active_ms}
    leeches = {row[0] for row in db.all(
        f"select c.id from cards c join notes n on n.id = c.nid where lower(n.tags) like '% leech %' "
        f"and c.ivl < {CURED_IVL}{in_decks}")} & active
    return Rows(cards, first_last, recent_lapses, set(day_reviews), total, today, leeches, dict(day_reviews))


class ReviewLog:
    """The review log's totals for one choice of decks and dates - each card's first and
    last review, and each day's count of reviews - kept between redraws. Read whole the first
    time, and after that only the reviews added since: a review session adds a few hundred
    rows to a log that can hold hundreds of thousands. It is read whole again when the day
    or the choice changes, or the newest review is gone (an undo).

    A card moved in or out of a deck the forest leaves out, with no review since, changes
    which of its old reviews count; the add-on reads the log whole again after each sync
    and at the start of each day (see payload.py), which catches that."""

    def __init__(self):
        self.key = None
        self.newest = 0
        self.first_last: dict = {}
        self.day_reviews: dict = {}

    def read(self, db, day_cutoff: int, only: str, since_ms: int) -> tuple:
        """(first_last, day_reviews) as load_rows has always counted them: `only` is
        _filters' condition on the review log, `since_ms` when the forest begins."""
        key = (day_cutoff, only, since_ms)
        newest = db.scalar("select max(id) from revlog") or 0
        if key != self.key or newest < self.newest:
            self._read_all(db, day_cutoff, only, since_ms, newest)
            self.key = key
        elif newest > self.newest:
            self._add(db, day_cutoff, only, since_ms, newest)
        self.newest = newest
        return self.first_last, self.day_reviews

    def _read_all(self, db, day_cutoff: int, only: str, since_ms: int, newest: int) -> None:
        # up to `newest` only: a review made meanwhile is added next time, not counted twice.
        # Not by the cid index: walking the whole table in order is about twice as fast
        self.first_last = {
            cid: (first, last)
            for cid, first, last in db.all(
                f"select cid, min(id), max(id) from revlog not indexed "
                f"where ease > 0 and type in {STUDY_TYPES} and id <= ?{only} group by cid", newest)
        }
        since = f" and id >= {since_ms}" if since_ms else ""
        self.day_reviews = dict(
            db.all(
                f"select (? - 1 - id / 1000) / {DAY_SECS}, count() from revlog "
                f"where ease > 0 and type in {STUDY_TYPES} and id < ? and id <= ?{only}{since} group by 1",
                day_cutoff, day_cutoff * 1000, newest,
            )
        )

    def _add(self, db, day_cutoff: int, only: str, since_ms: int, newest: int) -> None:
        for cid, rid in db.all(f"select cid, id from revlog where id > ? and id <= ? and ease > 0 "
                               f"and type in {STUDY_TYPES}{only}", self.newest, newest):
            first, last = self.first_last.get(cid, (rid, rid))
            self.first_last[cid] = (min(first, rid), max(last, rid))
            if rid < day_cutoff * 1000 and rid >= since_ms:
                day = (day_cutoff - 1 - rid // 1000) // DAY_SECS
                self.day_reviews[day] = self.day_reviews.get(day, 0) + 1


def _filters(dids: list | None, excluded: Iterable | None, skip: Iterable | None = None) -> tuple:
    """SQL to add to a query's conditions for the decks and cards that count (see load_rows):
    one for a query on cards (as c), one for a query on the review log."""
    ids = ",".join(str(int(d)) for d in dids) if dids else ""
    out = ",".join(str(int(d)) for d in excluded) if excluded else ""
    cids = ",".join(str(int(c)) for c in skip) if skip else ""
    # a card borrowed by a filtered deck has its home deck in odid, which is what
    # Anki's own deck: search follows
    home = "coalesce(nullif(c.odid, 0), c.did)"
    in_decks = ((f" and (c.did in ({ids}) or c.odid in ({ids}))" if ids else "") + (f" and {home} not in ({out})" if out else "")
                + (f" and c.id not in ({cids})" if cids else ""))
    only = ((f" and cid in (select id from cards c where c.did in ({ids}) or c.odid in ({ids}))" if ids else "")
            + (f" and cid not in (select id from cards c where {home} in ({out}))" if out else "")
            + (f" and cid not in ({cids})" if cids else ""))
    return in_decks, only


def load_review_days(db, day_cutoff: int, excluded: Iterable | None = None, skip: Iterable | None = None) -> set:
    """The days (as `ago`) with at least one review anywhere in the collection but the
    `excluded` decks and the `skip` cards, whatever the forest leaves out or starts after: what
    Nature goes by, so leaving a deck out never makes the days you studied only that deck
    count as missed."""
    _in_decks, only = _filters(None, excluded, skip)
    return {day for (day,) in db.all(
        f"select distinct (? - 1 - id / 1000) / {DAY_SECS} from revlog "
        f"where ease > 0 and type in {STUDY_TYPES} and id < ?{only}", day_cutoff, day_cutoff * 1000)}


def load_backlog(db, today: int, day_cutoff: int, days: int, excluded: Iterable | None = None,
                 skip: Iterable | None = None) -> tuple:
    """(how many reviews are overdue - due before today - and the review counts of the days
    you studied among the `days` before today), for the whole collection but the `excluded`
    decks and the `skip` cards. `today` is the scheduler's day number. A card borrowed by a
    filtered deck is due when its home deck has it due (odue)."""
    in_decks, only = _filters(None, excluded, skip)
    overdue = db.scalar(
        "select count() from cards c where c.queue in (2, 3) "
        f"and (case when c.odid != 0 and c.odue != 0 then c.odue else c.due end) < ?{in_decks}", today) or 0
    counts = [n for _day, n in db.all(
        f"select (? - 1 - id / 1000) / {DAY_SECS}, count() from revlog "
        f"where ease > 0 and type in {STUDY_TYPES} and id >= ? and id < ?{only} group by 1",
        day_cutoff, (day_cutoff - (days + 1) * DAY_SECS) * 1000, (day_cutoff - DAY_SECS) * 1000)]
    return overdue, counts


def has_new_cards(db, excluded: Iterable | None = None, skip: Iterable | None = None) -> bool:
    """Whether any new card is left to learn in the whole collection but the `excluded` decks
    and the `skip` cards: suspended ones don't count, buried ones do (they come back)."""
    in_decks, _only = _filters(None, excluded, skip)
    return bool(db.scalar(f"select exists (select 1 from cards c where c.type = 0 and c.queue != -1{in_decks})"))


def load_cured(db, day_cutoff: int, days: int, excluded: Iterable | None = None, skip: Iterable | None = None) -> dict:
    """The leeches cured (see CURED_IVL) within the last `days` days and still cured, counted
    by the day of the tree each belongs to (its first review): {ago: how many}."""
    in_decks, _only = _filters(None, excluded, skip)
    since_ms = (day_cutoff - days * DAY_SECS) * 1000
    out: dict = {}
    for _cid, first in db.all(
        f"select c.id, (select min(r.id) from revlog r where r.cid = c.id and r.ease > 0 and r.type in {STUDY_TYPES}) "
        "from cards c join notes n on n.id = c.nid "
        f"where lower(n.tags) like '% leech %' and c.queue != -1 and c.ivl >= {CURED_IVL}{in_decks} "
        f"and exists (select 1 from revlog r where r.cid = c.id and r.ivl >= {CURED_IVL} "
        f"and r.lastIvl < {CURED_IVL} and r.id >= ?)", since_ms):
        if first is None:
            continue
        ago = days_ago(first / 1000, day_cutoff)
        if ago >= 0:
            out[ago] = out.get(ago, 0) + 1
    return out


def load_deck_days(db, day_cutoff: int, dids: list, suspended: bool = False, skip: Iterable | None = None) -> set:
    """The `ago` values of the trees a deck would grow, without building its forest.

    Deck screens only need to know which of the main forest's trees hold this deck's
    cards, and that is one query instead of the whole pipeline. The `skip` cards hold none.
    """
    ids = ",".join(str(int(d)) for d in dids)
    not_skipped, _only = _filters(None, None, skip)
    rows = db.all(
        "select distinct (? - 1 - coalesce((select min(r.id) from revlog r "
        f"where r.cid = c.id and r.ease > 0 and r.type in {STUDY_TYPES}), c.id) / 1000) / {DAY_SECS} "
        f"from cards c where c.type != 0{'' if suspended else ' and c.queue != -1'} and (c.did in ({ids}) or c.odid in ({ids})){not_skipped}",
        day_cutoff,
    )
    return {int(row[0]) for row in rows if row[0] is not None and row[0] >= 0}


def load_tree_days(db, day_cutoff: int, skip: Iterable | None = None) -> dict:
    """Every tree each deck holds, for the settings to count without building a forest:
    {home deck: {ago: True if a card first studied that day is not suspended}}.

    A card belongs to its home deck (a filtered deck only borrows it) and is dated as
    build_forest dates it: by its first review, or its id if it has none. The `skip` cards
    hold no tree. One query; tree_days does the counting for any choice of decks, start
    and suspended cards.
    """
    not_skipped, _only = _filters(None, None, skip)
    out: dict = {}
    for did, ago, active in db.all(
            "select coalesce(nullif(c.odid, 0), c.did), (? - 1 - coalesce((select min(r.id) from revlog r "
            f"where r.cid = c.id and r.ease > 0 and r.type in {STUDY_TYPES}), c.id) / 1000) / {DAY_SECS}, "
            f"max(c.queue != -1) from cards c where c.type != 0{not_skipped} group by 1, 2", day_cutoff):
        if ago is not None and ago >= 0:
            out.setdefault(did, {})[int(ago)] = bool(active)
    return out


def tree_days(days: dict, dids: Iterable, since_ago: int | None = None, suspended: bool = True) -> set:
    """The trees (as `ago`) the decks `dids` grow together, from load_tree_days' answer:
    none older than `since_ago` days, and none made only of suspended cards unless the
    forest keeps them (`suspended`)."""
    out = set()
    for did in dids:
        for ago, active in days.get(did, {}).items():
            if (suspended or active) and (since_ago is None or ago <= since_ago):
                out.add(ago)
    return out


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


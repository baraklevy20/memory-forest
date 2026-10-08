"""What the forest counts: the decks it leaves out, where its days begin and end, and whether
the study data changed since it was last read."""

from __future__ import annotations

import datetime as _dt

from aqt import mw

from . import study_log
from .phone_note import phone_cards, phone_decks
from .state import config


def excluded_decks(cfg: dict | None = None) -> set:
    """Every deck left out of the forest: the ones unticked in the settings and all their
    subdecks, found afresh each time, so a deck made or moved under one later is out too.
    The deck the add-on keeps for the note that takes the forest to your phone is always out
    (the note's cards themselves are left out wherever they are: see phone_cards)."""
    out = phone_decks()
    for did in (cfg if cfg is not None else config()).get("excluded_decks") or []:
        try:
            out.update(mw.col.decks.deck_and_child_ids(int(did)))
        except Exception:  # a hand edit, or a deck deleted since
            continue
    return out


def changes():
    """Where the study data stands, read cheaply (a few ms on a big collection): the newest
    review, and the latest change to any card or note - but the note that carries the forest
    to your phone and its cards, which the add-on rewrites itself at every sync. What the
    forest is built from can only have changed if this has. (The collection's own modified
    time changes far more often - picking a deck, the phone's note - and each change used to
    cost a whole rebuild.) None when the collection can't say."""
    col = mw.col
    if col is None:
        return None
    cids = ",".join(str(int(c)) for c in phone_cards())
    not_phone = f" where id not in ({cids})" if cids else ""
    not_phone_note = f" where id not in (select nid from cards where id in ({cids}))" if cids else ""
    try:
        return (getattr(col, "path", None) or id(col), col.db.scalar("select max(id) from revlog"),
                *col.db.all(f"select max(mod), count() from cards{not_phone}")[0],
                col.db.scalar(f"select max(mod) from notes{not_phone_note}"))
    except Exception:  # an older or unusual collection: rebuild every time, as before
        return None


def day_cutoff(col) -> int:
    """When the collection's day ends, as a timestamp: the scheduler's day_cutoff, which
    Anki before 2.1.50 calls dayCutoff."""
    sched = col.sched
    return sched.day_cutoff if hasattr(sched, "day_cutoff") else sched.dayCutoff


def since(cfg: dict) -> int | None:
    """When the forest begins (the Ignore before setting), as a timestamp, or None."""
    try:
        date = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
    except ValueError:
        return None
    return study_log.day_start(date, day_cutoff(mw.col))


def deck_ids(did: int, excluded: set) -> list:
    """A deck and its subdecks, less those left out of the forest."""
    return [d for d in mw.col.decks.deck_and_child_ids(did) if d not in excluded]

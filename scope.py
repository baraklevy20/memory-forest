"""What the forest counts: the decks it leaves out, where its days begin and end, and whether
the study data changed since it was last read."""

from __future__ import annotations

import datetime as _dt

from aqt import mw

from . import study_log
from .phone_note import phone_cards, phone_decks
from .state import config, keeps_earlier_trees


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


def anki_today(cutoff: int | None = None) -> _dt.date:
    """Today as Anki counts it, by its rollover hour: until then, still yesterday's date."""
    return study_log.day_date(0, day_cutoff(mw.col) if cutoff is None else cutoff)


def since(cfg: dict) -> int | None:
    """When the forest begins (the Ignore before setting), as a timestamp, or None. Never
    later than Anki's today: a date picked after midnight, before the rollover, is today."""
    try:
        date = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
    except ValueError:
        return None
    cutoff = day_cutoff(mw.col)
    return study_log.day_start(min(date, anki_today(cutoff)), cutoff)


def trees_since(cfg: dict) -> int | None:
    """When the forest's trees begin, as a timestamp, or None: the start date, unless the trees
    from before it are kept (then only the breaks, Nature and the animals go by it: since)."""
    return None if keeps_earlier_trees(cfg) else since(cfg)


def counts_since(cfg: dict, cutoff: int) -> int | None:
    """The start date as days ago, while the trees from before it are kept: the day the forest's
    ponds and animals count from. None otherwise (the forest itself begins there, or has no start)."""
    begin = since(cfg) if keeps_earlier_trees(cfg) else None
    return None if begin is None else study_log.days_ago(begin, cutoff)


def _filtered_subdecks(did: int) -> tuple:
    """A deck and its subdecks, and those of them that are filtered decks."""
    family = mw.col.decks.deck_and_child_ids(did)
    if len(family) == 1:
        return family, set()
    real = {d.id for d in mw.col.decks.all_names_and_ids(include_filtered=False)}
    return family, {d for d in family if d != did and d not in real}


def deck_ids(did: int, excluded: set) -> list:
    """A deck and its subdecks, less those left out of the forest and the filtered ones: a card
    counts for its home deck, not a deck that has it on loan (its home's id finds it there)."""
    family, filtered = _filtered_subdecks(did)
    return [d for d in family if d not in excluded and d not in filtered]


def borrowed_from_elsewhere(did: int) -> list:
    """The cards that filtered subdecks of the deck `did` have on loan from outside it: Anki's
    deck: search finds them under `did`, but they count for their own home decks."""
    family, filtered = _filtered_subdecks(did)
    if not filtered:
        return []
    inside, lent = ",".join(str(int(d)) for d in family), ",".join(str(int(d)) for d in filtered)
    return [cid for (cid,) in mw.col.db.all(f"select id from cards where did in ({lent}) and odid not in ({inside}) order by id")]

"""Telling the note that carries the forest to your phone apart from your own study: the note
itself (whose being there is the "Show my forest on my phone" setting), its deck, and its
cards, whose reviews never count. phone.py writes the note; everything that reads your study
leaves these out."""

from __future__ import annotations

from aqt import mw

from .state import load_state, save_state

# the note type of the note that takes the forest to your phone (phone.py)
PHONE_NOTETYPE = "Memory Forest"
# where older versions kept the "Show my forest on my phone" switch, in the collection's
# config: no longer read (see phone_on), only taken away when the switch is next used
OLD_PHONE_SWITCH = "memoryForestPhone"


def phone_note_ids(col) -> list:
    """The notes that carry the forest to your phone (phone.py), oldest first: those of every
    note type of ours (two computers that each made one before they synced leave two)."""
    try:
        mids = [e.id for e in col.models.all_names_and_ids() if e.name == PHONE_NOTETYPE]
    except AttributeError:  # an Anki without it: the one its name finds
        m = col.models.by_name(PHONE_NOTETYPE)
        mids = [m["id"]] if m else []
    if not mids:
        return []
    return col.db.list(f"select id from notes where mid in ({','.join('?' * len(mids))}) order by id", *mids)


def phone_on(col=None) -> bool:
    """Whether the forest goes to the phone in this collection: whether its note is there.
    The note is the switch, so every computer sees the same once synced, and turning it off
    can't be undone by a sync. A config entry could: Anki syncs the collection's config as
    one piece, from whichever device changed anything last, so a phone that had only opened
    a deck since put its old "on" back over the "off" a computer had just synced."""
    col = mw.col if col is None else col
    return col is not None and bool(phone_note_ids(col))


# the deck phone.py makes for the note that takes the forest to your phone
PHONE_DECK = "Memory Forest"
# phone_decks' and phone_cards' last answers, and the collection and modification time they were for
_phone_decks: tuple = (None, None, frozenset())
_phone_cards: tuple = (None, None, frozenset())


def phone_decks() -> set:
    """The add-on's own deck for the note that carries the forest to your phone (phone.py),
    found by its name: the settings and the gear menu don't offer it, and it grows no forest.
    Never the deck its card happens to be in, which may be one of yours."""
    global _phone_decks
    try:
        col = mw.col
        mod = col.mod
        if _phone_decks[0] is col and _phone_decks[1] == mod:
            return set(_phone_decks[2])
        did = col.decks.id_for_name(PHONE_DECK)
        found = {did} if did else set()
    except Exception:  # no collection yet
        return set()
    _phone_decks = (col, mod, frozenset(found))
    return found


def phone_cards() -> set:
    """The cards of the note that carries the forest to your phone, wherever they are now,
    and every one it ever had here (remembered per profile once seen, since Anki keeps the
    reviews of a deleted card, and another computer's sync may be what deletes it): answering one is looking at the forest,
    not studying, so no review of theirs ever counts. Asked several times a redraw, so the
    answer is kept until the collection next changes."""
    global _phone_cards
    try:
        col = mw.col
        mod = col.mod
        if _phone_cards[0] is col and _phone_cards[1] == mod:
            return set(_phone_cards[2])
        m = col.models.by_name(PHONE_NOTETYPE)
        found = set(col.db.list("select id from cards where nid in (select id from notes where mid = ?)", m["id"])) if m else set()
    except Exception:  # no collection yet
        return set()
    if found:  # remembered as soon as seen, so a note deleted by a sync from elsewhere is too
        remember_phone_cards(found)
    found |= {c for c in load_state().get("phone_cards") or [] if isinstance(c, int)}
    _phone_cards = (col, mod, frozenset(found))
    return found


def remember_phone_cards(cids) -> None:
    """Keep leaving out the reviews of these cards once they are gone (see phone_cards)."""
    global _phone_cards
    state = load_state()
    known = {c for c in state.get("phone_cards") or [] if isinstance(c, int)}
    if set(cids) - known:
        state["phone_cards"] = sorted(known | set(cids))
        save_state(state)
    _phone_cards = (None, None, frozenset())

"""The small message the first time a new card is studied each day: today's tree is planted."""

from __future__ import annotations

import traceback

from aqt import mw
from aqt.utils import tooltip

from . import study_log
from .phone_note import phone_cards
from .scope import day_cutoff, excluded_decks
from .state import config, load_state, log, save_state

PLANTING_TOOLTIP_MS = 3500

_planted_today: str | None = None


def on_answer(reviewer, card, ease) -> None:
    """A small tooltip the first time a new card is studied each day."""
    cfg = config()
    if not cfg.get("planting_tooltip", True):
        return
    global _planted_today
    # the Anki day, not the calendar day: studying at 00:30 still joins yesterday's tree
    today = study_log.day_date(0, day_cutoff(mw.col)).isoformat()
    if _planted_today == today:  # already shown this session, no need to touch the disk
        return
    try:
        if mw.col.db.scalar("select count() from revlog where cid = ?", card.id) != 1:
            return
        if (card.odid or card.did) in excluded_decks(cfg) or card.id in phone_cards():  # plants nothing in the forest
            return
        state = load_state()
        if state.get("last_planted") == today:
            _planted_today = today
            return
        state["last_planted"] = today
        save_state(state)
        _planted_today = today
        tooltip("🌱 A new tree was planted in your forest today.", period=PLANTING_TOOLTIP_MS)
    except Exception:
        log("planting tooltip failed:\n" + traceback.format_exc())

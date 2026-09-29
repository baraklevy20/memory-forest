"""What the forest does when it is clicked, and the deck list's gear-menu entry: open the
settings, open the browser on a tree's cards, leave a deck out or bring it back."""

from __future__ import annotations

import traceback

from anki.collection import SearchNode
from aqt import dialogs, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.utils import tooltip

from . import events_state, study_log
from .panel import refresh
from .phone import follow_setting
from .state import MODULE, config, excluded_decks, keeps_suspended, log, phone_decks, save_config


def settings_changed() -> None:
    """After any change to the config: redraw, and make or take away the phone's deck."""
    refresh()
    follow_setting()


def open_settings() -> None:
    from .settings import open_settings as _open

    _open(MODULE, settings_changed)


def browse_day(days_ago: int, did: int | None = None, until_days_ago: int | None = None) -> None:
    """Open the browser on the cards first studied on that day (same rule as the trees), or
    on everything from that day up to `until_days_ago` when the deep forest is clicked."""
    terms = study_log.day_search(days_ago, until_days_ago, keeps_suspended())
    name = mw.col.decks.name_if_exists(did) if did else None
    if name:  # deck names can hold quotes and colons, so let Anki quote it
        terms.insert(0, mw.col.build_search_string(SearchNode(deck=name)))
    # the decks left out of the forest planted none of its trees (a deck: search takes
    # their subdecks with them)
    for out in config().get("excluded_decks") or []:
        try:
            out_name = mw.col.decks.name_if_exists(int(out))
        except (TypeError, ValueError):
            continue
        if out_name:
            terms.append(mw.col.build_search_string(SearchNode(negated=SearchNode(deck=out_name))))
    browser = dialogs.open("Browser", mw)
    browser.search_for(" ".join(terms))


def on_js_message(handled, message, context):
    if not isinstance(context, (DeckBrowser, Overview)) or not isinstance(message, str) or not message.startswith(MODULE + ":"):
        return handled
    cmd = message.split(":")[1:]
    try:
        if cmd[0] == "settings":
            open_settings()
        elif cmd[0] == "struck" and len(cmd) > 1:
            events_state.mark_seen(":".join(cmd[1:]))
        elif cmd[0] == "browse":
            browse_day(int(cmd[1]),
                       int(cmd[2]) if len(cmd) > 2 and cmd[2] else None,
                       int(cmd[3]) if len(cmd) > 3 and cmd[3] else None)
    except Exception:
        log(f"could not handle {message}:\n" + traceback.format_exc())
    return (True, None)


LEFT_OUT = "Left out of your forest. Its ⚙ menu brings it back."
BROUGHT_BACK = "Back in your forest."


def on_deck_options_menu(menu, did: int) -> None:
    """Leave a deck out of the forest, or bring it back, from its gear menu in the deck list."""
    try:
        deck = mw.col.decks.get(did, default=False)
        if not deck or deck.get("dyn") or did in phone_decks():  # the phone's deck is the forest itself
            return
        cfg = config()
        mine = [int(d) for d in cfg.get("excluded_decks") or [] if str(d).lstrip("-").isdigit()]
        if did in mine:
            action = menu.addAction("Bring back into Memory Forest")
            action.triggered.connect(lambda: _set_excluded([d for d in mine if d != did], BROUGHT_BACK))
        elif did in excluded_decks(cfg):
            action = menu.addAction("Left out of Memory Forest with its parent deck")
            action.setEnabled(False)
        else:
            action = menu.addAction("Leave out of Memory Forest")
            action.triggered.connect(lambda: _set_excluded(mine + [did], LEFT_OUT))
    except Exception:
        log("could not add to the deck menu:\n" + traceback.format_exc())


def _set_excluded(dids: list, message: str) -> None:
    cfg = config()
    cfg["excluded_decks"] = sorted(set(dids))
    save_config(cfg)
    refresh()
    tooltip(message)

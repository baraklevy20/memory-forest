"""The forest panel on the deck list and on a deck's own screen: its HTML, the scripts it
loads, and redrawing it in place when anything changes."""

from __future__ import annotations

import json
import os
import traceback

from aqt import mw

from .catalog import core_scripts, draft_scripts, scenery_files
from .payload import payload
from .scope import excluded_decks
from .state import MODULE, config, log, shows_on_deck_list

WEB = f"/_addons/{MODULE}/web"
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
BOOT = "forest.js"  # mounts straight away, so it goes last of all
# the panel and its data are named after this add-on's folder, so a second copy of it
# (the public edition installed beside this one) draws its own forest, not over this one
ROOT = f"memory-forest-{MODULE}"


def _url(rel: str) -> str:
    """A file's address for the page, with its modification time on the end. Anki's web
    view caches add-on files by address, so without it an updated add-on keeps running
    yesterday's scripts next to today's."""
    try:
        stamp = int(os.path.getmtime(os.path.join(WEB_DIR, rel)))
    except OSError:
        stamp = 0
    return f"{WEB}/{rel}?v={stamp}"


def _panel_parts(did: int | None = None, highlight: bool = False) -> tuple:
    """(element id, data as JSON, scripts before the boot script) for one forest panel."""
    info = payload(did, highlight)
    mood = info["mood"]
    data = json.dumps(info, ensure_ascii=False).replace("</", "<\\/")
    # only the pieces this scene actually needs are loaded, and each lives in one file of its own
    srcs = [_url(s) for s in core_scripts() + draft_scripts()] + [_url(rel) for rel in scenery_files(mood)] + [_url(BOOT)]
    srcs.pop()  # the boot script: the page adds it last, and a swap has no need of it
    return ROOT, data, srcs


def _panel_html(did: int | None = None, highlight: bool = False) -> str:
    root, data, srcs = _panel_parts(did, highlight)
    boot = _url(BOOT)
    return (
        f'<link rel="stylesheet" href="{_url("forest.css")}">'
        + f'<div id="{root}" class="af-panel"></div>'
        + f'<script type="application/json" id="{root}-data">{data}</script>'
        + "".join(f'<script src="{src}"></script>' for src in srcs)
        + f'<script src="{boot}" data-root="{root}"></script>'
    )


def on_deck_browser(deck_browser, content) -> None:
    if not shows_on_deck_list():  # switched off: only the deck screens have one
        return
    try:
        # content.tree renders inside a <table>, so a block there would be hoisted above
        # the decks; the start of the stats section sits directly below the deck list.
        content.stats = _panel_html() + content.stats
    except Exception:
        log("could not render the forest:\n" + traceback.format_exc())


def on_overview(overview, content) -> None:
    """A forest on a deck's own screen: grown from that deck and its subdecks, or the main
    forest with that deck's trees lit (the Deck screens setting)."""
    cfg = config()
    mode = cfg.get("deck_forest_mode", "highlight")
    if mode not in ("highlight", "own"):
        if mode != "off":
            log(f"unknown deck_forest_mode {mode!r}; showing no deck forest")
        return
    try:
        deck = mw.col.decks.current()
        if deck.get("dyn"):  # filtered decks borrow cards from elsewhere; skip them
            return
        if deck["id"] in excluded_decks(cfg):  # left out of the forest: it has none
            return
        content.table += _panel_html(deck["id"], highlight=mode == "highlight")
    except Exception:
        log("could not render the deck forest:\n" + traceback.format_exc())


def refresh() -> None:
    """Redraw the forest with the current config (no restart needed).

    The forest is swapped in place, inside the page that is already showing: reloading
    the whole deck list would blank the screen for a moment on every change. Only when
    there is no forest there to swap (or it should now be gone) does the page reload.
    """
    if mw.col is None:  # still starting up, or between profiles
        return
    if mw.state == "deckBrowser":
        if shows_on_deck_list():
            _swap_or_reload(mw.deckBrowser.web, mw.deckBrowser.refresh)
        else:  # a forest just switched off is still on the page: draw the list again without it
            js = f"!!document.getElementById({json.dumps(ROOT)})"
            mw.deckBrowser.web.evalWithCallback(js, lambda there: mw.deckBrowser.refresh() if there else None)
    elif mw.state == "overview":
        mode = config().get("deck_forest_mode", "highlight")
        deck = mw.col.decks.current()
        if mode in ("highlight", "own") and not deck.get("dyn") and deck["id"] not in excluded_decks():
            _swap_or_reload(mw.overview.web, mw.overview.refresh, deck["id"], mode == "highlight")
        else:
            mw.overview.refresh()


def _swap_or_reload(web, reload, did: int | None = None, highlight: bool = False) -> None:
    try:
        root, data, srcs = _panel_parts(did, highlight)
    except Exception:
        log("could not rebuild the forest:\n" + traceback.format_exc())
        return
    # through the panel itself: another copy of the add-on on the page has a swap of its own
    js = (f"(function () {{ const r = document.getElementById({json.dumps(root)}); "
          f"return r && r.afSwap ? r.afSwap({data}, {json.dumps(srcs)}) : false; }})()")
    web.evalWithCallback(js, lambda swapped: None if swapped else reload())

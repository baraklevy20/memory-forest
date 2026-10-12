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
from .state import MODULE, calendar_on, config, log, shows_on_deck_list, shows_on_finished

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


def _main_panel() -> tuple | None:
    """What the deck list shows: (show the forest, show the study calendar), or None for no
    panel at all. Each is a setting of its own, so either may show without the other."""
    cfg = config()
    forest, calendar = shows_on_deck_list(cfg), calendar_on("main", cfg)
    return (forest, calendar) if forest or calendar else None


def _deck_panel(deck: dict) -> tuple | None:
    """What a deck's screen shows: (its deck id, the main forest with that deck lit rather than
    a forest of its own, show the forest), or None for no panel. A filtered deck has none, nor
    does one left out of the forest. With only the calendar showing, the panel is built as the
    lit-up kind: the main forest is kept built, so that costs nothing."""
    cfg = config()
    if deck.get("dyn") or deck["id"] in excluded_decks(cfg):
        return None
    mode = cfg.get("deck_forest_mode", "highlight")
    if mode not in ("highlight", "own", "off"):
        log(f"unknown deck_forest_mode {mode!r}; showing no deck forest")
        mode = "off"
    forest = mode != "off"
    if not forest and not calendar_on("decks", cfg):
        return None
    return deck["id"], mode != "own", forest


def _panel_parts(did: int | None = None, highlight: bool = False, show_forest: bool = True) -> tuple:
    """(element id, data as JSON, scripts before the boot script) for one forest panel."""
    info = payload(did, highlight, show_forest)
    mood = info["mood"]
    data = json.dumps(info, ensure_ascii=False).replace("</", "<\\/")
    # only the pieces this scene actually needs are loaded, and each lives in one file of its own
    srcs = [_url(s) for s in core_scripts() + draft_scripts()] + [_url(rel) for rel in scenery_files(mood)] + [_url(BOOT)]
    srcs.pop()  # the boot script: the page adds it last, and a swap has no need of it
    return ROOT, data, srcs


def _panel_html(did: int | None = None, highlight: bool = False, show_forest: bool = True) -> str:
    root, data, srcs = _panel_parts(did, highlight, show_forest)
    boot = _url(BOOT)
    return (
        f'<link rel="stylesheet" href="{_url("forest.css")}">'
        + f'<div id="{root}" class="af-panel"></div>'
        + f'<script type="application/json" id="{root}-data">{data}</script>'
        + "".join(f'<script src="{src}"></script>' for src in srcs)
        + f'<script src="{boot}" data-root="{root}"></script>'
    )


def on_deck_browser(deck_browser, content) -> None:
    shows = _main_panel()
    if shows is None:  # both switched off: only the deck screens have one
        return
    try:
        # content.tree renders inside a <table>, so a block there would be hoisted above
        # the decks; the start of the stats section sits directly below the deck list.
        content.stats = _panel_html(show_forest=shows[0]) + content.stats
    except Exception:
        log("could not render the forest:\n" + traceback.format_exc())


def on_overview(overview, content) -> None:
    """A forest on a deck's own screen: grown from that deck and its subdecks, or the main
    forest with that deck's trees lit (the Deck screens setting), and the deck's own study
    calendar under it (or on its own)."""
    try:
        shows = _deck_panel(mw.col.decks.current())
        if shows is None:
            return
        content.table += _panel_html(*shows)
    except Exception:
        log("could not render the deck forest:\n" + traceback.format_exc())


def on_page_loaded(web) -> None:
    """A deck's screen once you have finished it: Anki shows its congratulations page in the
    overview's place, a page of its own that never asks overview_will_render_content, so the
    panel is added to it once it has loaded, as on_overview adds it to the usual screen (and
    is only added where there is none: the usual screen has one already)."""
    if web is not getattr(mw.overview, "web", None) or mw.state != "overview" or mw.col is None or not shows_on_finished():
        return
    if not _on_congrats(web):  # (the usual screen, with its panel already: nothing to build)
        return
    try:
        shows = _deck_panel(mw.col.decks.current())
        if shows is None:
            return
        root, data, srcs = _panel_parts(*shows)
    except Exception:
        log("could not render the finished deck's forest:\n" + traceback.format_exc())
        return
    # the panel's pieces put in by hand, in order (scripts added this way run in the order
    # they were added only when not async), the boot script last, as _panel_html has them
    js = (f"(function () {{ if (document.getElementById({json.dumps(root)})) return;"
          f" const box = document.createElement('div'); box.className = 'af-finished';"
          f" const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = {json.dumps(_url('forest.css'))};"
          f" const el = document.createElement('div'); el.id = {json.dumps(root)}; el.className = 'af-panel';"
          f" const d = document.createElement('script'); d.type = 'application/json'; d.id = {json.dumps(root + '-data')};"
          f" d.textContent = JSON.stringify({data});"
          f" box.append(css, el, d); document.body.append(box);"
          f" for (const src of {json.dumps(srcs + [_url(BOOT)])}) {{ const s = document.createElement('script');"
          f" s.src = src; s.async = false; if (src.indexOf({json.dumps(BOOT)}) >= 0) s.dataset.root = {json.dumps(root)};"
          f" box.append(s); }} }})()")
    web.eval(js)


def _on_congrats(web) -> bool:
    """Whether the overview shows Anki's congratulations page (a finished deck) rather than
    its own screen."""
    try:
        return "congrats" in web.url().toString()
    except Exception:
        return False


def refresh() -> None:
    """Redraw the forest with the current config (no restart needed).

    The forest is swapped in place, inside the page that is already showing: reloading
    the whole deck list would blank the screen for a moment on every change. Only when
    there is no forest there to swap (or it should now be gone) does the page reload.
    """
    if mw.col is None:  # still starting up, or between profiles
        return
    if mw.state == "deckBrowser":
        shows = _main_panel()
        if shows is not None:
            _swap_or_reload(mw.deckBrowser.web, mw.deckBrowser.refresh, show_forest=shows[0])
        else:  # a forest just switched off is still on the page: draw the list again without it
            js = f"!!document.getElementById({json.dumps(ROOT)})"
            mw.deckBrowser.web.evalWithCallback(js, lambda there: mw.deckBrowser.refresh() if there else None)
    elif mw.state == "overview":
        shows = _deck_panel(mw.col.decks.current())
        web = mw.overview.web
        if shows is not None and _on_congrats(web):
            # a finished deck's page (on_page_loaded): the panel taken off it as it is, or swapped,
            # or put on it again, with no reload of Anki's own page
            if shows_on_finished():
                _swap_or_reload(web, lambda: on_page_loaded(web), *shows)
            else:
                web.eval("document.querySelectorAll('.af-finished').forEach(e => e.remove())")
        elif shows is not None:
            _swap_or_reload(web, mw.overview.refresh, *shows)
        else:
            mw.overview.refresh()


def _swap_or_reload(web, reload, did: int | None = None, highlight: bool = False, show_forest: bool = True) -> None:
    try:
        root, data, srcs = _panel_parts(did, highlight, show_forest)
    except Exception:
        log("could not rebuild the forest:\n" + traceback.format_exc())
        return
    # through the panel itself: another copy of the add-on on the page has a swap of its own
    js = (f"(function () {{ const r = document.getElementById({json.dumps(root)}); "
          f"return r && r.afSwap ? r.afSwap({data}, {json.dumps(srcs)}) : false; }})()")
    web.evalWithCallback(js, lambda swapped: None if swapped else reload())

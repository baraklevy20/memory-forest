"""The forest panel on the deck list and on a deck's own screen: its HTML, the scripts it
loads, and redrawing it in place when anything changes."""

from __future__ import annotations

import json
import os
import time
import traceback

from aqt import mw
from aqt.qt import QShortcut

from . import bars, onigiri
from .catalog import core_scripts, draft_scripts, scenery_files
from .edition import manifest
from .payload import payload
from .scope import excluded_decks
from .state import MODULE, calendar_on, config, log, shows_on_deck_list, shows_on_finished

WEB = f"/_addons/{MODULE}/web"
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
BOOT = "forest.js"  # mounts straight away, so it goes last of all
# the panel and its data are named after this add-on's folder, so a second copy of it
# (the public edition installed beside this one) draws its own forest, not over this one
ROOT = f"memory-forest-{MODULE}"
# the study calendar in a tile of its own on Onigiri's grid (on_deck_browser_calendar)
CALENDAR_ROOT = ROOT + "-calendar"


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


# Onigiri's two tiles in one drawing of the deck list: what the first worked out, handed to the
# second rather than worked out again (the whole forest, its events and its heatmap, twice a drawing).
# Taken once, and only a moment after: the next drawing works it out afresh
_shared: dict = {}
SHARE_S = 2.0


def _info(did: int | None, highlight: bool, show_forest: bool, share: bool) -> dict:
    """payload(); with `share`, the other tile drawn in the same pass takes what this one worked out."""
    kept = _shared.pop((did, highlight), None)
    if kept and time.monotonic() - kept[0] < SHARE_S:
        info = kept[1]
    else:
        info = payload(did, highlight, show_forest or share)
        if share:
            _shared[(did, highlight)] = (time.monotonic(), info)
    # (as payload() has it for the heatmap alone: no forest, and no what's-new note on it)
    return info if show_forest or info.get("showForest") is False else dict(info, showForest=False, news=None)


def _panel_parts(did: int | None = None, highlight: bool = False, show_forest: bool = True,
                 show_calendar: bool = True, root: str = ROOT, share: bool = False) -> tuple:
    """(element id, data as JSON, scripts before the boot script) for one forest panel; without
    its study calendar when that has a tile of its own (_split); `share`, _info."""
    info = _info(did, highlight, show_forest, share)
    if not show_calendar:
        info = dict(info, calendar=None)
    mood = info["mood"]
    data = json.dumps(info, ensure_ascii=False).replace("</", "<\\/")
    # only the pieces this scene actually needs are loaded, and each lives in one file of its own
    # (and those the heatmap's look needs: a scenery's own tile style, heatmap_look.page_look)
    look = (info.get("calendar") or {}).get("look") or {}
    srcs = ([_url(s) for s in core_scripts() + draft_scripts()] + [_url(rel) for rel in scenery_files(mood)]
            + [_url(rel) for rel in look.get("files") or [] if rel not in scenery_files(mood) + list(draft_scripts())] + [_url(BOOT)])
    srcs.pop()  # the boot script: the page adds it last, and a swap has no need of it
    return root, data, srcs


def _panel_html(did: int | None = None, highlight: bool = False, show_forest: bool = True,
                show_calendar: bool = True, root: str = ROOT, share: bool = False) -> str:
    root, data, srcs = _panel_parts(did, highlight, show_forest, show_calendar, root, share)
    boot = _url(BOOT)
    return (
        f'<link rel="stylesheet" href="{_url("forest.css")}">'
        + f'<div id="{root}" class="af-panel"></div>'
        + f'<script type="application/json" id="{root}-data">{data}</script>'
        + "".join(f'<script src="{src}"></script>' for src in srcs)
        + f'<script src="{boot}" data-root="{root}"></script>'
    )


def on_deck_browser(deck_browser, content) -> None:
    """The panel under the deck list. Its name is kept: Onigiri, which draws the deck list as a
    grid of widgets, lists each callback there as a widget named after the add-on and keeps a
    placed one by its module and name. There it is the forest's tile, with the study calendar
    under it until the calendar's own tile is on the grid too (on_deck_browser_calendar)."""
    release_shortcuts()  # (first: a mark being named is gone with the page, whatever fails below)
    shows = _main_panel()
    if shows is None:  # both switched off: only the deck screens have one
        return
    split = _split()
    if split and not shows[0]:  # (the calendar alone, in its own tile: this one is left out)
        return
    try:
        # content.tree renders inside a <table>, so a block there would be hoisted above
        # the decks; the start of the stats section sits directly below the deck list.
        content.stats = _panel_html(show_forest=shows[0], show_calendar=not split, share=_both_tiles(shows)) + content.stats
    except Exception:
        log("could not render the forest:\n" + traceback.format_exc())


def on_deck_browser_calendar(deck_browser, content) -> None:
    """The study calendar's own tile on Onigiri's grid, Memory Forest Heatmap there
    (CALENDAR_TILE). Once on the grid it draws the calendar, and the forest's tile no longer
    does; until then, and on Anki's own deck list, it adds nothing."""
    if not _split():
        return
    shows = _main_panel()
    if shows is None or not shows[1]:
        return
    try:
        content.stats = _panel_html(show_forest=False, root=CALENDAR_ROOT, share=_both_tiles(shows)) + content.stats
    except Exception:
        log("could not render the study calendar:\n" + traceback.format_exc())


# Onigiri names a widget after the first part of its callback's module, which Anki takes for an
# add-on's folder: a folder of this name has none, so Anki names it by the folder, and the gallery
# lists the calendar's tile under a name of its own, beside Memory Forest, rather than as a second
# Memory Forest (offered only once the first was placed). The name is kept: a placed tile is kept
# by it ("<module>.<name>"). (no " - " in it: Onigiri's gallery takes a name up to one as the
# add-on's, and offers one of each.) Only Onigiri reads it; the callback is still this module's.
# Named after this copy's edition, Memory Forest Plus Heatmap beside Memory Forest Plus: with both
# editions installed, one name for both was one tile, which Onigiri gave the last one loaded


def tile_name(name: str | None) -> str:
    """The calendar's tile name for an edition named `name` (its manifest's)."""
    return f"{name or 'Memory Forest'} Heatmap"


CALENDAR_TILE = tile_name(manifest().get("name"))
on_deck_browser_calendar.__module__ = CALENDAR_TILE


def _split() -> bool:
    """Whether the study calendar has a tile of its own on Onigiri's grid."""
    return onigiri.is_placed(on_deck_browser_calendar)


def _both_tiles(shows: tuple) -> bool:
    """Whether Onigiri draws both tiles, the forest's and the calendar's, in each drawing (_info)."""
    return bool(shows[0] and shows[1]) and _split() and onigiri.is_placed(on_deck_browser)


def on_overview(overview, content) -> None:
    """A forest on a deck's own screen: grown from that deck and its subdecks, or the main
    forest with that deck's trees lit (the Deck screens setting), and the deck's own study
    calendar under it (or on its own)."""
    release_shortcuts()  # (first, as on_deck_browser)
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
    if web is not getattr(mw.overview, "web", None):
        return
    # a page of the main window loaded afresh (the congratulations page after a sync, or after
    # an unbury) takes a mark being named with it, and no render hook says so (release_shortcuts)
    release_shortcuts()
    if mw.state != "overview" or mw.col is None:
        return
    if not _on_congrats(web):  # (the usual screen, with its panel already: nothing to build)
        return
    try:
        shows = _deck_panel(mw.col.decks.current()) if shows_on_finished() else None
        if shows is None:  # (and no forest behind it: Anki's own bars, bars.py)
            bars.tint([])
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


_held: list = []  # the main window's shortcuts switched off while a name is typed (hold_shortcuts)


def hold_shortcuts(hold: bool) -> None:
    """Switch the main window's shortcuts off while a mark's name is typed on the deck list (its
    one-key ones, d, s, a, b, t and y, would act on every letter typed), and back on after."""
    if hold and not _held:
        _held.extend(s for s in mw.findChildren(QShortcut) if s.isEnabled())
        for s in _held:
            s.setEnabled(False)
    elif not hold:
        for s in _held:
            try:
                s.setEnabled(True)
            except RuntimeError:  # (one Anki has dropped since, on a change of screen)
                pass
        _held.clear()


def release_shortcuts(*_args) -> None:
    """The shortcuts back on when the page a mark's name was typed on goes (a redraw, a reload
    after a sync, another screen): that page never says it stopped typing (hold_shortcuts)."""
    hold_shortcuts(False)


def refresh() -> None:
    """Redraw the forest with the current config (no restart needed).

    The forest is swapped in place, inside the page that is already showing: reloading
    the whole deck list would blank the screen for a moment on every change. Only when
    there is no forest there to swap (or it should now be gone) does the page reload.
    """
    if mw.col is None:  # still starting up, or between profiles
        return
    release_shortcuts()  # (the swap takes a mark being named away without a word from the page)
    if mw.state == "deckBrowser":
        shows, web = _main_panel(), mw.deckBrowser.web
        if shows is not None and _split():
            # Onigiri's two tiles, each swapped on its own; one that should now be there, or gone,
            # draws the list again
            _swap_tiles(web, shows)
        elif shows is not None:
            _swap_or_reload(web, mw.deckBrowser.refresh, show_forest=shows[0])
        else:  # a forest just switched off is still on the page: draw the list again without it
            js = f"!!(document.getElementById({json.dumps(ROOT)}) || document.getElementById({json.dumps(CALENDAR_ROOT)}))"
            web.evalWithCallback(js, lambda there: mw.deckBrowser.refresh() if there else None)
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
        else:  # no panel on this deck's screen: drawn again only if one is still on the page
            js = f"!!document.getElementById({json.dumps(ROOT)})"
            web.evalWithCallback(js, lambda there: mw.overview.refresh() if there else None)


def _swap_tiles(web, shows: tuple) -> None:
    """The deck list's forest and study calendar in Onigiri's tiles of their own (_split), each
    swapped in place; the list drawn again when one should come or go."""
    reload = mw.deckBrowser.refresh
    # (the forest's only where its tile is on the grid too: Onigiri draws no other, so one left off
    # it is never there to swap, and wanting it drew the whole list again on every change)
    want = {ROOT: shows[0] and onigiri.is_placed(on_deck_browser), CALENDAR_ROOT: shows[1]}
    js = f"[{json.dumps(ROOT)}, {json.dumps(CALENDAR_ROOT)}].map(id => !!document.getElementById(id))"

    def swap(there) -> None:
        if not isinstance(there, list) or [bool(t) for t in there] != list(want.values()):
            reload()
            return
        share = _both_tiles(shows)
        if want[ROOT]:
            _swap_or_reload(web, reload, show_forest=True, show_calendar=False, share=share)
        if shows[1]:
            _swap_or_reload(web, reload, show_forest=False, root=CALENDAR_ROOT, share=share)

    web.evalWithCallback(js, swap)


def _swap_or_reload(web, reload, did: int | None = None, highlight: bool = False, show_forest: bool = True,
                    show_calendar: bool = True, root: str = ROOT, share: bool = False) -> None:
    try:
        root, data, srcs = _panel_parts(did, highlight, show_forest, show_calendar, root, share)
    except Exception:
        log("could not rebuild the forest:\n" + traceback.format_exc())
        return
    # through the panel itself: another copy of the add-on on the page has a swap of its own
    js = (f"(function () {{ const r = document.getElementById({json.dumps(root)}); "
          f"return r && r.afSwap ? r.afSwap({data}, {json.dumps(srcs)}) : false; }})()")
    web.evalWithCallback(js, lambda swapped: None if swapped else reload())

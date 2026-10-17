"""The add-on that `old_anki.py --check` installs beside Memory Forest: once the profile is
open it fills the collection with a few months of made-up reviews, so the forest is built
the way it is for everyone (from the study history, not the debug test forest, which a
built add-on does not ship), measures the cog in the real deck list, turns zooming on with
real mouse clicks, picks a tree, steps a day, walks about and back out, opens the settings
and paints every tab of them and the scenery picker, picks another scenery and checks the
forest was built again, writes what it found to check.json in the base folder and quits
Anki. It runs inside that Anki, so it uses only what every Anki it is run in has."""

import ast
import json
import os
import random
import sys
import time
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QEvent, QHeaderView, QMouseEvent, QObject, QPointF, QScrollArea, Qt, QTabBar, QTabWidget, QTimer

FOREST = os.environ.get("MEMORY_FOREST_FOLDER", "anki_forest")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT, LOG = os.path.join(BASE, "check.json"), os.path.join(BASE, "check.log")
COG_PX, COG_ICON_PX = 28, 15  # forest.css's .af-cog box, and core.js's COG icon
WAIT_MS, WAIT_TRIES = 1000, 20  # for the deck list (and the forest's idle-time build) to draw
SEED_CARDS, SEED_DAYS, SEED_REVIEWS = 60, 150, 5  # cards, how far back they start, reviews each
SEED_BIG_CARDS, SEED_BIG_AGO = 12, 20  # of those, first studied together: a big learning day, with flowers
OLD_DAY_AGO = 400  # a study calendar day this far back, past the year rated: may stop at
DIALOG_MAX_H = 672  # pt: the room a 1280 x 720 screen leaves the settings dialog, title bar included
CONSOLE_ERROR = 2  # QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel
# measured in the deck list's page: the cog and its icon, as the page is and again under
# 2.1.50's dark-Mac button styles (Anki's own CSS, keyed on a class Anki only sets when
# macOS itself is dark), whether the forest built (core.js leaves its scene on the panel's
# root as afEnv), how many trees it has, whether it is the one built before the scenery
# changed (marked below), how much of its canvas is painted, and its big days' trees and how
# many columns their flowers drew in (flowers.js notes each, for the grass to leave clear)
MEASURE = """(() => {
  const box = el => el ? (r => [Math.round(r.width), Math.round(r.height)])(el.getBoundingClientRect()) : null;
  const cog = document.querySelector('.af-cog'), icon = cog && cog.querySelector('svg');
  const c = document.querySelector('.af-panel canvas'), classes = document.body.className;
  const plain = { cog: box(cog), icon: box(icon) };
  document.body.classList.add('isMac', 'nightMode', 'macos-dark-mode');
  const darkMac = { cog: box(cog), icon: box(icon) };
  document.body.className = classes;
  let painted = 0;
  if (c) { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    for (let i = 3; i < d.length; i += 4) if (d[i]) painted++;
    painted = Math.round(100 * painted / (c.width * c.height)); }
  const root = [...document.querySelectorAll('*')].find(e => e.afEnv), env = root && root.afEnv;
  const trees = env ? env.placed.filter(q => !q.it.pond).length : 0;
  const big = env ? env.placed.filter(q => q.it.big).length : 0, flowers = env && env.flowerCols ? env.flowerCols.size : 0;
  // the study calendar under it (web/calendar.js): its box, and how many days its canvas holds
  const cal = document.querySelector('.af-cal'), calCanvas = cal && cal.querySelector('canvas');
  const calendar = cal ? { box: box(cal), canvas: calCanvas ? [calCanvas.width, calCanvas.height] : null } : null;
  return JSON.stringify({ plain, darkMac, built: !!env, trees, big, flowers, old: !!(env && env.checkMark), painted, calendar,
                          canvas: c ? [c.width, c.height] : null, classes, agent: navigator.userAgent });
})()"""
# Where the forest's zoom button or a button of its bar is, or a tree to pick (the front-most
# one nearest the middle, which nothing stands in front of), in the page's own pixels; and how
# the zoomed view stands (web/visit.js)
ZOOM_AT = """(sel => {
  const b = document.querySelector(sel);
  if (!b) return JSON.stringify({});
  b.scrollIntoView(false);  // the forest may run past the window's foot: scrolled to, as you would
  const r = b.getBoundingClientRect();
  return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
})"""
ZOOM_TREE = """(() => {
  const root = [...document.querySelectorAll('*')].find(e => e.afEnv), env = root.afEnv;
  const trees = env.placed.filter(q => !q.it.pond), near = Math.max(...trees.map(q => q.y));
  const p = trees.filter(q => q.y > near - 3 * env.u).sort((a, b) => Math.abs(a.x - env.W / 2) - Math.abs(b.x - env.W / 2))[0];
  const c = root.querySelector('canvas'), r = c.getBoundingClientRect(), k = r.width / env.W;
  // just above its foot (the page keeps no AnkiForest to measure its height by)
  return JSON.stringify({ x: r.left + p.x * k, y: r.top + (p.y - 3 * env.u * p.s) * k });
})()"""
ZOOM_STATE = """(() => {
  const root = [...document.querySelectorAll('*')].find(e => e.afEnv), env = root.afEnv;
  const st = root.afVisits.state;
  return JSON.stringify({ on: root.afVisits.on, picked: root.afVisits.picked, zoomed: !!(st && st.cam), bar: !root.querySelector('.af-visit').hidden,
    caption: !root.querySelector('.af-caption').hidden, trees: env.placed.filter(q => !q.it.pond).length,
    xs: env.placed.map(q => Math.round(q.x)).join(), mid: (r => [r.left + r.width / 2, r.top + r.height * 0.6])(root.querySelector('canvas').getBoundingClientRect()) });
})()"""
VISIT_MS = 800  # past the zoom's fade (web/visit.js FADE_MS) and the rebuild
MARK = "(() => { const e = [...document.querySelectorAll('*')].find(e => e.afEnv); if (e) e.afEnv.checkMark = 1; })()"

result = {"anki": None, "qt": None, "errors": [], "problems": [], "steps": []}


def note(line: str) -> None:
    """How far it got, as it goes: if Anki hangs (a dialog waiting for a click), this shows where."""
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _caught(kind, value, tb):
    # kept, not passed on to Anki: its error dialog would wait for a click
    result["errors"].append("".join(traceback.format_exception(kind, value, tb)))
    note("error: " + result["errors"][-1])


note("loaded")
sys.excepthook = _caught


def _console():
    """The web views' console, kept: an error in the forest's page shows only there, and one
    that stops a script (a syntax this Anki's browser does not know) counts as a problem."""
    from aqt.webview import AnkiWebPage
    shown = AnkiWebPage.javaScriptConsoleMessage

    def kept(self, level, msg, line, src):
        said = f"{src.rsplit('/', 1)[-1]}:{line} {msg}"
        result.setdefault("console", []).append(said)
        note(f"console: {said}")
        if getattr(level, "value", level) == CONSOLE_ERROR:
            result["problems"].append("console error: " + said)
        return shown(self, level, msg, line, src)
    AnkiWebPage.javaScriptConsoleMessage = kept


_console()


def _dialogs():
    """Anki's own warnings, kept rather than shown: one about an add-on that failed to load
    (a module an older Anki does not bundle) would otherwise wait for a click, before the
    profile even opens. This add-on loads first (old_anki.py names its folder so), in time
    to catch that one."""
    import aqt.addons
    import aqt.utils

    def kept(text, *_args, **_kwargs):
        result["errors"].append(f"Anki showed: {text}")
        note("dialog: " + str(text))
    for module in (aqt.utils, aqt.addons):
        for name in ("showWarning", "showCritical", "showInfo"):
            if hasattr(module, name):
                setattr(module, name, kept)


_dialogs()


class OffscreenTabs(QObject):
    def eventFilter(self, obj, event):
        # Qt5/mac tab bars call Cocoa border functions on move/show/hide. The
        # offscreen plugin has no Cocoa window. Layout/paint events still run.
        return isinstance(obj, QTabBar) and event.type() in (QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide)


if sys.platform == "darwin" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    from aqt.qt import QT_VERSION_STR
    if QT_VERSION_STR.startswith("5."):
        _offscreen_tabs = OffscreenTabs(mw)
        QApplication.instance().installEventFilter(_offscreen_tabs)


def step(name, fn):
    """Run one step, keeping any error rather than letting Anki show it."""
    note("step: " + name)
    try:
        fn()
        result["steps"].append(name)
    except Exception:
        result["errors"].append(f"{name}:\n{traceback.format_exc()}")
        note("error: " + result["errors"][-1])


def finish():
    note("finish")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    mw.unloadProfileAndExit()


def shot(name: str, web=None) -> None:
    """The deck list (or `web`) as it looks now, beside check.json, for a person to look at."""
    (web or mw.deckBrowser.web).grab().save(os.path.join(BASE, name + ".png"))


def measure(then, tries_left: int = WAIT_TRIES, old_ok: bool = True, web=None):
    """The deck list (or `web`) measured once the forest has built (or WAIT_TRIES seconds
    have gone), handed to `then`; with old_ok False it also waits for a forest other than
    the marked one."""
    def measured(raw):
        note(f"measured: {raw}")
        try:
            got = json.loads(raw)
        except Exception:
            got = {}
        ready = got.get("built") and got.get("painted") and (old_ok or not got.get("old"))
        if not ready and tries_left > 1:
            QTimer.singleShot(WAIT_MS, lambda: measure(then, tries_left - 1, old_ok, web))
            return
        then(got, raw)
    (web or mw.deckBrowser.web).evalWithCallback(MEASURE, measured)


def first_look(got, raw):
    result["deck_list"] = got
    shot("deck-list")
    if not got:
        result["problems"].append(f"the deck list did not answer: {raw!r}")
    for case in ("plain", "darkMac"):
        seen = got.get(case) or {}
        if seen.get("cog") != [COG_PX, COG_PX]:
            result["problems"].append(f"{case}: the cog is {seen.get('cog')}, not {COG_PX}x{COG_PX}")
        if seen.get("icon") != [COG_ICON_PX, COG_ICON_PX]:
            result["problems"].append(f"{case}: the cog's icon is {seen.get('icon')}, not {COG_ICON_PX}x{COG_ICON_PX}")
    cal = got.get("calendar") or {}
    if got.get("built") and not (cal.get("canvas") and (cal.get("box") or [0, 0])[1]):
        result["problems"].append(f"the study calendar did not draw under the forest: {cal or 'none'}")
    if not got.get("built"):
        result["problems"].append("the forest never built")
    elif not got.get("painted"):
        result["problems"].append("the forest built but its canvas is blank")
    elif not got.get("trees"):
        result["problems"].append("the forest built with no trees, from a collection with reviews")
    elif not got.get("big"):
        result["problems"].append(f"no big learning day, though {SEED_BIG_CARDS} cards were first studied {SEED_BIG_AGO} days ago")
    elif not got.get("flowers"):
        result["problems"].append("the big learning day's tree drew no flowers")
    else:
        result["steps"].append(f"flowers on {got['big']} big day(s)")
    QTimer.singleShot(0, visit)


def mouse(web, kind, x: float, y: float, button, held) -> None:
    """One real mouse event at (x, y) of the page, as Qt hands it to the web view (to the widget
    that takes its input), the page zoomed as Anki zooms it."""
    at = QPointF(x * web.zoomFactor(), y * web.zoomFactor())
    QApplication.sendEvent(web.focusProxy() or web, QMouseEvent(kind, at, button, held, Qt.KeyboardModifier.NoModifier))


def click(web, x: float, y: float) -> None:
    """The mouse moved onto (x, y) and clicked there."""
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    mouse(web, QEvent.Type.MouseMove, x, y, none, none)
    mouse(web, QEvent.Type.MouseButtonPress, x, y, left, left)
    mouse(web, QEvent.Type.MouseButtonRelease, x, y, left, none)


DRAG_STEPS, DRAG_PX = 10, 20  # a drag to the left, this many moves this far apart


def drag(web, x: float, y: float) -> None:
    """The mouse pressed at (x, y), dragged to the left and let go, a move at a time."""
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    mouse(web, QEvent.Type.MouseMove, x, y, none, none)
    mouse(web, QEvent.Type.MouseButtonPress, x, y, left, left)
    for i in range(1, DRAG_STEPS + 1):
        mouse(web, QEvent.Type.MouseMove, x - i * DRAG_PX, y, none, left)
        QApplication.processEvents()
    mouse(web, QEvent.Type.MouseButtonRelease, x - DRAG_STEPS * DRAG_PX, y, left, none)


def visit():
    """Zooming in the deck list turned on from the forest's zoom button (its bar in the
    caption's place), a tree picked by clicking it, a day on from the bar (which zooms in to
    that day's tree), walked about by dragging, then the whole forest again from Back."""
    web, state = mw.deckBrowser.web, {}

    def press(selector, then):
        def at(raw):
            got = json.loads(raw or "{}")
            if "x" not in got:
                result["problems"].append(f"nothing to click at {selector}")
                QTimer.singleShot(0, settings)
                return
            click(web, got["x"], got["y"])
            QTimer.singleShot(VISIT_MS, lambda: web.evalWithCallback(ZOOM_STATE, then))
        web.evalWithCallback(ZOOM_TREE if selector == "tree" else ZOOM_AT + f"('{selector}')", at)

    def turned_on(raw):
        got = json.loads(raw or "{}")
        if not got.get("on") or not got.get("bar") or got.get("caption") or got.get("zoomed"):
            result["problems"].append(f"the zoom button did not turn zooming on (and only that): {raw[:200] if raw else raw}")
            QTimer.singleShot(0, settings)
            return
        result["steps"].append("zoom on")
        press("tree", picked)

    def picked(raw):
        got = json.loads(raw or "{}")
        if got.get("picked") is None:
            result["problems"].append(f"a click on a tree did not pick it: {raw[:200] if raw else raw}")
            QTimer.singleShot(0, settings)
            return
        result["steps"].append(f"picked tree {got['picked']}")
        state["picked"] = got["picked"]
        press('.af-visit-btn[data-day]:not([disabled])', stepped)

    def stepped(raw):
        got = json.loads(raw or "{}")
        shot("visit")
        if got.get("picked") == state["picked"] or not got.get("zoomed"):
            result["problems"].append(f"a day step did not go to another tree: {raw[:200] if raw else raw}")
            QTimer.singleShot(0, settings)
            return
        result["steps"].append(f"stepped to tree {got['picked']} ({got['trees']} trees in view)")
        state["before"] = got
        drag(web, *got["mid"])
        QTimer.singleShot(VISIT_MS, lambda: web.evalWithCallback(ZOOM_STATE, dragged))

    def dragged(raw):
        got = json.loads(raw or "{}")
        if not got.get("zoomed") or got.get("xs") == state["before"].get("xs"):
            result["problems"].append(f"a drag did not walk about: {raw[:200] if raw else raw}")
        else:
            result["steps"].append("dragged along the rows")
        press('.af-visit-btn[data-act="back"]', left)

    def left(raw):
        got = json.loads(raw or "{}")
        if got.get("on") or got.get("bar") or not got.get("caption"):
            result["problems"].append(f"Back did not leave the zoomed view: {raw[:200] if raw else raw}")
        else:
            result["steps"].append("back to the whole forest")
        QTimer.singleShot(0, settings)

    note("step: zoom")
    forest = sys.modules.get(FOREST)
    if not getattr(getattr(forest, "payload", None), "ZOOM_RELEASED", True):
        result["steps"].append("zoom held back (payload.ZOOM_RELEASED): not checked")
        QTimer.singleShot(0, settings)
        return
    press(".af-zoom", turned_on)


def settings():
    forest = sys.modules.get(FOREST)
    if forest is None:
        result["problems"].append("the add-on did not load")
        QTimer.singleShot(0, finish)
        return
    state = {}

    def open_all():
        forest.actions.open_settings()
        dialog = state["dialog"] = forest.settings._open
        tabs = dialog.findChild(QTabWidget)
        for i in range(tabs.count()):
            tabs.setCurrentIndex(i)
            QApplication.processEvents()
            tabs.widget(i).grab()  # paints it, and everything in it, now
            result["steps"].append(f"tab {tabs.tabText(i)}")
            # the dialog and this tab's own height (pt), whether it scrolls (widgets.Scrolled: its
            # contents' full height then), and a picture of it
            page = tabs.widget(i)
            scrolls = isinstance(page, QScrollArea)
            own = (page.widget() if scrolls else page).minimumSizeHint().height()
            result.setdefault("dialog_heights", {})[tabs.tabText(i)] = [dialog.minimumSizeHint().height(), own, scrolls]
            if scrolls:  # (on this screen, with room to spare, it should show whole)
                for _ in range(5):
                    QApplication.processEvents()
                result["steps"].append(f"{tabs.tabText(i)} scrolls {page.verticalScrollBar().maximum()} pt"
                                       f" (dialog {dialog.height()} pt)")
            dialog.grab().save(os.path.join(BASE, f"settings-{tabs.tabText(i).lower()}.png"))
        tabs.setCurrentIndex(0)
        # every tab must fit a 1280 x 720 screen (SETTINGS_GUIDELINES.md): the dialog around a tab
        # adds the same to each, Scenery's picker gives back rows on a short screen, and a tab
        # that scrolls fits any
        heights = result["dialog_heights"]
        fixed = [(d, t) for d, t, scrolls in heights.values() if not scrolls]
        around = max(d for d, _t in fixed) - max(t for _d, t in fixed)
        for name, (_d, own, scrolls) in heights.items():
            if name != "Scenery" and not scrolls and own + around > DIALOG_MAX_H:
                result["problems"].append(f"the {name} tab needs {own + around} pt, more than {DIALOG_MAX_H}")

    def picker():
        # the Scenery tab's picker, its tiles painted (the moving ones at their first frame)
        picker = state["dialog"].scenery.picker
        QApplication.processEvents()
        picker.grab()
        # every tile, scrolled out of view or not, for a person to look at
        picker.scroll.widget().grab().save(os.path.join(BASE, "picker.png"))
        result["steps"].append(f"picker: {len(picker.tiles)} tiles")

    def change():
        # another scenery, chosen the way a click on its tile chooses it, then Done: the
        # config must take it and the forest be built again with it
        dialog = state["dialog"]
        box = dialog.scenery.preset
        before = dict(mw.addonManager.getConfig(FOREST) or {})
        box.setCurrentIndex((box.currentIndex() + 1) % box.count())
        state["scenery"] = box.currentData()
        mw.deckBrowser.web.eval(MARK)
        dialog.accept()
        after = mw.addonManager.getConfig(FOREST) or {}
        if after == before:
            result["problems"].append(f"choosing the {state['scenery']} scenery left the config as it was")

    step("settings", open_all)
    if "dialog" not in state:
        QTimer.singleShot(500, finish)
        return
    step("scenery picker", picker)
    step("change scenery", change)
    if "scenery" not in state:
        state["dialog"].reject()
        QTimer.singleShot(500, finish)
        return
    measure(lambda got, raw: changed(state["scenery"], got), old_ok=False)


def changed(scenery, got):
    shot("deck-list-" + str(scenery))
    if not got.get("built") or got.get("old"):
        result["problems"].append(f"the forest was not built again after choosing the {scenery} scenery")
    elif not got.get("painted"):
        result["problems"].append(f"the {scenery} forest built but its canvas is blank")
    else:
        result["steps"].append(f"rebuilt as {scenery}")
    step("phone", phone)
    step("deck screen", deck_screen)
    if "deck screen" in result["steps"]:
        measure(deck_looked, web=mw.overview.web)
    else:
        QTimer.singleShot(500, finish)


def phone():
    """The forest for the phone: turned on, written into its note, its card made new again
    after the phone answered it, then turned off and taken away."""
    forest = sys.modules[FOREST]
    col = mw.col
    forest.phone.switch(True)
    did = col.decks.id_for_name(forest.phone.PHONE_DECK)
    cids = col.db.list("select id from cards where did = ?", did) if did else []
    if not cids:
        result["problems"].append("the phone forest made no card")
        return
    nid = col.db.scalar("select nid from cards where id = ?", cids[0])
    if not col.db.scalar("select flds from notes where id = ?", nid).split("\x1f")[1]:
        result["problems"].append("the phone forest's note has no forest in it")
    col.db.execute("update cards set type = 2, queue = 2, ivl = 3 where id = ?", cids[0])  # studied on the phone
    forest.phone.publish()
    if col.db.scalar("select type from cards where id = ?", cids[0]) != 0:
        result["problems"].append("the phone forest's card was not made new again")
    forest.phone.switch(False)
    if col.decks.id_for_name(forest.phone.PHONE_DECK):
        result["problems"].append("turning the phone forest off left its deck")


def deck_screen():
    """A deck's own screen, which draws a forest of its own."""
    mw.col.decks.select(mw.col.decks.id("Default"))
    mw.moveToState("overview")


def deck_looked(got, raw):
    shot("deck-screen", mw.overview.web)
    if not got.get("built"):
        result["problems"].append("the deck screen's forest never built")
    elif not got.get("painted"):
        result["problems"].append("the deck screen's forest built but its canvas is blank")
    QTimer.singleShot(500, finish)


def catches_import_error(caught) -> bool:
    """Whether an except clause's type (a name, or a tuple of them) takes an ImportError."""
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    return any(isinstance(n, ast.Name) and n.id in ("ImportError", "ModuleNotFoundError") for n in names)


def imports():
    """Every module the add-on imports, anywhere in it (inside a function too, where it
    would fail only when that runs), imported here: the Anki builds before 2.1.50 carry
    only the standard library Anki itself uses."""
    import importlib
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), FOREST)
    names = set()
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    # one tried with a fallback (except ImportError) may be missing
                    guarded = {id(n) for t in ast.walk(tree) if isinstance(t, ast.Try)
                               and any(catches_import_error(h.type) for h in t.handlers)
                               for b in t.body for n in ast.walk(b)}
                    for node in ast.walk(tree):
                        if id(node) in guarded:
                            continue
                        if isinstance(node, ast.Import):
                            names.update(a.name for a in node.names)
                        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                            names.add(node.module)
    # its own modules, which it also names plainly for the unit tests (the fallback after
    # its relative imports) and never imports that way inside Anki
    own = {n[:-3] for _root, _dirs, files in os.walk(folder) for n in files if n.endswith(".py")}
    for name in sorted(n for n in names if n.split(".")[0] not in own):
        try:
            importlib.import_module(name)
        except ImportError as e:
            result["problems"].append(f"this Anki cannot import {name}: {e}")


def seed():
    """SEED_CARDS cards in Default, each first studied up to SEED_DAYS days ago and reviewed
    SEED_REVIEWS times since, written straight into the review log: a history to grow from,
    with the first SEED_BIG_CARDS all first studied SEED_BIG_AGO days ago, a big learning day."""
    col = mw.col
    models = col.models
    model = (models.by_name if hasattr(models, "by_name") else models.byName)("Basic")
    did = col.decks.id("Default")
    for i in range(SEED_CARDS):
        n = col.new_note(model) if hasattr(col, "new_note") else col.newNote()
        n["Front"], n["Back"] = f"front {i}", f"back {i}"
        if hasattr(col, "add_note"):
            col.add_note(n, did)
        else:
            col.addNote(n)
    sched = col.sched
    cutoff = getattr(sched, "day_cutoff", None) or sched.dayCutoff
    rng = random.Random(1)
    for k, cid in enumerate(col.db.list("select id from cards")):
        first = SEED_BIG_AGO if k < SEED_BIG_CARDS else rng.randint(SEED_REVIEWS + 1, SEED_DAYS)
        days = [first] + sorted(rng.sample(range(1, first), SEED_REVIEWS), reverse=True)
        ivl = 1
        for j, ago in enumerate(days):
            stamp = (cutoff - ago * 86400) * 1000 + k * 100 + j
            col.db.execute("insert into revlog values (?,?,?,?,?,?,?,?,?)", stamp, cid, -1, 3, ivl, max(ivl // 2, 0),
                           2500, 5000, 0 if j == 0 else 1)
            ivl = ivl * 2 + 1
        col.db.execute("update cards set type=2, queue=2, ivl=?, due=?, factor=2500, reps=? where id=?",
                       ivl, sched.today + rng.randint(-3, 20), len(days), cid)
    if hasattr(col, "save"):
        col.save()


def old_day():
    """A click on a study calendar day (study_log.calendar_search, as actions.browse_calendar_day
    sends it) finds that day's cards, though studied again since: the seeded card 1 given a
    review OLD_DAY_AGO days back, and a new card with only that review; the searches Anki
    might offer for it tried too, and the reviews and the card taken away again."""
    col = mw.col
    sched = col.sched
    cutoff = getattr(sched, "day_cutoff", None) or sched.dayCutoff
    old = col.db.list("select id from cards order by id limit 1")[0]
    model = (col.models.by_name if hasattr(col.models, "by_name") else col.models.byName)("Basic")
    n = col.new_note(model) if hasattr(col, "new_note") else col.newNote()
    n["Front"] = n["Back"] = "an old day's card"
    if hasattr(col, "add_note"):
        col.add_note(n, col.decks.id("Default"))
    else:
        col.addNote(n)
    alone = n.cards()[0].id
    stamp = (cutoff - (OLD_DAY_AGO + 1) * 86400 + 12 * 3600) * 1000  # (halfway through that Anki day)
    for k, cid in enumerate((old, alone)):
        col.db.execute("insert into revlog values (?,?,?,?,?,?,?,?,?)", stamp + k, cid, -1, 3, 1, 0, 2500, 5000, 1)
    want = sorted([old, alone])

    def tried(search):
        try:
            return sorted(col.find_cards(search))
        except Exception as e:
            return f"error {str(e).splitlines()[0][:60]}"
    try:
        terms = sys.modules[FOREST].study_log.calendar_search(col.db, -OLD_DAY_AGO, sched.today)
        found = tried(" ".join(terms))
        alts = {f"prop:rated=-{OLD_DAY_AGO}": None, f"rated:{OLD_DAY_AGO + 1}": None, f"cid:{old},{alone}": None}
        for search in alts:
            got = tried(search)
            alts[search] = "the day's cards" if got == want else ("both, and more" if isinstance(got, list) and set(want) <= set(got)
                                                                else ("only the recent one" if isinstance(got, list) and old in got
                                                                      else got if isinstance(got, str) else f"{len(got)} cards"))
    finally:
        col.db.execute("delete from revlog where id in (?, ?)", stamp, stamp + 1)
        col.remove_notes([n.id]) if hasattr(col, "remove_notes") else col.remNotes([n.id])
    result["steps"].append(f"day {OLD_DAY_AGO} ago: {' '.join(terms)} found {len(found) if isinstance(found, list) else found}"
                           f" of 2; " + "; ".join(f"{k} -> {v}" for k, v in alts.items()))
    if found != want:
        result["problems"].append(f"a click on a day {OLD_DAY_AGO} days back finds {found}, not its cards {want}:"
                                  f" {' '.join(terms)}")


def heatmap_browser_metrics():
    """Exercise the real browser's hooks, metric cells, sorting, and repeated cleanup."""
    from aqt import dialogs

    def settle():
        # The browser debounces selection/editor updates. Let each real interaction
        # finish before switching modes, searching again or closing its web view.
        end = time.monotonic() + 0.35
        while time.monotonic() < end:
            QApplication.processEvents()
            time.sleep(0.01)

    def open_day(*args, **kwargs):
        settle()
        forest.actions.browse_calendar_day(*args, **kwargs)
        settle()
        editor_ready(dialogs.open("Browser", mw))

    def editor_ready(browser):
        # A newly opened editor loads its JavaScript asynchronously. Searching or
        # closing before saveNow exists races Anki's save-before-action callback.
        if browser.editor.note is None:
            return  # Anki skips saving entirely while the editor has no note.
        end = time.monotonic() + 30
        while time.monotonic() < end:
            ready = []
            browser.editor.web.evalWithCallback("typeof saveNow === 'function'", ready.append)
            while not ready and time.monotonic() < end:
                QApplication.processEvents()
                time.sleep(0.01)
            if ready and ready[0]:
                return
            settle()
        details = []
        browser.editor.web.evalWithCallback("JSON.stringify({url:location.href,ready:document.readyState,scripts:Array.from(document.scripts).map(s=>s.src)})", details.append)
        settle()
        raise AssertionError("browser editor did not finish loading: " + str(details))

    def close_browser(browser):
        settle()
        editor_ready(browser)
        browser.close()
        end = time.monotonic() + 10
        while dialogs._dialogs["Browser"][1] is browser and time.monotonic() < end:
            QApplication.processEvents()
            time.sleep(0.01)
        if dialogs._dialogs["Browser"][1] is browser:
            raise AssertionError("browser did not finish its asynchronous close")
        settle()

    def text_at(data, row, section):
        # Recent Ankis fetch row values asynchronously, returning "..." first.
        end = time.monotonic() + 5
        while True:
            text = data.get_cell(data.index(row, section)).text
            if text != "..." or time.monotonic() >= end:
                return text
            QApplication.processEvents()
            time.sleep(0.01)

    def layout(browser):
        header = browser.table._view.horizontalHeader()
        # The last column stretches to the window's remaining room. Its width is
        # derived geometry, not a user preference: only fixed widths must survive.
        return [(header.logicalIndex(i), None if header.sectionResizeMode(header.logicalIndex(i)) == QHeaderView.ResizeMode.Stretch
                 else header.sectionSize(header.logicalIndex(i))) for i in range(header.count())]

    forest = sys.modules[FOREST]
    col = mw.col
    browser = dialogs.open("Browser", mw)
    # Give the initially empty editor a real note before switching table modes;
    # otherwise its queued selection callback can race the first script load.
    browser.search_for(f"cid:{col.db.scalar('select id from cards order by id limit 1')}")
    settle()
    editor_ready(browser)
    note("heatmap browser: editor ready")
    if browser.table.is_notes_mode():
        browser.table.toggle_state(False, browser.current_search())
    settle()
    header = browser.table._view.horizontalHeader()
    if header.count() > 2:
        header.moveSection(0, 2)
        header.resizeSection(header.logicalIndex(0), 137)
    before = layout(browser)
    browser.table.toggle_state(True, browser.current_search())
    settle()
    if header.count() > 2:
        header.moveSection(2, 0)
        header.resizeSection(header.logicalIndex(0), 194)
    before_notes = layout(browser)
    browser.table.toggle_state(False, browser.current_search())
    settle()
    cutoff = getattr(col.sched, "day_cutoff", None) or col.sched.dayCutoff
    offset = -200
    stamp = (cutoff + (offset - 1) * 86400 + 3600) * 1000
    model = (col.models.by_name if hasattr(col.models, "by_name") else col.models.byName)("Basic")
    # Keep these fixtures until this throwaway profile is discarded. Browser selection
    # callbacks can still run after close(), and older Ankis fail if their cards are gone.
    cards = []
    for index in range(3):
        n = col.new_note(model) if hasattr(col, "new_note") else col.newNote()
        n["Front"] = n["Back"] = f"heatmap metric card {index}"
        if hasattr(col, "add_note"):
            col.add_note(n, col.decks.id("Default"))
        else:
            col.addNote(n)
        cards.append(n.cards()[0].id)
    # A: most attempts; B: most total time and slowest median; C: slowest final answer.
    for index, times in enumerate(((6000, 6000, 1000), (20000, 500), (9000,))):
        for attempt, elapsed in enumerate(times):
            col.db.execute("insert into revlog values (?,?,?,?,?,?,?,?,?)",
                           stamp + index * 10 + attempt, cards[index], -1, 3, 1, 0, 2500, elapsed, 2 if attempt else 1)
    expectations = (
        ("reviews", [cards[0], cards[1], cards[2]], {cards[0]: "3", cards[1]: "2", cards[2]: "1"}),
        ("time", [cards[1], cards[0], cards[2]], {cards[0]: "13.0 s", cards[1]: "20.5 s", cards[2]: "9.0 s"}),
        ("median", [cards[1], cards[2], cards[0]], {cards[0]: "6.0 s", cards[1]: "10.2 s", cards[2]: "9.0 s"}),
    )
    for mode, wanted, values in expectations:
        note("heatmap browser: cards " + mode)
        open_day(offset, answer_mode=mode)
        browser = dialogs.open("Browser", mw)
        table = browser.table
        if table.is_notes_mode():
            settle()
            table.toggle_state(False, browser.current_search())
            settle()
            open_day(offset, answer_mode=mode)
        data = table._model
        found = [data.get_item(data.index(i, 0)) for i in range(data.rowCount())]
        if found != wanted:
            raise AssertionError(f"{mode}: sorted cards {found}, expected {wanted}")
        section = data.active_column_index(forest.actions.answer_column.KEY)
        if table._view.horizontalHeader().visualIndex(section) != 1:
            raise AssertionError(f"{mode}: metric column is not second")
        header = table._view.horizontalHeader()
        if header.sectionSize(section) < header.sectionSizeHint(section):
            raise AssertionError(f"{mode}: metric column clips its heading")
        for i, cid in enumerate(found):
            text = text_at(data, i, section)
            if text != values[cid]:
                raise AssertionError(f"{mode}: card {cid} shows {text!r}, expected {values[cid]!r}")
        result["steps"].append(f"heatmap {mode}: browser column and sorting")
        if mode == "reviews":
            # The first click must clean up too, without visiting another day or
            # switching Cards/Notes mode before closing the browser.
            close_browser(browser)
            if forest.actions.answer_column._session is not None:
                raise AssertionError("first heatmap click's session survived close")
            browser = dialogs.open("Browser", mw)
            editor_ready(browser)
            settle()
            if browser.table._model.active_column_index(forest.actions.answer_column.KEY) is not None:
                raise AssertionError("first heatmap click's column survived reopening")
            if layout(browser) != before:
                raise AssertionError(f"first heatmap click changed the reopened browser's layout: {layout(browser)}, expected {before}")
            result["steps"].append("first heatmap click: close/reopen has no metric column")

    # Sibling cards of one note can live in different decks. Their answers must not
    # inflate either a deck's Notes-mode totals or its sorting, or an excluded deck's.
    scope_model = col.models.copy(model)
    template = col.models.new_template("Sibling")
    template["qfmt"], template["afmt"] = "{{Back}}", "{{Front}}"
    col.models.add_template(scope_model, template)
    col.models.save(scope_model)
    selected, outside = col.decks.id("Heatmap selected"), col.decks.id("Heatmap outside")
    nids = []
    for index in range(2):
        n = col.new_note(scope_model)
        n["Front"], n["Back"] = f"scope {index}", "sibling"
        col.add_note(n, selected)
        pair = sorted(n.cards(), key=lambda card: card.ord)
        col.db.execute("update cards set did=? where id=?", outside, pair[1].id)
        nids.append(n.id)
        for part, (card, times) in enumerate(((pair[0], (1000, 9000) if index == 0 else (6000, 6000, 6000)),
                                             (pair[1], (60000,) * (30 if index == 0 else 1)))):
            for attempt, elapsed in enumerate(times):
                col.db.execute("insert into revlog values (?,?,?,?,?,?,?,?,?)", stamp + 1000 + index * 100 + part * 40 + attempt,
                               card.id, -1, 3, 1, 0, 2500, elapsed, 1)
    settle()
    table.toggle_state(True, browser.current_search())
    settle()
    for mode, values in (("reviews", ("2", "3")), ("time", ("10.0 s", "18.0 s")), ("median", ("5.0 s", "6.0 s"))):
        note("heatmap browser: scoped notes " + mode)
        open_day(offset, selected, answer_mode=mode)
        data = table._model
        found = [data.get_item(data.index(i, 0)) for i in range(data.rowCount())]
        if found != nids[::-1]:
            raise AssertionError(f"scoped {mode}: note sort {found}, expected {nids[::-1]}")
        section = data.active_column_index(forest.actions.answer_column.KEY)
        for nid, value in zip(nids, values):
            text = text_at(data, found.index(nid), section)
            if text != value:
                raise AssertionError(f"scoped {mode}: note shows {text!r}, expected {value!r}")
    original = dict(forest.state.config())
    try:
        forest.state.save_config(dict(original, excluded_decks=[outside]))
        open_day(offset, answer_mode="reviews")
        data = table._model
        found = [data.get_item(data.index(i, 0)) for i in range(data.rowCount())]
        section = data.active_column_index(forest.actions.answer_column.KEY)
        if [text_at(data, found.index(nid), section) for nid in nids] != ["2", "3"]:
            raise AssertionError("excluded sibling answers counted in Notes mode")
    finally:
        forest.state.save_config(original)
    result["steps"].append("heatmap scoped notes: attempts, time, median, sorting and excluded siblings")
    settle()
    table.toggle_state(False, browser.current_search())
    settle()
    open_day(offset, selected, answer_mode="reviews")
    # A real close, rather than calling cleanup by hand, must restore the layout before
    # Anki saves it; reopening must not bring back the dated column or its callbacks.
    note("heatmap browser: close and reopen")
    close_browser(browser)
    if forest.actions.answer_column._session is not None:
        raise AssertionError("heatmap browser session survived close")
    browser = dialogs.open("Browser", mw)
    editor_ready(browser)
    settle()
    if browser.table._model.active_column_index(forest.actions.answer_column.KEY) is not None:
        raise AssertionError("heatmap column survived browser reopening")
    if layout(browser) != before:
        raise AssertionError(f"browser layout was not restored: {layout(browser)}, expected {before}")
    browser.table.toggle_state(True, browser.current_search())
    settle()
    if browser.table._model.active_column_index(forest.actions.answer_column.KEY) is not None or layout(browser) != before_notes:
        raise AssertionError("Notes-mode column or layout survived the temporary metric session")
    browser.table.toggle_state(False, browser.current_search())
    settle()
    result["steps"].append("heatmap browser close/reopen restores columns and widths")
    open_day(offset, selected, answer_mode="reviews")
    cleanup = forest.actions.answer_column._session
    cleanup()
    cleanup()
    result["steps"].append("heatmap browser cleanup twice")
    close_browser(browser)


def opened():
    note("profile open")
    result["platform"] = QApplication.platformName()
    if os.environ.get("MEMORY_FOREST_SHOW") != "1" and result["platform"] != "offscreen":
        result["errors"].append("background checks require Qt's offscreen platform")
        finish()
        return
    try:
        from anki.buildinfo import version
        result["anki"] = version
    except Exception:
        pass
    try:
        from aqt.qt import qVersion
        result["qt"] = qVersion()
    except Exception:
        pass

    def show():
        mw.moveToState("deckBrowser")
        mw.showNormal()
        if os.environ.get("MEMORY_FOREST_SHOW") == "1":
            mw.raise_()
        mw.deckBrowser.refresh()

    step("imports", imports)
    step("seed reviews", seed)
    step("old calendar day", old_day)
    step("heatmap browser metrics", heatmap_browser_metrics)
    step("deck list", show)
    QTimer.singleShot(WAIT_MS, lambda: measure(first_look))


# Offscreen Qt does not deliver compositor frames. Keep the real canvas renderer
# running through timers, without needing visible windows or application focus.
def offscreen_frames(content, _context):
    # Anki's editor CSP permits add-on URLs, but forbids inline scripts.
    content.head = f'<script src="/_addons/{__name__}/offscreen.js"></script>' + content.head


if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    mw.addonManager.setWebExports(__name__, r"offscreen\.js")
    gui_hooks.webview_will_set_content.append(offscreen_frames)
gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, opened))

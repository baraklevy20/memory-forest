"""The add-on that `old_anki.py --check` installs beside Memory Forest: once the profile is
open it fills the collection with a few months of made-up reviews, so the forest is built
the way it is for everyone (from the study history, not the debug test forest, which a
built add-on does not ship), measures the cog in the real deck list, opens the settings
and paints every tab of them and the scenery picker, picks another scenery and checks the
forest was built again, writes what it found to check.json in the base folder and quits
Anki. It runs inside that Anki, so it uses only what every Anki it is run in has."""

import ast
import json
import os
import random
import sys
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTabWidget, QTimer

FOREST = os.environ.get("MEMORY_FOREST_FOLDER", "anki_forest")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT, LOG = os.path.join(BASE, "check.json"), os.path.join(BASE, "check.log")
COG_PX, COG_ICON_PX = 28, 15  # forest.css's .af-cog box, and core.js's COG icon
WAIT_MS, WAIT_TRIES = 1000, 20  # for the deck list (and the forest's idle-time build) to draw
SEED_CARDS, SEED_DAYS, SEED_REVIEWS = 60, 150, 5  # cards, how far back they start, reviews each
CONSOLE_ERROR = 2  # QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel
# measured in the deck list's page: the cog and its icon, as the page is and again under
# 2.1.50's dark-Mac button styles (Anki's own CSS, keyed on a class Anki only sets when
# macOS itself is dark), whether the forest built (core.js leaves its scene on the panel's
# root as afEnv), how many trees it has, whether it is the one built before the scenery
# changed (marked below), and how much of its canvas is painted
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
  return JSON.stringify({ plain, darkMac, built: !!env, trees, old: !!(env && env.checkMark), painted,
                          canvas: c ? [c.width, c.height] : null, classes, agent: navigator.userAgent });
})()"""
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
    if not got.get("built"):
        result["problems"].append("the forest never built")
    elif not got.get("painted"):
        result["problems"].append("the forest built but its canvas is blank")
    elif not got.get("trees"):
        result["problems"].append("the forest built with no trees, from a collection with reviews")
    QTimer.singleShot(0, settings)


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
        tabs.setCurrentIndex(0)

    def picker():
        # the General tab's picker, its tiles painted (the moving ones at their first frame)
        picker = state["dialog"].general.picker
        QApplication.processEvents()
        picker.grab()
        result["steps"].append(f"picker: {len(picker.tiles)} tiles")

    def change():
        # another scenery, chosen the way a click on its tile chooses it, then Done: the
        # config must take it and the forest be built again with it
        dialog = state["dialog"]
        box = dialog.general.preset
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
    did = col.decks.id_for_name(forest.phone.DECK)
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
    if col.decks.id_for_name(forest.phone.DECK):
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
    SEED_REVIEWS times since, written straight into the review log: a history to grow from."""
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
        first = rng.randint(SEED_REVIEWS + 1, SEED_DAYS)
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


def opened():
    note("profile open")
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
        # in front: the forest builds on the next animation frame, which the web view only
        # has while its window can be seen (a window behind the Anki you have open gets none)
        mw.showNormal()
        mw.raise_()
        mw.activateWindow()
        mw.deckBrowser.refresh()

    step("imports", imports)
    step("seed reviews", seed)
    step("deck list", show)
    QTimer.singleShot(WAIT_MS, lambda: measure(first_look))


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, opened))

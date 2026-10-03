"""The add-on that `old_anki.py --check` installs beside Memory Forest: once the profile is
open it turns the test forest on, measures the cog in the real deck list, opens the
settings and paints every tab of them and the scenery picker, writes what it found to
check.json in the base folder and quits Anki. It runs inside that Anki, so it uses only
what every supported Anki has."""

import json
import os
import sys
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTabWidget, QTimer

FOREST = os.environ.get("MEMORY_FOREST_FOLDER", "anki_forest")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT, LOG = os.path.join(BASE, "check.json"), os.path.join(BASE, "check.log")
COG_PX, COG_ICON_PX = 28, 15  # forest.css's .af-cog box, and core.js's COG icon
WAIT_MS, WAIT_TRIES = 1000, 20  # for the deck list (and the forest's idle-time build) to draw
# measured in the deck list's page: the cog and its icon, as the page is and again under
# 2.1.50's dark-Mac button styles (Anki's own CSS, keyed on a class Anki only sets when
# macOS itself is dark), and whether the forest built (core.js leaves its scene on the
# panel's root as afEnv) and painted its canvas
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
  const built = [...document.querySelectorAll('*')].some(e => e.afEnv);
  return JSON.stringify({ plain, darkMac, built, painted, canvas: c ? [c.width, c.height] : null, classes });
})()"""

result = {"anki": None, "errors": [], "problems": [], "steps": []}


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
    """The web views' console, kept: an error in the forest's page shows only there."""
    from aqt.webview import AnkiWebPage
    shown = AnkiWebPage.javaScriptConsoleMessage

    def kept(self, level, msg, line, src):
        result.setdefault("console", []).append(f"{src.rsplit('/', 1)[-1]}:{line} {msg}")
        note(f"console: {result['console'][-1]}")
        return shown(self, level, msg, line, src)
    AnkiWebPage.javaScriptConsoleMessage = kept


_console()


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


def measure(tries_left: int = WAIT_TRIES):
    mw.deckBrowser.web.evalWithCallback(MEASURE, lambda raw: measured(raw, tries_left))


def measured(raw, tries_left: int):
    note(f"measured: {raw}")
    try:
        got = json.loads(raw)
    except Exception:
        got = {}
    if not (got.get("built") and got.get("painted")) and tries_left > 1:
        QTimer.singleShot(WAIT_MS, lambda: measure(tries_left - 1))  # not built yet
        return
    result["deck_list"] = got
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
    QTimer.singleShot(0, settings)


def settings():
    forest = sys.modules[FOREST]
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
        # built as the dialog builds it (settings/dialog.py, _open_picker), but shown rather
        # than run modally: a picker that fails to paint would otherwise keep Anki waiting
        dialog = state["dialog"]
        pickers = sys.modules[f"{FOREST}.settings.scenery_picker"]
        box = dialog.general.preset
        p = pickers.SceneryPicker(dialog, dialog.general.scenery_choices(), box.currentData(), dialog._day())
        try:
            p.show()
            QApplication.processEvents()
            p.grab()
        finally:
            p.close()
            p.deleteLater()
            dialog.reject()

    step("settings", open_all)
    if "dialog" in state:
        step("scenery picker", picker)
    QTimer.singleShot(500, finish)


def opened():
    note("profile open")
    try:
        from anki.buildinfo import version
        result["anki"] = version
    except Exception:
        pass

    def forest_on():
        cfg = mw.addonManager.getConfig(FOREST) or {}
        cfg.update(test_forest=True)
        mw.addonManager.writeConfig(FOREST, cfg)
        mw.moveToState("deckBrowser")
        # in front: the forest builds on the next animation frame, which the web view only
        # has while its window can be seen (a window behind the Anki you have open gets none)
        mw.showNormal()
        mw.raise_()
        mw.activateWindow()
        mw.deckBrowser.refresh()

    step("test forest on", forest_on)
    QTimer.singleShot(WAIT_MS, measure)


gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(500, opened))

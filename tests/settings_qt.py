"""The real settings dialog, built offscreen with PyQt6, for tests that drive it as a user would.

fake_anki.py stands in for Anki with Qt stubbed out (enough to import the settings, never to
open them). Here a second copy of the add-on is loaded on real Qt: `aqt.qt` is PyQt6 (as
Anki's is), and aqt.theme / aqt.colors / aqt.props are small stand-ins for Anki's theme. Its
`aqt` has hooks of its own, so nothing it registers reaches the fake_anki copy's tests, and the
add-on's __init__.py is never run (the dialog needs none of its hooks). The real modules are
swapped in only while a Qt test runs (QtCase), and the stubs put back after, so the other tests
see what they always did.

Without PyQt6 the tests skip (SKIP says why), unless FOREST_QT_TESTS=required (CI's Qt job). Run with QT_QPA_PLATFORM=offscreen, which this
sets unless told otherwise:
    pip install PyQt6
    python3 -m unittest discover -s tests -p 'test_settings_dialog*.py'

Any exception raised inside a slot (a click, a timer, a hook) fails the test it happens in: PyQt
hands it to sys.excepthook, which QtCase records.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import importlib.util
import os
import sys
import tempfile
import traceback
import types
import unittest

import fake_anki
from fake_anki import ADDON_DIR, _Hook, mw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt6 import QtCore, QtGui, QtWidgets
except ImportError:  # (CI's unit-test matrix has no Qt: the Qt job runs these)
    QtCore = QtGui = QtWidgets = None

SKIP = "PyQt6 isn't installed: pip install PyQt6 to drive the real settings dialog"
HAVE_QT = QtWidgets is not None
# (CI's Qt job sets this, so a PyQt6 that fails to import fails the job rather than skipping it all)
if not HAVE_QT and os.environ.get("FOREST_QT_TESTS") == "required":
    raise ImportError("FOREST_QT_TESTS=required, and " + SKIP)
PACKAGE = "memory_forest_qt_under_test"
# pretending to be the base edition or Plus goes by editions.json, which the public repo has not
needs_editions = unittest.skipUnless(os.path.exists(os.path.join(ADDON_DIR, "editions.json")),
                                     "no editions.json: the public repo is one edition")
FIXED_TODAY = _dt.date(2026, 9, 19)  # (helpers.TODAY's day: out of every seasonal week)
DEBOUNCE_MS = 30  # the dialog's save after a change, in these tests (APPLY_DEBOUNCE_MS)
LIGHT, DARK = "#565656", "#c8c8c8"  # what the stand-in theme's colours come to


class Theme:
    """Anki's theme_manager, as the settings use it: night_mode, var() and themed_icon()."""

    def __init__(self):
        self.night_mode = False

    def var(self, colour: dict) -> str:
        return colour["dark" if self.night_mode else "light"]

    def themed_icon(self, _path: str) -> str:
        return ""  # (no icon file here: the date fields keep Qt's own arrow)


theme = Theme()
hooks = types.SimpleNamespace(theme_did_change=_Hook())
_swapped = ("aqt", "aqt.qt", "aqt.theme", "aqt.colors", "aqt.props")
_real: dict = {}
_stubs: dict = {}
app = None
addon = None


def _module(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m


def _colour(name: str) -> dict:
    """Any of Anki's colours (aqt.colors.FG, ...): a {"light", "dark"} pair, as its design system's are."""
    if name.isupper():
        return {"light": LIGHT, "dark": DARK}
    raise AttributeError(name)


def _build_modules() -> None:
    qt = _module("aqt.qt")
    for source in (QtCore, QtGui, QtWidgets):
        qt.__dict__.update({k: v for k, v in source.__dict__.items() if not k.startswith("_")})
    qt.qconnect = lambda signal, func: signal.connect(func)
    colours = _module("aqt.colors", __getattr__=_colour)
    stub_aqt = sys.modules["aqt"]
    aqt = _module("aqt", mw=mw, gui_hooks=hooks, dialogs=stub_aqt.dialogs)
    _real.update({
        "aqt": aqt, "aqt.qt": qt, "aqt.theme": _module("aqt.theme", theme_manager=theme), "aqt.colors": colours,
        "aqt.props": _module("aqt.props", BORDER_RADIUS={"light": "5px", "dark": "5px"}),
    })


def use_real() -> None:
    """Real Qt and the theme in place of fake_anki's stubs (until use_stubs)."""
    for name in _swapped:
        if name in sys.modules and sys.modules[name] is not _real[name]:
            _stubs[name] = sys.modules[name]
        sys.modules[name] = _real[name]


def use_stubs() -> None:
    for name in _swapped:
        if name in _stubs:
            sys.modules[name] = _stubs[name]


def _load():
    spec = importlib.util.spec_from_file_location(PACKAGE, os.path.join(ADDON_DIR, "__init__.py"),
                                                  submodule_search_locations=[ADDON_DIR])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = pkg  # (its __init__.py, which hooks into Anki, is never run)
    for name in ("state", "seasons", "news", "presets", "edition", "scope", "heatmap_look", "settings"):
        setattr(pkg, name, importlib.import_module(f"{PACKAGE}.{name}"))
    for name in ("dialog", "forest_tab", "heatmap_tab", "heatmap_look", "decks", "scenery_tab", "scenery_picker",
                 "customize", "widgets", "whats_new", "debug"):
        setattr(pkg, "s_" + name, importlib.import_module(f"{PACKAGE}.settings.{name}"))
    tmp = tempfile.mkdtemp(prefix="memory-forest-qt-test-")
    pkg.state.STATE_PATH = os.path.join(tmp, "state.json")
    pkg.seasons.SEASON_PATH = os.path.join(tmp, "season.json")
    pkg.news.NEWS_PATH = os.path.join(tmp, "news.json")
    pkg.state.log = lambda _msg: None
    pkg.s_decks.log = lambda _msg: None
    # "today", fixed (helpers.TODAY's day), for the sceneries offered without a debug date
    pkg.seasons._dt = types.SimpleNamespace(date=_FixedDate, timedelta=_dt.timedelta)
    return pkg


class _FixedDate(_dt.date):
    @classmethod
    def today(cls):
        return FIXED_TODAY


if HAVE_QT:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _build_modules()
    use_real()
    try:
        addon = _load()
    finally:
        use_stubs()


def reset(config=None, cards=((1, 10, 3), (2, 10, 40), (3, 20, 5), (4, 11, 12))) -> None:
    """A fresh collection and `config` (debug off unless it says), and this copy's records gone."""
    fake_anki.reset(cards=cards, config=dict({"debug": False}, **(config or {})))
    mw.col.models = types.SimpleNamespace(by_name=lambda _n: None, all_names_and_ids=lambda: [])
    mw.col.decks.id_for_name = lambda _n: None
    mw.col.db.list = lambda sql, *a: [r[0] for r in mw.col.db.all(sql, *a)]
    for path in (addon.state.STATE_PATH, addon.seasons.SEASON_PATH, addon.news.NEWS_PATH):
        if os.path.exists(path):
            os.remove(path)
    addon.s_dialog._last_tab = ""
    addon.state.set_settings_open(False)
    theme.night_mode = False
    del hooks.theme_did_change[:]


def saved() -> dict:
    """What the dialog wrote to the config, the debug switch left out (its default here is
    whatever the developer last set it to)."""
    return {k: v for k, v in mw.addonManager.config.items() if k != "debug"}


def current() -> dict:
    """The config as the add-on reads it: the defaults, under what was written."""
    return mw.addonManager.getConfig(PACKAGE)


def settle(turns: int = 4) -> None:
    for _ in range(turns):
        app.processEvents()


def wait(ms: int) -> None:
    """Let the event loop run for `ms` (the dialog saves APPLY_DEBOUNCE_MS after a change)."""
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


def let_save() -> None:
    """Wait until a change made in the dialog has been saved (and the forest redrawn)."""
    wait(DEBOUNCE_MS + 40)


def answer_modal(choose, tries: int = 40) -> None:
    """Once a modal box is up (QMessageBox.exec), call `choose(box)` to answer it; a box nobody
    answers is rejected after `tries`, so a test never hangs on one."""
    def look(left: int) -> None:
        box = app.activeModalWidget()
        if box is not None:
            choose(box)
        elif left > 0:
            QtCore.QTimer.singleShot(10, lambda: look(left - 1))
    QtCore.QTimer.singleShot(0, lambda: look(tries))


class QtCase(unittest.TestCase):
    """A test with real Qt in place, every exception inside a slot recorded and failing it, and
    every dialog it opened closed after it."""

    movies = False  # whether the scenery tiles get their moving pictures

    def setUp(self):
        if not HAVE_QT:
            self.skipTest(SKIP)
        use_real()
        self.addCleanup(use_stubs)
        self.slot_errors: list = []
        hook_was = sys.excepthook
        sys.excepthook = lambda *exc: self.slot_errors.append("".join(traceback.format_exception(*exc)))
        self.addCleanup(setattr, sys, "excepthook", hook_was)
        messages_was = QtCore.qInstallMessageHandler(self._qt_message)
        self.addCleanup(QtCore.qInstallMessageHandler, messages_was)
        # (the dialog saves a moment after a change: shorter here, so the tests wait less for it)
        dialog = addon.s_dialog
        self.addCleanup(setattr, dialog, "APPLY_DEBOUNCE_MS", dialog.APPLY_DEBOUNCE_MS)
        dialog.APPLY_DEBOUNCE_MS = DEBOUNCE_MS
        # (the scenery tiles' moving pictures: a hundred GIFs started at each opening, a quarter of
        # these tests' time; a test that wants them sets `movies`)
        if not self.movies:
            picker = addon.s_scenery_picker
            self.addCleanup(setattr, picker, "moving", picker.moving)
            picker.moving = lambda _key: None
        self.host = QtWidgets.QWidget()  # (the dialog's parent, Anki's main window)
        self.host.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        mw.isActiveWindow = lambda: False
        self.addCleanup(lambda: mw.__dict__.pop("isActiveWindow", None))
        self.changes = 0  # on_change calls (the forest redrawn)
        self.phone_calls: list = []
        # whether the phone's note is in the collection (phone_note.phone_on), made or taken away
        # as on_phone is called, as actions.phone_switched does
        self.phone = False
        forest_tab = addon.s_forest_tab
        phone_on_was = forest_tab.phone_on
        forest_tab.phone_on = lambda: self.phone
        self.addCleanup(setattr, forest_tab, "phone_on", phone_on_was)
        self.dialogs: list = []
        self.addCleanup(self._close_all)
        reset()

    def _qt_message(self, kind, _context, message):
        if kind in (QtCore.QtMsgType.QtCriticalMsg, QtCore.QtMsgType.QtFatalMsg):
            self.slot_errors.append(f"Qt: {message}")

    def _close_all(self):
        # (a dialog left open goes without writing anything, and no timer of its own fires into
        # the next test: a change still to save would write this test's config over that one's)
        for d in self.dialogs:
            try:
                d._debounce.stop()
                d._city_check.stop()
                d._reverting = False
                d.done(0)
                d.deleteLater()
            except RuntimeError:  # (already deleted)
                pass
        settle()
        self.host.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        settle(1)
        if self.slot_errors:
            self.fail("an exception inside a slot:\n" + "\n".join(self.slot_errors))

    def tearDown(self):
        settle()

    # -- opening -------------------------------------------------------------------------
    def on_change(self):
        self.changes += 1

    def on_phone(self, on):
        self.phone_calls.append(on)
        self.phone = on

    def reopen(self, module, on_change, on_phone, focus="", carry=None):
        """What settings.open_settings does for Restore defaults and a theme switch."""
        self.open_dialog(carry=carry, focus=focus)

    def open_dialog(self, config=None, focus: str = "", carry=None):
        """The dialog, opened on `config` (a fresh collection and config), or on the config as it
        is (None: the one setUp made, or what an earlier dialog in the test left)."""
        if config is not None:
            reset(config)
        d = addon.s_dialog.SettingsDialog(PACKAGE, self.on_change, self.on_phone, self.reopen, parent=self.host,
                                          focus=focus, carry=carry)
        d.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        d.show()
        settle()
        self.dialogs.append(d)
        return d

    @property
    def dialog(self):
        """The dialog open last (a theme switch or Restore defaults opens another)."""
        return self.dialogs[-1]

    def tab(self, d, name: str) -> None:
        for i in range(d.tabs.count()):
            if d.tabs.tabText(i).split(" ")[0].strip() == name:
                d.tabs.setCurrentIndex(i)
                settle()
                return
        raise AssertionError(f"no {name} tab: {self.tab_names(d)}")

    @staticmethod
    def tab_names(d) -> list:
        return [d.tabs.tabText(i).split(" ")[0].strip() for i in range(d.tabs.count())]

    # -- acting --------------------------------------------------------------------------
    def done(self, d=None):
        """Click Done."""
        d = d or self.dialog
        self.button(d, QtWidgets.QDialogButtonBox.StandardButton.Ok).click()
        settle()

    def cancel(self, d=None):
        d = d or self.dialog
        self.button(d, QtWidgets.QDialogButtonBox.StandardButton.Cancel).click()
        settle()

    @staticmethod
    def button(d, which):
        box = d.findChild(QtWidgets.QDialogButtonBox)
        return box.button(which)

    def press(self, widget, key) -> None:
        QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key, QtCore.Qt.KeyboardModifier.NoModifier))
        settle()

    def toggle_deck(self, d, did: int) -> None:
        """Click a deck's box in the Decks tab."""
        item = d.decks.items[did]
        checked = item.checkState(0) == QtCore.Qt.CheckState.Checked
        item.setCheckState(0, QtCore.Qt.CheckState.Unchecked if checked else QtCore.Qt.CheckState.Checked)
        settle()

    def switch_theme(self, dark: bool = True) -> None:
        """Anki's theme switched (View > Theme), as Anki tells its hooks."""
        theme.night_mode = dark
        hooks.theme_did_change()
        settle()

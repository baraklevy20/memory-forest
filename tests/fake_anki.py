"""A small stand-in for Anki, so the modules that talk to it can be tested too.

It puts fake `aqt` and `anki` modules in place (only what the add-on touches: mw, the
hooks, the browser, a tooltip), gives `mw` a collection in an in-memory SQLite database
with a few decks, and loads the add-on as a real package on top of it, so its relative
imports work as they do in Anki. The state file goes to a temporary folder, never to
user_files/.

    from fake_anki import addon, reset
    reset(cards=[...], config={...})   # a fresh collection and config for each test
    addon.payload.payload()
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import sqlite3
import sys
import tempfile
import types

from helpers import CUTOFF, TODAY, ms

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "memory_forest_under_test"
PROFILE = "Test profile"

# id -> name; "::" makes a subdeck, as in Anki. 30 is a filtered deck.
DECKS = {1: "Default", 10: "French", 11: "French::Verbs", 20: "German", 30: "Cram"}
FILTERED = {30}


class DB:
    """Anki's mw.col.db, over SQLite: .all() and .scalar()."""

    def __init__(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text,
                                due integer, odue integer default 0, mod integer default 0);
            create table revlog (id integer, cid integer, ease integer, type integer, ivl integer default 0, lastIvl integer default 0);
            create table notes (id integer, tags text, mod integer default 0);
        """)

    def all(self, sql, *args):
        return self.con.execute(sql, args).fetchall()

    def scalar(self, sql, *args):
        row = self.con.execute(sql, args).fetchone()
        return row[0] if row else None


class Decks:
    def __init__(self, current: int = 10):
        self.current_id = current

    def deck_and_child_ids(self, did: int) -> list:
        name = DECKS[did]  # a KeyError, as Anki raises for a deck that is gone
        return [d for d, n in DECKS.items() if n == name or n.startswith(name + "::")]

    def name_if_exists(self, did):
        return DECKS.get(did)

    def current(self) -> dict:
        return self.get(self.current_id)

    def get(self, did, default=True):
        if did not in DECKS:
            return None if default is False else {"id": 1, "name": "Default", "dyn": 0}
        return {"id": did, "name": DECKS[did], "dyn": 1 if did in FILTERED else 0}

    def all_names_and_ids(self, include_filtered=True):
        return [types.SimpleNamespace(id=d, name=n) for d, n in DECKS.items() if include_filtered or d not in FILTERED]


class QtStub(type):
    """Any Qt name, and any name on it: enough for the settings dialog's module to import
    (the tests never open the dialog)."""

    def __getattr__(cls, name):
        return QtStub(name, (), {})


class SearchNode:
    def __init__(self, deck=None, negated=None):
        self.deck, self.negated = deck, negated


_collections = itertools.count(1)


class Col:
    def __init__(self):
        # each its own path, as in Anki: the add-on's caches go by it, and an id() can come
        # round again for the next test's collection
        self.path = f"/fake/collection-{next(_collections)}.anki2"
        self.db = DB()
        self.decks = Decks()
        self.sched = types.SimpleNamespace(day_cutoff=CUTOFF, today=TODAY)
        self.mod = 1
        self.conf: dict = {}  # the collection's own config, synced with it

    def get_config(self, key, default=None):
        return self.conf.get(key, default)

    def set_config(self, key, value):
        self.conf[key] = value

    def build_search_string(self, node) -> str:
        if node.negated is not None:
            return "-" + self.build_search_string(node.negated)
        return f'"deck:{node.deck}"'


class AddonManager:
    def __init__(self):
        self.config: dict = {}
        with open(os.path.join(ADDON_DIR, "config.json"), encoding="utf-8") as f:
            self.defaults = json.load(f)

    def addonFromModule(self, name):
        return name.split(".")[0]

    def getConfig(self, _module):
        return dict(self.defaults, **self.config)

    def writeConfig(self, _module, cfg):
        self.config = dict(cfg)

    def addonConfigDefaults(self, _module):
        return dict(self.defaults)

    def setWebExports(self, *_a):
        pass

    def setConfigAction(self, *_a):
        pass

    def setConfigUpdatedAction(self, *_a):
        pass


class Browser:
    def __init__(self):
        self.searches: list = []

    def search_for(self, text):
        self.searches.append(text)


class Web:
    """A deck screen's web view: what it was asked to run."""

    def __init__(self):
        self.evaluated: list = []
        self.reloads = 0

    def evalWithCallback(self, js, callback):
        self.evaluated.append(js)
        callback(True)


mw = types.SimpleNamespace(
    addonManager=AddonManager(),
    col=None,
    state="deckBrowser",
    pm=types.SimpleNamespace(name=PROFILE),
    taskman=types.SimpleNamespace(run_in_background=lambda task, done, uses_collection=True: None),
)
browser = Browser()
tooltips: list = []
hooks = types.SimpleNamespace(**{name: [] for name in (
    "deck_browser_will_render_content", "overview_will_render_content", "reviewer_did_answer_card",
    "webview_did_receive_js_message", "deck_browser_will_show_options_menu", "sync_will_start", "sync_did_finish")})


def _install() -> None:
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m
        return m
    module("anki")
    module("anki.collection", SearchNode=SearchNode)
    module("aqt", mw=mw, gui_hooks=hooks, dialogs=types.SimpleNamespace(open=lambda name, _parent: browser))
    module("aqt.deckbrowser", DeckBrowser=type("DeckBrowser", (), {}))
    module("aqt.overview", Overview=type("Overview", (), {}))
    module("aqt.colors")
    module("aqt.props")
    module("aqt.theme", theme_manager=types.SimpleNamespace(var=lambda v: "", themed_icon=lambda p: p))
    module("aqt.utils", tooltip=lambda text, period=None: tooltips.append(text))
    qt = module("aqt.qt")
    qt.__getattr__ = lambda name: QtStub(name, (), {})


def _load():
    spec = importlib.util.spec_from_file_location(PACKAGE, os.path.join(ADDON_DIR, "__init__.py"),
                                                  submodule_search_locations=[ADDON_DIR])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = pkg
    spec.loader.exec_module(pkg)
    for name in ("state", "payload", "panel", "actions", "planting", "live_weather", "events_state", "settings"):
        setattr(pkg, name, importlib.import_module(f"{PACKAGE}.{name}"))
    return pkg


_install()
addon = _load()
_tmp = tempfile.mkdtemp(prefix="memory-forest-test-")
addon.state.STATE_PATH = os.path.join(_tmp, "state.json")
# the seasonal record too: never the real user_files, and fresh for every test
addon.state.SEASON_PATH = os.path.join(_tmp, "season.json")
addon.payload.log = lambda _msg: None  # "built N trees in M ms", on every build


def reset(cards=(), config=None, current_deck: int = 10, leeches=()):
    """A fresh collection holding `cards` - (cid, deck, first review days ago[, home deck]) -
    each reviewed once and due in a month (the cids in `leeches` tagged leech, and not yet
    cured), and `config` over the defaults; the add-on forgets what it cached and remembered."""
    mw.col = Col()
    mw.col.decks.current_id = current_deck
    mw.state = "deckBrowser"
    for c in cards:
        cid, did, days = c[:3]
        odid = c[3] if len(c) > 3 else 0
        mw.col.db.con.execute("insert into cards (id, nid, did, odid, type, queue, ivl, data, due) values (?, ?, ?, ?, 2, 2, ?, '{}', ?)",
                              (cid, cid, did, odid, 5 if cid in leeches else 30, TODAY + 30))
        mw.col.db.con.execute("insert into revlog (id, cid, ease, type) values (?, ?, 3, 0)", (ms(days), cid))
        mw.col.db.con.execute("insert into notes (id, tags) values (?, ?)", (cid, " leech " if cid in leeches else ""))
    mw.addonManager.config = dict(config or {})
    addon.payload._forest_cache.clear()
    addon.planting._planted_today = None
    browser.searches.clear()
    tooltips.clear()
    for path in (addon.state.STATE_PATH, addon.state.SEASON_PATH):
        if os.path.exists(path):
            os.remove(path)

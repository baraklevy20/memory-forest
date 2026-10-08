"""Which edition this copy is: Memory Forest or Memory Forest Plus, told apart by the package
each build writes into manifest.json - or while debug is on, the one the Debug tab pretends it
is (editions.json). Also whether this copy has its debug tools at all."""

from __future__ import annotations

import json
import os

from . import presets
from .state import ADDON_DIR, config

# Plus's package and its name as Anki shows it, and this folder's package in development
PLUS_PACKAGE, PLUS_NAME, DEV_PACKAGE = "memory_forest_plus", "Memory Forest Plus", "anki_forest"


def manifest(folder: str = ADDON_DIR) -> dict:
    """An add-on's manifest.json (this one's unless told), or nothing if it can't be read."""
    try:
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_plus() -> bool:
    """Whether this copy is Memory Forest Plus (or, while debug is on, pretends to be)."""
    pretend = debug_edition()
    if pretend:
        return pretend == "plus"
    return manifest().get("package") == PLUS_PACKAGE


def is_plus_folder(folder: str, meta=None) -> bool:
    """Whether the add-on installed in `folder` is Memory Forest Plus: installed from a file,
    its folder is named after its package; `meta` is Anki's record of it."""
    names = (os.path.basename(folder.rstrip(os.sep)), manifest(folder).get("package"), getattr(meta, "provided_name", None))
    return PLUS_PACKAGE in names or PLUS_NAME in names


def debug_available(cfg: dict | None = None) -> bool:
    """Whether debug is on and this copy has the debug tools to go with it: a release ships
    without them (dev/package.py), and debug turned on by hand there changes nothing."""
    cfg = config() if cfg is None else cfg
    return bool(cfg.get("debug", False)) and os.path.exists(os.path.join(ADDON_DIR, "debug_events.py"))


# the editions the Debug tab can pretend this copy is (editions.json, which only this copy has)
EDITIONS_FILE = os.path.join(ADDON_DIR, "editions.json")
DEBUG_EDITIONS = ("base", "plus")


def debug_edition(cfg: dict | None = None) -> str:
    """While debug is on, the edition this copy pretends to be ("base" or "plus"), or "" for
    itself: every scenery here, and its own manifest's say on whether it is Plus."""
    cfg = config() if cfg is None else cfg
    edition = cfg.get("debug_edition") or ""
    return edition if edition in DEBUG_EDITIONS and debug_available(cfg) else ""


def edition_presets(edition: str) -> set | None:
    """The preset keys `edition` ships, from editions.json, or None for every one here (no
    edition, or no editions.json to read it from)."""
    if not edition:
        return None
    try:
        with open(EDITIONS_FILE, encoding="utf-8") as f:
            envs = json.load(f)[edition]["envs"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {p.key for p in presets.FOREST_PRESETS
            if envs == "*" or p.environment in envs or p.key == presets.DAILY}

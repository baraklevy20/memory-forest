"""Onigiri (AnkiWeb 1011095603), which draws the deck list as a grid of widgets: which of this
add-on's tiles are on its grid. Only read, never written: its settings are its own."""

from __future__ import annotations

import sys

# Onigiri's settings module: found by what it holds, so a copy in a folder of another name is found too
_SETTINGS = ".core.config"
_found = None


def _settings():
    global _found
    if _found is not None and sys.modules.get(_found.__name__) is _found:
        return _found
    _found = None
    for name, module in list(sys.modules.items()):
        if (name.endswith(_SETTINGS) and module is not None and hasattr(module, "get_config_readonly")
                and hasattr(module, "_place_external_widgets")):
            _found = module
            break
    return _found


def placed() -> set:
    """The add-on widgets placed on Onigiri's grid, each as "<module>.<name>" of its callback (as
    Onigiri keeps them); none without Onigiri, or when its settings can't be read."""
    module = _settings()
    if module is None:
        return set()
    try:
        layout = module.get_config_readonly().get("externalWidgetLayout") or {}
        # (its layout as saved now, {"grid": .., "archive": ..}, or as it was once: the grid alone)
        grid = layout.get("grid", layout) if isinstance(layout, dict) else {}
        return {str(k) for k in grid} if isinstance(grid, dict) else set()
    except Exception:  # (whatever Onigiri has changed: the tile as it always was)
        return set()


def is_placed(callback) -> bool:
    return f"{callback.__module__}.{callback.__name__}" in placed()

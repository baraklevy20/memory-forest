"""The forest's settings dialog: four tabs, General (a preset, the real sky, animation,
the planting message), Fine-tuning (the five settings a preset fills in, and the rarer
ones), History (which decks and days the forest grows from), and About. Each tab is a
file of its own here; dialog.py puts them together and saves."""

from __future__ import annotations

from aqt.qt import Qt

from .dialog import SettingsDialog

_open: SettingsDialog | None = None


def is_open() -> bool:
    """Whether the dialog is up, so its live preview is not taken for a real change."""
    return _open is not None and _open.isVisible()


def open_settings(module: str, on_change) -> None:
    global _open
    if _open is not None and _open.isVisible():
        _open.raise_(); _open.activateWindow()
        return
    _open = SettingsDialog(module, on_change, open_settings)
    _open.setWindowModality(Qt.WindowModality.NonModal)
    _open.show()

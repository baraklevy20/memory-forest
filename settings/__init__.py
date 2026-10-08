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


def _closed(dialog: SettingsDialog) -> None:
    global _open
    if _open is dialog:  # Restore defaults opens the next one before this one is gone
        _open = None


def open_settings(module: str, on_change, focus: str = "") -> None:
    """Open the dialog (or bring it up), at the tab a note's button asked for, `focus`
    (news.opens)."""
    global _open
    if _open is not None and _open.isVisible():
        _open.show_news(focus)
        _open.raise_(); _open.activateWindow()
        return
    dialog = SettingsDialog(module, on_change, open_settings, focus=focus)
    # a closed dialog goes, picker and all: kept, each one opened stayed in memory for good
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.finished.connect(lambda _result: _closed(dialog))
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    _open = dialog
    dialog.show()

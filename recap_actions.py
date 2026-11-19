"""What the year's recap (web/recap.js) asks of Anki: its card answered, and its picture saved."""

from __future__ import annotations

import base64
import json
import os

from aqt import mw
from aqt.qt import QFileDialog, QStandardPaths
from aqt.utils import tooltip

from . import recap
from .i18n import t
from .state import log

PNG_HEAD = "data:image/png;base64,"


def handle(message: str) -> None:
    """`message` as the page sent it: "<channel>:recap:opened:2026", ":dismissed:2026", or
    ":save:2026:data:image/png;base64,..." (the picture, after the year)."""
    parts = message.split(":", 4)
    if len(parts) < 4 or not parts[3].isdigit():
        return
    what, year = parts[2], int(parts[3])
    if what == "opened":
        recap.answer(year, recap.OPENED)
    elif what == "dismissed":
        recap.answer(year, recap.DISMISSED)
    elif what == "debug_opened":
        recap.asked_done()
    elif what == "save" and len(parts) == 5 and parts[4].startswith(PNG_HEAD):
        save(year, base64.b64decode(parts[4][len(PNG_HEAD):]))


def default_path(year: int) -> str:
    """Where the save dialog starts: the Pictures folder (else home), memory-forest-2026.png."""
    # (an older PyQt5 has no StandardLocation scope: QStandardPaths.PicturesLocation there)
    where = getattr(getattr(QStandardPaths, "StandardLocation", QStandardPaths), "PicturesLocation")
    folder = QStandardPaths.writableLocation(where) or os.path.expanduser("~")
    return os.path.join(folder, f"memory-forest-{year}.png")


def save(year: int, png: bytes) -> str:
    """The picture saved where the person chooses; returns where ("" if they cancelled)."""
    path, _ = QFileDialog.getSaveFileName(mw, t("recap.save_title"), default_path(year), "PNG (*.png)")
    if not path:
        return ""
    if not path.lower().endswith(".png"):
        path += ".png"
    try:
        with open(path, "wb") as f:
            f.write(png)
    except OSError:
        log(f"could not save the year's picture to {path}")
        tooltip(t("recap.could_not_save"))
        return ""
    # (the page's button says so, the file's name under it; a tooltip had it in the window's corner)
    web = getattr(getattr(mw, "deckBrowser", None), "web", None)
    if web is not None and hasattr(web, "eval"):
        web.eval(f"window.AnkiForest && AnkiForest.recapSaved && AnkiForest.recapSaved({json.dumps(os.path.basename(path))})")
    else:
        tooltip(t("recap.saved"))
    return path

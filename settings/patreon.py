"""The Patreon banner at the top of the General tab: an invitation in Memory Forest, a
thank-you in Memory Forest Plus, the edition patrons get."""

from __future__ import annotations

import json
import os

from aqt.qt import (
    QDesktopServices,
    QGuiApplication,
    QHBoxLayout,
    QIcon,
    QLabel,
    QPixmap,
    QPushButton,
    QSize,
    Qt,
    QUrl,
    QVBoxLayout,
    QWidget,
)

PATREON = "https://www.patreon.com/BarakLevy"
PLUS_PACKAGE = "memory_forest_plus"
HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(HERE)
# pixel art: a full-grown tree from the forest's own engine (15x16) at the left of the button
# or the thank-you, and a coral heart (7x7) in the heading or the thank-you; each pixel is drawn as a square this many points wide
TREE = os.path.join(HERE, "patreon_tree.png")
HEART = os.path.join(HERE, "patreon_heart.png")
PIXEL_SCALE = 2

HEADING = "Enjoying Memory Forest?"
BUTTON = "Support it on Patreon and get every new\nscenery first, in Memory Forest Plus"
FREE = "Every Plus scenery joins this version later on."
# the heart goes between the first line and its "!"
THANKS = f'Thank you for supporting Memory Forest on <a href="{PATREON}">Patreon</a>'
THANKS_MORE = "New scenery arrives here first, every month."

BUTTON_STYLE = """
QPushButton { font-size: 15px; text-align: left; padding: 8px 14px;
              border: 1px solid rgba(128, 128, 128, 0.6); border-radius: 6px;
              background: rgba(128, 128, 128, 0.12); }
QPushButton:hover { background: rgba(128, 128, 128, 0.25); }
"""


def manifest() -> dict:
    """The add-on's manifest.json, or nothing if it can't be read."""
    try:
        with open(os.path.join(ADDON_DIR, "manifest.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_plus() -> bool:
    """Whether this copy is Memory Forest Plus: each edition's build writes its own package into manifest.json."""
    return manifest().get("package") == PLUS_PACKAGE


def pixel_art(path: str) -> tuple:
    """A pixel-art image and its size on screen, scaled up in whole steps so it stays sharp."""
    pix = QPixmap(path)
    if pix.isNull():
        return QPixmap(), QSize(0, 0)
    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    size = QSize(pix.width() * PIXEL_SCALE, pix.height() * PIXEL_SCALE)
    big = pix.scaled(round(size.width() * dpr), round(size.height() * dpr),
                     Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
    big.setDevicePixelRatio(dpr)
    return big, size


def with_heart(label: QLabel) -> QWidget:
    """The pixel heart, then `label`, centred together on one line."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addStretch(1)
    lay.addWidget(pixel_label(HEART), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addStretch(1)
    return row


def pixel_label(path: str) -> QLabel:
    label = QLabel()
    label.setPixmap(pixel_art(path)[0])
    return label


def thanks() -> QWidget:
    """Plus's thank-you: the tree, then two lines, the first ending in the heart and "!"."""
    first = QLabel(THANKS)
    first.setTextFormat(Qt.TextFormat.RichText); first.setOpenExternalLinks(True)
    line = QHBoxLayout()
    line.setSpacing(4)
    line.addWidget(first, 0, Qt.AlignmentFlag.AlignVCenter)
    line.addWidget(pixel_label(HEART), 0, Qt.AlignmentFlag.AlignVCenter)
    line.addWidget(QLabel("!"), 0, Qt.AlignmentFlag.AlignVCenter)
    line.addStretch(1)
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addLayout(line)
    text.addWidget(QLabel(THANKS_MORE))
    row = QWidget()
    row.setStyleSheet("QLabel { font-size: 15px; }")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(12)
    lay.addStretch(1)
    lay.addWidget(pixel_label(TREE), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addLayout(text)
    lay.addStretch(1)
    return row


def banner() -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 4, 0, 10)
    if is_plus():
        lay.addWidget(thanks())
        return box
    heading = QLabel(HEADING)
    heading.setStyleSheet("font-size: 16px; font-weight: bold;")
    tree, tree_size = pixel_art(TREE)
    button = QPushButton(QIcon(tree), BUTTON)
    button.setIconSize(tree_size)
    button.setStyleSheet(BUTTON_STYLE)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setAutoDefault(False)  # Enter in the dialog means Done, not Patreon
    button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PATREON)))
    free = QLabel(FREE)
    free.setAlignment(Qt.AlignmentFlag.AlignCenter)
    free.setStyleSheet("color: gray; font-size: 11px;")
    lay.addWidget(with_heart(heading))
    lay.addSpacing(6)
    lay.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
    lay.addWidget(free)
    return box

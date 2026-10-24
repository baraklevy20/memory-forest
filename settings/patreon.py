"""The Patreon banner at the top of the Scenery tab: an invitation in Memory Forest, a
thank-you in Memory Forest Plus, the edition patrons get."""

from __future__ import annotations

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

from ..edition import is_plus
from ..i18n import N_, tx
from .widgets import mirror_css

PATREON = "https://www.patreon.com/BarakLevy"
HERE = os.path.dirname(os.path.abspath(__file__))
# pixel art: a full-grown tree from the forest's own engine (15x16) at the left of the button
# or the thank-you, and a coral heart (7x7) in the heading or the thank-you; each pixel is drawn as a square this many points wide
TREE = os.path.join(HERE, "patreon_tree.png")
HEART = os.path.join(HERE, "patreon_heart.png")
PIXEL_SCALE = 2

HEADING = N_("settings.patreon.enjoying_memory_forest")
BUTTON = N_("settings.patreon.support_it_on_patreon_and_get")
FREE = N_("settings.patreon.every_plus_scenery_joins_this_version")
# the heart goes between the first line and its "!"
THANKS = N_("settings.patreon.thank_you_for_supporting_memory_forest")
THANKS_MORE = N_("settings.patreon.new_scenery_arrives_here_first_every")

BUTTON_STYLE = """
QPushButton { font-size: 15px; text-align: left; padding: 8px 14px;
              border: 1px solid rgba(128, 128, 128, 0.6); border-radius: 6px;
              background: rgba(128, 128, 128, 0.12); }
QPushButton:hover { background: rgba(128, 128, 128, 0.25); }
"""


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
    first = QLabel(tx(THANKS, url=PATREON))
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
    text.addWidget(QLabel(tx(THANKS_MORE)))
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
    heading = QLabel(tx(HEADING))
    heading.setStyleSheet("font-size: 16px; font-weight: bold;")
    tree, tree_size = pixel_art(TREE)
    button = QPushButton(QIcon(tree), tx(BUTTON))
    button.setIconSize(tree_size)
    button.setStyleSheet(mirror_css(BUTTON_STYLE))  # (its words against the tree, right to left too)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setAutoDefault(False)  # Enter in the dialog means Done, not Patreon
    button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PATREON)))
    free = QLabel(tx(FREE))
    free.setAlignment(Qt.AlignmentFlag.AlignCenter)
    free.setStyleSheet("color: gray; font-size: 11px;")
    lay.addWidget(with_heart(heading))
    lay.addSpacing(6)
    lay.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
    lay.addWidget(free)
    return box

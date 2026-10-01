"""The About tab."""

from __future__ import annotations

import json
import os

from aqt.qt import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, Qt, QVBoxLayout, QWidget

from .patreon import HEART, pixel_label

# the goats to thank (Patreon sponsors), written by dev/goats.py from Patreon before each release
GOATS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "goats.json")
GOAT_INTRO = ("Memory Forest grows thanks to everyone who rates it, shares it, sends ideas or reports "
              "a bug. Thank you, all of you! And a special thank-you to the wonderful people who "
              "sponsor my add-ons on Patreon:")
# the names read like film credits: down each column, then across, small and quiet
GOAT_COLUMNS = 3
GOAT_SCROLL_STYLE = """
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: rgba(128, 128, 128, 0.45); border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(128, 128, 128, 0.7); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

ABOUT = """<b>This is your forest.</b><br><br>
One tree for every day you have learned new cards: today's is the seedling at the front,
and the oldest stands at the back. Trees grow as those cards settle into memory, and take
on a few yellow leaves when some of them slip. Days of reviews alone plant no tree,
but they keep yours healthy.<br><br>
Real weather comes from <a href="https://open-meteo.com/">Open-Meteo</a>."""


def goats() -> list:
    try:
        with open(GOATS, encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError):
        return []
    return [n for n in names if isinstance(n, str) and n.strip()] if isinstance(names, list) else []


def thanks(names: list) -> QWidget | None:
    """The thank-you section: a divider, the pixel heart and a heading, a word for everyone
    who helps, then the goats' names
    in columns that scroll once they outgrow the tab. None until there is someone to
    thank, so an empty list shows nothing at all."""
    if not names:
        return None
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(10)
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: rgba(128, 128, 128, 0.35);")
    lay.addWidget(line)
    head = QHBoxLayout()
    head.setSpacing(8)
    head.addWidget(pixel_label(HEART), 0, Qt.AlignmentFlag.AlignVCenter)
    head.addWidget(QLabel("<b>Thank you</b>"), 0, Qt.AlignmentFlag.AlignVCenter)
    head.addStretch(1)
    lay.addLayout(head)
    intro = QLabel(GOAT_INTRO)
    intro.setWordWrap(True)
    lay.addWidget(intro)
    grid_box = QWidget()
    grid = QGridLayout(grid_box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(3)
    rows = -(-len(names) // GOAT_COLUMNS)
    for i, name in enumerate(names):
        label = QLabel(name)
        label.setTextFormat(Qt.TextFormat.PlainText)  # a name is shown as typed, never as markup
        label.setStyleSheet("font-size: 12px;")
        grid.addWidget(label, i % rows, i // rows)
    for col in range(GOAT_COLUMNS):
        grid.setColumnStretch(col, 1)
    grid.setRowStretch(rows, 1)
    scroll = QScrollArea()
    scroll.setWidget(grid_box)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # styling the area makes Qt draw its scrollbar the old way, arrows and all, so the bar is
    # styled too: a thin rounded handle, like the system's own
    scroll.setStyleSheet(GOAT_SCROLL_STYLE)
    lay.addWidget(scroll, 1)
    return box


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        av = QVBoxLayout(self)
        text = QLabel(ABOUT); text.setWordWrap(True); text.setTextFormat(Qt.TextFormat.RichText); text.setOpenExternalLinks(True)
        av.addWidget(text)
        section = thanks(goats())
        if section:
            av.addWidget(section, 1)  # the names take the room left, and scroll past it
        else:
            av.addStretch(1)

"""The About tab: what this is, how it works, and who to thank."""

from __future__ import annotations

import json
import os

from aqt.qt import (
    QFont,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QGuiApplication,
    QHBoxLayout,
    QLabel,
    QPalette,
    QScrollArea,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .patreon import ADDON_DIR, HEART, PATREON, TREE, is_plus, manifest, pixel_label
from .widgets import group

# the goats to thank (Patreon sponsors), written by dev/goats.py from Patreon before each release
GOATS = os.path.join(ADDON_DIR, "goats.json")

ANKIWEB_REVIEW = "https://ankiweb.net/shared/review/1255432496"
ISSUES = "https://github.com/baraklevy20/memory-forest/issues"
RELEASES = "https://github.com/baraklevy20/memory-forest/releases"
OPEN_METEO = "https://open-meteo.com/"

HOW = ("One tree for every day you learn new cards. Today's seedling is at the front, the oldest "
       "tree at the back. Trees grow as those cards settle into memory and get a few yellow "
       "leaves when some slip. Review-only days plant no tree, but keep yours healthy.")
THANKS_ALL = ("Memory Forest grows thanks to everyone who rates it, shares it, sends ideas or "
              "reports a bug. Thank you!")
THANKS_SPONSORS = "And a special thank-you to my Sponsors on Patreon:"
FREE_LINE = (f'New scenery arrives in Memory Forest Plus first, and comes to this version too. '
             f'<a href="{PATREON}">Join on Patreon</a>')
# the pixel heart follows this one, as in the General tab's thank-you
PLUS_LINE = f'You\'re part of this: thank you for supporting it on <a href="{PATREON}">Patreon</a>'
CREDITS = f'Made by Barak Levy · Weather from <a href="{OPEN_METEO}">Open-Meteo</a> · MIT licence'

TITLE_STYLE = "font-size: 16px; font-weight: bold;"
SMALL_PX = 11
# the names read like film credits: centred, down each column then across, small and quiet,
# in a box that stops growing at this many rows and scrolls past them
GOAT_PX = 12
GOAT_COLUMNS = 3
GOAT_MAX_ROWS = 8
GOAT_ROW_GAP = 3
GOAT_SCROLL_STYLE = """
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: rgba(128, 128, 128, 0.45); border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(128, 128, 128, 0.7); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def goats() -> list:
    try:
        with open(GOATS, encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError):
        return []
    return [n for n in names if isinstance(n, str) and n.strip()] if isinstance(names, list) else []


def quiet() -> str:
    """The theme's soft text colour, for the lines that stay in the background. From the
    palette, which Anki sets for its light and dark themes alike."""
    return QGuiApplication.palette().color(QPalette.ColorRole.PlaceholderText).name()


def small_style() -> str:
    return f"color: {quiet()}; font-size: {SMALL_PX}px;"


def text(html: str, style: str = "") -> QLabel:
    """A wrapping line of rich text whose links open in the browser."""
    label = QLabel(html)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    if style:
        label.setStyleSheet(style)
    return label


def link(url: str, words: str) -> str:
    return f'<a href="{url}">{words}</a>'


def header(plus: bool) -> QWidget:
    """The pixel tree, then the name, the version and the links beside it."""
    version = manifest().get("human_version", "")
    title = QLabel("Memory Forest Plus" if plus else "Memory Forest")
    title.setStyleSheet(TITLE_STYLE)
    news = link(RELEASES, "What's new")
    ver = text(f"Version {version} · {news}" if version else news, small_style())
    # the version can be copied, for a bug report
    ver.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    links = [link(ISSUES, "Report a bug or share an idea"), link(PATREON, "Patreon")]
    if not plus:
        links.insert(0, link(ANKIWEB_REVIEW, "Rate it on AnkiWeb"))
    words = QVBoxLayout()
    words.setSpacing(2)
    words.addWidget(title)
    words.addWidget(ver)
    words.addWidget(text(" · ".join(links)))
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(14)
    lay.addWidget(pixel_label(TREE), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addLayout(words, 1)
    return row


def names_grid(names: list) -> QScrollArea:
    """The sponsors' names in columns, scrolling once there are more than fit."""
    font = QFont()
    font.setPixelSize(GOAT_PX)
    names_box = QWidget()
    names_box.setStyleSheet(f"QLabel {{ font-size: {GOAT_PX}px; color: {quiet()}; }}")
    grid = QGridLayout(names_box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(GOAT_ROW_GAP)
    rows = -(-len(names) // GOAT_COLUMNS)
    for i, name in enumerate(names):
        label = QLabel(name)
        label.setTextFormat(Qt.TextFormat.PlainText)  # a name is shown as typed, never as markup
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(label, i % rows, i // rows)
    for col in range(GOAT_COLUMNS):
        grid.setColumnStretch(col, 1)
    scroll = QScrollArea()
    scroll.setWidget(names_box)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # styling the area makes Qt draw its scrollbar the old way, arrows and all, so the bar is
    # styled too: a thin rounded handle, like the system's own
    scroll.setStyleSheet(GOAT_SCROLL_STYLE)
    shown = min(rows, GOAT_MAX_ROWS)
    scroll.setMaximumHeight(shown * QFontMetrics(font).height() + (shown - 1) * GOAT_ROW_GAP)
    return scroll


def plus_line() -> QWidget:
    """Plus's thank-you, ending in the pixel heart."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    words = text(PLUS_LINE, small_style())
    words.setWordWrap(False)  # wrapping would leave the heart far from the words
    lay.addWidget(words, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(pixel_label(HEART), 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addStretch(1)
    return row


def thanks(names: list, plus: bool) -> QWidget:
    """A thank-you to everyone, then the sponsors by name once there are some, then a word
    on the edition."""
    lay = QVBoxLayout()
    lay.setSpacing(8)
    head = QHBoxLayout()
    head.setSpacing(8)
    head.addWidget(pixel_label(HEART), 0, Qt.AlignmentFlag.AlignVCenter)
    head.addWidget(text(THANKS_ALL), 1)
    lay.addLayout(head)
    if names:
        lay.addWidget(text(THANKS_SPONSORS))
        lay.addWidget(names_grid(names))
    lay.addWidget(plus_line() if plus else text(FREE_LINE, small_style()))
    return group("Thank you", lay)


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        plus = is_plus()
        how = QVBoxLayout()
        how.addWidget(text(HOW))
        av = QVBoxLayout(self)
        av.setSpacing(12)
        av.addWidget(header(plus))
        av.addWidget(group("How it works", how))
        av.addWidget(thanks(goats(), plus))
        av.addStretch(1)
        av.addWidget(text(CREDITS, small_style()))

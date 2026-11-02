# Copied from addon_libs/about_page.py by addon_libs/sync.py: edit it there, not here.
"""The parts of an add-on's About tab: the header, Language, What's new, More add-ons and Thank you. Every add-on
lays them out the same way (anki_forest/SETTINGS_GUIDELINES.md) and gives them its own words, so nothing here knows
an add-on's name or its strings: each part takes the text it shows, already in the reader's language, and `group`,
the add-on's own titled group."""

from __future__ import annotations

import html
import json

from aqt.qt import (
    QComboBox,
    QFont,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QGuiApplication,
    QHBoxLayout,
    QLabel,
    QMovie,
    QPixmap,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)

TITLE_STYLE = "font-size: 16px; font-weight: bold;"
# the names run on in one centred paragraph, small and quiet, in a box that stops growing at this many lines and
# scrolls past them (a whole tab must still fit a 1280 x 720 screen, native style too)
NAMES_PX = 12
NAMES_MAX_LINES = 4
# or like film credits (columns): centred, down each column then across, in a box that stops growing at this many rows
NAMES_MAX_ROWS = 8
NAMES_ROW_GAP = 3
SCROLL_STYLE = """
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: rgba(128, 128, 128, 0.45); border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: rgba(128, 128, 128, 0.7); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""
NEWS_MIN_H = 120  # points: What's new asks for no more than this, and fills what the tab has spare
# and at least this, two lines, on a short screen: at NEWS_MIN_H an About tab can be the dialog's tallest at its
# least, and the dialog taller than a 1280 x 720 screen has room for
NEWS_LEAST_H = 48
PICTURE_W, PICTURE_H = 96, 54


def pixel_picture(path: str, scale: int = 2) -> QLabel:
    """A pixel-art picture (the heart) scaled up in whole steps, so it stays sharp at any screen's scale."""
    label = QLabel()
    pix = QPixmap(path)
    if not pix.isNull():
        screen = QGuiApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen is not None else 1.0
        big = pix.scaled(round(pix.width() * scale * ratio), round(pix.height() * scale * ratio),
                         Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        big.setDevicePixelRatio(ratio)
        label.setPixmap(big)
    return label


def read_goats(path: str) -> list:
    """The sponsors' names in goats.json; none if it is missing or broken."""
    try:
        with open(path, encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError):
        return []
    return [n for n in names if isinstance(n, str) and n.strip()] if isinstance(names, list) else []


def rich(words: str, style: str = "") -> QLabel:
    """A wrapping line of rich text whose links open in the browser."""
    label = QLabel(words)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    if style:
        label.setStyleSheet(style)
    return label


def link(url: str, words: str) -> str:
    return f'<a href="{url}">{words}</a>'


def language_options(i18n, same_as_anki: str) -> list:
    """Language's choices: Anki's (`same_as_anki`, with {language}, named after the language it gives the add-on: its
    own, or English where there is no translation of it), then every language there is, in its own name."""
    anki = next((c for c in i18n.candidates(i18n.anki_lang()) if c in i18n.available()), "en")
    shown = same_as_anki.replace("{language}", i18n.NAMES.get(anki, anki))
    return [("", shown)] + [(k, i18n.NAMES.get(k, k)) for k in i18n.available()]


def language_box(name: str, language: QComboBox) -> QWidget:
    """Language, its name over the dropdown: at the header's far end, so it takes no height of its own."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    label = QLabel(name)
    label.setBuddy(language)
    lay.addWidget(label)
    lay.addWidget(language)
    return box


def header(title: str, mark: QWidget | None, lines: list, beside: QWidget | None = None) -> QWidget:
    """The add-on's mark, then its name and `lines` (the version, the links) beside it, and `beside` (Language) at
    the far end."""
    name = QLabel(title)
    name.setStyleSheet(TITLE_STYLE)
    words = QVBoxLayout()
    words.setSpacing(2)
    words.addStretch(1)
    words.addWidget(name)
    for line in lines:
        words.addWidget(line)
    words.addStretch(1)
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(14)
    if mark is not None:
        lay.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addLayout(words, 1)
    if beside is not None:
        lay.addWidget(beside, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


class _Names(QScrollArea):
    """As tall as the names' lines at this width, up to NAMES_MAX_LINES, and asking for no width of its own."""

    def __init__(self, label: QLabel) -> None:
        super().__init__()
        self.label = label
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        most = NAMES_MAX_LINES * self.label.fontMetrics().lineSpacing()
        return min(self.label.heightForWidth(width), most)

    def sizeHint(self) -> QSize:
        return QSize(1, self.heightForWidth(self.width()))

    def minimumSizeHint(self) -> QSize:
        return QSize(1, self.label.fontMetrics().lineSpacing())


def names_box(names: list, colour: str) -> QScrollArea:
    """The sponsors' names in a centred paragraph, scrolling once there are more than fit."""
    box = QLabel(" · ".join(n.replace(" ", " ") for n in names))  # (a line never breaks inside a name)
    box.setStyleSheet(f"QLabel {{ font-size: {NAMES_PX}px; color: {colour}; }}")
    box.setTextFormat(Qt.TextFormat.PlainText)  # a name is shown as typed, never as markup
    box.setWordWrap(True)
    box.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    scroll = _Names(box)
    scroll.setWidget(box)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # styling the area makes Qt draw its scrollbar the old way, arrows and all, so the bar is
    # styled too: a thin rounded handle, like the system's own
    scroll.setStyleSheet(SCROLL_STYLE)
    return scroll


def names_columns(names: list, colour: str, columns: int) -> QScrollArea:
    """The sponsors' names in columns, scrolling once there are more than fit."""
    font = QFont()
    font.setPixelSize(NAMES_PX)
    box = QWidget()
    box.setStyleSheet(f"QLabel {{ font-size: {NAMES_PX}px; color: {colour}; }}")
    grid = QGridLayout(box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(NAMES_ROW_GAP)
    rows = -(-len(names) // columns)
    for i, name in enumerate(names):
        label = QLabel(name)
        label.setTextFormat(Qt.TextFormat.PlainText)  # a name is shown as typed, never as markup
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(label, i % rows, i // rows)
    for col in range(columns):
        grid.setColumnStretch(col, 1)
    scroll = QScrollArea()
    scroll.setWidget(box)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(SCROLL_STYLE)
    shown = min(rows, NAMES_MAX_ROWS)
    scroll.setMaximumHeight(shown * QFontMetrics(font).height() + (shown - 1) * NAMES_ROW_GAP)
    return scroll


def thanks_group(group, title: str, heart: QWidget, thanks_all: str, thanks_sponsors: str, names: list, colour: str,
                 last: QWidget | None = None, columns: int = 0) -> QWidget:
    """A thank-you to everyone, the Sponsors by name once there are some (`.names`, or None): in a paragraph, or in
    `columns`; then `last`, a word on Patreon if the add-on has one here."""
    lay = QVBoxLayout()
    lay.setSpacing(8)
    head = QHBoxLayout()
    head.setSpacing(8)
    head.addWidget(heart, 0, Qt.AlignmentFlag.AlignVCenter)
    head.addWidget(rich(thanks_all), 1)
    lay.addLayout(head)
    shown = None
    if names:
        lay.addWidget(rich(thanks_sponsors))
        shown = names_columns(names, colour, columns) if columns else names_box(names, colour)
        lay.addWidget(shown)
    if last is not None:
        lay.addWidget(last)
    box = group(title, lay)
    box.names = shown
    return box


def notes_html(notes: list, newest: int = 1) -> str:
    """What's new: the newest versions of `notes` (release_notes.about), their lines under their headings, and a
    line under no heading in italics."""
    parts = []
    for version, summary, sections in notes[:newest]:
        lines = [f"<b>{html.escape(version)}</b>"] + ([f"<br>{html.escape(summary)}"] if summary else [])
        for head, items in sections:
            lines.append(f"<br><br><b>{html.escape(head)}</b>" + "".join(f"<br>• {html.escape(line)}" for line in items) if head
                         else "".join(f"<br><br><i>{html.escape(line)}</i>" for line in items))
        parts.append("".join(lines))
    return "<br><br>".join(parts)


class _Filler(QScrollArea):
    """A scroll area that asks for only NEWS_MIN_H and takes whatever room the tab has spare: asking for its whole
    contents would make the dialog as tall as a long release."""

    least = NEWS_LEAST_H

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), NEWS_MIN_H)

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), self.least)


class Capped(QScrollArea):
    """A tab's whole page in a borderless scroll area, as tall as its contents up to `most` points: an About tab with
    all its parts can be taller than a 1280 x 720 screen has room for, in a long language, so there it scrolls."""

    def __init__(self, content: QWidget, most: int) -> None:
        super().__init__()
        self.most = most
        self.setWidget(content)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(SCROLL_STYLE)

    def sizeHint(self) -> QSize:
        wanted = self.widget().sizeHint()
        return QSize(wanted.width(), min(wanted.height(), self.most))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


def whats_new(group, title: str, words: str, least: int = NEWS_LEAST_H) -> QWidget:
    """What's new, for the few who read. It fills the room the tab has spare (add it with a stretch) and scrolls past
    it, so a long release never makes the dialog taller; on the shortest screen it is `least` points tall. Its text:
    `.body`."""
    body = rich(words)
    body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (a short release sits at the top, not mid-box)
    scroll = _Filler()
    scroll.least = least
    # (the release notes stay English: left to right in a dialog that reads right to left too)
    scroll.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    scroll.setWidget(body)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(SCROLL_STYLE)
    lay = QVBoxLayout()
    lay.addWidget(scroll)
    box = group(title, lay)
    box.body = body
    return box


class Picture(QLabel):
    """A picture, still, or moving only while it can be seen (only the frame on show is kept). Its pixels are drawn at
    the label's size, so a 192x108 tile in a 96x54 label is crisp on a Retina screen."""

    def __init__(self, still: str, moving: str = "", width: int = PICTURE_W, height: int = PICTURE_H):
        super().__init__()
        self.setFixedSize(width, height)
        self.movie = None
        if moving:
            self.movie = QMovie(moving, parent=self)
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
            self.movie.frameChanged.connect(lambda _n: self._show(self.movie.currentPixmap()))
        if still:
            self._show(QPixmap(still))

    def _show(self, pix) -> None:
        if pix.isNull():
            return
        pix.setDevicePixelRatio(pix.width() / self.width())
        self.setPixmap(pix)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.movie is not None:
            self.movie.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self.movie is not None:
            self.movie.stop()


def more_group(group, title: str, entries: list, get_it: str, line_of=None) -> QWidget:
    """My other add-ons you don't have yet (more_addons.others): each one's picture, name and line, and a link to it
    on AnkiWeb. `line_of(entry)`: its line in the reader's language, if the add-on has that. `.rows`: what each shows."""
    rows = QVBoxLayout()
    rows.setSpacing(10)
    shown = []
    for e in entries:
        row = QHBoxLayout()
        row.setSpacing(12)
        picture = Picture(e["picture"], e["moving"])
        words = line_of(e) if line_of else e["line"]
        about = rich(f"<b>{html.escape(e['name'])}</b><br>{html.escape(words)}")
        status = rich(link(e["url"], html.escape(get_it)))
        status.setWordWrap(False)
        row.addWidget(picture, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(about, 1)
        row.addWidget(status, 0, Qt.AlignmentFlag.AlignVCenter)
        rows.addLayout(row)
        shown.append((picture, about, status))
    box = group(title, rows)
    box.rows = shown
    return box

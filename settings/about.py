"""The About tab: what this is, how it works, and who to thank - and the add-on's language, its
one setting (SETTINGS_GUIDELINES.md)."""

from __future__ import annotations

import html
import json
import os

from aqt.qt import (
    QComboBox,
    QFont,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QGuiApplication,
    QHBoxLayout,
    QLabel,
    QPalette,
    QScrollArea,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .. import i18n, news
from ..edition import is_plus, manifest
from ..i18n import N_, t, tx
from ..state import ADDON_DIR, config
from .patreon import HEART, PATREON, TREE, pixel_label
from .widgets import combo, group

# the newest versions the What's new group lists (the release notes link has the rest)
NEWS_VERSIONS = 1
NEWS_MIN_H = 120  # points: What's new asks for no more than this, and fills what the tab has spare
# and at least this, two lines, on a short screen: at NEWS_MIN_H the About tab was the dialog's tallest
# at its least, so in Anki's own style the dialog stayed 16-28 points taller than a 1280 x 720 screen
# has room for (fit_screen gives up scenery rows only while the Scenery tab is the tallest)
NEWS_LEAST_H = 48
# the goats to thank (Patreon sponsors), written by dev/goats.py from Patreon before each release
GOATS = os.path.join(ADDON_DIR, "goats.json")

ANKIWEB_REVIEW = "https://ankiweb.net/shared/review/1255432496"
ISSUES = "https://github.com/baraklevy20/memory-forest/issues"
RELEASES = "https://github.com/baraklevy20/memory-forest/releases"
MET_NORWAY = "https://api.met.no/"
OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"

# (two paragraphs, a key each)
HOW = (N_("settings.about.one_tree_for_every_day_you"),
       N_("settings.about.the_heatmap_under_it_shows_every"))
THANKS_ALL = N_("settings.about.memory_forest_grows_thanks_to_everyone")
THANKS_SPONSORS = N_("settings.about.and_a_special_thank_you_to")
FREE_LINE = N_("settings.about.new_scenery_arrives_in_memory_forest")
# the pixel heart follows this one, as in the Scenery tab's thank-you
PLUS_LINE = N_("settings.about.youre_part_of_this_thank_you")
# the credits, one key each, between dots
CREDITS = (N_("settings.about.made_by_barak_levy"), N_("settings.about.weather_from_met_norway_cc_by"),
           N_("settings.about.places_openstreetmap_contributors"), N_("settings.about.mit_licence"))

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


def language_options() -> list:
    """Language's choices: Anki's (named after the language it gives the add-on: its own, or
    English where there is no translation of it), then every language there is, in its own name."""
    anki = next((c for c in i18n.candidates(i18n.anki_lang()) if c in i18n.available()), "en")
    return [("", t("settings.about.same_as_anki", language=i18n.NAMES.get(anki, anki)))] + \
        [(k, i18n.NAMES.get(k, k)) for k in i18n.available()]


def language_box(language: QComboBox) -> QWidget:
    """Language, its name over the dropdown: at the header's far end, so it takes no height of
    its own (SETTINGS_GUIDELINES.md: the About tab's one setting)."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    name = QLabel(t("settings.about.language"))
    name.setBuddy(language)
    lay.addWidget(name)
    lay.addWidget(language)
    return box


def header(plus: bool, beside: QWidget | None = None) -> QWidget:
    """The pixel tree, then the name, the version and the links beside it, and `beside` (Language)
    at the far end."""
    version = manifest().get("human_version", "")
    title = QLabel("Memory Forest Plus" if plus else "Memory Forest")
    title.setStyleSheet(TITLE_STYLE)
    notes = link(RELEASES, t("settings.about.all_release_notes"))
    ver = text(t("settings.about.version_version", version=version) + " · " + notes if version else notes, small_style())
    # the version can be copied, for a bug report
    ver.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    links = [link(ISSUES, t("settings.about.report_a_bug_or_share_an")), link(PATREON, "Patreon")]
    if not plus:
        links.insert(0, link(ANKIWEB_REVIEW, t("settings.about.rate_it_on_ankiweb")))
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
    if beside is not None:
        lay.addWidget(beside, 0, Qt.AlignmentFlag.AlignVCenter)
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
    words = text(tx(PLUS_LINE, url=PATREON), small_style())
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
    head.addWidget(text(tx(THANKS_ALL)), 1)
    lay.addLayout(head)
    if names:
        lay.addWidget(text(tx(THANKS_SPONSORS)))
        lay.addWidget(names_grid(names))
    lay.addWidget(plus_line() if plus else text(tx(FREE_LINE, url=PATREON), small_style()))
    return group(t("settings.about.thank_you"), lay)


def credits() -> str:
    return " · ".join(tx(c, met=MET_NORWAY, osm=OSM_COPYRIGHT) for c in CREDITS)


class _Filler(QScrollArea):
    """A scroll area that asks for only NEWS_MIN_H and takes whatever room the tab has spare:
    asking for its whole contents would make the dialog as tall as a long release."""

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), NEWS_MIN_H)

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), NEWS_LEAST_H)


def news_html(cfg: dict) -> str:
    """What's new for the edition `cfg` has (or the Debug tab pretends it is): its versions'
    lines under New, Improved and Fixed, and the line naming what Plus got more, in italics."""
    parts = []
    for version, summary, sections in news.about(cfg)[:NEWS_VERSIONS]:
        lines = [f"<b>{version}</b>"] + ([f"<br>{html.escape(summary)}"] if summary else [])
        for head, items in sections:
            lines.append(f"<br><br><b>{head}</b>" + "".join(f"<br>• {html.escape(line)}" for line in items) if head
                         else "".join(f"<br><br><i>{html.escape(line)}</i>" for line in items))
        parts.append("".join(lines))
    return "<br><br>".join(parts)


def whats_new() -> QWidget:
    """What's new, for the few who read: what this edition has, newest first (news.py), under
    New, Improved and Fixed. It fills the room the other tabs leave this one and scrolls past
    it, so a long release never makes the dialog taller. Its text: `.body` (AboutTab.show_news)."""
    body = text(news_html(config()))
    body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (a short release sits at the top, not mid-box)
    scroll = _Filler()
    # (the release notes stay English, i18n.py: left to right in a dialog that reads right to left too)
    scroll.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    scroll.setWidget(body)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(GOAT_SCROLL_STYLE)
    lay = QVBoxLayout()
    lay.addWidget(scroll)
    box = group(t("settings.about.whats_new"), lay)
    box.body = body
    return box


class AboutTab(QWidget):
    def __init__(self, cfg: dict | None = None):
        super().__init__()
        plus = is_plus()
        # the language it speaks rather than Anki's (edition.language): the dialog opens again in it
        self.language = combo(language_options(), (cfg or {}).get("language") or "", "")
        how = QVBoxLayout()
        how.addWidget(text("<br><br>".join(tx(p) for p in HOW)))
        av = QVBoxLayout(self)
        av.setSpacing(12)
        av.addWidget(header(plus, language_box(self.language)))
        self.news = whats_new()
        av.addWidget(self.news, 1)  # (it takes the room to spare)
        av.addWidget(group(t("settings.about.how_it_works"), how))
        av.addWidget(thanks(goats(), plus))
        av.addWidget(text(credits(), small_style()))

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"language": (self.language, "Language")}

    def connect(self, changed) -> None:
        self.language.currentIndexChanged.connect(changed)

    def values(self) -> dict:
        return {"language": self.language.currentData() or ""}

    def show_news(self, cfg: dict) -> None:
        """What's new again, for the edition the Debug tab's choice makes this copy, at once."""
        fresh = news_html(cfg)
        if fresh != self.news.body.text():
            self.news.body.setText(fresh)

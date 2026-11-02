"""The About tab: what this is, how it works, and who to thank - and the add-on's language, its
one setting (SETTINGS_GUIDELINES.md)."""

from __future__ import annotations

import os

from aqt.qt import (
    QGuiApplication,
    QHBoxLayout,
    QPalette,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .. import about_page, i18n, news
from ..about_page import link
from ..about_page import rich as text
from ..edition import is_plus, manifest
from ..i18n import N_, t, tx
from ..state import ADDON_DIR, config
from .patreon import HEART, PATREON, TREE, pixel_label
from .widgets import combo, group

# the newest versions the What's new group lists (the release notes link has the rest)
NEWS_VERSIONS = 1
# the goats to thank (Patreon sponsors), written from Patreon by addon_libs/goats.py
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

SMALL_PX = 11
GOAT_COLUMNS = 3  # the names read like film credits


def goats() -> list:
    return about_page.read_goats(GOATS)


def quiet() -> str:
    """The theme's soft text colour, for the lines that stay in the background. From the
    palette, which Anki sets for its light and dark themes alike."""
    return QGuiApplication.palette().color(QPalette.ColorRole.PlaceholderText).name()


def small_style() -> str:
    return f"color: {quiet()}; font-size: {SMALL_PX}px;"


def language_options() -> list:
    return about_page.language_options(i18n, t("settings.about.same_as_anki", language="{language}"))


def header(plus: bool, beside: QWidget | None = None) -> QWidget:
    """The pixel tree, then the name, the version and the links beside it, and `beside` (Language)
    at the far end."""
    version = manifest().get("human_version", "")
    notes = link(RELEASES, t("settings.about.all_release_notes"))
    ver = text(t("settings.about.version_version", version=version) + " · " + notes if version else notes, small_style())
    # the version can be copied, for a bug report
    ver.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    links = [link(ISSUES, t("settings.about.report_a_bug_or_share_an")), link(PATREON, "Patreon")]
    if not plus:
        links.insert(0, link(ANKIWEB_REVIEW, t("settings.about.rate_it_on_ankiweb")))
    return about_page.header("Memory Forest Plus" if plus else "Memory Forest", pixel_label(TREE), [ver, text(" · ".join(links))], beside)


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
    return about_page.thanks_group(group, t("settings.about.thank_you"), pixel_label(HEART), tx(THANKS_ALL), tx(THANKS_SPONSORS), names, quiet(),
                                   plus_line() if plus else text(tx(FREE_LINE, url=PATREON), small_style()), columns=GOAT_COLUMNS)


def credits() -> str:
    return " · ".join(tx(c, met=MET_NORWAY, osm=OSM_COPYRIGHT) for c in CREDITS)


def news_html(cfg: dict) -> str:
    """What's new for the edition `cfg` has (or the Debug tab pretends it is)."""
    return about_page.notes_html(news.about(cfg), NEWS_VERSIONS)


def whats_new() -> QWidget:
    """What's new, what this edition has (news.py). Its text: `.body` (AboutTab.show_news)."""
    return about_page.whats_new(group, t("settings.about.whats_new"), news_html(config()))


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
        av.addWidget(header(plus, about_page.language_box(t("settings.about.language"), self.language)))
        self.news = whats_new()
        # (how it works first: it's what someone new opens this tab for; what's new means little yet)
        av.addWidget(group(t("settings.about.how_it_works"), how))
        av.addWidget(self.news, 1)  # (it takes the room to spare)
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

"""The Scenery tab: everything about how the forest looks - the scenery picker, the real sky
and its city, and Customize, the five settings a scenery stands for, which takes the tiles'
place while open (the tab is the same height either way)."""

from __future__ import annotations

from aqt.qt import QCheckBox, QComboBox, QHBoxLayout, QLineEdit, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from .. import presets
from ..edition import debug_edition, edition_presets
from ..live_weather import city_problem
from ..seasons import today
from ..state import animation_mode
from .customize import Customize
from .patreon import banner
from .scenery_picker import SceneryPicker
from .widgets import Link, Tab, error_style, group, hint, resize_with, set_options, set_quietly

CITY_NOTE = "Live weather from MET Norway, places from OpenStreetMap. Leave it empty to follow only your clock."
CITY_MIN_W = 120  # points: the city field takes the rest of the real-sky row, but never less
SEARCH_W = 240  # points: the search, on the group title's row


def preset_options(day, chosen: str | None, edition: str = "") -> list:
    """The presets to offer on `day`: a seasonal one only in its week, and only the ones the
    edition the Debug tab pretends this is ships - unless it is the one the settings already
    are (as Customize keeps its environment)."""
    ships = edition_presets(edition)
    return presets.options(tuple(p for p in presets.FOREST_PRESETS if p.key == chosen
                                 or (presets.unlocked(p, day) and (ships is None or p.key in ships))))


class SceneryTab(Tab):
    def __init__(self, cfg: dict, new_keys=()):
        super().__init__()
        # the choices and the chosen one, in a dropdown that is never shown: the picker's tiles
        # stand for it (a seasonal preset is only offered in its week)
        self.preset = QComboBox(self)
        self.preset.setVisible(False)
        day = today(cfg)
        set_options(self.preset, preset_options(day, presets.match(cfg), debug_edition(cfg)))
        set_quietly(self.preset, presets.match(cfg))
        self.picker = SceneryPicker(self._picked, animation_mode(cfg) != "off")
        self.picker.new_keys = set(new_keys)  # the sceneries new since the settings were last opened
        self.picker.set_choices(self.scenery_choices(), presets.match(cfg), day)
        self.real_sky = QCheckBox("Follow the real weather and time of day")
        self.real_sky.setChecked(presets.follows_real_sky(cfg))
        self.city = QLineEdit(cfg.get("city", ""))
        self.city.setPlaceholderText("Your city, e.g. Berlin")
        self.city.setMinimumWidth(CITY_MIN_W)
        self.city_status = hint("")
        self.city_status.setStyleSheet(error_style())
        self.custom = Customize(cfg, lambda: self.show_customize(False))
        self.customize = Link("", lambda: self.show_customize(True))
        self.picker.search.setFixedWidth(SEARCH_W)
        # the tiles with the way to Customize under them, or Customize in their place: one
        # page or the other, the stack as tall as the one in view (the dialog resizes to it, as
        # a Mac's own settings window does to each of its panes)
        tiles = QWidget()
        tv = QVBoxLayout(tiles)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(self.picker)
        tv.addWidget(self.customize)
        self.stack = QStackedWidget()
        self.stack.addWidget(tiles)
        self.stack.addWidget(self.custom)
        self._size_to_page()
        # the scenery's picker (the group's title names it, the search beside it) and its sky,
        # the city after the real sky's box on its row, greyed out while the weather isn't live.
        # Plain rows rather than a form: a form squeezes its rows around wrapped hints in a group
        sv = QVBoxLayout()
        sv.addWidget(self.stack)
        sky = QHBoxLayout()
        sky.addWidget(self.real_sky)
        sky.addWidget(self.city, 1)
        sv.addLayout(sky)
        sv.addWidget(self.city_status)
        sv.addWidget(hint(CITY_NOTE))
        v = QVBoxLayout(self)
        v.addWidget(banner())
        v.addWidget(group("Scenery", sv, beside=self.picker.search))
        v.addStretch(1)

    def show_customize(self, on: bool) -> None:
        """Customize in the tiles' place, or the tiles back (the search only with them), the
        window as much shorter or taller as the page is."""
        if on == self.customizing():
            return

        def turn() -> None:
            self.stack.setCurrentIndex(1 if on else 0)
            self._size_to_page()
            self.picker.allow_search(not on)
        resize_with(self, turn)
        (self.custom.back if on else self.customize).setFocus()

    def _size_to_page(self) -> None:
        """Only the page in view counts towards the stack's height (a stack goes by its tallest
        page otherwise, and Customize, the shorter, would leave a gap)."""
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            vertical = QSizePolicy.Policy.Preferred if i == self.stack.currentIndex() else QSizePolicy.Policy.Ignored
            page.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)
        self.stack.updateGeometry()

    def customizing(self) -> bool:
        return self.stack.currentIndex() == 1

    def offer(self, day, look: dict, edition: str = "") -> None:
        """The presets there are on `day` (a seasonal one comes out on its first day), in
        `edition` (see preset_options)."""
        set_options(self.preset, preset_options(day, presets.match(look), edition))
        self.picker.set_choices(self.scenery_choices(), presets.match(look), day)
        self.custom.offer(day)

    def _picked(self, key: str) -> None:
        """A tile clicked: chosen as choosing it from a list would (the dialog fills in the rest)."""
        i = self.preset.findData(key)
        if i >= 0:
            self.preset.setCurrentIndex(i)

    def scenery_choices(self) -> list:
        """The presets offered just now, for the picker (Custom isn't one)."""
        return [self.preset.itemData(i) for i in range(self.preset.count()) if self.preset.itemData(i) != presets.CUSTOM]

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"real_weather": (self.real_sky, "Follow the real weather"), "city": (self.city, "Your city"),
                **self.custom.news_targets()}

    def reveal(self, widget) -> None:
        """Open Customize if `widget` is in it, so a note pointing there finds it."""
        if self.custom.isAncestorOf(widget):
            self.show_customize(True)

    def connect(self, changed) -> None:
        self.city.editingFinished.connect(changed)
        self.custom.connect(changed)

    def sync(self) -> None:
        """The preset's card, the real-sky box, the city and Customize, in line with the five
        settings a preset stands for."""
        look = self.custom.look()
        key = presets.match(look)
        set_quietly(self.preset, key)
        self.picker.set_current(key)
        self.real_sky.blockSignals(True)
        self.real_sky.setChecked(presets.follows_real_sky(look))
        self.real_sky.blockSignals(False)
        live = look["weather"] == "auto"
        # the last lookup of this city, if it went wrong
        problem = city_problem(self.city.text()) if live else ""
        self.city_status.setText("" if not problem else
                                 "Couldn't find this city. Check the spelling, or try its English name." if problem.startswith("city not found")
                                 else "Couldn't reach the weather service; trying again soon.")
        self.city.setEnabled(live)
        self.city_status.setVisible(bool(problem))
        self.custom.sync()
        self.customize.setText(f"Customize {self.custom.name()} ›")
        self.fit()

    def values(self) -> dict:
        return {"city": self.city.text().strip(), **self.custom.values()}

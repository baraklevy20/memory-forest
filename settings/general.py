"""The General tab: the settings most people ever touch - a preset, the real sky,
Nature, and a few extras - in three groups, with the help kept short."""

from __future__ import annotations

import os

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QPushButton,
    QRect,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)

from .. import presets
from ..events import NATURE_LABELS, NATURE_NOTES, NATURE_SWITCH_NOTE, calm, nature_level
from ..live_weather import city_problem
from ..state import ANIMATION_VALUES, animation_mode, debug_edition, edition_presets, phone_on, set_phone_on, today
from .palette import color
from .patreon import banner
from .scenery_picker import SceneryPicker, crisp
from .widgets import combo, group, grow_window, hint, set_options, set_quietly

NATURE_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nature")
NATURE_ICON = 16  # points: the icons' own pixels, one a point
NATURE_GAP = 8
NATURE_STYLE = """
QPushButton {{ border: 1px solid {line}; border-radius: 7px; padding: 6px 10px; font-size: 13px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ border: 2px solid {ring}; padding: 5px 9px; background: rgba(128, 128, 128, 0.16); font-weight: bold; }}
"""
CITY_NOTE = "Live weather from MET Norway, places from OpenStreetMap. Leave it empty to follow only your clock."
PHONE_NOTE = 'Adds a "Memory Forest" deck with one card that shows your forest. It updates when you sync. Untick to remove it.'
ANIMATION_OPTIONS = [("on", "On"), ("off", "Off"), ("system", "Follow system")]
CITY_MIN_W = 120  # points: the city field takes the rest of the real-sky row, but never less


def preset_options(day, chosen: str | None, edition: str = "") -> list:
    """The presets to offer on `day`: a seasonal one only in its week, and only the ones the
    edition the Debug tab pretends this is ships - unless it is the one the settings already
    are (as the Fine-tuning tab keeps its environment)."""
    ships = edition_presets(edition)
    return presets.options(tuple(p for p in presets.FOREST_PRESETS if p.key == chosen
                                 or (presets.unlocked(p, day) and (ships is None or p.key in ships))))


class NatureChoice(QWidget):
    """The three Nature levels side by side, each with its icon (drawn by dev/nature_icons.py),
    the chosen one ringed as a focused field is in Anki."""

    def __init__(self, level: str):
        super().__init__()
        self.group = QButtonGroup(self)
        self.buttons = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(NATURE_GAP)
        style = NATURE_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS"))
        for key, label in NATURE_LABELS.items():
            b = QPushButton(QIcon(crisp(os.path.join(NATURE_ICONS, f"{key}.png"))), f" {label}")
            b.setIconSize(QSize(NATURE_ICON, NATURE_ICON))
            b.setAutoDefault(False)  # Enter in the dialog means Done
            b.setCheckable(True)
            b.setChecked(key == level)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(style)
            self.group.addButton(b)
            self.buttons[key] = b
            row.addWidget(b)

    def currentData(self) -> str:
        return next(k for k, b in self.buttons.items() if b.isChecked())

    def on_change(self, changed) -> None:
        self.group.buttonToggled.connect(lambda _b, on: on and changed())


class GeneralTab(QWidget):
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
        # On, Off, or Follow system (still while the system asks for reduced motion)
        self.animations = combo(ANIMATION_OPTIONS, animation_mode(cfg))
        # the tiles move unless the forest is off (Qt can't tell what the system asks for)
        self.animations.currentIndexChanged.connect(lambda _i: self.picker.animate(self.animations.currentData() != "off"))
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        self.phone = QCheckBox("Show my forest on my phone")
        # the collection's setting, not the add-on config's: it is written as it is ticked
        # (the dialog then makes or takes away the deck), and put back on Cancel
        self.phone_was = phone_on()
        self.phone.setChecked(self.phone_was)
        self.phone.toggled.connect(self._phone_toggled)
        self._watching_cancel = False
        self.nature = NatureChoice(nature_level(cfg.get("nature")))
        self.nature_note = hint("")
        self.nature_note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (its room fits the longest level)
        self.city_status = hint("")
        self.city_status.setStyleSheet("color: #c0392b; font-size: 11px;")
        self.city_note = hint(CITY_NOTE)
        # it keeps its room while the weather isn't live, so ticking the box never grows the tab
        policy = self.city_note.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.city_note.setSizePolicy(policy)
        # the scenery's picker (the group's title names it) and its sky, the city after the real
        # sky's box on its row; the city and its help only show while the weather is live.
        # Plain rows rather than a form: a form squeezes its rows around wrapped hints in a group
        sv = QVBoxLayout()
        sv.addWidget(self.picker)
        sky = QHBoxLayout()
        sky.addWidget(self.real_sky)
        sky.addWidget(self.city, 1)
        sv.addLayout(sky)
        sv.addWidget(self.city_status)
        sv.addWidget(self.city_note)
        nv = QVBoxLayout()
        nv.addWidget(self.nature)
        nv.addWidget(self.nature_note)
        ev = QVBoxLayout()
        motion = QHBoxLayout()
        motion.addWidget(QLabel("Animate the forest"))
        motion.addWidget(self.animations)
        motion.addStretch(1)
        ev.addLayout(motion)
        for box in (self.planting, self.phone):
            ev.addWidget(box)
        ev.addWidget(hint(PHONE_NOTE))
        v = QVBoxLayout(self)
        v.addWidget(banner())
        v.addWidget(group("Scenery", sv))
        v.addWidget(group("Nature", nv))
        v.addWidget(group("Extras", ev))
        v.addStretch(1)

    def _phone_toggled(self, on: bool) -> None:
        set_phone_on(on)
        dialog = self.window()
        if not self._watching_cancel and dialog is not self:
            dialog.rejected.connect(self._phone_put_back)
            self._watching_cancel = True

    def _phone_put_back(self) -> None:
        """Cancel puts the phone setting back as the dialog found it, as it does the add-on
        config - but not when Restore defaults closed the dialog: that keeps it as it is."""
        if not getattr(self.window(), "_reverting", True) or phone_on() == self.phone_was:
            return
        set_phone_on(self.phone_was)
        from ..actions import settings_changed
        settings_changed()

    def offer(self, day, look: dict, edition: str = "") -> None:
        """The presets there are on `day` (a seasonal one comes out on its first day), in
        `edition` (see preset_options)."""
        set_options(self.preset, preset_options(day, presets.match(look), edition))
        self.picker.set_choices(self.scenery_choices(), presets.match(look), day)

    def _picked(self, key: str) -> None:
        """A tile clicked: chosen as choosing it from a list would (the dialog fills in the rest)."""
        i = self.preset.findData(key)
        if i >= 0:
            self.preset.setCurrentIndex(i)

    def scenery_choices(self) -> list:
        """The presets offered just now, for the picker (Custom isn't one)."""
        return [self.preset.itemData(i) for i in range(self.preset.count()) if self.preset.itemData(i) != presets.CUSTOM]

    def connect(self, changed) -> None:
        self.animations.currentIndexChanged.connect(lambda _i: changed())
        for box in (self.planting, self.phone):
            box.toggled.connect(changed)
        self.city.editingFinished.connect(changed)
        self.nature.on_change(changed)

    def sync(self, look: dict) -> None:
        """The preset's card, the real-sky box and the city, in line with the five
        settings a preset stands for, whichever tab they were changed on."""
        key = presets.match(look)
        set_quietly(self.preset, key)
        self.picker.set_current(key)
        self.real_sky.blockSignals(True)
        self.real_sky.setChecked(presets.follows_real_sky(look))
        self.real_sky.blockSignals(False)
        # the last lookup of this city, if it went wrong
        problem = city_problem(self.city.text()) if look["weather"] == "auto" else ""
        self.city_status.setText("" if not problem else
                                 "Couldn't find this city. Check the spelling, or try its English name." if problem.startswith("city not found")
                                 else "Couldn't reach the weather service; trying again soon.")
        live = look["weather"] == "auto"
        self.city.setVisible(live)
        self.city_note.setVisible(live)
        self.city_status.setVisible(bool(problem))
        level = self.nature.currentData()
        note = NATURE_NOTES.get(level, "")
        self.nature_note.setText(note if calm(level) else f"{note} {NATURE_SWITCH_NOTE}")
        self._fit()

    def _fit(self) -> None:
        """Nature's line asks for room for its longest level from the start, so picking another
        never makes the dialog grow."""
        width = self.nature_note.width()
        if width > 0:
            metrics = self.nature_note.fontMetrics()
            texts = [n if calm(k) else f"{n} {NATURE_SWITCH_NOTE}" for k, n in NATURE_NOTES.items()]
            tallest = max(metrics.boundingRect(QRect(0, 0, width, 10000), Qt.TextFlag.TextWordWrap, t).height() for t in texts)
            self.nature_note.setMinimumHeight(tallest)
        grow_window(self)

    def minimumSizeHint(self) -> QSize:
        """At least the height the wrapped help needs at the tab's width. A dialog goes by its
        contents' plain size hints, which leave too little room for wrapped text, and the rows
        are then squeezed (the gap under the scenery card first). Qt asks again whenever
        anything in the tab changes, so the dialog's minimum always keeps up."""
        hint = super().minimumSizeHint()
        width = self.width() if self.width() > 0 else hint.width()
        return QSize(hint.width(), max(hint.height(), self.heightForWidth(max(width, hint.width()))))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def values(self) -> dict:
        return {
            "city": self.city.text().strip(),
            "animations": ANIMATION_VALUES[self.animations.currentData()],
            "planting_tooltip": self.planting.isChecked(),
            "nature": self.nature.currentData(),
        }

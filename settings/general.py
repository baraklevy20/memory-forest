"""The General tab: the settings most people ever touch - a preset, the real sky,
animation and the planting message."""

from __future__ import annotations

from aqt.qt import QCheckBox, QFormLayout, QLineEdit, QWidget

from .. import presets
from ..events import NATURE_LABELS, NATURE_NOTES, nature_level
from ..live_weather import city_problem
from ..state import OFF_VALUES, today
from .patreon import banner
from .widgets import combo, hint, set_options, set_quietly

NATURE_OPTIONS = list(NATURE_LABELS.items())


def preset_options(day, chosen: str | None) -> list:
    """The presets to offer on `day`: not a seasonal one before its first week, unless
    it is the one the settings already are (as the Fine-tuning tab keeps its environment)."""
    return presets.options(tuple(p for p in presets.FOREST_PRESETS if presets.unlocked(p, day) or p.key == chosen))


class GeneralTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        # a seasonal preset is not offered before its first week
        self.preset = combo(preset_options(today(cfg), presets.match(cfg)), presets.match(cfg))
        self.preset_note = hint("")
        self.real_sky = QCheckBox("Follow the real weather and time of day")
        self.real_sky.setChecked(presets.follows_real_sky(cfg))
        self.city = QLineEdit(cfg.get("city", ""))
        self.city.setPlaceholderText("Your city, e.g. Berlin")
        self.animations = QCheckBox("Animate the forest (clouds, rain, animals)")
        self.animations.setChecked(cfg.get("animations", True) not in OFF_VALUES)
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        self.phone = QCheckBox("Show my forest on my phone")
        self.phone.setChecked(cfg.get("phone_forest", False) not in OFF_VALUES)
        self.nature = combo(NATURE_OPTIONS, nature_level(cfg.get("nature")), nature_level(None))
        self.nature_note = hint("")
        lf = self.form = QFormLayout(self)
        lf.addRow(banner())
        lf.addRow("Scenery", self.preset)
        lf.addRow("", self.preset_note)
        lf.addRow("", self.real_sky)
        lf.addRow("City", self.city)
        self.city_status = hint("")
        self.city_status.setStyleSheet("color: #c0392b; font-size: 11px;")
        lf.addRow("", self.city_status)
        lf.addRow("", hint("Live weather for your city, from Open-Meteo. Without a city, only the "
                           "time of day follows your clock; the weather stays the scenery's."))
        lf.addRow("Nature", self.nature)
        lf.addRow("", self.nature_note)
        lf.addRow("", self.animations)
        lf.addRow("", self.planting)
        lf.addRow("", self.phone)
        lf.addRow("", hint("Adds a \"Memory Forest\" deck with one card that draws your forest in AnkiDroid; "
                           "study the deck to see it. The forest comes from this computer: "
                           "it updates each time Anki syncs here, so reviews done on your phone show up "
                           "after this computer syncs them in. Turning this off removes the deck again."))

    def offer(self, day, look: dict) -> None:
        """The presets there are on `day` (a seasonal one comes out on its first day)."""
        set_options(self.preset, preset_options(day, presets.match(look)))

    def connect(self, changed) -> None:
        for box in (self.animations, self.planting, self.phone):
            box.toggled.connect(changed)
        self.city.editingFinished.connect(changed)
        self.nature.currentIndexChanged.connect(changed)

    def sync(self, look: dict) -> None:
        """The preset, its note, the real-sky box and the city, in line with the five
        settings a preset stands for, whichever tab they were changed on."""
        key = presets.match(look)
        set_quietly(self.preset, key)
        spec = presets.by_key().get(key)
        self.preset_note.setText(spec.note if spec else "Your own mix, from the Fine-tuning tab. Choose any scenery above to start from it.")
        self.real_sky.blockSignals(True)
        self.real_sky.setChecked(presets.follows_real_sky(look))
        self.real_sky.blockSignals(False)
        self.city.setEnabled(look["weather"] == "auto")
        # the last lookup of this city, if it went wrong
        problem = city_problem(self.city.text()) if look["weather"] == "auto" else ""
        self.city_status.setText("" if not problem else
                                 "Couldn't find this city. Check the spelling, or try its English name." if problem.startswith("city not found")
                                 else "Couldn't reach the weather service; trying again soon.")
        if hasattr(self.form, "setRowVisible"):  # Qt 6.4+: the row takes no space while hidden
            self.form.setRowVisible(self.city_status, bool(problem))
        else:
            self.city_status.setVisible(bool(problem))
        self.nature_note.setText(NATURE_NOTES.get(self.nature.currentData(), ""))

    def values(self) -> dict:
        return {
            "city": self.city.text().strip(),
            "animations": self.animations.isChecked(),
            "planting_tooltip": self.planting.isChecked(),
            "phone_forest": self.phone.isChecked(),
            "nature": self.nature.currentData(),
        }

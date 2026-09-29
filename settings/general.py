"""The General tab: the settings most people ever touch - a preset, the real sky,
animation and the planting message."""

from __future__ import annotations

from aqt.qt import QCheckBox, QFormLayout, QLineEdit, QWidget

from .. import presets
from ..events import DEFAULT_STAKES, STAKES_LABELS, STAKES_NOTES
from ..live_weather import city_problem
from ..state import OFF_VALUES
from .widgets import combo, hint, set_quietly

STAKES_OPTIONS = list(STAKES_LABELS.items())


class GeneralTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self.preset = combo(presets.options(), presets.match(cfg))
        self.preset_note = hint("")
        self.real_sky = QCheckBox("Follow the real weather and time of day")
        self.real_sky.setChecked(presets.follows_real_sky(cfg))
        self.city = QLineEdit(cfg.get("city", ""))
        self.city.setPlaceholderText("Your city, e.g. Berlin")
        self.animations = QCheckBox("Animate the forest (clouds, rain, animals)")
        self.animations.setChecked(cfg.get("animations", True) not in OFF_VALUES)
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        self.stakes = combo(STAKES_OPTIONS, cfg.get("stakes") if isinstance(cfg.get("stakes"), str) else DEFAULT_STAKES, DEFAULT_STAKES)
        self.stakes_note = hint("")
        lf = self.form = QFormLayout(self)
        lf.addRow("Preset", self.preset)
        lf.addRow("", self.preset_note)
        lf.addRow("", self.real_sky)
        lf.addRow("City", self.city)
        self.city_status = hint("")
        self.city_status.setStyleSheet("color: #c0392b; font-size: 11px;")
        lf.addRow("", self.city_status)
        lf.addRow("", hint("Live weather for your city, from Open-Meteo. Without a city, only the "
                           "time of day follows your clock; the weather stays the preset's."))
        lf.addRow("Stakes", self.stakes)
        lf.addRow("", self.stakes_note)
        lf.addRow("", self.animations)
        lf.addRow("", self.planting)

    def connect(self, changed) -> None:
        for box in (self.animations, self.planting):
            box.toggled.connect(changed)
        self.city.editingFinished.connect(changed)
        self.stakes.currentIndexChanged.connect(changed)

    def sync(self, look: dict) -> None:
        """The preset, its note, the real-sky box and the city, in line with the five
        settings a preset stands for, whichever tab they were changed on."""
        key = presets.match(look)
        set_quietly(self.preset, key)
        spec = presets.by_key().get(key)
        self.preset_note.setText(spec.note if spec else "Your own mix, from the Fine-tuning tab. Pick a preset to start from one.")
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
        self.stakes_note.setText(STAKES_NOTES.get(self.stakes.currentData(), ""))

    def values(self) -> dict:
        return {
            "city": self.city.text().strip(),
            "animations": self.animations.isChecked(),
            "planting_tooltip": self.planting.isChecked(),
            "stakes": self.stakes.currentData(),
        }

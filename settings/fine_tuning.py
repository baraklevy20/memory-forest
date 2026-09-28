"""The Fine-tuning tab: the five settings a preset stands for, how and where the forest is
shown, and (while debug is on) the test forest."""

from __future__ import annotations

from aqt.qt import QFormLayout, QSpinBox, QVBoxLayout, QWidget

from .. import presets
from ..scene import ENVIRONMENTS, LANDMARKS, LANDSCAPES, TIME_LABELS, WEATHER_LABELS
from ..state import MAX_WIDTH_DEFAULT, MAX_WIDTH_MAX, MAX_WIDTH_MIN
from .debug import DebugGroup
from .widgets import combo, group, set_quietly

DAILY_OPTION = (presets.DAILY, "Surprise me daily")
ENV_OPTIONS = [DAILY_OPTION] + list(ENVIRONMENTS.items())
LANDSCAPE_OPTIONS = [DAILY_OPTION] + list(LANDSCAPES.items())
LANDMARK_OPTIONS = [DAILY_OPTION] + list(LANDMARKS.items())
WEATHER_OPTIONS = [("auto", "Live weather"), DAILY_OPTION] + list(WEATHER_LABELS.items())
TIME_OPTIONS = [("auto", "Follows your clock"), DAILY_OPTION] + list(TIME_LABELS.items())
DECK_OPTIONS = [("highlight", "The main forest, with that deck's trees lit"), ("own", "Their own forest, grown from that deck"), ("off", "No forest")]
WIDTH_STEP = 50


class FineTuningTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        base = presets.FOREST_PRESETS[0]
        self.environment = combo(ENV_OPTIONS, cfg.get("environment", base.environment), base.environment)
        self.landscape = combo(LANDSCAPE_OPTIONS, cfg.get("landscape", base.landscape), base.landscape)
        self.landmark = combo(LANDMARK_OPTIONS, cfg.get("landmark", base.landmark), base.landmark)
        self.weather = combo(WEATHER_OPTIONS, cfg.get("weather", base.weather), base.weather)
        self.time = combo(TIME_OPTIONS, cfg.get("time_of_day", base.time), base.time)
        self.deck_mode = combo(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight")
        self.max_width = QSpinBox(); self.max_width.setRange(MAX_WIDTH_MIN, MAX_WIDTH_MAX); self.max_width.setSingleStep(WIDTH_STEP); self.max_width.setSuffix(" px")
        try:
            self.max_width.setValue(int(cfg.get("max_width", MAX_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            self.max_width.setValue(MAX_WIDTH_DEFAULT)
        fv = QVBoxLayout(self)
        # the scene a preset stands for, apart from how and where the forest is shown
        ff = QFormLayout()
        ff.addRow("Environment", self.environment)
        ff.addRow("Landscape", self.landscape)
        ff.addRow("Landmark", self.landmark)
        ff.addRow("Weather", self.weather)
        ff.addRow("Time of day", self.time)
        df = QFormLayout()
        df.addRow("Deck screens", self.deck_mode)
        df.addRow("Maximum width", self.max_width)
        fv.addWidget(group("Scene", ff))
        fv.addWidget(group("Display", df))
        # the made-up test forest is a developer's tool: only there while debug is on
        self.debug = DebugGroup(cfg)
        self.debug_on = bool(cfg.get("debug", False))
        if self.debug_on:
            fv.addWidget(self.debug.widget())
        fv.addStretch(1)

    def _look_boxes(self) -> tuple:
        return ((self.environment, "environment"), (self.landscape, "landscape"), (self.landmark, "landmark"),
                (self.weather, "weather"), (self.time, "time_of_day"))

    def look(self) -> dict:
        """The five settings a preset stands for, as they are now."""
        return {field: box.currentData() for box, field in self._look_boxes()}

    def set_look(self, values: dict) -> None:
        """Fill in some of the five settings, without each announcing a change."""
        for box, field in self._look_boxes():
            if field in values:
                set_quietly(box, values[field])

    def connect(self, changed) -> None:
        for box in (self.environment, self.landscape, self.landmark, self.weather, self.time, self.deck_mode):
            box.currentIndexChanged.connect(changed)
        self.max_width.valueChanged.connect(changed)
        self.debug.connect(changed)

    def sync(self) -> None:
        self.debug.sync()

    def values(self) -> dict:
        return {
            **self.look(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "max_width": self.max_width.value(),
            **self.debug.values(),
        }

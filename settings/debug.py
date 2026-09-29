"""The Debug group on the Fine-tuning tab, a developer's tool that is only there while
debug is on: the made-up test forest, and a switch for each study event, to see them
without waiting for them."""

from __future__ import annotations

from aqt.qt import QCheckBox, QFormLayout, QHBoxLayout, QSlider, QSpinBox, Qt, QVBoxLayout

from ..debug_events import DEBUG_LEECHES_MAX, DEBUG_STAGNATION_MAX
from ..state import TEST_TREES_DEFAULT, TEST_TREES_MAX
from .widgets import group, hint

TREES_STEP, TREES_PAGE = 10, 250
DEBUG_NOTE = ("These show each event on whatever forest is on screen; set them back to off to "
              "see your own again.")


class DebugGroup:
    def __init__(self, cfg: dict):
        self.test = QCheckBox("Show a made-up test forest instead of mine")
        self.test.setChecked(bool(cfg.get("test_forest", False)))
        self.trees = QSlider(Qt.Orientation.Horizontal); self.trees.setRange(0, TEST_TREES_MAX); self.trees.setSingleStep(TREES_STEP); self.trees.setPageStep(TREES_PAGE)
        self.trees_box = QSpinBox(); self.trees_box.setRange(0, TEST_TREES_MAX); self.trees_box.setSingleStep(TREES_STEP); self.trees_box.setSuffix(" trees")
        try:
            n = max(0, min(TEST_TREES_MAX, int(cfg.get("test_trees", TEST_TREES_DEFAULT))))
        except (TypeError, ValueError):
            n = TEST_TREES_DEFAULT
        self.trees.setValue(n); self.trees_box.setValue(n)
        self.trees.valueChanged.connect(self.trees_box.setValue); self.trees_box.valueChanged.connect(self.trees.setValue)

        # and a switch for each study event, to see them without waiting for them
        def spin(key, top, suffix):
            box = QSpinBox(); box.setRange(0, top); box.setSuffix(suffix)
            try:
                box.setValue(max(0, min(top, int(cfg.get(key, 0) or 0))))
            except (TypeError, ValueError):  # a hand-edited config
                box.setValue(0)
            return box
        self.leeches = spin("debug_leeches", DEBUG_LEECHES_MAX, " trees")
        self.stagnation = spin("debug_stagnation", DEBUG_STAGNATION_MAX, "% tall")
        self.big = QCheckBox("Big learning days (wildflowers)"); self.big.setChecked(bool(cfg.get("debug_big_days", False)))

    def widget(self):
        dv = QVBoxLayout()
        row = QHBoxLayout(); row.addWidget(self.trees); row.addWidget(self.trees_box)
        dv.addWidget(self.test); dv.addLayout(row)
        ef = QFormLayout()
        ef.addRow("Crows (leeches)", self.leeches)
        ef.addRow("Tall grass", self.stagnation)
        ef.addRow("", self.big)
        dv.addLayout(ef)
        dv.addWidget(hint(DEBUG_NOTE))
        return group("Debug", dv)

    def connect(self, changed) -> None:
        for box in (self.test, self.big):
            box.toggled.connect(changed)
        for box in (self.trees_box, self.leeches, self.stagnation):
            box.valueChanged.connect(changed)

    def sync(self) -> None:
        on = self.test.isChecked()
        self.trees.setEnabled(on); self.trees_box.setEnabled(on)

    def values(self) -> dict:
        return {
            "test_forest": self.test.isChecked(),
            "test_trees": self.trees_box.value(),
            "debug_leeches": self.leeches.value(),
            "debug_stagnation": self.stagnation.value(),
            "debug_big_days": self.big.isChecked(),
        }

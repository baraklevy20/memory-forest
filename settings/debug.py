"""The Debug group on the Fine-tuning tab: the made-up test forest, a developer's tool
that is only there while debug is on."""

from __future__ import annotations

from aqt.qt import QCheckBox, QHBoxLayout, QSlider, QSpinBox, Qt, QVBoxLayout

from ..state import TEST_TREES_DEFAULT, TEST_TREES_MAX
from .widgets import group

TREES_STEP, TREES_PAGE = 10, 250


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

    def widget(self):
        dv = QVBoxLayout()
        row = QHBoxLayout(); row.addWidget(self.trees); row.addWidget(self.trees_box)
        dv.addWidget(self.test); dv.addLayout(row)
        return group("Debug", dv)

    def connect(self, changed) -> None:
        self.test.toggled.connect(changed)
        self.trees_box.valueChanged.connect(changed)

    def sync(self) -> None:
        self.trees.setEnabled(self.test.isChecked()); self.trees_box.setEnabled(self.test.isChecked())

    def values(self) -> dict:
        return {"test_forest": self.test.isChecked(), "test_trees": self.trees_box.value()}

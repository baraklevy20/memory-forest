"""The Debug tab, a developer's tool that is only there while debug is on: the made-up
test forest and the days passing on it, and a switch for each study event, to see them
without waiting for them."""

from __future__ import annotations

from aqt.qt import QCheckBox, QFormLayout, QHBoxLayout, QPushButton, QSlider, QSpinBox, Qt, QVBoxLayout, QWidget

from ..debug_events import DEBUG_BACKLOG_MAX
from ..events import TIMELINE_HAPPENINGS, TIMELINE_MAX_DAYS, timeline_steps
from ..state import TEST_TREES_DEFAULT, TEST_TREES_MAX
from .widgets import group, hint

TREES_STEP, TREES_PAGE = 10, 250
TIMELINE_NOTE = ("Days pass on the test forest, and what they bring follows from them as it would: "
                 "a day away on Merciless, or a week on Wild, brings the asteroid (fewer bring it closer), "
                 "and a week of reviewing only lets the grass grow. Studying plants a tree a day. A leech "
                 "brings a crow to a grown tree; curing one sends the oldest crow off and leaves a robin for "
                 "a week. A strike plays once - click its crater, or \"Asteroid struck\" under the forest, "
                 "to watch it again.")
DEBUG_NOTE = ("These show each event on whatever forest is on screen; set them back to off to "
              "see your own again. As the real events, they follow the Stakes: Peaceful shows no crows, "
              "tall grass or tumbleweeds. A backlog cleared stays cleared until you move the tumbleweeds "
              "again, or Reset.")
# what the label calls each kind of day, and what happens (once, and more than once)
DAY_KINDS = {"study": "studying", "review": "reviewing only", "away": "away"}
HAPPENINGS = {"leech": ("a card turns leech", "{n} cards turn leech"), "cure": ("a leech cured", "{n} leeches cured")}


class DebugTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
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
        # days to pass on the test forest: so many at a time, studying, reviewing only or away
        self.timeline = timeline_steps(cfg.get("debug_timeline"))
        self.timeline_label = hint("")
        self.days = QSpinBox(); self.days.setRange(1, TIMELINE_MAX_DAYS); self.days.setSuffix(" days"); self.days.setValue(1)
        self.timeline_steps = [self.days]  # what steps forward, which needs the test forest
        for text, kind in (("Studying", "study"), ("Reviewing only", "review"), ("Away", "away")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=kind: self._timeline_step(k))
            self.timeline_steps.append(b)
        self.timeline_reset = QPushButton("Reset")
        self.timeline_reset.clicked.connect(lambda: self._timeline_step(None))
        # and what happens along the way, on the next day to come
        self.happen = []
        for text, kind in (("A card turns leech", "leech"), ("A leech is cured", "cure")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=kind: self._timeline_step(k))
            self.happen.append(b)
        self.backlog = spin("debug_backlog", DEBUG_BACKLOG_MAX, "% deep")
        # a backlog cleared stays cleared until the tumbleweeds are moved again (or Reset)
        self.backlog.valueChanged.connect(self._backlog_moved)
        # clearing the backlog is a moment, not a state: each click blows the tumbleweeds away again
        self.clears = cfg.get("debug_backlog_cleared") if type(cfg.get("debug_backlog_cleared")) is int else 0
        self.was = cfg.get("debug_backlog_was") if type(cfg.get("debug_backlog_was")) is int else 0
        self.clear = QPushButton("Clear the backlog")
        self.clear.clicked.connect(self._clear_backlog)
        self.big = QCheckBox("Big learning days (wildflowers)"); self.big.setChecked(bool(cfg.get("debug_big_days", False)))
        self._changed = None
        self._lay_out()

    def _lay_out(self) -> None:
        tv = QVBoxLayout()
        row = QHBoxLayout(); row.addWidget(self.trees); row.addWidget(self.trees_box)
        tv.addWidget(self.test); tv.addLayout(row)
        tf = QFormLayout()
        steps = QHBoxLayout()
        for w in self.timeline_steps + [self.timeline_reset]:
            steps.addWidget(w)
        tf.addRow("Pass", steps)
        happen = QHBoxLayout()
        for b in self.happen:
            happen.addWidget(b)
        happen.addStretch(1)
        tf.addRow("Then", happen)
        tf.addRow("", self.timeline_label)
        tv.addLayout(tf)
        tv.addWidget(hint(TIMELINE_NOTE))
        ef = QFormLayout()
        hell = QHBoxLayout(); hell.addWidget(self.backlog); hell.addWidget(self.clear)
        ef.addRow("Tumbleweeds (review hell)", hell)
        ef.addRow("", self.big)
        ev = QVBoxLayout()
        ev.addLayout(ef)
        ev.addWidget(hint(DEBUG_NOTE))
        dv = QVBoxLayout(self)
        dv.addWidget(group("Test forest", tv))
        dv.addWidget(group("Study events", ev))
        dv.addStretch(1)

    def _timeline_step(self, kind) -> None:
        """Pass the days asked for, of this kind, or have something happen once (None
        starts the timeline over)."""
        n = 1 if kind in TIMELINE_HAPPENINGS else self.days.value()
        if kind is None:
            self.timeline = []
            self.clears = 0  # and no backlog cleared either
        elif self.timeline and self.timeline[-1][0] == kind:
            self.timeline[-1][1] += n  # days of one kind in a row add up, and so does what happens
        else:
            self.timeline.append([kind, n])
        self.timeline = timeline_steps(self.timeline)  # never past the most days it holds
        if self._changed:
            self._changed()

    def _backlog_moved(self, _value) -> None:
        self.clears = 0

    def _clear_backlog(self) -> None:
        """The tumbleweeds there are now (or some, if there are none) blow away."""
        self.was = self.backlog.value() or DEBUG_BACKLOG_MAX // 2
        self.clears += 1
        self.backlog.blockSignals(True)
        self.backlog.setValue(0)
        self.backlog.blockSignals(False)
        if self._changed:
            self._changed()

    def connect(self, changed) -> None:
        self._changed = changed
        for box in (self.test, self.big):
            box.toggled.connect(changed)
        for box in (self.trees_box, self.backlog):
            box.valueChanged.connect(changed)

    def sync(self) -> None:
        on = self.test.isChecked()
        self.trees.setEnabled(on); self.trees_box.setEnabled(on)
        def said(kind, n):
            if kind in HAPPENINGS:
                return HAPPENINGS[kind][n != 1].format(n=n)
            return f"{n} day{'s' if n != 1 else ''} {DAY_KINDS[kind]}"
        self.timeline_label.setText(" → ".join(said(kind, n) for kind, n in self.timeline)
                                    or "No days passed yet (needs the test forest)")
        for w in self.timeline_steps + self.happen:
            w.setEnabled(on)

    def values(self) -> dict:
        return {
            "test_forest": self.test.isChecked(),
            "test_trees": self.trees_box.value(),
            "debug_timeline": [list(step) for step in self.timeline],
            "debug_backlog": self.backlog.value(),
            "debug_backlog_cleared": self.clears,
            "debug_backlog_was": self.was,
            "debug_big_days": self.big.isChecked(),
        }

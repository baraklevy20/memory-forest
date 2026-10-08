"""The Fine-tuning tab: the five settings a preset stands for, under the scenery they start
from, and how and where the forest is shown."""

from __future__ import annotations

import os

from aqt.qt import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPalette,
    QPixmap,
    QRect,
    QSpinBox,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import presets
from ..scene import ENVIRONMENTS, LANDMARKS, LANDSCAPES, TIME_LABELS, WEATHER_LABELS
from ..state import MAX_WIDTH_DEFAULT, MAX_WIDTH_MAX, MAX_WIDTH_MIN, shows_on_deck_list, today
from .scenery_picker import PICTURES, crisp, mosaic
from .widgets import combo, group, hint, set_options, set_quietly

DAILY_OPTION = (presets.DAILY, "Surprise me daily")
ENV_OPTIONS = [DAILY_OPTION] + list(ENVIRONMENTS.items())
LANDSCAPE_OPTIONS = [DAILY_OPTION] + list(LANDSCAPES.items())
LANDMARK_OPTIONS = [DAILY_OPTION] + list(LANDMARKS.items())
WEATHER_OPTIONS = [("auto", "Live weather"), DAILY_OPTION] + list(WEATHER_LABELS.items())
TIME_OPTIONS = [("auto", "Follows your clock"), DAILY_OPTION] + list(TIME_LABELS.items())
# where the forest shows: the same "No forest" in both, so the two rows read alike
MAIN_OPTIONS = [(True, "Your forest"), (False, "No forest")]
DECK_OPTIONS = [("highlight", "Your forest, that deck's trees lit up"), ("own", "A forest of that deck's own"), ("off", "No forest")]
FIELD_NAMES = {"environment": "Environment", "landscape": "Landscape", "landmark": "Landmark",
               "weather": "Weather", "time_of_day": "Time of day"}
WIDTH_STEP = 50
WIDTH_BOX_W = 110
# the "starting from" strip: a piece from the middle of the scenery's picture, in its own pixels
TILE_W, TILE_H = 128, 72
STRIP_GAP, STRIP_TEXT_GAP, STRIP_BELOW = 12, 2, 6
RESET_GAP = 6  # between a dropdown and its Reset
# Reset is a quiet text link, not a button: grey, the accent colour under the pointer
RESET_STYLE = """
QToolButton {{ border: none; background: transparent; color: {quiet}; padding: 2px 4px; font-size: 12px; }}
QToolButton:hover {{ color: {accent}; text-decoration: underline; }}
"""
PRESET_NOTE = "Change anything below to make it your own mix. The General tab picks a scenery to start from."
MIX_NOTE = "Reset a row to put the scenery's own choice back."


def env_options(day, chosen: str | None) -> list:
    """The environments to offer on `day`: not a seasonal preset's before it first comes
    out, unless it is the one already chosen."""
    hidden = presets.hidden_environments(day) - {chosen}
    return [o for o in ENV_OPTIONS if o[0] not in hidden]


def tile(key: str) -> QPixmap:
    """The middle of a scenery's picture, at the strip's size, in whole pixels; a null pixmap
    if it has none."""
    pix = mosaic() if key == presets.DAILY else crisp(os.path.join(PICTURES, f"{key}.png"))
    if pix.isNull():
        return pix
    dpr = pix.devicePixelRatio()
    w, h = min(TILE_W, int(pix.width() / dpr)), min(TILE_H, int(pix.height() / dpr))
    x, y = (int(pix.width() / dpr) - w) // 2, (int(pix.height() / dpr) - h) // 2
    out = pix.copy(QRect(int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr)))
    out.setDevicePixelRatio(dpr)
    return out


class FineTuningTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        base = presets.FOREST_PRESETS[0]
        self._day = today(cfg)
        self._changed = None  # the dialog's, once connected
        self.environment = combo(env_options(self._day, cfg.get("environment")), cfg.get("environment", base.environment), base.environment)
        self.landscape = combo(LANDSCAPE_OPTIONS, cfg.get("landscape", base.landscape), base.landscape)
        self.landmark = combo(LANDMARK_OPTIONS, cfg.get("landmark", base.landmark), base.landmark)
        self.weather = combo(WEATHER_OPTIONS, cfg.get("weather", base.weather), base.weather)
        self.time = combo(TIME_OPTIONS, cfg.get("time_of_day", base.time), base.time)
        self.main_forest = combo(MAIN_OPTIONS, shows_on_deck_list(cfg), True)
        self.deck_mode = combo(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight")
        self.max_width = QSpinBox(); self.max_width.setRange(MAX_WIDTH_MIN, MAX_WIDTH_MAX); self.max_width.setSingleStep(WIDTH_STEP); self.max_width.setSuffix(" px")
        self.max_width.setMaximumWidth(WIDTH_BOX_W)
        try:
            self.max_width.setValue(int(cfg.get("max_width", MAX_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            self.max_width.setValue(MAX_WIDTH_DEFAULT)

        # the scenery the five settings start from: its picture, its name, and a line on what to do
        self.picture = QLabel(); self.picture.setFixedSize(TILE_W, TILE_H)
        self.start_name = QLabel()
        self.start_name.setWordWrap(True)  # (a mix's long name goes onto a second line)
        font = self.start_name.font(); font.setBold(True); font.setPointSizeF(font.pointSizeF() + 1)
        self.start_name.setFont(font)
        self.start_note = hint("")
        text = QVBoxLayout(); text.setSpacing(STRIP_TEXT_GAP)
        text.addStretch(1); text.addWidget(self.start_name); text.addWidget(self.start_note); text.addStretch(1)
        strip = QHBoxLayout(); strip.setSpacing(STRIP_GAP)
        strip.addWidget(self.picture, 0, Qt.AlignmentFlag.AlignTop); strip.addLayout(text, 1)

        # each of the five, with a Reset beside it while it differs from that scenery's own
        # choice; a hidden Reset keeps its room, so the dropdowns don't jump as it comes and goes
        labels = []
        self.resets = {}
        ff = QFormLayout()
        for box, field in self._look_boxes():
            reset = QToolButton(); reset.setText("\u21ba Reset")
            reset.setToolTip("Put back the scenery's own choice")
            reset.setCursor(Qt.CursorShape.PointingHandCursor)
            pal = reset.palette()
            reset.setStyleSheet(RESET_STYLE.format(quiet=pal.color(QPalette.ColorRole.PlaceholderText).name(),
                                                   accent=pal.color(QPalette.ColorRole.Highlight).name()))
            policy = reset.sizePolicy(); policy.setRetainSizeWhenHidden(True); reset.setSizePolicy(policy)
            reset.setVisible(False)
            reset.clicked.connect(lambda _checked=False, f=field: self._reset(f))
            self.resets[field] = reset
            row = QHBoxLayout(); row.setSpacing(RESET_GAP)
            row.addWidget(box, 1); row.addWidget(reset)
            labels.append(QLabel(FIELD_NAMES[field]))
            ff.addRow(labels[-1], row)
        scene = QVBoxLayout()
        scene.addLayout(strip); scene.addSpacing(STRIP_BELOW); scene.addLayout(ff)

        df = QFormLayout()
        for name, widget in (("Main screen", self.main_forest), ("Deck screens", self.deck_mode),
                             ("Forest width", self.max_width)):
            labels.append(QLabel(name))
            df.addRow(labels[-1], widget)
        # the labels of both groups in one column
        width = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setFixedWidth(width)

        fv = QVBoxLayout(self)
        fv.addWidget(group("Scene", scene))
        fv.addWidget(group("Where it shows", df))
        fv.addStretch(1)
        self.sync()

    def _look_boxes(self) -> tuple:
        return ((self.environment, "environment"), (self.landscape, "landscape"), (self.landmark, "landmark"),
                (self.weather, "weather"), (self.time, "time_of_day"))

    def look(self) -> dict:
        """The five settings a preset stands for, as they are now."""
        return {field: box.currentData() for box, field in self._look_boxes()}

    def offer(self, day) -> None:
        self._day = day
        set_options(self.environment, env_options(day, self.environment.currentData()))

    def sync(self) -> None:
        """The strip and the Resets, for the scenery the five settings are, or are nearest."""
        spec, differ = presets.nearest(self.look(), presets.available(self._day))
        self.picture.setPixmap(tile(spec.key))
        if differ:
            self.start_name.setText(f"Your own mix, from {spec.label}")
            self.start_note.setText(MIX_NOTE)
        else:
            self.start_name.setText(spec.label)
            self.start_note.setText(PRESET_NOTE)
        for field, reset in self.resets.items():
            reset.setVisible(field in differ)

    def _reset(self, field: str) -> None:
        """Put one setting back to the nearest scenery's own choice, as changing it by hand would."""
        spec, _differ = presets.nearest(self.look(), presets.available(self._day))
        self.set_look({field: spec.values()[field]})
        if self._changed:
            self._changed()
        else:
            self.sync()

    def set_look(self, values: dict) -> None:
        """Fill in some of the five settings, without each announcing a change."""
        for box, field in self._look_boxes():
            if field in values:
                set_quietly(box, values[field])

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        look = {f: (box, FIELD_NAMES[f]) for box, f in self._look_boxes()}
        return {**look, "main_forest": (self.main_forest, "Main screen"), "deck_forest_mode": (self.deck_mode, "Deck screens"),
                "max_width": (self.max_width, "Forest width")}

    def connect(self, changed) -> None:
        self._changed = changed
        for box in (self.environment, self.landscape, self.landmark, self.weather, self.time, self.main_forest, self.deck_mode):
            box.currentIndexChanged.connect(changed)
        self.max_width.valueChanged.connect(changed)

    def values(self) -> dict:
        return {
            **self.look(),
            "main_forest": self.main_forest.currentData(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "max_width": self.max_width.value(),
        }

"""Customize, on the Scenery tab: the five settings a preset stands for, in the tiles' place
while open (a "Customize <scenery>" link under the tiles opens it, "Sceneries" goes back), so
the scenery and its tuning share a page without making the tab any taller."""

from __future__ import annotations

from aqt.qt import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPalette,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import presets
from ..i18n import N_, t, tx
from ..scene import ENVIRONMENTS, LANDMARKS, LANDSCAPES, TIME_LABELS, WEATHER_LABELS
from ..seasons import offer_day
from .scenery_picker import mosaic, picture
from .widgets import Link, combo, hint, set_options, set_quietly

DAILY_OPTION = (presets.DAILY, N_("preset.daily"))
ENV_OPTIONS = [DAILY_OPTION] + [(k, f"env.{k}") for k in ENVIRONMENTS]  # (names: ids, shown with tx)
LANDSCAPE_OPTIONS = [DAILY_OPTION] + [(k, f"landscape.{k}") for k in LANDSCAPES]
LANDMARK_OPTIONS = [DAILY_OPTION] + [(k, f"landmark.{k}") for k in LANDMARKS]
WEATHER_OPTIONS = [("auto", N_("settings.customize.live_weather")), DAILY_OPTION] + list(WEATHER_LABELS.items())
TIME_OPTIONS = [("auto", N_("settings.customize.follows_your_clock")), DAILY_OPTION] + list(TIME_LABELS.items())
FIELD_NAMES = {"environment": N_("settings.customize.environment"), "landscape": N_("settings.customize.landscape"), "landmark": N_("settings.customize.landmark"),
               "weather": N_("settings.customize.weather"), "time_of_day": N_("settings.customize.time_of_day")}
RESET_GAP = 6  # between a dropdown and its Reset
# Reset is a quiet text link, not a button: grey, the accent colour under the pointer
RESET_STYLE = """
QToolButton {{ border: none; background: transparent; color: {quiet}; padding: 2px 4px; font-size: 12px; }}
QToolButton:hover {{ color: {accent}; text-decoration: underline; }}
"""
# the five in two columns: each holds a word or two, so a full-width row would be mostly empty
COLUMNS = 2
COLUMN_GAP, ROW_GAP = 18, 8
# the header: back to the tiles, then the scenery's picture (a small copy of its tile) and name
BACK = N_("settings.customize.sceneries")
THUMB_W, THUMB_H = 48, 27
HEADER_GAP = 12
PRESET_NOTE = N_("settings.customize.change_anything_here_to_make_it")
MIX_NOTE = N_("settings.customize.reset_a_row_to_put_the")


def env_options(day, chosen: str | None) -> list:
    """The environments to offer on `day`: not a seasonal preset's before it first comes
    out, unless it is the one already chosen."""
    hidden = presets.hidden_environments(day) - {chosen}
    return shown([o for o in ENV_OPTIONS if o[0] not in hidden])


def shown(options) -> list:
    """Options with their labels in the reader's language (they are marked where they're written)."""
    return [(key, tx(label)) for key, label in options]


class Customize(QWidget):
    def __init__(self, cfg: dict, on_back):
        super().__init__()
        base = presets.FOREST_PRESETS[0]
        self._day = offer_day(cfg)
        self._changed = None  # the dialog's, once connected
        self.environment = combo(env_options(self._day, cfg.get("environment")), cfg.get("environment", base.environment), base.environment)
        self.landscape = combo(shown(LANDSCAPE_OPTIONS), cfg.get("landscape", base.landscape), base.landscape)
        self.landmark = combo(shown(LANDMARK_OPTIONS), cfg.get("landmark", base.landmark), base.landmark)
        self.weather = combo(shown(WEATHER_OPTIONS), cfg.get("weather", base.weather), base.weather)
        self.time = combo(shown(TIME_OPTIONS), cfg.get("time_of_day", base.time), base.time)

        self.back = Link(tx(BACK), on_back)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.title = QLabel()
        font = self.title.font(); font.setBold(True); self.title.setFont(font)
        header = QHBoxLayout()
        header.setSpacing(HEADER_GAP)
        header.addWidget(self.back)
        header.addWidget(self.thumb)
        header.addWidget(self.title, 1)
        self.note = hint("")

        # each of the five, with a Reset beside it while it differs from that scenery's own
        # choice; a hidden Reset keeps its room, so the dropdowns don't jump as it comes and goes
        self.resets = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(COLUMN_GAP)
        grid.setVerticalSpacing(ROW_GAP)
        for i, (box, field) in enumerate(self._look_boxes()):
            reset = QToolButton(); reset.setText("\u21ba")
            reset.setToolTip(t("settings.customize.reset_put_back_the_scenerys_own"))
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
            r, c = divmod(i, COLUMNS)
            grid.addWidget(QLabel(tx(FIELD_NAMES[field])), r, 2 * c)
            grid.addLayout(row, r, 2 * c + 1)
        for c in range(COLUMNS):
            grid.setColumnStretch(2 * c + 1, 1)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(header)
        v.addWidget(self.note)
        v.addLayout(grid)
        v.addStretch(1)
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

    def link_text(self) -> str:
        """The way here under the tiles, naming what is being customized: the scenery, or a mix made from it."""
        if self._differ:
            return t("settings.customize.customize_your_own_mix_from_scenery", scenery=tx(self._spec.name))
        return t("settings.customize.customize_scenery", scenery=tx(self._spec.name))

    def sync(self) -> None:
        """The header, the note and the Resets, for the scenery the five settings are, or are
        nearest."""
        spec, differ = presets.nearest(self.look(), presets.available(self._day))
        self._spec, self._differ = spec, differ
        self.title.setText(t("settings.customize.customize_your_own_mix_from_scenery_2", scenery=tx(spec.name)) if differ
                           else t("settings.customize.customize_scenery_2", scenery=tx(spec.name)))
        pix = mosaic() if spec.key == presets.DAILY else picture(spec.key)
        if not pix.isNull():
            dpr = pix.devicePixelRatio()
            small = pix.scaled(round(THUMB_W * dpr), round(THUMB_H * dpr), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.FastTransformation)  # (a quarter: whole pixels)
            small.setDevicePixelRatio(dpr)
            self.thumb.setPixmap(small)
        self.note.setText(tx(MIX_NOTE if differ else PRESET_NOTE))
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
        return {f: (box, FIELD_NAMES[f]) for box, f in self._look_boxes()}

    def connect(self, changed) -> None:
        self._changed = changed
        for box, _field in self._look_boxes():
            box.currentIndexChanged.connect(changed)

    def values(self) -> dict:
        return self.look()

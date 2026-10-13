"""The Forest tab: how the forest behaves and where it shows - Nature, the screens it is on,
the study calendar, motion and the planting message, and the forest on your phone."""

from __future__ import annotations

import os

from aqt.qt import (
    QCheckBox,
    QHBoxLayout,
    QIcon,
    QPushButton,
    QRect,
    QSize,
    QSizePolicy,
    QSpinBox,
    Qt,
    QVBoxLayout,
)

from ..events import DEFAULT_NATURE, NATURE_LABELS, NATURE_NOTES, NATURE_SWITCH_NOTE, calm, nature_level
from ..phone_note import phone_on
from ..state import (
    ANIMATION_VALUES,
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    animation_mode,
    calendar_on,
    calendar_view,
    shows_on_deck_list,
    shows_on_finished,
    week_start,
)
from .palette import color
from .scenery_picker import crisp
from .widgets import Choice, Tab, form, group, hint

NATURE_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nature")
NATURE_ICON = 16  # points: the icons' own pixels, one a point
NATURE_GAP = 8
NATURE_STYLE = """
QPushButton {{ border: 1px solid {line}; border-radius: 7px; padding: 6px 10px; font-size: 13px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ border: 2px solid {ring}; padding: 5px 9px; background: rgba(128, 128, 128, 0.16); font-weight: bold; }}
"""
# (one line: SETTINGS_GUIDELINES.md)
PHONE_NOTE = 'Adds a "Memory Forest" deck with a card showing your forest and heatmap as you sync.'
ANIMATION_OPTIONS = [("on", "On"), ("off", "Off"), ("system", "Follow system")]
# where the forest shows: the same "No forest" in both, so the two rows read alike
MAIN_OPTIONS = [(True, "Your forest"), (False, "No forest")]
DECK_OPTIONS = [("highlight", "Your forest, that deck's trees lit up"), ("own", "A forest of that deck's own"), ("off", "No forest")]
# the study calendar: how much of it shows at once, and the day its weeks start on
CALENDAR_OPTIONS = [("timeline", "Timeline"), ("by_year", "By year")]
WEEK_OPTIONS = [("system", "Auto"), ("monday", "Mon"), ("sunday", "Sun"), ("saturday", "Sat")]
WEEK_TIPS = {"system": "Your system's first day of the week", "monday": "Monday", "sunday": "Sunday", "saturday": "Saturday"}
# the week's start as joined buttons, one control, the chosen one filled as Anki fills a default
# button (the corners rounded only at the row's two ends)
WEEK_STYLE = """
QPushButton {{ border: 1px solid {line}; border-left-width: {left}px; border-radius: 0; padding: 3px 10px;
              border-top-left-radius: {r0}px; border-bottom-left-radius: {r0}px;
              border-top-right-radius: {r1}px; border-bottom-right-radius: {r1}px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ background: {ring}; color: white; border-color: {ring}; }}
"""
WEEK_RADIUS = 6
# points between two fields sharing a row (the deck screens' forest and "On finished decks too",
# the calendar's two screens), so the tab grows no taller (SETTINGS_GUIDELINES.md)
CALENDAR_GAP = 24
WIDTH_STEP = 50
WIDTH_BOX_W = 110


class WeekChoice(Choice):
    """The day the study calendar's weeks start on, as a row of joined buttons: Auto (the
    system's), Mon, Sun, Sat."""

    def __init__(self, value: str):
        super().__init__(WEEK_OPTIONS, value, "system", gap=0, stretch=False)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)  # (its own width, not the row's)

    def make_button(self, key, label: str):
        at = [k for k, _label in WEEK_OPTIONS].index(key)
        first, last = at == 0, at == len(WEEK_OPTIONS) - 1
        b = QPushButton(label)
        b.setToolTip(WEEK_TIPS[key])
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(WEEK_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS"), left=1 if first else 0,
                                          r0=WEEK_RADIUS if first else 0, r1=WEEK_RADIUS if last else 0))
        return b


class NatureChoice(Choice):
    """The three Nature levels side by side, each with its icon (drawn by dev/nature_icons.py),
    the chosen one ringed as a focused field is in Anki."""

    def __init__(self, level: str):
        super().__init__(list(NATURE_LABELS.items()), level, DEFAULT_NATURE, gap=NATURE_GAP, stretch=False)

    def make_button(self, key, label: str):
        b = QPushButton(QIcon(crisp(os.path.join(NATURE_ICONS, f"{key}.png"))), f" {label}")
        b.setIconSize(QSize(NATURE_ICON, NATURE_ICON))
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b.setStyleSheet(NATURE_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS")))
        return b


def beside(first, *rest, top: bool = False) -> QHBoxLayout:
    """A row's field with more after it, CALENDAR_GAP on: centred on the row, or along its top
    line (`top`) beside a choice of several lines."""
    row, align = QHBoxLayout(), Qt.AlignmentFlag.AlignTop if top else Qt.AlignmentFlag.AlignVCenter
    row.addWidget(first, 0, align)
    row.addSpacing(CALENDAR_GAP)
    for w in rest:
        row.addWidget(w, 0, align)
    row.addStretch(1)
    return row


class ForestTab(Tab):
    def __init__(self, cfg: dict, on_phone, phone_was: bool | None = None):
        super().__init__()
        self.on_phone = on_phone  # makes or takes away the phone's deck (actions.phone_switched)
        self.nature = NatureChoice(nature_level(cfg.get("nature")))
        self.nature_note = hint("")
        self.nature_note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (its room fits the longest level)
        self.main_forest = Choice(MAIN_OPTIONS, shows_on_deck_list(cfg), True)
        self.deck_mode = Choice(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight", vertical=True)
        # the deck screens' forest and calendar on a deck you have finished too (Anki's
        # congratulations page), beside their choice
        self.finished = QCheckBox("On finished decks too")
        self.finished.setChecked(shows_on_finished(cfg))
        # the study calendar, under the forest or without it: on which screens, its view, its week
        self.calendar_main = QCheckBox("Main screen")
        self.calendar_main.setChecked(calendar_on("main", cfg))
        self.calendar_decks = QCheckBox("Deck screens")
        self.calendar_decks.setChecked(calendar_on("decks", cfg))
        self.calendar = Choice(CALENDAR_OPTIONS, calendar_view(cfg), "timeline")
        self.week = WeekChoice(week_start(cfg))
        self.max_width = QSpinBox(); self.max_width.setRange(MAX_WIDTH_MIN, MAX_WIDTH_MAX); self.max_width.setSingleStep(WIDTH_STEP); self.max_width.setSuffix(" px")
        self.max_width.setMaximumWidth(WIDTH_BOX_W)
        try:
            self.max_width.setValue(int(cfg.get("max_width", MAX_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            self.max_width.setValue(MAX_WIDTH_DEFAULT)
        # On, Off, or Follow system (still while the system asks for reduced motion)
        self.animations = Choice(ANIMATION_OPTIONS, animation_mode(cfg), "on")
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        self.phone = QCheckBox("Show my forest on my phone")
        # not the add-on config's: whether the collection holds the note that takes the forest
        # to your phone (phone.py), made or taken away as it is ticked, and put back on Cancel -
        # as it was when the first of the dialogs opened, after Restore defaults reopened it
        self.phone_was = phone_on() if phone_was is None else phone_was
        self.phone.setChecked(phone_on())
        self.phone.toggled.connect(self.on_phone)

        nv = QVBoxLayout()
        nv.addWidget(self.nature)
        nv.addWidget(self.nature_note)
        where = form()
        where.addRow("Main screen", self.main_forest)
        where.addRow("Deck screens", beside(self.deck_mode, self.finished, top=True))
        where.addRow("Forest width", self.max_width)
        cal = form()
        cal.addRow("Show on", beside(self.calendar_main, self.calendar_decks))
        cal.addRow("View", self.calendar)
        cal.addRow("Week starts on", self.week)
        motion = QVBoxLayout()
        animate = form()
        animate.addRow("Animate the forest", self.animations)
        motion.addLayout(animate)
        motion.addWidget(self.planting)
        pv = QVBoxLayout()
        pv.addWidget(self.phone)
        pv.addWidget(hint(PHONE_NOTE))
        v = QVBoxLayout(self)
        self.nature_group = group("Nature", nv)
        v.addWidget(self.nature_group)
        v.addWidget(group("Where it shows", where))
        self.calendar_group = group("Study heatmap", cal)
        v.addWidget(self.calendar_group)
        v.addWidget(group("Motion and messages", motion))
        v.addWidget(group("On your phone", pv))
        v.addStretch(1)

    def put_phone_back(self) -> None:
        """Cancel puts the phone setting back as the dialog found it, as it does the add-on
        config."""
        if phone_on() != self.phone_was:
            self.on_phone(self.phone_was)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"nature": (self.nature_group.title, "Nature"), "main_forest": (self.main_forest, "Main screen"),
                "deck_forest_mode": (self.deck_mode, "Deck screens"),
                "calendar": (self.calendar_group.title, "Study heatmap"), "max_width": (self.max_width, "Forest width"),
                "animations": (self.animations, "Animate the forest"), "planting_tooltip": (self.planting, "The planting message"),
                "phone": (self.phone, "Your forest on your phone")}

    def connect(self, changed) -> None:
        for choice in (self.animations, self.main_forest, self.deck_mode, self.calendar, self.week):
            choice.on_change(changed)
        self.max_width.valueChanged.connect(changed)
        for box in (self.planting, self.phone, self.calendar_main, self.calendar_decks, self.finished):
            box.toggled.connect(changed)
        self.nature.on_change(changed)

    def sync(self) -> None:
        level = self.nature.currentData()
        note = NATURE_NOTES.get(level, "")
        self.nature_note.setText(note if calm(level) else f"{note} {NATURE_SWITCH_NOTE}")
        # (how it shows only matters while it shows somewhere)
        on = self.calendar_main.isChecked() or self.calendar_decks.isChecked()
        # (a finished deck's screen shows what the deck screens do, so only while they show something)
        self.finished.setEnabled(self.deck_mode.currentData() != "off" or self.calendar_decks.isChecked())
        self.calendar.setEnabled(on); self.week.setEnabled(on)
        self.fit()

    def fit(self) -> None:
        """Nature's line asks for room for its longest level from the start, so picking another
        never makes the dialog grow."""
        width = self.nature_note.width()
        if width > 0:
            metrics = self.nature_note.fontMetrics()
            texts = [n if calm(k) else f"{n} {NATURE_SWITCH_NOTE}" for k, n in NATURE_NOTES.items()]
            tallest = max(metrics.boundingRect(QRect(0, 0, width, 10000), Qt.TextFlag.TextWordWrap, t).height() for t in texts)
            self.nature_note.setMinimumHeight(tallest)
        super().fit()

    def values(self) -> dict:
        return {
            "animations": ANIMATION_VALUES[self.animations.currentData()],
            "planting_tooltip": self.planting.isChecked(),
            "nature": self.nature.currentData(),
            "main_forest": self.main_forest.currentData(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "calendar": self.calendar.currentData(),
            "calendar_week_start": self.week.currentData(),
            "calendar_main": self.calendar_main.isChecked(),
            "calendar_decks": self.calendar_decks.isChecked(),
            "finished_decks": self.finished.isChecked(),
            "max_width": self.max_width.value(),
        }

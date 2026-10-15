"""The Heatmap tab: the study heatmap under the forest - the screens it shows on, its view and the
day its weeks start on; and, under Start date, the reviews from before the forest's start date and
where your streak counts from. Without a start date (Decks tab) those two change nothing, so they
are never greyed out for it: a hint says so. What the shades go by is the toggle on the heatmap
itself, not repeated here."""

from __future__ import annotations

from aqt.qt import QCheckBox, QEvent, QPushButton, QSizePolicy, Qt, QVBoxLayout

from ..payload import _week_start_day
from ..state import calendar_on, calendar_view, shows_record, streak_from_start, week_start
from .forest_tab import beside
from .palette import color
from .widgets import Choice, Tab, form, group, hint, hint_style

# how much of it shows at once, and the day its weeks start on
CALENDAR_OPTIONS = [("timeline", "Timeline"), ("by_year", "By year")]
WEEK_OPTIONS = [("system", "Auto"), ("monday", "Mon"), ("sunday", "Sun"), ("saturday", "Sat")]
WEEK_TIPS = {"system": "Your system's first day of the week", "monday": "Monday", "sunday": "Sunday", "saturday": "Saturday"}
# the days as the page counts them (Sunday 0): Auto's label names the system's
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
# the week's start as joined buttons, one control, the chosen one a soft grey with a blue edge (the
# solid blue was the loudest thing on the tab; the corners rounded only at the row's two ends)
WEEK_STYLE = """
QPushButton {{ border: 1px solid {line}; border-left-width: {left}px; border-radius: 0; padding: 3px 10px;
              border-top-left-radius: {r0}px; border-bottom-left-radius: {r0}px;
              border-top-right-radius: {r1}px; border-bottom-right-radius: {r1}px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ background: rgba(128, 128, 128, 0.38); border-color: {ring}; }}
QPushButton:disabled {{ color: {off}; background: rgba(128, 128, 128, 0.05); }}
QPushButton:checked:disabled {{ color: {off}; background: rgba(128, 128, 128, 0.22); border-color: {line}; }}
"""
WEEK_RADIUS = 6
VIEW_NOTE = "Timeline: the past year and the weeks ahead. By year: January to December."
# (one line: SETTINGS_GUIDELINES.md)
# where your streak counts from: your real one (from your first review), or from the forest's start date
STREAK_FROM_OPTIONS = [(False, "Your first review"), (True, "The start date")]
START_NOTE = "Your forest's start date is set on the Decks tab. Without one, these change nothing."


class WeekChoice(Choice):
    """The day the heatmap's weeks start on, as a row of joined buttons: Auto (the system's),
    Mon, Sun, Sat."""

    def __init__(self, value: str):
        super().__init__(WEEK_OPTIONS, value, "system", gap=0, stretch=False)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)  # (its own width, not the row's)
        # one Tab stop, the chosen day, and the arrow keys from day to day, as round radio buttons
        # do (push buttons are each a Tab stop of their own, with no arrows)
        for b in self.buttons.values():
            b.installEventFilter(self)
        self.group.buttonToggled.connect(lambda _b, _on: self._tab_stop())
        self._tab_stop()

    def _tab_stop(self) -> None:
        for b in self.buttons.values():
            b.setFocusPolicy(Qt.FocusPolicy.StrongFocus if b.isChecked() else Qt.FocusPolicy.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            keys = list(self.buttons)
            at = keys.index(self.currentData()) + (1 if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down) else -1)
            if 0 <= at < len(keys):
                self.buttons[keys[at]].setChecked(True)
                self.buttons[keys[at]].setFocus()
            return True
        return False

    def make_button(self, key, label: str):
        at = [k for k, _label in WEEK_OPTIONS].index(key)
        first, last = at == 0, at == len(WEEK_OPTIONS) - 1
        tip = WEEK_TIPS[key]
        if key == "system":  # (Auto (Mon): the day it comes to here)
            day = DAY_NAMES[_week_start_day({})]
            label, tip = f"{label} ({day[:3]})", f"{tip}: {day}"
        b = QPushButton(label)
        b.setToolTip(tip)
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(WEEK_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS"), off=color("FG_DISABLED"),
                                          left=1 if first else 0,
                                          r0=WEEK_RADIUS if first else 0, r1=WEEK_RADIUS if last else 0))
        return b


class HeatmapTab(Tab):
    def __init__(self, cfg: dict):
        super().__init__()
        # under the forest or without it: on which screens
        self.calendar_main = QCheckBox("Main screen")
        self.calendar_main.setChecked(calendar_on("main", cfg))
        self.calendar_decks = QCheckBox("Deck screens")
        self.calendar_decks.setChecked(calendar_on("decks", cfg))
        self.calendar = Choice(CALENDAR_OPTIONS, calendar_view(cfg), "timeline")
        self.week = WeekChoice(week_start(cfg))
        # the reviews from before the forest's start date, in the heatmap all the same
        self.record = QCheckBox("Show the reviews from before it")
        self.record.setChecked(shows_record(cfg))
        self.streak_from = Choice(STREAK_FROM_OPTIONS, streak_from_start(cfg), False)
        self._streak_pick = self.streak_from.currentData()  # (what it goes back to once the reviews before show again)

        where = form()
        where.addRow("Show on", beside(self.calendar_main, self.calendar_decks))
        layout = self.layout_form = form()
        layout.addRow("View", self.calendar)
        self.view_note = hint(VIEW_NOTE)
        # (greyed out with the view, which a plain hint's colour would not be)
        self.view_note.setStyleSheet(f"QLabel {{ {hint_style()} }} QLabel:disabled {{ color: {color('FG_DISABLED')}; }}")
        layout.addRow("", self.view_note)
        layout.addRow("Week starts on", self.week)
        start = self.start_form = form()
        start.addRow(self.record)
        start.addRow("Count your streak from", self.streak_from)
        start.addRow(hint(START_NOTE))
        # (the three groups' fields start on one line)
        labels = [f.itemAt(r, f.ItemRole.LabelRole).widget() for f in (where, layout, start) for r in range(f.rowCount())
                  if f.itemAt(r, f.ItemRole.LabelRole) and f.itemAt(r, f.ItemRole.LabelRole).widget()]
        widest = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(widest)
        v = QVBoxLayout(self)
        self.where_group = group("Where it shows", where)
        v.addWidget(self.where_group)
        v.addWidget(group("Layout", layout))
        self.start_group = group("Start date", start)
        v.addWidget(self.start_group)
        v.addStretch(1)

    # the notes that make this whole tab new: their NEW goes on the tab's name too
    new_tab_keys = ("calendar",)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"calendar": (self.where_group.title, "Study heatmap"),
                "streak_from_start": (self.streak_from, "Count your streak from")}

    def connect(self, changed) -> None:
        for choice in (self.calendar, self.week, self.streak_from):
            choice.on_change(changed)
        for box in (self.calendar_main, self.calendar_decks, self.record):
            box.toggled.connect(changed)

    def sync(self) -> None:
        # (how it shows only matters while it shows somewhere)
        on = self.calendar_main.isChecked() or self.calendar_decks.isChecked()
        self.calendar.setEnabled(on); self.week.setEnabled(on); self.record.setEnabled(on); self.view_note.setEnabled(on)
        for field in (self.calendar, self.week):  # (their labels grey out with them)
            label = self.layout_form.labelForField(field)
            if label is not None:
                label.setEnabled(on)
        # (a heatmap that leaves out the reviews before the start date counts the streak from it
        # too: shown as such while it can't be changed, and back to your own pick after)
        record = self.record.isChecked()
        if record and not self.streak_from.isEnabled():
            self.streak_from.set_quietly(self._streak_pick)
        elif not record and self.streak_from.isEnabled():
            self._streak_pick = self.streak_from.currentData()
            self.streak_from.set_quietly(True)
        self.streak_from.setEnabled(record)
        label = self.start_form.labelForField(self.streak_from)
        if label is not None:
            label.setEnabled(record)
        self.fit()

    def values(self) -> dict:
        return {
            "calendar": self.calendar.currentData(),
            "calendar_week_start": self.week.currentData(),
            "calendar_main": self.calendar_main.isChecked(),
            "calendar_decks": self.calendar_decks.isChecked(),
            "calendar_record": self.record.isChecked(),
            # (your own pick kept while the start date decides it)
            "streak_from_start": self.streak_from.currentData() if self.record.isChecked() else self._streak_pick,
        }

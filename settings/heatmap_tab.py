"""The Heatmap tab: the study heatmap under the forest - the screens it shows on, its view and the
day its weeks start on. What it counts (earlier reviews, where your streak counts from) stays on
the Decks tab, beside the start date it goes by."""

from __future__ import annotations

from aqt.qt import QCheckBox, QPushButton, QSizePolicy, Qt, QVBoxLayout

from ..state import calendar_on, calendar_view, week_start
from .forest_tab import beside
from .palette import color
from .widgets import Choice, Tab, form, group, hint

# how much of it shows at once, and the day its weeks start on
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
# (one line: SETTINGS_GUIDELINES.md)
DECKS_NOTE = "Earlier reviews and where your streak counts from are on the Decks tab, beside the start date."


class WeekChoice(Choice):
    """The day the heatmap's weeks start on, as a row of joined buttons: Auto (the system's),
    Mon, Sun, Sat."""

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

        where = form()
        where.addRow("Show on", beside(self.calendar_main, self.calendar_decks))
        layout = form()
        layout.addRow("View", self.calendar)
        layout.addRow("Week starts on", self.week)
        v = QVBoxLayout(self)
        self.where_group = group("Where it shows", where)
        v.addWidget(self.where_group)
        v.addWidget(group("Layout", layout))
        v.addWidget(hint(DECKS_NOTE))
        v.addStretch(1)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"calendar": (self.where_group.title, "Study heatmap")}

    def connect(self, changed) -> None:
        for choice in (self.calendar, self.week):
            choice.on_change(changed)
        for box in (self.calendar_main, self.calendar_decks):
            box.toggled.connect(changed)

    def sync(self) -> None:
        # (how it shows only matters while it shows somewhere)
        on = self.calendar_main.isChecked() or self.calendar_decks.isChecked()
        self.calendar.setEnabled(on); self.week.setEnabled(on)
        self.fit()

    def values(self) -> dict:
        return {
            "calendar": self.calendar.currentData(),
            "calendar_week_start": self.week.currentData(),
            "calendar_main": self.calendar_main.isChecked(),
            "calendar_decks": self.calendar_decks.isChecked(),
        }

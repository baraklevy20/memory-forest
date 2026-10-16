"""The Heatmap tab: the study heatmap under the forest - the screens it shows on, its view and the
day its weeks start on; under Streak, how many days a week it counts; under Start date, the reviews
from before the forest's start date and where your streak counts from; and its look: whose colours
its days take and how its tiles are drawn (heatmap_look.py, chosen by eye: settings/heatmap_look.py).
Without a start date (Decks tab) the earlier reviews and the streak's start change nothing, so they
are never greyed out for it: a hint says so. What the shades go by is the toggle on the heatmap
itself, not repeated here."""

from __future__ import annotations

from aqt.qt import QCheckBox, QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from ..payload import _week_start_day
from ..scope import anki_today
from ..state import (
    STREAK_WEEKS,
    calendar_on,
    calendar_view,
    shows_record,
    streak_from_start,
    streak_week,
    streak_week_since,
    week_start,
)
from .forest_tab import beside
from .heatmap_look import LOOK_NOTE, LookControls
from .palette import color
from .widgets import Choice, JoinedChoice, Link, Tab, form, group, hint, hint_style, resize_with

# how much of it shows at once, and the day its weeks start on
CALENDAR_OPTIONS = [("timeline", "Timeline"), ("by_year", "By year")]
WEEK_OPTIONS = [("system", "Auto"), ("monday", "Mon"), ("sunday", "Sun"), ("saturday", "Sat")]
WEEK_TIPS = {"system": "Your system's first day of the week", "monday": "Monday", "sunday": "Sunday", "saturday": "Saturday"}
# the days as the page counts them (Sunday 0): Auto's label names the system's
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
VIEW_NOTE = "Timeline: the past year and the weeks ahead. By year: January to December."
# (one line: SETTINGS_GUIDELINES.md)
# where your streak counts from: your real one (from your first review), or from the forest's start date
STREAK_FROM_OPTIONS = [(False, "Your first review"), (True, "The start date")]
# the look's page: the line that opens it, under the settings, and its header
LOOK_LINK, LOOK_BACK, LOOK_TITLE = "Colours and tiles \u203a", "\u2039 Heatmap", "Colours and tiles"
LOOK_SUMMARY_GAP, LOOK_HEADER_GAP = 10, 14
START_NOTE = "Your forest's start date is set on the Decks tab. Without one, these change nothing."
# how many days a week it counts: a week's other days, missed, pass as a day with nothing due does
STREAK_WEEK_OPTIONS = [(7, "Every day"), (6, "6 days a week"), (5, "5 days a week")]
# (one line: SETTINGS_GUIDELINES.md)
STREAK_WEEK_NOTE = "A day off keeps your streak but doesn't add to it. Days off count from the day you choose this."


class WeekChoice(JoinedChoice):
    """The day the heatmap's weeks start on, as a row of joined buttons: Auto (the system's),
    Mon, Sun, Sat."""

    def __init__(self, value: str):
        super().__init__(WEEK_OPTIONS, value, "system", WEEK_TIPS)

    def label_for(self, key, label: str) -> tuple:
        tip = WEEK_TIPS[key]
        if key == "system":  # (Auto (Mon): the day it comes to here)
            day = DAY_NAMES[_week_start_day({})]
            label, tip = f"{label} ({day[:3]})", f"{tip}: {day}"
        return label, tip


class HeatmapTab(Tab):
    def __init__(self, cfg: dict):
        super().__init__()
        # under the forest or without it: on which screens
        self.calendar_main = QCheckBox("Main screen")
        self.calendar_main.setChecked(calendar_on("main", cfg))
        self.calendar_decks = QCheckBox("Deck screens")
        self.calendar_decks.setChecked(calendar_on("decks", cfg))
        self.calendar = Choice(CALENDAR_OPTIONS, calendar_view(cfg), "timeline")
        # (the same setting as the switch on the heatmap: what it was when last read here, and
        # whether it was changed here since, so the switch's change is taken in, not undone)
        self.view_known, self.view_touched = self.calendar.currentData(), False
        self.calendar.on_change(self._view_changed_here)
        self.week = WeekChoice(week_start(cfg))
        # the reviews from before the forest's start date, in the heatmap all the same
        self.record = QCheckBox("Show the reviews from before it")
        self.record.setChecked(shows_record(cfg))
        self.streak_from = Choice(STREAK_FROM_OPTIONS, streak_from_start(cfg), False)
        self._streak_pick = self.streak_from.currentData()  # (what it goes back to once the reviews before show again)
        # days off: counted from the day they are chosen (the dialog keeps that day as it finds it)
        self.streak_week = Choice(STREAK_WEEK_OPTIONS, streak_week(cfg), 7)
        self.week_was = (self.streak_week.currentData(), streak_week_since(cfg))

        # (where it shows: Layout's first row, not a group of one row: the tab was taller than a
        # 720-pixel screen has room for, and the Look line at its foot went out of sight)
        layout = self.layout_form = form()
        layout.addRow("Show on", beside(self.calendar_main, self.calendar_decks))
        layout.addRow("View", self.calendar)
        self.view_note = hint(VIEW_NOTE)
        # (greyed out with the view, which a plain hint's colour would not be)
        self.view_note.setStyleSheet(f"QLabel {{ {hint_style()} }} QLabel:disabled {{ color: {color('FG_DISABLED')}; }}")
        layout.addRow("", self.view_note)
        layout.addRow("Week starts on", self.week)
        streak = form()
        streak.addRow("Your streak counts", self.streak_week)
        streak.addRow("", hint(STREAK_WEEK_NOTE))
        start = self.start_form = form()
        start.addRow(self.record)
        start.addRow("Count your streak from", self.streak_from)
        start.addRow(hint(START_NOTE))
        # (the groups' fields start on one line)
        labels = [f.itemAt(r, f.ItemRole.LabelRole).widget() for f in (layout, streak, start) for r in range(f.rowCount())
                  if f.itemAt(r, f.ItemRole.LabelRole) and f.itemAt(r, f.ItemRole.LabelRole).widget()]
        widest = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(widest)
        # its look: whose colours (Scenery, the ready ramps, your own) and its tiles, on a page of
        # their own in the settings' place (as Customize takes the scenery tiles'), opened from a
        # line at the foot of the settings that shows what is chosen
        self.look = LookControls(cfg)
        self.look.on_refresh(self._show_summary)
        self.summary_strip, self.summary_text = QLabel(), QLabel()
        self.open_look = Link(LOOK_LINK, lambda: self.show_look(True))
        summary = QHBoxLayout()
        summary.setSpacing(LOOK_SUMMARY_GAP)
        summary.addWidget(self.summary_strip)
        summary.addWidget(self.summary_text)
        summary.addStretch(1)
        summary.addWidget(self.open_look)
        settings = QWidget()
        sv = QVBoxLayout(settings)
        sv.setContentsMargins(0, 0, 0, 0)
        self.layout_group = group("Layout", layout)
        sv.addWidget(self.layout_group)
        sv.addWidget(group("Streak", streak))
        self.start_group = group("Start date", start)
        sv.addWidget(self.start_group)
        self.look_group = group("Look", summary)
        sv.addWidget(self.look_group)
        sv.addStretch(1)  # (in a taller window the groups keep together, the room left under them)
        look_page = QWidget()
        lv = QVBoxLayout(look_page)
        lv.setContentsMargins(0, 0, 0, 0)
        self.back = Link(LOOK_BACK, lambda: self.show_look(False))
        title = QLabel(LOOK_TITLE)
        font = title.font(); font.setBold(True); title.setFont(font)
        header = QHBoxLayout()
        header.setSpacing(LOOK_HEADER_GAP)
        header.addWidget(self.back)
        header.addWidget(title, 1)
        for w in (self.back, title):  # (the header keeps its line's height, the groups take the rest)
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        lv.addLayout(header)
        lv.addWidget(hint(LOOK_NOTE))
        lv.addSpacing(LOOK_HEADER_GAP)
        self.colours_group = group("Colours", self.look.colours)
        lv.addWidget(self.colours_group)
        self.tiles_group = group("Tiles", self.look.tiles_box)
        lv.addWidget(self.tiles_group)
        lv.addStretch(1)
        self.stack = QStackedWidget()
        self.stack.addWidget(settings)
        self.stack.addWidget(look_page)
        self._size_to_page()
        v = QVBoxLayout(self)
        v.addWidget(self.stack)
        v.addStretch(1)
        self._show_summary()

    def show_look(self, on: bool) -> None:
        """The look's page in the settings' place, or the settings back, the window as much
        shorter or taller as the page is (as the Scenery tab's Customize)."""
        if on == self.looking():
            return

        def turn() -> None:
            self.stack.setCurrentIndex(1 if on else 0)
            self._size_to_page()
            self.updateGeometry()
        resize_with(self, turn)
        (self.back if on else self.open_look).setFocus()

    def looking(self) -> bool:
        return self.stack.currentIndex() == 1

    def _size_to_page(self) -> None:
        """Only the page in view counts towards the stack's height (scenery_tab._size_to_page)."""
        for i in range(self.stack.count()):
            vertical = QSizePolicy.Policy.Preferred if i == self.stack.currentIndex() else QSizePolicy.Policy.Ignored
            self.stack.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, vertical)
        self.stack.updateGeometry()

    def _show_summary(self) -> None:
        pix, text = self.look.summary()
        self.summary_strip.setPixmap(pix)
        self.summary_text.setText(text)

    def reveal(self, widget) -> None:
        """Open the look's page if `widget` is on it, so a note pointing there finds it."""
        if self.stack.widget(1).isAncestorOf(widget):
            self.show_look(True)

    # the notes that make this whole tab new: their NEW goes on the tab's name too
    new_tab_keys = ("calendar",)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"calendar": (self.layout_group.title, "Study heatmap"),
                "streak_from_start": (self.streak_from, "Count your streak from"),
                "streak_week": (self.streak_week, "Your streak counts"),
                "calendar_colours": (self.colours_group.title, "Heatmap colours"),
                "calendar_tiles": (self.tiles_group.title, "Heatmap tiles")}

    def connect(self, changed) -> None:
        for choice in (self.calendar, self.week, self.streak_from, self.streak_week):
            choice.on_change(changed)
        for box in (self.calendar_main, self.calendar_decks, self.record):
            box.toggled.connect(changed)
        self.look.on_change(changed)

    def set_scenery(self, key: str, edition_cfg: dict) -> None:
        """The scenery the Scenery tab has chosen, and the edition the Debug tab pretends this is:
        Match the scenery shows its picture, and the Plus sceneries are locked as the picker's are."""
        self.look.set_scenery(key, edition_cfg)

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
        for g in (self.colours_group, self.tiles_group, self.look_group):
            g.setEnabled(on)
        self.fit()

    def _view_changed_here(self) -> None:
        self.view_touched = self.calendar.currentData() != self.view_known

    def reload_view(self, cfg: dict) -> None:
        """Take in a view chosen on the heatmap itself since it was last read here (Timeline |
        By year), unless it was changed here since."""
        outside = calendar_view(cfg)
        if outside != self.view_known and not self.view_touched:
            self.calendar.set_quietly(outside)
        self.view_known = outside

    def values(self) -> dict:
        return {
            "calendar": self.calendar.currentData(),
            "calendar_week_start": self.week.currentData(),
            "calendar_main": self.calendar_main.isChecked(),
            "calendar_decks": self.calendar_decks.isChecked(),
            "calendar_record": self.record.isChecked(),
            # (your own pick kept while the start date decides it)
            "streak_from_start": self.streak_from.currentData() if self.record.isChecked() else self._streak_pick,
            **self.week_values(),
            **self.look.values(),
        }

    def week_values(self) -> dict:
        """The days a week your streak counts, and the day its days off count from: kept while it
        stays under 7, today when it goes under, none at every day (so days off never reach back)."""
        week = self.streak_week.currentData()
        was, since = self.week_was
        if week not in STREAK_WEEKS or week == 7:
            return {"streak_week": 7, "streak_week_since": ""}
        keep = since if was != 7 and since is not None else anki_today()
        return {"streak_week": week, "streak_week_since": keep.isoformat()}

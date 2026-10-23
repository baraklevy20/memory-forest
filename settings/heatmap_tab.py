"""The Heatmap tab: the study heatmap under the forest, on one page. First its look, what people
change most: whose colours its days take and its style (heatmap_look.py, chosen by eye:
settings/heatmap_look.py); then the screens it shows on and the day its weeks start on; under
Streak, how many days a week it counts; under Start date, the reviews from before the forest's start
date and where your streak counts from. Its view (Timeline | By year | Streak) is the switch on the heatmap.
Without a start date (Decks tab) the earlier reviews and the streak's start change nothing, so they
are never greyed out for it: a hint says so. What the shades go by is the toggle on the heatmap
itself, not repeated here."""

from __future__ import annotations

from aqt.qt import QCheckBox, QLabel, QVBoxLayout, QWidget

from ..payload import week_start_day
from ..scope import anki_today
from ..state import (
    STREAK_WEEKS,
    calendar_fill,
    calendar_on,
    calendar_width,
    shows_record,
    streak_from_start,
    streak_week,
    streak_week_since,
    week_start,
)
from .forest_tab import beside
from .heatmap_look import LookControls
from .widgets import Choice, JoinedChoice, Tab, form, group, hint

# its width (state.CALENDAR_WIDTHS) and what fills it (state.CALENDAR_FILLS)
WIDTH_OPTIONS = [("fixed", "Fixed"), ("forest", "Follow the forest"), ("full", "Full width")]
WIDTH_TIPS = {"fixed": "680 px, or less where there is less room",
              "forest": "85% of the forest's width",
              "full": "85% of the room it has: the row under or over the deck list, or its column beside it"}
FILL_OPTIONS = [("more", "More months"), ("bigger", "Bigger days")]
FILL_TIPS = {"more": "Every day the same size: a wider heatmap shows more months",
             "bigger": "Ten months, with bigger days to fill the width"}
# (Fill it with is the Timeline's: never greyed out, as the view is switched on the heatmap itself)
FILL_NOTE = "By year and Streak always fit a year to the width."
# the day its weeks start on
WEEK_OPTIONS = [("system", "Auto"), ("monday", "Mon"), ("sunday", "Sun"), ("saturday", "Sat")]
WEEK_TIPS = {"system": "Your system's first day of the week", "monday": "Monday", "sunday": "Sunday", "saturday": "Saturday"}
# the days as the page counts them (Sunday 0): Auto's label names the system's
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
# where your streak counts from: your real one (from your first review), or from the forest's start date
STREAK_FROM_OPTIONS = [(False, "Your first review"), (True, "The start date")]
# one page (2026-10-16): its look first, what people change most; the view left to the switch on
# the heatmap and the page's hint gone, it fits the dialog without a second page. ("Style", not
# "Tiles", which could as well be the tiles' colours: one word, as Colours is, and shape or texture
# alike, which "Pattern" was not for Flat and Round)
START_NOTE = "Your forest's start date is set on the Decks tab."
# how many days a week it counts: a week's other days, missed, pass as a day with nothing due does
STREAK_WEEK_OPTIONS = [(7, "Every day"), (6, "6 days a week"), (5, "5 days a week")]
# (one line: SETTINGS_GUIDELINES.md)
STREAK_WEEK_NOTE = "A day off keeps your streak but doesn't add to it."
HINT_GAP = 4  # (between a field and its hint)


def with_hint(field, text: str) -> QWidget:
    """`field` with its hint just under it, as one field of a form row: a hint in a row of its own
    took a form's row spacing and a wrapped label's room, a big gap under one line."""
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(HINT_GAP)
    v.addWidget(field)
    v.addWidget(hint(text))
    return box


class WeekChoice(JoinedChoice):
    """The day the heatmap's weeks start on, as a row of joined buttons: Auto (the system's),
    Mon, Sun, Sat."""

    def __init__(self, value: str):
        super().__init__(WEEK_OPTIONS, value, "system", WEEK_TIPS)

    def label_for(self, key, label: str) -> tuple:
        tip = WEEK_TIPS[key]
        if key == "system":  # (Auto (Mon): the day it comes to here)
            day = DAY_NAMES[week_start_day({})]
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
        self.week = WeekChoice(week_start(cfg))
        self.heat_width = JoinedChoice(WIDTH_OPTIONS, calendar_width(cfg), "forest", WIDTH_TIPS)
        self.fill = JoinedChoice(FILL_OPTIONS, calendar_fill(cfg), "more", FILL_TIPS)
        self.fill_label = QLabel("Fill it with")
        # the reviews from before the forest's start date, in the heatmap all the same
        self.record = QCheckBox("Show the reviews from before your forest's start date")
        self.record.setChecked(shows_record(cfg))
        self.streak_from = Choice(STREAK_FROM_OPTIONS, streak_from_start(cfg), False)
        self._streak_pick = self.streak_from.currentData()  # (what it goes back to once the reviews before show again)
        self._streak_free = True  # (whether it is yours to choose just now: sync)
        # days off: counted from the day they are chosen (the dialog keeps that day as it finds it)
        self.streak_week = Choice(STREAK_WEEK_OPTIONS, streak_week(cfg), 7)
        self.week_was = (self.streak_week.currentData(), streak_week_since(cfg))

        # (where it shows: Layout's first row, not a group of one row: the tab was taller than a
        # 720-pixel screen has room for, and the Look line at its foot went out of sight)
        # (two groups named for what they hold, not one "Settings": what the heatmap shows, and how
        # the streak counts, rest days and the start date's say in it)
        layout = self.layout_form = form()
        layout.addRow("Show on", beside(self.calendar_main, self.calendar_decks))
        # (Width with what fills it on one row: two parts of one size, each a word or two)
        self.width_row = beside(self.heat_width, self.fill_label, self.fill)
        width_box = self.width_box = QWidget()  # (the row with its hint just under it: with_hint, for a row of two)
        wv = QVBoxLayout(width_box)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(HINT_GAP)
        wv.addLayout(self.width_row)
        wv.addWidget(hint(FILL_NOTE))
        layout.addRow("Width", width_box)
        layout.addRow("Week starts on", self.week)
        layout.addRow(self.record)
        streak = self.start_form = form()
        streak.addRow("Your streak counts", with_hint(self.streak_week, STREAK_WEEK_NOTE))
        streak.addRow("Your streak counts from", self.streak_from)
        streak.addRow(hint(START_NOTE))
        # (the groups' fields start on one line: one fixed width, which a NEW tag on any of them
        # grows for all, whats_new._tag_label)
        labels = [f.itemAt(r, f.ItemRole.LabelRole).widget() for f in (layout, streak) for r in range(f.rowCount())
                  if f.itemAt(r, f.ItemRole.LabelRole) and f.itemAt(r, f.ItemRole.LabelRole).widget()]
        widest = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setFixedWidth(widest)
        # its look first, what people change most: whose colours (Scenery, the ready ramps, your
        # own) and its style; then where it shows, its weeks, the streak and the start date
        self.look = LookControls(cfg)
        v = QVBoxLayout(self)
        self.colours_group = group("Colours", self.look.colours)
        v.addWidget(self.colours_group)
        self.tiles_group = group("Style", self.look.tiles_box)
        v.addWidget(self.tiles_group)
        self.layout_group = group("Layout", layout)
        v.addWidget(self.layout_group)
        v.addWidget(group("Streak", streak))
        v.addStretch(1)  # (in a taller window the groups keep together, the room left under them)

    # the notes that make this whole tab new: their NEW goes on the tab's name too
    new_tab_keys = ("calendar",)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"calendar": (self.layout_group.title, "Study heatmap"),
                "streak_from_start": (self.streak_from, "Your streak counts from"),
                "streak_week": (self.streak_week, "Your streak counts"),
                "calendar_colours": (self.colours_group.title, "Heatmap colours"),
                "calendar_tiles": (self.tiles_group.title, "Heatmap style"),
                "calendar_width": (self.heat_width, "Width"), "calendar_fill": (self.fill, "Fill it with")}

    def connect(self, changed) -> None:
        for choice in (self.week, self.heat_width, self.fill, self.streak_from, self.streak_week):
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
        self.week.setEnabled(on); self.record.setEnabled(on)
        for w in (self.heat_width, self.fill_label, self.fill):
            w.setEnabled(on)
        for field in (self.width_box, self.week):
            label = self.layout_form.labelForField(field)  # (its label greys out with it)
            if label is not None:
                label.setEnabled(on)
        # (a heatmap that leaves out the reviews before the start date counts the streak from it
        # too: shown as such while it can't be changed, and back to your own pick after)
        # (with the heatmap shown nowhere the box is greyed, and the streak counts as your pick:
        # payload._page_stats goes by the start date's record only where a heatmap shows)
        record = self.record.isChecked() or not on
        if record and not self.streak_from.isEnabled():
            self.streak_from.set_quietly(self._streak_pick)
        elif not record and self.streak_from.isEnabled():
            self._streak_pick = self.streak_from.currentData()
            self.streak_from.set_quietly(True)
        self.streak_from.setEnabled(record)
        self._streak_free = record
        label = self.start_form.labelForField(self.streak_from)
        if label is not None:
            label.setEnabled(record)
        for g in (self.colours_group, self.tiles_group):
            g.setEnabled(on)
        self.fit()

    def values(self) -> dict:
        return {
            "calendar_week_start": self.week.currentData(),
            "calendar_width": self.heat_width.currentData(),
            "calendar_fill": self.fill.currentData(),
            "calendar_main": self.calendar_main.isChecked(),
            "calendar_decks": self.calendar_decks.isChecked(),
            "calendar_record": self.record.isChecked(),
            # (your own pick kept while the start date decides it)
            "streak_from_start": self.streak_from.currentData() if self._streak_free else self._streak_pick,
            **self.week_values(),
            **self.look.values(),
        }

    def week_values(self) -> dict:
        """The days a week your streak counts, and the day its days off count from: kept while the
        count stays as it was, today when it changes, none at every day (so days off never reach
        back: from 6 to 5, the old day would give the weeks before a second day off)."""
        week = self.streak_week.currentData()
        was, since = self.week_was
        if week not in STREAK_WEEKS or week == 7:
            return {"streak_week": 7, "streak_week_since": ""}
        keep = since if week == was and since is not None else anki_today()
        return {"streak_week": week, "streak_week_since": keep.isoformat()}

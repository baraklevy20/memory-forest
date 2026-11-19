"""The Debug tab's Year recap group: the year's card shown again (move the tab's Date into the recap's
window to see it, December or January)."""

from __future__ import annotations

import datetime as _dt

from aqt.qt import QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget

from .. import recap
from .widgets import group, hint

NOTE = ("The year's look back (recap.py, web/recap.js) is offered from Dec 7 to Jan 15: in December the year so "
        "far, and answered then, its card comes back once in January. Move the Date below into that window to "
        "see it: a card on the deck list's forest, then a link under its caption. Show the card again forgets "
        "that the year chosen was opened or dismissed.")


def make(changed, day: _dt.date | None = None) -> QWidget:
    """The group; `changed()` redraws the forest. `day`: the Debug tab's date, when one is set: the
    year whose card it shows is the one chosen to begin with."""
    # (in January, the year just gone: the one its card is offered for; by the Debug tab's date, as the
    # card is: pretending Jan 5, 2026 it is 2025's card on the deck list, and the clock's year was 2026 here)
    today = day or _dt.date.today()
    year = QSpinBox(); year.setRange(2000, 2100); year.setValue(recap.year_for(today) or today.year)
    again = QPushButton("Show the card again")
    again.setAutoDefault(False)  # Enter in the dialog means Done

    def forgot():
        recap.forget(year.value())
        changed()
    again.clicked.connect(forgot)
    row = QHBoxLayout(); row.addWidget(year); row.addWidget(again); row.addStretch(1)
    box = QVBoxLayout(); box.addLayout(row); box.addWidget(hint(NOTE))
    return group("Year recap", box)

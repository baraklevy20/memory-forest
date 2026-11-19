"""The Debug tab's Year recap group: the recap opened now, for any year, and its card shown again."""

from __future__ import annotations

import datetime as _dt

from aqt.qt import QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget

from .. import recap
from .widgets import group, hint

NOTE = ("The year's look back (recap.py, web/recap.js) is offered from Dec 15 to Jan 15 (move the Date below to "
        "see that): a card on the deck list's forest, then a link in its caption. Open it now opens it on the "
        "deck list for the year chosen, any day. Show the card again forgets that "
        "the year chosen was opened or dismissed.")


def make(changed) -> QWidget:
    """The group; `changed()` redraws the forest (the deck list opens the recap as it draws)."""
    # (in January, the year just gone: the one its card is offered for)
    today = _dt.date.today()
    year = QSpinBox(); year.setRange(2000, 2100); year.setValue(recap.year_for(today) or today.year)
    open_now = QPushButton("Open it now")
    again = QPushButton("Show the card again")
    for b in (open_now, again):
        b.setAutoDefault(False)  # Enter in the dialog means Done

    def opened():
        recap.ask_open(year.value())
        changed()

    def forgot():
        recap.forget(year.value())
        changed()
    open_now.clicked.connect(opened)
    again.clicked.connect(forgot)
    row = QHBoxLayout(); row.addWidget(year); row.addWidget(open_now); row.addWidget(again); row.addStretch(1)
    box = QVBoxLayout(); box.addLayout(row); box.addWidget(hint(NOTE))
    return group("Year recap", box)

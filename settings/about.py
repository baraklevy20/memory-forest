"""The About tab."""

from __future__ import annotations

from aqt.qt import QLabel, Qt, QVBoxLayout, QWidget

ABOUT = """<b>This is your forest.</b><br><br>
One tree for every day you have learned new cards: today's is the seedling at the front,
and the oldest stands at the back. Trees grow as those cards settle into memory, and take
on a few yellow leaves when some of them slip. Days of reviews alone plant no tree,
but they keep yours healthy.<br><br>
Real weather comes from <a href="https://open-meteo.com/">Open-Meteo</a>."""


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        av = QVBoxLayout(self)
        text = QLabel(ABOUT); text.setWordWrap(True); text.setTextFormat(Qt.TextFormat.RichText); text.setOpenExternalLinks(True)
        av.addWidget(text); av.addStretch(1)

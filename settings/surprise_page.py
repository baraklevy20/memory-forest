"""Surprise me daily's sceneries: the page that takes the tiles' place on the Scenery tab (as
Customize does), where each scenery it takes turns with is ticked, or unticked to leave it out."""

from __future__ import annotations

from aqt.qt import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .. import presets
from .scenery_picker import SceneryPicker
from .widgets import Link, hint

BACK = "‹ Sceneries"
TITLE = "Surprise me daily"
# one line beside the title, so the page is no taller than the tiles with their links under them
NOTE = "Untick the ones you'd rather not see."  # (how many are ticked: on the link)
ONE_LEFT = "Only one ticked: the same scenery every day."
HEADER_GAP = 12


def turn_keys(offered) -> list:
    """Of the sceneries `offered` (a holiday's only in its week), the ones Surprise me daily takes turns with."""
    specs = presets.by_key()
    return [k for k in offered if k in specs and k != presets.DAILY]


class SurprisePage(QWidget):
    def __init__(self, cfg: dict, on_back, on_change, animate: bool):
        super().__init__()
        # the ones left out, whether offered here or not (a Plus scenery in the base edition
        # stays left out, should Plus come back)
        self.left_out = presets.left_out(cfg)
        self.on_change = on_change
        self.offered = []
        self.back = Link(BACK, on_back)
        self.title = QLabel(TITLE)
        font = self.title.font(); font.setBold(True); self.title.setFont(font)
        self.note = hint("")
        header = QHBoxLayout()
        header.setSpacing(HEADER_GAP)
        header.addWidget(self.back)
        header.addWidget(self.title)
        header.addWidget(self.note, 1)
        self.picker = SceneryPicker(self._ticked, animate, many=True)
        self.picker.allow_search(False)  # (the tiles page's search stays on the group's row)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(header)
        v.addWidget(self.picker)

    def heightForWidth(self, width: int) -> int:
        """None while another page is in view (the Scenery tab ignores this one then): a stack
        asks every page for its height at a width, whatever its size policy, and this page's
        wrapped hint would make the tab as tall as this page on the tiles and on Customize."""
        if self.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored:
            return -1
        return super().heightForWidth(width)

    def offer(self, offered, day) -> None:
        """Tick boxes for the sceneries it can take turns with among those `offered` on `day`."""
        self.offered = turn_keys(offered)
        self.picker.set_choices(self.offered, None, day)
        self.picker.set_ticked(self._kept())
        self._count()

    def _ticked(self, _key: str) -> None:
        ticked = set(self.picker.ticked())
        self.left_out = {k for k in self.left_out if k not in self.offered} | {k for k in self.offered if k not in ticked}
        self._count()
        self.on_change()

    def _kept(self) -> list:
        """The ones offered it takes turns with: with every one left out (the holiday kept alone
        gone with its week, or only Plus's kept in the base edition), all of them, as the forest
        has them (`presets.of_the_day`). The ones left out stay so until a box is ticked."""
        return [k for k in self.offered if k not in self.left_out] or list(self.offered)

    def kept(self) -> int:
        return len(self._kept())

    def summary(self) -> str:
        """How many it takes turns with: "all 12", or "9 of 12"."""
        kept, every = self.kept(), len(self.offered)
        return f"all {every}" if kept == every else f"{kept} of {every}"

    def _count(self) -> None:
        self.note.setText(ONE_LEFT if self.kept() == 1 else NOTE)

    def values(self) -> dict:
        return {"surprise_left_out": sorted(self.left_out)}

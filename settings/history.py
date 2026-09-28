"""The History tab: which decks and days the forest grows from."""

from __future__ import annotations

import datetime as _dt

from aqt import mw
from aqt.qt import QCheckBox, QDate, QDateEdit, QHBoxLayout, Qt, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..state import OFF_VALUES
from .widgets import group, hint

DECK_ROLE = Qt.ItemDataRole.UserRole
DATE_FORMAT = "d MMMM yyyy"
DECKS_NOTE = "Unticked decks are left out of the forest. Tick them again anytime to bring them back."
SINCE_NOTE = "The forest starts over from this day. Untick it anytime to bring the rest back."
SUSPENDED_NOTE = "Their trees stay just as they were when the cards were suspended."


class HistoryTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self.excluded = set()
        for did in cfg.get("excluded_decks") or []:
            try:
                self.excluded.add(int(did))
            except (TypeError, ValueError):
                pass
        self.decks = QTreeWidget()
        self.decks.setHeaderHidden(True)
        self._fill_decks()
        since = None
        try:
            since = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
        except ValueError:
            pass
        self.since_on = QCheckBox("Leave out everything before")
        self.since_on.setChecked(since is not None)
        self.since = QDateEdit()
        self.since.setCalendarPopup(True)
        self.since.setDisplayFormat(DATE_FORMAT)
        self.since.setMaximumDate(QDate.currentDate())
        self.since.setDate(QDate(since.year, since.month, since.day) if since else QDate.currentDate())
        deck_box = QVBoxLayout(); deck_box.addWidget(self.decks); deck_box.addWidget(hint(DECKS_NOTE))
        sv = QVBoxLayout()
        since_row = QHBoxLayout(); since_row.addWidget(self.since_on); since_row.addWidget(self.since); since_row.addStretch(1)
        sv.addLayout(since_row); sv.addWidget(hint(SINCE_NOTE))
        self.keep_suspended = QCheckBox("Keep the trees of suspended cards")
        self.keep_suspended.setChecked(cfg.get("keep_suspended", True) not in OFF_VALUES)
        kv = QVBoxLayout(); kv.addWidget(self.keep_suspended); kv.addWidget(hint(SUSPENDED_NOTE))
        hv = QVBoxLayout(self)
        hv.addWidget(group("Decks", deck_box), 1)
        hv.addWidget(group("Suspended cards", kv))
        hv.addWidget(group("Start date", sv))

    def _fill_decks(self) -> None:
        """The deck tree, one checkbox a deck; filtered decks only borrow cards, so they
        are not in it."""
        items: dict = {}
        for deck in mw.col.decks.all_names_and_ids(include_filtered=False):
            parent, _sep, leaf = deck.name.rpartition("::")
            item = QTreeWidgetItem([leaf])
            item.setData(0, DECK_ROLE, deck.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            (items[parent] if parent in items else self.decks.invisibleRootItem()).addChild(item)
            items[deck.name] = item
        self._paint_decks()

    def _paint_decks(self) -> None:
        """Tick every deck that counts. Under an unticked one, its subdecks are unticked
        and greyed out, but each keeps its own choice for when the parent comes back."""
        def paint(item, parent_off: bool) -> None:
            off = parent_off or item.data(0, DECK_ROLE) in self.excluded
            item.setCheckState(0, Qt.CheckState.Unchecked if off else Qt.CheckState.Checked)
            item.setDisabled(parent_off)
            for i in range(item.childCount()):
                paint(item.child(i), off)
        self.decks.blockSignals(True)
        root = self.decks.invisibleRootItem()
        for i in range(root.childCount()):
            paint(root.child(i), False)
        self.decks.blockSignals(False)

    def connect(self, changed) -> None:
        def deck_toggled(item, _column) -> None:
            did = item.data(0, DECK_ROLE)
            if item.checkState(0) == Qt.CheckState.Checked:
                self.excluded.discard(did)
            else:
                self.excluded.add(did)
            self._paint_decks()
            changed()
        self.decks.itemChanged.connect(deck_toggled)
        self.since_on.toggled.connect(changed)
        self.keep_suspended.toggled.connect(changed)
        self.since.dateChanged.connect(changed)

    def sync(self) -> None:
        self.since.setEnabled(self.since_on.isChecked())

    def values(self) -> dict:
        return {
            # only decks that still exist, so a deleted one doesn't linger
            "excluded_decks": sorted(self.excluded & {d.id for d in mw.col.decks.all_names_and_ids(include_filtered=False)}),
            "ignore_before": self.since.date().toString("yyyy-MM-dd") if self.since_on.isChecked() else "",
            "keep_suspended": self.keep_suspended.isChecked(),
        }

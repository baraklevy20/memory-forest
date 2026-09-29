"""The History tab: which decks and days the forest grows from."""

from __future__ import annotations

import datetime as _dt

from aqt import mw
from aqt.qt import QCheckBox, QDate, QHBoxLayout, Qt, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..state import OFF_VALUES, phone_decks
from .widgets import date_field, group, hint

DECK_ROLE = Qt.ItemDataRole.UserRole
DATE_FORMAT = "d MMMM yyyy"
DECKS_NOTE = ("Unticked decks are left out of the forest. Tick them again anytime to bring them back. "
              "You can also leave a deck out from its ⚙ menu in the deck list.")
SINCE_NOTE = "The forest starts over from this day. Untick it anytime to bring the rest back."
SUSPENDED_NOTE = "They keep their tree's size, but no longer count against its health."


def _ids(cfg: dict) -> set:
    """The decks a config leaves out, however it was hand-edited."""
    out = set()
    for did in cfg.get("excluded_decks") or []:
        try:
            out.add(int(did))
        except (TypeError, ValueError):
            pass
    return out


class HistoryTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self.excluded = _ids(cfg)
        # what the config held when last read or written here: a deck left out from its gear
        # menu while the dialog is open changes it behind the dialog's back
        self.known = set(self.excluded)
        self.changed_outside = False
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
        self.since = date_field(DATE_FORMAT)
        self.since.setMaximumDate(QDate.currentDate())
        # ticked for the first time, it starts at the beginning of this month, not today,
        # which would leave only a seedling
        today = QDate.currentDate()
        self.since.setDate(QDate(since.year, since.month, since.day) if since else QDate(today.year(), today.month(), 1))
        deck_box = QVBoxLayout(); deck_box.addWidget(self.decks); deck_box.addWidget(hint(DECKS_NOTE))
        sv = QVBoxLayout()
        since_row = QHBoxLayout(); since_row.addWidget(self.since_on); since_row.addWidget(self.since); since_row.addStretch(1)
        sv.addLayout(since_row); sv.addWidget(hint(SINCE_NOTE))
        self.keep_suspended = QCheckBox("Suspended cards stay in their trees")
        self.keep_suspended.setChecked(cfg.get("keep_suspended", True) not in OFF_VALUES)
        kv = QVBoxLayout(); kv.addWidget(self.keep_suspended); kv.addWidget(hint(SUSPENDED_NOTE))
        hv = QVBoxLayout(self)
        hv.addWidget(group("Decks", deck_box), 1)
        hv.addWidget(group("Start date", sv))
        hv.addWidget(group("Suspended cards", kv))

    def _fill_decks(self) -> None:
        """The deck tree, one checkbox a deck; filtered decks only borrow cards, and the
        phone's deck holds the forest itself, so they are not in it."""
        items: dict = {}
        phone = phone_decks()
        self.items: dict = {}
        for deck in mw.col.decks.all_names_and_ids(include_filtered=False):
            if deck.id in phone:
                continue
            parent, _sep, leaf = deck.name.rpartition("::")
            item = QTreeWidgetItem([leaf if parent in items else deck.name])
            item.setData(0, DECK_ROLE, deck.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            (items[parent] if parent in items else self.decks.invisibleRootItem()).addChild(item)
            items[deck.name] = item
            self.items[deck.id] = item
        self._paint_decks()
        self._show_left_out()

    def _show_left_out(self) -> None:
        """Open the tree down to every deck left out, so none is hidden in a folded parent."""
        for did in self.excluded:
            item = self.items.get(did)
            parent = item.parent() if item is not None else None
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()

    def reload(self, cfg: dict) -> None:
        """Take in a deck left out or brought back from its gear menu since the config was
        last read here."""
        outside = _ids(cfg)
        if outside == self.known:
            return
        self.changed_outside = True
        # keep what was changed here and not saved yet
        self.excluded = (outside | (self.excluded - self.known)) - (self.known - self.excluded)
        self.known = outside
        self._paint_decks()
        self._show_left_out()

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

    def values(self, cfg: dict) -> dict:
        """What this tab saves, over `cfg`, the config as it is now."""
        self.reload(cfg)
        # only decks that still exist, so a deleted one doesn't linger
        excluded = self.excluded & {d.id for d in mw.col.decks.all_names_and_ids(include_filtered=False)}
        self.known = set(excluded)
        return {
            "excluded_decks": sorted(excluded),
            "ignore_before": self.since.date().toString("yyyy-MM-dd") if self.since_on.isChecked() else "",
            "keep_suspended": self.keep_suspended.isChecked(),
        }

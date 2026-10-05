"""The History tab: which decks and days the forest grows from."""

from __future__ import annotations

import datetime as _dt

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QDate,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPalette,
    Qt,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import study_log
from ..state import OFF_VALUES, day_cutoff, log, phone_cards, phone_decks
from .widgets import date_field, group, grow_window, hint

DECK_ROLE = Qt.ItemDataRole.UserRole
DATE_FORMAT = "d MMMM yyyy"
DECKS_NOTE = "Unticked decks grow no trees. You can also do this from a deck's ⚙ menu."
SINCE_NOTE = "Days before this are left out. Untick it to bring them back."
SINCE_OFF_NOTE = "Your forest starts on your first day of study, {first}."
SUSPENDED_NOTE = "They keep their tree's size but never hurt its health."
COUNTING = "Counting your trees…"
# with fewer decks than this, the list opens fully; with more, only down to the decks left out
UNFOLD_UNDER = 15
# room between the start date and the suspended cards, now they share a group
WHAT_COUNTS_GAP = 8


def _ids(cfg: dict) -> set:
    """The decks a config leaves out, however it was hand-edited."""
    out = set()
    for did in cfg.get("excluded_decks") or []:
        try:
            out.add(int(did))
        except (TypeError, ValueError):
            pass
    return out


def outside_moves(before: set, after: set, left_out: set, brought_back: set) -> tuple:
    """The decks left out and brought back from outside the dialog, `left_out` and
    `brought_back` so far, once the config has gone from `before` to `after` behind its back."""
    added, removed = after - before, before - after
    return (left_out | added) - removed, (brought_back | removed) - added


def undo_here(original: set, left_out: set, brought_back: set) -> set:
    """The decks left out as the dialog opened, with only the changes made outside it."""
    return (original - brought_back) | left_out


class HistoryTab(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self.excluded = _ids(cfg)
        # what the config held when last read or written here: a deck left out from its gear
        # menu while the dialog is open changes it behind the dialog's back
        self.known = set(self.excluded)
        # as the dialog opened, and what was changed behind its back since: Cancel undoes only
        # what was changed here
        self.original = set(self.excluded)
        self.left_out_outside: set = set()
        self.brought_back_outside: set = set()
        self.changed_outside = False
        # {home deck: {ago: has a card not suspended}}, once the collection has been read
        self.days: dict | None = None
        self.today = _dt.date.today()
        self.decks = QTreeWidget()
        self.decks.setHeaderHidden(True)
        # each deck's tree count sits on the right, in the second column
        self.decks.setColumnCount(2)
        header = self.decks.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._fill_decks()
        since = None
        try:
            since = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
        except ValueError:
            pass
        self.since_on = QCheckBox("Start the forest on")
        self.since_on.setChecked(since is not None)
        self.since = date_field(DATE_FORMAT)
        self.since.setMaximumDate(QDate.currentDate())
        # ticked for the first time, it starts at the beginning of this month, not today,
        # which would leave only a seedling
        today = QDate.currentDate()
        self.since.setDate(QDate(since.year, since.month, since.day) if since else QDate(today.year(), today.month(), 1))
        self.summary = QLabel(COUNTING)
        deck_box = QVBoxLayout(); deck_box.addWidget(self.decks); deck_box.addWidget(self.summary); deck_box.addWidget(hint(DECKS_NOTE))
        sv = QVBoxLayout()
        since_row = QHBoxLayout(); since_row.addWidget(self.since_on); since_row.addWidget(self.since); since_row.addStretch(1)
        self.since_hint = hint(SINCE_NOTE)
        sv.addLayout(since_row); sv.addWidget(self.since_hint)
        sv.addSpacing(WHAT_COUNTS_GAP)
        self.keep_suspended = QCheckBox("Keep suspended cards in their trees")
        self.keep_suspended.setChecked(cfg.get("keep_suspended", True) not in OFF_VALUES)
        sv.addWidget(self.keep_suspended); sv.addWidget(hint(SUSPENDED_NOTE))
        hv = QVBoxLayout(self)
        hv.addWidget(group("Decks", deck_box), 1)
        hv.addWidget(group("What counts", sv))
        # reading the collection can take a moment on a big one: after the dialog is up
        QTimer.singleShot(0, self._load_days)

    def _load_days(self) -> None:
        """Read every deck's trees, once; each count after that is done here in Python. If
        the collection can't be read, the counts are simply left out."""
        try:
            cutoff = day_cutoff(mw.col)
            days = study_log.load_tree_days(mw.col.db, cutoff, phone_cards())
            today = study_log.day_date(0, cutoff)
        except Exception as e:  # the counts are a nicety, never an error
            log(f"history: tree counts unavailable ({e!r})")
            self.summary.hide()
            return
        self.days, self.today = days, today
        self.recount()

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
        if len(self.items) < UNFOLD_UNDER:
            self.decks.expandAll()
        else:
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
        self.left_out_outside, self.brought_back_outside = outside_moves(
            self.known, outside, self.left_out_outside, self.brought_back_outside)
        # keep what was changed here and not saved yet
        self.excluded = (outside | (self.excluded - self.known)) - (self.known - self.excluded)
        self.known = outside
        self._paint_decks()
        self._show_left_out()
        self.recount()

    def cancelled(self) -> list:
        """The decks left out once Cancel undoes what was changed here (call reload first)."""
        return sorted(undo_here(self.original, self.left_out_outside, self.brought_back_outside))

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

    def _counted(self) -> set:
        """The decks that grow trees as the tab stands now: ticked, under a ticked parent."""
        return {did for did, item in self.items.items()
                if item.checkState(0) == Qt.CheckState.Checked and not item.isDisabled()}

    def recount(self) -> None:
        """Show each deck's trees, the whole forest's, and the day it starts on, for the
        decks, start date and suspended cards chosen here (before they are saved)."""
        if self.days is None:
            return
        days, counted = self.days, self._counted()
        since_ago = (self.today - self.since.date().toPyDate()).days if self.since_on.isChecked() else None
        suspended = self.keep_suspended.isChecked()

        dim = self.decks.palette().color(QPalette.ColorRole.PlaceholderText)
        self.decks.blockSignals(True)
        root = self.decks.invisibleRootItem()
        for i in range(root.childCount()):
            self._deck_trees(root.child(i), days, counted, since_ago, suspended, dim)
        self.decks.blockSignals(False)
        # a deck the list doesn't show (a card whose deck is gone) still grows trees, as in the
        # forest; the phone's deck never does
        growing = counted | (set(days) - set(self.items) - phone_decks())
        total = study_log.tree_days(days, growing, since_ago, suspended)
        everything = study_log.tree_days(days, growing, None, suspended)
        text = f"Your forest: <b>{_trees_text(len(total))}</b>"
        if len(everything) > len(total):
            text += f" &nbsp;({len(everything) - len(total):,} earlier ones left out)"
        self.summary.setText(text)
        self._show_first_day(max(everything) if everything else None)
        # the counts come in just after the dialog opens, and can make this tab taller
        grow_window(self)

    def _deck_trees(self, item, days: dict, counted: set, since_ago: int | None, suspended: bool, dim) -> set:
        """A deck's trees with those of its subdecks that count, written on its row. (A
        method, not a function nested in recount: one calling itself there held on to itself,
        and so to the whole collection's tree days, after every count.)"""
        did = item.data(0, DECK_ROLE)
        out = study_log.tree_days(days, [did], since_ago, suspended) if did in counted else set()
        for i in range(item.childCount()):
            out |= self._deck_trees(item.child(i), days, counted, since_ago, suspended, dim)
        if did not in counted:  # its subdecks may count, but it grows nothing itself
            out = set()
        item.setText(1, _trees_text(len(out)) if out else "no trees")
        item.setForeground(1, dim)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return out

    def _show_first_day(self, oldest: int | None) -> None:
        """Without a start date, say which day the forest starts on: the first one studied.
        The calendar goes no further back, but never moves a date already chosen."""
        if oldest is None:
            self.since_hint.setText(SINCE_NOTE)
            return
        first = self.today - _dt.timedelta(days=oldest)
        chosen = self.since.date().toPyDate()
        self.since.blockSignals(True)
        self.since.setMinimumDate(QDate(*(min(first, chosen) if self.since_on.isChecked() else first).timetuple()[:3]))
        self.since.blockSignals(False)
        self.since_hint.setText(SINCE_NOTE if self.since_on.isChecked() else
                                SINCE_OFF_NOTE.format(first=f"{first.day} {first:%B %Y}"))

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
        self.recount()

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


def _trees_text(n: int) -> str:
    return f"{n:,} tree{'' if n == 1 else 's'}"

"""Customize for Nature, on the Forest tab: what a level brings, changed. It takes the place of the
level tiles while open (a "Customize <level> ›" link under them opens it, "‹ Nature" goes back), as
the scenery's Customize does on the Scenery tab (SETTINGS_GUIDELINES.md).

Each of the bad habits' marks (crows, tall grass, tumbleweeds) is a box, with its numbers under it;
the level's own cost of a missed day (Wild's fire, Merciless's asteroid) has its numbers and no box:
picking another level is how to change it. The config keeps only what differs from the level
(`nature_custom`, events.custom_values), and picking a level starts again from its own."""

from __future__ import annotations

from aqt.qt import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QPalette, QPixmap, QSpinBox, Qt, QToolButton, QVBoxLayout, QWidget

from .. import events
from ..events import NATURE_LABELS, NUMBERS
from ..i18n import N_, t, tn, tx
from .customize import HEADER_GAP, RESET_GAP, RESET_STYLE
from .widgets import Link, hint

BACK = N_("settings.nature.back")
OWN_NOTE = N_("settings.customize.change_anything_here_to_make_it")  # (the scenery's Customize says it so too)
MIX_NOTE = N_("settings.nature.reset_a_row_to_put_the")
RESET_TIP = N_("settings.nature.reset_put_back_the_levels_own")
# the level's own cost of a missed day: its title, and a line for Peaceful, which has no numbers
COST_TITLES = {"peaceful": N_("settings.nature.ponds"), "wild": N_("settings.nature.fire"), "merciless": N_("settings.nature.asteroid")}
PONDS_NOTE = N_("settings.nature.a_week_or_more_away_leaves")
MARK_LABELS = {"crows": N_("settings.nature.crows_on_leeches"), "grass": N_("settings.nature.tall_grass"),
               "tumbleweeds": N_("settings.nature.tumbleweeds")}
# what brings each mark, under its box (the grass says it in its row)
MARK_NOTES = {"crows": N_("settings.nature.ankis_leech_threshold_in_deck_options"),
              "tumbleweeds": N_("settings.nature.when_overdue_reviews_pass_twice_a")}
# each number's row: the words before it, its unit (a plural, the number left out: Qt writes it), the
# words after it, and a hint under it
ROWS = {
    "strike_after": (N_("settings.nature.strikes_after"), "days", N_("settings.nature.without_reviews"),
                     N_("settings.nature.it_comes_closer_each_day_you")),
    "fire_from": (N_("settings.nature.breaks_out_after"), "days", N_("settings.nature.without_reviews"),
                  N_("settings.nature.smoke_rises_the_day_before_as")),
    "fire_heal": (N_("settings.nature.goes_out_after"), "study", None, None),
    "grass_after": (N_("settings.nature.after"), "days", N_("settings.nature.without_new_cards"), None),
}
COST_ROWS = {"peaceful": (), "wild": ("fire_from", "fire_heal"), "merciless": ("strike_after",)}
THUMB_W, THUMB_H = 48, 24  # a small copy of the level's tile (150 x 75)
INDENT = 26  # points: a mark's rows under its box, past the box itself
ROW_GAP, COLUMN_GAP, GROUP_GAP = 6, 8, 10


class Unit(QSpinBox):
    """A number of days: its unit after it, in the plural the number takes ("1 day", "3 days")."""

    def __init__(self, key: str, unit: str):
        super().__init__()
        _level, _own, lo, hi = NUMBERS[key]
        self.unit = unit
        self.setRange(lo, hi)
        self.valueChanged.connect(self._unit)
        self._unit(self.value())

    def _unit(self, n: int) -> None:
        self.setSuffix(" " + (tn("settings.nature.n_days_of_study", n) if self.unit == "study" else tn("settings.nature.n_days", n)))

    def room(self) -> int:
        """The width its longest text needs ("30 days of study"), with room for the arrows."""
        was = self.value()
        self.blockSignals(True)
        self.setValue(self.maximum())
        self._unit(self.maximum())
        need = self.sizeHint().width()
        self.setValue(was)
        self.blockSignals(False)
        self._unit(was)
        return need

    def set_quietly(self, n: int) -> None:
        self.blockSignals(True)
        self.setValue(n)
        self.blockSignals(False)
        self._unit(self.value())


class NaturePage(QWidget):
    def __init__(self, level: str, custom, on_back, stills: dict):
        super().__init__()
        self.level = events.nature_level(level)
        self.stills = stills  # each level's tile, still (its picture in the header)
        self._changed = None  # the dialog's, once connected
        self.back = Link(tx(BACK), on_back)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.title = QLabel()
        font = self.title.font(); font.setBold(True); self.title.setFont(font)
        header = QHBoxLayout()
        header.setSpacing(HEADER_GAP)
        header.addWidget(self.back)
        header.addWidget(self.thumb)
        header.addWidget(self.title, 1)
        self.note = hint("")

        # one grid, so every number lines up whichever rows show: [indent | words | number | words]
        grid = QGridLayout()
        grid.setHorizontalSpacing(COLUMN_GAP)
        grid.setVerticalSpacing(ROW_GAP)
        grid.setColumnMinimumWidth(0, INDENT - COLUMN_GAP)
        grid.setColumnStretch(4, 1)
        self.grid = grid
        self.spins, self.boxes, self.resets = {}, {}, {}
        self.rows = {}  # what shows only on its level: level -> widgets; a mark's: mark -> widgets under its box
        self._row = 0
        for lv in ("peaceful", "wild", "merciless"):
            title = QLabel(tx(COST_TITLES[lv]))
            font = title.font(); font.setBold(True); title.setFont(font)
            widgets = [self._line(title, lv)]
            if lv == "peaceful":
                widgets.append(self._hint(tx(PONDS_NOTE)))
            for key in COST_ROWS[lv]:
                widgets += self._number(key)
            self.rows[lv] = widgets
        for mark in events.MARKS:
            box = QCheckBox(tx(MARK_LABELS[mark]))
            box.toggled.connect(lambda _on: self._changed and self._changed())
            self.boxes[mark] = box
            self._gap()
            self._line(box, mark)
            under = []
            if mark in MARK_NOTES:
                under.append(self._hint(tx(MARK_NOTES[mark])))
            if mark == "grass":
                under += self._number("grass_after")
            self.rows[mark] = under

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(header)
        v.addWidget(self.note)
        v.addSpacing(GROUP_GAP - ROW_GAP)
        v.addLayout(grid)
        v.addStretch(1)
        self.set_custom(custom)
        # every number as wide as the widest it can be, so they line up and none is cramped
        width = max(spin.room() for spin in self.spins.values())
        for spin in self.spins.values():
            spin.setMinimumWidth(width)

    # ---------- building ----------

    def _reset(self, key: str) -> QToolButton:
        """A quiet ↺ beside a row while it differs from the level's own, keeping its room hidden."""
        reset = QToolButton()
        reset.setText("↺")
        reset.setToolTip(tx(RESET_TIP))
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        pal = reset.palette()
        reset.setStyleSheet(RESET_STYLE.format(quiet=pal.color(QPalette.ColorRole.PlaceholderText).name(),
                                               accent=pal.color(QPalette.ColorRole.Highlight).name()))
        policy = reset.sizePolicy(); policy.setRetainSizeWhenHidden(True); reset.setSizePolicy(policy)
        reset.setVisible(False)
        reset.clicked.connect(lambda _checked=False, k=key: self.reset(k))
        self.resets[key] = reset
        return reset

    def _line(self, widget, key: str) -> QWidget:
        """A title or a mark's box across the grid, its ↺ beside it."""
        line = QWidget()
        row = QHBoxLayout(line)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(RESET_GAP)
        row.addWidget(widget)
        row.addWidget(self._reset(key))
        row.addStretch(1)
        self.grid.addWidget(line, self._row, 0, 1, 5)
        self._row += 1
        return line

    def _hint(self, text: str) -> QLabel:
        label = hint(text)
        self.grid.addWidget(label, self._row, 1, 1, 4)
        self._row += 1
        return label

    def _gap(self) -> None:
        if self._row:
            self.grid.setRowMinimumHeight(self._row, GROUP_GAP - ROW_GAP)
            self._row += 1

    def _number(self, key: str) -> list:
        before, unit, after, note = ROWS[key]
        spin = Unit(key, unit)
        spin.valueChanged.connect(lambda _n: self._changed and self._changed())
        self.spins[key] = spin
        out = [QLabel(tx(before)), spin]
        self.grid.addWidget(out[0], self._row, 1)
        self.grid.addWidget(spin, self._row, 2)
        if after:
            out.append(QLabel(tx(after)))
            self.grid.addWidget(out[-1], self._row, 3)
        self._row += 1
        if note:
            out.append(self._hint(tx(note)))
        return out

    # ---------- the values ----------

    def own(self) -> dict:
        return events.own_rules(self.level)

    def rules(self) -> dict:
        """The level as the page has it now."""
        out = {m: b.isChecked() for m, b in self.boxes.items()}
        out.update({k: s.value() for k, s in self.spins.items()})
        return out

    def custom(self) -> dict:
        """What the config keeps: only what differs from the level's own (and that the level uses)."""
        return events.custom_values(self.level, self.rules())

    def set_custom(self, custom) -> None:
        """Show the level with `custom` (the config's `nature_custom`) on top, announcing nothing."""
        r = events.rules(self.level, custom)
        for m, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(r[m])
            box.blockSignals(False)
        for k, spin in self.spins.items():
            spin.set_quietly(r[k])
        self.sync()

    def set_level(self, level: str) -> None:
        """A level picked: that level, with its own marks and numbers (as a scenery tile picks the
        scenery's own five)."""
        self.level = events.nature_level(level)
        self.set_custom({})

    def reset(self, key: str) -> None:
        """Put a row back as the level has it: a mark's box and its numbers, or the level's cost."""
        keys = [key] if key in self.boxes else []
        keys += ["grass_after"] if key == "grass" else list(COST_ROWS.get(key, ()))
        self.set_custom({k: v for k, v in self.custom().items() if k not in keys})
        if self._changed:
            self._changed()

    def link_text(self) -> str:
        """The way here under the tiles, naming the level, or a mix made from it."""
        name = tx(NATURE_LABELS[self.level])
        if self.custom():
            return t("settings.nature.customize_your_own_mix_from_level", level=name)
        return t("settings.nature.customize_level", level=name)

    def sync(self) -> None:
        """The header, the note, the rows the level shows, what is greyed out and the ↺s, for the
        values as they are."""
        name, custom = tx(NATURE_LABELS[self.level]), self.custom()
        self.title.setText(t("settings.nature.customize_your_own_mix_from_level_2", level=name) if custom
                           else t("settings.nature.customize_level_2", level=name))
        self.note.setText(tx(MIX_NOTE if custom else OWN_NOTE))
        for lv in COST_ROWS:
            for w in self.rows[lv]:
                w.setVisible(lv == self.level)
        for m in events.MARKS:  # (an unticked mark's numbers stay, greyed: SETTINGS_GUIDELINES.md)
            for w in self.rows[m]:
                w.setEnabled(self.boxes[m].isChecked())
        for key, reset in self.resets.items():
            changed = [key] if key in custom else []
            changed += [k for k in (["grass_after"] if key == "grass" else COST_ROWS.get(key, ())) if k in custom]
            reset.setVisible(bool(changed))
        still = self.stills.get(self.level)
        if isinstance(still, QPixmap) and not still.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            small = still.scaled(round(THUMB_W * dpr), round(THUMB_H * dpr), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            small.setDevicePixelRatio(dpr)
            self.thumb.setPixmap(small)

    def connect(self, changed) -> None:
        self._changed = changed

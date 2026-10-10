"""The Forest tab: how the forest behaves and where it shows - Nature, the screens it is on,
motion and the planting message, and the forest on your phone."""

from __future__ import annotations

import os

from aqt.qt import (
    QCheckBox,
    QIcon,
    QPushButton,
    QRect,
    QSize,
    QSizePolicy,
    QSpinBox,
    Qt,
    QVBoxLayout,
)

from ..events import DEFAULT_NATURE, NATURE_LABELS, NATURE_NOTES, NATURE_SWITCH_NOTE, calm, nature_level
from ..phone_note import phone_on
from ..state import ANIMATION_VALUES, MAX_WIDTH_DEFAULT, MAX_WIDTH_MAX, MAX_WIDTH_MIN, animation_mode, shows_on_deck_list
from .palette import color
from .scenery_picker import crisp
from .widgets import Choice, Tab, form, group, hint

NATURE_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nature")
NATURE_ICON = 16  # points: the icons' own pixels, one a point
NATURE_GAP = 8
NATURE_STYLE = """
QPushButton {{ border: 1px solid {line}; border-radius: 7px; padding: 6px 10px; font-size: 13px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ border: 2px solid {ring}; padding: 5px 9px; background: rgba(128, 128, 128, 0.16); font-weight: bold; }}
"""
PHONE_NOTE = 'Adds a "Memory Forest" deck with one card that shows your forest. It updates when you sync. Untick to remove it.'
ANIMATION_OPTIONS = [("on", "On"), ("off", "Off"), ("system", "Follow system")]
# where the forest shows: the same "No forest" in both, so the two rows read alike
MAIN_OPTIONS = [(True, "Your forest"), (False, "No forest")]
DECK_OPTIONS = [("highlight", "Your forest, that deck's trees lit up"), ("own", "A forest of that deck's own"), ("off", "No forest")]
WIDTH_STEP = 50
WIDTH_BOX_W = 110


class NatureChoice(Choice):
    """The three Nature levels side by side, each with its icon (drawn by dev/nature_icons.py),
    the chosen one ringed as a focused field is in Anki."""

    def __init__(self, level: str):
        super().__init__(list(NATURE_LABELS.items()), level, DEFAULT_NATURE, gap=NATURE_GAP, stretch=False)

    def make_button(self, key, label: str):
        b = QPushButton(QIcon(crisp(os.path.join(NATURE_ICONS, f"{key}.png"))), f" {label}")
        b.setIconSize(QSize(NATURE_ICON, NATURE_ICON))
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b.setStyleSheet(NATURE_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS")))
        return b


class ForestTab(Tab):
    def __init__(self, cfg: dict, on_phone, phone_was: bool | None = None):
        super().__init__()
        self.on_phone = on_phone  # makes or takes away the phone's deck (actions.phone_switched)
        self.nature = NatureChoice(nature_level(cfg.get("nature")))
        self.nature_note = hint("")
        self.nature_note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (its room fits the longest level)
        self.main_forest = Choice(MAIN_OPTIONS, shows_on_deck_list(cfg), True)
        self.deck_mode = Choice(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight", vertical=True)
        self.max_width = QSpinBox(); self.max_width.setRange(MAX_WIDTH_MIN, MAX_WIDTH_MAX); self.max_width.setSingleStep(WIDTH_STEP); self.max_width.setSuffix(" px")
        self.max_width.setMaximumWidth(WIDTH_BOX_W)
        try:
            self.max_width.setValue(int(cfg.get("max_width", MAX_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            self.max_width.setValue(MAX_WIDTH_DEFAULT)
        # On, Off, or Follow system (still while the system asks for reduced motion)
        self.animations = Choice(ANIMATION_OPTIONS, animation_mode(cfg), "on")
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        self.phone = QCheckBox("Show my forest on my phone")
        # not the add-on config's: whether the collection holds the note that takes the forest
        # to your phone (phone.py), made or taken away as it is ticked, and put back on Cancel -
        # as it was when the first of the dialogs opened, after Restore defaults reopened it
        self.phone_was = phone_on() if phone_was is None else phone_was
        self.phone.setChecked(phone_on())
        self.phone.toggled.connect(self.on_phone)

        nv = QVBoxLayout()
        nv.addWidget(self.nature)
        nv.addWidget(self.nature_note)
        where = form()
        where.addRow("Main screen", self.main_forest)
        where.addRow("Deck screens", self.deck_mode)
        where.addRow("Forest width", self.max_width)
        motion = QVBoxLayout()
        animate = form()
        animate.addRow("Animate the forest", self.animations)
        motion.addLayout(animate)
        motion.addWidget(self.planting)
        pv = QVBoxLayout()
        pv.addWidget(self.phone)
        pv.addWidget(hint(PHONE_NOTE))
        v = QVBoxLayout(self)
        self.nature_group = group("Nature", nv)
        v.addWidget(self.nature_group)
        v.addWidget(group("Where it shows", where))
        v.addWidget(group("Motion and messages", motion))
        v.addWidget(group("On your phone", pv))
        v.addStretch(1)

    def put_phone_back(self) -> None:
        """Cancel puts the phone setting back as the dialog found it, as it does the add-on
        config."""
        if phone_on() != self.phone_was:
            self.on_phone(self.phone_was)

    def news_targets(self) -> dict:
        """The settings here a note can point at (news.py): key -> (widget, name)."""
        return {"nature": (self.nature_group.title, "Nature"), "main_forest": (self.main_forest, "Main screen"),
                "deck_forest_mode": (self.deck_mode, "Deck screens"), "max_width": (self.max_width, "Forest width"),
                "animations": (self.animations, "Animate the forest"), "planting_tooltip": (self.planting, "The planting message"),
                "phone": (self.phone, "Your forest on your phone")}

    def connect(self, changed) -> None:
        for choice in (self.animations, self.main_forest, self.deck_mode):
            choice.on_change(changed)
        self.max_width.valueChanged.connect(changed)
        for box in (self.planting, self.phone):
            box.toggled.connect(changed)
        self.nature.on_change(changed)

    def sync(self) -> None:
        level = self.nature.currentData()
        note = NATURE_NOTES.get(level, "")
        self.nature_note.setText(note if calm(level) else f"{note} {NATURE_SWITCH_NOTE}")
        self.fit()

    def fit(self) -> None:
        """Nature's line asks for room for its longest level from the start, so picking another
        never makes the dialog grow."""
        width = self.nature_note.width()
        if width > 0:
            metrics = self.nature_note.fontMetrics()
            texts = [n if calm(k) else f"{n} {NATURE_SWITCH_NOTE}" for k, n in NATURE_NOTES.items()]
            tallest = max(metrics.boundingRect(QRect(0, 0, width, 10000), Qt.TextFlag.TextWordWrap, t).height() for t in texts)
            self.nature_note.setMinimumHeight(tallest)
        super().fit()

    def values(self) -> dict:
        return {
            "animations": ANIMATION_VALUES[self.animations.currentData()],
            "planting_tooltip": self.planting.isChecked(),
            "nature": self.nature.currentData(),
            "main_forest": self.main_forest.currentData(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "max_width": self.max_width.value(),
        }

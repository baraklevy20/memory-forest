"""The Forest tab: how the forest behaves and where it shows - Nature, the screens it is on,
motion and the planting message, and the forest on your phone. The heatmap under it has a tab
of its own (heatmap_tab.py)."""

from __future__ import annotations

import os

from aqt import mw
from aqt.qt import (
    QAbstractButton,
    QCheckBox,
    QColor,
    QEvent,
    QFont,
    QHBoxLayout,
    QLabel,
    QLinearGradient,
    QMovie,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRect,
    QRectF,
    QSize,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..events import DEFAULT_NATURE, NATURE_LABELS, NATURE_NOTES, NATURE_SWITCH_NOTE, calm, nature_level
from ..phone_note import phone_on
from ..state import (
    ANIMATION_VALUES,
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    animation_mode,
    shows_on_deck_list,
    shows_on_finished,
)
from .palette import color
from .scenery_picker import NAME_FONT, NAME_PAD, RING, TILE_RADIUS
from .widgets import Choice, Tab, form, group, hint

NATURE_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nature")
# Nature's levels as picture tiles, each what that level does to a forest over the days: the real
# engine on a made-up forest (dev/nature_gifs.py, npm run nature-gifs), a pixel a point, with the
# level's name on it as a scenery tile has its own (SETTINGS_GUIDELINES.md: Decided)
NATURE_GIF_W, NATURE_GIF_H = 150, 75
NATURE_TILE_GAP = 16
# the shade under a tile's name: its share of the picture's height, and how dark at the foot
# (lighter than a scenery tile's: the crater and the pond lie near the foot)
NATURE_SHADE_H, NATURE_SHADE_ALPHA = 0.4, 150
# while a tile is still (not chosen, or the forest is still: Animate the forest Off, or Follow
# system with Anki's Reduce motion on), the moment that tells the most, in ms from the start:
# the fire at its height, the crater, the pond
NATURE_STILL_MS = {"peaceful": 8000, "wild": 4800, "merciless": 4600}
# what "On finished decks too" covers: both, so it is never greyed out by the Heatmap tab's deck screens
# (SETTINGS_GUIDELINES.md: one tab's control never changes another's)
FINISHED_NOTE = "Covers the forest and the heatmap."
# (one line: SETTINGS_GUIDELINES.md)
PHONE_NOTE = 'Adds a "Memory Forest" deck with a card showing your forest and heatmap as you sync.'
ANIMATION_OPTIONS = [("on", "On"), ("off", "Off"), ("system", "Follow system")]
# where the forest shows: the same "No forest" in both, so the two rows read alike
MAIN_OPTIONS = [(True, "Your forest"), (False, "No forest")]
DECK_OPTIONS = [("highlight", "Your forest, that deck's trees lit up"), ("own", "A forest of that deck's own"), ("off", "No forest")]
# points between two fields sharing a row (the deck screens' forest and "On finished decks too",
# the heatmap's two screens), so the tab grows no taller (SETTINGS_GUIDELINES.md)
CALENDAR_GAP = 24
WIDTH_STEP = 50
WIDTH_BOX_W = 110


def reduce_motion() -> bool:
    """Whether Anki asks for less motion (its Reduce motion preference; older Anki has none)."""
    ask = getattr(getattr(mw, "pm", None), "reduce_motion", None)
    try:
        return bool(ask()) if callable(ask) else False
    except Exception:  # (a profile not loaded yet)
        return False


def nature_moves(mode: str) -> bool:
    """Whether the chosen level's picture moves, for Animate the forest's `mode`."""
    return mode == "on" or (mode == "system" and not reduce_motion())


class NatureTile(QAbstractButton):
    """One Nature level: its picture, moving while chosen and the forest is animated (and the tile
    can be seen), else still at NATURE_STILL_MS, with the level's name on it; the chosen one ringed.
    Only the frame on show is kept, as the scenery tiles do."""

    def __init__(self, key: str, label: str):
        super().__init__()
        self.key, self.label = key, label
        self.movie = QMovie(os.path.join(NATURE_ICONS, f"{key}.gif"), parent=self)
        self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
        self.still = self._frame_at(NATURE_STILL_MS.get(key, 0))
        self.movie.frameChanged.connect(lambda _n: self.update())
        self.moving = True
        self.setCheckable(True)  # (Qt's own nextCheckState: the group keeps one chosen, SETTINGS_GUIDELINES.md)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(label)
        font = self.font()
        font.setPixelSize(NAME_FONT)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.toggled.connect(lambda _on: self._play())

    def _frame_at(self, ms: int) -> QPixmap:
        """The movie's frame at `ms` from its start (QMovie seeks only by frame)."""
        m, at = self.movie, 0
        if not m.isValid():
            return QPixmap()
        m.jumpToFrame(0)
        for i in range(max(1, m.frameCount())):
            if i and not m.jumpToFrame(i):
                break
            at += max(0, m.nextFrameDelay())
            if at > ms:
                break
        frame = QPixmap(m.currentPixmap())
        m.jumpToFrame(0)
        return frame

    def set_moving(self, moving: bool) -> None:
        self.moving = moving
        self._play()

    def playing(self) -> bool:
        return self.movie.state() == QMovie.MovieState.Running

    def _play(self) -> None:
        if self.isChecked() and self.moving and self.isVisible():
            if not self.playing():
                self.movie.start()
        elif self.playing():
            self.movie.stop()
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._play()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.movie.stop()

    def keyPressEvent(self, event) -> None:
        """Enter picks the tile with the focus, as Space does (as on a scenery tile)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            return
        super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(NATURE_GIF_W + 2 * RING, NATURE_GIF_H + 2 * RING)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(RING, RING, NATURE_GIF_W, NATURE_GIF_H)
        path = QPainterPath()
        path.addRoundedRect(frame, TILE_RADIUS, TILE_RADIUS)
        p.save()
        p.setClipPath(path)
        # a pixel a point, so no smoothing comes into it (the frames are the engine's own pixels)
        p.drawPixmap(frame, self.movie.currentPixmap() if self.playing() else self.still, QRectF(0, 0, NATURE_GIF_W, NATURE_GIF_H))
        # the name, white on a shade that darkens toward the foot, as on a scenery tile
        top = frame.bottom() - NATURE_GIF_H * NATURE_SHADE_H
        shade = QLinearGradient(0, top, 0, frame.bottom())
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, NATURE_SHADE_ALPHA))
        p.fillRect(QRectF(frame.left(), top, NATURE_GIF_W, frame.bottom() - top), shade)
        name_h = self.fontMetrics().height()
        name = QRectF(frame.left() + NAME_PAD, frame.bottom() - NAME_PAD + 2 - name_h, NATURE_GIF_W - 2 * NAME_PAD, name_h)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(name.translated(0, 1), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)
        p.setPen(QColor("white"))
        p.drawText(name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)
        p.restore()
        # the chosen one ringed in the theme's focus blue; the one with the focus, if another, thinly
        if self.isChecked() or self.hasFocus():
            pen = QPen(QColor(color("BORDER_FOCUS")) if self.isChecked() else self.palette().color(QPalette.ColorRole.Mid))
            pen.setWidthF(RING if self.isChecked() else 1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            edge = RING / 2 if self.isChecked() else 0.75
            p.drawRoundedRect(frame.adjusted(-edge, -edge, edge, edge), TILE_RADIUS + edge, TILE_RADIUS + edge)
        p.end()


class NatureTiles(Choice):
    """The three Nature levels as picture tiles side by side: one choice, one Tab stop (the chosen
    tile) and the arrow keys from one tile to the next, as widgets.JoinedChoice has."""

    def __init__(self, level: str):
        super().__init__(list(NATURE_LABELS.items()), level, DEFAULT_NATURE, gap=NATURE_TILE_GAP, stretch=True)
        for b in self.buttons.values():
            b.installEventFilter(self)
        self.group.buttonToggled.connect(lambda _b, _on: self._tab_stop())
        self._tab_stop()

    def make_button(self, key, label: str):
        return NatureTile(key, label)

    def _tab_stop(self) -> None:
        for b in self.buttons.values():
            b.setFocusPolicy(Qt.FocusPolicy.StrongFocus if b.isChecked() else Qt.FocusPolicy.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            keys = list(self.buttons)
            at = keys.index(self.currentData()) + (1 if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down) else -1)
            if 0 <= at < len(keys):
                self.buttons[keys[at]].setChecked(True)
                self.buttons[keys[at]].setFocus()
            return True
        return False

    def set_moving(self, moving: bool) -> None:
        for t in self.buttons.values():
            t.set_moving(moving)


def beside(first, *rest, top: bool = False) -> QHBoxLayout:
    """A row's field with more after it, CALENDAR_GAP on: centred on the row, or along its top
    line (`top`) beside a choice of several lines."""
    row, align = QHBoxLayout(), Qt.AlignmentFlag.AlignTop if top else Qt.AlignmentFlag.AlignVCenter
    row.addWidget(first, 0, align)
    row.addSpacing(CALENDAR_GAP)
    for w in rest:
        row.addWidget(w, 0, align)
    row.addStretch(1)
    return row


class ForestTab(Tab):
    def __init__(self, cfg: dict, on_phone, phone_was: bool | None = None):
        super().__init__()
        self.on_phone = on_phone  # makes or takes away the phone's deck (actions.phone_switched)
        self.nature = NatureTiles(nature_level(cfg.get("nature")))
        # what the chosen level does, under the tiles in the dialog's own text size: a hint's small
        # grey under pictures this loud reads as a footnote (SETTINGS_GUIDELINES.md: Decided)
        self.nature_note = QLabel("")
        self.nature_note.setWordWrap(True)
        self.nature_note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)  # (its room fits the longest level)
        self.nature_note.installEventFilter(self)
        self.main_forest = Choice(MAIN_OPTIONS, shows_on_deck_list(cfg), True)
        self.deck_mode = Choice(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight", vertical=True)
        # the deck screens' forest and heatmap on a deck you have finished too (Anki's
        # congratulations page), beside their choice
        self.finished = QCheckBox("On finished decks too")
        self.finished.setChecked(shows_on_finished(cfg))
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

        # the levels as picture tiles, what the chosen one does under them
        nv = QVBoxLayout()
        nv.addWidget(self.nature)
        nv.addWidget(self.nature_note)
        where = form()
        where.addRow("Main screen", self.main_forest)
        finished = QWidget()  # (the box with its hint just under it, as heatmap_tab.with_hint has them)
        fv = QVBoxLayout(finished)
        fv.setContentsMargins(0, 0, 0, 0)
        fv.setSpacing(4)
        fv.addWidget(self.finished)
        note = hint(FINISHED_NOTE)
        note.setWordWrap(False)  # (one short line: wrapped, it took the box's width and broke in two)
        fv.addWidget(note)
        where.addRow("Deck screens", beside(self.deck_mode, finished, top=True))
        where.addRow("Forest width", self.max_width)
        motion = QVBoxLayout()
        animate = form()
        # (the planting message beside it, on one row: room for Nature's moving picture)
        animate.addRow("Animate the forest", beside(self.animations, self.planting))
        motion.addLayout(animate)
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
                "deck_forest_mode": (self.deck_mode, "Deck screens"), "finished_decks": (self.finished, "On finished decks too"),
                "max_width": (self.max_width, "Forest width"),
                "animations": (self.animations, "Animate the forest"), "planting_tooltip": (self.planting, "The planting message"),
                "phone": (self.phone, "Your forest on your phone")}

    def connect(self, changed) -> None:
        for choice in (self.animations, self.main_forest, self.deck_mode):
            choice.on_change(changed)
        self.max_width.valueChanged.connect(changed)
        for box in (self.planting, self.phone, self.finished):
            box.toggled.connect(changed)
        self.nature.on_change(changed)

    def sync(self) -> None:
        level = self.nature.currentData()
        note = NATURE_NOTES.get(level, "")
        self.nature_note.setText(note if calm(level) else f"{note} {NATURE_SWITCH_NOTE}")
        self.nature.set_moving(nature_moves(self.animations.currentData()))
        self.fit()

    def fit(self) -> None:
        self._note_room()
        super().fit()

    def _note_room(self) -> None:
        """Nature's words ask for room for the longest level's at their width, so picking another
        never makes the dialog grow - measured again as they are laid out wider or narrower (the
        tab's own resize comes before theirs, so its width there is the last one's)."""
        width = self.nature_note.width()
        if width > 0:
            metrics = self.nature_note.fontMetrics()
            texts = [n if calm(k) else f"{n} {NATURE_SWITCH_NOTE}" for k, n in NATURE_NOTES.items()]
            tallest = max(metrics.boundingRect(QRect(0, 0, width, 10000), Qt.TextFlag.TextWordWrap, t).height() for t in texts)
            if tallest != self.nature_note.minimumHeight():
                self.nature_note.setMinimumHeight(tallest)

    def eventFilter(self, obj, event):
        if obj is self.nature_note and event.type() == QEvent.Type.Resize:
            self._note_room()
        return False

    def values(self) -> dict:
        return {
            "animations": ANIMATION_VALUES[self.animations.currentData()],
            "planting_tooltip": self.planting.isChecked(),
            "nature": self.nature.currentData(),
            "main_forest": self.main_forest.currentData(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "finished_decks": self.finished.isChecked(),
            "max_width": self.max_width.value(),
        }

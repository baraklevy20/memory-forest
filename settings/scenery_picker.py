"""The scenery picker: what the Scenery box opens instead of a dropdown list, since a list
of pictures big enough to read runs off the screen. Tiles, as many to a row as fit, in
sections, with a search once there are many. Clicking a tile picks it and closes the picker,
as choosing from a list would; Esc closes it with nothing changed."""

from __future__ import annotations

import os

from aqt.qt import (
    QAbstractButton,
    QColor,
    QComboBox,
    QDialog,
    QEasingCurve,
    QFont,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QGuiApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPoint,
    QPointF,
    QPushButton,
    QRect,
    QRectF,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QTextLayout,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager

from .. import presets
from .palette import color
from .widgets import hint

# each preset's picture, drawn by dev/thumbnails.py: a piece of its scene in the scene's own
# pixels, shown a pixel a point in the picker
PICTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenery")
PICTURE_W, PICTURE_H = 192, 108
SEARCH_FROM = 12  # tiles before the picker offers a search
SEARCH_W = 220
COLUMNS = 4
MAX_H = 720  # points the picker may grow to before it scrolls (less on a screen without the room)
MIN_H = 240  # ... and never less than this, however small the screen says it is
TITLE_BAR_ROOM = 48  # points kept free on the screen for the picker's title bar and edges
COLUMN_GAP, ROW_GAP = 16, 10
MARGIN = 20  # points round the picker's edge
SECTION_GAP = 14  # points above a section's title, after the first
TAG_FONT, TAG_PAD = 10, 4  # the "Until" label on a holiday's tile, in points
# the Scenery card: the chosen scenery's small picture (dev/thumbnails.py, a pixel a point),
# then its name and what it is, with "Change…" in the top right corner; all of it opens the picker
CARD_PICTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenery_small")
CARD_PIC_W, CARD_PIC_H = 96, 54
CARD_PAD, CARD_GAP = 8, 12  # points round the card's edge, and between the picture and the words
CARD_H = CARD_PIC_H + 2 * CARD_PAD
CARD_RADIUS, CARD_PIC_RADIUS = 10, 6
CARD_NAME_FONT, CARD_CHANGE_FONT, CARD_NOTE_FONT = 14, 13, 11
CARD_LINE, CARD_NOTE_GAP = 18, 4  # the name's line, and the room under it before the description
CUSTOM_NOTE = "Your own mix from Fine-tuning. Pick a scenery to start again from it."
# how far its fill stands off the window's colour (as QColor.lighter/darker take it), and more under the pointer
CARD_LIFT_DARK, CARD_LIFT_LIGHT, CARD_HOVER = 160, 104, 110
# the keys that open the picker from the Scenery card, and those a dropdown would step or jump
# through its list with, which do nothing there (letters jump too, unless Ctrl or Cmd is down)
OPEN_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_F4)
STEP_KEYS = (Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)
JUMP_KEEPS = (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.MetaModifier, Qt.KeyboardModifier.AltModifier)
# Surprise me daily's tile: these four, in quarters
DAILY_MOSAIC = ("aurora", "synthwave", "lanterns", "bamboo")

# A tile: the picture with rounded corners and its name under it, lifting a little under the
# pointer; the chosen one ringed in the theme's focus blue, with a tick in its corner.
TILE_RADIUS = 8
RING = 3  # the chosen tile's ring, and the room left round every picture for it
LIFT, LIFT_MS = 3, 140  # how far a tile rises under the pointer, and how quickly
NAME_GAP, NAME_FONT = 6, 13
BADGE = 20  # the tick's circle, across
SECTION_STYLE = "font-size: 12px; font-weight: bold;"
TITLE_STYLE = "font-size: 15px; font-weight: bold;"
SEARCH_STYLE = """
QLineEdit {{ border: 1px solid {line}; border-radius: 7px; padding: 5px 10px; background: {ground}; font-size: 13px; }}
QLineEdit:focus {{ border-color: {focus}; }}
"""


def _pixel_ratio() -> float:
    screen = QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


def crisp(path: str) -> QPixmap:
    """A pixel-art picture, scaled up in whole pixels for the screen so the art stays sharp
    at a pixel a point; a null pixmap if there is none."""
    return _whole_pixels(QPixmap(path))


def _whole_pixels(raw: QPixmap) -> QPixmap:
    if raw.isNull():
        return raw
    dpr = max(1, round(_pixel_ratio()))
    big = raw.scaled(raw.width() * dpr, raw.height() * dpr, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    big.setDevicePixelRatio(dpr)
    return big


def picture(key: str) -> QPixmap:
    """A preset's picture, or a null pixmap if it has none."""
    return crisp(os.path.join(PICTURES, f"{key}.png"))


def mosaic() -> QPixmap:
    """Surprise me daily's picture: four sceneries it takes turns with, a quarter each."""
    dpr = max(1, round(_pixel_ratio()))
    out = QPixmap(PICTURE_W * dpr, PICTURE_H * dpr)
    out.fill(QColor(0, 0, 0, 0))
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    w, h = PICTURE_W * dpr // 2, PICTURE_H * dpr // 2
    shown = [k for k in DAILY_MOSAIC if k in presets.by_key()]
    for i, key in enumerate(shown[:4]):
        raw = QPixmap(os.path.join(PICTURES, f"{key}.png"))
        if not raw.isNull():
            p.drawPixmap(QRect((i % 2) * w, (i // 2) * h, w, h), raw)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out


def card_picture(key: str) -> QPixmap:
    """A preset's small picture for the Scenery card, or a null pixmap if it has none. Surprise
    me daily's is a mosaic as its tile is: the middle quarter of each of the four, uncut pixels."""
    if key != presets.DAILY:
        return crisp(os.path.join(CARD_PICTURES, f"{key}.png"))
    out = QPixmap(CARD_PIC_W, CARD_PIC_H)
    out.fill(QColor(0, 0, 0, 0))
    p = QPainter(out)
    w, h = CARD_PIC_W // 2, CARD_PIC_H // 2
    shown = [k for k in DAILY_MOSAIC if k in presets.by_key()]
    for i, k in enumerate(shown[:4]):
        p.drawPixmap(QPoint((i % 2) * w, (i // 2) * h), QPixmap(os.path.join(CARD_PICTURES, f"{k}.png")),
                     QRect(w // 2, h // 2, w, h))
    p.end()
    return _whole_pixels(out)


def two_lines(text: str, font: QFont, width: int) -> list:
    """`text` wrapped at `width`, the second line cut short with … if it runs on."""
    fm = QFontMetrics(font)
    layout = QTextLayout(text, font)
    layout.beginLayout()
    first = layout.createLine()
    first.setLineWidth(width)
    layout.endLayout()
    end = first.textStart() + first.textLength()
    rest = text[end:].strip()
    lines = [text[:end].strip()]
    if rest:
        lines.append(fm.elidedText(rest, Qt.TextElideMode.ElideRight, width))
    return lines


def tagged(pix: QPixmap, text: str) -> QPixmap:
    """`pix` with a small dark label in its bottom left corner. (A painter on a high-density
    pixmap works in points, as the picture is shown.)"""
    out = QPixmap(pix)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont()
    font.setPixelSize(TAG_FONT)
    font.setBold(True)
    p.setFont(font)
    box = p.fontMetrics().boundingRect(text).adjusted(-TAG_PAD, -TAG_PAD // 2, TAG_PAD, TAG_PAD // 2)
    box.moveBottomLeft(QPoint(TAG_PAD * 2, PICTURE_H - TAG_PAD * 2))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 190))
    p.drawRoundedRect(box, TAG_PAD, TAG_PAD)
    p.setPen(QColor("white"))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return out


def last_day(preset, day) -> str:
    end = presets.season_ends(preset, day)
    last = end.fromordinal(end.toordinal() - 1)
    return f"{last.day} {last.strftime('%b')}"


# The mix badge on Custom's picture: three sliders, set at different heights, drawn in pixels
# BADGE_PX points across on a dark rounded square, BADGE_INSET from the picture's corner.
BADGE_ART = (  # three sliders: K a knob, | its track
    ".|..K..|.",
    ".|.KKK.|.",
    ".|.KKK.|.",
    ".|..|.KKK",
    "KKK.|.KKK",
    "KKK.|..|.",
    ".|..|..|.",
    ".|..|..|.",
    ".|..|..|.",
)
BADGE_PX, BADGE_PAD, BADGE_INSET, BADGE_RADIUS = 2, 3, 4, 4
BADGE_GROUND, BADGE_KNOB, BADGE_TRACK = (0, 0, 0, 170), (255, 255, 255, 255), (255, 255, 255, 140)  # RGBA


def mix_badge(p: QPainter, right: float, bottom: float) -> None:
    """The mix badge, its bottom right corner at (right, bottom)."""
    side = len(BADGE_ART[0]) * BADGE_PX + 2 * BADGE_PAD
    left, top = round(right - side), round(bottom - side)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(*BADGE_GROUND))
    p.drawRoundedRect(QRectF(left, top, side, side), BADGE_RADIUS, BADGE_RADIUS)
    for y, row in enumerate(BADGE_ART):
        for x, c in enumerate(row):
            if c != ".":
                p.fillRect(left + BADGE_PAD + x * BADGE_PX, top + BADGE_PAD + y * BADGE_PX, BADGE_PX, BADGE_PX,
                           QColor(*(BADGE_KNOB if c == "K" else BADGE_TRACK)))
    p.restore()


class SceneryBox(QComboBox):
    """The Scenery card: the chosen scenery's picture, name and what it is, with "Change…" in
    its corner; a click anywhere on it opens the picker instead of a list. (A dropdown
    underneath, so the choices and the change signal are a dropdown's.)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.open_picker = None  # set by the dialog
        self.mixed_from = None  # for Custom: the scenery its mix starts from (set by the tab)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(CARD_H)  # (never squeezed, whatever else in the tab grows)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)  # (to redraw as the pointer comes and goes)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # (not a dropdown's wheel focus: the wheel does nothing here)

    def showPopup(self) -> None:
        if self.open_picker:
            self.open_picker()
        else:
            super().showPopup()

    def wheelEvent(self, event) -> None:
        """Scrolling over the card scrolls the tab, never the scenery (a dropdown's wheel would
        change the forest at each notch, Custom too)."""
        event.ignore()

    def keyPressEvent(self, event) -> None:
        """The keys that would step through a dropdown's list open the picker instead; letters
        and Home/End, which would jump to a choice, do nothing."""
        key = event.key()
        if key in OPEN_KEYS:
            self.showPopup()
        elif key in STEP_KEYS or (event.text().strip() and not any(event.modifiers() & m for m in JUMP_KEEPS)):
            event.accept()
        else:
            super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), CARD_H)

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), CARD_H)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # colours from the palette: Anki's CSS colours aren't always ones Qt can read, and an
        # unreadable colour paints black
        palette = self.palette()
        accent = palette.color(QPalette.ColorRole.Highlight)
        subtle = palette.color(QPalette.ColorRole.PlaceholderText)
        hover = self.underMouse()
        # a step off the window's own colour, as Anki's buttons are
        night = theme_manager.night_mode
        window = palette.color(QPalette.ColorRole.Window)
        fill = window.lighter(CARD_LIFT_DARK) if night else window.darker(CARD_LIFT_LIGHT)
        if hover:
            fill = fill.lighter(CARD_HOVER) if night else fill.darker(CARD_HOVER)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(accent if hover or self.hasFocus() else palette.color(QPalette.ColorRole.Mid), 1))
        p.setBrush(fill)
        p.drawRoundedRect(frame, CARD_RADIUS, CARD_RADIUS)

        # the picture, a pixel a point so no smoothing comes into it. Custom shows the scenery its
        # mix comes from, with the mix badge in its corner (a plain grey one if there is none)
        key = self.currentData()
        spec = presets.by_key().get(key)
        shown = key if spec else self.mixed_from
        pic = QRectF(CARD_PAD, CARD_PAD, CARD_PIC_W, CARD_PIC_H)
        pix = card_picture(shown) if shown else QPixmap()
        path = QPainterPath()
        path.addRoundedRect(pic, CARD_PIC_RADIUS, CARD_PIC_RADIUS)
        if pix.isNull():
            p.fillPath(path, QColor(128, 128, 128, 60))
        else:
            p.save()
            p.setClipPath(path)
            p.drawPixmap(pic.topLeft(), pix)
            p.restore()
        if not spec:
            mix_badge(p, pic.right() - BADGE_INSET, pic.bottom() - BADGE_INSET)

        # "Change…" in the top right corner, the name beside it, and under both what it is
        x = int(pic.right()) + CARD_GAP
        right = self.width() - CARD_GAP
        # "Change…" in the text's own colour, the accent under the pointer
        change = "Change\u2026"
        change_font = QFont(self.font())
        change_font.setPixelSize(CARD_CHANGE_FONT)
        change_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(change_font)
        p.setPen(accent if hover else palette.color(QPalette.ColorRole.WindowText))
        change_w = p.fontMetrics().horizontalAdvance(change)
        p.drawText(QRectF(right - change_w, CARD_PAD, change_w, CARD_LINE),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, change)
        name_font = QFont(self.font())
        name_font.setPixelSize(CARD_NAME_FONT)
        name_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(name_font)
        p.setPen(palette.color(QPalette.ColorRole.WindowText))
        room = max(0, right - change_w - CARD_GAP - x)
        p.drawText(QRectF(x, CARD_PAD, room, CARD_LINE), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight, room))
        note_font = QFont(self.font())
        note_font.setPixelSize(CARD_NOTE_FONT)
        p.setFont(note_font)
        p.setPen(subtle)
        line_h = p.fontMetrics().height()
        for i, line in enumerate(two_lines(spec.note if spec else CUSTOM_NOTE, note_font, max(1, right - x))):
            p.drawText(QRectF(x, CARD_PAD + CARD_LINE + CARD_NOTE_GAP + i * line_h, right - x, line_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
        p.end()


class _Tile(QAbstractButton):
    def __init__(self, preset, pix: QPixmap, on_hover):
        super().__init__()
        self.preset = preset
        self.pix = pix
        self._on_hover = on_hover
        self._lift = 0.0
        self._rise = QVariantAnimation(self)
        self._rise.setDuration(LIFT_MS)
        self._rise.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rise.valueChanged.connect(self._lifted)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(preset.note)
        font = self.font()
        font.setPixelSize(NAME_FONT)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)

    def sizeHint(self) -> QSize:
        return QSize(PICTURE_W + 2 * RING, RING + PICTURE_H + NAME_GAP + self.fontMetrics().height() + RING)

    def _lifted(self, value) -> None:
        self._lift = float(value)
        self.update()

    def _rise_to(self, end: float) -> None:
        self._rise.stop()
        # (both ends floats: an animation between a float and an int never moves)
        self._rise.setStartValue(float(self._lift))
        self._rise.setEndValue(float(end))
        self._rise.start()

    def enterEvent(self, event) -> None:
        self._on_hover(self.preset)
        self._rise_to(LIFT)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._on_hover(None)
        self._rise_to(0)
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(RING, RING - self._lift, PICTURE_W, PICTURE_H)
        path = QPainterPath()
        path.addRoundedRect(frame, TILE_RADIUS, TILE_RADIUS)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(frame.topLeft(), self.pix)  # (a pixel a point, so no smoothing comes into it)
        p.restore()
        ring = QColor(color("BORDER_FOCUS"))
        if self.isChecked() or self.hasFocus():
            pen = QPen(ring if self.isChecked() else self.palette().color(QPalette.ColorRole.Mid))
            pen.setWidthF(RING if self.isChecked() else 1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            edge = RING / 2 if self.isChecked() else 0.75
            p.drawRoundedRect(frame.adjusted(-edge, -edge, edge, edge), TILE_RADIUS + edge, TILE_RADIUS + edge)
        if self.isChecked():
            badge = QRectF(frame.right() - BADGE - 6, frame.top() + 6, BADGE, BADGE)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawEllipse(badge)
            tick = QPen(QColor("white"))
            tick.setWidthF(2)
            tick.setCapStyle(Qt.PenCapStyle.RoundCap)
            tick.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(tick)
            x, y, w = badge.left(), badge.top(), BADGE
            p.drawPolyline([QPointF(x + w * 0.28, y + w * 0.52), QPointF(x + w * 0.44, y + w * 0.67), QPointF(x + w * 0.72, y + w * 0.36)])
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        name = QRectF(RING, frame.bottom() + NAME_GAP, PICTURE_W, self.fontMetrics().height())
        p.drawText(name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.fontMetrics().elidedText(self.preset.label, Qt.TextElideMode.ElideRight, PICTURE_W))
        p.end()


class SceneryPicker(QDialog):
    """Every scenery to choose from on `day`, in sections: one in its holiday week first,
    then the rest in the catalogue's order, Surprise me daily leading them. Accepted, `current`
    is the one picked."""

    def __init__(self, parent, keys: list, current: str, day):
        super().__init__(parent)
        self.setWindowTitle("Choose a scenery")
        self.current = current
        self.columns = 0
        specs = presets.by_key()
        chosen = [specs[k] for k in keys if k in specs]
        limited = [p for p in chosen if p.season]
        rest = [p for p in chosen if not p.season]
        rest.sort(key=lambda p: p.key != presets.DAILY)  # (a stable sort: the catalogue's order stays)
        self.tiles = []
        self.sections = []
        for title, members in (("This week only", limited), ("Sceneries", rest)):
            if not members:
                continue
            tiles = []
            for p in members:
                pix = mosaic() if p.key == presets.DAILY else picture(p.key)
                if p.season:
                    pix = tagged(pix, f"Until {last_day(p, day)}")
                tile = _Tile(p, pix, self._hovered)
                tile.setChecked(p.key == current)
                tile.clicked.connect(lambda _checked=False, t=tile: self._pick(t.preset.key))
                tiles.append(tile)
            self.tiles += tiles
            self.sections.append((QLabel(title), QGridLayout(), tiles))

        self.search = QLineEdit()
        self.search.setPlaceholderText(f"Search {len(self.tiles)} sceneries")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(SEARCH_W)
        self.search.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.search.setStyleSheet(SEARCH_STYLE.format(line=color("BORDER_SUBTLE"), focus=color("BORDER_FOCUS"),
                                                      ground=color("CANVAS_CODE")))
        self.search.textChanged.connect(lambda _text: self._layout())
        self.none_found = hint("No scenery has that in its name.")
        self.none_found.hide()

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(MARGIN - RING, MARGIN - RING, MARGIN - RING, MARGIN)
        for i, (label, grid, _tiles) in enumerate(self.sections):
            label.setStyleSheet(SECTION_STYLE)
            label.setContentsMargins(RING, 0, 0, 0)  # (in line with the pictures, not their rings)
            if i:
                bv.addSpacing(SECTION_GAP)
            bv.addWidget(label)
            grid.setHorizontalSpacing(COLUMN_GAP - 2 * RING)
            grid.setVerticalSpacing(ROW_GAP)
            bv.addLayout(grid)
        bv.addWidget(self.none_found)
        bv.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidget(body)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # the title, with the search beside it; under the tiles, what the scenery under the
        # pointer (else the chosen one) is, and Cancel
        title = QLabel("Choose a scenery")
        title.setStyleSheet(TITLE_STYLE)
        head = QHBoxLayout()
        head.setContentsMargins(MARGIN, MARGIN * 3 // 4, MARGIN, MARGIN * 3 // 4)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.search)
        self.note = hint("")
        self.note.setStyleSheet(f"color: {color('FG_SUBTLE')}; font-size: 12px;")
        # the window's default button, so macOS draws it blue (Enter still picks the tile with
        # the focus, or the first scenery the search leaves: keyPressEvent takes it first)
        cancel = QPushButton("Close")
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        foot = QHBoxLayout()
        foot.setContentsMargins(MARGIN, MARGIN * 3 // 4, MARGIN, MARGIN * 3 // 4)
        foot.addWidget(self.note, 1)
        foot.addWidget(cancel)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addLayout(head)
        v.addWidget(_rule())
        v.addWidget(self.scroll, 1)
        v.addWidget(_rule())
        v.addLayout(foot)
        # (only once it is in the picker: a widget shown with no parent is a window of its own,
        # which takes the focus and, when it goes, hands it to Anki's main window)
        self.search.setVisible(len(self.tiles) > SEARCH_FROM)
        # a section's title only when there is more than one to tell apart
        for label, _grid, _tiles in self.sections:
            label.setProperty("wanted", len(self.sections) > 1)
        self._hovered(None)
        # wide enough for COLUMNS; then, with the tiles laid out at that width, as tall as they
        # are, up to MAX_H
        tile_w = (self.tiles[0].sizeHint().width() if self.tiles else PICTURE_W) + COLUMN_GAP - 2 * RING
        scrollbar = self.scroll.verticalScrollBar().sizeHint().width()
        tallest = _room_on_screen(parent)
        self.resize(COLUMNS * tile_w - COLUMN_GAP + 2 * RING + 2 * (MARGIN - RING) + scrollbar, tallest)
        self._layout()
        rest = self.sizeHint().height() - self.scroll.sizeHint().height()  # the title, the note, the rules
        self.resize(self.width(), min(tallest, body.sizeHint().height() + rest))

    def _pick(self, key: str) -> None:
        self.current = key
        self.accept()

    def keyPressEvent(self, event) -> None:
        """Enter picks the tile with the focus (Tab and the arrows move it), else the first
        scenery a search leaves; with neither it is Close's, as the window's default button."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focused = self.focusWidget()
            if isinstance(focused, _Tile):
                self._pick(focused.preset.key)
                return
            if self.search.text().strip():
                first = next((t.preset.key for t in self.tiles if t.isVisible()), None)
                if first:
                    self._pick(first)
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout()

    def _layout(self) -> None:
        """Lay out the tiles whose name or note has the search in it, a section at a time,
        as many to a row as the width holds."""
        tile_w = (self.tiles[0].sizeHint().width() if self.tiles else PICTURE_W) + COLUMN_GAP - 2 * RING
        # its own width, less the scroll bar's: the scroll area is only resized after this
        room = self.width() - 2 * (MARGIN - RING) - self.scroll.verticalScrollBar().sizeHint().width() + COLUMN_GAP - 2 * RING
        self.columns = max(1, room // tile_w)
        want = self.search.text().strip().lower()
        found = 0
        for label, grid, tiles in self.sections:
            for t in tiles:
                grid.removeWidget(t)
                t.hide()
            shown = [t for t in tiles if not want or want in t.preset.label.lower() or want in t.preset.note.lower()]
            for i, t in enumerate(shown):
                grid.addWidget(t, i // self.columns, i % self.columns, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                t.show()
            # any room left over goes after the last column, so the gaps between tiles stay even
            for c in range(grid.columnCount()):
                grid.setColumnStretch(c, 0)
            grid.setColumnStretch(self.columns, 1)
            label.setVisible(bool(shown) and bool(label.property("wanted")))
            found += len(shown)
        self.none_found.setVisible(not found)

    def _hovered(self, preset) -> None:
        """The line under the tiles: what the scenery under the pointer is, else the chosen one."""
        if preset is None:
            preset = presets.by_key().get(self.current)
        self.note.setText(preset.note if preset else "")


def _room_on_screen(parent) -> int:
    """How tall the picker may be: MAX_H, or less on a small screen (the one `parent` is on),
    leaving room for the window's title bar."""
    screen = None
    try:
        screen = parent.window().screen() if parent is not None else None
    except AttributeError:  # (QWidget.screen is Qt 5.14 and later)
        pass
    screen = screen or QGuiApplication.primaryScreen()
    if screen is None:
        return MAX_H
    return max(MIN_H, min(MAX_H, screen.availableGeometry().height() - TITLE_BAR_ROOM))


def _rule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setStyleSheet(f"color: {color('BORDER_SUBTLE')};")
    return line

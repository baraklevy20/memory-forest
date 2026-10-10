"""The scenery picker, right on the Scenery tab: every scenery as a moving picture with its
name on it, in a scrolling panel of tiles, as many to a row as fit, in sections, with a
search once there are many. Clicking a tile picks it; clicking a Plus one, which this copy
lacks, shows the way to it under the panel."""

from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass

from aqt.qt import (
    QAbstractButton,
    QColor,
    QEasingCurve,
    QFont,
    QFontMetrics,
    QGridLayout,
    QGuiApplication,
    QLabel,
    QLinearGradient,
    QLineEdit,
    QMovie,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPointF,
    QPolygonF,
    QRect,
    QRectF,
    QScrollArea,
    QSize,
    Qt,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)

from .. import presets
from .palette import color
from .patreon import PATREON
from .widgets import hint, hint_style

# each preset's picture, drawn by dev/thumbnails.py: a piece of its scene in the scene's own
# pixels, shown a pixel a point; and the same piece moving (dev/tile_gifs.py), shown instead
# where there is one and the forest is animated
PICTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenery")
MOVING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenery_anim")
PICTURE_W, PICTURE_H = 192, 108
# the sceneries Memory Forest Plus has and this copy does not (written by dev/thumbnails.py):
# the picker shows them after the rest, locked, with a PLUS label on the picture
PLUS_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plus.json")
PLUS_TAG = "PLUS"
PLUS_INK = (240, 200, 110, 255)  # RGBA
NEW_TAG = "NEW"  # a scenery new since the settings were last opened (news.py), for this visit
NEW_INK = (159, 227, 180, 255)  # RGBA
# a Plus scenery's line under the tiles, the same under the pointer and once clicked (when it
# stays, so the link can be reached): the way to it, opened only if they follow the link.
# (The sceneries' own descriptions stay in their JSON: nobody read them under the tiles.)
PLUS_LINE = '{label} is in Memory Forest Plus. <a href="{url}">Get it on Patreon</a>'
CUSTOM_NOTE = "Your own mix, made in Customize. Pick a scenery to start again from it."
SEARCH_FROM = 12  # tiles before the picker offers a search
COLUMN_GAP, ROW_GAP = 10, 10
SECTION_GAP = 10  # points above a section's title, after the first
# rows the panel shows before it scrolls, at most and at least: half a row peeks out, so it
# looks scrollable. The dialog gives up rows, half a row at a time, on a screen too short for it
ROWS_SHOWN, ROWS_FEWEST = 2.5, 1.5
ROW_H = PICTURE_H + ROW_GAP
MIN_COLUMNS = 3  # the panel is never narrower than this many tiles (the dialog grows to hold them)
# Surprise me daily's tile: these four, in quarters
DAILY_MOSAIC = ("aurora", "synthwave", "lanterns", "bamboo")

# A tile: the picture with rounded corners and its name on it, over a shade at the foot, lifting
# a little under the pointer; the chosen one ringed in the theme's focus blue, with a tick in its
# corner. Labels on it ("Until 25 Dec", PLUS) are small dark pills.
TILE_RADIUS = 8
RING = 3  # the chosen tile's ring, and the room left round every picture for it (above it, LIFT more)
LIFT, LIFT_MS = 3, 140  # how far a tile rises under the pointer, and how quickly
NAME_FONT, NAME_PAD = 14, 9  # the name on the picture, and its room from the picture's edges
SHADE_H, SHADE_ALPHA = 0.55, 170  # the shade under the name: its share of the picture's height, and how dark at the foot
BADGE = 20  # the tick's circle, across
PILL_FONT, PILL_INSET, PILL_PAD_X, PILL_PAD_Y, PILL_SPACING = 11, 6, 7, 3, 1.5
PILL_GROUND = (0, 0, 0, 170)  # RGBA
SECTION_STYLE = "font-size: 12px; font-weight: bold;"
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


def moving(key: str) -> str | None:
    """A preset's moving picture, if it has one."""
    path = os.path.join(MOVING, f"{key}.gif")
    return path if os.path.exists(path) else None


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


@dataclass(frozen=True)
class PlusScenery:
    """A scenery only Memory Forest Plus has: a tile to look at, never to pick."""

    key: str
    label: str
    note: str = ""
    season: object = None


def plus_only(offered) -> list:
    """The Plus sceneries not `offered` here (this copy lacks them, or the Debug tab pretends it
    is the base edition) that it has the picture of, in the catalogue's order."""
    try:
        with open(PLUS_LIST, encoding="utf-8") as f:
            listed = json.load(f)
    except (OSError, ValueError):
        return []
    return [PlusScenery(e["key"], e["label"], e.get("note", "")) for e in listed
            if e["key"] not in offered and os.path.exists(os.path.join(PICTURES, f"{e['key']}.png"))]


def pill(p: QPainter, text: str, ink: QColor, x: float, top: float, right_aligned: bool) -> None:
    """A small dark label, its top corner at (x, top): the left one, or the right one."""
    font = QFont()
    font.setPixelSize(PILL_FONT)
    font.setBold(True)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, PILL_SPACING if text in (PLUS_TAG, NEW_TAG) else 0)
    fm = QFontMetrics(font)
    w = fm.horizontalAdvance(text) + 2 * PILL_PAD_X
    h = fm.height() + 2 * PILL_PAD_Y
    box = QRectF(x - w if right_aligned else x, top, w, h)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(*PILL_GROUND))
    p.drawRoundedRect(box, h / 2, h / 2)
    p.setFont(font)
    p.setPen(ink)
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    p.restore()


def last_day(preset, day) -> str:
    end = presets.season_ends(preset, day)
    last = end.fromordinal(end.toordinal() - 1)
    return f"{last.day} {last.strftime('%b')}"


class _Search(QLineEdit):
    def keyPressEvent(self, event) -> None:
        """Enter picks the first scenery found (returnPressed) and goes no further: let through,
        it would press the dialog's Done as well."""
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()


class _Tile(QAbstractButton):
    def __init__(self, preset, pix: QPixmap, gif: str | None, tag: str):
        super().__init__()
        self.preset = preset
        self.locked = isinstance(preset, PlusScenery)  # shown, never picked: no lift, no focus
        self.pix = pix
        self.tag = tag  # a holiday's "Until ..." label, in the top left corner
        self.new = False  # NEW in that corner instead (a holiday's scenery is never announced)
        self.movie = None
        self.playing = False  # whether it moves while it can be seen
        if gif:
            # only the frame on show is kept: a dozen tiles' every frame came to about 50 MB
            self.movie = QMovie(gif, parent=self)
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
            self.movie.frameChanged.connect(lambda _n: self.update())
        self._lift = 0.0
        self._rise = QVariantAnimation(self)
        self._rise.setDuration(LIFT_MS)
        self._rise.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rise.valueChanged.connect(self._lifted)
        self.setCheckable(not self.locked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.locked:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        font = self.font()
        font.setPixelSize(NAME_FONT)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

    def nextCheckState(self) -> None:
        """A click (or Space or Enter) chooses a tile, and never unchooses one: clicking the chosen
        tile again leaves it chosen, as there is always a scenery."""
        self.setChecked(True)

    def animate(self, on: bool) -> None:
        """Play the moving picture, or show the still one. It only plays while the tile can be
        seen: hidden by the search, on another tab or with the dialog closed, it stops."""
        self.playing = on
        self._play(on and self.isVisible())

    def _play(self, on: bool) -> None:
        if self.movie:
            if on and self.movie.state() != QMovie.MovieState.Running:
                self.movie.start()
            elif not on:
                self.movie.stop()
            self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._play(self.playing)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._play(False)

    def sizeHint(self) -> QSize:
        return QSize(PICTURE_W + 2 * RING, LIFT + PICTURE_H + 2 * RING)  # (room to rise, ring and all)

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
        if not self.locked:
            self._rise_to(LIFT)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._rise_to(0)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        """Enter picks the tile with the focus, as Space does."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(RING, LIFT + RING - self._lift, PICTURE_W, PICTURE_H)
        path = QPainterPath()
        path.addRoundedRect(frame, TILE_RADIUS, TILE_RADIUS)
        p.save()
        p.setClipPath(path)
        playing = self.movie is not None and self.movie.state() == QMovie.MovieState.Running
        # a pixel a point, so no smoothing comes into it (the frames are the picture's own pixels)
        if playing:
            p.drawPixmap(frame, self.movie.currentPixmap(), QRectF(0, 0, PICTURE_W, PICTURE_H))
        else:
            p.drawPixmap(frame.topLeft(), self.pix)
        # the name, white on a shade that darkens toward the foot
        shade = QLinearGradient(0, frame.bottom() - PICTURE_H * SHADE_H, 0, frame.bottom())
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, SHADE_ALPHA))
        p.fillRect(QRectF(frame.left(), frame.bottom() - PICTURE_H * SHADE_H, PICTURE_W, PICTURE_H * SHADE_H), shade)
        name_h = self.fontMetrics().height()
        name = QRectF(frame.left() + NAME_PAD, frame.bottom() - NAME_PAD + 2 - name_h, PICTURE_W - 2 * NAME_PAD, name_h)
        text = self.fontMetrics().elidedText(self.preset.label, Qt.TextElideMode.ElideRight, int(name.width()))
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(name.translated(0, 1), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        p.setPen(QColor("white"))
        p.drawText(name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        p.restore()
        if self.tag:
            pill(p, self.tag, QColor("white"), frame.left() + PILL_INSET, frame.top() + PILL_INSET, False)
        elif self.new:
            pill(p, NEW_TAG, QColor(*NEW_INK), frame.left() + PILL_INSET, frame.top() + PILL_INSET, False)
        if self.locked:
            pill(p, PLUS_TAG, QColor(*PLUS_INK), frame.right() - PILL_INSET, frame.top() + PILL_INSET, True)
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
            # a QPolygonF, not a list: Anki 2.1.50's PyQt 6.2 takes no list here
            p.drawPolyline(QPolygonF([QPointF(x + w * 0.28, y + w * 0.52), QPointF(x + w * 0.44, y + w * 0.67),
                                      QPointF(x + w * 0.72, y + w * 0.36)]))
        p.end()


class SceneryPicker(QWidget):
    """The panel of tiles on the Scenery tab: every scenery to choose from on the day, in
    sections - one in its holiday week first, then the rest in the catalogue's order, Surprise
    me daily leading them, the Plus ones this copy lacks last. `on_pick(key)` is called with
    the scenery clicked."""

    def __init__(self, on_pick, animate: bool):
        super().__init__()
        self.on_pick = on_pick
        self.animated = animate
        self.current = None
        self.new_keys = set()  # sceneries that wear NEW (see _Tile.new)
        self.invite = None  # the Plus scenery last clicked: its line stays under the tiles
        self.shown_for = None  # (keys, day) the tiles were made for
        self.tiles = []
        self.sections = []
        self.columns = 0

        # the search goes on the group title's row (the Scenery tab puts it there), so it is the
        # picker's only until then: never without a parent, which would make it a window
        self.search = _Search(self)
        self.search_wanted = False  # enough sceneries to need it (SEARCH_FROM)
        self.search_allowed = True  # the tiles are in view (not Customize, in their place)
        self.search.setClearButtonEnabled(True)
        self.search.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.search.setStyleSheet(SEARCH_STYLE.format(line=color("BORDER_SUBTLE"), focus=color("BORDER_FOCUS"),
                                                      ground=color("CANVAS_CODE")))
        self.search.textChanged.connect(lambda _text: self._layout())
        self.search.returnPressed.connect(self._pick_first)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # the panel is the group's own colour, not a well of the window's: its inside is see-through
        # (the viewport's, not the scroll area's: that would reach the scroll bar too, and swap the
        # system's for Qt's own)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.rows = ROWS_SHOWN
        self.max_h = round(self.rows * ROW_H)  # (no taller than its tiles, when fewer)
        self.scroll.setFixedHeight(self.max_h)
        self.setMinimumWidth(MIN_COLUMNS * (PICTURE_W + COLUMN_GAP) - COLUMN_GAP + 2 * RING
                             + self.scroll.verticalScrollBar().sizeHint().width())
        self.note = hint("")
        self.note.setStyleSheet(hint_style())
        self.note.setTextFormat(Qt.TextFormat.RichText)
        self.note.setOpenExternalLinks(True)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.scroll)
        v.addWidget(self.note)
        self.search.setVisible(False)
        self.note.setVisible(False)

    def allow_search(self, on: bool) -> None:
        """Show the search while the tiles are in view, if there are enough of them to need it."""
        self.search_allowed = on
        self.search.setVisible(on and self.search_wanted)

    def set_rows(self, rows: float) -> None:
        """Show this many rows before scrolling (the dialog's choice, for the screen)."""
        self.rows = rows
        self.max_h = round(rows * ROW_H)
        self.scroll.setFixedHeight(self.max_h)
        self._layout()

    def set_choices(self, keys: list, current: str, day) -> None:
        """Offer these sceneries on `day` (tiles made again only when they change), `current` the chosen one."""
        if self.shown_for != (tuple(keys), day):
            self.shown_for = (tuple(keys), day)
            self._make_tiles(keys, day)
        self.set_current(current)

    def set_current(self, key: str) -> None:
        self.current = key
        for t in self.tiles:
            if not t.locked:
                t.setChecked(t.preset.key == key)
        self._show_line()

    def animate(self, on: bool) -> None:
        self.animated = on
        for t in self.tiles:
            t.animate(on)

    def _make_tiles(self, keys: list, day) -> None:
        specs = presets.by_key()
        chosen = [specs[k] for k in keys if k in specs]
        limited = [p for p in chosen if p.season]
        rest = [p for p in chosen if not p.season]
        rest.sort(key=lambda p: p.key != presets.DAILY)  # (a stable sort: the catalogue's order stays)
        rest += plus_only(set(keys))
        self.tiles = []
        self.sections = []
        body = QWidget()
        body.setAutoFillBackground(False)
        bv = self.body_layout = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 0, 0)
        groups = [(title, members) for title, members in (("This week only", limited), ("Sceneries", rest)) if members]
        for i, (title, members) in enumerate(groups):
            tiles = []
            for p in members:
                daily = p.key == presets.DAILY
                tile = _Tile(p, mosaic() if daily else picture(p.key), None if daily else moving(p.key),
                             f"Until {last_day(p, day)}" if p.season else "")
                tile.new = not tile.locked and p.key in self.new_keys
                if tile.locked:
                    tile.clicked.connect(lambda _checked=False, t=tile: self._invite(t.preset))
                else:
                    tile.clicked.connect(lambda _checked=False, t=tile: self._pick(t.preset.key))
                tiles.append(tile)
            label = QLabel(title)
            label.setStyleSheet(SECTION_STYLE)
            label.setContentsMargins(RING, 0, 0, 0)  # (in line with the pictures, not their rings)
            if i:
                bv.addSpacing(SECTION_GAP)
            bv.addWidget(label)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(COLUMN_GAP - 2 * RING)
            grid.setVerticalSpacing(ROW_GAP - 2 * RING - LIFT)
            bv.addLayout(grid)
            # a section's title only when there is more than one to tell apart
            label.setVisible(len(groups) > 1)
            self.tiles += tiles
            self.sections.append((label, grid, tiles))
        self.none_found = hint("No scenery has that in its name.")
        bv.addWidget(self.none_found)
        bv.addStretch(1)
        self.scroll.setWidget(body)  # (the old tiles go with the old body)
        self.search.setPlaceholderText(f"Search {len(self.tiles)} sceneries")
        self.search_wanted = len(self.tiles) > SEARCH_FROM
        self.allow_search(self.search_allowed)
        self.columns = 0
        self._layout()
        for t in self.tiles:
            t.animate(self.animated)

    def _pick(self, key: str) -> None:
        self.invite = None
        self.on_pick(key)

    def _pick_first(self) -> None:
        """Enter in the search picks the first scenery it leaves."""
        first = next((t.preset.key for t in self.tiles if t.isVisible() and not t.locked), None)
        if first and self.search.text().strip():
            self._pick(first)

    def _invite(self, preset) -> None:
        """A Plus tile clicked: its line, with the link, stays under the tiles."""
        self.invite = preset
        self._show_line()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout()

    def _layout(self) -> None:
        """Lay out the tiles whose name or note has the search in it, a section at a time,
        as many to a row as the width holds, centred; the panel as tall as they are, up to max_h."""
        if not self.sections:
            return
        tile_w = PICTURE_W + COLUMN_GAP
        scrollbar = self.scroll.verticalScrollBar().sizeHint().width()
        room = self.width() - scrollbar + COLUMN_GAP - 2 * RING
        self.columns = max(1, room // tile_w)
        want = self.search.text().strip().lower()
        found = 0
        for label, grid, tiles in self.sections:
            for t in tiles:
                grid.removeWidget(t)
                t.hide()
            shown = [t for t in tiles if not want or want in t.preset.label.lower()]
            for i, t in enumerate(shown):
                grid.addWidget(t, i // self.columns, i % self.columns, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                t.show()
            label.setVisible(bool(shown) and len(self.sections) > 1)
            found += len(shown)
        self.none_found.setVisible(not found)
        # as tall as the tiles, up to max_h; and the room left over split either side of them
        # (the section titles move in with them, so they stay in line)
        need = self.scroll.widget().sizeHint().height()
        self.scroll.setFixedHeight(min(need, self.max_h))
        used = self.columns * tile_w - COLUMN_GAP + 2 * RING
        spare = max(0, self.width() - (scrollbar if need > self.max_h else 0) - used)
        self.body_layout.setContentsMargins(spare // 2, 0, spare - spare // 2, 0)

    def _show_line(self) -> None:
        """The line under the tiles, only while there is something to say: the way to the Plus
        scenery last clicked, else, on Custom, what that is. (Not on hover: the line coming and
        going would move everything under it as the pointer crosses the tiles.)"""
        if self.invite is not None:
            text = PLUS_LINE.format(label=html.escape(self.invite.label), url=PATREON)
        elif self.current not in presets.by_key():
            text = html.escape(CUSTOM_NOTE)
        else:
            text = ""
        self.note.setText(text)
        self.note.setVisible(bool(text))

"""The Heatmap tab's Colours and Tiles: chosen by eye. Whose colours (the scenery's, a ready ramp,
or your own) and how its tiles are drawn, each option a picture drawn with the heatmap's own sums (heatmap_look.py), so a strip here is the
heatmap's key. The heatmap behind the dialog is the preview."""

from __future__ import annotations

import datetime as _dt

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QColor,
    QColorDialog,
    QEvent,
    QFont,
    QFontMetrics,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QImage,
    QLabel,
    QMenu,
    QObject,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPoint,
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager

from .. import heatmap_look as HL
from .. import presets, scene
from ..i18n import N_, t, tx
from ..live_weather import for_config
from ..seasons import today
from .widgets import JoinedChoice, app_rtl, bidi, follow_direction, form, forward, hint, picture_button_style, pixel_ratio, rtl

# a strip: the four shades of a day studied as the heatmap's tiles, side by side, at 1 tile pixel a
# point (as the heatmap is at about that size)
STRIP_GAP = 2
ICON_W, ICON_H = 4 * (HL.TILE + STRIP_GAP) - STRIP_GAP, HL.TILE
SWATCH_W, SWATCH_H = 28, 16
BUTTON_COLUMNS, BUTTON_GAP = 3, 6  # the ready ramps and the tiles, three to a row (the dialog stays its width)
SCENERY_LABEL = N_("settings.heatmap_look.scenery")
# any scenery's colours, kept when the scenery changes: one button that opens a list of them (a button
# each grew with every scenery, and several looked alike: Aurora, Starry night and Frozen market)
# the scenery's colours, as a dropdown first among the ready ones: the scenery's own (they follow
# it), or any scenery's, kept when you change the scenery (2026-10-16: one button, no row of its own)
PICK_LABEL = " {name} \u25be"  # (a space between the picture and the word, as option_button has)
PICK_TIP = N_("settings.heatmap_look.your_current_scenerys_colours_or_another")
FOLLOW_NAME = N_("settings.heatmap_look.current_scenery")  # (plain words: "This scenery's own" read as complex, 2026-10-16)
# the sceneries' own tiles as one dropdown too, as the colours are (2026-10-23: a button each made one
# long row, and grows with every scenery that draws its own): the current scenery's (they follow it),
# or any scenery's that can be had just now; the basic styles beside it
TILE_PICK_TIP = N_("settings.heatmap_look.your_current_scenerys_tiles_or_another")
BUSIER_LABEL = N_("settings.heatmap_look.busier_days")
# the ready ramps' tooltips: what they run from and to (each scenery's says whose it is)
READY_TIPS = {"olive": N_("settings.heatmap_look.review_heatmaps_olive_deep_olive_green"),
              "lime": N_("settings.heatmap_look.lime_green_to_bright_lime"),
              "ice": N_("settings.heatmap_look.review_heatmaps_ice_deep_blue_to"),
              "magenta": N_("settings.heatmap_look.review_heatmaps_magenta_deep_pink_to"),
              "flame": N_("settings.heatmap_look.review_heatmaps_flame_bright_red_to")}
# Busier days, as joined buttons, shown only in Anki's dark mode, the only one it changes (a light
# page's shades always run darker for more): no words needed to say which page it is for
# (Pace turns too: its strong end is the faster days)
BUSIER_TIPS = {"lighter": N_("settings.heatmap_look.in_ankis_dark_mode_busier_days"),
               "darker": N_("settings.heatmap_look.busier_days_are_darker_in_ankis")}
# each tile style's name and tooltip, by id: i18n reads their English from web/heatmap/<key>.json
TILE_LABELS = {k: f"heatmap_style.{k}" for k in HL.TILE_SPECS}
TILE_TIPS = {k: f"heatmap_style.{k}.tip" if v.get("tip") else "" for k, v in HL.TILE_SPECS.items()}
# (a whole sentence for each page it is faint on, or both)
FAINT_NOTES = {("light",): N_("settings.heatmap_look.your_busiest_colour_is_hard_to"),
               ("dark",): N_("settings.heatmap_look.your_busiest_colour_is_hard_to_2"),
               ("dark", "light"): N_("settings.heatmap_look.your_busiest_colour_is_hard_to_3")}
# (one line: SETTINGS_GUIDELINES.md; under the page's header, as it is about both groups. "Your colours
# stay when you change the scenery" was cut: Scenery, the default, changes with it)


def page_bg() -> tuple:
    """The heatmap's page under Anki's theme just now (heatmap_look.PAGES)."""
    return HL.PAGES["dark" if getattr(theme_manager, "night_mode", False) else "light"], getattr(theme_manager, "night_mode", False)


def forest_hour(cfg: dict) -> str:
    """The forest's hour just now (mood.time: the clock, the city's sun or a fixed hour), as
    payload.py finds it for the scenery's day, so the pictures wear the colours the heatmap does."""
    real, place, _error = for_config(cfg)
    try:
        return scene.choose_mood(cfg, _dt.datetime.combine(today(cfg), _dt.datetime.now().time()), real, place)["time"]
    except Exception:  # (a hand-edited config it can't read: the scenery's colours as they are)
        return ""


def _pixmap(pixels: dict, w: int, h: int, scale: int = 1) -> QPixmap:
    """Pixels ((x, y) -> colour) as a picture, each pixel `scale` points, crisp on the screen."""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    for (x, y), c in pixels.items():
        if 0 <= x < w and 0 <= y < h:
            img.setPixelColor(x, y, QColor(*(max(0, min(255, int(v))) for v in c)))
    dpr = max(1, round(pixel_ratio()))
    pm = QPixmap.fromImage(img.scaled(w * dpr * scale, h * dpr * scale, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation))
    pm.setDevicePixelRatio(dpr)
    return pm


# smooth corners, as calendar.js sharpen draws them: each tile's face a rounded square at the screen's
# resolution, its corners' radius (and a style's own, Round's, and how much bigger it is drawn)
SMOOTH_R = 1.8


def flipped(pm: QPixmap) -> QPixmap:
    """A sample as the words read: right to left, mirrored, the quiet days on the right and the
    busy ones on the left (as the heatmap's Less ... More key on the page)."""
    if not rtl():
        return pm
    out = QPixmap.fromImage(pm.toImage().mirrored(True, False))
    out.setDevicePixelRatio(pm.devicePixelRatio())
    return out


def strip(look: dict, drawer: str = HL.TILE_DEFAULT, sample: bool = False, page: tuple | None = None, gaps: bool = True,
          smooth: tuple | None = None) -> QPixmap:
    """`_strip`, quiet to busy as the words read (flipped)."""
    return flipped(_strip(look, drawer, sample, page, gaps, smooth))


def _strip(look: dict, drawer: str = HL.TILE_DEFAULT, sample: bool = False, page: tuple | None = None, gaps: bool = True,
           smooth: tuple | None = None) -> QPixmap:
    """The four shades of `look` (heatmap_look.preview_look) as tiles, on this theme's page (or
    `page`, (its colour, dark)); a tile sample (`sample`) at two points a pixel, so a texture
    shows; a shape with spaces between its days (`gaps`) as a tile for each, as the heatmap draws it;
    with smooth corners (`smooth`: (radius, grow) in the heatmap's pixels), each tile's face a
    rounded square drawn smooth, as the heatmap draws it."""
    bg, dark = page or page_bg()
    shades = HL.shades(look["colours"], bg, dark, look.get("exact", False), look.get("flipLight", False), look.get("darker", False),
                       look.get("hour"))
    scale = 2 if sample else 1
    pm = _pixmap(_strip_pixels(shades, drawer, dark, gaps), ICON_W, ICON_H, scale)
    return _smoothed(pm, shades, scale, *smooth) if smooth else pm


def tile_sample(look: dict, key: str, cfg: dict, here_env: str) -> QPixmap:
    """The tile style `key`'s sample in `look`'s colours, as the heatmap draws it: its own spaces and
    smooth corners (TILE_STYLE); smooth Round is a Flat tile, rounder and a little bigger
    (calendar.js paletteOf). Scenery's is the scenery's own (heatmap_look.tile_style)."""
    key = HL.tile_style(dict(cfg, calendar_tiles=key), here_env)
    gaps, smooth = HL.TILE_STYLE[key]
    spec = HL.TILE_SPECS[key]
    drawer = "flat" if smooth and spec.get("smoothRadius") else HL.tile_env(dict(cfg, calendar_tiles=key), here_env)
    corners = (spec.get("smoothRadius", SMOOTH_R), spec.get("smoothGrow", 0)) if smooth and gaps else None
    return flipped(_pair(_strip(look, drawer, sample=True, gaps=gaps, smooth=corners), gaps))


# a style's sample: a quiet day's tile and a busy day's, side by side at two points a pixel (all four
# shades made the buttons too wide for one row: 2026-10-16)
PAIR_W, PAIR_H = 2 * (2 * HL.TILE + STRIP_GAP), 2 * ICON_H


def _pair(pm: QPixmap, gaps: bool = True) -> QPixmap:
    """The first and last tiles of a four-tile sample (`strip(..., sample=True)`), side by side: with
    the space between them a style has (`gaps`), or none for one whose days join (Contours: its
    band's two ends, one band)."""
    dpr = pm.devicePixelRatio()
    out = QPixmap(int(PAIR_W * dpr), int(PAIR_H * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(QColor(0, 0, 0, 0))
    p = QPainter(out)
    w = 2 * HL.TILE
    for at, src in ((0, 0), (w + (2 * STRIP_GAP if gaps else 0), 3 * 2 * (HL.TILE + STRIP_GAP))):
        p.drawPixmap(QRectF(at, 0, w, PAIR_H), pm, QRectF(src * dpr, 0, w * dpr, PAIR_H * dpr))
    p.end()
    return out


# the shade a menu's tile is drawn in, by the page: the darker of the two middle ones (the second on a
# dark page, the third on a light one, whose shades run darker), its scenery's colour at its fullest
# and dark enough that a light mark shows (the busiest, a dark page's palest, washed Starry night out
# and hid Misty valley's rime and the ice's shine, 2026-10-23)
MENU_SHADE = {True: 1, False: 2}


def menu_tile(look: dict, key: str, cfg: dict, here_env: str) -> QPixmap:
    """The tile style `key` as one day's tile (MENU_SHADE, by the page) at two points a pixel, as
    tile_sample draws it, in a square the size of a menu's pictures (QUAD)."""
    key = HL.tile_style(dict(cfg, calendar_tiles=key), here_env)
    gaps, smooth = HL.TILE_STYLE[key]
    spec = HL.TILE_SPECS[key]
    drawer = "flat" if smooth and spec.get("smoothRadius") else HL.tile_env(dict(cfg, calendar_tiles=key), here_env)
    corners = (spec.get("smoothRadius", SMOOTH_R), spec.get("smoothGrow", 0)) if smooth and gaps else None
    pm = _strip(look, drawer, sample=True, gaps=gaps, smooth=corners)
    shade = MENU_SHADE[page_bg()[1]]
    dpr = pm.devicePixelRatio()
    out = QPixmap(int(QUAD * dpr), int(QUAD * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(QColor(0, 0, 0, 0))
    w, at = 2 * HL.TILE, (QUAD - 2 * HL.TILE) / 2
    p = QPainter(out)
    p.drawPixmap(QRectF(at, at, w, w), pm, QRectF(shade * 2 * (HL.TILE + STRIP_GAP) * dpr, 0, w * dpr, w * dpr))
    p.end()
    return out


def _smoothed(pm: QPixmap, shades, scale: int, radius: float, grow: float) -> QPixmap:
    """`pm`'s tiles as the heatmap's smooth corners draw them: each face (all but the tile's edge row
    and column) a rounded square, antialiased, filled with its shade and its texture inside."""
    dpr = pm.devicePixelRatio()
    out = QPixmap(pm.size())
    out.setDevicePixelRatio(dpr)
    out.fill(QColor(0, 0, 0, 0))
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    face = HL.TILE - 1
    for i, (colour, _tone, _edge) in enumerate(shades):
        x0 = i * (HL.TILE + STRIP_GAP)
        # (a style that draws its tiles bigger, Round, shifted in by as much, so none is cut at the
        # picture's edge: the tiles keep inside its width and height)
        rect = QRectF(x0 * scale, 0, (face + 2 * grow) * scale, (face + 2 * grow) * scale)
        path = QPainterPath()
        path.addRoundedRect(rect, (radius + grow) * scale, (radius + grow) * scale)
        p.fillPath(path, QColor(*(int(v) for v in colour)))
        p.save()
        p.setClipPath(path)
        src = QRectF(x0 * scale * dpr, 0, face * scale * dpr, face * scale * dpr)
        p.drawPixmap(QRectF((x0 + grow) * scale, grow * scale, face * scale, face * scale), pm, src)
        p.restore()
    p.end()
    return out


def _strip_pixels(shades, drawer: str, dark: bool, gaps: bool = True) -> dict:
    # (a shape's sample as its file says: "round" or "contours"; with spaces between the days, as a
    # tile for each)
    sample = HL.TILE_SPECS.get(drawer, {}).get("sample")
    if sample in ("round", "contours") and gaps:
        return round_tiles(shades, outlined=sample == "contours", dark=dark)
    if sample == "contours":
        return contour_pixels(shades, dark)
    if sample == "round":
        return rounded_pixels(shades, dark)
    pixels = {}
    for i, shade in enumerate(shades):
        for (x, y), c in HL.tile_pixels(drawer, shade, i).items():
            pixels[x + i * (HL.TILE + STRIP_GAP), y] = c
    return pixels


def rounded_pixels(shades, dark: bool = True) -> dict:
    """Rounded's sample: the four shades as one shape, the gutters filled, its corners cut two
    pixels round (calendar.js shapesPass)."""
    w, h, pixels = ICON_W, HL.TILE - 1, {}
    for x in range(w):
        i = min(3, x // (HL.TILE + STRIP_GAP))
        colour, tone, _edge = shades[i]
        for y in range(h):
            lx = x - i * (HL.TILE + STRIP_GAP)
            pixels[x, y] = tone if (HL.hash_str(f"{i},{lx >> 1},{y >> 1}") & 3) == 0 else colour
    _cut_corners(pixels, w, h)
    return pixels


def round_tiles(shades, outlined: bool = False, dark: bool = True) -> dict:
    """Round's sample with spaces between the days (calendar.js shapesPass): each shade a tile of
    its own in one colour, its corners cut round; Contours' (`outlined`), each a flat tile with its edge."""
    pixels, face = {}, HL.TILE - 1
    for i, (colour, _tone, _edge) in enumerate(shades):
        tile = {}
        for x in range(face):
            for y in range(face):
                tile[x, y] = colour  # (one colour, as Flat's)
        _cut_corners(tile, face, face)
        if outlined:
            ink = HL.mix(shades[3][2], HL.DARK, 0.45 if dark else 0.35)
            for (x, y) in list(tile):
                if any((x + dx, y + dy) not in tile for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    tile[x, y] = ink
        for (x, y), c in tile.items():
            pixels[x + i * (HL.TILE + STRIP_GAP), y] = c
    return pixels


def _cut_corners(pixels: dict, w: int, h: int) -> None:
    for cx, cy, dx, dy in ((0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
        for p in ((cx, cy), (cx + dx, cy), (cx, cy + dy)):
            pixels.pop(p, None)


def contour_pixels(shades, dark: bool = True) -> dict:
    """Contours' sample: the four shades as one outlined shape in flat bands, a line in the higher
    band's edge colour where a band rises (web/heatmap/contours.js)."""
    w, h, pixels = ICON_W, HL.TILE - 1, {}
    ink = HL.mix(shades[3][2], HL.DARK, 0.45 if dark else 0.35)
    band = [min(3, round(3 * x / (w - 1))) for x in range(w)]
    for x in range(w):
        for y in range(h):
            rises = x + 1 < w and band[x + 1] > band[x]
            pixels[x, y] = shades[min(3, band[x] + 1)][2] if rises else shades[band[x]][0]
    _cut_corners(pixels, w, h)
    for (x, y) in list(pixels):
        if any((x + dx, y + dy) not in pixels for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            pixels[x, y] = ink
    return pixels


QUAD = 2 * HL.TILE + STRIP_GAP  # (a menu's icons are square: the four shades two by two)


def quad(look: dict, drawer: str = HL.TILE_DEFAULT) -> QPixmap:
    """The four shades of `look` as tiles two by two, quietest top left, busiest bottom right (mirrored right to left): a
    strip for a square place (the scenery picker's list)."""
    bg, dark = page_bg()
    shades = HL.shades(look["colours"], bg, dark, look.get("exact", False), look.get("flipLight", False), look.get("darker", False),
                       look.get("hour"))
    pixels = {}
    for i, shade in enumerate(shades):
        for (x, y), c in HL.tile_pixels(drawer, shade, i).items():
            pixels[x + (i % 2) * (HL.TILE + STRIP_GAP), y + (i // 2) * (HL.TILE + STRIP_GAP)] = c
    return flipped(_pixmap(pixels, QUAD, QUAD))  # (right to left, quietest top right)


def swatch(hex_colour: str) -> QPixmap:
    pm = QPixmap(SWATCH_W * 2, SWATCH_H * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(128, 128, 128, 160), 1))
    p.setBrush(QColor(hex_colour))
    p.drawRoundedRect(QRectF(0.5, 0.5, SWATCH_W - 1, SWATCH_H - 1), 3, 3)
    p.end()
    return pm


def option_button(label: str, tip: str = "") -> QPushButton:
    """A choice drawn as a picture and a word, as Nature's are."""
    b = QPushButton(f" {label}")  # (a space between the picture and the word)
    b.setIconSize(QSize(ICON_W, ICON_H))
    b.setAutoDefault(False)  # Enter in the dialog means Done
    b.setCheckable(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(picture_button_style(bold=False))
    if tip:
        b.setToolTip(tip)
    return b


class PickButton(QPushButton):
    """A choice that stands for one of several keys (a scenery's colours, "ready:aurora"): a click
    opens a list of them instead of choosing; picking one from it chooses this button for that key.
    `choices()` gives the list, (key, name); `icons()` each key's picture, drawn only as the list
    opens (every scenery's strip was painted again at each change of the tab)."""

    def __init__(self, choices, icons, tip: str, follow: str = HL.MATCH):
        super().__init__(PICK_LABEL.format(name=tx(SCENERY_LABEL)))
        # (`follow`: the key that follows the scenery, named "Scenery" on the button)
        self.choices, self.icons, self.follow, self.key, self.picked = choices, icons, follow, follow, None
        self.setIconSize(QSize(ICON_W, ICON_H))
        self.setAutoDefault(False)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(picture_button_style(bold=False))
        self.setToolTip(tip)
        self.clicked.connect(self._open)

    def nextCheckState(self) -> None:
        """A click opens the list, and only a pick chooses; the group still unchecks it through
        here when another choice is made (SETTINGS_GUIDELINES.md)."""
        if self.isChecked() and self.group() is not None and self.group().checkedButton() is not self:
            self.setChecked(False)

    def takes(self, key) -> bool:
        return any(k == key for k, _name in self.choices())

    def set_key(self, key) -> None:
        """(its strip is drawn with the others': LookControls.refresh)"""
        self.key = key
        name = tx(SCENERY_LABEL) if key == self.follow else next((n for k, n in self.choices() if k == key), key)
        self.setText(PICK_LABEL.format(name=name))

    def _open(self) -> None:
        menu = follow_direction(QMenu(self))
        menu.setStyleSheet(f"QMenu {{ icon-size: {QUAD}px; }}")  # (each picture at its own size: square)
        icons = self.icons()
        for i, (key, name) in enumerate(self.choices()):
            if i == 1:
                menu.addSeparator()  # (the scenery's own, then every scenery's)
            act = menu.addAction(icons[key], bidi(name, menu.isRightToLeft()))
            act.setIconVisibleInMenu(True)  # (macOS leaves menus' icons out unless asked)
            if self.isChecked() and key == self.key:  # (the one chosen in bold: a tick took the strip's place)
                font = act.font(); font.setBold(True); act.setFont(font)
            act.triggered.connect(lambda _c=False, k=key: self._pick(k))
        if menu.isRightToLeft() and not app_rtl():
            _right_align(menu)
        # (under the button, from the corner its words start at)
        at = self.rect().bottomLeft()
        if self.isRightToLeft():  # (its right edge under the button's)
            at = self.rect().bottomRight() - QPoint(menu.sizeHint().width() - 1, 0)
        menu.exec(self.mapToGlobal(at))

    def _pick(self, key) -> None:
        was = self.isChecked() and self.key
        self.set_key(key)
        self.setChecked(True)  # (the group unchecks the one chosen before and announces it)
        if was and was != key and self.picked:
            self.picked()


def _right_align(menu: QMenu) -> None:
    """A menu's names against its pictures, on the right, right to left: Qt draws a menu's text on
    the left of its room whatever the menu's direction (it goes by the app's), so each name is led
    by no-break spaces up to the widest."""
    menu.ensurePolished()  # (a menu's own font, the system's for menus, only once polished)

    def metrics(act) -> QFontMetrics:
        font = QFont(menu.font())
        font.setBold(act.font().bold())  # (the chosen one's in bold)
        return QFontMetrics(font)
    acts = [a for a in menu.actions() if not a.isSeparator()]
    widest = max((metrics(a).horizontalAdvance(a.text()) for a in acts), default=0)
    for a in acts:
        fm, text = metrics(a), a.text()
        # (one at a time, the whole line measured: a lone space's width is rounded, a row of them isn't)
        while fm.horizontalAdvance("\u00a0" + text) <= widest:
            text = "\u00a0" + text
        a.setText(text)


class OneOf(QButtonGroup):
    """Buttons anywhere on the tab as one choice, read and set by each one's key (a ready ramp,
    Yours, a tile style): exactly one is chosen. One Tab stop, the chosen one, and the arrow keys
    from one shown button to the next, as widgets.JoinedChoice has (each push button was a Tab stop
    of its own: some twenty on the page)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.keys = {}
        self.buttonToggled.connect(lambda _b, _on: self._tab_stop())

    def add(self, key, button) -> None:
        self.keys[key] = button
        self.addButton(button)
        button.installEventFilter(self)
        self._tab_stop()

    def _tab_stop(self) -> None:
        for b in self.keys.values():
            b.setFocusPolicy(Qt.FocusPolicy.StrongFocus if b.isChecked() else Qt.FocusPolicy.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            shown = [b for b in self.keys.values() if b.isVisible() and b.isEnabled()]
            if obj in shown:
                at = shown.index(obj) + forward(obj, event.key())
                if 0 <= at < len(shown):
                    if isinstance(shown[at], PickButton):  # (chosen for the colours it has, its list not opened)
                        shown[at].setChecked(True)
                    else:
                        shown[at].click()  # (as a click: a tile style's own corners and spaces come with it)
                    shown[at].setFocus()
            return True
        return False

    def currentData(self):
        key = next((k for k, b in self.keys.items() if b.isChecked()), None)
        b = self.keys.get(key)
        return b.key if isinstance(b, PickButton) else key

    def set_quietly(self, key) -> None:
        b = self.keys.get(key)
        if b is None:  # (a key a PickButton stands for)
            b = next((p for p in self.keys.values() if isinstance(p, PickButton) and p.takes(key)), None)
            if b is not None:
                b.set_key(key)
        if b is not None:
            self.blockSignals(True)
            b.setChecked(True)
            self.blockSignals(False)
            self._tab_stop()


class LookControls(QObject):
    """Colours and Tiles, for the Heatmap tab to put in its two groups (`colours`, `tiles`)."""

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.here = "golden_lake"  # the scenery chosen on the Scenery tab (the dialog says: set_scenery)
        self.edition_cfg = cfg
        self.hour = ""  # the forest's hour (forest_hour), which the scenery's own colours follow
        self.mine = HL.mine(cfg)
        self.changed = None
        self.source = OneOf(self)
        # the scenery's own colours first (the default), then the ready ramps
        ready = QGridLayout()
        ready.setContentsMargins(0, 0, 0, 0)
        ready.setSpacing(BUTTON_GAP)
        # (the scenery's colours: its own, or any scenery's, from one dropdown: _scenery_choices)
        self.scenery = PickButton(self._scenery_choices, self._scenery_icons, tx(PICK_TIP))
        self.scenery.picked = self._announce
        self.source.add("scenery", self.scenery)
        ready.addWidget(self.scenery, 0, 0)
        self.ready = {}
        # (a seasonal scenery's only in its week, a Plus one only in Plus: _place)
        # (a scenery this copy hasn't at all, a Plus one in the base edition's build, has no button)
        for key, label in HL.READY_LABELS.items():
            b = option_button(tx(label), tx(READY_TIPS.get(key, "")))
            self.ready[key] = b
            self.source.add(HL.READY_PREFIX + key, b)
        self.ready_grid = ready
        # (Custom, not "Yours": with no row labels, the word says these are colours you pick; 2026-10-16)
        self.yours = option_button(t("settings.heatmap_look.custom"), t("settings.heatmap_look.colours_you_pick_one_dim_to"))
        self.source.add(HL.MINE, self.yours)
        self.first = QPushButton()
        self.second = QPushButton()
        for b, tip, i in ((self.first, t("settings.heatmap_look.your_colour_with_a_blend_the"), 0), (self.second, t("settings.heatmap_look.the_busiest_days_colour"), 1)):
            b.setIconSize(QSize(SWATCH_W, SWATCH_H))
            b.setAutoDefault(False)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, i=i: self._pick_colour(i))
        self.blend = QCheckBox(t("settings.heatmap_look.blend_into"))
        self.blend.setChecked(HL.mine_two(cfg))
        self.blend.toggled.connect(self._blend_toggled)
        mine_row = QHBoxLayout()
        mine_row.setContentsMargins(0, 0, 0, 0)
        mine_row.addWidget(self.yours)
        mine_row.addSpacing(8)
        mine_row.addWidget(self.first)
        mine_row.addSpacing(8)
        mine_row.addWidget(self.blend)
        mine_row.addWidget(self.second)
        mine_row.addStretch(1)
        # which way a dark page's shades run (a light page's never change), as joined buttons
        self.busier = JoinedChoice([(k, tx(label)) for k, label in HL.BUSIER], HL.busier(cfg), "lighter",
                                   {k: tx(tip) for k, tip in BUSIER_TIPS.items()})
        self.busier_box = QWidget()
        busier_row = QHBoxLayout(self.busier_box)
        busier_row.setContentsMargins(0, 0, 0, 0)
        busier_row.addWidget(QLabel(tx(BUSIER_LABEL)))  # (in its row: the rows above have no labels)
        busier_row.addSpacing(BUTTON_GAP)
        busier_row.addWidget(self.busier)
        busier_row.addStretch(1)
        self.faint = hint("")

        self.tile_choice = OneOf(self)
        tiles_row = QGridLayout()
        tiles_row.setContentsMargins(0, 0, 0, 0)
        tiles_row.setSpacing(BUTTON_GAP)
        # (the sceneries' own tiles: the current scenery's, or any scenery's, from one dropdown: _tile_choices)
        self.tile_pick = PickButton(self._tile_choices, self._tile_icons, tx(TILE_PICK_TIP), follow=HL.TILE_FOLLOW)
        self.tile_pick.setIconSize(QSize(PAIR_W, PAIR_H))
        self.tile_pick.picked = lambda: self._tile_clicked(self.tile_pick.key)
        self.tile_choice.add(HL.TILE_FOLLOW, self.tile_pick)
        # then the basic styles, a button each
        self.tile_buttons = {}
        for key in HL.BASIC_TILES:
            b = option_button(tx(TILE_LABELS[key]), tx(TILE_TIPS[key]))
            b.setIconSize(QSize(PAIR_W, PAIR_H))  # (a quiet day's tile and a busy day's: _pair)
            self.tile_buttons[key] = b
            self.tile_choice.add(key, b)
        self.tiles_grid = tiles_row
        self.tile_choice.set_quietly(HL.tiles_choice(cfg))
        # (a style chosen, by a click, the arrow keys or the dropdown: its own corners and spaces back)
        self.tile_choice.buttonToggled.connect(lambda _b, on: on and self._tile_clicked(self.tile_choice.currentData()))
        # each style's smooth corners and spaces between the days are its own (heatmap_look.TILE_STYLE);
        # while debugging, two switches can change them, and picking a style puts them back to its own
        # (set by _seed_switches once the scenery in view is known: what each goes by is the style
        # that scenery resolves to, not Flat's)
        self.smooth = QCheckBox("Smooth corners (debug)")
        self.smooth.setToolTip("Each day's tile with smooth, rounded corners, drawn at your screen's resolution. Not for the joined shapes.")
        self.smooth.toggled.connect(lambda _on: self._announce())
        self.gaps = QCheckBox("Spaces between days (debug)")
        self.gaps.toggled.connect(lambda _on: self._announce())
        self._seeded_for = None  # (the scenery and its style the switches were last seeded for)
        for line in (self.faint,):
            line.setVisible(False)

        # the two groups' insides: the tab puts them in place
        self.colours = QVBoxLayout()
        # (no row labels: the group's name says what they are, and Custom says which are yours;
        # "Ready colours" read oddly, 2026-10-16)
        rows = form()
        rows.setVerticalSpacing(BUTTON_GAP)  # (one gap between all the rows: macOS's form left a wider one above Custom)
        rows.addRow(ready)
        # (the note that your busiest colour is faint sits under your colours, not under Busier days)
        mine_box = QVBoxLayout()
        mine_box.setContentsMargins(0, 0, 0, 0)
        mine_box.addLayout(mine_row)
        mine_box.addWidget(self.faint)
        rows.addRow(mine_box)
        rows.addRow(self.busier_box)
        self.colours.addLayout(rows)
        self.tiles_box = QVBoxLayout()
        self.tiles_box.addLayout(tiles_row)
        # (debugging only, and not while the Debug tab pretends this is the base or Plus edition,
        # which have neither: set_scenery shows or hides them as the edition changes)
        if HL.debug_available(cfg):
            self.tiles_box.addWidget(self.smooth)
            self.tiles_box.addWidget(self.gaps)
        self.debug_switches = HL.debug_available(cfg)
        self.source.buttonToggled.connect(lambda _b, on: on and self._announce())
        self.busier.on_change(self._announce)
        # (a tile style announces once its switches are its own: _tile_clicked)
        self.source.set_quietly(HL.colours_choice(cfg))
        self._drawn = None  # (what the pictures were last drawn for)
        self._laid = None  # (the buttons last laid out: set_scenery)
        self.set_scenery("golden_lake", cfg)

    def on_change(self, changed) -> None:
        self.changed = changed

    def _announce(self) -> None:
        self.refresh()
        if self.changed:
            self.changed()

    def _blend_toggled(self, _on: bool) -> None:
        self.source.keys[HL.MINE].setChecked(True)  # (announces, unless already chosen)
        self._announce()

    def _pick_colour(self, i: int) -> None:
        picked = QColorDialog.getColor(QColor(self.mine[i]), (self.first, self.second)[i].window(), t("settings.heatmap_look.your_colour") if i == 0 else t("settings.heatmap_look.your_busiest_days_colour"))
        if not picked.isValid():
            return
        self.mine[i] = picked.name().lower()
        if i == 1 and not self.blend.isChecked():
            self.blend.blockSignals(True)
            self.blend.setChecked(True)
            self.blend.blockSignals(False)
        if self.source.currentData() != HL.MINE:
            self.source.keys[HL.MINE].setChecked(True)
        else:
            self._announce()

    def _tile_clicked(self, key: str) -> None:
        """A tile style picked: its smooth corners and spaces back to its own (TILE_STYLE), so the
        debug switches show what a user would see."""
        if key in HL.TILE_STYLE:
            gaps, smooth = self._own_style(key)
            for box, on in ((self.gaps, gaps), (self.smooth, smooth)):
                box.blockSignals(True)
                box.setChecked(on)
                box.blockSignals(False)
            self._announce()

    def set_scenery(self, key: str, edition_cfg: dict) -> None:
        """The scenery on the Scenery tab now (Scenery shows its colours), and the edition the
        Debug tab pretends this is (whose Plus tiles are locked)."""
        spec = presets.by_key().get(key)
        if key == presets.DAILY:
            spec = presets.of_the_day(today(edition_cfg), leave_out=presets.left_out(edition_cfg))
        self.here = spec.key if spec else self.here
        self.edition_cfg = edition_cfg
        self.hour = forest_hour(edition_cfg)
        # (the debug switches: not while the Debug tab pretends this is a release; set once they
        # have a parent, or they would flash up as windows of their own)
        if self.debug_switches:
            for box in (self.smooth, self.gaps):
                if box.parent() is not None:
                    box.setVisible(not HL.debug_edition(edition_cfg))
        # (only what can be had: no Plus colours or tiles this copy lacks, a seasonal scenery's only
        # in its week; a choice no longer offered shows the default)
        colours = list(self.ready)
        tiles = [k for k in self.tile_buttons if HL.tile_shown(k, edition_cfg)]
        own_tiles = [k for k, _name in self._tile_choices()]
        # (laid out again only when the buttons shown change: this runs on every change in any tab)
        if self._laid != (colours, tiles):
            self._laid = (colours, tiles)
            self._place(self.ready_grid, [self.scenery] + [self.ready[k] for k in colours], [self.ready[k] for k in self.ready if k not in colours])
            # (the styles in one row: a few, each a short word and a small sample)
            self._place(self.tiles_grid, [self.tile_pick] + [self.tile_buttons[k] for k in tiles], [self.tile_buttons[k] for k in self.tile_buttons if k not in tiles],
                        columns=len(tiles) + 1)
            # (even columns: each grid's buttons as wide as its widest, and Yours as the colours')
            self._even([self.scenery, *(self.ready[k] for k in colours), self.yours])
        source = self.source.currentData()
        offered = [*colours, *(k[len(HL.READY_PREFIX):] for k, _n in self._scenery_choices() if k != HL.MATCH)]
        if source is None or (source.startswith(HL.READY_PREFIX) and source[len(HL.READY_PREFIX):] not in offered):
            self.source.set_quietly(HL.MATCH)
        if self.tile_choice.currentData() not in tiles + own_tiles:
            self.tile_pick.set_key(HL.TILE_FOLLOW)
            self.tile_choice.set_quietly(HL.TILE_FOLLOW)
        self._seed_switches(edition_cfg)
        self.refresh()

    def _seed_switches(self, cfg: dict) -> None:
        """The debug switches as the heatmap draws just now: a saved override (`debug_gaps`,
        `debug_smooth` a bool), else the style's own for the scenery in view and the style chosen -
        what style_values compares them to, so switches nobody touched never write anything. Seeded
        again as the scenery or the style it draws in changes (a Debug edition or date can change
        that too; a style picked puts them back itself: _tile_clicked)."""
        own = self._own_style(self.tile_choice.currentData() or HL.TILE_FOLLOW)
        if self._seeded_for == (self.here, own):
            return
        self._seeded_for = (self.here, own)
        for box, key, theirs in ((self.gaps, "debug_gaps", own[0]), (self.smooth, "debug_smooth", own[1])):
            saved = cfg.get(key)
            box.blockSignals(True)
            box.setChecked(saved if isinstance(saved, bool) else theirs)
            box.blockSignals(False)

    def _scenery_choices(self) -> list:
        """The scenery dropdown's list: the scenery's own (they follow it), then every scenery's colours
        that can be had just now (HL.scenery_ready_env): (key, name), each named as the scenery picker
        names it."""
        known = presets.by_key()
        return [(HL.MATCH, tx(FOLLOW_NAME))] + [(HL.READY_PREFIX + k, tx(known[k].name)) for k in HL.SCENERY_READY
                                           if k in known and HL.scenery_ready_env(k, self.edition_cfg)]

    def _scenery_icons(self) -> dict:
        """Each of the dropdown's choices as a picture: its strip in the tiles chosen (key -> QIcon)."""
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self._values_now())
        drawn = HL.tile_env(cfg, here_env)
        drawn = drawn if drawn in HL.DRAWERS else HL.TILE_DEFAULT
        return {key: QIcon(quad(HL.preview_look(dict(cfg, calendar_colours=key), here_env, self.hour), drawn)) for key, _name in self._scenery_choices()}

    def _tile_choices(self) -> list:
        """The tiles dropdown's list: the current scenery's (they follow it), then each scenery's own
        tiles that can be had just now (HL.tile_shown): (key, name), each named after its scenery as the
        scenery picker names it, as the colours' dropdown is (a style's own name, Rime or Brush, didn't
        say whose it was: 2026-10-23)."""
        names = {p.environment: p.name for p in presets.FOREST_PRESETS}
        return [(HL.TILE_FOLLOW, tx(FOLLOW_NAME))] + [(k, tx(names.get(HL.TILE_ENVS[k], TILE_LABELS[k]))) for k in HL.SCENERY_TILES
                                                 if HL.tile_shown(k, self.edition_cfg)]

    def _tile_icons(self) -> dict:
        """Each of the tiles dropdown's choices as a picture: a busy day's tile at two points a pixel, as
        the Style buttons draw theirs, in its own scenery's colours (the current scenery's for Current
        scenery), so each reads as its scenery's at a glance (key -> QIcon). (In the colours chosen, at a
        point a pixel and four shades two by two, Brush, Scanlines and Rime looked alike, 2026-10-23; a
        menu's pictures are square, so the buttons' two tiles side by side ran into the names on a Mac.)"""
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self._values_now(), calendar_colours=HL.MATCH)
        icons = {}
        for key, _name in self._tile_choices():
            env = HL.TILE_ENVS.get(key, here_env)
            icons[key] = QIcon(menu_tile(HL.preview_look(dict(cfg, calendar_tiles=key), env, self.hour), key, cfg, env))
        return icons

    def _values_now(self) -> dict:
        return {"calendar_mine": list(self.mine), "calendar_mine_two": self.blend.isChecked(),
                "calendar_tiles": self.tile_choice.currentData() or HL.TILE_FOLLOW,
                "calendar_busier": self.busier.currentData() or "lighter"}

    @staticmethod
    def _even(buttons: list) -> None:
        widest = max(b.sizeHint().width() for b in buttons)
        for b in buttons:
            b.setMinimumWidth(widest)

    @staticmethod
    def _place(grid, shown: list, hidden: list, columns: int = BUTTON_COLUMNS) -> None:
        """`shown` in `grid`, at most BUTTON_COLUMNS to a row and the rows as even as they can be
        (four are two and two, not three and one; seven are three, two and two), and `hidden` out of it."""
        for b in shown + hidden:
            grid.removeWidget(b)
        for b in hidden:
            b.setVisible(False)
        rows = max(1, -(-len(shown) // max(1, columns)))
        sizes = [len(shown) // rows + (1 if r < len(shown) % rows else 0) for r in range(rows)]
        places = [(r, c) for r, n in enumerate(sizes) for c in range(n)]
        for b, (row, col) in zip(shown, places):
            grid.addWidget(b, row, col)
            if b.parent() is not None:  # (never shown before it has a parent: it would flash up as a window)
                b.setVisible(True)
        used = max(sizes) if shown else 0
        for c in range(grid.columnCount() + 1):  # (the room left over goes after the last column used)
            grid.setColumnStretch(c, 1 if c == used else 0)

    def values(self) -> dict:
        return {
            "calendar_colours": self.source.currentData() or HL.MATCH,
            "calendar_mine": list(self.mine),
            "calendar_mine_two": self.blend.isChecked(),
            "calendar_tiles": self.tile_choice.currentData() or HL.TILE_FOLLOW,
            "calendar_busier": self.busier.currentData() or "lighter",
            **self.style_values(),
        }

    def _own_style(self, key: str) -> tuple:
        """(spaces, smooth corners) of the style `key` draws in just now: Scenery's, the scenery's own."""
        here_env = presets.by_key()[self.here].environment
        return HL.TILE_STYLE[HL.tile_style(dict(self.edition_cfg, calendar_tiles=key), here_env)]

    def style_values(self) -> dict:
        """The debug switches, kept only where they differ from the tile style's own (None: as the
        style has it), so a later change to a style still reaches anyone who never touched them."""
        gaps, smooth = self._own_style(self.tile_choice.currentData() or HL.TILE_FOLLOW)
        return {"debug_gaps": None if self.gaps.isChecked() == gaps else self.gaps.isChecked(),
                "debug_smooth": None if self.smooth.isChecked() == smooth else self.smooth.isChecked()}

    def refresh(self) -> None:
        """Draw every picture again for the choices as they are now (and the theme)."""
        # (Busier days only in dark mode; set once it has a parent: shown before, it flashes up as a window)
        if self.busier_box.parent() is not None:
            dark = page_bg()[1]
            self.busier_box.setVisible(dark)
        # a colour of your own that hardly stands out from a page: said, not changed (shown only
        # once in the tab: a widget shown before it has a parent flashes up as a window)
        mine_look = HL.preview_look(dict(self.edition_cfg, **self.values()), presets.by_key()[self.here].environment)
        faint = HL.faint_on(mine_look["colours"]) if self.source.currentData() == HL.MINE else []
        self.faint.setText(tx(FAINT_NOTES[tuple(p for p in ("dark", "light") if p in faint)]) if faint else "")
        if self.faint.parent() is not None:
            self.faint.setVisible(bool(faint))
        state = (self.here, self.hour, repr(sorted(self.values().items())), HL.debug_edition(self.edition_cfg), page_bg())
        if state == self._drawn:
            return
        self._drawn = state
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self.values())
        # (each in the tiles chosen, as the heatmap's key draws them; a joined shape's as Flat's)
        drawn = HL.tile_env(cfg, here_env)
        drawn = drawn if drawn in HL.DRAWERS else HL.TILE_DEFAULT
        self.scenery.setIcon(QIcon(strip(HL.preview_look(dict(cfg, calendar_colours=self.scenery.key), here_env, self.hour), drawn)))
        for key, b in self.ready.items():
            look = HL.preview_look(dict(cfg, calendar_colours=HL.READY_PREFIX + key), here_env)
            b.setIcon(QIcon(strip(look, drawn)))
        self.yours.setIcon(QIcon(strip(HL.preview_look(dict(cfg, calendar_colours=HL.MINE), here_env), drawn)))
        for b, c in ((self.first, self.mine[0]), (self.second, self.mine[1])):
            icon = QIcon(swatch(c))
            icon.addPixmap(swatch(c), QIcon.Mode.Disabled)  # (unblended, the second keeps its colour, its button greyed)
            b.setIcon(icon)
        self.second.setEnabled(self.blend.isChecked())
        look = HL.preview_look(cfg, here_env, self.hour)
        for key, b in self.tile_buttons.items():  # (each as its style draws it: its own spaces and corners)
            b.setIcon(QIcon(tile_sample(look, key, cfg, here_env)))
        self.tile_pick.setIcon(QIcon(tile_sample(look, self.tile_pick.key, cfg, here_env)))

"""The Heatmap tab's Colours and Tiles: chosen by eye. Whose colours (the scenery's, a ready ramp,
or your own) and how its tiles are drawn, each option a picture drawn with the heatmap's own sums (heatmap_look.py), so a strip here is the
heatmap's key. The heatmap behind the dialog is the preview."""

from __future__ import annotations

from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QColor,
    QColorDialog,
    QEvent,
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
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)
from aqt.theme import theme_manager

from .. import heatmap_look as HL
from .. import presets
from ..seasons import today
from .forest_tab import NATURE_STYLE
from .palette import color
from .scenery_picker import _pixel_ratio
from .widgets import JoinedChoice, form, hint

# a strip: the four shades of a day studied as the heatmap's tiles, side by side, at 1 tile pixel a
# point (as the heatmap is at about that size)
STRIP_GAP = 2
ICON_W, ICON_H = 4 * (HL.TILE + STRIP_GAP) - STRIP_GAP, HL.TILE
SWATCH_W, SWATCH_H = 28, 16
BUTTON_COLUMNS, BUTTON_GAP = 3, 6  # the ready ramps and the tiles, three to a row (the dialog stays its width)
SCENERY_LABEL = "Scenery"
SCENERY_READY_TIP = "{name}'s colours, on any scenery"
# any scenery's colours, kept when the scenery changes: one button that opens a list of them (a button
# each grew with every scenery, and several looked alike: Aurora, Starry night and Frozen market)
# the scenery's colours, as a dropdown first among the ready ones: the scenery's own (they follow
# it), or any scenery's, kept when you change the scenery (2026-10-16: one button, no row of its own)
PICK_LABEL = "{name} \u25be"
PICK_TIP = "The scenery's own colours, which follow it, or any scenery's, kept when you change the scenery"
FOLLOW_NAME = "This scenery's own"
BUSIER_LABEL = "Busier days"
# the ready ramps' tooltips: what they run from and to (each scenery's says whose it is)
READY_TIPS = {"olive": "Review Heatmap's Olive: deep olive green to pale yellow-green",
              "lime": "Lime: green to bright lime",
              "ice": "Review Heatmap's Ice: deep blue to pale ice blue",
              "magenta": "Review Heatmap's Magenta: deep pink to pale pink",
              "flame": "Review Heatmap's Flame: bright red to yellow"}
# Busier days, as joined buttons, shown only in Anki's dark mode, the only one it changes (a light
# page's shades always run darker for more): no words needed to say which page it is for
BUSIER_TIPS = {"lighter": "In Anki's dark mode, busier days are lighter. In light mode, always darker.",
               "darker": "Busier days are darker in Anki's dark mode too, as in light mode."}
# each tile style's name and tooltip, as its file says (web/heatmap/<key>.json; heatmap_look.TILE_SPECS)
TILE_LABELS = {k: v.get("label", k) for k, v in HL.TILE_SPECS.items()}
TILE_TIPS = {k: v.get("tip", "") for k, v in HL.TILE_SPECS.items()}
FAINT_NOTE = "Your busiest colour is hard to see on {pages} page. The heatmap shows it as you picked it."
PAGE_NAMES = {"light": "a light", "dark": "a dark"}
# (one line: SETTINGS_GUIDELINES.md; under the page's header, as it is about both groups. "Your colours
# stay when you change the scenery" was cut: Scenery, the default, changes with it)
LOOK_NOTE = "The heatmap behind this window shows each choice."
BUTTON_STYLE = NATURE_STYLE.replace(" font-weight: bold;", "")


def page_bg() -> tuple:
    """The heatmap's page under Anki's theme just now (heatmap_look.PAGES)."""
    return HL.PAGES["dark" if getattr(theme_manager, "night_mode", False) else "light"], getattr(theme_manager, "night_mode", False)


def _pixmap(pixels: dict, w: int, h: int, scale: int = 1) -> QPixmap:
    """Pixels ((x, y) -> colour) as a picture, each pixel `scale` points, crisp on the screen."""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    for (x, y), c in pixels.items():
        if 0 <= x < w and 0 <= y < h:
            img.setPixelColor(x, y, QColor(*(max(0, min(255, int(v))) for v in c)))
    dpr = max(1, round(_pixel_ratio()))
    pm = QPixmap.fromImage(img.scaled(w * dpr * scale, h * dpr * scale, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation))
    pm.setDevicePixelRatio(dpr)
    return pm


# smooth corners, as calendar.js sharpen draws them: each tile's face a rounded square at the screen's
# resolution, its corners' radius (and a style's own, Round's, and how much bigger it is drawn)
SMOOTH_R = 1.8


def strip(look: dict, drawer: str = HL.TILE_DEFAULT, sample: bool = False, page: tuple | None = None, gaps: bool = True,
          smooth: tuple | None = None) -> QPixmap:
    """The four shades of `look` (heatmap_look.preview_look) as tiles, on this theme's page (or
    `page`, (its colour, dark)); a tile sample (`sample`) at two points a pixel, so a texture
    shows; a shape with spaces between its days (`gaps`) as a tile for each, as the heatmap draws it;
    with smooth corners (`smooth`: (radius, grow) in the heatmap's pixels), each tile's face a
    rounded square drawn smooth, as the heatmap draws it."""
    bg, dark = page or page_bg()
    shades = HL.shades(look["colours"], bg, dark, look.get("exact", False), look.get("lightSame", False), look.get("darker", False))
    scale = 2 if sample else 1
    pm = _pixmap(_strip_pixels(shades, drawer, dark, gaps), ICON_W, ICON_H, scale)
    return _smoothed(pm, shades, scale, *smooth) if smooth else pm


def tile_sample(look: dict, key: str, cfg: dict, here_env: str) -> QPixmap:
    """The tile style `key`'s sample in `look`'s colours, as the heatmap draws it: its own spaces and
    smooth corners (TILE_STYLE); smooth Round is a Flat tile, rounder and a little bigger
    (calendar.js paletteOf)."""
    gaps, smooth = HL.TILE_STYLE[key]
    spec = HL.TILE_SPECS[key]
    drawer = "flat" if smooth and spec.get("smoothRadius") else HL.drawer_for(dict(cfg, calendar_tiles=key), here_env)
    corners = (spec.get("smoothRadius", SMOOTH_R), spec.get("smoothGrow", 0)) if smooth and gaps else None
    return strip(look, drawer, sample=True, gaps=gaps, smooth=corners)


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
    # (a shape's sample as its file says: "round", "contours" or "panes"; with spaces between the days,
    # round or contours as a tile for each)
    sample = HL.TILE_SPECS.get(drawer, {}).get("sample")
    if sample == "panes":
        return pane_pixels(shades, dark)
    if sample in ("round", "contours") and gaps:
        return round_tiles(shades, outlined=sample == "contours", dark=dark)
    if sample == "contours":
        return contour_pixels(shades, dark)
    if sample == "round":
        return rounded_pixels(shades, False, dark)
    pixels = {}
    for i, shade in enumerate(shades):
        for (x, y), c in HL.tile_pixels(drawer, shade, i).items():
            pixels[x + i * (HL.TILE + STRIP_GAP), y] = c
    return pixels


BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def rounded_pixels(shades, smooth: bool = False, dark: bool = True) -> dict:
    """Rounded's sample: the four shades as one shape, the gutters filled, its corners cut two
    pixels round; Smooth's: outlined, the shades blending along it, dithered (calendar.js
    shapesPass)."""
    w, h, pixels = ICON_W, HL.TILE - 1, {}
    ink = HL.mix(shades[3][2], HL.DARK, 0.45 if dark else 0.35)
    for x in range(w):
        i = min(3, x // (HL.TILE + STRIP_GAP))
        colour, tone, _edge = shades[i]
        for y in range(h):
            lx = x - i * (HL.TILE + STRIP_GAP)
            if smooth:
                level = 3 * x / (w - 1)
                b = int(level)
                pixels[x, y] = shades[min(3, b + 1 if (level - b) * 16 > BAYER[y & 3][x & 3] + 0.5 else b)][0]
            else:
                pixels[x, y] = tone if (HL.hash_str(f"{i},{lx >> 1},{y >> 1}") & 3) == 0 else colour
    corners = {(px, py) for cx, cy, dx, dy in ((0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1))
               for px, py in ((cx, cy), (cx + dx, cy), (cx, cy + dy))}
    for p in corners:
        pixels.pop(p, None)
    if smooth:  # (its outline: every pixel with the page beside it)
        for (x, y) in list(pixels):
            if any((x + dx, y + dy) not in pixels for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pixels[x, y] = ink
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


PANE_SEEDS = ((2, 5), (6, 1), (8, 6), (14, 3), (19, 6), (20, 0), (25, 4), (31, 1), (32, 7), (38, 3))  # (a few panes per shade, uneven)
LEAD_DARK, LEAD_LIGHT, GLINT, GLINT_AMT = 0.6, 0.72, 13, 0.08  # (as a drafted panes shape draws them)


def pane_pixels(shades, dark: bool = True) -> dict:
    """A panes sample, for a drafted tile style that draws its days as panes (web/drafts/): a few
    panes in each shade (by where the pane's seed is), nearest-seed shapes, lead between them and
    round the whole."""
    w, h = ICON_W, HL.TILE - 1
    bg, _dark = page_bg()
    lead = HL.mix(bg, HL.DARK, LEAD_DARK if dark else LEAD_LIGHT)
    pane = {(x, y): min(range(len(PANE_SEEDS)), key=lambda i: (PANE_SEEDS[i][0] - x) ** 2 + (PANE_SEEDS[i][1] - y) ** 2)
            for x in range(w) for y in range(h)}
    pixels = {}
    for (x, y), i in pane.items():
        edge = x in (0, w - 1) or y in (0, h - 1) or pane.get((x + 1, y), i) != i or pane.get((x, y + 1), i) != i
        colour = shades[min(3, PANE_SEEDS[i][0] // (HL.TILE + STRIP_GAP))][0]
        pixels[x, y] = lead if edge else HL.mix(colour, (255, 255, 255), GLINT_AMT) if (x - y + h * GLINT) % GLINT == 0 else colour
    return pixels


QUAD = 2 * HL.TILE + STRIP_GAP  # (a menu's icons are square: the four shades two by two)


def quad(look: dict, drawer: str = HL.TILE_DEFAULT) -> QPixmap:
    """The four shades of `look` as tiles two by two, quietest top left, busiest bottom right: a
    strip for a square place (the scenery picker's list)."""
    bg, dark = page_bg()
    shades = HL.shades(look["colours"], bg, dark, look.get("exact", False), look.get("lightSame", False), look.get("darker", False))
    pixels = {}
    for i, shade in enumerate(shades):
        for (x, y), c in HL.tile_pixels(drawer, shade, i).items():
            pixels[x + (i % 2) * (HL.TILE + STRIP_GAP), y + (i // 2) * (HL.TILE + STRIP_GAP)] = c
    return _pixmap(pixels, QUAD, QUAD)


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
    b = QPushButton(f" {label}")
    b.setIconSize(QSize(ICON_W, ICON_H))
    b.setAutoDefault(False)  # Enter in the dialog means Done
    b.setCheckable(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(BUTTON_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS")))
    if tip:
        b.setToolTip(tip)
    return b


class PickButton(QPushButton):
    """A choice that stands for one of several keys (a scenery's colours, "ready:aurora"): a click
    opens a list of them instead of choosing; picking one from it chooses this button for that key.
    `items()` gives the list: (key, name, icon)."""

    def __init__(self, items, tip: str):
        super().__init__(PICK_LABEL.format(name=SCENERY_LABEL))
        self.items, self.key, self.picked = items, HL.MATCH, None
        self.setIconSize(QSize(ICON_W, ICON_H))
        self.setAutoDefault(False)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(BUTTON_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS")))
        self.setToolTip(tip)
        self.clicked.connect(self._open)

    def nextCheckState(self) -> None:
        """A click opens the list, and only a pick chooses; the group still unchecks it through
        here when another choice is made (SETTINGS_GUIDELINES.md)."""
        if self.isChecked() and self.group() is not None and self.group().checkedButton() is not self:
            self.setChecked(False)

    def takes(self, key) -> bool:
        return any(k == key for k, _name, _icon in self.items())

    def set_key(self, key) -> None:
        """(its strip is drawn with the others': LookControls.refresh)"""
        self.key = key
        name = SCENERY_LABEL if key == HL.MATCH else next((n for k, n, _i in self.items() if k == key), key)
        self.setText(PICK_LABEL.format(name=name))

    def _open(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ icon-size: {QUAD}px; }}")  # (each one's four tiles at their own size)
        for i, (key, name, icon) in enumerate(self.items()):
            if i == 1:
                menu.addSeparator()  # (the scenery's own, then every scenery's)
            act = menu.addAction(icon, name)
            act.setIconVisibleInMenu(True)  # (macOS leaves menus' icons out unless asked)
            if self.isChecked() and key == self.key:  # (the one chosen in bold: a tick took the strip's place)
                font = act.font(); font.setBold(True); act.setFont(font)
            act.triggered.connect(lambda _c=False, k=key: self._pick(k))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _pick(self, key) -> None:
        was = self.isChecked() and self.key
        self.set_key(key)
        self.setChecked(True)  # (the group unchecks the one chosen before and announces it)
        if was and was != key and self.picked:
            self.picked()


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
                at = shown.index(obj) + (1 if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down) else -1)
                if 0 <= at < len(shown):
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
        self.mine = HL.mine(cfg)
        self.changed = None
        self.refreshed = None  # (the Heatmap tab's line that shows what is chosen)
        self.source = OneOf(self)
        # the scenery's own colours first (the default), then the ready ramps
        ready = QGridLayout()
        ready.setContentsMargins(0, 0, 0, 0)
        ready.setSpacing(BUTTON_GAP)
        # (the scenery's colours: its own, or any scenery's, from one dropdown: _scenery_items)
        self.scenery = PickButton(self._scenery_items, PICK_TIP)
        self.scenery.picked = self._announce
        self.source.add("scenery", self.scenery)
        ready.addWidget(self.scenery, 0, 0)
        self.ready = {}
        # (a seasonal scenery's only in its week, a Plus one only in Plus: _place)
        # (a scenery this copy hasn't at all, a Plus one in the base edition's build, has no button)
        for key, label in HL.READY_LABELS.items():
            b = option_button(label, READY_TIPS.get(key, ""))
            self.ready[key] = b
            self.source.add(HL.READY_PREFIX + key, b)
        self.ready_grid = ready
        # (Custom, not "Yours": with no row labels, the word says these are colours you pick; 2026-10-16)
        self.yours = option_button("Custom", "Colours you pick: one, dim to full, or two, blending from the first to the second")
        self.source.add(HL.MINE, self.yours)
        self.first = QPushButton()
        self.second = QPushButton()
        for b, tip, i in ((self.first, "Your colour (with a blend: the quietest days')", 0), (self.second, "The busiest days' colour", 1)):
            b.setIconSize(QSize(SWATCH_W, SWATCH_H))
            b.setAutoDefault(False)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, i=i: self._pick_colour(i))
        self.blend = QCheckBox("Blend into")
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
        self.busier = JoinedChoice(HL.BUSIER, HL.busier(cfg), "lighter", BUSIER_TIPS)
        self.busier_box = QWidget()
        busier_row = QHBoxLayout(self.busier_box)
        busier_row.setContentsMargins(0, 0, 0, 0)
        busier_row.addWidget(QLabel(BUSIER_LABEL))  # (in its row: the rows above have no labels)
        busier_row.addSpacing(BUTTON_GAP)
        busier_row.addWidget(self.busier)
        busier_row.addStretch(1)
        self.faint = hint("")

        self.tile_choice = OneOf(self)
        tiles_row = QGridLayout()
        tiles_row.setContentsMargins(0, 0, 0, 0)
        tiles_row.setSpacing(BUTTON_GAP)
        self.tile_buttons = {}
        for key in HL.TILES:
            b = option_button(TILE_LABELS[key], TILE_TIPS[key])
            b.setIconSize(QSize(2 * ICON_W, 2 * ICON_H))  # (a sample: two points a pixel)
            self.tile_buttons[key] = b
            self.tile_choice.add(key, b)
        self.tiles_grid = tiles_row
        self.tile_choice.set_quietly(HL.tiles_choice(cfg))
        for key, b in self.tile_buttons.items():
            b.clicked.connect(lambda _c=False, k=key: self._tile_clicked(k))
        # each style's smooth corners and spaces between the days are its own (heatmap_look.TILE_STYLE);
        # while debugging, two switches can change them, and picking a style puts them back to its own
        self.smooth = QCheckBox("Smooth corners (debug)")
        self.smooth.setToolTip("Each day's tile with smooth, rounded corners, drawn at your screen's resolution. Not for the joined shapes.")
        self.smooth.setChecked(HL.smooth(dict(cfg, debug=True)))
        self.smooth.toggled.connect(lambda _on: self._announce())
        self.gaps = QCheckBox("Spaces between days (debug)")
        self.gaps.setChecked(HL.gaps(dict(cfg, debug=True)))
        self.gaps.toggled.connect(lambda _on: self._announce())
        for line in (self.faint,):
            line.setVisible(False)

        # the two groups' insides: the tab puts them in place
        self.colours = QVBoxLayout()
        # (no row labels: the group's name says what they are, and Custom says which are yours;
        # "Ready colours" read oddly, 2026-10-16)
        rows = form()
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
        if HL.debug_available(cfg):
            self.tiles_box.addWidget(self.smooth)
            self.tiles_box.addWidget(self.gaps)
        self.source.buttonToggled.connect(lambda _b, on: on and self._source_changed())
        self.busier.on_change(self._announce)
        self.tile_choice.buttonToggled.connect(lambda _b, on: on and self._announce())
        self.source.set_quietly(HL.colours_choice(cfg))
        self._drawn = None  # (what the pictures were last drawn for)
        self.set_scenery("golden_lake", cfg)

    def on_change(self, changed) -> None:
        self.changed = changed

    def on_refresh(self, refreshed) -> None:
        self.refreshed = refreshed

    def summary(self) -> tuple:
        """What is chosen, for the line that opens the look's page: the colours as the tiles draw
        them (a sample), and in one phrase, the tiles then the colours ("Round tiles in Aurora's
        colours", "Ice blocks in the scenery's colours"; a tile's `phrase`, else its name and "tiles")."""
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self.values())
        source = self.source.currentData() or HL.MATCH
        ready = source[len(HL.READY_PREFIX):]
        colours = ("the scenery's colours" if source == HL.MATCH else "your colours" if source == HL.MINE
                   else HL.READY_LABELS.get(ready) or f"{HL.SCENERY_READY[ready]}'s colours")  # ("Aurora" alone read as the scenery)
        tile = self.tile_choice.currentData() or HL.TILE_DEFAULT
        tiles = HL.TILE_SPECS.get(tile, {}).get("phrase") or f"{TILE_LABELS[tile]} tiles"
        pix = tile_sample(HL.preview_look(cfg, here_env), tile, cfg, here_env)
        return pix, f"{tiles} in {colours}"

    def _announce(self) -> None:
        self.refresh()
        if self.changed:
            self.changed()

    def _source_changed(self) -> None:
        self._announce()

    def _blend_toggled(self, _on: bool) -> None:
        self.source.keys[HL.MINE].setChecked(True)  # (announces, unless already chosen)
        self._announce()

    def _pick_colour(self, i: int) -> None:
        picked = QColorDialog.getColor(QColor(self.mine[i]), (self.first, self.second)[i].window(), "Your colour" if i == 0 else "Your busiest days' colour")
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
            gaps, smooth = HL.TILE_STYLE[key]
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
            spec = presets.of_the_day(today(edition_cfg))
        self.here = spec.key if spec else self.here
        self.edition_cfg = edition_cfg
        # (only what can be had: no Plus colours or tiles this copy lacks, a seasonal scenery's only
        # in its week; a choice no longer offered shows the default)
        colours = list(self.ready)
        tiles = [k for k in self.tile_buttons if HL.tile_shown(k, edition_cfg)]
        self._place(self.ready_grid, [self.scenery] + [self.ready[k] for k in colours], [self.ready[k] for k in self.ready if k not in colours])
        self._place(self.tiles_grid, [self.tile_buttons[k] for k in tiles], [self.tile_buttons[k] for k in self.tile_buttons if k not in tiles])
        # (even columns: each grid's buttons as wide as its widest, and Yours as the colours')
        self._even([self.scenery, *(self.ready[k] for k in colours), self.yours])
        self._even([self.tile_buttons[k] for k in tiles])
        source = self.source.currentData()
        offered = [*colours, *(k[len(HL.READY_PREFIX):] for k, _n, _i in self._scenery_items())]
        if source is None or (source.startswith(HL.READY_PREFIX) and source[len(HL.READY_PREFIX):] not in offered):
            self.source.set_quietly(HL.MATCH)
        if self.tile_choice.currentData() not in tiles:
            self.tile_choice.set_quietly(HL.TILE_DEFAULT)
        self.refresh()

    def _scenery_items(self) -> list:
        """The scenery dropdown's list: the scenery's own (they follow it), then every scenery's colours
        that can be had just now (HL.scenery_ready_env): (key, name, its strip in the tiles chosen)."""
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self._values_now())
        drawn = HL.drawer_for(cfg, here_env)
        drawn = drawn if drawn in HL.DRAWERS else HL.TILE_DEFAULT
        own = [(HL.MATCH, FOLLOW_NAME, QIcon(quad(HL.preview_look(dict(cfg, calendar_colours=HL.MATCH), here_env), drawn)))]
        return own + [(HL.READY_PREFIX + k, name, QIcon(quad(HL.preview_look(dict(cfg, calendar_colours=HL.READY_PREFIX + k), here_env), drawn)))
                      for k, name in HL.SCENERY_READY.items() if k in presets.by_key() and HL.scenery_ready_env(k, self.edition_cfg)]

    def _values_now(self) -> dict:
        return {"calendar_mine": list(self.mine), "calendar_mine_two": self.blend.isChecked(),
                "calendar_tiles": self.tile_choice.currentData() or HL.TILE_DEFAULT,
                "calendar_busier": self.busier.currentData() or "lighter"}

    @staticmethod
    def _even(buttons: list) -> None:
        widest = max(b.sizeHint().width() for b in buttons)
        for b in buttons:
            b.setMinimumWidth(widest)

    @staticmethod
    def _place(grid, shown: list, hidden: list) -> None:
        """`shown` in `grid`, at most BUTTON_COLUMNS to a row and the rows as even as they can be
        (four are two and two, not three and one; seven are three, two and two), and `hidden` out of it."""
        for b in shown + hidden:
            grid.removeWidget(b)
        for b in hidden:
            b.setVisible(False)
        rows = max(1, -(-len(shown) // BUTTON_COLUMNS))
        sizes = [len(shown) // rows + (1 if r < len(shown) % rows else 0) for r in range(rows)]
        places = [(r, c) for r, n in enumerate(sizes) for c in range(n)]
        for b, (row, col) in zip(shown, places):
            grid.addWidget(b, row, col)
            if b.parent() is not None:  # (never shown before it has a parent: it would flash up as a window)
                b.setVisible(True)
        grid.setColumnStretch(BUTTON_COLUMNS, 1)

    def values(self) -> dict:
        return {
            "calendar_colours": self.source.currentData() or HL.MATCH,
            "calendar_mine": list(self.mine),
            "calendar_mine_two": self.blend.isChecked(),
            "calendar_tiles": self.tile_choice.currentData() or HL.TILE_DEFAULT,
            "calendar_busier": self.busier.currentData() or "lighter",
            **self.style_values(),
        }

    def style_values(self) -> dict:
        """The debug switches, kept only where they differ from the tile style's own (None: as the
        style has it), so a later change to a style still reaches anyone who never touched them."""
        gaps, smooth = HL.TILE_STYLE[self.tile_choice.currentData() or HL.TILE_DEFAULT]
        return {"debug_gaps": None if self.gaps.isChecked() == gaps else self.gaps.isChecked(),
                "debug_smooth": None if self.smooth.isChecked() == smooth else self.smooth.isChecked()}

    def refresh(self) -> None:
        """Draw every picture again for the choices as they are now (and the theme)."""
        if self.refreshed:
            self.refreshed()
        # (Busier days only in dark mode; set once it has a parent: shown before, it flashes up as a window)
        if self.busier_box.parent() is not None:
            dark = page_bg()[1]
            self.busier_box.setVisible(dark)
        # a colour of your own that hardly stands out from a page: said, not changed (shown only
        # once in the tab: a widget shown before it has a parent flashes up as a window)
        mine_look = HL.preview_look(dict(self.edition_cfg, **self.values()), presets.by_key()[self.here].environment)
        faint = HL.faint_on(mine_look["colours"]) if self.source.currentData() == HL.MINE else []
        self.faint.setText(FAINT_NOTE.format(pages=" or ".join(PAGE_NAMES[p] for p in faint)) if faint else "")
        if self.faint.parent() is not None:
            self.faint.setVisible(bool(faint))
        state = (self.here, repr(sorted(self.values().items())), HL.debug_edition(self.edition_cfg), page_bg())
        if state == self._drawn:
            return
        self._drawn = state
        here_env = presets.by_key()[self.here].environment
        cfg = dict(self.edition_cfg, **self.values())
        # (each in the tiles chosen, as the heatmap's key draws them; a joined shape's as Flat's)
        drawn = HL.drawer_for(cfg, here_env)
        drawn = drawn if drawn in HL.DRAWERS else HL.TILE_DEFAULT
        self.scenery.setIcon(QIcon(strip(HL.preview_look(dict(cfg, calendar_colours=self.scenery.key), here_env), drawn)))
        for key, b in self.ready.items():
            look = HL.preview_look(dict(cfg, calendar_colours=HL.READY_PREFIX + key), here_env)
            b.setIcon(QIcon(strip(look, drawn)))
        self.yours.setIcon(QIcon(strip(HL.preview_look(dict(cfg, calendar_colours=HL.MINE), here_env), drawn)))
        for b, c in ((self.first, self.mine[0]), (self.second, self.mine[1])):
            icon = QIcon(swatch(c))
            icon.addPixmap(swatch(c), QIcon.Mode.Disabled)  # (unblended, the second keeps its colour, its button greyed)
            b.setIcon(icon)
        self.second.setEnabled(self.blend.isChecked())
        look = HL.preview_look(cfg, here_env)
        for key, b in self.tile_buttons.items():  # (each as its style draws it: its own spaces and corners)
            b.setIcon(QIcon(tile_sample(look, key, cfg, here_env)))

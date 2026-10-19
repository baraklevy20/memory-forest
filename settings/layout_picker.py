"""Layout (Forest tab, Where it shows): where the forest and the heatmap sit round the deck list,
chosen by picture (state.LAYOUTS), then the side a side column stands on (its width is the Forest
width's: web/core.js AF.arrange). Each picture
is a small sketch of the deck list, drawn here in whole pixels in the theme's greys and a forest's
greens, mirrored for the left side. Only the deck list follows it: a deck's screen, the finished-deck
page, Onigiri's tile and the phone keep the two stacked (web/core.js AF.arrange)."""

from __future__ import annotations

from aqt.qt import (
    QColor,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPixmap,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..state import (
    LAYOUT_DEFAULT,
    LAYOUTS,
    layout_key,
    layout_side,
)
from .palette import readable
from .widgets import Choice, JoinedChoice, hint, picture_button_style, pixel_ratio

# the presets, in the order shown: the two stacked ones first and last, the side ones between
LAYOUT_OPTIONS = [("under", "Under the list"), ("forest_side", "Forest beside"), ("both_side", "Both beside"),
                  ("heatmap_side", "Heatmap beside"), ("heatmap_first", "Heatmap first")]
LAYOUT_TIPS = {
    "under": "The forest under the deck list, the heatmap under the forest",
    "forest_side": "The forest beside the deck list, the heatmap under the list",
    "both_side": "The forest and the heatmap beside the deck list, one above the other",
    "heatmap_side": "The heatmap beside the deck list, the forest under the list",
    "heatmap_first": "The heatmap under the deck list, the forest under the heatmap",
}
SIDE_OPTIONS = [("right", "Right"), ("left", "Left")]
# (one line: SETTINGS_GUIDELINES.md)
LAYOUT_NOTE = "Beside the deck list while the window has room, under it otherwise. Deck screens keep them stacked."
TILE_GAP = 6  # points between two pictures
# a picture, in points (a point is one of its pixels at 1x, two on a Retina screen)
PIC_W, PIC_H = 60, 36
# its colours, (light, dark): the deck list's lines, the forest's sky, ground and trees, the heatmap's
# three shades
INK = ("#8c8c8c", "#8f8f8f")
SKY = ("#a9cdea", "#5f86ad")
GROUND = ("#7fb05a", "#5f9447")
TREES = ("#3f7a34", "#3a6e30")
SHADES = (("#cfe3b8", "#9ccc6b", "#4f8f3a"), ("#3c5a2f", "#6aa04a", "#a8d67e"))


def _rects(key: str) -> list:
    """The sketch of `key` with its side column on the right: (what, x, y, w, h) in its pixels."""
    if key == "forest_side":
        return [("list", 3, 3, 28, 13), ("forest", 35, 3, 22, 13), ("heat", 3, 26, 54, 2)]
    if key == "both_side":
        return [("list", 3, 3, 28, 13), ("forest", 35, 3, 22, 13), ("heat", 35, 20, 22, 3)]
    if key == "heatmap_side":
        return [("list", 3, 3, 28, 13), ("heat", 35, 3, 22, 3), ("forest", 3, 21, 54, 12)]
    if key == "heatmap_first":
        return [("list", 16, 2, 28, 13), ("heat", 15, 18, 30, 2), ("forest", 12, 25, 36, 10)]
    return [("list", 16, 2, 28, 13), ("forest", 12, 17, 36, 10), ("heat", 15, 29, 30, 2)]


def picture(key: str, side: str = "right") -> QPixmap:
    """The picture for preset `key`, its side column on `side`, in whole pixels for this screen."""
    dpr = max(1, round(pixel_ratio()))
    pm = QPixmap(PIC_W * dpr, PIC_H * dpr)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.scale(dpr, dpr)  # (whole pixels: each of the sketch's is dpr device pixels, never smoothed)
    mirror = side == "left" and LAYOUTS[key][0:2] != ("below", "below")
    shades = readable(SHADES)

    def fill(x, y, w, h, colour):
        p.fillRect(PIC_W - x - w if mirror else x, y, w, h, QColor(readable(colour) if isinstance(colour, tuple) else colour))

    for what, x, y, w, h in _rects(key):
        if what == "list":  # the deck list: a header, then each deck's name and its numbers
            for i in range(5):
                fill(x, y + i * 3, w - 8 if i else w, 1, INK)
                if i:
                    fill(x + w - 5, y + i * 3, 5, 1, INK)
        elif what == "forest":  # a strip of sky, ground and a row of trees
            sky = h * 2 // 5
            fill(x, y, w, sky, SKY)
            fill(x, y + sky, w, h - sky, GROUND)
            for t in range(x + 2, x + w - 2, 4):
                fill(t, y + sky - 2, 3, 3, TREES)
                fill(t + 1, y + sky - 3, 1, 1, TREES)
        else:  # the heatmap: `h` rows of days, 2 pixels each, one apart
            for row in range(h):
                for col, cx in enumerate(range(x, x + w - 1, 3)):
                    fill(cx, y + row * 3, 2, 2, shades[(col * 7 + row * 5) % 3])
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


class LayoutChoice(Choice):
    """The presets as pictures with their names under them, side by side, kept together on the
    row's left; the chosen one ringed as the Nature buttons are."""

    def __init__(self, value: str):
        self.pictures = {}
        super().__init__(LAYOUT_OPTIONS, value, LAYOUT_DEFAULT, gap=TILE_GAP, stretch=True)
        # (all as wide as the widest, so the row reads as one even choice)
        wide = max(b.minimumWidth() for b in self.buttons.values())
        for b in self.buttons.values():
            b.setFixedWidth(wide)

    def make_button(self, key, label: str):
        b = QPushButton()
        b.setCheckable(True)
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(LAYOUT_TIPS[key])
        b.setAccessibleName(label)
        b.setStyleSheet(picture_button_style(bold=False))
        v = QVBoxLayout(b)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)
        pic, name = QLabel(), QLabel(label)
        for w in (pic, name):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # (the button takes the click)
        name.setStyleSheet("font-size: 12px; background: transparent;")
        pic.setStyleSheet("background: transparent;")
        v.addWidget(pic)
        v.addWidget(name)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        b.setMinimumSize(v.sizeHint().width() + 4, PIC_H + 40)
        self.pictures[key] = pic
        return b

    def draw(self, side: str) -> None:
        for key, pic in self.pictures.items():
            pic.setPixmap(picture(key, side))


class LayoutControls:
    """The Layout row's parts: the pictures, then Side for a side column, greyed out while
    the chosen preset has none, with a line of help under them."""

    def __init__(self, cfg: dict):
        self.choice = LayoutChoice(layout_key(cfg))
        self.side = JoinedChoice(SIDE_OPTIONS, layout_side(cfg), "right")
        self.box = QWidget()
        v = QVBoxLayout(self.box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(self.choice)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.side_label = QLabel("Side")
        row.addWidget(self.side_label)
        row.addWidget(self.side)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(hint(LAYOUT_NOTE))
        self.side.on_change(self.sync)
        self.choice.on_change(self.sync)
        self.sync()

    def on_change(self, changed) -> None:
        self.choice.on_change(changed)
        self.side.on_change(changed)

    def sync(self) -> None:
        """Side only matters for a preset with a side column; the pictures follow it."""
        beside = LAYOUTS[self.choice.currentData()][0:2] != ("below", "below")
        for w in (self.side_label, self.side):
            w.setEnabled(beside)
        self.choice.draw(self.side.currentData())

    def values(self) -> dict:
        return {"layout": self.choice.currentData(), "layout_side": self.side.currentData()}

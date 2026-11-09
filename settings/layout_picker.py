"""Layout (Forest tab, Where it shows): where the forest and the heatmap sit round the deck list,
chosen by picture (state.LAYOUTS): both under it, both beside it, the First beside it and the other
under it, the First above it and the other under it, or the forest behind the list (filling the
window, the list and the heatmap on frosted cards over it: web/core.js AF.arrange). Then on one row the Side a column beside the
list stands on, and First: the one that gets the place beside or above the list, and comes first. Each picture is
a small sketch of the deck list, drawn here in whole pixels in the theme's greys and a forest's
greens, mirrored for the left side, the two in the order chosen. Only the deck list follows it: a
deck's screen, the finished-deck page, Onigiri's tile and the phone keep the two stacked under what
they have, in the First order (web/core.js AF.arrange); but Background, which a deck's screen and
the finished-deck page follow too. Background has its own Heatmap choice in First's place (First means
nothing there): under the list, or beside it on Side, on the list's screen."""

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

from ..i18n import N_, t, tx
from ..state import (
    LAYOUT_BEHIND_HEAT_DEFAULT,
    LAYOUT_DEFAULT,
    LAYOUTS,
    layout_behind_heatmap,
    layout_first,
    layout_key,
    layout_side,
)
from .palette import readable
from .widgets import Choice, JoinedChoice, hint, picture_button_style, pixel_ratio

# the layouts, in the order shown: under the list as it always was, both beside it, one beside it,
# one above it, the forest behind it
LAYOUT_OPTIONS = [("under", N_("settings.layout.under_the_list")), ("beside", N_("settings.layout.beside_it")),
                  ("one_beside", N_("settings.layout.one_beside")), ("above", N_("settings.layout.above_the_list")),
                  ("behind", N_("settings.layout.background"))]
LAYOUT_TIPS = {
    "under": N_("settings.layout.the_forest_and_the_heatmap_under"),
    "beside": N_("settings.layout.the_forest_and_the_heatmap_beside"),
    "one_beside": N_("settings.layout.the_first_beside_the_deck_list"),
    "above": N_("settings.layout.the_first_above_the_deck_list"),
    "behind": N_("settings.layout.the_forest_as_the_window_s_background"),
}
SIDE_OPTIONS = [("right", N_("settings.layout.right")), ("left", N_("settings.layout.left"))]
# which comes first where the two stand together, and which goes above the list with Above the list
FIRST_LABEL = N_("settings.layout.first")
FIRST_OPTIONS = [("forest", N_("settings.layout.forest")), ("heatmap", N_("settings.layout.heatmap"))]
FIRST_TIP = N_("settings.layout.the_one_that_goes_beside_or")
# Background's heatmap, in First's place: under the list or beside it (state.LAYOUT_BEHIND_HEAT)
HEAT_LABEL = N_("settings.layout.heatmap")
HEAT_OPTIONS = [("under", N_("settings.layout.under_the_list")), ("beside", N_("settings.layout.beside_it"))]
# (one line: SETTINGS_GUIDELINES.md)
LAYOUT_NOTE = N_("settings.layout.beside_the_list_while_the_window")
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
# Background's frosted card under the list's lines (the theme's page, a little see-through)
CARD = ("#e4ece6", "#3a4148")


def _rects(key: str, first: str = "forest", heat: str = "under") -> list:
    """The sketch of `key` with its side column on the right, the forest first or the heatmap
    (`first`), Background's heatmap under the list or beside it (`heat`): (what, x, y, w, h) in its pixels."""
    if key == "beside":
        if first == "heatmap":
            return [("list", 3, 3, 28, 13), ("heat", 35, 3, 22, 3), ("forest", 35, 14, 22, 13)]
        return [("list", 3, 3, 28, 13), ("forest", 35, 3, 22, 13), ("heat", 35, 20, 22, 3)]
    if key == "one_beside":
        if first == "heatmap":
            return [("list", 3, 3, 28, 13), ("heat", 35, 3, 22, 3), ("forest", 3, 21, 54, 12)]
        return [("list", 3, 3, 28, 13), ("forest", 35, 3, 22, 13), ("heat", 3, 26, 54, 2)]
    if key == "behind" and heat == "beside":  # (the list and the heatmap side by side on their cards over the sky)
        return [("forest", 0, 0, PIC_W, PIC_H), ("card", 4, 2, 30, 17), ("list", 6, 4, 26, 13), ("card", 37, 2, 20, 10), ("heat", 39, 4, 17, 3)]
    if key == "behind":  # the forest the whole picture, the list on its card over the sky, the heatmap under it
        return [("forest", 0, 0, PIC_W, PIC_H), ("card", 14, 2, 32, 17), ("list", 16, 4, 28, 13), ("heat", 15, 22, 30, 2)]
    if key == "above":
        if first == "heatmap":
            return [("heat", 15, 1, 30, 2), ("list", 16, 8, 28, 13), ("forest", 12, 24, 36, 10)]
        return [("forest", 12, 1, 36, 8), ("list", 16, 12, 28, 13), ("heat", 15, 28, 30, 2)]
    if first == "heatmap":
        return [("list", 16, 2, 28, 13), ("heat", 15, 18, 30, 2), ("forest", 12, 25, 36, 10)]
    return [("list", 16, 2, 28, 13), ("forest", 12, 17, 36, 10), ("heat", 15, 29, 30, 2)]


def picture(key: str, side: str = "right", first: str = "forest", heat: str = "under") -> QPixmap:
    """The picture for layout `key`, Beside's column on `side`, the two in the order `first`,
    Background's heatmap at `heat`, in whole pixels for this screen."""
    dpr = max(1, round(pixel_ratio()))
    pm = QPixmap(PIC_W * dpr, PIC_H * dpr)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.scale(dpr, dpr)  # (whole pixels: each of the sketch's is dpr device pixels, never smoothed)
    mirror = side == "left" and ("side" in LAYOUTS[key] or (key == "behind" and heat == "beside"))
    shades = readable(SHADES)

    def fill(x, y, w, h, colour):
        p.fillRect(PIC_W - x - w if mirror else x, y, w, h, QColor(readable(colour) if isinstance(colour, tuple) else colour))

    for what, x, y, w, h in _rects(key, first, heat):
        if what == "list":  # the deck list: a header, then each deck's name and its numbers
            for i in range(5):
                fill(x, y + i * 3, w - 8 if i else w, 1, INK)
                if i:
                    fill(x + w - 5, y + i * 3, 5, 1, INK)
        elif what == "card":
            fill(x, y, w, h, CARD)
        elif what == "forest":  # a strip of sky, ground and a row of trees
            sky = h * 2 // 5 if h < PIC_H else h * 7 // 10  # (behind the list: mostly sky, as the window is)
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


def shown(options) -> list:
    """Options with their labels in the reader's language (they are marked where they're written)."""
    return [(key, tx(label)) for key, label in options]


class LayoutChoice(Choice):
    """The layouts as pictures with their names under them, side by side, kept together on the
    row's left; the chosen one ringed as the Nature buttons are."""

    def __init__(self, value: str):
        self.pictures = {}
        super().__init__(shown(LAYOUT_OPTIONS), value, LAYOUT_DEFAULT, gap=TILE_GAP, stretch=True)
        # (all as wide as the widest, so the row reads as one even choice)
        wide = max(b.minimumWidth() for b in self.buttons.values())
        for b in self.buttons.values():
            b.setFixedWidth(wide)

    def make_button(self, key, label: str):
        b = QPushButton()
        b.setCheckable(True)
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(tx(LAYOUT_TIPS[key]))
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

    def draw(self, side: str, first: str = "forest", heat: str = "under") -> None:
        for key, pic in self.pictures.items():
            pic.setPixmap(picture(key, side, first, heat))


class LayoutControls:
    """The Layout row's parts: the pictures, then on one row Side, greyed out but for the layouts
    beside the list, and First (greyed out for none: every other layout stacks the two somewhere, a
    deck's screen at least), or with Background its Heatmap in First's place (Under the list | Beside
    it, Side then for its side), with a line of help under them."""

    def __init__(self, cfg: dict):
        self.choice = LayoutChoice(layout_key(cfg))
        self.side = JoinedChoice(shown(SIDE_OPTIONS), layout_side(cfg), "right")
        self.order = JoinedChoice(shown(FIRST_OPTIONS), layout_first(cfg), "forest")
        self.order.setToolTip(tx(FIRST_TIP))
        self.heat = JoinedChoice(shown(HEAT_OPTIONS), layout_behind_heatmap(cfg), LAYOUT_BEHIND_HEAT_DEFAULT)
        self.box = QWidget()
        v = QVBoxLayout(self.box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(self.choice)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.side_label = QLabel(t("settings.layout.side"))
        row.addWidget(self.side_label)
        row.addWidget(self.side)
        row.addSpacing(18)
        first = self.first_label = QLabel(tx(FIRST_LABEL))
        first.setToolTip(tx(FIRST_TIP))
        row.addWidget(first)
        row.addWidget(self.order)
        # (Background's own, in First's place: first, as First is, and Side after it as in every row)
        self.heat_label = QLabel(tx(HEAT_LABEL))
        row.insertWidget(0, self.heat)
        row.insertWidget(0, self.heat_label)
        self.heat_gap = QWidget()
        self.heat_gap.setFixedWidth(18)
        row.insertWidget(2, self.heat_gap)
        row.addStretch(1)
        v.addLayout(row)
        self.note = hint(tx(LAYOUT_NOTE))
        keep = self.note.sizePolicy()
        keep.setRetainSizeWhenHidden(True)  # (its row keeps its place: the rows under it don't jump as the layout is chosen)
        self.note.setSizePolicy(keep)
        v.addWidget(self.note)
        self.side.on_change(self.sync)
        self.order.on_change(self.sync)
        self.heat.on_change(self.sync)
        self.choice.on_change(self.sync)
        self.sync()

    def on_change(self, changed) -> None:
        self.choice.on_change(changed)
        self.side.on_change(changed)
        self.order.on_change(changed)
        self.heat.on_change(changed)

    def sync(self) -> None:
        """Side only matters beside the list; the pictures follow it, First and Background's Heatmap.
        Background shows its Heatmap in First's place, First meaning nothing there."""
        key = self.choice.currentData()
        behind = key == "behind"
        heat = self.heat.currentData()
        beside = "side" in LAYOUTS[key] or (behind and heat == "beside")
        for w in (self.side_label, self.side):
            w.setEnabled(beside)
        for w in (self.first_label, self.order):
            w.setVisible(not behind)
        for w in (self.heat_label, self.heat, self.heat_gap):
            w.setVisible(behind)
        # (it says deck screens keep them under the list: Background's don't)
        self.note.setVisible(not behind)
        self.choice.draw(self.side.currentData(), self.order.currentData(), heat)

    def values(self) -> dict:
        return {"layout": self.choice.currentData(), "layout_side": self.side.currentData(),
                "layout_first": self.order.currentData(), "layout_behind_heatmap": self.heat.currentData()}

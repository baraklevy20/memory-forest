"""The small pieces every tab of the settings dialog is built from."""

from __future__ import annotations

import re

from aqt.qt import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QCalendarWidget,
    QCheckBox,
    QColor,
    QComboBox,
    QDateEdit,
    QEvent,
    QFormLayout,
    QFrame,
    QGroupBox,
    QGuiApplication,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QLocale,
    QObject,
    QPixmap,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QTabBar,
    QTextCharFormat,
    QTimer,
    QToolButton,
    QTransform,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from .palette import ERROR, HINT, LINK, chevron, color, radius, readable

# a choice drawn as a picture and a word (Nature's levels, the heatmap's colours and styles): the
# chosen one ringed as a focused field is in Anki, and in bold where `bold`
PICTURE_BUTTON_STYLE = """
QPushButton {{ border: 1px solid {line}; border-radius: 7px; padding: 6px 10px; font-size: 13px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ border: 2px solid {ring}; padding: 5px 9px; background: rgba(128, 128, 128, 0.16);{weight} }}
"""


def picture_button_style(bold: bool = True) -> str:
    return PICTURE_BUTTON_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS"),
                                       weight=" font-weight: bold;" if bold else "")


def direction() -> Qt.LayoutDirection:
    """The way the add-on's words read (i18n.direction): right to left for a right-to-left language
    (Hebrew, Arabic, Persian..., or the made-up en-XB), else left to right, whatever Anki's own
    language is, so the dialog matches its words."""
    return Qt.LayoutDirection.RightToLeft if i18n.direction() == "rtl" else Qt.LayoutDirection.LeftToRight


def rtl() -> bool:
    """Whether the dialog reads right to left (for what is decided before a widget has a parent)."""
    return i18n.direction() == "rtl"


def app_rtl() -> bool:
    """Whether Anki itself reads right to left (its own language): what Qt lays out a painted line,
    a button's words and a style sheet's text-align by, whatever the widget's direction."""
    return QGuiApplication.layoutDirection() == Qt.LayoutDirection.RightToLeft


def mirror_css(css: str, on: bool | None = None) -> str:
    """A style sheet with its left and right swapped, right to left (`on`, else the dialog's way): Qt's
    style sheets never swap a border-left, a top-left corner or a text-align themselves."""
    if not (rtl() if on is None else on):
        return css
    return re.sub(r"\b(left|right)\b", lambda m: "right" if m.group(1) == "left" else "left", css)


def leading(widget: QWidget | None = None):
    """Text set at the start of its line, as the words read: the left, or the right right to
    left. Absolute, as Qt goes by Anki's direction or the text's own otherwise (made-up en-XB, or a
    right-to-left line that starts with "Memory Forest", would sit on the left; a German one on the
    right in a right-to-left Anki)."""
    if widget.isRightToLeft() if widget is not None else rtl():
        return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute
    if app_rtl():
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
    return Qt.AlignmentFlag.AlignLeft


def forward(widget: QWidget, key) -> int:
    """+1 or -1: the next or the previous of a row for an arrow key, Right going back right to left."""
    ahead = key in (Qt.Key.Key_Right, Qt.Key.Key_Down)
    if widget.isRightToLeft() and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
        ahead = not ahead
    return 1 if ahead else -1


# a line's words embedded the dialog's way (RLE or LRE ... PDF): Qt lays out a button's, a check box's,
# a tab's, a group's title, a combo's and a painted text in Anki's direction, not the widget's, so in
# an English Anki a right-to-left line with "Patreon" in it came out in the wrong order (and in a
# right-to-left Anki, a German one with its full stop in front); a label goes by its text
RLE, LRE, PDF = "\u202b", "\u202a", "\u202c"
# and a label's lines go by its first letter's way: a mark that reads right to left before it ("Memory
# Forest גדל..." put "Memory Forest" on the right otherwise)
RLM = "\u200f"
TAG = re.compile(r"<[a-zA-Z!/][^>]*>")


def unmarked(text: str) -> str:
    return text.replace(RLE, "").replace(LRE, "").replace(PDF, "").replace(RLM, "")


def bidi(text: str, on: bool | None = None) -> str:
    """`text` with each line read right to left (`on`, else the words' way) or left to right, where
    that isn't Anki's way already; as it is otherwise (an English add-on in an English Anki)."""
    on = rtl() if on is None else on
    if not text or on == app_rtl():
        return text
    mark = RLE if on else LRE
    return "\n".join(mark + line + PDF for line in unmarked(text).split("\n"))


class _Bidi(QObject):
    """Keeps a control's words embedded the dialog's way (bidi) when its text is set again later (a
    dropdown's button naming the one picked, a link naming the scenery), as it is next drawn."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint:
            _embed(obj)
        return False


def _embed(w: QWidget) -> None:
    on = w.isRightToLeft()
    if isinstance(w, QLabel):
        text = w.text()
        if on and text and not text.startswith(RLM):
            # (Qt takes a text for rich text by a tag on its first line: the mark before it would
            # make it plain, its tags shown, so a label read as rich text is told it is)
            if w.textFormat() == Qt.TextFormat.AutoText and TAG.search(text.lstrip().split("\n", 1)[0]):
                w.setTextFormat(Qt.TextFormat.RichText)
            w.setText(RLM + text)
    elif isinstance(w, QAbstractButton):
        if w.text() != bidi(w.text(), on):
            w.setText(bidi(w.text(), on))
    elif isinstance(w, QGroupBox):
        if w.title() != bidi(w.title(), on):
            w.setTitle(bidi(w.title(), on))
    elif isinstance(w, QTabBar):
        for i in range(w.count()):
            if w.tabText(i) != bidi(w.tabText(i), on):
                w.setTabText(i, bidi(w.tabText(i), on))
    elif isinstance(w, QComboBox):
        for i in range(w.count()):
            if w.itemText(i) != bidi(w.itemText(i), on):
                w.setItemText(i, bidi(w.itemText(i), on))


def mirror(root: QWidget) -> None:
    """Where the dialog's direction isn't plain left to right in a left-to-right Anki: set every label
    and text field under `root` at the start of its lines, the words' way (the right right to left;
    centred ones stay), and embed the controls' words the words' way (bidi), now and whenever they
    change. Qt's own controls mirror their layout by themselves."""
    if not (root.isRightToLeft() or app_rtl()):
        return
    if not root.window().testAttribute(Qt.WidgetAttribute.WA_SetLayoutDirection):
        return  # (not in the dialog yet, so in Anki's direction for now: the dialog's own call does it)
    side = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignJustify
    for w in [root] + root.findChildren(QWidget):
        if isinstance(w, (QLabel, QLineEdit)):
            a = w.alignment()
            if not (a & Qt.AlignmentFlag.AlignHCenter or a & Qt.AlignmentFlag.AlignAbsolute):
                start = Qt.AlignmentFlag.AlignRight if w.isRightToLeft() else Qt.AlignmentFlag.AlignLeft
                w.setAlignment((a & ~side) | start | Qt.AlignmentFlag.AlignAbsolute)
        if isinstance(w, (QLabel, QAbstractButton, QGroupBox, QTabBar, QComboBox)) and not w.property("af_bidi"):
            if isinstance(w, QAbstractButton) and not w.text():
                continue  # (a picture: a scenery's tile draws its own name)
            w.setProperty("af_bidi", True)
            if w.isRightToLeft() and mac_native():
                _mac_right_to_left(w)
            _embed(w)
            w.installEventFilter(_Bidi(w))


def mac_native() -> bool:
    """Whether the dialog is drawn in macOS's own style (Anki's native look on a Mac)."""
    style = QApplication.style()
    return style is not None and style.objectName().lower() in ("macos", "macintosh")


# macOS's own dropdown is drawn left to right whatever the widget's direction (its arrows on the right,
# its words on the left): right to left, a dropdown drawn by a style sheet instead, its arrow on the left
RTL_COMBO_STYLE = """
QComboBox {{ border: 1px solid {line}; border-radius: {radius}; padding: 3px 8px 3px 24px;
            background: {ground}; color: {fg}; }}
QComboBox:focus, QComboBox:on {{ border-color: {focus}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center left; width: 20px; border: none; }}
"""


def _mac_right_to_left(w: QWidget) -> None:
    """macOS's style right to left: its dropdowns drawn by a style sheet (RTL_COMBO_STYLE), and a space
    between a check box's or a radio button's box and its words, which it puts flush otherwise."""
    if isinstance(w, QComboBox) and not w.styleSheet():
        arrow = chevron()
        w.setStyleSheet(RTL_COMBO_STYLE.format(line=color("BORDER_SUBTLE"), radius=radius(), ground=color("BUTTON_BG"),
                                               fg=color("FG"), focus=color("BORDER_FOCUS"))
                        + (f"QComboBox::down-arrow {{ image: url({arrow}); width: 12px; height: 12px; }}" if arrow else ""))
    elif isinstance(w, (QCheckBox, QRadioButton)) and w.text():
        w.setText("\u2002" + unmarked(w.text()))  # (an en space: at the words' start, beside the box)


def follow_direction(widget: QWidget) -> QWidget:
    """A window of its own (a message box, a menu) takes the app's direction, not its parent's:
    set it to the words' direction."""
    widget.setLayoutDirection(direction())
    return widget


def pixel_ratio() -> float:
    """The main screen's device pixels a point."""
    screen = QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


# room inside a group's frame, and between its title and the frame (the title is a label
# of its own, because native styles such as macOS's set it flush on the frame)
GROUP_MARGINS = (12, 10, 12, 10)
GROUP_TITLE_GAP = 6
HINT_PX = 12
# between radio buttons side by side, and one above another
CHOICE_GAP, CHOICE_ROW_GAP = 14, 4


def combo(options, value, fallback=None) -> QComboBox:
    """A dropdown on `value`. A value it doesn't offer (a hand edit, or one from an older
    version) shows `fallback` instead of whatever happens to be first."""
    box = QComboBox()
    for key, label in options:
        box.addItem(label, key)
    i = box.findData(value)
    if i < 0 and fallback is not None:
        i = box.findData(fallback)
    box.setCurrentIndex(max(i, 0))
    return box


class Choice(QWidget):
    """Two to five choices as radio buttons, every one in view (a dropdown would hide them),
    side by side or one above another. Read and set like a combo: by each choice's data.
    A subclass can draw its choices as other checkable buttons (make_button)."""

    def __init__(self, options, value, fallback=None, vertical: bool = False, gap: int | None = None, stretch: bool = True):
        super().__init__()
        self.group = QButtonGroup(self)
        self.buttons = {}
        lay = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(gap if gap is not None else CHOICE_ROW_GAP if vertical else CHOICE_GAP)
        for key, label in options:
            b = self.make_button(key, label)
            self.group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b)
        if stretch and not vertical:
            lay.addStretch(1)
        # a value it doesn't offer (a hand edit, or one from an older version) shows `fallback`
        try:
            offered = value in self.buttons
        except TypeError:  # (a list or an object, hand-edited in: no choice's key)
            offered = False
        self.set_quietly(value if offered else fallback)
        if self.currentData() is None and self.buttons:
            self.set_quietly(next(iter(self.buttons)))

    def make_button(self, _key, label: str):
        return QRadioButton(label)

    def setFocus(self) -> None:
        """Focus the chosen button (a note pointing here, news.py): the group itself takes none."""
        button = self.buttons.get(self.currentData())
        if button is not None:
            button.setFocus()

    def currentData(self):
        return next((k for k, b in self.buttons.items() if b.isChecked()), None)

    def set_quietly(self, value) -> None:
        """Choose `value` without announcing a change."""
        button = self.buttons.get(value)
        if button is None:
            return
        self.group.blockSignals(True)
        button.setChecked(True)
        self.group.blockSignals(False)

    def on_change(self, changed) -> None:
        """Call `changed()` once a choice is made (not again for the one it replaces)."""
        self.group.buttonToggled.connect(lambda _b, on: on and changed())


# a few short choices as joined buttons, one control, the chosen one a soft grey with a blue edge (a
# solid blue was the loudest thing on the tab; the corners rounded only at the row's two ends): the
# Heatmap tab's week start, Busier days
JOINED_STYLE = """
QPushButton {{ border: 1px solid {line}; border-left-width: {left}px; border-radius: 0; padding: 3px 10px 3px {pad}px;
              border-top-left-radius: {r0}px; border-bottom-left-radius: {r0}px;
              border-top-right-radius: {r1}px; border-bottom-right-radius: {r1}px;
              background: rgba(128, 128, 128, 0.10); }}
QPushButton:hover {{ background: rgba(128, 128, 128, 0.20); }}
QPushButton:checked {{ background: rgba(128, 128, 128, 0.38); border-color: {ring}; border-left-width: 1px; padding-left: {pad_on}px; }}
QPushButton:disabled {{ color: {off}; background: rgba(128, 128, 128, 0.05); }}
QPushButton:checked:disabled {{ color: {off}; background: rgba(128, 128, 128, 0.22); border-color: {line}; }}
"""
# (a button after the first has no left border, its neighbour's right one between them; chosen, its
# ring needs all four sides: its left border comes back, a pixel of padding giving way, so it keeps
# its width)
JOINED_PAD = 10
JOINED_RADIUS = 6


class JoinedChoice(Choice):
    """A few short choices as a row of joined buttons (JOINED_STYLE), as wide as they are; `tips`,
    each one's tooltip. One Tab stop, the chosen one, and the arrow keys from one to the next, as
    round radio buttons have (push buttons are each a Tab stop of their own, with no arrows)."""

    def __init__(self, options, value, fallback=None, tips: dict | None = None):
        self.keys, self.tips = [k for k, _label in options], tips or {}
        super().__init__(options, value, fallback, gap=0, stretch=False)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)  # (its own width, not the row's)
        for b in self.buttons.values():
            b.installEventFilter(self)
        self.group.buttonToggled.connect(lambda _b, _on: self._tab_stop())
        self._tab_stop()

    def _tab_stop(self) -> None:
        for b in self.buttons.values():
            b.setFocusPolicy(Qt.FocusPolicy.StrongFocus if b.isChecked() else Qt.FocusPolicy.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            keys = list(self.buttons)
            at = keys.index(self.currentData()) + forward(obj, event.key())
            if 0 <= at < len(keys):
                self.buttons[keys[at]].setChecked(True)
                self.buttons[keys[at]].setFocus()
            return True
        return False

    def label_for(self, key, label: str) -> tuple:
        """(the button's words, its tooltip)."""
        return label, self.tips.get(key, "")

    def make_button(self, key, label: str):
        at = self.keys.index(key)
        first, last = at == 0, at == len(self.keys) - 1
        label, tip = self.label_for(key, label)
        b = QPushButton(label)
        if tip:
            b.setToolTip(tip)
        b.setAutoDefault(False)  # Enter in the dialog means Done
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(mirror_css(JOINED_STYLE.format(line=color("BORDER_SUBTLE"), ring=color("BORDER_FOCUS"), off=color("FG_DISABLED"),
                                            left=1 if first else 0, pad=JOINED_PAD, pad_on=JOINED_PAD - (0 if first else 1),
                                            r0=JOINED_RADIUS if first else 0, r1=JOINED_RADIUS if last else 0)))  # (right to left the first is the rightmost)
        return b


class Link(QLabel):
    """A line of text that does something when clicked (or on Space or Enter while it has the
    focus), in a link's colour: a label rather than a tool button, which Anki's style keeps
    smaller than the text around it, whatever its own style sheet says."""

    def __init__(self, text: str, on_click):
        super().__init__(text)
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # (greyed out while what it opens has nothing to say: the hint's grey, no underline)
        self.setStyleSheet(f"QLabel {{ color: {readable(LINK)}; }} QLabel:focus, QLabel:hover {{ text-decoration: underline; }}"
                           f" QLabel:disabled {{ color: {readable(HINT)}; text-decoration: none; }}")

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.EnabledChange:
            self.setCursor(Qt.CursorShape.PointingHandCursor if self.isEnabled() else Qt.CursorShape.ArrowCursor)
        super().changeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.on_click()
        else:
            super().keyPressEvent(event)


class Tab(QWidget):
    """A settings tab with wrapped help in it. A dialog goes by its contents' plain size hints,
    which leave too little room for wrapped text, and the rows are then squeezed (the gaps
    between groups first); this asks for the height the help needs at the tab's width. Qt asks
    again whenever anything in the tab changes, so the dialog's minimum always keeps up."""

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        width = self.width() if self.width() > 0 else hint.width()
        return QSize(hint.width(), max(hint.height(), self.heightForWidth(max(width, hint.width()))))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit()

    def fit(self) -> None:
        grow_window(self)


def form() -> QFormLayout:
    """A form laid out the same everywhere: labels on the left and fields filling the rest.
    macOS's own form centres itself and leaves each field at its smallest, so rows of radio
    buttons would float in the middle of their group."""
    out = QFormLayout()
    out.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    out.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    out.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return out


def group(title: str, layout, beside: QWidget | None = None) -> QWidget:
    """A titled group: the title, a little room, then `layout` inside a frame. `beside` goes on
    the title's row, at its right (the scenery picker's search); the row keeps its height
    while it is hidden, so nothing below moves as it comes and goes."""
    layout.setContentsMargins(*GROUP_MARGINS)
    frame = QGroupBox()
    frame.setLayout(layout)
    out = QWidget()
    v = QVBoxLayout(out)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(GROUP_TITLE_GAP)
    out.title = QLabel(title)  # (a note can tag it NEW: settings/whats_new.py)
    if beside is None:
        v.addWidget(out.title)
    else:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(out.title, 0, Qt.AlignmentFlag.AlignBottom)
        h.addStretch(1)
        h.addWidget(beside)
        row.setMinimumHeight(beside.sizeHint().height())
        v.addWidget(row)
    v.addWidget(frame)
    return out


def date_field(display_format: str) -> QDateEdit:
    """A date box with a calendar popup, styled like Anki's own dropdowns. Anki's theme
    leaves the date edit half-styled: the text box inside gets a frame of its own, the
    arrow keeps the native look, and the calendar paints weekends red on a blue bar."""
    box = QDateEdit()
    box.setCalendarPopup(True)
    # (its months and weekdays in the add-on's language, which Qt's own locale need not be)
    here = QLocale(i18n.format_lang().replace("-", "_"))
    box.setLocale(here)
    box.calendarWidget().setLocale(here)
    box.setDisplayFormat(display_format)
    box.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
    arrow = chevron()
    box.setStyleSheet(f"""
    QDateEdit {{
        padding: 2px 4px 2px 6px;
        border: 1px solid {color("BORDER_SUBTLE")};
        border-radius: {radius()};
        background: {color("CANVAS_CODE")};
    }}
    QDateEdit:focus, QDateEdit:on {{ border-color: {color("BORDER_FOCUS")}; }}
    QDateEdit QLineEdit {{ border: none; background: transparent; padding: 0; }}
    QDateEdit::drop-down {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 20px;
        border: none;
    }}
    """ + (f"QDateEdit::down-arrow {{ image: url({arrow}); }}" if arrow else ""))
    cal = box.calendarWidget()
    cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    cal.setStyleSheet(f"""
    QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {color("CANVAS_ELEVATED")}; }}
    QCalendarWidget QToolButton {{
        color: {color("FG")};
        background: transparent;
        border: none;
        border-radius: {radius()};
        padding: 3px 6px;
    }}
    QCalendarWidget QToolButton:hover {{ background: {color("BUTTON_BG")}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QAbstractItemView {{
        background: {color("CANVAS_ELEVATED")};
        color: {color("FG")};
        selection-background-color: {color("BORDER_FOCUS")};
        selection-color: white;
        outline: none;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {color("FG_DISABLED")}; }}
    """)
    # weekends like any other day
    plain = QTextCharFormat()
    plain.setForeground(QColor(color("FG")))
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        cal.setWeekdayTextFormat(day, plain)
    # Anki ships only an up and a down chevron, so the month arrows are the down one turned
    down = QPixmap(arrow) if arrow else QPixmap()  # an Anki without themed icons: Qt's own arrows
    # (its pop-up is a window of its own, which would read as Anki does: the words' way, the month
    # before on the right right to left, its arrow pointing right)
    cal.setLayoutDirection(direction())
    back = -90 if rtl() else 90
    for name, angle in (("qt_calendar_prevmonth", back), ("qt_calendar_nextmonth", -back)):
        button = cal.findChild(QToolButton, name)
        if button is not None and not down.isNull():
            button.setIcon(QIcon(down.transformed(QTransform().rotate(angle))))
    return box


def grow_window(widget: QWidget) -> None:
    """Grow the window `widget` is in if it now needs more room than it has. A window already
    up doesn't grow by itself when something inside it asks for more height (a tab whose
    help text got longer), and its layout then takes the room out of the gaps between rows."""
    win = widget.window()
    if win is widget or not win.isVisible():
        return
    need = win.minimumSizeHint().height()
    if win.height() < need:
        win.resize(win.width(), need)


def resize_with(widget: QWidget, change, tries: int = 5) -> None:
    """Call `change()`, which makes the window `widget` is in want another height (a page of a
    different height in view), then resize the window to it, keeping any room the user added
    by resizing it. Qt takes a turn or two of the event loop to update a window's minimum size,
    and until then it won't get shorter, so this waits for them."""
    win = widget.window()
    if win is widget:  # (not in a window yet: nothing to resize)
        change()
        return
    # (a window not shown yet, as the dialog opens on Customize, is fitted once it is up)
    old = win.minimumSizeHint().height()
    extra = max(0, win.height() - old)

    def fit(left: int) -> None:
        want = win.minimumSizeHint().height() + extra
        if left > 0 and (win.minimumSizeHint().height() == old or want < win.minimumHeight()):
            QTimer.singleShot(0, lambda: fit(left - 1))
            return
        win.resize(win.width(), max(want, win.minimumHeight()))
    change()
    QTimer.singleShot(0, lambda: fit(tries))

def hint_style() -> str:
    return f"color: {readable(HINT)}; font-size: {HINT_PX}px;"


def error_style() -> str:
    return f"color: {readable(ERROR)}; font-size: {HINT_PX}px;"


def hint(text: str) -> QLabel:
    """A line of help under a setting, in a grey that reads at 4.5:1 or better."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(hint_style())
    return label


def set_options(box: QComboBox, options) -> None:
    """Offer these options instead, without announcing a change, keeping the current one
    where it is still offered."""
    if [(box.itemData(i), unmarked(box.itemText(i))) for i in range(box.count())] == list(options):
        return
    current = box.currentData()
    box.blockSignals(True)
    box.clear()
    for key, label in options:
        box.addItem(label, key)
    box.setCurrentIndex(max(box.findData(current), 0))
    box.blockSignals(False)


def set_quietly(box: QComboBox, value) -> None:
    """Point a combo at a value without it announcing a change."""
    box.blockSignals(True)
    i = box.findData(value)
    if i >= 0:
        box.setCurrentIndex(i)
    box.blockSignals(False)


SCROLL_MIN_H = 320  # points: the least a scrolling tab asks for (a short screen scrolls the rest)


class Scrolled(QScrollArea):
    """A tab that scrolls on a screen too short for it (the Forest tab): as big as its contents
    where there is room, so it opens like any other tab, and only as small as SCROLL_MIN_H asks
    where there isn't, the rest a scroll away."""

    def __init__(self, tab: QWidget, cap=None):
        super().__init__()
        self.cap = cap  # () -> the most it asks for, so a long tab doesn't make every tab as tall
        self.setWidget(tab)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        tab.setAutoFillBackground(False)

    def bar(self) -> int:
        """The room the vertical scroll bar takes when it shows, kept beside the tab so it never
        covers or squeezes it."""
        return self.verticalScrollBar().sizeHint().width()

    def sizeHint(self) -> QSize:
        inner = self.widget().minimumSizeHint().expandedTo(self.widget().sizeHint())
        height = inner.height() if self.cap is None else min(inner.height(), max(SCROLL_MIN_H, self.cap()))
        return QSize(inner.width() + self.bar(), height + 2 * self.frameWidth())

    def minimumSizeHint(self) -> QSize:
        return QSize(self.widget().minimumSizeHint().width() + self.bar(), SCROLL_MIN_H)

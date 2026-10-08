"""The small pieces every tab of the settings dialog is built from."""

from __future__ import annotations

from aqt.qt import (
    QCalendarWidget,
    QColor,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QIcon,
    QLabel,
    QPixmap,
    Qt,
    QTextCharFormat,
    QToolButton,
    QTransform,
    QVBoxLayout,
    QWidget,
)

from .palette import chevron, color, radius

# room inside a group's frame, and between its title and the frame (the title is a label
# of its own, because native styles such as macOS's set it flush on the frame)
GROUP_MARGINS = (12, 10, 12, 10)
GROUP_TITLE_GAP = 6


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


def group(title: str, layout) -> QWidget:
    """A titled group: the title, a little room, then `layout` inside a frame."""
    layout.setContentsMargins(*GROUP_MARGINS)
    frame = QGroupBox()
    frame.setLayout(layout)
    out = QWidget()
    v = QVBoxLayout(out)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(GROUP_TITLE_GAP)
    out.title = QLabel(title)  # (a note can tag it NEW: settings/whats_new.py)
    v.addWidget(out.title)
    v.addWidget(frame)
    return out


def date_field(display_format: str) -> QDateEdit:
    """A date box with a calendar popup, styled like Anki's own dropdowns. Anki's theme
    leaves the date edit half-styled: the text box inside gets a frame of its own, the
    arrow keeps the native look, and the calendar paints weekends red on a blue bar."""
    box = QDateEdit()
    box.setCalendarPopup(True)
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
    for name, angle in (("qt_calendar_prevmonth", 90), ("qt_calendar_nextmonth", -90)):
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


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray; font-size: 11px;")
    return label


def set_options(box: QComboBox, options) -> None:
    """Offer these options instead, without announcing a change, keeping the current one
    where it is still offered."""
    if [(box.itemData(i), box.itemText(i)) for i in range(box.count())] == list(options):
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

"""The small pieces every tab of the settings dialog is built from."""

from __future__ import annotations

from aqt.qt import QComboBox, QGroupBox, QLabel, QVBoxLayout, QWidget

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
    v.addWidget(QLabel(title))
    v.addWidget(frame)
    return out


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray; font-size: 11px;")
    return label


def set_quietly(box: QComboBox, value) -> None:
    """Point a combo at a value without it announcing a change."""
    box.blockSignals(True)
    i = box.findData(value)
    if i >= 0:
        box.setCurrentIndex(i)
    box.blockSignals(False)

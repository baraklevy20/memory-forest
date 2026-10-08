"""NEW on a setting: where a note's button (news.py) points in the settings, tagged so it is
found at a glance. Any setting a tab names (its news_targets) can be pointed at; the tag
goes where it reads best for the layout the setting sits in. A label (a group's title, say)
is tagged in its own text: point at one to mark a whole group of controls."""

from __future__ import annotations

from aqt.qt import QBoxLayout, QFormLayout, QHBoxLayout, QLabel, QLayout, QSizePolicy, Qt, QWidget

NEW_TAG = "NEW"
NEW_STYLE = "color: white; background: #2f8f52; border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: bold;"
# on a form's label, where a stylesheet can't reach: the same colours as rich text
NEW_HTML = ' <span style="background-color: #2f8f52; color: white; font-size: 10px; font-weight: bold;">&nbsp;NEW&nbsp;</span>'


def pill() -> QLabel:
    label = QLabel(NEW_TAG)
    label.setStyleSheet(NEW_STYLE)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return label


def _holds(item, widget: QWidget) -> bool:
    """Whether a layout item is the widget, or a layout with it somewhere inside."""
    if item is None:
        return False
    if item.widget() is widget:
        return True
    inner = item.layout()
    return inner is not None and any(_holds(inner.itemAt(i), widget) for i in range(inner.count()))


def _form_label(root: QWidget, widget: QWidget) -> QLabel | None:
    """The label of the form row the widget is in (its field, or part of it), if it is in one."""
    for form in root.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            if _holds(form.itemAt(row, QFormLayout.ItemRole.FieldRole), widget):
                label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label is not None and isinstance(label.widget(), QLabel):
                    return label.widget()
    return None


def _box(root: QWidget, widget: QWidget) -> QBoxLayout | None:
    """The row or column the widget sits in directly."""
    layouts = ([root.layout()] if root.layout() else []) + root.findChildren(QLayout)
    return next((lay for lay in layouts if isinstance(lay, QBoxLayout) and lay.indexOf(widget) >= 0), None)


def _tag_label(root: QWidget, label: QLabel) -> None:
    fixed = label.minimumWidth() if label.minimumWidth() == label.maximumWidth() else 0
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(label.text() + NEW_HTML)
    # labels made one width (as Fine-tuning's are) all grow to keep the tag, and in line
    if fixed and label.sizeHint().width() > fixed:
        wider = label.sizeHint().width()
        for other in root.findChildren(QLabel):
            if other.minimumWidth() == fixed == other.maximumWidth():
                other.setFixedWidth(wider)


def tag(root: QWidget, widget: QWidget) -> bool:
    """Tag the widget NEW (once): a label in its own text, a form row's field on its label,
    or anything else beside it - after it in a row, or in a row of its own made around it in
    a column. False if it can't be placed."""
    if widget.property("af_new"):
        return True
    label = widget if isinstance(widget, QLabel) else _form_label(root, widget)
    if label is not None:
        _tag_label(root, label)
    else:
        box = _box(root, widget)
        if box is None:
            return False
        i = box.indexOf(widget)
        if box.direction() in (QBoxLayout.Direction.LeftToRight, QBoxLayout.Direction.RightToLeft):
            box.insertWidget(i + 1, pill(), 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            stretch = box.stretch(i)
            box.removeWidget(widget)
            row = QHBoxLayout()
            # a group of controls (it has a layout) or a widget that asks for room keeps the column's width
            wide = widget.layout() is not None or widget.sizePolicy().horizontalPolicy() in (
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            row.addWidget(widget, 1 if wide else 0)
            row.addWidget(pill(), 0, Qt.AlignmentFlag.AlignTop if widget.sizeHint().height() > 40 else Qt.AlignmentFlag.AlignVCenter)
            if not wide:
                row.addStretch(1)
            box.insertLayout(i, row, stretch)
    widget.setProperty("af_new", True)
    return True

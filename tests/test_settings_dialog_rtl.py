"""The settings dialog reads the way its words do: right to left in Hebrew (or the made-up en-XB),
left to right in English even inside a right-to-left Anki. Skipped without PyQt6: see settings_qt.py."""

from __future__ import annotations

import sys
import types
import unittest

import settings_qt as Q
from settings_qt import QtCase, addon

if Q.HAVE_QT:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QIcon, QPixmap
    from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QMenu


class DirectionTests(QtCase):
    def speak(self, lang: str):
        """Open the dialog in `lang`, as the Debug tab's Language does."""
        i18n = sys.modules[Q.PACKAGE + ".i18n"]
        was = addon.s_dialog.language
        addon.s_dialog.language = lambda _cfg: lang
        self.addCleanup(setattr, addon.s_dialog, "language", was)
        self.addCleanup(i18n.set_override, None)
        return self.open_dialog({})

    def test_right_to_left_in_a_right_to_left_language(self):
        d = self.speak("en-XB")
        self.assertEqual(d.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        self.assertTrue(d.tabs.isRightToLeft())
        w = addon.s_widgets
        # (Qt lays out a button's words in the app's direction: they're embedded right to left)
        done = next(b for b in d.findChildren(QDialogButtonBox)[0].buttons() if b.text())
        self.assertTrue(done.text().startswith(w.RLE))
        # a label starts its lines on the right, whatever its first letter
        hint = next(lab for lab in d.findChildren(QLabel) if lab.text() and lab.wordWrap() and lab.isVisible())
        self.assertTrue(hint.alignment() & Qt.AlignmentFlag.AlignRight)
        self.assertTrue(hint.text().startswith(w.RLM))

    def test_english_stays_left_to_right_in_a_right_to_left_anki(self):
        QApplication.instance().setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.addCleanup(QApplication.instance().setLayoutDirection, Qt.LayoutDirection.LeftToRight)
        d = self.speak("en")
        self.assertEqual(d.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        self.assertFalse(any(addon.s_widgets.RLE in b.text() for b in d.findChildren(QDialogButtonBox)[0].buttons()))

    def test_cancel_in_the_add_ons_words(self):
        d = self.speak("de")
        cancel = d.findChildren(QDialogButtonBox)[0].button(QDialogButtonBox.StandardButton.Cancel)
        self.assertEqual(cancel.text(), "Abbrechen")


class HelperTests(unittest.TestCase):
    """The pieces right to left is made of, without a dialog."""

    @unittest.skipUnless(Q.HAVE_QT, Q.SKIP)
    def test_style_sheets_swap_sides(self):
        css = "QPushButton { border-left-width: 1px; border-top-right-radius: 6px; text-align: left; }"
        w = addon.s_widgets
        self.assertEqual(w.mirror_css(css, False), css)
        self.assertEqual(w.mirror_css(css, True),
                         "QPushButton { border-right-width: 1px; border-top-left-radius: 6px; text-align: right; }")

    @unittest.skipUnless(Q.HAVE_QT, Q.SKIP)
    def test_each_line_embedded_once(self):
        w = addon.s_widgets
        once = w.bidi("one\ntwo", True)
        self.assertEqual(once, f"{w.RLE}one{w.PDF}\n{w.RLE}two{w.PDF}")
        self.assertEqual(w.bidi(once, True), once)
        self.assertEqual(w.bidi("one", False), "one")


class MenuTests(QtCase):
    """A right-to-left menu (the heatmap's Scenery and tile dropdowns) draws each picture on the right
    and its name against it, on its left: macOS's style draws them left to right whatever the
    menu's direction, and Qt's own does the words so in a left-to-right Anki."""

    def rows(self, app_direction):
        QApplication.instance().setLayoutDirection(app_direction)
        self.addCleanup(QApplication.instance().setLayoutDirection, Qt.LayoutDirection.LeftToRight)
        menu = QMenu()
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        menu._style = addon.s_heatmap_look._MenuRightToLeft()
        menu.setStyle(menu._style)
        red = QPixmap(16, 16)
        red.fill(QColor(255, 0, 0))
        for name in ("Synthwave", "Lofi room"):
            menu.addAction(QIcon(red), name).setIconVisibleInMenu(True)
        menu.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        menu.show()
        img = menu.grab().toImage()
        menu.close()
        y = menu.actionGeometry(menu.actions()[0]).center().y() * img.height() // menu.height()
        row = [img.pixelColor(x, y) for x in range(img.width())]
        icon = [x for x, c in enumerate(row) if c.red() > 200 and c.green() < 60 and c.blue() < 60]
        back = row[1]
        words = [x for x, c in enumerate(row) if 4 <= x < len(row) - 4 and x not in icon and abs(c.lightness() - back.lightness()) > 60]
        return img.width(), icon, words

    def check(self, app_direction):
        width, icon, words = self.rows(app_direction)
        self.assertTrue(icon and words)
        self.assertGreater(icon[0], width // 2)  # (the picture on the right)
        self.assertLess(max(words), icon[0])  # (the name on its left,
        self.assertLess(icon[0] - max(words), width // 6)  # against it)

    def test_in_a_right_to_left_anki(self):
        self.check(Qt.LayoutDirection.RightToLeft)

    def test_in_a_left_to_right_anki(self):
        self.check(Qt.LayoutDirection.LeftToRight)


class StyleNameTests(QtCase):
    """macOS's style is still known behind an app style sheet (Anki's hook lets add-ons add one), which
    hides its name: the boxes' space and the dropdowns right to left went missing in a Hebrew Anki."""

    def name_with(self, widget_style):
        import enum
        from unittest import mock

        class WidgetStyle(enum.Enum):
            ANKI, NATIVE = 0, 1
        pm = types.SimpleNamespace(get_widget_style=lambda: getattr(WidgetStyle, widget_style))
        app = QApplication.instance()
        app.setStyleSheet("QToolTip { color: red; }")
        self.addCleanup(app.setStyleSheet, "")
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(sys.modules["aqt"], "mw", types.SimpleNamespace(pm=pm), create=True), \
                mock.patch.object(sys.modules["aqt.theme"], "WidgetStyle", WidgetStyle, create=True):
            return addon.s_widgets.style_name()

    def test_native_behind_a_style_sheet(self):
        self.assertEqual(self.name_with("NATIVE"), "macos")

    def test_ankis_own_look_behind_a_style_sheet(self):
        self.assertEqual(self.name_with("ANKI"), "fusion")

    def test_named_without_one(self):
        self.assertEqual(addon.s_widgets.style_name(), QApplication.style().objectName().lower())


class _Metrics:
    """Each character 10 px; cut short as Qt does, "…" at the end."""

    def horizontalAdvance(self, text):
        return 10 * len(text)

    def elidedText(self, text, _mode, width):
        return text if len(text) * 10 <= width else text[:max(0, width // 10 - 1)] + "…"


class TileNameTests(unittest.TestCase):
    """A scenery tile's name: one line where it fits, else two, the second cut short."""

    @unittest.skipUnless(Q.HAVE_QT, Q.SKIP)
    def test_lines(self):
        lines = addon.s_scenery_picker.name_lines
        fm = _Metrics()
        self.assertEqual(lines(fm, "Golden hour", 200), ["Golden hour"])
        self.assertEqual(lines(fm, "Markt am gefrorenen Fluss", 200), ["Markt am gefrorenen", "Fluss"])
        self.assertEqual(lines(fm, "aa bb cc dd ee ff gg hh", 80), ["aa bb cc", "dd ee f…"])
        self.assertEqual(lines(fm, "Unbreakablylongword x", 100), ["Unbreakab…"])


if __name__ == "__main__":
    unittest.main()

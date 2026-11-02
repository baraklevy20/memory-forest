"""The About tab on real Qt: What's new above the thank-you, and the sponsors in columns like film credits."""

from __future__ import annotations

import sys
import unittest
from unittest import mock

from settings_qt import QtCase, QtWidgets


class AboutTests(QtCase):
    def test_what_s_new_is_above_the_thank_you_and_the_names_are_in_columns(self):
        about = sys.modules[self.about_module()]
        names = [f"Sponsor {i}" for i in range(6)]
        with mock.patch.object(about, "goats", lambda: names):
            d = self.open_dialog({})
        self.tab(d, "About")
        labels = {w.text(): w for w in d.about.findChildren(QtWidgets.QLabel)}
        first, last = labels["Sponsor 0"], labels["Sponsor 2"]
        self.assertGreater(last.mapToGlobal(last.rect().topLeft()).x(), first.mapToGlobal(first.rect().topLeft()).x())
        news = d.about.news.mapToGlobal(d.about.news.rect().topLeft()).y()
        self.assertLess(news, first.mapToGlobal(first.rect().topLeft()).y())

    def about_module(self) -> str:
        d = self.open_dialog({})
        return type(d.about).__module__


if __name__ == "__main__":
    unittest.main()

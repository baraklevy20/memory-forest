"""The heatmap browser column shows the clicked day's values and sits second."""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from fake_anki import addon, mw, reset

column = addon.actions.answer_column


class Hook:
    """Anki's append/remove interface, deliberately without list iteration."""
    def __init__(self):
        self.callbacks = []

    def append(self, callback):
        self.callbacks.append(callback)

    def remove(self, callback):
        self.callbacks.remove(callback)

    def __call__(self, *args):
        for callback in self.callbacks.copy():
            callback(*args)


def legacy_column(key, cards_mode_label, notes_mode_label, uses_cell_font, alignment):
    """The Anki 2.1.45 constructor has no tooltip fields."""
    return types.SimpleNamespace(key=key, cards_mode_label=cards_mode_label, notes_mode_label=notes_mode_label, sorting=99)


class Watcher:
    def __init__(self, parent):
        pass

    def deleteLater(self):
        pass


class AnswerColumnTests(unittest.TestCase):
    def setUp(self):
        reset()
        self.browser = mock.Mock()
        self.model = self.browser.table._model
        self.model.columns = {}
        self.active = None
        self.model.active_column_index.side_effect = lambda key: self.active
        self.browser.table._on_column_toggled.side_effect = lambda on, key: setattr(self, "active", 1 if on else None)
        watcher = mock.patch.object(column, "QObject", Watcher)
        watcher.start()
        self.addCleanup(watcher.stop)
        event = mock.patch.object(column, "QEvent", types.SimpleNamespace(Type=types.SimpleNamespace(Close=19)))
        event.start()
        self.addCleanup(event.stop)
        self.header = self.browser.table._view.horizontalHeader.return_value
        self.header.count.return_value = 4
        self.header.visualIndex.return_value = 3
        self.fetch = Hook()
        self.search = Hook()
        self.patch = mock.patch.multiple(column.gui_hooks, browser_did_fetch_row=self.fetch,
                                         browser_will_search=self.search, create=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        columns = types.SimpleNamespace(SORTING_NONE=0, ALIGNMENT_CENTER=0)
        self.modules = mock.patch.dict(sys.modules, {"aqt.browser.table": types.SimpleNamespace(Column=legacy_column)})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.columns = mock.patch("anki.collection.BrowserColumns", columns, create=True)
        self.columns.start()
        self.addCleanup(self.columns.stop)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if column._session:
            column._session()

    def show(self, label="Answer time (2026-10-17)"):
        with mock.patch.object(mw.col.db, "all", return_value=[(1, 10), (2, 10)]):
            column.show(self.browser, {1: 1250, 2: 4700}, label, "rated:1")

    def value(self, item, notes=False):
        row = types.SimpleNamespace(cells=[types.SimpleNamespace(text="card"), types.SimpleNamespace(text="")])
        self.fetch(item, notes, row, ["noteFld", column.KEY])
        self.assertEqual(row.cells[0].text, "card")
        return row.cells[1].text

    def test_day_values_second_column_and_notes(self):
        self.show()
        self.browser.table._on_column_toggled.assert_called_once_with(True, column.KEY)
        self.header.moveSection.assert_called_once_with(3, 1)
        self.assertEqual(self.model.columns[column.KEY].cards_mode_label, "Answer time (2026-10-17)")
        self.assertEqual(self.model.columns[column.KEY].sorting, 0)
        self.assertEqual(self.value(1), "1.2 s")
        self.assertEqual(self.value(10, True), "4.7 s")
        self.assertEqual(self.value(99), "—")

    def test_modern_column_sorting_and_tooltips_are_set_when_available(self):
        def modern_column(**kwargs):
            return types.SimpleNamespace(**kwargs, sorting_cards=99, sorting_notes=99,
                                         cards_mode_tooltip="", notes_mode_tooltip="")
        with mock.patch.object(sys.modules["aqt.browser.table"], "Column", modern_column):
            self.show()
        definition = self.model.columns[column.KEY]
        self.assertEqual((definition.sorting_cards, definition.sorting_notes), (0, 0))
        self.assertIn("Median seconds", definition.cards_mode_tooltip)
        self.assertEqual(definition.cards_mode_tooltip, definition.notes_mode_tooltip)

    def test_attempts_are_counts_and_time_includes_all_cards_in_notes_mode(self):
        for metric, card_text, note_text in (("reviews", "2", "5"), ("time", "2.0 s", "5.0 s")):
            values = {1: 2, 2: 3} if metric == "reviews" else {1: 2000, 2: 3000}
            with mock.patch.object(mw.col.db, "all", return_value=[(1, 10), (2, 10)]):
                column.show(self.browser, values, "Day metric", "rated:1", metric)
            self.assertEqual(self.value(1), card_text)
            self.assertEqual(self.value(10, True), note_text)

    def test_other_searches_do_not_show_the_clicked_days_times(self):
        self.show()
        self.search(types.SimpleNamespace(browser=self.browser, search="deck:Other"))
        self.assertEqual(self.value(1), "—")
        self.search(types.SimpleNamespace(browser=self.browser, search="rated:1"))
        self.assertEqual(self.value(1), "1.2 s")

    def test_reopening_replaces_hooks_and_existing_column(self):
        self.show()
        self.show("Answer time (2026-10-16)")
        self.assertEqual(len(self.fetch.callbacks), 1)
        self.assertEqual(len(self.search.callbacks), 1)
        self.browser.table._on_column_toggled.assert_called_once_with(True, column.KEY)
        self.cleanup()
        self.assertEqual(self.fetch.callbacks, [])
        self.assertEqual(self.search.callbacks, [])
        self.assertIsNone(self.active)
        self.assertNotIn(column.KEY, self.model.columns)
        self.header.restoreState.assert_called_with(self.header.saveState.return_value)

    def test_close_restores_layout_before_browser_preferences_are_saved(self):
        self.show()
        watcher = self.browser.installEventFilter.call_args.args[0]
        event = types.SimpleNamespace(type=lambda: column.QEvent.Type.Close)
        self.assertFalse(watcher.eventFilter(self.browser, event))
        self.assertIsNone(self.active)
        self.assertIsNone(column._session)
        self.assertEqual(self.fetch.callbacks, [])
        self.header.restoreState.assert_called_once_with(self.header.saveState.return_value)

    def test_switching_modes_restores_departing_layout_and_replaces_session(self):
        table = self.browser.table
        original_toggle = table.toggle_state
        table.is_notes_mode.return_value = False
        original_toggle.side_effect = lambda on, search: setattr(table.is_notes_mode, "return_value", on)
        self.show()
        previous = column._session
        with mock.patch.object(mw.col.db, "all", return_value=[(1, 10), (2, 10)]):
            table.toggle_state(True, "rated:1")
        original_toggle.assert_called_once_with(True, "rated:1")
        self.assertIsNot(column._session, previous)
        self.assertEqual(len(self.fetch.callbacks), 1)
        self.header.restoreState.assert_called_once_with(self.header.saveState.return_value)
        self.cleanup()
        self.assertIs(table.toggle_state, original_toggle)
        self.assertIsNone(self.active)

    def test_cleanup_is_safe_when_called_twice_or_qt_has_destroyed_the_browser(self):
        self.show()
        cleanup = column._session
        self.browser.destroyed.disconnect.side_effect = RuntimeError("wrapped C++ object deleted")
        cleanup(object())
        cleanup()
        self.assertEqual(self.fetch.callbacks, [])
        self.assertEqual(self.search.callbacks, [])
        self.assertIsNone(column._session)
        self.browser.destroyed.disconnect.assert_called_once()

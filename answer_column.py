"""The clicked heatmap day's card metric, beside the card text in Anki's browser."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QEvent, QObject, Qt

KEY = "memoryForestAnswerTime"
_session = None


def _toggle_column(table, on: bool) -> None:
    # Anki resets the model when toggling columns, but its menu handler does not
    # restore the cached selection. Keep row indexes valid for editor callbacks.
    table._save_selection()
    try:
        table._on_column_toggled(on, KEY)
    finally:
        table._restore_selection(table._intersected_selection)


def note_values(times: dict, metric: str) -> dict:
    """Aggregate only matching cards; Pace shows the slowest card's median."""
    values = {}
    ids = ",".join(str(int(cid)) for cid in times) or "0"
    for cid, nid in mw.col.db.all(f"select id, nid from cards where id in ({ids})"):
        if cid in times:
            values[nid] = (values.get(nid, 0) + times[cid] if metric in ("reviews", "time")
                           else max(values.get(nid, -1), times[cid]))
    return values


def show(browser, times: dict, label: str, search: str, metric: str = "median") -> None:
    from anki.collection import BrowserColumns
    from aqt.browser.table import Column

    global _session
    previous_layout = None
    if _session:
        if _session.browser is browser:
            previous_layout = _session(restore=False)
        else:
            _session()

    table = browser.table
    model = table._model
    # Remove a stale column left by an earlier version before remembering the layout.
    if previous_layout is None and model.active_column_index(KEY) is not None:
        _toggle_column(table, False)
    header = table._view.horizontalHeader()
    if previous_layout is None:
        previous_layout = header.saveState()
    original_toggle = table.toggle_state
    detail = {
        "reviews": "Number of answers on the clicked day, including retries. Notes show the sum across their cards.",
        "time": "Total seconds spent answering on the clicked day, including retries. Notes show the sum across their cards.",
        "median": "Median seconds per answer for the card on the clicked day, including retries. Notes show the slowest matching card's median.",
    }[metric]
    description = f"{label}. {detail}"
    model.columns[KEY] = Column(
        key=KEY, cards_mode_label=label, notes_mode_label=label,
        uses_cell_font=False, alignment=BrowserColumns.ALIGNMENT_CENTER,
    )
    # 2.1.45 has one sorting field; newer versions split cards and notes.
    for field in ("sorting", "sorting_cards", "sorting_notes"):
        if hasattr(model.columns[KEY], field):
            setattr(model.columns[KEY], field, BrowserColumns.SORTING_NONE)
    # Tooltip fields were added after Anki 2.1.45.
    for field in ("cards_mode_tooltip", "notes_mode_tooltip"):
        if hasattr(model.columns[KEY], field):
            setattr(model.columns[KEY], field, description)
    active = True
    note_times = note_values(times, metric)

    def fetched(item, notes, row, columns):
        if KEY not in columns:
            return
        value = (note_times if notes else times).get(item) if active else None
        cell = row.cells[columns.index(KEY)]
        cell.text = (str(int(value)) if metric == "reviews" else f"{value / 1000:.1f} s") if value is not None else "—"

    def searched(context):
        nonlocal active
        if context.browser is browser:
            active = context.search == search

    cleaned = False

    def cleanup(*_args, restore=True):
        global _session
        nonlocal cleaned
        if cleaned:
            return
        cleaned = True
        # Anki hooks expose append/remove, but are not iterable containers.
        gui_hooks.browser_did_fetch_row.remove(fetched)
        gui_hooks.browser_will_search.remove(searched)
        try:
            # Close is observed before Anki saves its column preferences. destroyed alone
            # is too late to restore Qt's header or keep the key out of persisted columns.
            if restore:
                if model.active_column_index(KEY) is not None:
                    _toggle_column(table, False)
                header.restoreState(previous_layout)
            browser.removeEventFilter(watcher)
            watcher.deleteLater()
            browser.destroyed.disconnect(cleanup)
        except (RuntimeError, TypeError):
            pass  # Qt may already have disconnected the signal during destruction.
        table.toggle_state = original_toggle
        if restore:
            model.columns.pop(KEY, None)
        if _session is cleanup:
            _session = None
        return previous_layout

    class CloseWatcher(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Close:
                cleanup()
            return False

    watcher = CloseWatcher(browser)

    def toggle_state(is_notes_mode, last_search):
        if is_notes_mode == table.is_notes_mode():
            return original_toggle(is_notes_mode, last_search)
        # Each mode persists its own columns and header. Restore the departing mode
        # before Anki saves it, then give the new mode its own temporary column.
        cleanup()
        original_toggle(is_notes_mode, last_search)
        if last_search == search:
            show(browser, times, label, search, metric)

    table.toggle_state = toggle_state
    browser.installEventFilter(watcher)
    gui_hooks.browser_did_fetch_row.append(fetched)
    gui_hooks.browser_will_search.append(searched)
    browser.destroyed.connect(cleanup)
    cleanup.browser = browser
    _session = cleanup
    if model.active_column_index(KEY) is None:
        _toggle_column(table, True)
    header = table._view.horizontalHeader()
    section = model.active_column_index(KEY)
    header.moveSection(header.visualIndex(section), min(1, header.count() - 1))
    # Moving the appended column also moves its stretch mode. Let Anki stretch the
    # last visible column again, and fit this one's complete heading and values.
    table._set_column_sizes()
    model.mark_cache_stale()
    model.headerDataChanged.emit(Qt.Orientation.Horizontal, section, section)
    table._view.resizeColumnToContents(section)

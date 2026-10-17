"""The clicked heatmap day's card metric, beside the card text in Anki's browser."""

from __future__ import annotations

from aqt import gui_hooks, mw

KEY = "memoryForestAnswerTime"
_session = None


def show(browser, times: dict, label: str, search: str, metric: str = "median") -> None:
    from anki.collection import BrowserColumns
    from aqt.browser.table import Column

    global _session
    if _session:
        _session()

    table = browser.table
    model = table._model
    detail = {
        "reviews": "Number of answers on the clicked day, including retries. Notes show the sum across their cards.",
        "time": "Total seconds spent answering on the clicked day, including retries. Notes show the sum across their cards.",
        "median": "Seconds taken for the card's last answer on the clicked day. Notes show the slowest matching card.",
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
    note_times = {}
    ids = ",".join(str(int(cid)) for cid in times) or "0"
    for cid, nid in mw.col.db.all(f"select id, nid from cards where id in ({ids})"):
        if cid in times:
            note_times[nid] = (note_times.get(nid, 0) + times[cid] if metric in ("reviews", "time")
                               else max(note_times.get(nid, -1), times[cid]))

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

    def cleanup(*_args):
        global _session
        nonlocal cleaned
        if cleaned:
            return
        cleaned = True
        # Anki hooks expose append/remove, but are not iterable containers.
        gui_hooks.browser_did_fetch_row.remove(fetched)
        gui_hooks.browser_will_search.remove(searched)
        try:
            browser.destroyed.disconnect(cleanup)
        except (RuntimeError, TypeError):
            pass  # Qt may already have disconnected the signal during destruction.
        if _session is cleanup:
            _session = None

    gui_hooks.browser_did_fetch_row.append(fetched)
    gui_hooks.browser_will_search.append(searched)
    browser.destroyed.connect(cleanup)
    _session = cleanup
    if model.active_column_index(KEY) is None:
        table._on_column_toggled(True, KEY)
    header = table._view.horizontalHeader()
    header.moveSection(header.visualIndex(model.active_column_index(KEY)), min(1, header.count() - 1))
    model.mark_cache_stale()

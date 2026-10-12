"""The days you mark as important on the study calendar (an exam, say): kept in the collection's
own config, so they sync to your other computers with it, and drawn as a pin on their day
(web/calendar.js). Right-click a day to mark it, or to take its mark away."""

from __future__ import annotations

import datetime as _dt

KEY = "memoryForestImportantDays"  # the collection config key (synced)


def important_days(col) -> list:
    """The marked days, as ISO dates, oldest first; none if the collection can't say."""
    try:
        days = col.get_config(KEY, [])
    except Exception:
        return []
    return sorted({d for d in days if _is_date(d)}) if isinstance(days, list) else []


def toggle(col, day: str) -> bool:
    """Mark `day` (an ISO date) as important, or take its mark away; whether it is marked now."""
    if not _is_date(day):
        raise ValueError(f"not a date: {day!r}")
    days = set(important_days(col)) ^ {day}
    col.set_config(KEY, sorted(days))
    return day in days


def _is_date(day) -> bool:
    try:
        _dt.date.fromisoformat(day)
        return True
    except (TypeError, ValueError):
        return False

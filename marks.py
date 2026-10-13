"""The days you mark as important on the study heatmap (an exam, say): kept in the collection's
own config, so they sync to your other computers with it, and drawn on their day with the icon
you chose (web/calendar.js). Right-click a day to mark it, name it and pick its icon, or to take
its mark away."""

from __future__ import annotations

import datetime as _dt

KEY = "memoryForestImportantDays"  # the collection config key (synced)
# the icons a mark can wear (calendar.js MARK_ICONS draws them), the first the one a mark starts with
ICONS = ("pin", "exam", "trip", "birthday", "star", "heart")
NAME_MAX = 40  # characters a mark's name keeps


def important_days(col) -> list:
    """The marked days, oldest first, each {"day": ISO date, "icon": one of ICONS, "name": its
    name or ""}; none if the collection can't say. A day kept as a bare date (by an older
    version) is a plain pin."""
    try:
        days = col.get_config(KEY, [])
    except Exception:
        return []
    if not isinstance(days, list):
        return []
    out = {}
    for d in days:
        mark = _mark(d)
        if mark:
            out[mark["day"]] = mark
    return [out[day] for day in sorted(out)]


def set_mark(col, day: str, icon: str = ICONS[0], name: str = "") -> None:
    """Mark `day` (an ISO date) as important, with its icon and name (both changed if it was)."""
    if not _is_date(day):
        raise ValueError(f"not a date: {day!r}")
    mark = {"day": day, "icon": icon if icon in ICONS else ICONS[0], "name": _clean(name)}
    col.set_config(KEY, [m for m in important_days(col) if m["day"] != day] + [mark])


def unmark(col, day: str) -> None:
    """Take `day`'s mark away (nothing if it had none)."""
    col.set_config(KEY, [m for m in important_days(col) if m["day"] != day])


def _mark(d) -> dict | None:
    """A kept mark as important_days gives it, or None for one it can't read."""
    if _is_date(d):
        return {"day": d, "icon": ICONS[0], "name": ""}
    if isinstance(d, dict) and _is_date(d.get("day")):
        icon = d.get("icon")
        return {"day": d["day"], "icon": icon if icon in ICONS else ICONS[0], "name": _clean(d.get("name"))}
    return None


def _clean(name) -> str:
    """A name as kept: one line, trimmed, no longer than NAME_MAX."""
    return " ".join(str(name).split())[:NAME_MAX] if isinstance(name, str) else ""


def _is_date(day) -> bool:
    try:
        _dt.date.fromisoformat(day)
        return True
    except (TypeError, ValueError):
        return False

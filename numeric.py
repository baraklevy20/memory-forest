"""Numeric helpers for Anki builds with and without the statistics module."""

from __future__ import annotations

try:
    from statistics import median
except ImportError:  # the Anki builds before 2.1.50 do not bundle it
    def median(values) -> float:
        v = sorted(values)
        mid = len(v) // 2
        return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2

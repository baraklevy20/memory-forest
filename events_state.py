"""The events - what the way you study brings to the forest - on Anki's side: what the page
needs to show them. The rules are in events.py, the drawing in web/events/."""

from __future__ import annotations

from . import events


def apply(forest: dict, cfg: dict, test: bool) -> tuple:
    """The forest after the events have had their say, and what the page needs to show
    them: (forest, extras for the page)."""
    days = forest.get("review_days") or set()
    extras = {"stagnation": events.stagnation(forest["trees"], days)}
    return forest, extras

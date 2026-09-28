"""How well a card is remembered, from the FSRS memory state Anki keeps in its data blob.

This module never imports aqt, so it runs in unit tests and in the dev scripts.
"""

from __future__ import annotations

import json
import re

# FSRS forgetting curve: R = (1 + factor * elapsed / stability) ** -decay. FSRS-6 gives
# every card its own decay next to its stability; 0.5 is the FSRS-4.5/5 value, for which
# factor works out to the familiar 19/81.
DEFAULT_DECAY = 0.5
# Stability is the number of days until recall falls to this.
STABILITY_RECALL = 0.9

_S_RE = re.compile(r'"s"\s*:\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)')
_DECAY_RE = re.compile(r'"decay"\s*:\s*([0-9.]+(?:[eE][-+]?\d+)?)')


def retrievability(stability: float, elapsed_days: float, data: str) -> float:
    """How likely this card still is to be recalled, on its own forgetting curve."""
    m = _DECAY_RE.search(data or "")
    try:
        decay = float(m.group(1)) if m else DEFAULT_DECAY
    except ValueError:
        decay = DEFAULT_DECAY
    if not 0 < decay < 1:
        decay = DEFAULT_DECAY
    factor = STABILITY_RECALL ** (-1.0 / decay) - 1
    return (1 + factor * elapsed_days / stability) ** -decay


def stability(data: str):
    """FSRS memory stability from a card's data blob. Parsing every card's JSON is a
    measurable slice of a whole-collection build, so read the one key directly and only
    fall back to a real parse when the shortcut doesn't match."""
    if not data:
        return None
    m = _S_RE.search(data)
    if m:
        try:
            s = float(m.group(1))
        except ValueError:
            return None
        return s if s > 0 else None
    try:
        s = json.loads(data).get("s")
    except (ValueError, AttributeError):
        return None
    return float(s) if isinstance(s, (int, float)) and s > 0 else None

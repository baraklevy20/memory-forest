"""Small JSON files under user_files/ (weather cache, forest state).

Writes go through a temporary file so a crash mid-write can't leave a truncated
file behind - losing the weather cache is harmless, but losing the record of
which trees were already ancient would replay the celebration.
"""

from __future__ import annotations

import json
import os


def load_json(path: str) -> dict:
    """The file's contents, or {} - including when the file holds something that isn't
    an object, which a truncated write from an older version could leave behind."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_json(path: str, data: dict) -> None:
    """Atomic within the directory; raises only on OSError from the caller's disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)

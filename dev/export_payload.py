"""Export a forest payload from a *copy* of an Anki collection, for the dev preview.

    python anki_forest/dev/export_payload.py "~/Library/Application Support/Anki2/User 1/collection.anki2"

Copies the collection (and its -wal, so a running Anki's recent reviews are
included) to a temp dir, builds the same data the add-on embeds, and writes
dev/payload.js next to this script. The payload is your own study history, so it
is gitignored.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import forest_data
import memory
import milestones
import scene
import study_log

DEFAULT_ROLLOVER_HOUR = 4  # Anki's own default, for a collection that never set one
MAX_WIDTH = 900


class DB:
    """Minimal stand-in for Anki's DBProxy (.all / .scalar)."""

    def __init__(self, path: str):
        self.con = sqlite3.connect(path)

    def all(self, sql, *args):
        return self.con.execute(sql, args).fetchall()

    def scalar(self, sql, *args):
        row = self.con.execute(sql, args).fetchone()
        return row[0] if row else None


def day_cutoff(rollover: int) -> int:
    now = dt.datetime.now()
    cut = now.replace(hour=rollover, minute=0, second=0, microsecond=0)
    if cut <= now:
        cut += dt.timedelta(days=1)
    return int(cut.timestamp())


def main() -> None:
    src = os.path.expanduser(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="anki-forest-")
    for suffix in ("", "-wal"):
        if os.path.exists(src + suffix):
            shutil.copy2(src + suffix, os.path.join(tmp, "collection.anki2" + suffix))
    db = DB(os.path.join(tmp, "collection.anki2"))
    rollover = int(db.scalar("select val from config where key = 'rollover'") or DEFAULT_ROLLOVER_HOUR)
    crt = int(db.scalar("select crt from col"))
    cutoff = day_cutoff(rollover)
    today = (cutoff - crt) // study_log.DAY_SECS - 1

    started = time.perf_counter()
    rows = study_log.load_rows(db, cutoff)
    forest = forest_data.merge_old(forest_data.build_forest(rows, cutoff, today, time.time()))
    took = (time.perf_counter() - started) * 1000

    now = dt.datetime.now()
    cfg = {}
    mood = scene.choose_mood(cfg, now)
    ann = milestones.anniversaries(forest["trees"], now.date())
    payload = {
        "trees": forest["trees"], "stats": forest["stats"], "visitors": forest["visitors"], "anniversaries": ann, "merged": forest.get("merged"),
        "mood": mood, "journal": scene.journal(forest, mood, now.date(), ann),
        "animations": True, "tooltips": True, "maxWidth": MAX_WIDTH, "events": [], "forestSeed": forest["forest_seed"], "credit": False,
    }
    with open(os.path.join(HERE, "payload.js"), "w", encoding="utf-8") as f:
        f.write("window.PAYLOAD = " + json.dumps(payload, ensure_ascii=False) + ";\n")
    fsrs = sum(1 for c in rows.cards if memory.stability(c[4]) is not None)
    print(f"{len(forest['trees'])} trees from {len(rows.cards)} cards ({fsrs} with FSRS stability) in {took:.0f} ms")
    print("stats:", json.dumps(forest["stats"]))
    print("visitors:", [v["key"] for v in forest["visitors"]])
    print("mood:", mood, "| journal:", payload["journal"])
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

"""The day the forest is drawn for, and the seasonal scenery: a holiday's preset stands in
for yours in its week, and yours comes back after it (presets.follow_season)."""

from __future__ import annotations

import datetime as _dt
import os

from . import events, presets
from .edition import debug_available
from .state import USER_FILES, config, log, save_config
from .store import load_json, save_json

# the seasonal scenery's record: shared by every profile, as the look settings are
SEASON_PATH = os.path.join(USER_FILES, "season.json")


def today(cfg: dict | None = None) -> _dt.date:
    """The date the scenery is chosen for: today, or while debug is on, the debug date
    (if one is set) moved on by the days passed on the test forest's timeline - so passing
    a week there also carries a holiday's week over, as it would in real days."""
    cfg = config() if cfg is None else cfg
    day = _dt.date.today()
    if not debug_available(cfg):
        return day
    try:
        day = _dt.date.fromisoformat(cfg.get("debug_date") or "") or day
    except (TypeError, ValueError):
        pass
    if cfg.get("test_forest"):  # the timeline passes days only on the test forest
        day += _dt.timedelta(days=events.timeline_days(events.timeline_steps(cfg.get("debug_timeline")))[0])
    return day


def follow_season(cfg: dict, day: _dt.date | None = None) -> dict:
    """The config, changed to a seasonal preset in its week and back after it (see
    presets.follow_season), and saved if it changed."""
    day = day or today(cfg)
    record = load_json(SEASON_PATH)
    change, kept = presets.follow_season(cfg, record, day)
    if kept != record:
        try:
            save_json(SEASON_PATH, kept)
        except OSError:
            log(f"could not save {SEASON_PATH}")
    if change and any(cfg.get(k) != v for k, v in change.items()):
        cfg = dict(cfg, **change)
        save_config(cfg)
    return cfg


def forget_seasons() -> None:
    """Let every holiday's week change the scenery again (the Debug tab's replay)."""
    try:
        save_json(SEASON_PATH, {})
    except OSError:
        log(f"could not save {SEASON_PATH}")


def season_returns(cfg: dict, today: _dt.date) -> _dt.date | None:
    """The day the scenery from before comes back, while a seasonal preset stands in for it."""
    active = load_json(SEASON_PATH).get("active")
    now = presets.in_season(today)
    if not (now and isinstance(active, dict) and active.get("tag") == f"{now.key}:{today.year}"):
        return None
    if {k: cfg.get(k) for k in presets.LOOK} != active.get("applied") or active.get("before") == active.get("applied"):
        return None
    return presets.season_ends(now, today)

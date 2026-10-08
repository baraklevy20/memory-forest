"""The live weather for your city, when the real sky is on: read from the cache in
user_files, and refreshed in the background (the forest redraws when it arrives)."""

from __future__ import annotations

import inspect
import os

from aqt import mw

from .state import USER_FILES
from .weather import WeatherCache

_weather = WeatherCache(os.path.join(USER_FILES, "weather.json"))
_refreshing = False
# what redraws the forest once new weather is in: __init__ hands it panel.refresh, which this
# module can't import, the panel drawing from the weather
_redraw = None


def redraw_with(redraw) -> None:
    global _redraw
    _redraw = redraw


def _maybe_refresh(city: str) -> None:
    global _refreshing
    if _refreshing or not _weather.needs_refresh(city):
        return
    _refreshing = True

    def done(future) -> None:
        global _refreshing
        _refreshing = False
        try:
            result = future.result()
        except Exception:
            return
        if result is not None and mw.state == "deckBrowser" and _redraw:
            _redraw()

    # the weather needs no collection, so it need not wait for one - where this Anki can
    # be told so (older ones take no `uses_collection`)
    extra = {"uses_collection": False} if "uses_collection" in inspect.signature(mw.taskman.run_in_background).parameters else {}
    mw.taskman.run_in_background(lambda: _weather.refresh(city), done, **extra)


def for_config(cfg: dict) -> tuple:
    """(the weather now, the place it is for, why it is missing) for the config's city, while
    the weather follows the real sky - (None, None, "") otherwise. Starts a refresh when the
    cache is due one."""
    city = (cfg.get("city") or "").strip()
    real = place = None
    error = ""
    if city and (cfg.get("weather") or "auto") == "auto":
        real, place = _weather.current(city), _weather.place(city)
        if real is None:  # say so, instead of quietly looking like no city was ever set
            error = _weather.failing(city)
        _maybe_refresh(city)
    return real, place, error


def city_problem(city: str) -> str:
    """Why the live weather for `city` is missing, for the settings dialog, or ""."""
    return _weather.failing(city) if city.strip() else ""

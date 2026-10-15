"""The scenes e2e/render_check.py draws: every preset, every environment against every landscape,
hour and weather, every landmark, forests of every size either side of the deep-forest cutoff,
and the study heatmap's own (e2e/render_heatmap.py)."""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from render_heatmap import heatmap_scenes

import forest_data
import presets
import scene

SCENE_TREES = 200  # the forest every scene is drawn on, unless it is about forest size
# the forest sizes tried, either side of the deep-forest cutoff
SIZES = (0, 1, 2, 30, forest_data.MAX_INDIVIDUAL_TREES - 1, forest_data.MAX_INDIVIDUAL_TREES,
         forest_data.MAX_INDIVIDUAL_TREES + 1, 1000, 5000)
# --quick keeps every this-many-th environment and preset, and the first few of the rest
QUICK_ENV_EVERY, QUICK_PRESET_EVERY, QUICK_WEATHERS, QUICK_TIMES, QUICK_LANDMARKS = 4, 5, 3, 2, 2


def scenes(quick: bool) -> list:
    """Every preset, and every environment against every landscape, hour and weather.

    The bug that prompted this file was a landscape nobody rendered; the one after it was
    a sun nobody had drawn at dusk, because weather and time of day were only ever tried
    on the plain forest. The matrix is the point, not the count.
    """
    out, envs = [], list(scene.ENVIRONMENTS)
    lands, marks = list(scene.LANDSCAPES), list(scene.LANDMARKS)
    weathers, times = list(scene.WEATHERS), list(scene.TIMES)
    if quick:
        envs = list(dict.fromkeys(envs[::QUICK_ENV_EVERY] + ["natural"]))  # natural is often already in the slice
        weathers, times, marks = weathers[:QUICK_WEATHERS], times[:QUICK_TIMES], marks[:QUICK_LANDMARKS]

    for env in envs:  # every environment on every landscape
        for land in lands:
            out.append((f"{env}-{land}", {"environment": env, "landscape": land, "weather": "clear", "time_of_day": "day"}, SCENE_TREES))
    for env in envs:  # every environment at every hour of the day, and in every weather
        for t in times:
            out.append((f"{env}-at-{t}", {"environment": env, "landscape": "meadow", "weather": "clear", "time_of_day": t}, SCENE_TREES))
        for w in weathers:
            out.append((f"{env}-in-{w}", {"environment": env, "landscape": "meadow", "weather": w, "time_of_day": "day"}, SCENE_TREES))
    for land in lands:  # every landscape in every weather, and at night
        for w in weathers:
            out.append((f"{land}-{w}", {"environment": "natural", "landscape": land, "weather": w, "time_of_day": "day"}, SCENE_TREES))
        for t in times:
            out.append((f"{land}-{t}", {"environment": "natural", "landscape": land, "weather": "clear", "time_of_day": t}, SCENE_TREES))
    for mark in marks:  # every landmark
        for land in lands:
            out.append((f"{mark}-{land}", {"environment": "natural", "landscape": land, "landmark": mark, "weather": "clear", "time_of_day": "day"}, SCENE_TREES))
    # the catalogue the settings dialog offers, drawn exactly as it ships
    for p in (presets.FOREST_PRESETS[::QUICK_PRESET_EVERY] if quick else presets.FOREST_PRESETS):
        out.append((f"preset-{p.key}", dict(p.values()), SCENE_TREES))
    for n in SIZES:
        out.append((f"trees-{n}", {"environment": "natural", "landscape": "lake", "weather": "clear", "time_of_day": "day"}, n))
    out += heatmap_scenes()
    # two scenes sharing a name would quietly become one, which is how coverage is lost
    names = [c[0] for c in out]
    assert len(set(names)) == len(names), "duplicate scene names: " + str(sorted({n for n in names if names.count(n) > 1}))
    return out

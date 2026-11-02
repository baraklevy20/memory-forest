"""Memory Forest's own words, beyond locales/en.json: each scenery's label and note, read from its .json, with ids
of their own: env.<key>, landscape.<key>, landmark.<key>, preset.<key> and preset.<key>.note, heatmap_style.<key>
and heatmap_style.<key>.tip. i18n.py (the shared one, addon_libs/) adds them to the English. The release notes stay
English: an update ships before its notes could be translated."""

from __future__ import annotations

import json
import os

try:
    from . import catalog as files
except ImportError:  # the tests and dev scripts import these files as top-level modules
    import catalog as files

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def scenery_english(web: str | None = None) -> dict:
    """id -> English for the scenery this copy has, read from each one's .json."""
    web = web or files.WEB
    out = {}
    for kind, prefix in (("envs", "env"), ("landscapes", "landscape"), ("landmarks", "landmark")):
        folder = os.path.join(web, kind)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            if not name.endswith(".json"):
                continue
            spec, key = _read(os.path.join(folder, name)), name[:-5]
            if spec.get("label"):
                out[f"{prefix}.{key}"] = spec["label"]
            preset = spec.get("preset")
            if isinstance(preset, dict) and preset.get("label"):
                pk = preset.get("key", key)
                out[f"preset.{pk}"] = preset["label"]
                if preset.get("note"):
                    out[f"preset.{pk}.note"] = preset["note"]
    # the Plus sceneries the base edition's picker shows locked
    plus = os.path.join(HERE, "settings", "plus.json")
    if os.path.exists(plus):
        try:
            with open(plus, encoding="utf-8") as f:
                for spec in json.load(f):
                    out.setdefault(f"preset.{spec['key']}", spec["label"])
                    if spec.get("note"):
                        out.setdefault(f"preset.{spec['key']}.note", spec["note"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    # (and the tile styles still in the works, in web/drafts/heatmap/ where this copy has them: never collected)
    for folder in (os.path.join(web, "heatmap"), os.path.join(web, "drafts", "heatmap")):
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            if name.endswith(".json"):
                spec, key = _read(os.path.join(folder, name)), name[:-5]
                if spec.get("label"):
                    out.setdefault(f"heatmap_style.{key}", spec["label"])
                if spec.get("tip"):
                    out.setdefault(f"heatmap_style.{key}.tip", spec["tip"])
    return out


def english() -> dict:
    return scenery_english()

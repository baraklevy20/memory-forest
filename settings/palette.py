"""The settings' colours, from Anki's theme: its design system's (2.1.55 and later), or the
older palette's nearest (2.1.50 to 2.1.54), which has no aqt.props, no theme_manager.var
and no themed icons."""

from __future__ import annotations

from aqt import colors
from aqt.theme import theme_manager

# each colour asked for by its 2.1.55 name, and the 2.1.50 palette's nearest in its place
OLD = {
    "FG": "TEXT_FG",
    "FG_SUBTLE": "SLIGHTLY_GREY_TEXT",
    "FG_DISABLED": "DISABLED",
    "BORDER_SUBTLE": "FAINT_BORDER",
    "BORDER_FOCUS": "FOCUS_BORDER",
    "CANVAS_CODE": "FRAME_BG",
    "CANVAS_ELEVATED": "FRAME_BG",
    "BUTTON_BG": "FRAME_BG",
}
OLD_RADIUS = "5px"  # what 2.1.55's props.BORDER_RADIUS comes to


def color(name: str) -> str:
    """The theme's colour `name` (FG, BORDER_FOCUS, ...), as a CSS colour for a style sheet."""
    if hasattr(theme_manager, "var") and hasattr(colors, name):
        return theme_manager.var(getattr(colors, name))
    return theme_manager.color(getattr(colors, OLD[name]))


def radius() -> str:
    """The corner radius of Anki's own fields."""
    try:
        from aqt import props
        return theme_manager.var(props.BORDER_RADIUS)
    except (ImportError, AttributeError):
        return OLD_RADIUS


def chevron() -> str | None:
    """The path of Anki's down chevron, or None where Anki has no themed icons (Qt then draws
    its own arrow)."""
    themed = getattr(theme_manager, "themed_icon", None)
    return themed("mdi:chevron-down") if themed else None

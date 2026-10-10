"""The settings' colours, from Anki's theme: its design system's (2.1.55 and later), or the
older palette's nearest (2.1.45 to 2.1.54), which has no aqt.props, no theme_manager.var
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
# a 2.1.50 palette colour the 2.1.45 to 2.1.49 palette lacks, and its nearest there
OLDER = {"FOCUS_BORDER": "HIGHLIGHT_BG"}
OLD_RADIUS = "5px"  # what 2.1.55's props.BORDER_RADIUS comes to
# help lines and the city's problem, (light, dark): Anki's FG_SUBTLE is under 4.5:1 on its own
# window (4.4:1 light, 3.8:1 dark), and a fixed red reads at 2.6:1 on the dark one
HINT = ("#5c5c5c", "#a3a3a3")
ERROR = ("#b42318", "#f87171")
LINK = ("#1d5fd1", "#8ab4ff")  # (5.4:1 and 6.7:1; Anki's focus blue is 3.6:1 on its dark window)


def color(name: str) -> str:
    """The theme's colour `name` (FG, BORDER_FOCUS, ...), as a CSS colour for a style sheet."""
    if hasattr(theme_manager, "var") and hasattr(colors, name):
        return theme_manager.var(getattr(colors, name))
    old = OLD[name]
    if not hasattr(colors, old):
        old = OLDER[old]
    return theme_manager.color(getattr(colors, old))


def readable(pair: tuple) -> str:
    """The light or dark one of a (light, dark) pair, for Anki's theme as it is now."""
    return pair[1] if getattr(theme_manager, "night_mode", False) else pair[0]


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

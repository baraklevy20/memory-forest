"""The study heatmap's look (the Heatmap tab's Colours and Tiles): whose colours its days take and
how its tiles are drawn, kept when the scenery changes. payload.py hands web/calendar.js what to
draw with (`look`), through the route the sceneries already have: a scenery's `calendar` colours
and its `calendarTile` (web/envs/*.js). The settings draw their pictures with the same sums as
calendar.js (shades, tiles), so a strip in the dialog is the heatmap's own key.

Nothing here imports Qt, so the tests run it as it is."""

from __future__ import annotations

import functools
import json
import math
import os

from . import catalog, presets
from .edition import debug_edition, edition_presets
from .i18n import N_
from .seasons import offer_day, today
from .state import save_config

# ---- the choices, as the config keeps them ----
# whose colours: the scenery's ("scenery", today's look), a ready ramp ("ready:flame"), or your own
# ("mine"). (Another scenery's colours, as pictures, and a hand-picked pair for each scenery were
# tried and cut, 2026-10-16: borrowed colours mostly looked dull, and the pictures took half the tab)
MATCH, MINE = "scenery", "mine"
READY_PREFIX = "ready:"
# the tile styles, each in a file of its own (web/heatmap/<key>.json, and .js where it draws itself:
# calendar.js AF.heatmapTiles), in their `order`: Flat (the default), Round, Contours, and a scenery's
# own tiles (`env`: its calendarTile), a seasonal one's only in its week (`season`: its preset). Each
# says its `label` and `tip` for the Heatmap tab, its spaces between the days and smooth corners
# (`gaps`, `smooth`), whether it is a joined shape (`shape`) and how its sample is drawn (`sample`).
# The styles still in the works are in web/drafts/heatmap/, which only this copy has (never a release
# or the public repo). (Cut 2026-10-16: Plain, Flat with a light texture; Smooth, the shapes outlined
# with their shades blended; and Scenery, the scenery's own tiles, which was always one of the others)
TILE_DIRS = (os.path.join(catalog.WEB, "heatmap"), os.path.join(catalog.WEB, catalog.DRAFTS, "heatmap"))


def tile_specs() -> dict:
    """key -> what its file says, every tile style this copy has, in their order."""
    found = []
    for folder, draft in zip(TILE_DIRS, (False, True)):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    spec = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(spec, dict):
                found.append((spec.get("order", 99), name[:-5], dict(spec, draft=draft)))
    return {key: spec for _order, key, spec in sorted(found, key=lambda t: (t[0], t[1]))}


TILE_SPECS = tile_specs()
TILES = tuple(TILE_SPECS)
TILE_DEFAULT = "flat"  # (Scenery's on a scenery with none of its own)
TILE_FOLLOW = "scenery"  # (the default, and what a style that can't be had falls back to: the scenery's own style, changing with it; web/heatmap/scenery.json)
SHAPES = tuple(k for k, v in TILE_SPECS.items() if v.get("shape"))
# the Heatmap tab's two kinds of style: a scenery's own tiles (its medium: in the Scenery dropdown)
# and the basic ones beside it (Flat, Round, Contours)
SCENERY_TILES = tuple(k for k, v in TILE_SPECS.items() if v.get("env"))
BASIC_TILES = tuple(k for k in TILES if k != TILE_FOLLOW and k not in SCENERY_TILES)
TILE_ENVS = {k: v["env"] for k, v in TILE_SPECS.items() if v.get("env")}
# the sceneries that wear a style anyone can pick as their own (its file's "sceneries": Round on Lanterns)
TILE_WORN = {env: k for k, v in TILE_SPECS.items() for env in v.get("sceneries", ())}
# (Scenery has no style of its own: it is the scenery's, tile_style)  # whose calendarTile draws them
TILE_SEASONS = {k: v["season"] for k, v in TILE_SPECS.items() if v.get("season")}  # by the preset whose week they come in
# each style's spaces between the days and smooth corners (drawn at the screen's resolution):
# neither is a setting of its own
TILE_STYLE = {k: (v.get("gaps", True) is not False, v.get("smooth") is True) for k, v in TILE_SPECS.items()}

# the ready ramps: Review Heatmap's five themes, by their names and in its order, each from its
# darkest to its lightest shade (its review-heatmap.css, dark mode), so someone coming from it finds
# theirs: Olive and Lime were nearly half of the heatmaps posted on Reddit (2026-10-16)
MINE_DEFAULT = ["#2a9d8f", "#e9c46a"]

READY = {
    "olive": ["#3b6427", "#dae289"],
    "lime": ["#3f9a14", "#c6ff00"],  # (a real lime: Review Heatmap's is GitHub's old forest green, lime in name only)
    "ice": ["#0063de", "#a8d5f6"],
    "magenta": ["#ae017e", "#fcc5c0"],  # (its pink stretch: its ends, deep purple and near white, read as purple, not the pink its users see)
    "flame": ["#e31a1c", "#fed976"],  # (its bright stretch: its dark wine and near-white yellow ends went dull)
}
# (the names shown with i18n.tx)
READY_LABELS = {"olive": N_("heatmap_look.olive"), "lime": N_("heatmap_look.lime"), "ice": N_("heatmap_look.ice"), "magenta": N_("heatmap_look.magenta"), "flame": N_("heatmap_look.flame")}
# and each scenery's own colours, on any scenery ("ready:aurora", by its preset): shaded as that
# scenery shades them (not `exact`), from its colour in KEYS_FILE. For now every scenery with one,
# until the ready colours are chosen (2026-10-16); a Plus one this copy lacks isn't offered. Named
# by its preset's label, as the scenery picker names it (presets.by_key()[key].label)
SCENERY_READY = ("golden_lake", "misty_valley", "cherry_blossom", "starry_night", "aurora", "lanterns", "bamboo",
                 "synthwave", "chalkboard", "pumpkin_patch", "frozen_market")

# each scenery's own colour(s) as calendar.js finds them (its `calendar`, or its most colourful
# crown colour): for the settings' pictures, and for another scenery's colours on the heatmap
# (page_look); a scenery's own the heatmap reads from the scenery itself. Written by
# dev/heatmap_keys.py (npm run heatmap-keys) when a scenery is added or recoloured.
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "heatmap_keys.json")
# and what the forest's hour does to them (calendar.js hourOf), by the same script: each scenery's
# day colours (`day`, its calendarDay), its colours for each hour (`hours`, its calendarHours) and
# its night sky's tint (`tint`), each only where it has one
HOURS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "heatmap_hours.json")


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@functools.lru_cache(maxsize=None)
def own_keys() -> dict:
    """KEYS_FILE, read once (it changes only with a new build)."""
    return _read_json(KEYS_FILE)


@functools.lru_cache(maxsize=None)
def own_hours() -> dict:
    """HOURS_FILE, read once."""
    return _read_json(HOURS_FILE)


# what the forest's hour does to a scenery's own colours (calendar.js hourOf, HOUR_TURN and
# DAY_SHARE: keep the two in step): a day scenery's turn towards its night tint after dark; a night
# scenery's meet its day colours by day, halfway at dawn and golden hour
HOUR_TURN = {"dusk": 0.1, "night": 0.35}
AFTER_DARK = ("dusk", "night")
DAY_SHARE = {"dawn": 0.5, "day": 1, "golden_hour": 0.5}


def hour_of(env: str, time: str) -> dict | None:
    """What the hour `time` (the forest's: mood.time) does to the environment's own colours, as
    calendar.js hourOf has it: {"to", "share"} towards the colours it names for that hour or for the
    day, {"turn", "tint"} after dark for a day scenery, or None where its own colours stand. The
    scenery's own hour is its preset's (mood.home, scene.choose_mood)."""
    spec = own_hours().get(env) or {}
    home = next((p.time for p in presets.FOREST_PRESETS if p.environment == env), "day")
    if spec.get("hours"):
        to = spec["hours"].get(time)
        return {"to": to, "share": 1} if to else None
    if home in AFTER_DARK:
        share = DAY_SHARE.get(time)
        return {"to": spec["day"], "share": share} if share and spec.get("day") else None
    turn = HOUR_TURN.get(time)
    return {"turn": turn, "tint": spec["tint"]} if turn and spec.get("tint") else None


def _hex_ok(value) -> bool:
    return isinstance(value, str) and len(value) == 7 and value[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in value[1:])


def colours_choice(cfg: dict) -> str:
    """Whose colours the heatmap takes (see MATCH): a value it can't use (a hand edit, a ready
    ramp from a later version) is the scenery's."""
    value = cfg.get("calendar_colours", MATCH)
    if value in (MATCH, MINE):
        return value
    if isinstance(value, str) and value.startswith(READY_PREFIX) and value[len(READY_PREFIX):] in (*READY, *SCENERY_READY):
        return value
    return MATCH


def scenery_ready_shown(key: str, cfg: dict) -> bool:
    """Whether a scenery's colours are among the ready ones (SCENERY_READY) just now: KEYS_FILE
    lists its colour, and a seasonal scenery's only in its week: today's, or the debug date's
    (seasons.today; never every season at once, as the scenery picker offers them while debugging
    with no date). A Plus one this copy lacks shows too, locked (scenery_ready_env)."""
    spec = presets.by_key().get(key)
    return key in SCENERY_READY and spec is not None and spec.environment in own_keys() and presets.unlocked(spec, today(cfg))


def scenery_ready_env(key: str, cfg: dict) -> str | None:
    """The environment of a scenery's colours among the ready ones, if they can be used just now
    (scenery_ready_shown, and this copy has the scenery); else None."""
    if not scenery_ready_shown(key, cfg):
        return None
    env = presets.by_key()[key].environment
    return None if plus_locked(env, cfg) else env


def tiles_choice(cfg: dict) -> str:
    """The tile style chosen: one of TILES, else Scenery (TILE_FOLLOW, the default: it follows the
    scenery)."""
    value = cfg.get("calendar_tiles", TILE_FOLLOW)
    return value if value in TILES else TILE_FOLLOW


# the space between the days' tiles, in the heatmap's pixels: calendar.js's GAP (1), or the style's
# own (its file's "gap": Round keeps 2, its circles apart)
GAP_MAX = 6


def tile_gap(cfg: dict, here: str = "") -> int | None:
    """The style's own space between tiles, or None: calendar.js's own."""
    value = TILE_SPECS.get(tile_style(cfg, here), {}).get("gap")
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= GAP_MAX else None


def tile_style(cfg: dict, here: str = "") -> str:
    """The style the heatmap is drawn in for `cfg` while the scenery's environment is `here`:
    Scenery's is that scenery's own (the style its environment draws, TILE_ENVS: Brush on Starry
    night; or one it wears, TILE_WORN: Round on Lanterns; a holiday's in its week), else Flat; any
    other is itself if it can be had just now (tile_shown), else Scenery's."""
    choice = tiles_choice(cfg)
    if choice != TILE_FOLLOW and tile_shown(choice, cfg):
        return choice
    if here in TILE_WORN:
        return TILE_WORN[here]
    return next((k for k, env in TILE_ENVS.items() if env == here and tile_shown(k, cfg)), TILE_DEFAULT)


def mine(cfg: dict) -> list:
    """Your two colours (the second used only while you blend into it), as "#rrggbb"."""
    value = cfg.get("calendar_mine")
    value = value if isinstance(value, list) else []
    return [(c.lower() if _hex_ok(c) else d) for c, d in zip(value + MINE_DEFAULT[len(value):], MINE_DEFAULT)]


def mine_two(cfg: dict) -> bool:
    return cfg.get("calendar_mine_two") not in (False, None, "false", "False", 0, "0")


@functools.lru_cache(maxsize=None)
def _env_file(env: str) -> bool:
    """Whether this copy has the environment's file (web/envs/<env>.js): asked once each."""
    return os.path.exists(os.path.join(catalog.WEB, "envs", f"{env}.js"))


def plus_locked(env: str, cfg: dict) -> bool:
    """Whether a scenery's environment is one this copy can't use: Plus's, in the base edition
    (or while the Debug tab pretends this is it), or one whose file it lacks."""
    if env != "natural" and not _env_file(env):
        return True
    ships = edition_presets(debug_edition(cfg))
    return ships is not None and not any(p.environment == env and p.key in ships for p in presets.FOREST_PRESETS)


# which way a dark page's shades run (the Heatmap tab): busier days lighter (towards white, the
# default), or darker (a pale tint for a quiet day down to a deep colour for a busy one). A light
# page's already run darker for more
BUSIER = (("lighter", N_("heatmap_look.lighter")), ("darker", N_("heatmap_look.darker")))


def busier(cfg: dict) -> str:
    return "darker" if cfg.get("calendar_busier") == "darker" else "lighter"


def gaps(cfg: dict, here: str = "") -> bool:
    """Whether the days keep the spaces between them, as the tile style has them (TILE_STYLE). For
    Round and Contours too: with spaces, each day is a shape of its own."""
    return TILE_STYLE[tile_style(cfg, here)][0]


def smooth(cfg: dict, here: str = "") -> bool:
    """Whether the tiles are drawn as smooth rounded squares at the screen's resolution, as the tile
    style has them (TILE_STYLE). Not with the joined shapes, which are no tiles; Round with spaces
    is a tile, so it can be."""
    return TILE_STYLE[tile_style(cfg, here)][1]


def tile_shown(key: str, cfg: dict) -> bool:
    """Whether a tile style is offered just now: not a Plus one this copy lacks, a seasonal
    scenery's only in its week (today's, or the debug date's; any while debugging with no date, as
    its scenery is: seasons.offer_day), and one still in the works (a
    draft's) not while the Debug tab pretends this is the base or Plus edition, which has none."""
    if key in TILE_ENVS and plus_locked(TILE_ENVS[key], cfg):
        return False
    if TILE_SPECS.get(key, {}).get("draft") and debug_edition(cfg):
        return False
    spec = presets.by_key().get(TILE_SEASONS.get(key, ""))
    return spec is None or presets.unlocked(spec, offer_day(cfg))


def tile_env(cfg: dict, here: str = "") -> str:
    """Whose tiles draw the heatmap (tile_style, while the scenery's environment is `here`):
    "flat", a shape (SHAPES), or the environment whose medium it is (Brush, Scanlines, a seasonal
    scenery's)."""
    style = tile_style(cfg, here)
    return TILE_ENVS.get(style, style)


def page_look(cfg: dict, mood: dict) -> dict:
    """What calendar.js draws the heatmap with (data.calendar.look): `colours` (a colour, or two
    for a ramp) in place of the scenery's own (None: the scenery's); `tile`, whose tiles ("flat", a shape such as "round", or an environment with calendarTile);
    `files`, the scenery files they need beyond today's (the page loads them, the phone too);
    `exact`, colours you picked (yours, a ready ramp), shown as picked on either page (exact_steps);
    `flipLight`, a ready ramp run the other way on a light page, its deep colour the busiest (as
    Review Heatmap's light mode: its ramps run pale to deep on a dark page);
    `darker`, a dark page's busier days darker (busier); `moving`, whether a moving style moves
    (moving); `smoothRadius`/`smoothGrow`, a style's
    smooth corners (Round's, from its .json)."""
    here = mood.get("special") or "natural"
    choice = colours_choice(cfg)
    colours, exact, flip = None, False, False
    if choice == MINE:
        first, second = mine(cfg)
        colours, exact = ([first, second] if mine_two(cfg) else first), True
    elif choice.startswith(READY_PREFIX) and choice[len(READY_PREFIX):] in READY:
        colours, exact, flip = READY[choice[len(READY_PREFIX):]], True, True
    elif choice.startswith(READY_PREFIX):
        env = scenery_ready_env(choice[len(READY_PREFIX):], cfg)
        colours = own_keys()[env] if env else None
    tile = tile_env(cfg, here)
    files = [f"envs/{tile}.js" for _ in [0] if tile not in ("flat", *SHAPES, here)
             and os.path.exists(os.path.join(catalog.WEB, "envs", f"{tile}.js"))]
    corners = {k: v for k, v in TILE_SPECS.get(tile, {}).items() if k in ("smoothRadius", "smoothGrow")}
    return {"colours": colours, "exact": exact, "tile": tile, "files": files,
            "flipLight": flip, "darker": busier(cfg) == "darker", "gaps": gaps(cfg, here),
            "smooth": smooth(cfg, here), "gap": tile_gap(cfg, here), **corners}


def preview_look(cfg: dict, here_env: str, time: str = "") -> dict:
    """What the settings' pictures draw for the choice in `cfg` while the scenery's environment is
    `here_env`: page_look's, its `colours` always filled in (a scenery's own read from KEYS_FILE),
    and a scenery's own at the forest's hour `time` (`hour`: hour_of), as the heatmap wears them
    just now; colours chosen (yours, a ready ramp, another scenery's) stay as chosen, as there."""
    look = page_look(cfg, {"special": here_env})
    if look["colours"] is None:
        look["colours"] = scenery_own(here_env)
        look["hour"] = hour_of(here_env, time) if time else None
    return look


def scenery_own(env: str):
    keys = own_keys()
    return keys.get(env) or keys.get("natural") or "#8fb35e"


# ---- calendar.js's sums, for the settings' pictures (keep the two in step) ----
DARK = (16, 16, 16)
LIGHT_STEPS, LIGHT_CHROMA = (0.82, 0.69, 0.56, 0.43), 0.08
DARK_STEPS, DARK_CHROMA = (0.45, 0.58, 0.72, 0.85), (0.6, 1.0, 1.0, 0.5)
KEY_L, KEY_S = (0.36, 0.56), 0.28
# an empty day's grey, laid over the page (calendar.js EMPTY, EMPTY_LIGHT)
EMPTY_GREY, EMPTY_ALPHA, EMPTY_ALPHA_LIGHT = (128, 128, 128), 0.11, 0.2
# the least the faintest of your own colours must stand apart from an empty day (OKLab distance)
EMPTY_APART = 0.06


def hexc(value: str) -> tuple:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def to_hex(c) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in c)


def mix(a, b, t: float) -> tuple:
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _unlin(v: float) -> float:
    v = 12.92 * v if v <= 0.0031308 else 1.055 * max(v, 0) ** (1 / 2.4) - 0.055
    return 255 * min(1, max(0, v))


def oklab(c) -> tuple:
    r, g, b = (_lin(v) for v in c)
    cb = lambda v: math.copysign(abs(v) ** (1 / 3), v)  # noqa: E731
    l_ = cb(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = cb(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = cb(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_, 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def from_oklab(L: float, A: float, B: float) -> tuple:
    l_ = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m_ = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s_ = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (_unlin(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_), _unlin(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
            _unlin(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_))


def fits(L: float, A: float, B: float) -> bool:
    """Whether an OKLab colour is one the screen can show (calendar.js fits)."""
    lo, mid, sh = ((L + 0.3963377774 * A + 0.2158037573 * B) ** 3, (L - 0.1055613458 * A - 0.0638541728 * B) ** 3,
                   (L - 0.0894841775 * A - 1.2914855480 * B) ** 3)
    rgb = (4.0767416621 * lo - 3.3077115913 * mid + 0.2309699292 * sh, -1.2684380046 * lo + 2.6097574011 * mid - 0.3413193965 * sh,
           -0.0041960863 * lo - 0.7034186147 * mid + 1.7076147010 * sh)
    return all(-0.0005 <= v <= 1.0005 for v in rgb)


def blend(a, b, t: float) -> tuple:
    p, q = oklab(a), oklab(b)
    return from_oklab(*(p[i] + (q[i] - p[i]) * t for i in range(3)))


def apart(a, b) -> float:
    """How far apart two colours look (OKLab distance)."""
    p, q = oklab(a), oklab(b)
    return math.dist(p, q)


def readable(c) -> tuple:
    """A colour kept within the lightness and saturation a tile can show (calendar.js readable;
    by hand, as calendar.js does it: Anki 2.1.45's Python has no colorsys)."""
    r, g, b = (v / 255 for v in c)
    hi, lo = max(r, g, b), min(r, g, b)
    hue, sat, light = 0.0, 0.0, (hi + lo) / 2
    if hi != lo:
        d = hi - lo
        sat = d / (2 - hi - lo) if light > 0.5 else d / (hi + lo)
        hue = ((g - b) / d + (6 if g < b else 0)) if hi == r else (b - r) / d + 2 if hi == g else (r - g) / d + 4
        hue /= 6
    light, sat = min(KEY_L[1], max(KEY_L[0], light)), max(KEY_S, sat)
    q = light * (1 + sat) if light < 0.5 else light + sat - light * sat
    p = 2 * light - q

    def ch(t):
        t %= 1
        return 255 * (p + (q - p) * 6 * t if t < 1 / 6 else q if t < 1 / 2 else p + (q - p) * (2 / 3 - t) * 6 if t < 2 / 3 else p)
    return ch(hue + 1 / 3), ch(hue), ch(hue - 1 / 3)


def empty_on(bg, dark: bool) -> tuple:
    return mix(bg, EMPTY_GREY, EMPTY_ALPHA if dark else EMPTY_ALPHA_LIGHT)


DARK_PAGE = (44, 44, 44)  # Anki's dark page
FAINT_FADE, FADE_STEP, DIM = 0.25, 0.05, (0.55, 0.36, 0.18, 0)


def exact_steps(colours, bg, dark: bool) -> list:
    """The four shades of colours you picked, the same on either page (calendar.js exactSteps): the
    busiest exactly the last colour, the others stepping to it from the first through OKLab; one
    colour runs from dim (into the page) to full. Only the faintest fades a little into the page,
    less where it would come too near an empty day."""
    two = isinstance(colours, (list, tuple))
    a = hexc(colours[0] if two else colours)
    b = hexc(colours[1]) if two else a

    def at(i, f):
        if two:
            return blend(a, b, i / 3) if i else mix(a, bg, f)
        return mix(a, bg, DIM[i] if i else f)
    blank, f = empty_on(bg, dark), (FAINT_FADE if two else DIM[0])
    while f > 0 and apart(at(0, f), blank) < EMPTY_APART:
        f = max(0, f - FADE_STEP)
    return [at(i, f) for i in range(3)] + [b]


def _keys_of(colours) -> list:
    """A colour, or two for a ramp, as the four shades' key colours (calendar.js keysOf)."""
    if isinstance(colours, (list, tuple)):
        return [readable(blend(hexc(colours[0]), hexc(colours[1]), i / 3)) for i in range(4)]
    return [readable(hexc(colours))] * 4


def hour_turn(c, hour: dict) -> tuple:
    """A colour's hue turned `hour["turn"]` of the way towards the night tint, the short way round,
    its lightness kept (calendar.js hourTurn)."""
    k, t = oklab(c), oklab(hexc(hour["tint"]))
    h, to = math.atan2(k[2], k[1]), math.atan2(t[2], t[1])
    turned = h + math.atan2(math.sin(to - h), math.cos(to - h)) * hour["turn"]
    C = math.hypot(k[1], k[2])
    while C > 0.01 and not fits(k[0], C * math.cos(turned), C * math.sin(turned)):
        C *= 0.95
    return from_oklab(k[0], C * math.cos(turned), C * math.sin(turned))


def day_blend(a, b, t: float) -> tuple:
    """`t` of the way from colour `a` to `b` by hue (the short way round) and colourfulness
    (calendar.js dayBlend)."""
    if t >= 1:
        return b
    p, q = oklab(a), oklab(b)
    hp, hq = math.atan2(p[2], p[1]), math.atan2(q[2], q[1])
    h = hp + math.atan2(math.sin(hq - hp), math.cos(hq - hp)) * t
    L = p[0] + (q[0] - p[0]) * t
    C = math.hypot(p[1], p[2]) + (math.hypot(q[1], q[2]) - math.hypot(p[1], p[2])) * t
    while C > 0.01 and not fits(L, C * math.cos(h), C * math.sin(h)):
        C *= 0.95
    return from_oklab(L, C * math.cos(h), C * math.sin(h))


def shades(colours, bg, dark: bool, exact: bool = False, flip_light: bool = False, darker: bool = False,
           hour: dict | None = None) -> list:
    """The four shades of a day studied, fewest reviews to most, each (its colour, its darker
    tone, its edge), for `colours` (one, or two for a ramp) on a page of colour `bg` (calendar.js
    shades). `exact`: colours you picked (exact_steps); `flip_light`: a ready ramp the other way
    round on a light page, its deep colour the busiest; `darker`: a dark page's run the other way (busier);
    `hour`: what the forest's hour does to a scenery's own colours (hour_of)."""
    pair = isinstance(colours, (list, tuple))
    keys = _keys_of(colours)
    if hour and not exact:
        keys = ([day_blend(keys[i], c, hour["share"]) for i, c in enumerate(_keys_of(hour["to"]))] if hour.get("to")
                else [hour_turn(c, hour) for c in keys])
    steps = []
    for i, L in enumerate(DARK_STEPS if dark else LIGHT_STEPS):
        k = oklab(keys[i])
        C, h = max(LIGHT_CHROMA, math.hypot(k[1], k[2])) * (DARK_CHROMA[i] if dark else 1), math.atan2(k[2], k[1])
        while C > 0.01 and not fits(L, C * math.cos(h), C * math.sin(h)):  # (colourfulness gives way, not lightness)
            C *= 0.95
        steps.append(from_oklab(L, C * math.cos(h), C * math.sin(h)))
    if exact:
        steps = exact_steps(list(colours)[::-1] if flip_light and not dark and pair else colours, bg, dark)
    if dark and darker:
        steps.reverse()
    tone, rim = (0.07, 0.22) if dark else (0.16, 0.3)
    return [(c, mix(c, DARK, tone), mix(c, DARK, rim)) for c in steps]


def contrast(a, b) -> float:
    """WCAG's contrast ratio between two colours."""
    def lum(c):
        r, g, b_ = (_lin(v) for v in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# a colour you pick that stands out from a page less than this (WCAG's ratio) is hard to see on it
LOW_CONTRAST = 1.5
PAGES = {"dark": DARK_PAGE, "light": (245, 245, 245)}


def faint_on(colours) -> list:
    """The pages ("light", "dark") on which your busiest colour hardly stands out (the settings say so)."""
    top = hexc(colours[1] if isinstance(colours, (list, tuple)) else colours)
    return [page for page, bg in PAGES.items() if contrast(top, bg) < LOW_CONTRAST]


# ---- the tiles' textures (calendar.js plainTile, and the sceneries' calendarTile) ----
TILE = 9


def hash_str(s: str) -> int:
    """calendar.js's hashStr (FNV-1a)."""
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _plain(pal, edge, v, T):
    out = {}
    for y in range(T):
        for x in range(T):
            e = y == T - 1 or x == T - 1
            out[x, y] = edge if e else pal[1 if (hash_str(f"{v},{x >> 1},{y >> 1}") & 3) == 0 else 0]
    return out


MOONLIGHT = (0xfa, 0xec, 0xaa)


def _brush(pal, _edge, v, T):  # starry_night.js
    n, tones, out = T - 1, [pal[0], pal[1], mix(pal[0], MOONLIGHT, 0.14), pal[0]], {}
    noise = lambda x, y, s: (hash_str(f"{s},{x},{y}") % 1000) / 1000  # noqa: E731
    for y in range(n):
        x, k = (-1 if (y + v) % 2 else -2 - (v & 1)), 0
        while x < n:
            length, c = (3 if noise(x, y, v) < 0.5 else 4), tones[(y * 3 + k + v) % 4]
            for i in range(length):
                px = x + i
                if px < 0 or px >= n:
                    continue
                if ((px == 0 and i == 0) or (px == n - 1 and i == length - 1)) and noise(px, y, 9 + v) < 0.5:
                    continue
                out[px, y] = c
            x += length
            k += 1
    return out


def _scanlines(pal, _edge, _v, T):  # synthwave.js
    n = T - 1
    return {(x, y): mix(pal[0], (0, 0, 0), 0.2) if y % 2 else pal[0] for y in range(n) for x in range(n)}


RIB_LIGHT = (255, 250, 235)


def _pumpkin(pal, _edge, _v, T):  # pumpkin_patch.js
    n, out = T - 1, {}
    for y in range(n):
        for x in range(n):
            if ((x in (0, n - 1)) and (y in (0, n - 1))) or (y == 0 and x in (3, 4)):
                continue
            out[x, y] = pal[1] if x in (2, 5) else mix(pal[0], RIB_LIGHT, 0.1) if x in (1, 4) else pal[0]
    return out


ICE_SHINE = (255, 250, 235)


def _ice(pal, _edge, v, T):  # frozen_market.js
    n, out = T - 1, {}
    for y in range(n):
        for x in range(n):
            d, corner = x + y, (x in (0, n - 1)) and (y in (0, n - 1))
            out[x, y] = (mix(pal[0], ICE_SHINE, 0.22) if corner else mix(pal[0], ICE_SHINE, 0.2) if d == 3 or (d == 5 and v % 2)
                         else pal[1] if d > 9 else pal[0])
    return out


CHALK = (0xee, 0xf0, 0xe4)


def _chalk(pal, _edge, v, T):  # chalkboard.js
    n, out = T - 1, {}
    noise = lambda x, y, s: (hash_str(f"{s},{x},{y}") % 1000) / 1000  # noqa: E731
    gap = tuple(c * 0.72 for c in pal[0])
    for y in range(n):
        for x in range(n):
            side, corner = x in (0, n - 1) or y in (0, n - 1), x in (0, n - 1) and y in (0, n - 1)
            if (corner and noise(x, y, 200 + v) < 0.7) or (side and noise(x, y, 210 + v) < 0.12):
                continue
            band = (x + y + 1 + v) // 4
            shift = 1 if noise(band, y >> 1, 220 + v) < 0.4 else 0
            if (x + y + 1 + v + shift) % 4 < 2:
                c = (mix(pal[0], gap, 0.5) if noise(x, y, 230 + v) < 0.14
                     else mix(pal[0], CHALK, 0.2) if noise(x, y, 240 + v) > 0.88 else pal[0])
            else:
                c = mix(pal[0], gap, 0.45) if noise(x, y, 250 + v) < 0.2 else gap
            out[x, y] = c
    return out


BAMBOO_JOINTS = ((2, 5), (4, 1), (1, 5), (5, 3))


def _canes(pal, _edge, v, T):  # bamboo.js
    n, s, out = T - 1, pal[0], {}
    scaled = lambda c, k: tuple(max(0, min(255, q * k)) for q in c)  # noqa: E731
    joints = BAMBOO_JOINTS[v % 4]
    for y in range(n):
        for x in range(n):
            if x in (0, n - 1) and y in (0, n - 1):
                continue
            cx, j = x & 3, joints[0 if x < 4 else 1]
            c = scaled(s, 1.14) if cx == 0 else scaled(s, 0.78) if cx == 3 else scaled(s, 0.84) if cx == 2 else s
            if y == j:
                c = scaled(s, 0.7)
            elif y == j - 1 and cx < 3:
                c = scaled(s, 1.2)
            out[x, y] = c
    return out


RIME = (236, 248, 246)


def _rime(pal, _edge, v, T):  # misty_valley.js
    n, out = T - 1, {}
    for y in range(n):
        for x in range(n):
            if x in (0, n - 1) and y in (0, n - 1):
                continue
            frost = (0.25 if (x + v) % 3 == 2 else 0.62) if y == 0 else 0.32 if y == 1 and (x + v) % 4 == 1 else 0
            out[x, y] = mix(pal[0], RIME, frost) if frost else pal[0]
    return out


# a giraffe's hide (savanna_sundown.js hidePass, a drawn shape): each day four patches round its
# middle, each point nudged by the day, parted by the coat's paler network. The Heatmap tab's sample
# is a day alone, each variant one of SAMPLE_DAYS, drawn as the heatmap draws that day with no
# neighbours (the patches of the days round it, which cross its border there, aren't in a sample)
HIDE_POINTS, HIDE_NUDGE = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)), 1.6
COAT_LINE, COAT_DARK, COAT_LIFT = (255, 240, 214), (96, 52, 30), 0.16
SAMPLE_DAYS = ("2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08")


def coat_line(c, k: float = 1):
    pale = c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114 > 172
    return mix(c, COAT_DARK, COAT_LIFT * 0.8 * k) if pale else mix(c, COAT_LINE, COAT_LIFT * k)


def _hide(pal, _edge, v, T):  # savanna_sundown.js
    pts = []
    for k, (fx, fy) in enumerate(HIDE_POINTS):
        h = hash_str(f"hide|{k}|{SAMPLE_DAYS[v]}")
        pts.append((fx * T + ((h & 15) / 15 * 2 - 1) * HIDE_NUDGE, fy * T + (((h >> 4) & 15) / 15 * 2 - 1) * HIDE_NUDGE))
    patch = {}
    for y in range(T):
        for x in range(T):
            best, bd = -1, math.inf
            for j, (px, py) in enumerate(pts):
                d = (px - x) ** 2 + (py - y) ** 2
                if d < bd:
                    best, bd = j, d
            patch[x, y] = best
    out = {}
    for (x, y), j in patch.items():
        r, b = patch.get((x + 1, y), j), patch.get((x, y + 1), j)
        out[x, y] = coat_line(pal[0]) if r != j or b != j else pal[0]
    return out


# lagoon bubbles (coral_reef.js, calendarShaped): each day a round bubble, the sunlit ripple across
# it, its lower right rim in its edge and a glint at its upper left; a pixel bigger with no spaces
BUBBLE_LIT, BUBBLE_GLINT = (255, 255, 255), 0.5


def _bubbles(pal, edge, v, T):  # coral_reef.js
    S = T - 1 if T > 9 else T
    h = S / 2
    r2, lit, glint, out = h * h + 0.25, mix(pal[0], BUBBLE_LIT, 0.15), mix(pal[0], BUBBLE_LIT, BUBBLE_GLINT), {}
    inside = lambda x, y: 0 <= x < S and 0 <= y < S and (x + 0.5 - h) * (x + 0.5 - h) + (y + 0.5 - h) * (y + 0.5 - h) <= r2  # noqa: E731
    gx = gy = math.floor(S * 0.28)
    for y in range(S):
        for x in range(S):
            if not inside(x, y):
                continue
            if not inside(x + 1, y) or not inside(x, y + 1):
                out[x, y] = edge
            elif (x == gx and y in (gy, gy + 1)) or (y == gy and x == gx + 1):
                out[x, y] = glint
            else:
                w = math.floor(math.sin(x * 0.8 + v * 1.9) * 1.1 + 0.5)  # (Math.round)
                r = (y + w + v) % 4
                out[x, y] = lit if r == 0 else pal[1] if r == 1 else pal[0]
    return out


RINGS_DARK = (24, 8, 44)


# heat haze (psychedelic.js hazeLive, a moving shape): the weeks seen through rippled glass. The
# Heatmap tab's sample is still: a day alone, as the heatmap draws it at its first moment with no
# day round it (ink on all four sides), the day at column 2v, row 3 of the weeks, T pixels a day
HAZE_RING, HAZE_INK, HAZE_BEND, HAZE_RISE = 0.2, 0.28, 0.8, 1.4


def _haze(pal, _edge, v, T):
    x0, y0, out = 1 + 2 * v * T, 4 + 3 * T, {}
    cx = T + 0.5 if v & 1 else -0.5
    cols = (tuple(int(c) for c in pal[0]), tuple(int(c) for c in mix(pal[0], RINGS_DARK, HAZE_RING)), tuple(int(c) for c in mix(pal[0], RINGS_DARK, HAZE_INK)))
    for ly in range(T):
        for lx in range(T):
            x, y = x0 + lx, y0 + ly
            fx = math.floor(x + 0.5 + HAZE_BEND * math.sin(y * 0.16 + x * 0.05)) - x0
            fy = math.floor(y + 0.5 + HAZE_RISE * math.sin(x * 0.14 + 1.3)) - y0
            if not (0 <= fx < T and 0 <= fy < T):
                continue
            if fx in (0, T - 1) or fy in (0, T - 1):
                out[lx, ly] = cols[2]
            else:
                out[lx, ly] = cols[math.floor(math.hypot(fx + 0.5 - cx, fy + 1) / 2.6) & 1]
    return out


def _flat(pal, edge, _v, T):
    return {(x, y): edge if x == T - 1 or y == T - 1 else pal[0] for y in range(T) for x in range(T)}


# each environment that draws its tiles in a medium of its own (calendarTile), and how
DRAWERS = {"plain": _plain, "flat": _flat, "starry_night": _brush, "synthwave": _scanlines, "pumpkin_patch": _pumpkin, "frozen_market": _ice, "chalkboard": _chalk,
           "misty_valley": _rime, "bamboo": _canes, "savanna_sundown": _hide, "coral_reef": _bubbles,
           "psychedelic": _haze}


def tile_pixels(drawer: str, shade, v: int = 0) -> dict:
    """A tile's pixels, (x, y) -> colour, as `drawer` (a DRAWERS key) draws it in `shade`
    (shades()'s colour, tone, edge); pixels left out are the page's."""
    colour, tone, edge = shade
    return DRAWERS.get(drawer, _plain)([colour, tone], edge, v, TILE)


def out_of_season(cfg: dict) -> dict:
    """The changes that put a seasonal scenery's colours or tiles, chosen in its week, back to the
    defaults once the week is over (as the scenery itself goes): {} while there are none."""
    change = {}
    choice = cfg.get("calendar_colours")
    if isinstance(choice, str) and choice.startswith(READY_PREFIX) and choice[len(READY_PREFIX):] in SCENERY_READY:
        spec = presets.by_key().get(choice[len(READY_PREFIX):])
        if spec is not None and spec.season and not presets.unlocked(spec, today(cfg)):
            change["calendar_colours"] = MATCH
    if cfg.get("calendar_tiles") in TILE_SEASONS and not tile_shown(cfg["calendar_tiles"], cfg):
        change["calendar_tiles"] = TILE_FOLLOW
    return change


def follow_season(cfg: dict) -> dict:
    """The config with a seasonal scenery's heatmap colours or tiles gone once its week is over
    (out_of_season), saved if that changed it; as seasons.follow_season does for the scenery."""
    change = out_of_season(cfg)
    if not change:
        return cfg
    cfg = dict(cfg, **change)
    save_config(cfg)
    return cfg

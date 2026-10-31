"""Layout's Background: Anki's top toolbar and bottom bar, separate pages of their own over and under
the forest, wear the colours of the scene's edge beside them, blurred and still, so the forest isn't
framed by two flat strips of another colour (2026-10-31). The forest stays in the window; its page
sends, for each bar, a band of the scene's edge squeezed to a few columns (drawn smoothly across the
bar) with its average colour (web/core.js AF.barEdges), as "<channel>:bars:{json}" when the scene is
drawn; "<channel>:bars" alone takes them away. (Slices of the scene itself, laid out under the bars,
looked broken at the seams and hid what walked there.) Each bar wears it only while it shows Anki's
own page colour: a theme or another add-on that paints it keeps its own. The toolbar only where its
links stand on Anki's own pill (its card style, body.fancy): an older Anki's links stand on the bar
itself, and its text was made for the page's colour. Leaving the deck list and the deck screens, for
a review say, takes them away."""

from __future__ import annotations

import json
import re

from aqt import mw

from .state import log

STYLE_ID = "af-bars"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
PNG = re.compile(r"^data:image/png;base64,[A-Za-z0-9+/=]+$")
MAX_PICTURE = 20_000  # characters: a bar's band is a few pixels, well under 1 KB
# (in each bar's page: the band over its colour, as a style of its own, over Anki's page colour only)
JS = """(function (look, needsPill) {
  var style = document.getElementById(%(id)s);
  if (!look) { if (style) style.remove(); return; }
  if (!style) {
    if (needsPill && !document.body.classList.contains('fancy')) return;
    var probe = document.createElement('div');
    probe.style.background = 'var(--canvas)';
    document.body.appendChild(probe);
    var canvas = getComputedStyle(probe).backgroundColor;
    probe.remove();
    if (getComputedStyle(document.body).backgroundColor !== canvas) return;
    style = document.createElement('style');
    style.id = %(id)s;
    document.head.appendChild(style);
  }
  style.textContent = 'html, body { background: ' + look.colour + (look.picture ? ' url("' + look.picture + '") 0 0 / 100%% 100%% no-repeat' : '')
    + ' !important; image-rendering: auto; }';
})(%(look)s, %(pill)s)"""

_looks: tuple | None = None  # (the toolbar's, the bottom bar's): {"colour", "picture"}, or None


def _bars() -> list:
    """(its web view, its look, whether it needs Anki's pill) for each bar this Anki has."""
    top, bottom = _looks or (None, None)
    toolbar = getattr(getattr(mw, "toolbar", None), "web", None)
    return [(web, look, pill) for web, look, pill in ((toolbar, top, True), (getattr(mw, "bottomWeb", None), bottom, False)) if web]


def _apply(web, look, pill: bool) -> None:
    try:
        web.eval(JS % {"id": json.dumps(STYLE_ID), "look": json.dumps(look), "pill": json.dumps(pill)})
    except Exception:
        log("could not colour Anki's bars")


def _look(colour, picture) -> dict | None:
    if not isinstance(colour, str) or not HEX.match(colour):
        return None
    ok = isinstance(picture, str) and len(picture) <= MAX_PICTURE and PNG.match(picture)
    return {"colour": colour, "picture": picture if ok else ""}


def tint(args: list) -> None:
    """From the forest's page: each bar's band and colour (as JSON), or nothing (none)."""
    global _looks
    try:
        sent = json.loads(":".join(args)) if args else None
    except ValueError:
        sent = None
    looks = None
    if isinstance(sent, dict):
        top, bottom = _look(sent.get("topColour"), sent.get("top")), _look(sent.get("bottomColour"), sent.get("bottom"))
        looks = (top, bottom) if top and bottom else None
    _looks = looks
    for web, look, pill in _bars():
        _apply(web, look, pill)


def on_page_loaded(web) -> None:
    """A bar drawn afresh (Anki redraws them as screens change) wears its band again."""
    if _looks is None:
        return
    for bar, look, pill in _bars():
        if web is bar:
            _apply(web, look, pill)


def on_state_change(new_state: str, _old_state: str) -> None:
    """Off the screens the forest stands behind (a review, say): Anki's own bars. Back on them, the
    forest's page sends its bands again as it is drawn."""
    if new_state not in ("deckBrowser", "overview") and _looks is not None:
        tint([])

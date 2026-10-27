"""Put the docs' moving pictures side by side, as the README and the AnkiWeb page show them:
a few grid GIFs in docs/grid/ made from the per-scenery GIFs (docs/animated/, dev/make_gif.py)
and the Nature GIFs (docs/nature/).

    python3 dev/docs_grids.py        (npm run docs-grids; npm run docs-pictures runs it too)

    docs/grid/sceneries.gif   the free edition's sceneries
    docs/grid/plus.gif        the ones only Memory Forest Plus has (here, where editions.json is)
    docs/grid/nature.gif      the three Nature levels in one row

The sceneries come in the order they arrived in that edition (release_notes.json: the first
version with an item that `needs` the scenery there; the first release's in the catalogue's
order), with their preset's name on each, so a new scenery joins the end by itself once
it has its docs/animated GIF. A seasonal one is left out: it is a surprise.

Two to a row, each at half the GIF's size: the recordings draw every canvas pixel as a 2 x 2
block, so half is the canvas exactly, one pixel a pixel, and two of them are as wide as one
was (three to a row would scale by two thirds and smear the pixels). The Nature row has three,
scaled down smoothly: they show what happens to the whole forest, not its detail. Every tile
shows the same frame at the same moment, so they loop together, seamlessly where the inputs do.
Each name sits on a see-through black badge in its tile's bottom-left corner (--labels under: in a
strip under it), in Nunito (dev/fonts/).
One palette for the whole GIF, no dithering, then gifsicle. Needs ffmpeg and gifsicle.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

import editions

import events
import i18n
import presets
import release_notes

DOCS = os.path.join(ADDON, "docs")
SCENERY_GIFS = os.path.join(DOCS, "animated")
NATURE_GIFS = os.path.join(DOCS, "nature")
OUT = os.path.join(DOCS, "grid")
# the sheet: Anki's dark page around the tiles (as the heatmap pictures have it), a name under each
BG = (44, 44, 44)
MARGIN, GAP, LABEL_H, RADIUS = 6, 8, 26, 6
# a name over its tile sits on a badge in its bottom-left corner: this far in from both edges (on
# a 388 px tile; less on a smaller one), padded and rounded so, and its text this many px bigger
# than under the tile. The badge is 60% black, blended into each frame, so the scene shows through
# faintly: the least of the 60-75% tried, and every name keeps a contrast of 6 or more (WCAG AA
# asks 4.5) against the brightest of the scene behind it on its tile's busiest frame (2026-10-27)
BADGE_INSET, BADGE_PAD, BADGE_RADIUS, BADGE_BG, INSIDE_GROW = 6, (7, 3), 5, (0, 0, 0, 153), 1
# every name in Nunito Bold (dev/fonts/, with its licence; only the docs use it): a rounded
# humanist sans whose open shapes stay clear at this small size, and whose round ends sit well
# with the pixel art; in a soft white
FONT = os.path.join(HERE, "fonts", "Nunito", "Nunito[wght].ttf")
FONT_PX, FONT_WEIGHT, TEXT = 14, 700, (244, 242, 236)
NATURE_TILE = (256, 128)
# colours for the whole GIF, and how hard gifsicle may squeeze it (0: not lossy)
COLOURS, LOSSY = 256, 0


def arrival(key: str, edition: str | None, versions: list) -> tuple:
    """(the version's age, the item's place in it) where `key` first arrived in `edition`,
    or (-1, 0) when no note names it (it came with the first release)."""
    oldest_first = list(reversed(versions))
    for age, v in enumerate(oldest_first):
        for pos, entry in enumerate(release_notes.items(v)):
            needs = (entry.get("needs") or "").split()
            if f"scenery:{key}" not in needs:
                continue
            only = [n.partition(":")[2] for n in needs if n.startswith("edition:")]
            if not only or edition in only:
                return age, pos
    return -1, 0


def groups() -> list:
    """(output name, [(gif path, name)]) for each scenery grid, in the pages' order."""
    order = {p.key: i for i, p in enumerate(presets.FOREST_PRESETS)}
    shown = [p for p in presets.FOREST_PRESETS if not p.season and p.environment != presets.DAILY
             and os.path.exists(os.path.join(SCENERY_GIFS, p.key + ".gif"))]
    versions = release_notes.load()
    if editions.available():
        base = editions.scenery("base")["presets"]
        plus = {p["key"] for p in editions.plus_only()}
        sets = (("sceneries", "base", base), ("plus", "plus", plus))
    else:  # the public repo: everything here is the edition
        sets = (("sceneries", None, {p.key for p in shown}),)
    out = []
    for name, edition, keys in sets:
        chosen = sorted((p for p in shown if p.key in keys), key=lambda p: (*arrival(p.key, edition, versions), order[p.key]))
        out.append((name, [(os.path.join(SCENERY_GIFS, p.key + ".gif"), p.label) for p in chosen]))
    return out


def nature() -> list:
    english = i18n.english()
    return [(os.path.join(NATURE_GIFS, level + ".gif"), english.get(label, label)) for level, label in events.NATURE_LABELS.items()]


def font(size: int):
    """The label font at `size`; a system one if its file is missing."""
    from PIL import ImageFont
    try:
        face = ImageFont.truetype(FONT, size)
    except OSError:
        for path in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(path, size - 1)
            except OSError:
                continue
        return ImageFont.load_default()
    face.set_variation_by_axes([FONT_WEIGHT if a.get("name") in (b"Weight", "Weight") else a["default"] for a in face.get_variation_axes()])
    return face


def label_layer(size: tuple, xy: tuple, anchor: str, text: str, inside: bool):
    """A transparent layer of `size` with a tile's name: under the tile, at `xy` (PIL's text
    `anchor`); over it (`inside`), on a badge in the bottom-left corner of a tile `size` big, a
    size up, so it reads over anything."""
    from PIL import Image, ImageDraw
    face = font(FONT_PX + (INSIDE_GROW if inside else 0))
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if inside:
        # the badge fits the font's caps and descenders, whatever this name's letters are
        cap, desc = -face.getbbox("H", anchor="ls")[1], face.getbbox("gjpqy", anchor="ls")[3]
        left, _top, right, _bottom = face.getbbox(text, anchor="ls")
        inset = max(4, BADGE_INSET * size[0] // 388)
        (px, py), h = BADGE_PAD, cap + desc + 2 * BADGE_PAD[1]
        box = (inset, size[1] - inset - h, inset + right - left + 2 * px, size[1] - inset)
        draw.rounded_rectangle(box, radius=BADGE_RADIUS, fill=BADGE_BG)
        xy, anchor = (box[0] + px - left, box[1] + py + cap), "ls"
    text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(text_layer).text(xy, text, fill=TEXT + (255,), font=face, anchor=anchor)
    layer.alpha_composite(text_layer)
    return layer


def frames(path: str) -> tuple:
    """(RGB frames, their durations in ms) of a GIF."""
    from PIL import Image
    im = Image.open(path)
    out, durations = [], []
    for i in range(im.n_frames):
        im.seek(i)
        out.append(im.convert("RGB"))
        durations.append(im.info.get("duration", 100))
    return out, durations


def at(durations: list, t: float) -> int:
    """The frame showing `t` ms into a loop of these durations."""
    t %= sum(durations)
    for i, d in enumerate(durations):
        if t < d:
            return i
        t -= d
    return len(durations) - 1


def sheet(tiles: list, per_row: int, size: tuple | None, out: str, inside: bool = True) -> None:
    """Write the grid GIF of `tiles` [(gif, name)], `per_row` across, each `size` (None: half
    its GIF, pixel for pixel), the last row centred; each name on a badge in its tile's corner
    (`inside`), or in a strip under it."""
    from PIL import Image, ImageDraw
    sources = [frames(path) for path, _name in tiles]
    w0, h0 = sources[0][0][0].size
    tw, th = size or (w0 // 2, h0 // 2)
    rows = -(-len(tiles) // per_row)
    label_h = 0 if inside else LABEL_H
    width = 2 * MARGIN + per_row * tw + (per_row - 1) * GAP
    height = 2 * MARGIN + rows * (th + label_h) + (rows - 1) * GAP
    # the timeline is the longest input's; a shorter one repeats in it
    durations = max((d for _f, d in sources), key=sum)
    places = []
    for i in range(len(tiles)):
        row, col = divmod(i, per_row)
        in_row = min(per_row, len(tiles) - row * per_row)
        x = MARGIN + (width - 2 * MARGIN - (in_row * tw + (in_row - 1) * GAP)) // 2 + col * (tw + GAP)
        places.append((x, MARGIN + row * (th + label_h + GAP)))
    back = Image.new("RGBA", (width, height), BG)
    layers = []
    for (x, y), (_path, name) in zip(places, tiles):
        if inside:
            layers.append(label_layer((tw, th), (0, 0), "ls", name, True))
        else:
            back.alpha_composite(label_layer(back.size, (x + tw // 2, y + th + LABEL_H // 2 + 1), "mm", name, False))
    back = back.convert("RGB")
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw - 1, th - 1), radius=RADIUS, fill=255)
    resample = Image.NEAREST if size is None else Image.LANCZOS
    with tempfile.TemporaryDirectory() as tmp:
        t = 0.0
        for n, d in enumerate(durations):
            frame = back.copy()
            for i, ((x, y), (shots, times)) in enumerate(zip(places, sources)):
                tile = shots[at(times, t + 0.5)].resize((tw, th), resample)
                if layers:
                    tile = Image.alpha_composite(tile.convert("RGBA"), layers[i]).convert("RGB")
                frame.paste(tile, (x, y), mask)
            frame.save(os.path.join(tmp, f"f{n:04d}.png"))
            t += d
        # ffmpeg takes one rate: the inputs' average, which their 60/70 ms steps are
        fps = len(durations) * 1000 / sum(durations)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", f"{fps:.4f}", "-i", os.path.join(tmp, "f%04d.png"),
                        "-vf", f"split[a][b];[a]palettegen=max_colors={COLOURS}:stats_mode=full[p];[b][p]paletteuse=dither=none",
                        "-loop", "0", out], check=True)
    subprocess.run(["gifsicle", "-b", "-O3", *([f"--lossy={LOSSY}"] if LOSSY else []), out], check=True)
    print(f"{os.path.relpath(out, ADDON) if out.startswith(ADDON) else out}: {width}x{height}, {len(tiles)} tiles, {len(durations)} frames "
          f"({os.path.getsize(out) // 1024} KB)")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Make the docs' grid GIFs.")
    ap.add_argument("--labels", choices=("inside", "under"), default="inside",
                    help="each name on a badge in its tile's corner (the default), or in a strip under it")
    ap.add_argument("--out", default=OUT, help="the folder to write to")
    a = ap.parse_args()
    inside = a.labels == "inside"
    for name, tiles in groups():
        if tiles:
            sheet(tiles, 2, None, os.path.join(a.out, name + ".gif"), inside)
    sheet(nature(), 3, NATURE_TILE, os.path.join(a.out, "nature.gif"), inside)


if __name__ == "__main__":
    main()

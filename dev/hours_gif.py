"""The hours GIFs' shared parts: the hours and their pace, the GIF writer with a palette an hour,
and the new-moon night. dev/docs_grids.py's grids (the docs) and dev/post_gifs.py's hours GIFs
(the Patreon posts) both go through the hours at this pace, so they match.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import scene

FPS = 15
HOURS = ("dawn", "day", "golden_hour", "dusk", "night")
HOLD, FADE = 35, 10  # frames an hour holds, and crossfades into the next
DEEP_AT = 22  # the new-moon night's hour of the clock
DEEP_SHARE = 0.2  # a new-moon night this much of the scene apart from the moonlit one is an hour of its own


def palette(frames: list, colours: int) -> Image.Image:
    """One palette for these frames together (a sample of them, one under another)."""
    sample = frames[:: max(1, len(frames) // 6)][:6]
    w, h = sample[0].size
    sheet = Image.new("RGB", (w, h * len(sample)))
    for i, f in enumerate(sample):
        sheet.paste(f, (0, i * h))
    return sheet.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def pick(n: int, keep: int) -> list:
    """`keep` of n frames, evenly apart."""
    keep = max(1, min(n, keep))
    return [round(i * n / keep) for i in range(keep)]


def write_gif(segments: list, out: str, label: str, fits: tuple, limit: float) -> tuple:
    """segments: (kind, frame loaders), each loader returning an RGB image: a "hold" shares one
    palette, a "fade" has a palette a frame. Each segment lasts as long as its frames at FPS,
    however many are kept. Written at the first step of `fits` [(colours, every how many
    hold frames kept, fade frames kept of FADE)] under `limit` bytes. -> (bytes, frames, seconds)."""
    for colours, every, fades in fits:
        frames, times, clock = [], [], 0.0
        for kind, seg in segments:
            idx = pick(len(seg), -(-len(seg) // every) if kind == "hold" else round(len(seg) * fades / FADE))
            rgb = [seg[i]() for i in idx]
            if kind == "hold":
                pal = palette(rgb, colours)
                frames += [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb]
            else:
                frames += [f.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in rgb]
            # (each frame until the next kept one, in the GIF's whole hundredths, the rounding carried on)
            for k, i in enumerate(idx):
                end = (idx[k + 1] if k + 1 < len(idx) else len(seg)) - i
                t = round((clock + end * 1000 / FPS) / 10) * 10 - round(clock / 10) * 10
                times.append(int(t))
                clock += end * 1000 / FPS
        buf = io.BytesIO()
        frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=times, loop=0, disposal=1, optimize=True)
        size = buf.tell()
        print(f"  {label}: {colours} colours, {len(frames)} frames: {size / 1e6:.2f} MB")
        if size <= limit:
            with open(out, "wb") as f:
                f.write(buf.getvalue())
            return size, len(frames), sum(times) / 1000
    sys.exit(f"{label}: still over {limit / 1e6:g} MB at the fewest colours and frames")


def new_moon_night(near: dt.datetime) -> dt.datetime:
    """The night nearest `near` with the moon nearest new."""
    nights = [dt.datetime.combine(near.date() + dt.timedelta(days=d), dt.time(DEEP_AT)) for d in range(-15, 16)]
    return min(nights, key=lambda t: min(scene.moon_phase(t), 1 - scene.moon_phase(t)))


def differs_images(x: Image.Image, y: Image.Image) -> float:
    """differs, for two images."""
    from PIL import ImageChops
    x, y = x.convert("RGB"), y.convert("RGB")
    box = (0, 0, x.width, x.width // 2)  # (the forest: half as tall as wide)
    diff = ImageChops.difference(x.crop(box), y.crop(box)).convert("L").point(lambda v: 255 if v else 0)
    return diff.histogram()[255] / (box[2] * box[3])

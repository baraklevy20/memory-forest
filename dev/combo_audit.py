"""Which settings does each environment actually listen to?

Environment, weather and time of day are meant to be independent. Some environments paint
their own sky, so the time of day stops mattering; some hide the ground, so the landscape
does. This renders each environment against each setting and measures how much of the
picture each setting changes: a setting the dialog offers that changes nothing is a dead
setting, however well it draws.

    python3 dev/combo_audit.py

It exits non-zero if a combination goes quiet that is not in EXPECTED_INERT below, so a
dead setting cannot come back unnoticed. Needs Chrome, and takes a few minutes.
"""

from __future__ import annotations

import base64
import concurrent.futures
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

from render_check import WORKERS, render

import scene

TIMES = ("day", "night", "dusk")
WEATHERS = ("clear", "rain", "snow", "fog")
LANDSCAPES = tuple(scene.LANDSCAPES)
TREES = 150  # the forest each combination is drawn on
# How much of the picture a setting actually changes, in per cent. Under a few per cent
# the setting is there in name only - that is what "it doesn't work" looks like.
DEAD, WEAK = 1.0, 8.0


def pixels(data_url: str):
    """Decode a canvas PNG into raw RGB, so two scenes can be compared properly."""
    raw = base64.b64decode(data_url.split(",", 1)[1])
    pos, idat, w, h, ct, bd = 8, b"", 0, 0, 6, 8
    while pos < len(raw):
        ln = struct.unpack(">I", raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", raw[pos + 8:pos + 18])
        elif typ == b"IDAT":
            idat += raw[pos + 8:pos + 8 + ln]
        pos += 12 + ln
    d = zlib.decompress(idat)
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct] * (bd // 8)
    stride, out, prev, i = w * bpp, bytearray(), bytearray(w * bpp), 0
    for _ in range(h):
        f = d[i]; i += 1
        line = bytearray(d[i:i + stride]); i += stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                line[x] = (line[x] + ((line[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                line[x] = (line[x] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        out += line
        prev = line
    return w, h, bpp, bytes(out)


def difference(a: str, b: str) -> float:
    """How much of the picture changed, as a percentage of its pixels."""
    if not a or not b:
        return -1.0
    w, h, bpp, pa = pixels(a)
    _w, _h, _b, pb = pixels(b)
    if len(pa) != len(pb):
        return 100.0
    n = sum(1 for i in range(0, len(pa), bpp) if pa[i:i + 3] != pb[i:i + 3])
    return round(100 * n / (w * h), 1)


def cases() -> list:
    out = []
    for env in scene.ENVIRONMENTS:
        for t in TIMES:
            out.append((f"{env}|time|{t}", {"environment": env, "landscape": "meadow", "weather": "clear", "time_of_day": t}, TREES))
        for w in WEATHERS:
            out.append((f"{env}|weather|{w}", {"environment": env, "landscape": "meadow", "weather": w, "time_of_day": "day"}, TREES))
        for land in LANDSCAPES:
            out.append((f"{env}|landscape|{land}", {"environment": env, "landscape": land, "weather": "clear", "time_of_day": "day"}, TREES))
    return out


# Combinations that genuinely cannot show a setting, and why. Everything else that goes
# quiet is a bug. Keep the reason honest: if it reads like an excuse, fix the environment
# instead of adding a line here.
EXPECTED_INERT: dict = {}


def main() -> None:
    todo = cases()
    print(f"{len(todo)} renders\n")
    shots = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for name, r in pool.map(render, todo):
            shots[name] = r.get("png") or ""
            if r.get("errors"):
                print(f"ERROR {name}: {r['errors'][0].splitlines()[0][:80]}")

    print(f"\n{'environment':<16} {'time of day':<22} {'weather':<22} landscape")
    problems = []
    for env in scene.ENVIRONMENTS:
        row = []
        for axis, values in (("time of day", TIMES), ("weather", WEATHERS), ("landscape", LANDSCAPES)):
            base = shots.get(f"{env}|{axis.split()[0]}|{values[0]}")
            diffs = {v: difference(base, shots.get(f"{env}|{axis.split()[0]}|{v}")) for v in values[1:]}
            worst = max(diffs.values()) if diffs else 0
            detail = " ".join(f"{v}:{d}%" for v, d in diffs.items())
            row.append(detail)
            for v, d in diffs.items():
                if d < 0:
                    problems.append((env, axis, v, "did not render"))
                elif d <= DEAD:
                    problems.append((env, axis, v, f"changes {d}% of the picture - effectively nothing"))
                elif d <= WEAK and worst <= WEAK:
                    problems.append((env, axis, v, f"changes only {d}% of the picture"))
        print(f"{env:<16} {row[0]:<22} {row[1]:<22} {row[2]}")

    unexpected = [p for p in problems if (p[0], p[1], p[2]) not in EXPECTED_INERT]
    known = {(p[0], p[1], p[2]) for p in problems}
    stale = [k for k in EXPECTED_INERT if k not in known]

    print(f"\n{len(problems)} combinations where the setting barely shows:")
    for env, axis, value, what in problems:
        mark = "   " if (env, axis, value) in EXPECTED_INERT else ">> "
        print(f"  {mark}{env:<15} {axis} = {value:<10} {what}")
    if stale:
        print("\nthese no longer need an exception, drop them from EXPECTED_INERT:")
        for env, axis, value in stale:
            print(f"    {env:<15} {axis} = {value}")
    if unexpected:
        print(f"\n{len(unexpected)} settings that do nothing and have no reason to (marked >> above)")
        sys.exit(1)
    print("\nevery setting changes the picture, or says in EXPECTED_INERT why it cannot")


if __name__ == "__main__":
    main()

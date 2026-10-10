"""Draw the small icon beside each Nature level on the Forest tab, with the forest's own
engine in headless Chrome: Peaceful, a full-grown tree by a pond (the pond a missed day
leaves there); Wild, the same tree burning, charred by the engine and in its flames; and
Merciless, the asteroid. Each is saved as settings/nature/<level>.png, ICON pixels square.

    python3 dev/nature_icons.py

Needs Chrome.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
sys.path.insert(0, ADDON)
sys.path.insert(0, HERE)

from render_check import CHROME, scripts

OUT = os.path.join(ADDON, "settings", "nature")
ICON = 16

DRAW = """
const AF = window.AnkiForest, { sprite } = AF.pixel, noise = AF.events.noise, N = %ICON%;
const env = { theme: { hzStep: 0, haze: '#ffffff' }, mood: { special: 'natural' }, spriteKey: 'nature-icon' };
const SEED = 11, TREE_H = 13;
const layer = () => { const c = document.createElement('canvas'); c.width = N; c.height = N; return [c, c.getContext('2d')]; };
const px = (g, x, y, c) => { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), 1, 1); };
// the visible part of a sprite, so it can be set down on its real pixels
function trim(cv) {
  const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
  let x0 = cv.width, y0 = cv.height, x1 = -1, y1 = -1;
  for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) if (d[(y * cv.width + x) * 4 + 3]) {
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  const c = document.createElement('canvas'); c.width = x1 - x0 + 1; c.height = y1 - y0 + 1;
  c.getContext('2d').drawImage(cv, -x0, -y0); return c;
}
const tree = burn => trim(sprite({ stage: AF.STAGE.MATURE, kind: 0, size: 1, health: 0, variant: 0, seed: SEED, burn }, TREE_H, 0, env));

// a pond, as web/ponds.js draws one in the natural forest: a rim, deeper water at the back,
// a glint, and reeds at its edge
function pond(g, cx, cy, w, h) {
  const water = AF.u.hex('#8fbcd8'), c0 = water, c1 = AF.u.mix(c0, [255, 255, 255], 0.45), deep = AF.u.mix(c0, [0, 0, 0], 0.18);
  const edge = AF.u.mix(AF.u.hex('#4f7a3a'), [0, 0, 0], 0.2);
  AF.u.ellipseFill(g, cx, cy, w, h, (q, x, y) => q > 0.8 ? edge : y < cy - h * 0.2 ? deep : ((x * 3 + y * 7) % 11 === 0 ? c1 : c0));
  g.fillStyle = AF.u.rgb(c1); g.fillRect(Math.round(cx - w * 0.2), Math.round(cy - h * 0.05), Math.max(2, Math.round(w * 0.18)), 1);
  for (const [x, hh] of [[cx + w / 2 - 1, 3], [cx + w / 2 - 2, 2]]) { g.fillStyle = '#2f4a2a'; g.fillRect(Math.round(x), Math.round(cy - hh), 1, hh); px(g, x, cy - hh - 1, '#8a6a3a'); }
}

// Wild's flames on the burnt side of the crown, as web/events/fire.js draws them at a blaze
const FLAME = ['#fff3b0', '#ffc94a', '#ff8a2a', '#d9471b', '#9c2a14'];
function flames(g, t, ox, oy) {
  const d = t.getContext('2d').getImageData(0, 0, t.width, t.height).data, cols = [];
  for (let x = 0; x < t.width; x++) for (let y = 0; y < t.height; y++) if (d[(y * t.width + x) * 4 + 3]) { cols.push([x, y]); break; }
  const side = AF.burnSide(SEED), reach = AF.burnReach(1), n = cols.length;
  const burning = cols.filter((c, i) => { const u = n > 1 ? i / (n - 1) : 0; return (side ? 1 - u : u) < reach - 0.05; });
  const tall = t.height * 0.35;
  burning.forEach(([x, top], i) => {
    const m = burning.length, mid = 1 - Math.abs(i - (m - 1) / 2) / (m / 2 + 0.5);
    const hh = Math.round(tall * (0.35 + 0.65 * mid ** 0.7) * (0.6 + 0.5 * noise(x * 3 + SEED, 0)));
    for (let j = -1; j <= hh; j++) {
      const q = hh > 0 ? j / hh : 0;
      if (q > 0.5 && noise(x + j * 31, SEED) < q * 0.7) continue;
      px(g, ox + x, oy + top + 1 - j, FLAME[Math.min(FLAME.length - 1, Math.floor(q * FLAME.length))]);
    }
  });
}

// Merciless's asteroid, in the colours web/events/asteroid.js gives it as it comes down: a
// dark rock, hot on its leading edge, with a tail of fire behind it
const FIRE = ['#5a1208', '#9c2a14', '#d9471b', '#ff8a2a', '#ffc94a', '#fff3b0'];
function asteroid(g, x, y, r) {
  const TAIL = 11;
  for (let i = TAIL; i >= 1; i--) {  // far end first, so the hotter part lies on top
    const col = FIRE[Math.max(0, 5 - Math.floor(i / 2))], w = i < 4 ? 2 : i < 8 ? 1 : 0;
    for (let k = -w; k <= w; k++) if (i < 8 || noise(i, k) < 0.7) px(g, x + i * 0.8 + k * 0.6, y - i * 0.8 + k * 0.6, col);
  }
  const disc = (rr, c) => { for (let dy = -rr; dy <= rr; dy++) for (let dx = -rr; dx <= rr; dx++) if (dx * dx + dy * dy <= rr * rr + rr * 0.6) px(g, x + dx, y + dy, c); };
  disc(r, '#3a3230');
  disc(Math.max(0, r - 2), '#2a2320');
  px(g, x + 1, y - 1, '#6a605a');
  for (const [dx, dy] of [[-r, 0], [-r, 1], [-r + 1, 2], [0, r], [1, r], [-1, r]]) px(g, x + dx, y + dy, '#ffc94a');  // the leading edge, glowing
}

function peaceful() {
  const [c, g] = layer(), t = tree(0);
  g.drawImage(t, 1, N - t.height - 1);
  pond(g, N - 5, N - 3, 9, 5);
  return c;
}
function wild() {
  const [c, g] = layer(), t = tree(1), ox = Math.round((N - t.width) / 2), oy = N - t.height;
  g.drawImage(t, ox, oy);
  flames(g, t, ox, oy);
  return c;
}
function merciless() {
  const [c, g] = layer();
  asteroid(g, 5, 10, 3);
  return c;
}
const out = {};
for (const [k, f] of [['peaceful', peaceful], ['wild', wild], ['merciless', merciless]]) out[k] = f().toDataURL();
document.getElementById('o').textContent = JSON.stringify(out);
"""


def main() -> None:
    page = ("<!doctype html><meta charset=utf-8><pre id=o></pre>"
            f"<script>{scripts()}</script><script>{DRAW.replace('%ICON%', str(ICON))}</script>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(page)
        path = fh.name
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--dump-dom", "file://" + path],
                             capture_output=True, text=True, timeout=120).stdout
    finally:
        os.unlink(path)
    m = re.search(r'<pre id="?o"?>(.*?)</pre>', dom, re.S)
    if not m or not m.group(1).strip():
        raise SystemExit("the page drew nothing")
    os.makedirs(OUT, exist_ok=True)
    for level, url in json.loads(html.unescape(m.group(1))).items():
        with open(os.path.join(OUT, f"{level}.png"), "wb") as f:
            f.write(base64.b64decode(url.split(",", 1)[1]))
        print(f"  {level}")


if __name__ == "__main__":
    main()

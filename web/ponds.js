/* Memory Forest — ponds (long breaks) and puddles (after rain). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, mixHex, rgb, clamp, ellipseFill, pxLine } = AF.u;
const { GROUND_BOTTOM, ROWS_TOP } = AF.GEOM;
const colWidth = AF.colWidth;

const DEFAULT_WATER = '#8fbcd8';
// a pond spans its slots and a little more, never smaller than POND_MIN_W (in env.u) by
// POND_MIN_H pixels, and is POND_ASPECT as deep as it is wide; reeds stand at its edge
const POND_OVERHANG = 1.05, POND_MIN_W = 8, POND_MIN_H = 5, POND_ASPECT = 0.34, POND_REEDS = 5;
// puddles sit in the widest gaps of the front row: at most MAX_PUDDLES, between
// PUDDLE_MIN_W and PUDDLE_MAX_W wide (in env.u), PUDDLE_ASPECT as deep as wide
const MAX_PUDDLES = 4, PUDDLE_MIN_W = 4, PUDDLE_MAX_W = 8, PUDDLE_ASPECT = 0.3;
// a pond reaches back POND_BACK of its depth behind its own row and is at most POND_ROWS
// row gaps deep, so it stays within the two rows kept clear in front of it; a forest
// too young for a second row gives it POND_LONE_ROW of the ground instead
const POND_BACK = 0.35, POND_ROWS = 2.2, POND_LONE_ROW = 0.2, POND_SKY_GAP = 2;
// a front-row pond may spill this far (of the canvas height) past the last row's line,
// which still keeps it off a lake's or a river's shore
const POND_FRONT_SPILL = 0.02;
// where the rows are squeezed tight a pond may lie as flat as this (in pixels), not to touch the next
const POND_FLAT_H = 3;
/* Where a pond's water lies, which its drawing, its hover and anything floating on it all go by.
 * It spans its own slots and no more: a young forest's zoom enlarges the trees, not the
 * water, or the ponds at the back swell up over the horizon. It never crosses the horizon
 * nor runs off the bottom of the ground. */
AF.pondBox = function (env, p) {
  const { u, H } = env, it = p.it, persp = p.s / env.layout.zoom;
  // a landscape that squeezes the rows onto its own ground narrows the slots too:
  // measure one slot where this pond stands, on the nearer side of any gap it squeezes out
  const land = AF.landOf(env), step = 1 / (env.layout.perRow + 0.5);
  const at_x = x => land.placeX ? land.placeX(Object.assign({}, it, { x }), env) : x;
  const squeeze = land.placeX ? Math.min(Math.abs(at_x(it.x + step) - at_x(it.x)), Math.abs(at_x(it.x) - at_x(it.x - step))) / step : 1;
  const colW = colWidth(env) * squeeze;
  const xs = env.placed.filter(q => q.it.pond && q.it.group === it.group).map(q => q.x);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const top = env.hor + H * ROWS_TOP, bot = H * (env.bot || GROUND_BOTTOM);
  // the gap to the row in front, or for the front row the one behind it
  const at = d => Math.pow(clamp(d, 0, 1), 1.1), g = it.rowGap;
  const rowStep = g ? (bot - top) * Math.max(at(it.depth + g) - at(it.depth), at(it.depth) - at(it.depth - g)) : (bot - top) * POND_LONE_ROW;
  const w = Math.max(POND_MIN_W * u * persp, it.slots * colW * POND_OVERHANG * persp);
  let h = Math.min(Math.max(POND_MIN_H, w * POND_ASPECT), Math.max(POND_FLAT_H, rowStep * POND_ROWS), bot - env.hor - POND_SKY_GAP);
  // hung from its row's own line rather than its slot's jittered one, so ponds a few rows
  // apart keep the rows between them clear
  const rowY = g ? top + (bot - top) * at(it.depth) : p.y;
  let y0 = Math.max(env.hor + POND_SKY_GAP, rowY - h * POND_BACK);
  // near the front a pond lies flatter rather than rising into the pond behind it; it only
  // moves up once it is as flat as a pond gets
  const floor = bot + H * POND_FRONT_SPILL;
  h = Math.max(POND_FLAT_H, Math.min(h, floor - y0));
  y0 = Math.min(y0, floor - h);
  return { cx, cy: y0 + h / 2, w, h, x0: cx - w / 2, x1: cx + w / 2, y0, y1: y0 + h };
};
AF.drawPond = function (g, env, p) {
  if (!p.it.first) return;
  const th = env.theme, { cx, cy, w, h } = AF.pondBox(env, p);
  const water = hex((th.frozen ? '#dfe8f0' : th.water) || DEFAULT_WATER);
  const hz = p.hz * (th.hzStep || 0.1) * 3, c0 = mix(water, hex(th.haze), hz), c1 = mix(c0, [255, 255, 255], 0.45), deep = mix(c0, [0, 0, 0], th.frozen ? 0.06 : 0.18), edge = mix(hex(th.g1), [0, 0, 0], 0.2);
  ellipseFill(g, cx, cy, w, h, (q, x, y) => q > 0.8 ? edge : y < cy - h * 0.2 ? deep : ((x * 3 + y * 7) % 11 === 0 ? c1 : c0));
  const R = rng(p.it.seed), reed = th.snow ? '#8a9a8a' : '#2f4a2a', tip = '#8a6a3a';
  for (let k = 0; k < POND_REEDS; k++) { const side = k % 2 ? 1 : -1, x = Math.round(cx + side * (w / 2 - 1 - R() * w * 0.15)), y = Math.round(cy + R() * h * 0.2), hh = 2 + (R() * 3 | 0);
    g.fillStyle = reed; g.fillRect(x, y - hh, 1, hh); g.fillStyle = tip; g.fillRect(x, y - hh - 1, 1, 1); }
  g.fillStyle = rgb(c1);
  if (th.frozen) pxLine(g, cx - w * 0.25, cy + h * 0.15, cx + w * 0.2, cy - h * 0.05);
  else g.fillRect(Math.round(cx - w * 0.2), Math.round(cy - h * 0.05), Math.max(2, Math.round(w * 0.18)), 1);
  if (env.afterItem) env.afterItem(g, p);
};
AF.findPuddles = function (env) {
  if (!env.theme.puddles || env.mood.landscape === 'lake') return [];
  const frontRow = Math.max(...env.placed.map(p => p.it.row || 0));
  const row = env.placed.filter(p => !p.it.pond && p.it.row === frontRow).sort((a, b) => a.x - b.x);
  const gaps = [];
  for (let i = 1; i < row.length; i++) gaps.push({ x: (row[i - 1].x + row[i].x) / 2, y: Math.round(Math.max(row[i - 1].y, row[i].y) + 2), w: Math.min(row[i].x - row[i - 1].x - 2, PUDDLE_MAX_W * env.u) });
  // none where there is water already: a landscape's (a river's channel is the widest gap) or a pond's
  const land = AF.landOf(env), ponds = env.placed.filter(p => p.it.pond && p.it.first).map(p => AF.pondBox(env, p));
  const dry = g => {
    const x0 = g.x - g.w / 2, x1 = g.x + g.w / 2, y1 = g.y + Math.max(2, Math.round(g.w * PUDDLE_ASPECT));
    return !(land.wet && land.wet(env, x0, x1, g.y)) && !ponds.some(b => x1 > b.x0 && x0 < b.x1 && y1 > b.y0 && g.y < b.y1);
  };
  return gaps.filter(g => g.w >= PUDDLE_MIN_W * env.u && dry(g)).sort((a, b) => b.w - a.w).slice(0, MAX_PUDDLES);
};
AF.drawPuddle = function (g, env, pd) {
  const c0 = hex(mixHex(env.theme.water || DEFAULT_WATER, env.theme.sky[env.theme.sky.length - 1], 0.4)), c1 = mix(c0, [255, 255, 255], 0.4), h = Math.max(2, Math.round(pd.w * PUDDLE_ASPECT));
  for (let y = 0; y < h; y++) for (let x = -pd.w / 2; x <= pd.w / 2; x++) {
    if ((x / (pd.w / 2)) ** 2 + ((y - h / 2 + 0.5) / (h / 2)) ** 2 > 1) continue;
    g.fillStyle = rgb(y === 0 && (x | 0) % 3 === 0 ? c1 : c0); g.fillRect(Math.round(pd.x + x), pd.y + y, 1, 1);
  }
};
})();

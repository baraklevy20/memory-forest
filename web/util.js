/* Memory Forest — shared helpers: random numbers, colours, pixels and layers, text for the page,
 * the bridge back to Anki, and the stages a tree goes through. Loaded first: it makes
 * window.AnkiForest, which every other script adds to. */
(function () {
'use strict';
// Every copy of the add-on on a page gets an object of its own: the files loaded after this
// one register themselves on it, and its boot script (forest.js) lets the name go again, so
// another copy - an older version installed beside this one, or the other edition - can
// never overwrite this copy's functions.
const AF = window.AnkiForest = { engines: {} };
const TAU = Math.PI * 2;

/* ---------- utilities ---------- */
function rng(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const toHex = c => '#' + c.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
const mixHex = (a, b, t) => toHex(mix(hex(a), hex(b), t));
const rgb = (c, a = 1) => typeof c === 'string' ? c : `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
/* one pixel (or a small block) of colour; `c` is an [r,g,b] triple or any CSS colour */
const px = (g, c, x, y, w = 1, h = 1) => { g.fillStyle = rgb(c); g.fillRect(Math.round(x), Math.round(y), w, h); };
function ellipseFill(g, cx, cy, w, h, colorAt) {
  for (let y = Math.floor(cy - h / 2); y <= cy + h / 2; y++) for (let x = Math.floor(cx - w / 2); x <= cx + w / 2; x++) {
    const q = ((x + 0.5 - cx) / (w / 2)) ** 2 + ((y + 0.5 - cy) / (h / 2)) ** 2;
    if (q <= 1) px(g, colorAt(q, x, y), x, y);
  }
}
function layer(W, H) { const c = document.createElement('canvas'); c.width = Math.max(1, W); c.height = Math.max(1, H); return [c, c.getContext('2d', { willReadFrequently: true })]; }
const B4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const MAX_LINE_PX = 4000;  // a runaway line gives up rather than hang the panel
/* A pixel line, filled once, its pixels gathered into runs: a row of them for a flat line, a
 * column for a steep one. Its pixels never repeat, so one shape draws exactly what a call a
 * pixel did (a grid of these was thousands of calls a frame) */
function pxLine(g, x0, y0, x1, y1) {
  x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy;
  const line = new Path2D(), flat = dx >= -dy;
  let rx = x0, ry = y0, n = 0;  // the run so far: n pixels from (rx, ry), along the line's long way
  const run = () => { if (flat) line.rect(sx > 0 ? rx : rx - n + 1, ry, n, 1); else line.rect(rx, sy > 0 ? ry : ry - n + 1, 1, n); };
  for (let i = 0; i < MAX_LINE_PX; i++) {
    if (flat ? y0 !== ry : x0 !== rx) { run(); rx = x0; ry = y0; n = 0; }
    n++;
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; }
  }
  run();
  g.fill(line);
}
function fmtDate(iso) { const d = new Date(iso + 'T12:00:00'); return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }); }  // (English, as all the words around it)
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
const cap = t => t.charAt(0).toUpperCase() + t.slice(1);
const canBrowse = () => typeof pycmd === 'function';  // Anki's bridge may not be a window property
const send = msg => { if (canBrowse()) pycmd(msg); };
// the colour behind a page: the first of `els` with a background you can see, as [r, g, b], or
// null (read as it is drawn, so any theme and any Anki version answers alike)
function pageBg(els) {
  for (const el of els) {
    const m = el && el.nodeType === 1 && window.getComputedStyle(el).backgroundColor.match(/[\d.]+/g);
    if (m && (m.length < 4 || +m[3] > 0.5)) return [+m[0], +m[1], +m[2]];
  }
  return null;
}
/* Where a pointer event on `el` is, in its own css pixels as the layout has them, [x, y]: from
 * the event's offset, which a turned element (the phone's sideways view) keeps in the element's
 * own frame, taken back out of any zoom an app puts on the page (AnkiDroid's card zoom), which
 * the offset and the screen show but the layout's sizes don't (a 90-degree turn swaps the box's
 * sides, which leaves its area alone) */
function pointIn(e, el) {
  const r = el.getBoundingClientRect(), w = el.clientWidth, h = el.clientHeight;
  const zoom = w && h ? Math.sqrt(r.width * r.height / (w * h)) || 1 : 1;
  return [e.offsetX / zoom, e.offsetY / zoom];
}
// the colour behind a transparent page, which AnkiDroid and AnkiMobile paint themselves: their
// night grey in night mode (the card's class: the app's theme, which the system's need not be),
// else white
const NIGHT_PAGE = [47, 47, 49], DAY_PAGE = [255, 255, 255];
const appBg = () => document.querySelector('.nightMode, .night_mode, .night-mode') ? NIGHT_PAGE : DAY_PAGE;
// "Animate the forest": on, off, or 'system' (still while the system asks for less motion)
const animates = data => data.animations === 'system'
  ? !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)
  : Boolean(data.animations);
/* Loop mode, for a recording that repeats seamlessly (Commit Forest): the clock wraps every
 * AF.LOOP seconds, and each motion is rounded to a whole number of cycles in that time, so the
 * last frame leads straight back into the first. Off (null) in the add-on, where these give
 * back what they are given. */
AF.LOOP = null;
// an angular speed (rad/s), as used in sin(t * w)
const cyc = w => AF.LOOP ? Math.round(w * AF.LOOP / TAU) * TAU / AF.LOOP : w;
// a period in seconds, as used in (t + phase) % p
const per = p => AF.LOOP ? AF.LOOP / Math.max(1, Math.round(AF.LOOP / p)) : p;
// a speed across a span that wraps, as used in (x + t * v) % span
const drift = (v, span) => AF.LOOP ? Math.round(v * AF.LOOP / span) * span / AF.LOOP : v;
// the same for something that must be seen to travel (a bird): at least one whole trip a loop
const trip = (v, span) => AF.LOOP ? Math.max(1, Math.round(v * AF.LOOP / span)) * span / AF.LOOP : v;
/* A procession too slow to finish a trip in a loop instead hands over: by the loop's end
 * item k has taken item k + 1's place, and looks like it. `handover(k, t)` is k's place in
 * the line at time t (k itself outside loop mode); `along(values, at)` reads a per-item
 * value at such a place, eased from one item's to the next one's. */
const handover = (k, t) => AF.LOOP ? k + (t % AF.LOOP) / AF.LOOP : k;
function along(values, at) {
  const n = values.length, i = Math.floor(at), f = at - i, a = values[((i % n) + n) % n], b = values[(((i + 1) % n) + n) % n];
  return a + (b - a) * f;
}
AF.u = { cyc, per, drift, trip, handover, along, rng, hashStr, hex, mix, toHex, mixHex, rgb, px, ellipseFill, layer, B4, clamp, pxLine, TAU, fmtDate, esc, cap, canBrowse, send, animates, pageBg, appBg, pointIn };
AF.STAGE_H = [4, 8, 13, 19, 27, 38];
AF.STAGE_NAMES = ['seedling', 'sapling', 'young', 'mature', 'old', 'ancient'];
AF.STAGE = { SEEDLING: 0, SAPLING: 1, YOUNG: 2, MATURE: 3, OLD: 4, ANCIENT: 5 };
})();

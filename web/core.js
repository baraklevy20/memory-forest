/* Memory Forest — shared helpers, layout, moods, the scene runner, tooltips and animals.
 * The pixel engine (web/engines/pixel.js) draws the sky, ground and trees; everything
 * else — weather rules, animals, ponds, hover and click — lives here. */
(function () {
'use strict';
const AF = window.AnkiForest = window.AnkiForest || { engines: {} };
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
function pxLine(g, x0, y0, x1, y1) {
  x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy;
  for (let i = 0; i < MAX_LINE_PX; i++) { g.fillRect(x0, y0, 1, 1); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; } }
}
AF.u = { rng, hashStr, hex, mix, toHex, mixHex, rgb, px, ellipseFill, layer, B4, clamp, pxLine, TAU };
AF.STAGE_H = [4, 8, 13, 19, 27, 38];
AF.STAGE_NAMES = ['seedling', 'sapling', 'young', 'mature', 'old', 'ancient'];
AF.STAGE = { SEEDLING: 0, SAPLING: 1, YOUNG: 2, MATURE: 3, OLD: 4, ANCIENT: 5 };
const { YOUNG, MATURE, OLD, ANCIENT } = AF.STAGE;
// where the horizon and the front of the forest sit, as fractions of the canvas height
const HORIZON = 0.42, GROUND_BOTTOM = 0.965;
// the rows start this far below the horizon (of the canvas height)
const ROWS_TOP = 0.045;
// the planting spans the canvas but for a sliver at each side
const SLOT_MARGIN = 0.02, SLOT_SPAN = 0.96;
/* the width of one planting slot, as AF.place spreads them */
const colWidth = env => SLOT_SPAN * env.W / (env.layout.perRow + 0.5);

/* ---------- layout constants ---------- */
// a pond takes one slot per this many days of the break, within these bounds
const POND_DAYS_PER_SLOT = 10, POND_SLOTS = [2, 4];
// ponds keep this many rows apart, so their water never meets
const POND_APART = 3;
const TREE_VARIANTS = 4;
// trees per row grow with the square root of the forest, within bounds; a very big
// forest gets wider rows so it does not recede forever
const ROW_SPREAD = 1.6, ROW_MIN = 10, ROW_MAX = 34, ROW_MAX_BIG = 52, BIG_FOREST_ITEMS = 500;
// how far a tree may stray from its slot, as a share of the slot and of the row gap
const X_JITTER = 0.7, Y_JITTER = 0.6;
// a lone first row scatters its trees from this depth to the front
const SINGLE_ROW_NEAREST = 0.3;
// a young forest is drawn larger: zoomed in until it has about 2^ZOOM_FULL_LOG trees
const ZOOM_FULL_LOG = 7, ZOOM_PER_LOG = 0.15, ZOOM_MAX = 1.8;
// the back row is drawn at FAR_SCALE of the front row's size, growing by NEAR_GAIN to the front
const FAR_SCALE = 0.82, NEAR_GAIN = 0.18;
// a faded tree on a deck screen sits this deep in the haze
const DIM_HAZE = 1.5;

/* the deep forest: one band per doubling beyond DEEP_TREES_PER_BAND trees, up to
 * DEEP_MAX_BANDS, rising from DEEP_BASE below the horizon; band k's crowns stand
 * AF.DEEP.crown + k * AF.DEEP.step high and it sits AF.DEEP.rise higher than the one in
 * front of it (all in env.u). The engine and the tree line both measure from these. */
const DEEP_TREES_PER_BAND = 60, DEEP_MAX_BANDS = 4, DEEP_BASE = 2;
AF.DEEP = { crown: 10, step: 8, rise: 1.5 };
/* how deep in the haze deep-forest band k stands (0 is the nearest), never quite gone */
AF.deepHaze = (th, k) => Math.min(0.92, (th.hzStep || 0.12) * (2.6 + k * 1.7));

/* ---------- layout: one slot per tree, oldest at the back ---------- */
AF.layout = function (trees) {
  const items = [];
  trees.forEach((t, i) => {
    if (t.gap) {
      const slots = clamp(Math.ceil(t.gap / POND_DAYS_PER_SLOT), POND_SLOTS[0], POND_SLOTS[1]);
      for (let k = 0; k < slots; k++) items.push({ pond: true, group: i, days: t.gap, slots, first: k === 0, seed: (t.seed ^ (k * 7919 + 17)) >>> 0 });
    }
    items.push(Object.assign({}, t, { index: i, variant: t.seed % TREE_VARIANTS }));
  });
  const n = items.length, perRow = clamp(Math.round(Math.sqrt(n) * ROW_SPREAD), ROW_MIN, n > BIG_FOREST_ITEMS ? ROW_MAX_BIG : ROW_MAX);
  // ponds never split across rows and keep the two cells in front clear, so they stay visible
  const reserved = new Set(), water = new Set(); let cell = 0;
  const free = c => { while (reserved.has(c)) c++; return c; };
  // no other pond within POND_APART rows either way, nor a column beyond either end: a
  // pond reaches over the rows beside it and the rows are staggered, so diagonal
  // neighbours would touch
  const crowded = (c, slots) => {
    const r = Math.floor(c / perRow), c0 = c % perRow;
    for (let dr = -POND_APART; dr <= POND_APART; dr++) for (let dc = -1; dc <= slots; dc++) {
      const cc = c0 + dc;
      if (cc >= 0 && cc < perRow && water.has((r + dr) * perRow + cc)) return true;
    }
    return false;
  };
  // a pond is drawn as one ellipse across its slots, so they have to be consecutive free
  // cells on one row, clear of other ponds
  const fits = (c, slots) => {
    for (let k = 0; k < slots; k++) if (reserved.has(c + k) || (c + k) % perRow < c % perRow) return false;
    return !crowded(c, slots);
  };
  const put = it => {
    it.cell = cell;
    // keep the two cells in front of a pond clear so it stays visible, and the one
    // behind it too: the break should read as a gap in the planting, not a full row
    if (it.pond) {
      water.add(cell);
      const r = Math.floor(cell / perRow), c = cell % perRow;
      reserved.add((r + 1) * perRow + c);
      reserved.add((r + 2) * perRow + c);
      if (it.first && c > 0) reserved.add(cell - 1);
    }
    cell++;
  };
  // A pond with no room where it falls waits, and the trees after it fill the planting
  // until there is room: it lands a few trees late rather than leaving holes behind it.
  const units = [], waiting = [];
  items.forEach(it => { if (it.pond && !it.first) units[units.length - 1].push(it); else units.push([it]); });
  const tryWaiting = () => {
    for (let k = 0; k < waiting.length; k++) {
      cell = free(cell);
      if (fits(cell, waiting[k].length)) { waiting.splice(k, 1)[0].forEach(put); k = -1; }
    }
  };
  for (const unit of units) {
    tryWaiting();
    cell = free(cell);
    if (!unit[0].pond) put(unit[0]);
    else if (fits(cell, unit.length)) unit.forEach(put);
    else waiting.push(unit);
  }
  // any still waiting go past the last tree, where there is always room
  for (const unit of waiting) { cell = free(cell); while (!fits(cell, unit.length)) cell = free(cell + 1); unit.forEach(put); }
  const rows = Math.max(1, Math.ceil(cell / perRow)), single = rows === 1;
  items.forEach((it, i) => {
    const row = Math.floor(it.cell / perRow), col = it.cell % perRow, r = rng(it.seed || i + 1);
    it.row = row; it.fromFront = rows - 1 - row;
    it.depth = rows === 1 ? 1 : row / (rows - 1);
    const c = single ? col + (perRow - n) / 2 : col;  // a lone first row is centred
    it.x = (c + 0.5 + (r() - 0.5) * X_JITTER + (row % 2 ? 0.5 : 0)) / (perRow + 0.5);
    it.jy = (r() - 0.5) * Y_JITTER;
    // how far a tree may drift from its row
    it.rowGap = rows > 1 ? 1 / (rows - 1) : 0;
    // a forest too young for a second row doesn't stand in a line: its trees are
    // scattered over the meadow, near and far
    if (single) it.depth = SINGLE_ROW_NEAREST + (1 - SINGLE_ROW_NEAREST) * r();
  });
  const zoom = clamp(1 + (ZOOM_FULL_LOG - Math.log2(Math.max(2, trees.length))) * ZOOM_PER_LOG, 1, ZOOM_MAX);
  return { items, perRow, rows, zoom };
};
/* The oldest trees, drawn as a few bands of canopy receding into the haze instead of
 * one sprite each: more bands the further back your forest goes. */
AF.deepForest = function (merged, env) {
  const u = env.u, n = merged.count;
  const bands = clamp(Math.round(Math.log2(Math.max(2, n / DEEP_TREES_PER_BAND))), 1, DEEP_MAX_BANDS);
  // It rises from the horizon, each band standing higher and hazier than the last, the way
  // distance reads in this view. The near trees cover its foot; its tops carry on above them.
  const base = Math.round(env.hor + DEEP_BASE * u), h = Math.round((AF.DEEP.crown + bands * AF.DEEP.step) * u);
  // the engine fills this in with what it actually drew, so hovering empty sky says nothing
  return { merged, bands, base, h, u, boxes: [] };
};

AF.place = function (it, W, H, env) {
  const hor = H * HORIZON, top = hor + H * ROWS_TOP, bot = H * (env.bot || GROUND_BOTTOM), z = env.layout.zoom;
  const land = AF.landOf(env);
  const x = land.placeX ? land.placeX(it) : it.x;  // a landscape may squeeze the rows onto its own ground
  // on a deck screen in "lit" mode, trees without that deck's cards recede into the haze
  // a tree drifts off its row, but never up onto the hills nor off the bottom
  return { x: (SLOT_MARGIN + SLOT_SPAN * x) * W, y: top + (bot - top) * clamp(Math.pow(it.depth, 1.1) + it.jy * it.rowGap, 0, 1), s: (FAR_SCALE + NEAR_GAIN * it.depth) * z, hz: it.dim ? DIM_HAZE : 1 - it.depth };
};

/* Where the top of the forest stands: the deep-forest bands and the back rows. A few
 * stragglers may poke higher; the line follows the bulk of the canopy. Environments hang
 * their big sky pieces (a sun, a gem, a bust) clear of it. */
AF.treeLine = function (env) {
  const u = env.u, tops = [];
  for (const p of env.placed || []) if (!p.it.pond) tops.push(p.y - AF.STAGE_H[p.it.stage] * u * p.s);
  tops.sort((a, b) => a - b);
  let line = tops.length ? tops[Math.floor(tops.length * 0.04)] : env.hor;
  const d = env.deep;
  if (d && !AF.landOf(env).noDeep) line = Math.min(line, d.base - (d.bands - 1) * AF.DEEP.rise * u - (AF.DEEP.crown + (d.bands - 1) * AF.DEEP.step) * u * 0.95);
  return Math.min(env.hor, line);
};

/* ---------- times of day ---------- */
AF.TIMES = {
  dawn: { sky: ['#b3bcd8', '#cbc3dc', '#e3c8d4', '#f1cfc2', '#f7dcc0', '#fae8cf'], orb: { kind: 'sun', x: 0.3, y: 0.3, r: 8, c: '#fff6dc', glow: '#fbe6c6', halo: 7 },
    far: '#b7b2cb', near: '#9ea8b8', g0: '#9ab28e', g1: '#628463', grass: '#86a47e', haze: '#eadfd3', hzStep: 0.13, water: '#c3c6dc',
    tint: '#c8a8b8', tintAmt: 0.12, rim: '#f6c9b8', shadow: 0.6, clouds: { n: 4, top: '#fff6ee', bot: '#e7d5da', a: 230 }, birdC: '#5e5a6e' },
  day: { sky: ['#6aa6d8', '#82b6df', '#9cc6e6', '#b5d4ea', '#cde0ea', '#e0ebe8'], orb: { kind: 'sun', x: 0.8, y: 0.13, r: 7, c: '#fffbe6', glow: '#fff3c4', halo: 5 },
    far: '#9ab0c4', near: '#7c9c96', g0: '#6f9a58', g1: '#446c3c', grass: '#86b068', haze: '#c6d8dc', hzStep: 0.12, water: '#8fbcd8',
    clouds: { n: 5, top: '#ffffff', bot: '#dfe8ef', a: 240 }, birdC: '#3d4a55' },
  golden_hour: { sky: ['#6f93c0', '#9aaec4', '#d4bca0', '#efc48c', '#f7d49a', '#fbe2b0'], orb: { kind: 'sun', x: 0.78, y: 0.15, r: 7, c: '#fff0c8', glow: '#ffd99a', halo: 5 },
    far: '#a898a6', near: '#8a8c84', g0: '#7f9c50', g1: '#4d6a36', grass: '#a0b460', haze: '#ead2ac', hzStep: 0.12, water: '#b0a890',
    tint: '#e0a060', tintAmt: 0.06, rim: '#ffac8a', shadow: 0.9, clouds: { n: 4, top: '#fff0d8', bot: '#e8c0a0', a: 235 }, birdC: '#4a3a30' },
  dusk: { sky: ['#1f2b47', '#34436a', '#5e5f86', '#9a7a93', '#d49a8a', '#eebf98'], orb: { kind: 'sun', x: 0.72, y: 0.35, r: 7, c: '#f8dca8', glow: '#f6d3a0', halo: 4 },
    far: '#6c6a8e', near: '#4b5670', g0: '#4a6448', g1: '#2a4230', grass: '#3f6446', haze: '#9a93ad', hzStep: 0.12, water: '#7d78a0',
    tint: '#5a3f5e', tintAmt: 0.22, rim: '#f2b57a', shadow: 1.0, clouds: { n: 5, top: '#f3cbb7', bot: '#c79fae', a: 235 }, birdC: '#3a3148' },
  night: { sky: ['#060a18', '#0b1430', '#131f45', '#1c2a58', '#263666', '#324476'], orb: { kind: 'moon', x: 0.22, y: 0.17, r: 7, c: '#eef1f8', glow: '#5b6d9c', halo: 5 },
    far: '#1d2848', near: '#162140', g0: '#1a2b2d', g1: '#101b1d', grass: '#22383a', haze: '#2a3560', hzStep: 0.1, tint: '#141d3c', tintAmt: 0.45, water: '#1d2a4a',
    clouds: { n: 3, top: '#2c3766', bot: '#222b54', a: 200 }, stars: 90, birdC: '#2a3148' },
  // the warm plum night that lantern nights use
  plum_night: { sky: ['#0a0922', '#181136', '#281744', '#3a1e4d', '#4f2853', '#673356'], orb: { kind: 'moon', x: 0.82, y: 0.14, r: 5, c: '#f3e6c8', glow: '#6e4a6a', halo: 3 },
    far: '#231836', near: '#1b132c', g0: '#1b2426', g1: '#10181a', grass: '#223030', haze: '#3a2a4a', hzStep: 0.1, tint: '#1d1530', tintAmt: 0.5, water: '#2a1f3e',
    clouds: { n: 3, top: '#3a2a55', bot: '#2a1f40', a: 200 }, stars: 60, birdC: '#2a1f3a', warmFlies: true }
};

/* ---------- environments ----------
 * Each environment lives in web/envs/<key>.js and registers itself here: its look, its
 * tweaks to the theme, its tree colours and its scenery, and `night: true` if it only
 * makes sense after dark. Delete that file and the environment is gone - nothing else in
 * the add-on mentions it by name. */
// kept if already there: a second copy of the add-on on the same page (the public
// edition beside this one) adds to these rather than wiping what the first registered
AF.ENVS = AF.ENVS || {};
AF.env = function (key, spec) { AF.ENVS[key] = spec; };
AF.envOf = env => AF.ENVS[env.mood.special] || {};

/* ---------- landscapes and landmarks ----------
 * The same bargain as environments: web/landscapes/<key>.js holds everything that makes a
 * lake a lake, web/landmarks/<key>.js everything that makes a peak a peak, and deleting
 * either file removes it from the add-on. A scene has one landscape and one landmark. */
AF.LANDSCAPES = AF.LANDSCAPES || {};
AF.landscape = function (key, spec) { AF.LANDSCAPES[key] = spec; };
AF.landOf = env => AF.LANDSCAPES[env.mood.landscape] || {};

AF.LANDMARKS = AF.LANDMARKS || {};
AF.landmark = function (key, spec) { AF.LANDMARKS[key] = spec; };
AF.markOf = env => AF.LANDMARKS[env.mood.landmark] || {};

/* ---------- mood → theme: weather, specials, events, and your numbers as ambience ---------- */
// your numbers as ambience: a firefly per streak day and a bird per REVIEWS_PER_BIRD of
// today's reviews, up to a limit; a lantern per ANCIENT_PER_LANTERN ancient trees
const MAX_FLIES = 60, REVIEWS_PER_BIRD = 40, MAX_BIRDS = 6, ANCIENT_PER_LANTERN = 12, MAX_LANTERNS = 3;
// how much weather there is to draw: drops, splashes, flakes and glints on the ground
const RAIN_DROPS = 260, STORM_DROPS = 320, SPLASHES = 46, SNOWFLAKES = 190, DEEP_SNOWFLAKES = 320;
const AFTER_RAIN_DROPS = 36, AFTER_RAIN_GLINTS = 40;
// a cloudy night keeps this share of its stars; an aurora night has at least AURORA_STARS
const CLOUDY_STARS = 0.3, AURORA_STARS = 110;
// the aurora hides a moon this close to new
const NEW_MOON_HIDDEN = 0.08;
AF.theme = function (mood, stats, events) {
  const sp = mood.special, night = mood.time === 'night';
  const spec = AF.ENVS[sp] || {};
  const look = (spec.look && spec.look(mood, night)) || AF.TIMES[mood.time] || AF.TIMES.day;
  const th = JSON.parse(JSON.stringify(look));
  if (spec.theme) spec.theme(th, mood, night);
  const w = mood.weather, ev = events || [];
  const mixAll = (keys, col, amt) => keys.forEach(k => { if (th[k]) th[k] = mixHex(th[k], col, amt); });
  const mixSky = (col, amt) => { th.sky = th.sky.map(c => mixHex(c, col, amt)); };
  const skyMid = () => th.sky[Math.floor(th.sky.length / 2)];
  const addTint = (col, amt) => { th.tint = th.tint ? mixHex(th.tint, col, 0.5) : col; th.tintAmt = Math.max(th.tintAmt || 0, amt); };
  if (th.orb) th.orb.phase = mood.moon;
  th.tint = th.tint || null; th.tintAmt = th.tintAmt || 0;
  th.flies = 0; th.birds = 0; th.stars = th.stars || 0;
  const calm = w === 'clear' || w === 'cloudy' || w === 'after_rain';
  const clearSky = w === 'clear' || w === 'after_rain';
  if (calm && (night || mood.time === 'dusk')) th.flies = clamp(stats.streak || 0, 0, MAX_FLIES);
  if (calm && !night) th.birds = clamp(Math.ceil((stats.today_reviews || 0) / REVIEWS_PER_BIRD), 0, MAX_BIRDS);
  if (!clearSky) th.stars = w === 'cloudy' ? Math.round(th.stars * CLOUDY_STARS) : 0;

  if (w === 'cloudy') {
    mixSky(night ? '#1a2030' : '#9aa3ad', 0.6);
    if (th.orb) { th.orb.halo = 0; th.orb.c = mixHex(th.orb.c, skyMid(), 0.6); }
    th.clouds = { n: 7, top: mixHex(th.clouds.top, '#c9ced4', 0.4), bot: mixHex(th.clouds.bot, '#8e98a2', 0.4), a: 245 };
    th.deck = { n: 3, top: night ? '#2a3040' : '#c3c9cf', bot: night ? '#1c2230' : '#9aa3ad', a: 250 };
    addTint('#8e9aa4', 0.12); th.flat = true; th.rim = null; th.shadow = 0;
  } else if (w === 'rain' || w === 'storm') {
    const grey = night ? '#10151c' : (w === 'storm' ? '#3c464e' : '#56626b');
    mixSky(grey, w === 'storm' ? 0.65 : 0.5);
    if (!night) th.sky = th.sky.map((c, i) => i >= th.sky.length - 2 ? mixHex(c, '#6e6a78', 0.5) : c);
    mixAll(['far', 'near'], grey, 0.4); mixAll(['g0', 'g1', 'grass'], '#33443a', 0.25);
    th.haze = mixHex(th.haze, grey, 0.5);
    addTint(w === 'storm' ? '#2a3440' : '#3a4a55', w === 'storm' ? 0.35 : 0.3);
    th.clouds = { n: 9, top: mixHex(grey, '#8a96a0', 0.35), bot: mixHex(grey, '#1a2026', 0.25), a: 250, y0: 0, dy: 0.18, speed: 1.4 };
    th.deck = { n: 3, top: mixHex(grey, '#6a7680', 0.3), bot: mixHex(grey, '#1a2026', 0.3), a: 250 };
    th.rain = w === 'storm' ? STORM_DROPS : RAIN_DROPS; th.splashes = SPLASHES; th.lightning = w === 'storm';
    if (w === 'storm') th.wind = true;
    th.orb = null; th.rim = null; th.shadow = 0;
  } else if (w === 'fog') {
    const fogC = night ? '#3a4458' : '#dcdcd8';
    mixSky(fogC, 0.55); mixAll(['far', 'near'], fogC, 0.5);
    th.haze = fogC; th.hzStep *= 1.25; th.fog = mixHex(fogC, '#ffffff', night ? 0.1 : 0.3);
    th.clouds = null; th.rim = null; th.shadow = 0;
    if (th.orb) { th.orb.halo = 0; th.orb.r *= 1.5; th.orb.c = mixHex(th.orb.c, th.fog, 0.5); th.orb.soft = true; }
  } else if (w === 'snow' || w === 'deep_winter') {
    const deep = w === 'deep_winter';
    mixSky(deep ? (night ? '#1e2432' : '#b7bcc4') : (night ? '#26314a' : '#c9d2df'), deep ? 0.65 : 0.45);
    th.g0 = night ? '#61789a' : '#e8eef6'; th.g1 = night ? '#34465e' : '#cbd6e4'; th.grass = night ? '#7890ac' : '#dfe7f1';
    mixAll(['far', 'near'], night ? '#3a4a66' : (deep ? '#d0d6de' : '#c4cedd'), deep ? 0.55 : 0.4);
    addTint(night ? '#141d3c' : '#9aa6b8', deep ? 0.2 : 0.12);
    th.snow = true; th.snowfall = deep ? DEEP_SNOWFLAKES : SNOWFLAKES;
    th.clouds = { n: deep ? 4 : 3, top: night ? '#3a4566' : '#eef2f7', bot: night ? '#2c3552' : '#d3dbe6', a: 230 };
    th.water = night ? '#40506c' : '#c9d6e6'; th.shadow = 0;
    if (th.orb && th.orb.kind === 'sun') { th.orb.halo = 0; th.orb.c = mixHex(th.orb.c, skyMid(), 0.6); }
    if (deep) { th.deepSnow = true; th.frozen = true; th.water = night ? '#5a6a86' : '#dfe8f0'; th.orb = null; th.stars = 0; th.rim = null;
      th.deck = { n: 3, top: night ? '#2a3040' : '#c8cdd4', bot: night ? '#1c2230' : '#a8aeb8', a: 250 }; }
  } else if (w === 'after_rain') {
    mixSky('#b8bcc8', 0.18);
    th.rainbow = !night; th.glints = AFTER_RAIN_GLINTS; th.rain = AFTER_RAIN_DROPS; th.rainLight = true; th.puddles = true;
    if (th.clouds) { th.clouds.y0 = 0; th.clouds.dy = 0.1; }
    mixAll(['g0', 'g1'], '#2f4a3a', 0.15);
  }
  if (mood.wind) th.wind = true;

  // the sky already holds a fixed field of them
  if (sp === 'lanterns') th.lanterns = clamp(Math.round((stats.ancient || 0) / ANCIENT_PER_LANTERN), 1, MAX_LANTERNS);
  if (sp === 'aurora' && w !== 'rain' && w !== 'storm') {
    th.aurora = true; if (clearSky) th.stars = Math.max(th.stars, AURORA_STARS);
    if (th.orb && th.orb.kind === 'moon') { if (mood.moon < NEW_MOON_HIDDEN || mood.moon > 1 - NEW_MOON_HIDDEN) th.orb = null; else th.orb.x = 0.86; }
  }
  if (night && clearSky) {
    th.shooting = true;
    if (ev.includes('meteor_shower')) th.meteors = true;
    if (ev.includes('new_ancient')) th.bigStar = true;
    if (ev.includes('harvest_moon') && th.orb) th.orb = { kind: 'moon', x: 0.7, y: 0.33, r: 11, c: '#f4c27a', glow: '#c98a4a', halo: 6, full: true };
  }
  // an environment's last word, once the weather and the sky are settled
  if (spec.after) spec.after(th, mood, night, stats);
  return th;
};

/* ---------- animals and the cabin ---------- */
const VISITORS = {
  rabbit: { pal: { b: '#b9a38a', d: '#7a6450', e: '#2a2018', l: '#f1ebe2' }, frames: [
    ['..d.d...', '..d.d...', '..b.b...', '.bbbb...', 'bebbbbb.', '.blllbbl', '..d..d..'],
    ['...d.d..', '..d.d...', '..b.b...', '.bbbb...', 'bebbbbb.', '.blllbbl', '..d..d..']] },
  deer: { pal: { b: '#9a653f', d: '#5a3a26', l: '#c9a07a', w: '#f4ede4' }, frames: [
    ['.......d.d.', '........d..', '.......bbb.', '.......bbbl', 'lbbbbbbbb..', '.bbbbbbbb..', '.d.d..d.d..', '.d.d..d.d..'],
    ['...........', '...........', '...........', '.......d.d.', 'wbbbbbbbd..', '.bbbbbbbbb.', '.d.d..d.bbl', '.d.d..d.d..']] },
  stag: { pal: { b: '#8a5a38', d: '#4e3220', l: '#c9a07a', w: '#f4ede4' }, frames: [
    ['......d...d', '......dd.dd', '.......ddd.', '.......bbb.', '.......bbbl', 'lbbbbbbbb..', '.bbbbbbbb..', '.d.d..d.d..', '.d.d..d.d..'],
    ['...........', '...........', '...........', '...........', '......d.d.d', 'wbbbbbbbdd.', '.bbbbbbbbb.', '.d.d..d.bbl', '.d.d..d.d..']] },
  fox: { pal: { o: '#d9772e', w: '#f3ece2', d: '#3a2418', e: '#1a1008' }, frames: [
    ['........o.o', '........ooo', '........oeow', 'ww.oooooooo', '.wooooooo..', '..d.d..d.d.'],
    ['........o.o', '........ooo', '........oeow', '.w.oooooooo', 'w.ooooooo..', '..d.d..d.d.']] },
  owl: { pal: { b: '#8a7458', d: '#3e3226', y: '#f1d45a', l: '#d8c8a8' }, frames: [
    ['d...d', 'bbbbb', 'bybyb', 'bbdbb', 'blllb', 'blllb', '.b.b.'],
    ['d...d', 'bbbbb', 'bdbdb', 'bbdbb', 'blllb', 'blllb', '.b.b.']] },
  heron: { pal: { g: '#9aa4ae', e: '#1a1a1a', d: '#e0a33a', w: '#e6eaee', k: '#4a4f55' }, frames: [
    ['..gg....', '.gegddd.', '..g.....', '..g.....', '.ggg....', 'gggww...', '.gggw...', '..ggg...', '...k....', '...k....', '..kk....'],
    ['..gg....', '.gggddd.', '..g.....', '..g.....', '.ggg....', 'gggww...', '.gggw...', '..ggg...', '...k....', '...k....', '..kk....']] },
  cabin: { pal: { c: '#6e6a70', r: '#7a3a2e', R: '#5a2a22', w: '#9a7250', W: '#7a5a3e', o: '#3e2a1c', n: '#2e3a4a' }, frames: [
    ['......cc....', '......cc....', '...rrrrrrr..', '..rrrrrrrrR.', '.rrrrrrrrrRR', 'RRRRRRRRRRRR', '.wWwWwWwWwW.', '.woowWwnnwW.', '.woowWwnnwW.', '.woowWwWwWw.']] }
};
const FRONT_SLOTS = [0.9, 0.22, 0.75, 0.38, 0.6];
// seconds: each animal at the front moves on every ROAM_EVERY (plus a little more per
// animal, and offset by ROAM_OFFSET each, so they never set off together) and takes
// WALK_SECS to get there, stepping WALK_FPS frames a second
const ROAM_EVERY = 150, ROAM_STAGGER = 41, ROAM_OFFSET = 37, WALK_SECS = 4, WALK_FPS = 4;
// how far either side of its spot an animal wanders, as a share of the width
const ROAM_REACH = 0.045;
// a resting animal shows its second frame (a glance, a nibble) while a slow wave is above this
const IDLE_GLANCE = 0.93;
// a rabbit covers its walk in RABBIT_HOPS hops, RABBIT_HOP_PX high
const RABBIT_HOPS = 5, RABBIT_HOP_PX = 3;
// the animals stand this far below the front row (of the height), never off the canvas
const VISITOR_DROP = 0.025, VISITOR_LOWEST = 0.995;
const CABIN_X = 0.05, CABIN_SMOKE_PUFFS = 4;
const FACES_LEFT = { rabbit: true };  // which way each sprite is drawn looking

function paintSprite(g, rows, x0, y0, pal, colorOf, flip = false) {
  rows.forEach((row, yy) => { for (let xx = 0; xx < row.length; xx++) { const ch = row[xx]; if (ch === '.') continue; g.fillStyle = colorOf(pal[ch] || '#000000', ch); g.fillRect(x0 + (flip ? row.length - 1 - xx : xx), y0 + yy, 1, 1); } });
}
/* A new arrangement every day, the same all day: the date mixed into the forest's seed. */
const daySeed = env => ((env.data.forestSeed || 3) ^ Math.imul((env.data.dayNumber || 0) + 1, 2654435761)) >>> 0;
function visitorColor(env, hz) {
  const th = env.theme, tint = th.tint ? hex(th.tint) : null, haze = hex(th.haze);
  return col => { if (env.visitorTint) return env.visitorTint; let c = hex(col); if (tint) c = mix(c, tint, th.tintAmt); if (hz) c = mix(c, haze, hz * th.hzStep * 4); return rgb(c); };
}

/* animals that live inside the forest are drawn into the land at the right depth */
AF.placeVisitors = function (env) {
  const list = env.data.visitors || [], keys = list.map(v => v.key), trees = env.placed.filter(p => !p.it.pond);
  const inForest = {}, front = [];
  const R = rng(daySeed(env)), any = pool => pool[Math.floor(R() * pool.length)];
  // the owl perches on one of the oldest trees, the heron wades at one of the ponds
  const old = trees.filter(p => p.it.stage === ANCIENT), older = old.length ? old : trees.filter(p => p.it.stage === OLD);
  if (keys.includes('owl') && older.length) inForest.owl = { host: any(older) };
  const ponds = env.placed.filter(p => p.it.pond && p.it.first);
  if (keys.includes('heron') && ponds.length) inForest.heron = { host: any(ponds) };
  const band = (lo, hi) => trees.filter(p => p.it.fromFront >= lo && p.it.fromFront <= hi);
  for (const [key, lo, hi] of [['deer', 2, 4], ['stag', 4, 6]]) {
    if (!keys.includes(key)) continue;
    // never on a tree another animal already took
    const taken = new Set(Object.values(inForest).map(s => s.host));
    const free = list => list.filter(p => !taken.has(p));
    const pool = free(band(lo, hi)).length ? free(band(lo, hi)) : free(band(0, 2));
    if (pool.length) inForest[key] = { host: any(pool), graze: true };
  }
  for (const v of list) if (!inForest[v.key] && v.key !== 'cabin') front.push(v);
  env.inForest = inForest; env.frontVisitors = front; env.staticBoxes = [];
  const byHost = new Map();
  for (const [key, spot] of Object.entries(inForest)) byHost.set(spot.host, (byHost.get(spot.host) || []).concat([key]));
  env.afterItem = (lg, p) => {
    const keysHere = byHost.get(p); if (!keysHere) return;
    for (const key of keysHere) {
      const spr = VISITORS[key], v = list.find(x => x.key === key), frame = spr.frames[inForest[key].graze ? 1 : 0];
      let x0, y0;
      if (key === 'owl') { const h = AF.STAGE_H[p.it.stage] * env.u * p.s; x0 = Math.round(p.x - 2); y0 = Math.round(p.y - h - frame.length + 3); }
      else if (key === 'heron') { const b = AF.pondBox(env, p); x0 = Math.round(b.cx + b.w * 0.2); y0 = Math.round(b.cy - frame.length + 1); }
      else { x0 = Math.round(p.x + 4); y0 = Math.round(p.y - frame.length + 1); }
      paintSprite(lg, frame, x0, y0, spr.pal, visitorColor(env, p.hz));
      if (key === 'owl' && env.mood.time === 'night') { lg.fillStyle = '#f7e27a'; lg.fillRect(x0 + 1, y0 + 2, 1, 1); lg.fillRect(x0 + 3, y0 + 2, 1, 1); }
      env.staticBoxes.push({ v, x0, y0, x1: x0 + frame[0].length, y1: y0 + frame.length });
    }
  };
};

/* the rest stand at the edge of the forest; the cabin sits front-left after a year */
AF.drawVisitors = function (g, env, t) {
  const list = env.frontVisitors || [], color = visitorColor(env, 0);
  env.visitorBoxes = (env.staticBoxes || []).slice();
  const baseY = Math.round(env.visitorY || env.H * Math.min(VISITOR_LOWEST, (env.bot || GROUND_BOTTOM) + VISITOR_DROP));
  const cabin = (env.data.visitors || []).find(v => v.key === 'cabin');
  if (cabin) {
    const spr = VISITORS.cabin, frame = spr.frames[0], x0 = Math.round(env.W * CABIN_X), y0 = baseY - frame.length, lit = env.mood.time === 'night' || env.mood.time === 'dusk';
    paintSprite(g, frame, x0, y0, spr.pal, (col, ch) => ch === 'n' && lit ? '#ffd27a' : color(col));
    if (lit) { g.fillStyle = 'rgba(255,210,122,.18)'; g.fillRect(x0 + 6, y0 + 6, 4, 4); }
    else if (!env.theme.rain) for (let k = 0; k < CABIN_SMOKE_PUFFS; k++) { const q = (t * 0.25 + k / CABIN_SMOKE_PUFFS) % 1, sx = x0 + 6 + Math.round(Math.sin(q * 6 + k) * 1.5 + q * 4), sy = y0 - Math.round(q * 12); g.fillStyle = `rgba(220,220,225,${0.55 * (1 - q)})`; g.fillRect(sx, sy, q > 0.5 ? 2 : 1, 1); }
    env.visitorBoxes.push({ v: cabin, x0, y0, x1: x0 + frame[0].length, y1: baseY });
  }
  // Each animal has its own stretch of the front, shuffled daily. Every few minutes it
  // wanders to a new spot in that stretch, then stays there a while.
  const slots = FRONT_SLOTS.slice(), SR = rng(daySeed(env) ^ 0x51ed);
  for (let i = slots.length - 1; i > 0; i--) { const j = Math.floor(SR() * (i + 1)); [slots[i], slots[j]] = [slots[j], slots[i]]; }
  list.forEach((v, i) => {
    const spr = VISITORS[v.key]; if (!spr || i >= slots.length) return;
    const W = env.W, roam = W * ROAM_REACH, period = ROAM_EVERY + i * ROAM_STAGGER, walk = WALK_SECS, k = Math.floor((t + i * ROAM_OFFSET) / period), ph = (t + i * ROAM_OFFSET) - k * period;
    const spot = n => W * slots[i] + (rng((daySeed(env) + n * 7919 + i * 104729) >>> 0)() - 0.5) * 2 * roam;
    const from = spot(k - 1), to = spot(k), moving = !env.still && ph < walk, q = moving ? ph / walk : 1;
    const x = from + (to - from) * q, dir = to >= from ? 1 : -1;
    let frame = spr.frames[moving ? Math.floor(ph * WALK_FPS) % spr.frames.length : (Math.sin(t * 0.7 + i * 2.1) > IDLE_GLANCE ? 1 : 0)], dy = 0;
    // a rabbit hops rather than walks
    if (v.key === 'rabbit') { frame = spr.frames[0]; if (moving) dy = -Math.round(Math.abs(Math.sin(q * Math.PI * RABBIT_HOPS)) * RABBIT_HOP_PX); }
    const flip = FACES_LEFT[v.key] ? dir > 0 : dir < 0;  // face the way it last went
    const x0 = Math.round(x - frame[0].length / 2), y0 = baseY - frame.length + dy;
    paintSprite(g, frame, x0, y0, spr.pal, color, flip);
    env.visitorBoxes.push({ v, x0, y0, x1: x0 + frame[0].length, y1: baseY });
  });
};

/* ---------- ponds (long breaks) and puddles (after rain) ---------- */
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
  const at_x = x => land.placeX ? land.placeX(Object.assign({}, it, { x })) : x;
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
  return gaps.filter(g => g.w >= PUDDLE_MIN_W * env.u).sort((a, b) => b.w - a.w).slice(0, MAX_PUDDLES);
};
AF.drawPuddle = function (g, env, pd) {
  const c0 = hex(mixHex(env.theme.water || DEFAULT_WATER, env.theme.sky[env.theme.sky.length - 1], 0.4)), c1 = mix(c0, [255, 255, 255], 0.4), h = Math.max(2, Math.round(pd.w * PUDDLE_ASPECT));
  for (let y = 0; y < h; y++) for (let x = -pd.w / 2; x <= pd.w / 2; x++) {
    if ((x / (pd.w / 2)) ** 2 + ((y - h / 2 + 0.5) / (h / 2)) ** 2 > 1) continue;
    g.fillStyle = rgb(y === 0 && (x | 0) % 3 === 0 ? c1 : c0); g.fillRect(Math.round(pd.x + x), pd.y + y, 1, 1);
  }
};

/* ---------- tooltips ---------- */
function fmtDate(iso) { const d = new Date(iso + 'T12:00:00'); return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
// memory strength reads in days, then in months from MONTHS_FROM days, then in years
const DAYS_PER_YEAR = 365, DAYS_PER_MONTH = 30, MONTHS_FROM = 60;
AF.fmtStrength = d => d >= DAYS_PER_YEAR ? `${(d / DAYS_PER_YEAR).toFixed(1)} years` : d >= MONTHS_FROM ? `${Math.round(d / DAYS_PER_MONTH)} months` : `${Math.round(d)} days`;
function tipHtml(t, words) {
  const when = t.ago === 0 ? 'today' : t.ago === 1 ? 'yesterday' : `${t.ago} days ago`;
  const lines = [`<b>${esc(fmtDate(t.date))}</b> · ${esc(words.planted)} ${when}`, `${t.n} card${t.n === 1 ? '' : 's'} · ${esc(words.stages[t.stage])}`];
  if (t.suspended && t.suspended >= t.n) {
    // every card retired: the tree stands as it was, with nothing left to measure
    lines.push(t.n === 1 ? 'Its card is suspended' : `All ${t.n} cards suspended`);
  } else if (t.stage >= YOUNG) {
    // "measured" is false when there is no forgetting curve behind the number, only a
    // count of what has gone wrong lately - so the tooltip must not claim more than that
    const parts = t.measured === false
      ? [`${Math.round(t.remembered * 100)}% still going well`]
      : [`~${Math.round(t.remembered * 100)}% remembered`];
    if (t.strength) parts.push(`lasts ~${AF.fmtStrength(t.strength)}`);
    lines.push(parts.join(' · '));
    if (t.struggling && t.stage >= MATURE) lines.push(`${t.struggling} of ${t.n} relearning or lapsed this week`);
    if (t.suspended) lines.push(`${t.suspended} of ${t.n} suspended`);
  }
  if (canBrowse()) lines.push(CLICK_HINT);
  return lines.join('<br>');
}
const CLICK_HINT = '<span class="af-hint">Click to see these cards</span>';
function pondHtml(p) { return `<b>A quiet pond</b><br>${p.days} days without reviews`; }
function deepHtml(m, words) {
  const lines = [`<b>${esc(cap(words.deep))}</b>`,
    `${m.count.toLocaleString()} older ${esc(words.many)} · ${m.cards.toLocaleString()} cards`,
    `${esc(fmtDate(m.from_date))} – ${esc(fmtDate(m.to_date))}`];
  if (m.ancient) lines.push(`${m.ancient.toLocaleString()} of them ancient`);
  if (canBrowse()) lines.push(CLICK_HINT);
  return lines.join('<br>');
}
function visitorHtml(v) { const who = v.label.charAt(0).toUpperCase() + v.label.slice(1); return `<b>${esc(who)}</b><br>${v.key === 'cabin' ? 'Built' : 'Moved in'} when ${esc(v.why)}.`; }
/* What one day is called, in the tooltips and the caption */
AF.WORDS = { one: 'tree', many: 'trees', planted: 'planted', deep: 'the deep forest', stages: AF.STAGE_NAMES };
const cap = t => t.charAt(0).toUpperCase() + t.slice(1);
const canBrowse = () => typeof pycmd === 'function';  // Anki's bridge may not be a window property
const send = msg => { if (canBrowse()) pycmd(msg); };

/* ---------- the scene runner ---------- */
AF.mount = function (root, data, opts) {
  // a night-only environment (`night: true`) keeps to the night while the hour is the real one
  if (data.mood.clock && (AF.ENVS[data.mood.special] || {}).night) data = Object.assign({}, data, { mood: Object.assign({}, data.mood, { time: 'night' }) });
  const engine = AF.engines.pixel, words = AF.WORDS;
  // a later mount on the same root (a settings change, swapped in place) retires this one
  const token = {};
  root.afToken = token;
  const current = () => root.afToken === token;
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animate = data.animations && !reduce;
  root.innerHTML = (data.inAnki ? '<div class="af-top"><button type="button" class="af-cog" title="Memory Forest settings" aria-label="Memory Forest settings">' + COG + '</button></div>' : '')
    + '<div class="af-scene"><canvas class="af-canvas" aria-label="Your study forest"></canvas><div class="af-tip" hidden></div></div>'
    + '<div class="af-caption"><span class="af-journal"></span><span class="af-meta"></span></div>';
  const cog = root.querySelector('.af-cog');
  if (cog) cog.addEventListener('click', () => send(`${data.channel}:settings`));
  const sceneEl = root.querySelector('.af-scene'), canvas = root.querySelector('canvas'), tip = root.querySelector('.af-tip');
  root.style.maxWidth = data.maxWidth + 'px';
  caption(root, data);
  captionTips(root);

  const layout = AF.layout(data.trees);
  // with animations off the forest is one still moment: every redraw uses this time
  const stillAt = performance.now();
  let env = null, hover = null, deepHover = null, visible = true, running = false;

  function build() {
    const cssW = Math.max(MIN_CSS_W, Math.min(sceneEl.clientWidth || data.maxWidth, data.maxWidth));
    const k = Math.max(MIN_PIXEL_SCALE, Math.floor(cssW / CSS_W_PER_SCALE)), W = Math.floor(cssW / k), H = Math.floor(W / ASPECT);
    canvas.style.width = W * k + 'px'; canvas.style.height = H * k + 'px';
    canvas.width = W; canvas.height = H;
    env = { W, H, u: W / BASE_W, hor: Math.round(H * HORIZON), mood: data.mood, data, layout, engine, bot: GROUND_BOTTOM };
    env.theme = AF.theme(data.mood, data.stats, data.events);
    env.still = !animate;  // one calm moment: nothing brief (a flash, a hop, a blink) is caught in it
    engine.prepare(env);
    env.deep = data.merged ? AF.deepForest(data.merged, env) : null;
    env.placed = layout.items.map(it => Object.assign({ it }, AF.place(it, W, H, env))).sort((a, b) => a.y - b.y);
    env.puddles = AF.findPuddles(env);
    AF.placeVisitors(env);
    env.sky = engine.sky(env);
    const [land, lg] = layer(W, H); env.land = land; env.lg = lg;
    engine.steps(env).forEach(s => s(lg));
    engine.post(env);
    env.fx = AF.fx.init(env);
    env.g = canvas.getContext('2d', env.quantize ? { willReadFrequently: true } : {});
    // anniversary trees, resolved once instead of scanned for on every frame
    env.glowing = (data.anniversaries || []).map(idx => env.placed.find(q => !q.it.pond && q.it.index === idx)).filter(Boolean);
  }

  function frame(ts) {
    if (!env) return;
    const g = env.g, t = ts / 1000;
    env.t = t;  // the moment being drawn, for an engine that hit-tests moving things
    g.clearRect(0, 0, env.W, env.H);
    g.drawImage(env.sky, 0, 0);
    if (env.fx) AF.fx.back(g, env, t);
    if (engine.frameBack) engine.frameBack(g, env, t);
    g.drawImage(env.fx && env.fx.flash && env.landLit ? env.landLit : env.land, 0, 0);
    engine.frame(g, env, t);
    AF.drawVisitors(g, env, t);
    drawGlow(g, t);
    if (env.fx) AF.fx.front(g, env, t);
    if (env.quantize) env.quantize(g, env.W, env.H);
    drawMarker(g);
  }

  /* an anniversary tree glows: two faint pixel discs of warm light and a few gold
   * sparkles twinkling round its crown */
  const GLOW_DISCS = [0.85, 0.55], GLOW_SPARKLES = 6;  // disc radii as shares of the tree's height
  function drawGlow(g, t) {
    env.glowing.forEach(p => {
      const h = AF.STAGE_H[p.it.stage] * env.u * p.s, cx = Math.round(p.x), cy = Math.round(p.y - h * 0.55);
      g.save(); g.globalCompositeOperation = 'lighter';
      g.fillStyle = `rgba(255,226,150,${0.06 + 0.03 * Math.sin(t * 1.4)})`;
      for (const k of GLOW_DISCS) {
        const r = Math.max(2, Math.round(h * k));
        for (let dy = -r; dy <= r; dy++) { const w = Math.round(Math.sqrt(r * r - dy * dy)); g.fillRect(cx - w, cy + dy, w * 2, 1); }
      }
      g.restore();
      for (let i = 0; i < GLOW_SPARKLES; i++) {
        const a = i / GLOW_SPARKLES * Math.PI * 2 + t * 0.3, on = Math.sin(t * 2.2 + i * 1.7) > 0.2;
        if (!on) continue;
        g.fillStyle = '#ffe6a0';
        g.fillRect(Math.round(cx + Math.cos(a) * h * 0.6), Math.round(cy + Math.sin(a) * h * 0.5), 1, 1);
      }
    });
  }
  function drawMarker(g) {
    if (!hover) return;
    const x = Math.round(hover.x), y = Math.round(hover.top - 3);
    g.fillStyle = 'rgba(20,20,20,.7)'; g.fillRect(x - 3, y - 1, 7, 1);
    g.fillStyle = '#fff8e0';
    for (let r = 0; r < 3; r++) g.fillRect(x - (2 - r), y + r, 5 - 2 * r, 1);
  }

  function boxOf(p) {
    const h = AF.STAGE_H[p.it.stage] * env.u * p.s, w = Math.max(h * 0.8, 4 * env.u);
    return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - h, y1: p.y + env.u };
  }
  function pick(mx, my) {
    for (const b of env.visitorBoxes || []) if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { visitor: b.v };
    for (let i = env.placed.length - 1; i >= 0; i--) {
      const p = env.placed[i];
      if (p.it.pond) {
        if (!p.it.first) continue;
        const b = AF.pondBox(env, p);
        if (((mx - b.cx) / (b.w / 2)) ** 2 + ((my - b.cy) / (b.h / 2)) ** 2 <= 1) return { p, pond: true };
        continue;
      }
      const b = boxOf(p);
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { p, b };
    }
    return deepPick(mx, my);
  }
  function deepPick(mx, my) {  // the distant canopy, wherever the engine actually drew it
    for (const b of (env.deep && env.deep.boxes) || []) {
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { deep: env.deep.merged, b };
    }
    return null;
  }
  if (data.tooltips) {
    canvas.addEventListener('mousemove', e => {
      if (!env) return;
      const r = canvas.getBoundingClientRect();
      const scale = env.W / (r.width || env.W), mx = (e.clientX - r.left) * scale, my = (e.clientY - r.top) * scale;
      const hit = pick(mx, my);
      deepHover = null;
      if (!hit) { hover = null; tip.hidden = true; canvas.style.cursor = ''; return; }
      if (hit.visitor) { hover = null; tip.innerHTML = visitorHtml(hit.visitor); canvas.style.cursor = ''; }
      else if (hit.deep) {
        hover = null;
        tip.innerHTML = deepHtml(hit.deep, words);
        canvas.style.cursor = data.inAnki && !data.testForest ? 'pointer' : '';
        deepHover = hit.deep;
      }
      else {
        hover = { x: hit.p.x, top: hit.b ? hit.b.y0 : hit.p.y - 4 * env.u, tree: hit.pond ? null : hit.p.it };
        tip.innerHTML = hit.pond ? pondHtml(hit.p.it) : tipHtml(hit.p.it, words);
        canvas.style.cursor = !hit.pond && data.inAnki && !data.testForest ? 'pointer' : '';
      }
      tip.hidden = false;
      const sr = sceneEl.getBoundingClientRect();
      let left = e.clientX - sr.left + TIP_OFFSET, top = e.clientY - sr.top + TIP_OFFSET;
      if (left + tip.offsetWidth > sr.width - TIP_MARGIN) left = e.clientX - sr.left - tip.offsetWidth - TIP_OFFSET;
      if (top + tip.offsetHeight > sr.height - TIP_MARGIN) top = e.clientY - sr.top - tip.offsetHeight - TIP_OFFSET;
      tip.style.left = Math.max(TIP_MARGIN, left) + 'px'; tip.style.top = Math.max(TIP_MARGIN, top) + 'px';
      if (!animate) frame(stillAt);  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { hover = null; deepHover = null; tip.hidden = true; canvas.style.cursor = ''; if (!animate) frame(stillAt); });
    canvas.addEventListener('click', () => {
      if (data.testForest) return;
      if (deepHover) send(`${data.channel}:browse:${deepHover.from_ago}:${deckFor(data)}:${deepHover.to_ago}`);
      else if (hover && hover.tree) send(`${data.channel}:browse:` + hover.tree.ago + ':' + (data.deckId && !hover.tree.dim ? data.deckId : ''));
    });
  }

  // ~15 frames a second is plenty for drifting clouds and fireflies; pauses when hidden
  function loop() {
    let last = 0;
    const tick = ts => {
      if (!current()) return;  // swapped out: let this forest's loop end
      if (visible && !document.hidden && ts - last > FRAME_MS) { last = ts; frame(ts); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  function start() {
    build();
    frame(animate ? performance.now() : stillAt);
    if (animate && !running) { running = true; loop(); }
  }
  if ('IntersectionObserver' in window) new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(sceneEl);
  let lastW = 0, rt;
  if ('ResizeObserver' in window) new ResizeObserver((_es, obs) => {
    if (!current()) { obs.disconnect(); return; }
    const w = sceneEl.clientWidth; if (!env || Math.abs(w - lastW) < RESIZE_MIN_PX) return; lastW = w;
    clearTimeout(rt); rt = setTimeout(() => { if (AF.clearCaches) AF.clearCaches(); build(); frame(animate ? performance.now() : stillAt); }, RESIZE_DEBOUNCE_MS);
  }).observe(sceneEl);
  // build after the deck list has painted, so the forest never delays it - unless this is a
  // swap, where the old forest was just cleared and waiting would show an empty panel
  if (opts && opts.now) { lastW = sceneEl.clientWidth; start(); return; }
  const idle = window.requestIdleCallback || (cb => setTimeout(cb, IDLE_FALLBACK_MS));
  requestAnimationFrame(() => idle(() => { lastW = sceneEl.clientWidth; start(); }, { timeout: IDLE_TIMEOUT_MS }));
};

/* Redraw a forest already on the page with new data, without reloading the page: load any
 * scripts the new scene needs that the page does not have yet, then mount over the old
 * one. False when that forest is not on this page, so the add-on reloads it instead. */
AF.swap = function (id, data, srcs) {
  const root = document.getElementById(id);
  if (!root) return false;
  const have = new Set([...document.scripts].map(s => s.src));
  const missing = srcs.filter(s => !have.has(new window.URL(s, window.location.href).href));
  const next = i => {
    if (i < missing.length) {
      const el = document.createElement('script');
      el.src = missing[i];
      el.onload = el.onerror = () => next(i + 1);
      document.head.appendChild(el);
      return;
    }
    if (AF.clearCaches) AF.clearCaches();  // sprites were drawn for the old scene
    AF.mount(root, data, { now: true });
  };
  next(0);
  return true;
};

const FRAME_MS = 66;  // ~15 frames a second
// the canvas is drawn at a few hundred pixels across and scaled up by a whole number:
// one step per CSS_W_PER_SCALE CSS pixels, at least MIN_PIXEL_SCALE; env.u is one
// BASE_W-th of its width, so everything is sized the same at any scale
const MIN_CSS_W = 240, CSS_W_PER_SCALE = 300, MIN_PIXEL_SCALE = 2, BASE_W = 320, ASPECT = 2;
// the tooltip sits this far from the pointer, and this far inside the scene's edges
const TIP_OFFSET = 14, TIP_MARGIN = 6;
// a resize rebuilds the scene once the width has moved this much and settled this long
const RESIZE_MIN_PX = 8, RESIZE_DEBOUNCE_MS = 200;
// the first build waits for an idle moment, however busy, no longer than IDLE_TIMEOUT_MS
const IDLE_FALLBACK_MS = 30, IDLE_TIMEOUT_MS = 300;
const COG = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6a.5.5 0 0 0 .1-.6l-2-3.5a.5.5 0 0 0-.6-.2l-2.5 1a7.3 7.3 0 0 0-1.7-1l-.4-2.6a.5.5 0 0 0-.5-.4h-4a.5.5 0 0 0-.5.4l-.4 2.6c-.6.3-1.2.6-1.7 1l-2.5-1a.5.5 0 0 0-.6.2l-2 3.5a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6a.5.5 0 0 0-.1.6l2 3.5c.1.2.4.3.6.2l2.5-1c.5.4 1.1.7 1.7 1l.4 2.6c0 .2.3.4.5.4h4c.2 0 .5-.2.5-.4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1c.2.1.5 0 .6-.2l2-3.5a.5.5 0 0 0-.1-.6L19.4 13zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>';
const WEATHER_NAMES = { clear: 'clear sky', cloudy: 'cloudy', fog: 'fog', rain: 'rain', storm: 'thunderstorm', snow: 'snow', deep_winter: 'deep winter', after_rain: 'after the rain' };

/* the merged band spans every deck, so on a deck screen showing the whole forest it is
 * browsed without a deck filter; a deck's own forest keeps it */
const deckFor = data => (data.deckId && !data.highlight ? data.deckId : '');

function caption(root, data) {
  const s = data.stats, m = data.mood, words = AF.WORDS;
  root.querySelector('.af-journal').textContent = data.journal || '';
  const items = [];
  if (data.testForest) items.push(['Test forest', `Made-up ${words.many} from the Test forest setting. Turn it off in the forest settings to see your real one.`]);
  if (data.highlight) items.push([`${(data.deckName || '').split('::').pop()}: ${data.litCount} of ${s.trees} ${words.many}`, `${cap(words.many)} holding cards from this deck stay in colour; the rest fade back. Change this with Deck screens in the forest settings.`]);
  if (s.trees) items.push([`${s.trees.toLocaleString()} ${s.trees === 1 ? words.one : words.many}`, `One ${words.one} for each day you learned new cards. Hover over one to see its day, click it to see its cards.`]);
  if (data.merged) items.push([`${data.merged.count.toLocaleString()} in ${words.deep}`,
    `Your ${words.many} from ${fmtDate(data.merged.from_date)} to ${fmtDate(data.merged.to_date)} stand together in the distance, holding ${data.merged.cards.toLocaleString()} cards. Drawing every one of them individually would slow the deck list down.`
    + (canBrowse() && !data.testForest ? ' Click to see their cards.' : ''),
    data.testForest ? '' : `${data.channel}:browse:${data.merged.from_ago}:${deckFor(data)}:${data.merged.to_ago}`]);
  if (s.ancient) items.push([`${s.ancient} ancient`, `${cap(words.many)} whose cards you will likely remember for more than a year: their median memory strength is at least 365 days. That is FSRS stability where you have it, and the scheduling interval where you do not.`]);
  if (s.streak) items.push([`${s.streak}-day streak`, 'Days in a row with at least one review.']);
  // the scene's name, unless it is the plain default
  if (data.sceneName) items.push([data.sceneName, data.sceneTip || 'The preset, chosen in the forest settings.']);
  if (data.weatherError) {
    const lost = data.weatherError.startsWith('city not found');
    items.push([lost ? 'City not found' : 'Live weather unavailable', lost
      ? "Open-Meteo does not know that city, so the preset keeps its own weather. Check the spelling, or try its English name, in the forest settings."
      : `The live weather could not be fetched (${data.weatherError}), so the preset keeps its own weather for now.`]);
  }
  // the weather only when it is live; otherwise it is simply part of the preset
  if (m.source === 'real') {
    items.push([`Weather: ${WEATHER_NAMES[m.weather] || m.weather}${m.city ? ` in ${m.city}` : ''}${m.temp != null ? `, ${Math.round(m.temp)}°` : ''}`,
      'Live weather from Open-Meteo.']);
  }
  root.querySelector('.af-meta').innerHTML = items.map(([t, tip, cmd]) =>
    `<span class="af-info${cmd && canBrowse() ? ' af-click' : ''}" data-tip="${esc(tip)}"${cmd ? ` data-cmd="${esc(cmd)}"` : ''}>${esc(t)}</span>`).join(' · ')
    + (data.credit ? ' <span class="af-credit">· weather by Open-Meteo</span>' : '');
}
/* caption hints use the forest's own tooltip (Anki's webview doesn't show title tooltips) */
function captionTips(root) {
  const capTip = document.createElement('div'); capTip.className = 'af-tip af-cap-tip'; capTip.hidden = true; root.append(capTip);
  root.querySelectorAll('.af-info').forEach(el => {
    el.addEventListener('mouseenter', () => {
      capTip.textContent = el.dataset.tip; capTip.hidden = false;
      const pr = root.getBoundingClientRect(), r = el.getBoundingClientRect();
      const left = Math.min(Math.max(0, r.left - pr.left + r.width / 2 - capTip.offsetWidth / 2), pr.width - capTip.offsetWidth);
      capTip.style.left = left + 'px'; capTip.style.top = (r.top - pr.top - capTip.offsetHeight - TIP_MARGIN) + 'px';
    });
    el.addEventListener('mouseleave', () => { capTip.hidden = true; });
    if (el.dataset.cmd && canBrowse()) el.addEventListener('click', () => send(el.dataset.cmd));
  });
}
})();

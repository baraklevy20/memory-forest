/* Memory Forest — layout: where every tree, pond and the deep forest stand, and where the top
 * of the forest reaches. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, clamp } = AF.u;

// where the horizon and the front of the forest sit, as fractions of the canvas height
const HORIZON = 0.42, GROUND_BOTTOM = 0.965;
// the rows start this far below the horizon (of the canvas height)
const ROWS_TOP = 0.045;
// the planting spans the canvas but for a sliver at each side
const SLOT_MARGIN = 0.02, SLOT_SPAN = 0.96;
/* the width of one planting slot, as AF.place spreads them */
const colWidth = env => SLOT_SPAN * env.W / (env.layout.perRow + 0.5);
AF.GEOM = { HORIZON, GROUND_BOTTOM, ROWS_TOP };
AF.colWidth = colWidth;

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
      for (let k = 0; k < slots; k++) items.push({ pond: true, group: i, days: t.gap, from: t.gap_from, to: t.gap_to, slots, first: k === 0, seed: (t.seed ^ (k * 7919 + 17)) >>> 0 });
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
  const x = land.placeX ? land.placeX(it, env) : it.x;  // a landscape may squeeze the rows onto its own ground
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
})();

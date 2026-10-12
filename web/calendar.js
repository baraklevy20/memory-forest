/* Memory Forest — the study calendar, under the forest or on its own: one tile a day in weeks
 * (starting on the day your system, or the setting, says), as the Review Heatmap add-on draws
 * them. A day studied is in the scenery's colour, standing out more from the page the more you
 * reviewed (measured against your own days, so every pace uses all four shades); a missed day is
 * a faint tile (the tooltip says when a break made a pond); the days ahead are tilled soil,
 * stronger the more cards fall due. The milestones are the forest's own: each of its animals
 * (AF.VISITOR_SPRITES) stands on the day it came, in the scenery's own look for them, and today's
 * seedling (AF.pixel.sprite) stands on today once you have studied. The current streak has a
 * bracket under it, with the trophies and the goal ahead in a lane below. A click on a day opens
 * its cards in Anki's browser (actions.browse_calendar_day); a right-click pins it (marks.py).
 *
 * Two views, each fitted to the room there is: Timeline (`timeline`: a year or more with this
 * month most of the way along, paged back and on with ‹ ›; on the phone, the whole history swiped
 * along) and By year (`by_year`: January to December). payload.py sends data.calendar = { view,
 * start, days, due, animals, breakDays, browse, marks, forestStart, streakFromStart, weekStart }:
 * the date of the first day counted, the reviews of each day from it to today, the cards due on
 * each day from today on, the day each animal came, the forest's own rule for ponds, whether a
 * click opens a day, the days you pinned, the forest's start date (if any), whether the streak
 * restarts there, and the weekday the weeks start on. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hashStr, hex, rgb, layer, esc, mix, cap, send, animates } = AF.u;
const { SEEDLING } = AF.STAGE;

// low-res pixels: a day's square, the tile drawn in it, the band above the weeks for the
// animals and the pins (at their day's column), and the streak lane below the weeks: the
// brackets, with the trophies and the goal pennant under them
const CELL = 11, TILE = 9, TOP = 14, ROWS = 7, BRACKET = 15;  // (TOP: the tallest icon's height, and room under it)
// css pixels: the footer's row (the journal and the key), the month labels' band and the streaks'
// notes (forest.css), for the room kept for the calendar before it is drawn
const FOOT_H = 18, MONTHS_H = 14, NOTES_H = 16;
const LABEL_END = 30;  // css px: a month's label starting this close to the row's end is left out
// the smallest scale the pixels stay crisp at, in device pixels; below it they are smoothed, and
// Timeline shows fewer months
const SHARP = 1.5;
const SHOWN_STREAK = 30;  // an earlier streak this long or longer gets a bracket of its own
// the trophies of your longest streaks, first to third: a cup on a stand, in pixels (G the
// metal, L its shine, D its shade), and each one's metal
const TROPHY = ['GGGGGGG', 'G.GLG.G', 'G.GLG.G', '.GGGGG.', '..GGG..', '...D...', '..DDD..', '.DDDDD.'];
const TROPHIES = [
  { G: '#e3b04b', L: '#fff3c4', D: '#a8782a', place: 'longest' },
  { G: '#c9ccd1', L: '#f6f7f9', D: '#8b9098', place: 'second-longest' },
  { G: '#c4834a', L: '#ecc196', D: '#8a5528', place: 'third-longest' }
].map(t => ({ frames: [TROPHY], pal: { G: t.G, L: t.L, D: t.D }, place: t.place }));
// a day you marked as important (an exam, say: marks.py), its pin: R the head, L its shine, D the needle
const PIN = { frames: [['.RRR.', 'RLRRR', 'RRRRR', '.RRR.', '..D..', '..D..', '..D..']], pal: { R: '#e0524a', L: '#ffb3a8', D: '#8a7a6a' } };
// the goal ahead: a pennant on the day the current streak would pass the next record, gold when
// it would be your longest, silver your second-longest (P its pole, G the metal, L its shine)
const GOAL = ['PGGGG', 'PGGLG', 'PGGG.', 'PG...', 'P....', 'P....', 'P....', 'P....'];
const GOALS = TROPHIES.slice(0, 2).map(t => ({ frames: [GOAL], pal: { P: '#8a7a6a', G: t.pal.G, L: t.pal.L }, place: t.place }));
const GOAL_LINE = 0.75;  // the dotted line from today to the goal: gold, this strong (on a dark page)
// the trophies' and the pennant's metals on a light page, by their own metal: gold, silver, bronze
const METALS_ON_LIGHT = { '#e3b04b': { G: '#b07d1e', L: '#e3b04b', D: '#8f6a1c' }, '#c9ccd1': { G: '#8b9098', L: '#c9ccd1', D: '#6f747c' },
  '#c4834a': { G: '#a8692f', L: '#c4834a', D: '#7a4a22' } };
const PINE_PERCENT = 28;
// the four shades split your days studied in the last year at these shares (fewest to most):
// a quarter of them each
const SHADE_SPLITS = [0.25, 0.5, 0.75], SHADE_SPAN = 365;
// the days ahead by their cards due, on a log scale up to the busiest day in the next year (due
// counts fall away steadily, so a quarter of the days each would light only the next weeks)
const BEFORE_FOREST = 0.5;  // a day before the forest's start date: its tile this strong (your record, not the forest's time)
const TILE_VARIANTS = 4;  // each shade's tile comes in this many textures, drawn once
const DAY_MS = 86400000;
const MONTHS_SHOWN = 12, MONTHS_MIN = 3, TODAY_AT = 0.7;  // Timeline: a year (more when wide, fewer when narrow), this month this far along
// the phone: the calendar is one long timeline swiped along (no buttons to page with), its pixels
// this many css pixels each, running this many months past this one
const SWIPED_K = 1.4, SWIPED_AHEAD = 5, SWIPED_TODAY_AT = 0.75;  // (and opened with today this far across)
const LABEL_GAP = 6, TIP_GAP = 8;  // css px between two month labels, and between a day and its tooltip
const THEME_SETTLE_MS = 400;
const TOUCH_PAD = 6, TAP_SLOP = 10;  // low-res px round an animal, a pin or a trophy that a finger's tap still counts for; css px a tap may move  // a page whose colour eases to the new theme has got there by then
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const deep = v => Array.isArray(v) ? v.map(deep) : hex(v);
const P = {};
Object.entries({
  // a day ahead's tilled soil, warm browns from light tan to dark loam, the same on any page
  // (never faded into it), the busiest days the lightest
  till: [['#d2a86e', '#c99e64'], ['#b07a42', '#a6713a'], ['#87552a', '#7d4d25'], ['#5c3517', '#532f13']],
  tillEdge: ['#b8905a', '#925f30', '#6b411d', '#44260f'],
  gold: '#e3b04b', goldOnLight: '#a8782a', past: '#9a8a74',
  // today's frame: light on a dark page, dark on a light one
  today: '#f4e3a0', todayOnLight: '#5e4a22'
}).forEach(([k, v]) => { P[k] = deep(v); });

const utc = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const iso = ms => new Date(ms).toISOString().slice(0, 10);
// a day as the forest's tooltips write it (AF.u.fmtDate: your system's own way), with its weekday
const fmt = ms => AF.u.fmtDate(iso(ms));
const weekday = ms => new Date(iso(ms) + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long' });
// a day's row: 0 on the day the weeks start (payload.WEEK_START_DAYS: Monday unless the system
// or the setting says otherwise), as the page counts days (Sunday 0)
let weekStart = 1;
const dow = ms => (new Date(ms).getUTCDay() - weekStart + 7) % 7;
const num = n => n.toLocaleString('en');
const yearOf = ms => new Date(ms).getUTCFullYear();

/* every day by its offset from today (0 today, -1 yesterday, 1 tomorrow): its reviews or cards
 * due, the streaks (runs of days studied), the breaks long enough to make a pond, and the
 * review counts that split your days into the four shades */
function history(cal) {
  const today = utc(cal.start) + (cal.days.length - 1) * DAY_MS;
  const first = 1 - cal.days.length;  // the first day counted
  // (a start date leaves your record whole: `fs`, the day the forest began, only dims the days
  // before it, brings the animals from it on, and the ponds, the forest's, are only after it)
  const n = o => o > 0 ? cal.due[o] || 0 : o >= first ? cal.days[o - first] || 0 : 0;
  const fs = cal.forestStart ? (utc(cal.forestStart) - today) / DAY_MS : null;
  const breakDays = cal.breakDays || 7;
  const runs = [], pond = new Set();
  let run = null, gap = null;
  for (let o = first; o <= 0; o++) {
    if (n(o)) {
      // a break of breakDays or more is a pond, as forest_data._breaks has it (counted from the
      // forest's start)
      const from = fs !== null ? Math.max(gap, fs) : gap;
      if (gap !== null && o - from >= breakDays) for (let g = from; g < o; g++) pond.add(g);
      gap = null;
      // (a streak runs on over the forest's start date, your real one, as the caption counts it;
      // unless the Decks tab says to count it from the start date too)
      if (run && !(cal.streakFromStart && o === fs)) run.to = o; else runs.push(run = { from: o, to: o });
    } else {
      run = null;
      if (gap === null && o > first) gap = o;
    }
  }
  // a streak lives on through today until today ends (forest_data._streaks)
  const end = runs[runs.length - 1];
  const current = end && end.to >= -1 ? end : null;
  const runOf = o => runs.find(r => o >= r.from && o <= r.to) || null;
  // your three longest streaks (of SHOWN_STREAK days or more; the first to reach a length ranks
  // above a later one as long), each with a trophy at its last day: gold, silver, bronze
  const podium = new Map(runs.filter(r => r.to - r.from + 1 >= SHOWN_STREAK)
    .sort((a, b) => (b.to - b.from) - (a.to - a.from) || a.from - b.from).slice(0, TROPHIES.length).map((r, i) => [r, i]));
  // the goal: the day the current streak, kept up, passes the second-longest of the others (to be
  // second) or, once it has, the longest (to be first); none once it is the longest already
  let goal = null;
  if (current) {
    const others = runs.filter(r => r !== current && r.to - r.from + 1 >= SHOWN_STREAK).map(r => r.to - r.from + 1).sort((a, b) => b - a);
    const len = current.to - current.from + 1, need = i => Math.max(SHOWN_STREAK, (others[i] || 0) + 1);
    const rank = others.length && len < need(1) ? 1 : len < need(0) ? 0 : -1;
    if (rank >= 0) goal = { o: current.from + need(rank) - 1, rank, beats: others[rank] || 0 };
  }
  // the shades: where your days studied in the last year split into four (at least 1 apart)
  const splitsOf = vals => {
    vals.sort((a, b) => a - b);
    const splits = [1];
    for (const share of SHADE_SPLITS) splits.push(Math.max(splits[splits.length - 1] + 1, vals.length ? vals[Math.floor(share * (vals.length - 1))] + 1 : splits.length * 50));
    return v => splits.reduce((lv, s, i) => v >= s ? i : lv, 0);  // 0 the fewest .. 3 the most
  };
  const recent = [];
  let busiest = 1;
  for (let o = Math.max(first, 1 - SHADE_SPAN); o <= 0; o++) if (n(o)) recent.push(n(o));
  for (let o = 1; o <= Math.min(SHADE_SPAN, cal.due.length - 1); o++) busiest = Math.max(busiest, n(o));
  const shade = splitsOf(recent), dueShade = v => Math.min(3, Math.floor(4 * Math.log(v) / Math.log(busiest + 1)));
  // the animals, each on the day it came (none before the forest began)
  const animals = new Map();
  for (const a of cal.animals || []) if (-a.ago >= (fs !== null ? fs : first)) animals.set(-a.ago, (animals.get(-a.ago) || []).concat([a]));
  return {
    today, first, n, fs, runs, pond, current, runOf, podium, goal, animals,
    marked: new Set((cal.marks || []).map(d => (utc(d) - today) / DAY_MS)),
    shade, dueShade, dueToday: cal.due[0] || 0,
    ahead: cal.due.length - 1  // the last day ahead counted
  };
}

/* the days a view shows, [from, to] as offsets: Timeline's `count` months (a year, more when
 * wide, fewer when narrow), `page` such stretches back (negative) or on; the phone's whole
 * history, swiped along; or By year's January to December */
function windowOf(H, view, page, year, count) {
  if (view === 'swiped') {  // the phone's: from the first month counted to a few months ahead, swiped along
    const f = new Date(H.today + H.first * DAY_MS), t = new Date(H.today);
    return { from: (Date.UTC(f.getUTCFullYear(), f.getUTCMonth(), 1) - H.today) / DAY_MS,
      to: (Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + SWIPED_AHEAD + 1, 1) - H.today) / DAY_MS - 1, apart: true };
  }
  if (view === 'by_year') {
    const y = year || yearOf(H.today);
    return { from: (Date.UTC(y, 0, 1) - H.today) / DAY_MS, to: (Date.UTC(y, 11, 31) - H.today) / DAY_MS, year: y };
  }
  // Timeline: this month TODAY_AT along (a year: eight months before it and three after), the
  // past being the story
  const t = new Date(H.today), y = t.getUTCFullYear(), m = t.getUTCMonth() - Math.round(count * TODAY_AT) + page * count;
  return { from: (Date.UTC(y, m, 1) - H.today) / DAY_MS, to: (Date.UTC(y, m + count, 1) - H.today) / DAY_MS - 1, apart: true };
}

/* the four shades a day studied takes, fewest reviews to most, with their tiles' edges: built
 * round the scenery's colour (its own `calendar` colour, or its most colourful crown colour,
 * AF.foliage), from pale to deep, so the calendar belongs to the scene */
const PALE = [232, 228, 216], DARK = [16, 16, 16];
// a scenery's colour kept within a lightness and saturation a tile can show: a silhouette
// scenery's near-black trees (Witch across the moon) would make every tile black
const KEY_L = [0.36, 0.56], KEY_S = 0.28;
function readable(c) {
  const [r, g, b] = c.map(v => v / 255), max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, sat = 0, l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6;
  }
  l = Math.min(KEY_L[1], Math.max(KEY_L[0], l)); sat = Math.max(KEY_S, sat);
  const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat, p = 2 * l - q;
  const ch = t => { t = (t + 1) % 1; return 255 * (t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p); };
  return [ch(h + 1 / 3), ch(h), ch(h - 1 / 3)];
}
/* The page the calendar sits on: its colour (the first background behind `el` with any, AF.u.pageBg;
 * on a phone's transparent card, the app's own, AF.u.appBg) and whether it is dark (Anki's dark mode). */
function pageOf(el) {
  const behind = [];
  for (let e = el; e && e.nodeType === 1; e = e.parentElement) behind.push(e);
  const bg = AF.u.pageBg(behind) || AF.u.appBg();
  return { bg, dark: bg[0] * 0.3 + bg[1] * 0.59 + bg[2] * 0.11 < 128 };
}
/* the shades run towards the page's opposite, so a day stands out the more you studied: darker
 * for more on a light page, brighter for more on a dark one (a dark page's pale tiles would
 * otherwise draw the eye to your quietest days) */
function shades(env, dark) {
  // a scenery whose trees are not its colour names its own (`calendar`: Frozen market's ice blue)
  const chroma = c => Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]), own = AF.envOf(env).calendar;
  const key = readable(own ? hex(own) : AF.foliage(env).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a));
  // (about evenly far apart, the top two as easy to tell apart as the rest)
  const steps = dark ? [mix(key, DARK, 0.58), mix(key, DARK, 0.36), mix(key, DARK, 0.1), mix(key, PALE, 0.5)]
    : [mix(key, PALE, 0.45), mix(key, PALE, 0.1), mix(key, DARK, 0.22), mix(key, DARK, 0.48)];
  return { grass: steps.map(c => [c, mix(c, DARK, 0.07)]), edge: steps.map(c => mix(c, DARK, 0.22)) };
}

/* the scene the calendar is drawn for: the forest's own (`env`, its theme and the look its
 * environment gave the animals), or with no forest showing, one made from the data alone */
function sceneOf(data, env) {
  if (!env) {
    env = { mood: data.mood, data, W: 200, H: 100, u: 1, theme: AF.theme(data.mood, data.stats, data.events) };
    const spec = AF.envOf(env);
    try { if (spec.prepare) spec.prepare(env); } catch { /* only its look for the animals is wanted */ }
  }
  // the scenery's trees in plain light (no hour's tint, haze or rim): the same at any hour
  return { theme: Object.assign({}, env.theme, { tint: null, tintAmt: 0, hzStep: 0, rim: null }), mood: env.mood, u: 1,
    layout: null, data: env.data, visitorTint: env.visitorTint };
}
function spriteOf(t, h, env) {
  try { return AF.pixel.sprite(t, h, 0, env); }
  catch { return AF.pixel.sprite(t, h, 0, Object.assign({}, env, { mood: Object.assign({}, env.mood, { special: 'natural' }) })); }
}
/* a missed day, a day ahead with nothing due, or one before your history, drawn empty: a faint
 * grey square (no edge of its own) that sits back on Anki's light and dark pages alike */
const EMPTY = 'rgba(128, 128, 128, 0.11)';
function empty(g, x, y) { g.fillStyle = EMPTY; g.fillRect(x, y, TILE, TILE); }
/* a shade's tiles, each of its TILE_VARIANTS textures drawn once (two tones in 2x2 clusters and
 * an edge), kept for every calendar after */
const tiles = new Map();
function tilesOf(pal, edge) {
  const key = pal.concat([edge]).map(c => c.join(',')).join('|');
  if (!tiles.has(key)) {
    const out = [];
    for (let v = 0; v < TILE_VARIANTS; v++) {
      const [cv, g] = layer(TILE, TILE);
      for (let y = 0; y < TILE; y++) for (let x = 0; x < TILE; x++) {
        const e = y === TILE - 1 || x === TILE - 1;
        g.fillStyle = rgb(e ? edge : pal[(hashStr(v + ',' + (x >> 1) + ',' + (y >> 1)) & 3) === 0 ? 1 : 0]);
        g.fillRect(x, y, 1, 1);
      }
      out.push(cv);
    }
    tiles.set(key, out);
  }
  return tiles.get(key);
}
// a light colour the scenery gives its animals (Synthwave's neon) glows around them, and
const GLOW_FROM = 0.55, GLOW_ALPHA = 0.32;
// any other animal is outlined in the page's own colour, cut out of the tiles as the gaps
// between them are, so it reads at a tile's size on any shade
function drawAnimal(g, spr, x0, y0, tint, outline) {
  const rows = spr.frames[0], w = rows[0].length, at = (x, y) => y >= 0 && y < rows.length && x >= 0 && x < w && spr.pal[rows[y][x]];
  const c = tint && hex(tint), light = c && (c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11) / 255 >= GLOW_FROM;
  g.fillStyle = light ? rgb(c, GLOW_ALPHA) : rgb(outline);
  for (let y = -1; y <= rows.length; y++) for (let x = -1; x <= w; x++) {
    if (!at(x, y) && (at(x - 1, y) || at(x + 1, y) || at(x, y - 1) || at(x, y + 1))) g.fillRect(x0 + x, y0 + y, 1, 1);
  }
  rows.forEach((line, y) => { for (let x = 0; x < w; x++) {
    const col = spr.pal[line[x]];
    if (col) { g.fillStyle = tint || col; g.fillRect(x0 + x, y0 + y, 1, 1); }
  } });
}

/* the shades a view draws with: the scenery's for days studied, soil for days ahead: a day's
 * tile among them (or null for an empty one), the key's, and the hover's */
function paletteOf(H, sp, paper) {
  const dark = paper.dark, S = shades(sp, dark);
  const soil = lv => P.till[lv], soilEdge = lv => P.tillEdge[lv];
  const dueLv = n => 3 - H.dueShade(n);  // (the busiest day the lightest tan, on any page)
  const tile = c => {
    const v = hashStr(iso(c.ms)) % TILE_VARIANTS, soilTile = lv => tilesOf(soil(lv), soilEdge(lv))[v];
    // today before you study: soil, by the cards it has due, until your first review
    if (c.o === 0 && !c.n && H.dueToday) return soilTile(dueLv(H.dueToday));
    if (!c.n || c.o > H.ahead) return null;
    if (c.o > 0) return soilTile(dueLv(c.n));
    const lv = H.shade(c.n);
    return tilesOf(S.grass[lv], S.edge[lv])[v];
  };
  const lit = S.grass[dark ? 3 : 0][0];  // the hover's colour: the shade that stands out most from the page
  // (the key: the four shades of a day studied; the soil and the empty days say what they are)
  return { tile, key: [0, 1, 2, 3].map(lv => tilesOf(S.grass[lv], S.edge[lv])[0]), ring: rgb(lit), glow: rgb(lit, 0.45) };
}
// a seedling of its own day's kind (pine or broadleaf, and its look)
function seedlingOf(sp, ms) {
  const seed = hashStr('calendar|' + iso(ms));
  return spriteOf({ stage: SEEDLING, kind: seed % 100 < PINE_PERCENT ? 1 : 0, size: 0, health: 0, variant: seed % 7, seed, index: -1 }, 7, sp);
}
function frame(g, x, y, T, dark) {  // a light frame round today's tile (dark on a light page)
  g.fillStyle = rgb(dark ? P.today : P.todayOnLight);
  const tx = x - 1, ty = y - 1;
  g.fillRect(tx, ty, T + 1, 1); g.fillRect(tx, ty + T, T + 1, 1); g.fillRect(tx, ty, 1, T + 1); g.fillRect(tx + T, ty, 1, T + 1);
}

/* one view drawn: the canvas, and where everything on it is */
function paint(H, win, sp, paper) {
  const dark = paper.dark, band = TOP;
  // the days in weeks, their first day on top; Timeline starts each month in a column of its own (By
  // year runs its months on in the same weeks)
  const cells = [];
  let col = 0;
  // (Timeline: a month that starts its week, the one before having filled its last, has no
  // ragged edge to set it apart, so an empty column comes between them)
  for (let o = win.from; o <= win.to; o++) {
    const ms = H.today + o * DAY_MS, row = dow(ms), first = o === win.from, starts = win.apart && new Date(ms).getUTCDate() === 1;
    if (!first && starts) col += row === 0 ? 2 : 1;
    else if (!first && row === 0) col++;
    cells.push({ o, ms, n: H.n(o), col, row });
  }
  const xOf = c => 1 + c.col * CELL, yOf = c => band + c.row * CELL + 1;
  const at = new Map();  // (each day by its column and row, for the pointer)
  for (const c of cells) { c.x = xOf(c); c.y = yOf(c); at.set(c.col * ROWS + c.row, c); }
  const W = xOf(cells[cells.length - 1]) + CELL, Hh = band + ROWS * CELL + BRACKET;
  const [cv, g] = layer(W, Hh);
  const pal = paletteOf(H, sp, paper);
  // the tiles first, each with a texture of its own day's (the same whichever page it is on); a
  // missed day, or one before your history, faint, so the view is never half bare
  for (const c of cells) {
    const t = pal.tile(c);
    // (a day before the forest's start date, studied or not, dimmed)
    g.globalAlpha = H.fs !== null && c.o < H.fs ? BEFORE_FOREST : 1;
    if (t) g.drawImage(t, c.x, c.y);
    else empty(g, c.x, c.y);
    g.globalAlpha = 1;
  }
  const animals = H.animals;
  const marks = [];  // (where the marks over the weeks stand, for the pointer)
  // the forest's first day, with a start date: its seedling over the day it began (the one mark
  // the start date leaves here, besides the animals coming only after it)
  if (H.fs !== null && H.fs >= win.from && H.fs <= win.to) {
    const c = cells[H.fs - win.from], s = seedlingOf(sp, c.ms), x0 = c.x + Math.floor((TILE - s.width) / 2), y0 = band - 2 - s.height;
    g.drawImage(s, x0, y0);
    marks.push({ x0, x1: x0 + s.width, y0, y1: band - 1, c });
  }
  // today's seedling, once today is studied (an animal that came today stands there instead)
  const sown = cells.find(c => c.o === 0 && c.n && !animals.has(0));
  if (sown) {
    const s = seedlingOf(sp, sown.ms);
    g.drawImage(s, sown.x + Math.floor((TILE - 1 - s.width) / 2) + 1, sown.y + TILE - s.height);
  }
  const today = cells.find(c => c.o === 0);
  if (today) frame(g, today.x, today.y, TILE, dark);
  // the streaks: a bracket under the weeks each ran through, gold for the current one, cut at
  // the view's edges (with no end mark there)
  const by = band + ROWS * CELL + 3, brackets = [];
  for (const r of H.runs) {
    const len = r.to - r.from + 1, live = r === H.current;
    if (len < SHOWN_STREAK && !live) continue;
    const fo = Math.max(r.from, win.from), to = Math.min(r.to, win.to);
    if (fo > to) continue;
    const a = cells[fo - win.from], b = cells[to - win.from];
    const x0 = a.x + (fo === r.from ? 1 : 0), x1 = b.x + TILE - 2;
    g.fillStyle = rgb(live ? (dark ? P.gold : P.goldOnLight) : P.past);
    g.fillRect(x0, by, x1 - x0 + 1, 1);
    if (fo === r.from) g.fillRect(x0, by - 2, 1, 2);
    if (to === r.to) g.fillRect(x1, by - 2, 1, 2);
    brackets.push({ x0, x1, len, live });
  }
  // the streak lane: a trophy under the last day of each of your longest streaks and the goal
  // pennant under its day, below the brackets, and a dotted gold line from today on to the goal
  // (all the streak's marks together, none cutting through the weeks)
  if (H.goal && H.current && H.current.to >= win.from && H.current.to <= win.to) {
    const a = cells[H.current.to - win.from], gc = H.goal.o <= win.to ? cells[H.goal.o - win.from] : cells[cells.length - 1];
    g.fillStyle = dark ? rgb(P.gold, GOAL_LINE) : rgb(P.goldOnLight);
    for (let x = a.x + TILE; x <= gc.x + 4; x += 2) g.fillRect(x, by, 1, 1);
    if (H.goal.o <= win.to) g.fillRect(gc.x + 4, by - 2, 1, 2);
  }
  const lane = [];
  for (const [run, i] of H.podium) lane.push([run.to, TROPHIES[i]]);
  if (H.goal) lane.push([H.goal.o, GOALS[H.goal.rank]]);
  for (const [o, spr] of lane) {
    if (o < win.from || o > win.to) continue;
    const c = cells[o - win.from], w = spr.frames[0][0].length, x0 = c.x + Math.floor((TILE - w) / 2), y0 = by + 3;
    // (on a light page in their deeper shades: pale gold and silver would fade into it)
    const metal = !dark && METALS_ON_LIGHT[spr.pal.G];
    drawAnimal(g, metal ? Object.assign({}, spr, { pal: Object.assign({}, spr.pal, metal) }) : spr, x0, y0, null, paper.bg);
    marks.push({ x0, x1: x0 + w, y0, y1: y0 + spr.frames[0].length, c });
  }
  // the animals and the pins of the days you marked in the band over the weeks, at their day's
  // column, feet just above the first row, each moved right of the one before where they would touch
  {
    const placed = [], above = new Map(animals);
    for (const o of H.marked) above.set(o, [{ spr: PIN }].concat(above.get(o) || []));
    cells.filter(c => above.has(c.o)).sort((a, b) => a.col - b.col || a.row - b.row).forEach(c => {
      above.get(c.o).forEach(a => {
        const spr = a.spr || (AF.VISITOR_SPRITES && AF.VISITOR_SPRITES[a.key]);
        if (!spr) return;
        const rows = spr.frames[0], w = rows[0].length;
        let x0 = c.x + Math.floor((TILE - w) / 2);
        for (const [l, r] of placed) if (x0 <= r + 1 && x0 + w >= l - 1) x0 = r + 2;
        const y0 = band - 2 - rows.length;
        placed.push([x0, x0 + w - 1]);
        drawAnimal(g, spr, x0, y0, sp.visitorTint, paper.bg);
        marks.push({ x0, x1: x0 + w, y0, y1: band - 1, c });
      });
    });
  }
  return { cv, W, Hh, cells, at, brackets, band, marks, ring: pal.ring, glow: pal.glow, key: pal.key };
}

// a year's weeks, about as wide as they come: By year's, or Timeline's months apart (its
// months' own weeks, and the odd empty column)
const widthOf = view => (view === 'by_year' ? 53 : 65) * CELL + 1;
const dpr = () => window.devicePixelRatio || 1;
const sharpK = () => Math.min(1, SHARP / dpr());
/* the scale `W` low-res pixels fill `width` css pixels at: whole device pixels, every tile and gap
 * the same; or, too narrow to stay crisp that way, all the width, smoothed (lay) */
const scaleFor = (width, W) => { const k = Math.floor(width / W * dpr()) / dpr(); return k >= sharpK() ? k : width / W; };
/* the months Timeline shows in a grid this wide: a year at least, filling the width at whole
 * device pixels; fewer, down to MONTHS_MIN, where a year would be too small to stay crisp */
function countFor(view, width) {
  if (view !== 'timeline' || !width) return MONTHS_SHOWN;
  const k = Math.floor(width / widthOf(view) * dpr()) / dpr();
  if (k >= sharpK()) return Math.max(MONTHS_SHOWN, Math.floor(MONTHS_SHOWN * width / (widthOf(view) * k)));
  return Math.max(MONTHS_MIN, Math.floor(MONTHS_SHOWN * width / (widthOf(view) * sharpK())));
}
// the phone's timeline scale for weeks this tall (css px): whole pixels, from SWIPED_K up
AF.calendarScaleFor = height => Math.max(SWIPED_K, Math.floor(height * dpr() / (TOP + ROWS * CELL + BRACKET)) / dpr());
/* how tall the calendar will be at this width, for the room kept for it until it is drawn */
AF.calendarHeight = function (cal, width) {
  const view = cal.view === 'by_year' ? 'by_year' : 'timeline', W = widthOf(view) * countFor(view, width) / MONTHS_SHOWN;
  const k = width > 0 ? scaleFor(width, W) : 1;
  return Math.ceil(MONTHS_H + (TOP + ROWS * CELL + BRACKET) * k + NOTES_H + FOOT_H);
};

AF.calendar = function (root, data, env) {
  const cal = data.calendar;
  if (!cal || !cal.days || !cal.days.length) return;
  // (a calendar drawn here before stops watching the page: this one takes its place)
  if (root.afCalStop) root.afCalStop();
  let box = root.querySelector('.af-cal');
  if (!box) { box = document.createElement('div'); box.className = 'af-cal'; root.append(box); }
  weekStart = cal.weekStart == null ? 1 : cal.weekStart;
  const H = history(cal), view = cal.view === 'by_year' ? 'by_year' : 'timeline', sp = sceneOf(data, env);
  const deck = data.deckId && !data.testForest ? data.deckId : '';
  const swiped = !data.inAnki;  // on the phone: swiped along rather than paged
  let page = 0, year = null;  // Timeline's stretch (0: today's), By year's year

  // the weeks, and a footer: the forest's journal (the panel's last line), the way about (‹ ›,
  // with Today before them only once paged away, so they stay where they are as it comes and
  // goes) and the key, the last two shown on hover (forest.css)
  box.innerHTML = '<div class="af-cal-grid"><div class="af-cal-months"></div><div class="af-cal-hover" hidden></div><div class="af-cal-notes"></div></div>'
    + '<div class="af-cal-foot"><span class="af-cal-journal"></span><span class="af-cal-acts">'
    + '<button type="button" class="af-cal-chev af-cal-today" data-go="0">Today</button>'
    + '<button type="button" class="af-cal-chev" data-go="-1" aria-label="Earlier" title="Earlier">‹</button>'
    + '<button type="button" class="af-cal-chev" data-go="1" aria-label="Later" title="Later">›</button>'
    + '</span><span class="af-cal-key"></span></div>'
    + '<div class="af-tip af-cal-tip" hidden></div>';
  if (swiped) box.classList.add('af-cal-swiped');
  // the forest's journal comes down to the foot of the panel: a forest's caption with the
  // calendar under it would read as the calendar's
  const journal = root.querySelector('.af-caption .af-journal');
  if (journal) box.querySelector('.af-cal-journal').appendChild(journal);
  box.style.minHeight = '';  // (the room kept for it while the forest was building)
  const grid = box.querySelector('.af-cal-grid'), btn = go => box.querySelector(`[data-go="${go}"]`);
  // (on the phone only Today, which brings today back into view)
  if (swiped) { btn(-1).hidden = btn(1).hidden = true; grid.classList.add('af-cal-scroll'); }
  box.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => (swiped ? toToday(true) : go(b.dataset.go))));
  const months = box.querySelector('.af-cal-months');
  const notes = box.querySelector('.af-cal-notes'), tip = box.querySelector('.af-cal-tip'), hover = box.querySelector('.af-cal-hover');
  let drawn = null, k = 2, last;  // (last: the day the pointer was last on)
  let paper = pageOf(box);
  // the day under the pointer: lit with the shade that stands out most and ringed in it, lifted a little
  const ring = c => {
    hover.hidden = !c;
    if (!c) return;
    const cv = drawn.cv;
    hover.style.left = (cv.offsetLeft + (c.x - 1) * k) + 'px';
    hover.style.top = (cv.offsetTop + (c.y - 1) * k) + 'px';
    hover.style.width = hover.style.height = (TILE + 1) * k + 'px';
    hover.style.borderColor = drawn.ring; hover.style.background = drawn.glow;
  };
  const unpoint = () => { tip.hidden = true; ring(null); last = undefined; };
  // how far you can page: back to the first day counted, on to the last day ahead counted
  const can = win => ({ back: win.from > H.first, on: win.to < H.ahead });

  function draw() {
    const count = swiped ? MONTHS_SHOWN : countFor(view, grid.clientWidth);
    const win = windowOf(H, swiped ? 'swiped' : view, page, year, count);
    drawn = Object.assign(paint(H, win, sp, paper), { win, count });
    last = undefined;
    grid.querySelectorAll('canvas').forEach(c => c.remove());
    drawn.cv.className = 'af-cal-canvas';
    grid.insertBefore(drawn.cv, notes);
    const may = can(win);
    btn(-1).disabled = !may.back; btn(1).disabled = !may.on;
    // what the tiles mean, read off the tiles themselves
    const swatch = cv => { const c = document.createElement('canvas'); c.width = c.height = TILE; c.getContext('2d').drawImage(cv, 0, 0); c.className = 'af-cal-swatch'; return c; };
    const keyBox = box.querySelector('.af-cal-key'), word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
    keyBox.textContent = '';  // (and each appended alone: Chromium 77, Anki 2.1.45's, has no replaceChildren)
    [word('Less')].concat(drawn.key.map(swatch), [word('More')]).forEach(el => keyBox.appendChild(el));
    btn(0).disabled = !swiped && (view === 'by_year' ? win.year === yearOf(H.today) : page === 0);
    lay();
  }
  function go(where) {
    const was = drawn.win.from;
    if (where === '0') { page = 0; year = null; }
    else {
      const may = can(drawn.win);
      if (where === '-1' ? !may.back : !may.on) return;  // (a click on a button just disabled)
      if (view === 'by_year') year = (year || yearOf(H.today)) + +where;
      else page += +where;
    }
    unpoint();
    draw();
    // the new stretch slides in from the side you went towards (unless the forest is kept still)
    if (drawn.win.from !== was && animates(data)) {
      grid.classList.remove('af-cal-from-left', 'af-cal-from-right');
      void grid.offsetWidth;  // (so the animation starts again on a quick second click)
      grid.classList.add(drawn.win.from < was ? 'af-cal-from-left' : 'af-cal-from-right');
    }
  }
  // fitted to the room there is (scaleFor), smaller than its pixels if need be: no scrolling
  function lay() {
    const d = drawn;
    k = swiped ? Math.round((data.swipedK || SWIPED_K) * dpr()) / dpr() : scaleFor(grid.clientWidth || d.W * 2, d.W);
    d.cv.style.width = d.W * k + 'px'; d.cv.style.height = d.Hh * k + 'px';
    box.querySelectorAll('.af-cal-swatch').forEach(sw => { sw.style.width = sw.style.height = TILE * k + 'px'; });  // (the key's tiles as big as the calendar's)
    d.cv.style.imageRendering = k < sharpK() ? 'auto' : '';  // (too small to stay crisp, pixels smooth better than they drop)
    let html = '', lastM = -1;
    for (const c of d.cells) {
      const day = new Date(c.ms);
      if (day.getUTCDate() > 7 || day.getUTCMonth() === lastM || c.x * k > d.W * k - LABEL_END) continue;
      lastM = day.getUTCMonth();
      // January is its year alone, every other month its name
      const text = lastM === 0 ? String(day.getUTCFullYear()) : MONTHS[lastM];
      html += `<span${text !== MONTHS[lastM] ? ' class="af-cal-year"' : ''} style="left:${c.x * k}px">${text}</span>`;
    }
    months.innerHTML = html;
    // where two would touch (a narrow calendar), the one with a year stays and the other goes
    let prev = null;
    for (const s of months.children) {
      if (prev && s.offsetLeft < prev.offsetLeft + prev.offsetWidth + LABEL_GAP) {
        const drop = prev.classList.contains('af-cal-year') && !s.classList.contains('af-cal-year') ? s : prev;
        drop.hidden = true;
        if (drop === s) continue;
      }
      prev = s;
    }
    // each earlier streak's length under its bracket, if there is room for it (the current one's is in the caption)
    notes.innerHTML = d.brackets.filter(b => !b.live && (b.x1 - b.x0) * k >= 48).map(b =>
      `<span class="af-cal-note" style="left:${(b.x0 + b.x1) / 2 * k}px">${num(b.len)} days</span>`).join('');
    if (swiped) { away(); clip(); }
  }
  // the phone's timeline: opened on today, most of the way across, the days behind it in view
  function toToday(smooth) {
    const today = drawn.cells.find(c => c.o === 0), left = today ? Math.max(0, today.x * k - grid.clientWidth * SWIPED_TODAY_AT) : 0;
    if (smooth && grid.scrollTo) grid.scrollTo({ left, behavior: 'smooth' }); else grid.scrollLeft = left;
  }
  // (the timeline: Today only while today is scrolled out of view; a month's label cut by an
  // edge hidden until whole)
  function away() {
    const t = drawn.cells.find(c => c.o === 0);
    if (!t) return;
    const x = t.x * k - grid.scrollLeft;
    btn(0).hidden = x > 0 && x < grid.clientWidth - TILE * k;
  }
  function clip() {
    for (const s of months.children) s.style.visibility = s.offsetLeft < grid.scrollLeft + 4 || s.offsetLeft + s.offsetWidth > grid.scrollLeft + grid.clientWidth - 4 ? 'hidden' : '';
  }
  draw();
  if (swiped) {
    toToday(false);
    grid.addEventListener('scroll', () => { away(); clip(); }, { passive: true }); away(); clip();
    // turned on its side (the phone's full screen, web/phone.js), a swipe along the calendar runs
    // down the screen, which the page's own scrolling won't follow: it is followed here
    let from = null;
    grid.addEventListener('touchstart', e => { from = grid.closest('.af-sideways') && e.touches.length === 1 ? [e.touches[0].clientY, grid.scrollLeft] : null; }, { passive: true });
    grid.addEventListener('touchmove', e => {
      if (!from) return;
      e.preventDefault();
      grid.scrollLeft = from[1] - (e.touches[0].clientY - from[0]);
    }, { passive: false });
    grid.addEventListener('touchend', () => { from = null; });
  }
  // a new width: Timeline's months counted again (draw), or the same ones laid out again
  let lastW = grid.clientWidth;
  const ro = window.ResizeObserver ? new ResizeObserver(() => {
    if (!box.isConnected) { stop(); return; }
    if (grid.clientWidth === lastW) return;
    lastW = grid.clientWidth;
    if (!swiped && countFor(view, lastW) !== drawn.count) draw(); else lay();
  }) : null;
  if (ro) ro.observe(grid);
  // Anki switched between light and dark: the page's colour is read again and the days painted
  // for it (their shades, the animals' outlines, today's frame). Anki marks the switch on the
  // page's classes, and the system's own switch shows in the colour scheme; a moment later too,
  // for a page whose colour eases across
  const repaper = () => {
    if (!box.isConnected) return;
    const p = pageOf(box);
    if (p.bg.join() === paper.bg.join()) return;
    paper = p; unpoint();
    draw();
  };
  const rethink = () => { if (!box.isConnected) { stop(); return; } requestAnimationFrame(repaper); setTimeout(repaper, THEME_SETTLE_MS); };
  const mo = window.MutationObserver ? new window.MutationObserver(rethink) : null;
  for (const el of [document.documentElement, document.body]) if (mo && el) mo.observe(el, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] });
  const scheme = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  if (scheme && scheme.addListener) scheme.addListener(rethink);
  function stop() {
    if (mo) mo.disconnect();
    if (ro) ro.disconnect();
    if (scheme && scheme.removeListener) scheme.removeListener(rethink);
    if (root.afCalStop === stop) root.afCalStop = null;
  }
  root.afCalStop = stop;

  // the day under the pointer (or an animal's, a pin's or a trophy's above or below the weeks):
  // its square's column and row, the gaps between tiles counted with the tile before them
  // (a finger's tap counts a little way round one, the nearest, as it hides what it touches;
  // never on the weeks themselves, where the tap is a day's)
  let touched = false;  // (the last press a finger's: pointerdown below)
  // (where on the canvas, AF.u.pointIn: right on a page the app zooms and in the phone's sideways
  // view; on anything but the canvas, nothing)
  const cellAt = e => {
    if (e.target !== drawn.cv) return null;
    const [x, y] = AF.u.pointIn(e, drawn.cv), px = x / k, py = y / k;
    const pad = touched && (py < drawn.band || py >= drawn.band + ROWS * CELL) ? TOUCH_PAD : 0;
    const off = m => Math.max(m.x0 - px, 0, px - m.x1 + 1) + Math.max(m.y0 - py, 0, py - m.y1 + 1);
    const mark = drawn.marks.filter(m => px >= m.x0 - pad && px < m.x1 + pad && py >= m.y0 - pad && py < m.y1 + pad)
      .sort((a, b) => off(a) - off(b))[0];
    if (mark) return mark.c;
    const col = Math.floor(px / CELL), row = Math.floor((py - drawn.band) / CELL);
    return px >= 0 && row >= 0 && row < ROWS ? drawn.at.get(col * ROWS + row) || null : null;
  };
  // which days a click opens: a day with reviews (today too, once studied), a day ahead with cards due
  const opens = c => cal.browse && c.n > 0 && c.o <= H.ahead && c.o >= H.first;
  const cards = (n, what) => `${num(n)} ${what}${n === 1 ? '' : 's'}`;
  // its date, its reviews or cards due, and where it sits in its streak
  const point = e => {
    const c = cellAt(e);
    if (c === last) return;  // (still on the same day: nothing changes)
    last = c;
    ring(c);
    grid.classList.toggle('af-click', !!c && opens(c));
    if (!c) { tip.hidden = true; return; }
    const run = c.o <= 0 && c.n ? H.runOf(c.o) : null;
    const what = c.o < H.first ? 'Before the first day your forest counts'
      : c.o > H.ahead ? 'Too far ahead to count'
      : c.o > 0 ? (c.n ? `${cards(c.n, 'card')} due` : 'Nothing due yet')
      : c.o === 0 && !c.n && H.dueToday ? `${cards(H.dueToday, 'card')} due, not studied yet`
      : c.o === 0 && H.dueToday ? `${cards(c.n, 'review')} so far, ${num(H.dueToday)} still due`
      : c.n ? cards(c.n, 'review') : H.pond.has(c.o) ? 'Not studied (a pond in the forest)' : 'Not studied';
    const day = run ? c.o - run.from + 1 : 0, total = run ? run.to - run.from + 1 : 0;
    const where = !run ? ''
      : (run === H.current ? `Day ${num(day)} of your ${num(total)}-day streak` : `Day ${num(day)} of ${num(total)} in a row`)
        + (day === 1 ? ': where it began' : '')
        + (H.podium.has(run) ? `<br>Your ${TROPHIES[H.podium.get(run)].place} streak` : '');
    const goal = H.goal && H.goal.o === c.o
      ? `<br>Keep your streak to here and it becomes your ${GOALS[H.goal.rank].place}` + (H.goal.beats ? `, past ${num(H.goal.beats)} days` : '') : '';
    const began = H.fs === c.o ? '<br>Your forest began' : '';
    const came = goal + began + (H.animals.get(c.o) || []).map(a => `<br>${esc(cap(a.label))} came: ${esc(a.why)}`).join('');
    const marked = H.marked.has(c.o) ? '<br>Marked as important' : '';
    tip.innerHTML = `<b>${esc(weekday(c.ms))}, ${esc(fmt(c.ms))}</b><br>${what}${where ? `<br><i>${where}</i>` : ''}${came}${marked}`;
    tip.hidden = false;
    // above the day, centred on it, so it never covers the days you read next (below it when
    // there is no room above), kept inside the calendar's sides; placed by the page's own
    // offsets, which a zoomed page leaves right
    const left = grid.offsetLeft + drawn.cv.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + drawn.cv.offsetTop;
    const cx = left + (c.x + TILE / 2) * k, top = canvasTop + (c.y - 1) * k, bottom = canvasTop + (c.y + TILE + 1) * k;
    const above = drawn.cv.getBoundingClientRect().top + (c.y - 1) * k - tip.offsetHeight - TIP_GAP >= 0;
    tip.style.left = Math.min(box.clientWidth - tip.offsetWidth, Math.max(0, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (above ? top - tip.offsetHeight - TIP_GAP : bottom + TIP_GAP) + 'px';
  };
  grid.addEventListener('mousemove', point);
  // a finger's tap, taken as it lifts (a phone's web view need not make up a mouse's move for
  // it), unless it was a swipe along the timeline
  let down = null;
  grid.addEventListener('pointerdown', e => {
    touched = e.pointerType !== 'mouse';
    down = touched ? [e.clientX, e.clientY] : null;
  });
  grid.addEventListener('pointerup', e => {
    if (down && Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) < TAP_SLOP) { last = undefined; point(e); }
    down = null;
  });
  grid.addEventListener('pointercancel', () => { down = null; });
  grid.addEventListener('mouseleave', () => { unpoint(); grid.classList.remove('af-click'); });
  grid.addEventListener('click', e => {
    const c = cellAt(e);
    if (c && opens(c)) send(`${data.channel}:day:${c.o}:${deck}`);
  });
  // a right-click on a day marks it as important (an exam, say: marks.py), or takes its mark
  // away: kept by the add-on, and drawn here at once (the forest itself is not drawn again)
  grid.addEventListener('contextmenu', e => {
    const c = cellAt(e);
    if (!c || !data.inAnki) return;  // (on the phone there is no add-on to keep the mark)
    e.preventDefault();
    if (!H.marked.delete(c.o)) H.marked.add(c.o);
    cal.marks = [...H.marked].map(o => iso(H.today + o * DAY_MS));  // (for a forest redrawn from this data)
    unpoint();
    draw();
    send(`${data.channel}:mark:${iso(c.ms)}`);
  });
};
})();

/* Memory Forest — the study heatmap's tiles: the scene it is drawn for, each day's tile and its
 * palette (paletteOf), the frames and rings round a day, the joined shapes (shapesPass) and the smooth
 * tiles drawn at the screen's own resolution (sharpen). */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { hashStr, hex, rgb, layer, mix, oklab, fromOklab } = AF.u;
const { SEEDLING } = AF.STAGE;
const { STATE, TILE, TOP, ROWS, PINE_PERCENT, FADE, TILE_VARIANTS, P, iso, DARK, EMPTY_ALPHA, EMPTY_ALPHA_LIGHT, blankOn, apart, hourOf, shades, toned } = Cal;

/* the scene the calendar is drawn for: the forest's own (`env`, its theme and the look its
 * environment gave the animals), or with no forest showing, one made from the data alone */
function sceneOf(data, env) {
  if (!env) {
    env = { mood: data.mood, data, W: 200, H: 100, u: 1, theme: AF.theme(data.mood, data.stats, data.events) };
    const spec = AF.envOf(env);
    try { if (spec.prepare) spec.prepare(env); } catch { /* only its look for the animals is wanted */ }
  }
  // the scenery's trees in plain light (no hour's tint, haze or rim), and what the hour does to its
  // colours (hourOf)
  return { theme: Object.assign({}, env.theme, { tint: null, tintAmt: 0, hzStep: 0, rim: null }), mood: env.mood, u: 1,
    layout: null, data: env.data, visitorTint: env.visitorTint, hour: hourOf(env.mood) };
}
function spriteOf(t, h, env) {
  try { return AF.pixel.sprite(t, h, 0, env); }
  catch { return AF.pixel.sprite(t, h, 0, Object.assign({}, env, { mood: Object.assign({}, env.mood, { special: 'natural' }) })); }
}
/* a missed day, a day ahead with nothing due, or one before your history, drawn empty: a faint
 * grey square (no edge of its own) that sits back on Anki's light and dark pages alike */
const EMPTY = `rgba(128, 128, 128, ${EMPTY_ALPHA})`, EMPTY_LIGHT = `rgba(128, 128, 128, ${EMPTY_ALPHA_LIGHT})`;  // (clearer on a light page, so the weeks hold together)
const FREE_MARK = 'rgba(128, 128, 128, 0.5)';  // a day with nothing due, outside any streak: a single pixel, darker grey
// a day a streak passed over (nothing due, or a day off) wears a ring in the heatmap's own colour: the
// first shade, from the faintest, this far (OKLab) from the empty grey it rings (the faintest on a dark
// page; on a light one, where it is nearly the grey, the second)
const REST_APART = 0.10;
const restShade = (pal, paper) => { const blank = blankOn(paper); let lv = 0; while (lv < 3 && apart(pal.grass[lv][0], blank) < REST_APART) lv++; return pal.grass[lv][0]; };
/* a 1px ring just inside a tile's face, its four corners left off, as the pixel tiles round theirs */
function restRing(g, x, y, F) { for (let i = 1; i < F - 1; i++) { g.fillRect(x + i, y, 1, 1); g.fillRect(x + i, y + F - 1, 1, 1); g.fillRect(x, y + i, 1, 1); g.fillRect(x + F - 1, y + i, 1, 1); } }
/* a day with no reviews at all (before the first): the empty grey as a film over the page; on a
 * picture (core.js AF.pageCards, .af-text-bands) the empty day's solid tile, as the empty days
 * after it have: the film was lost on the picture, the weeks before the first review gone */
const noReviews = paper => paper.solid ? rgb(blankOn(paper)) : paper.dark ? EMPTY : EMPTY_LIGHT;
function empty(g, x, y, fill = EMPTY, T = TILE) { g.fillStyle = fill; g.fillRect(x, y, T, T); }
// a drawn tile's face: the box of its pixels, [left, top, right, bottom] in it (Flat's 9 with its
// edge, a scenery's own tile 8, its gap in its last row and column), measured once a tile
const FACES = new WeakMap();
function faceOf(t) {
  let f = FACES.get(t);
  if (f) return f;
  let d;
  try { d = t.getContext('2d').getImageData(0, 0, t.width, t.height).data; } catch { return [0, 0, t.width, t.height]; }
  let x0 = t.width, y0 = t.height, x1 = 0, y1 = 0;
  for (let y = 0; y < t.height; y++) for (let x = 0; x < t.width; x++) {
    if (!d[(y * t.width + x) * 4 + 3]) continue;
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x + 1); y1 = Math.max(y1, y + 1);
  }
  f = x1 > x0 ? [x0, y0, x1, y1] : [0, 0, t.width, t.height];
  FACES.set(t, f);
  return f;
}
/* a tile's texture: two tones in 2x2 clusters and an edge, its four corners left off so it reads
 * soft and round at its size (2026-10-16: bevel, dither, a soft brush and an inset were tried; at
 * 1x only the corners showed). A scenery with a look of its own (Starry night's brushstrokes) draws
 * its tiles in it instead (its style's `draw(g, pal, edge, v, size)`: `pal` the shade and its darker
 * tone, `v` which of the TILE_VARIANTS) */
function plainTile(g, pal, edge, v, T) {
  // today's two-tone texture, its four corners left off, so a tile reads round at its size
  for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
    if ((x === 0 || x === T - 1) && (y === 0 || y === T - 1)) continue;
    const e = y === T - 1 || x === T - 1;
    g.fillStyle = rgb(e ? edge : pal[(hashStr(v + ',' + (x >> 1) + ',' + (y >> 1)) & 3) === 0 ? 1 : 0]);
    g.fillRect(x, y, 1, 1);
  }
}
/* a shade's tiles, each of its TILE_VARIANTS textures drawn once, kept for every calendar after */
const tiles = new Map();
function tilesOf(pal, edge, look, gapless = false) {
  const key = (look ? look.name : '') + (gapless ? '|whole' + STATE.CELL : '') + '|' + pal.concat([edge]).map(c => c.join(',')).join('|');
  if (!tiles.has(key)) {
    const out = [];
    for (let v = 0; v < TILE_VARIANTS; v++) {
      // (with no spaces between the days, a tile fills its whole cell: drawn a pixel bigger, so the
      // gap every tile style keeps in its last row and column falls outside it)
      const [cv, g] = layer(gapless ? STATE.CELL : TILE, gapless ? STATE.CELL : TILE);
      (look ? look.draw : plainTile)(g, pal, edge, v, gapless ? STATE.CELL + 1 : TILE);
      cv.fill = pal[0];  // (its colour, for Smooth: the rounded face filled, then its texture over it)
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
  // the Heatmap tab's look (heatmap_look.page_look): its tiles (`tile`, a style, web/heatmap/<key>.js:
  // a scenery's own among them loaded only while it is drawn); missing, or one this page lacks, plainTile's
  const L = H.look || {};
  const drawn = AF.heatmapTiles[L.tile];
  const dark = paper.dark, S = shades(sp, paper, L);
  // (a shape with spaces and smooth corners whose style gives a `smoothRadius` (its .json, in the look), Round: each day a
  // tile of its own, as round as its shape cut in pixels but its edge drawn at the screen's
  // resolution, antialiased, in Flat's one colour: under sharpen with that radius)
  const gapless = L.gaps === false, roundTile = !!(drawn && L.smoothRadius && L.smooth && !gapless);
  // (a style's `shaped`: its tiles of a shape of their own)
  const flat = { name: 'flat', draw: AF.heatmapTiles.flat.draw }, look = roundTile ? flat
    : drawn && drawn.draw ? { name: L.tile, draw: drawn.draw, shaped: !!drawn.shaped } : null;
  const shapes = isShape(L.tile) && !roundTile ? L.tile : null;
  // the soil faded into the page, so the days ahead sit behind the days you studied
  const fade = FADE, till = dark ? P.tillDark : P.till, edges = dark ? P.tillDarkEdge : P.tillEdge;
  // (on a light page in lightness only, keeping most of its colour: mixed with white, brown went grey-mauve)
  const bgL = oklab(paper.bg)[0], toPage = c => {
    if (dark) return mix(c, paper.bg, fade);
    const k = oklab(c);
    return fromOklab(k[0] + (bgL - k[0]) * fade, k[1] * (1 - 0.6 * fade), k[2] * (1 - 0.6 * fade));
  };
  const soil = lv => till[lv].map(toPage), soilEdge = lv => toPage(edges[lv]);
  // (more due stands out more, as more studied does: lighter on a dark page, darker on a light one)
  const dueLv = n => dark ? 3 - H.dueShade(n) : H.dueShade(n);
  // a day's shade: its two tones and edge, whether it is soil (a day ahead), and its texture (v)
  const shadeOf = c => {
    const v = hashStr(iso(c.ms)) % TILE_VARIANTS, soilOf = lv => ({ pal: soil(lv), edge: soilEdge(lv), soil: true, v, lv });
    // today before you study: soil, by the cards it has due, until your first review
    if (c.o === 0 && !c.n && H.dueToday) return soilOf(dueLv(H.dueToday));
    if (!c.n || c.o > H.ahead) return null;
    if (c.o > 0) return soilOf(dueLv(c.n));
    const lv = H.shade(c.o);
    return { pal: S.grass[lv], edge: S.edge[lv], soil: false, v, lv };
  };
  const tile = c => { const t = shadeOf(c); return t && tilesOf(t.pal, t.edge, look, gapless)[t.v]; };
  // (an empty day in a scenery's own tiles: the empty grey's flat square, the same tile over it at
  // half strength, its tone and edge darkened as a shade's are, so the weeks read as one medium and
  // each day keeps its square: at full strength, hatching's dropped pixels broke it up, and a ring
  // would read as a rest day's, 2026-10-19; Flat's are its plain squares)
  const blankPal = toned(blankOn(paper), dark), BLANK_TEXTURE = 0.5;
  // (a tile of a shape of its own, `shaped`: the grey only inside that shape, the same mix)
  const shaped = !!(look && look.shaped);
  const blankLook = look && { name: look.name + '|blank', draw: (g, p, e, v, T) => {
    if (shaped) {
      look.draw(g, p, e, v, T);
      g.globalCompositeOperation = 'source-atop'; g.globalAlpha = 1 - BLANK_TEXTURE;
      g.fillStyle = rgb(p[0]); g.fillRect(0, 0, T, T);
      g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1;
      return;
    }
    g.fillStyle = rgb(p[0]); g.fillRect(0, 0, T - 1, T - 1);
    g.globalAlpha = BLANK_TEXTURE; look.draw(g, p, e, v, T); g.globalAlpha = 1;
  } };
  const blankTile = c => look && look.name !== 'flat' ? tilesOf(blankPal[0], blankPal[1], blankLook, gapless)[hashStr(iso(c.ms)) % TILE_VARIANTS] : null;
  // (the key: the four shades of a day studied, in Flat's one colour for a shape, as Contours'
  // bands and Round's days are; the soil and the empty days say what they are; the hover's ring in
  // today's frame colours, which show on every shade, its inside clear, so the day and its mark
  // keep their colours)
  return { tile, blankTile, shadeOf, gapless, roundTile, shapes, shaped, grass: S.grass, edge: S.edge,
    // (for the shapes: the soil's four shades, the empty days' grey as one colour, and the page)
    tills: [0, 1, 2, 3].map(lv => soil(lv)[0]), blank: blankOn(paper), page: paper.bg,
    key: [0, 1, 2, 3].map(lv => tilesOf(S.grass[lv], S.edge[lv], shapes ? flat : look)[0]), ring: rgb(dark ? P.today : P.todayOnLight) };
}

// a seedling of its own day's kind (pine or broadleaf, and its look)
function seedlingOf(sp, ms) {
  const seed = hashStr('calendar|' + iso(ms));
  return spriteOf({ stage: SEEDLING, kind: seed % 100 < PINE_PERCENT ? 1 : 0, size: 0, health: 0, variant: seed % 7, seed, index: -1 }, 7, sp);
}
// a light frame round today's tile (dark on a light page), in the gaps all round it: on the page's
// colour, so it shows whatever the day's shade (on the tile's own edge, a busy day's dark tile hid it)
function frame(g, x, y, T, dark, bg) {
  g.fillStyle = rgb(dark ? P.today : P.todayOnLight);
  const tx = x - 1, ty = y - 1;
  g.fillRect(tx, ty, T + 2, 1); g.fillRect(tx, ty + T + 1, T + 2, 1); g.fillRect(tx, ty, 1, T + 2); g.fillRect(tx + T + 1, ty, 1, T + 2);
  // (and a line of the page's colour just inside it, so it never runs into a tile as dark as it is)
  g.fillStyle = rgb(bg);
  g.fillRect(x, y, T, 1); g.fillRect(x, y + T - 1, T, 1); g.fillRect(x, y, 1, T); g.fillRect(x + T - 1, y, 1, T);
}

/* a shaped day's outline: `inside(x, y)` says whether a heatmap pixel is the day's own (its tile's
 * painted pixels, or its pane); today's frame round it, a line of the page's colour on its own rim
 * and the light ring just outside it, and a rest day's ring on its rim, as the square ones are */
const MASKS = new WeakMap();
function maskOf(t) {
  let m = MASKS.get(t);
  if (m) return m;
  const d = t.getContext('2d').getImageData(0, 0, t.width, t.height).data;
  m = new Uint8Array(t.width * t.height);
  for (let i = 0; i < m.length; i++) m[i] = d[i * 4 + 3] ? 1 : 0;
  MASKS.set(t, m);
  return m;
}
const tileIn = (t, c) => { const m = maskOf(t); return (x, y) => { const lx = x - c.x, ly = y - c.y; return lx >= 0 && ly >= 0 && lx < t.width && ly < t.height && !!m[ly * t.width + lx]; }; };
const rimOf = (inside, x, y) => inside(x, y) && N4.some(([dx, dy]) => !inside(x + dx, y + dy));
function shapedFrame(g, inside, c, R, dark, bg) {
  for (let y = c.y - R; y < c.y + 2 * R; y++) for (let x = c.x - R; x < c.x + 2 * R; x++) {
    if (rimOf(inside, x, y)) { g.fillStyle = rgb(bg); g.fillRect(x, y, 1, 1); }
    else if (!inside(x, y) && DIAG.concat(N4).some(([dx, dy]) => inside(x + dx, y + dy))) { g.fillStyle = rgb(dark ? P.today : P.todayOnLight); g.fillRect(x, y, 1, 1); }
  }
}
function shapedRing(g, inside, c, R) {
  for (let y = c.y - R; y < c.y + 2 * R; y++) for (let x = c.x - R; x < c.x + 2 * R; x++) if (rimOf(inside, x, y)) g.fillRect(x, y, 1, 1);
}

/* The heatmap's tile styles (the Heatmap tab's Tiles), each in a file of its own: web/heatmap/<key>.js
 * (and .json, what the tab says of it), or for one still in the works, web/drafts/ (this copy only).
 * A scenery's own style (its .json's `env`, the scenery it comes with: Brush, Scanlines, the seasonal
 * ones; with `own`, one only that scenery wears, never offered) is not among the page's scripts
 * (catalog.SCRIPTS): the page loads its file only while the heatmap is drawn in it
 * (heatmap_look.page_look's `files`), and an edition without that scenery ships without it. A
 * scenery never draws tiles itself. A style registers itself in AF.heatmapTiles[key] as one of:
 *  - { draw(g, pal, edge, v, T), shaped }: each day a tile of its own, drawn as plainTile is (Flat;
 *    `shaped`, Lagoon water's round tiles: its empty days, today's frame and a rest day's ring follow
 *    its shape);
 *  - { fields, prepare(ctx), paint(ctx, c, x, y, edge, i, state) }: a joined shape (Round, Contours):
 *    the days of each field (`fields`: the days studied 'grass', the days ahead 'soil', the empty
 *    days 'blank') side by side are one shape, the gutters between them filled while there are no
 *    spaces between days, each shape's outer corners cut and inner corners filled in whole-pixel
 *    steps; `paint` gives each pixel's colour (`edge`: on the shape's rim; `prepare` any work
 *    first, its answer `state`). Shapes join where the days touch: across months in By year,
 *    while Timeline's months, each in columns of their own, stay apart (2026-10-14);
 *  - { pass(ctx) }: draws the days itself, and gives back each pixel's day (an Int32Array, -1
 *    none) for the pointer, or null.
 */
AF.heatmapTiles = AF.heatmapTiles || {};

const isShape = k => { const t = AF.heatmapTiles[k]; return !!t && !t.draw; };
const DIAG = [[-1, -1], [1, -1], [-1, 1], [1, 1]], N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const FIELD_SIGMA = 6, FIELD_REACH = 2;
/* the shade at a pixel of a day's field, 0 to 3, unrounded: the days round it of its own kind (studied,
 * or ahead) weighted by how near their tiles' centres are (a Gaussian about a day across) */
function fieldLv(c, x, y, get) {
  const t = c.shade;
  let sum = 0, w = 0;
  for (let dc = -FIELD_REACH; dc <= FIELD_REACH; dc++) for (let dr = -FIELD_REACH; dr <= FIELD_REACH; dr++) {
    const n = get(c.col + dc, c.row + dr);
    if (!n || !n.shade || n.shade.blank || !n.shade.soil !== !t.soil) continue;
    const dx = n.x + (TILE >> 1) - x, dy = n.y + (TILE >> 1) - y, k = Math.exp(-(dx * dx + dy * dy) / (2 * FIELD_SIGMA * FIELD_SIGMA));
    sum += n.shade.lv * k; w += k;
  }
  return Math.min(3, Math.max(0, w ? sum / w : t.lv));
}
// a shape's outline: the days ahead their own shade's edge, the days studied a pixel darker than the busiest's
const outlineOf = (t, pal, dark) => (t.soil ? mix(t.edge, DARK, dark ? 0.15 : 0.2) : mix(pal.edge[3], DARK, dark ? 0.45 : 0.35));
function shapesPass(g, cells, at, W, Hh, H, pal, dark) {
  const style = AF.heatmapTiles[pal.shapes], rows = ROWS;
  const get = (col, row) => (row >= 0 && row < rows ? at.get(col * ROWS + row) : undefined);
  const ctx = { g, cells, get, W, Hh, H, pal, rows, dark, TOP, CELL: STATE.CELL, TILE, FADE, DARK, layer, mix, hashStr, iso, fieldLv, outlineOf };
  if (style.pass) return { owner: style.pass(ctx), lvAt: null };
  // (a moving shape: drawn now at the moving styles' clock, or its first moment where it stays
  // still, and again each frame: AF.calendar's loop)
  if (style.live) { const L = style.live(ctx); L.draw(g, H.still ? 0 : STATE.liveClock); return { owner: L.owner, lvAt: null, live: L }; }
  const [cv, rg] = layer(W, Hh), img = rg.createImageData(W, Hh), d = img.data;
  // (each pixel's day and shade, for a hover's highlight: a month, a streak, or a shade of the key
  // lit by the shape's own pixels, not by squares across it; `level` a style's own, Contours' bands)
  const owner = new Int32Array(W * Hh).fill(-1), lvAt = new Int8Array(W * Hh).fill(-1);
  const kind = c => (!c || !c.shade ? '' : c.shade.blank ? 'blank' : c.shade.soil ? 'soil' : 'grass');
  for (const field of style.fields) {
    const isIn = c => kind(c) === field;
    // each pixel's day (-1 none): a day's tile, the gutter to a neighbour right or below that is
    // in too, and the corner between four
    const own = new Int32Array(W * Hh).fill(-1);
    const put = (x0, y0, w, h, i) => { for (let y = y0; y < y0 + h; y++) for (let x = x0; x < x0 + w; x++) own[y * W + x] = i; };
    cells.forEach((c, i) => {
      if (!isIn(c)) return;
      put(c.x, c.y, TILE, TILE, i);
      // (with spaces between the days, no day joins another: each its own little shape)
      if (!pal.gapless) return;
      const R = isIn(get(c.col + 1, c.row)), D = isIn(get(c.col, c.row + 1));
      if (R) put(c.x + TILE, c.y, STATE.CELL - TILE, TILE, i);
      if (D) put(c.x, c.y + TILE, TILE, STATE.CELL - TILE, i);
      if (R && D && isIn(get(c.col + 1, c.row + 1))) put(c.x + TILE, c.y + TILE, STATE.CELL - TILE, STATE.CELL - TILE, i);
    });
    // the corners, two pixels round: outer ones cut, inner ones filled
    const f = (x, y) => x >= 0 && y >= 0 && x < W && y < Hh && own[y * W + x] >= 0, out = own.slice();
    for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (f(x, y)) {
        for (const [dx, dy] of DIAG) if (!f(x + dx, y) && !f(x, y + dy)) {
          out[i] = -1;
          if (f(x - dx, y) && !f(x - dx, y + dy)) out[i - dx] = -1;
          if (f(x, y - dy) && !f(x + dx, y - dy)) out[i - dy * W] = -1;
        }
      } else {
        for (const [dx, dy] of DIAG) if (f(x + dx, y) && f(x, y + dy) && f(x + dx, y + dy)) {
          out[i] = own[i + dx];
          if (!f(x - dx, y) && f(x - dx, y + dy)) out[i - dx] = own[i - dx + dy * W];
          if (!f(x, y - dy) && f(x + dx, y - dy)) out[i - dy * W] = own[i + dx - dy * W];
        }
      }
    }
    // each pixel in its day's colour, as the style paints it (a day before the start date faded,
    // as its tile would be)
    const edgeAt = (x, y) => N4.some(([dx, dy]) => { const X = x + dx, Y = y + dy; return X < 0 || Y < 0 || X >= W || Y >= Hh || out[Y * W + X] < 0; });
    const state = style.prepare ? style.prepare(Object.assign({ out }, ctx)) : null;
    for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
      const o = out[y * W + x];
      if (o < 0) continue;
      const c = cells[o], k = (y * W + x) * 4;
      const col = style.paint(ctx, c, x, y, edgeAt(x, y), y * W + x, state);
      owner[y * W + x] = o;
      if (c.shade && !c.shade.blank && !c.shade.soil) lvAt[y * W + x] = style.level ? style.level(state, y * W + x) : c.shade.lv;
      d[k] = col[0]; d[k + 1] = col[1]; d[k + 2] = col[2];
      d[k + 3] = H.fs !== null && c.o < H.fs ? Math.round(255 * (1 - FADE)) : 255;
    }
  }
  rg.putImageData(img, 0, 0);
  g.drawImage(cv, 0, 0);
  return { owner, lvAt };
}

/* Smooth (the Heatmap tab's switch, `look.smooth`): each day's tile, in whichever style is chosen,
 * drawn inside a rounded square at the screen's own resolution, as GitHub's are (drawn in the
 * heatmap's own pixels and scaled up, corners step). The tiles, the empty days and today's frame are
 * drawn by sharpen once the scale is known; the marks, the free days' dots, the brackets and the
 * lane stay on the heatmap's pixels, over them. Not with the joined shapes (Contours, a drafted shape,
 * Round without spaces), which are no tiles. (The path by hand: Chromium 77, Anki 2.1.45's, has no
 * roundRect) */
const SMOOTH_R = 1.8;  // (the corners' radius, in the heatmap's pixels: GitHub's 2px on a 10px tile)
function rounded(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}
/* a view's tiles, empty days and today's frame drawn smooth on `hi`, `s` device pixels to the
 * heatmap's pixel, under `lo` (the rest of it, in its pixels) */
function sharpen(hi, lo, cells, H, dark, paper, s, F, R, G = 0) {
  const W = lo.width, Hh = lo.height;
  hi.width = Math.round(W * s); hi.height = Math.round(Hh * s);
  const g = hi.getContext('2d');
  g.setTransform(hi.width / W, 0, 0, hi.height / Hh, 0, 0);
  g.imageSmoothingEnabled = false;  // (a tile's own texture stays crisp inside its smooth outline)
  // (the rounded square is the tile's face, F: its last row and column are the gap between days,
  // which a style draws in its edge tone and which inside a smooth outline read as a stepped rim;
  // a style may grow it by G all round, its colour filling the rim, so the spaces between days are
  // narrower)
  const tile = (c, inset) => {
    const i = (inset || 0) - G;
    rounded(g, c.x + i, c.y + i, F - 2 * i, F - 2 * i, Math.max(0.6, R - i));
    if (c.t) {
      g.fillStyle = rgb(c.t.fill); g.fill();
      g.save(); g.clip(); g.drawImage(c.t, 0, 0, F, F, c.x, c.y, F, F); g.restore();
    } else { g.fillStyle = noReviews(paper); g.fill(); }
  };
  for (const c of cells) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    tile(c);
  }
  // (a rest day's ring, paint: the tile's own rounded outline in the heatmap's faint shade, the empty grey inside)
  for (const c of cells) if (c.rest) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    rounded(g, c.x - G, c.y - G, F + 2 * G, F + 2 * G, Math.max(0.6, R + G)); g.fillStyle = rgb(c.rest); g.fill();
    rounded(g, c.x + 1 - G, c.y + 1 - G, F + 2 * G - 2, F + 2 * G - 2, Math.max(0.6, R + G - 1)); g.fillStyle = rgb(blankOn(paper)); g.fill();
  }
  g.globalAlpha = 1;
  const today = cells.find(c => c.o === 0);
  if (today) {
    // (as frame: a light ring in the gaps all round, a line of the page's colour just inside it)
    rounded(g, today.x - 1 - G, today.y - 1 - G, F + 2 + 2 * G, F + 2 + 2 * G, R + 1 + G); g.fillStyle = rgb(dark ? P.today : P.todayOnLight); g.fill();
    rounded(g, today.x - G, today.y - G, F + 2 * G, F + 2 * G, R + G); g.fillStyle = rgb(paper.bg); g.fill();
    tile(today, 1);
  }
  g.drawImage(lo, 0, 0);
}

Object.assign(Cal, { sceneOf, FREE_MARK, restShade, restRing, noReviews, empty, faceOf, drawAnimal, paletteOf, seedlingOf, frame, tileIn, shapedFrame, shapedRing, DIAG, shapesPass, SMOOTH_R, sharpen });
})();

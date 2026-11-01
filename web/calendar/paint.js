/* Memory Forest — the study heatmap's canvas: one view's days painted, with its marks, brackets, trophies,
 * goal and animals; what follows time (a bracket, the goal) asks which way time runs. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { rgb, layer } = AF.u;
const { STATE, TILE, TOP, ROWS, BRACKET, SHOWN_STREAK, TROPHIES, markOf, GOALS, GOALS_RTL, GOAL_AT, GOAL_AT_RTL, GOAL_LINE, METALS_ON_LIGHT, FADE, TILE_FACE, P, FREE_MARK, restShade, restRing, noReviews, empty, faceOf, drawAnimal, paletteOf, seedlingOf, frame, tileIn, shapedFrame, shapedRing, columns, shapesPass, markPalOf, SMOOTH_R, sharpen, weeksWidth, dpr } = Cal;

/* one view drawn: the canvas, and where everything on it is */

function paint(H, win, sp, paper) {
  const dark = paper.dark, band = TOP;
  // the days in weeks, their first day on top; Timeline starts each month in a column of its own (By
  // year runs its months on in the same weeks)
  const cells = columns(H, win).map(([o, ms, col, row]) => ({ o, ms, n: H.n(o), col, row }));
  const W = weeksWidth(H, win, cells[cells.length - 1].col), Hh = band + ROWS * STATE.CELL + BRACKET;
  // right to left (AF.i18n.rtl), time runs the other way: each week's column counted from the right
  // end, so the first week stands at the right and today towards the left. From here on a column is
  // where a day stands on screen, whichever way: the tiles, the shapes joining their neighbours, the
  // pointer's day (`at`); only what follows time (a streak's bracket from its first day to its last,
  // the goal ahead) asks `rtl` again. Each tile, sprite and mark is drawn as it is, unmirrored
  const rtl = AF.i18n.rtl(), cols = (W - 1) / STATE.CELL;
  if (rtl) for (const c of cells) c.col = cols - 1 - c.col;
  const xOf = c => 1 + c.col * STATE.CELL, yOf = c => band + c.row * STATE.CELL + 1;
  const at = new Map();  // (each day by its column and row, for the pointer)
  for (const c of cells) { c.x = xOf(c); c.y = yOf(c); at.set(c.col * ROWS + c.row, c); }
  const [cv, g0] = layer(W, Hh);
  let g = g0;
  // the animals (and the forest's first seedling) on a layer of their own over it, shown while the
  // pointer is on the heatmap (forest.css): the forest's milestones, which the forest shows already
  const [above, ag] = layer(W, Hh);
  const pal = paletteOf(H, sp, paper), smooth = !!(H.look && H.look.smooth) && !pal.shapes;
  // the tiles first, each with a texture of its own day's (the same whichever page it is on); a
  // missed day, or one before your history, faint, so the view is never half bare
  for (const c of cells) {
    // (Round, Contours, a drafted shape: the days studied, and the days ahead, are drawn after,
    // as shapes: shapesPass; all but Rounded the empty days too)
    // (a style that draws the empty days too, as Contours does, gets them as shades of their own)
    const style = pal.shapes && AF.heatmapTiles[pal.shapes];
    if (style) c.shade = pal.shadeOf(c) || (!style.fields || style.fields.indexOf('blank') >= 0 ? { blank: true } : null);
    const t = pal.shapes ? null : pal.tile(c) || pal.blankTile(c);
    // (a day before the forest's start date, studied or not, dimmed)
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    // (its face, for a selection's lit square and the hover's ring to sit evenly round it)
    const T = pal.gapless ? STATE.CELL : TILE;
    c.face = smooth ? [0, 0, pal.gapless ? STATE.CELL : TILE_FACE, pal.gapless ? STATE.CELL : TILE_FACE] : t ? faceOf(t) : [0, 0, T, T];
    if (smooth) c.t = t;  // (drawn by sharpen)
    else if (t) g.drawImage(t, c.x, c.y);
    else if (!c.shade) empty(g, c.x, c.y, noReviews(paper), pal.gapless ? STATE.CELL : TILE);
    g.globalAlpha = 1;
  }
  // (a joined shape: each pixel's day and shade, for the highlight; a drafted one's days also for the pointer)
  const joined = pal.shapes ? shapesPass(g, cells, at, W, Hh, H, pal, dark) : null;
  const pane = joined && !joined.lvAt ? joined.owner : null;
  // (a moving shape: the days on the canvas's own layer, and all drawn over them from here on on a
  // layer of their own, laid over the days each time they move)
  const live = joined && joined.live, ov = live ? layer(W, Hh) : null;
  if (live) g = ov[1];
  // (a day with nothing due, or a day off: inside a streak, a hollow tile, a ring in the heatmap's
  // faint shade round the empty grey (restShade), so the day reads as a slot the streak passed
  // through, unfilled, never as studied, and the week does not read as a gap; a single pixel was
  // too faint to see and a gold block read as a highlight, 2026-10-17. Not on today, whose frame
  // says it; outside any streak that pixel; over the shapes. Smooth tiles draw theirs in sharpen)
  const rest = restShade(pal, paper), face = pal.gapless ? STATE.CELL : TILE_FACE;
  // (a day's own shape: a shaped tile's painted pixels, or a drawn shape's pane)
  const index = new Map(cells.map((c, i) => [c, i]));
  const shapeIn = c => {
    if (pane) { const i = index.get(c); return (x, y) => x >= 0 && y >= 0 && x < W && y < Hh && pane[y * W + x] === i; }
    if (!pal.shaped || smooth) return null;
    const t = pal.tile(c) || pal.blankTile(c);
    return t ? tileIn(t, c) : null;
  };
  for (const c of cells) if (H.free.has(c.o) && !c.n) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    const run = c.o < 0 ? H.runOf(c.o) : null, mid = TILE >> 1;
    if (run && smooth) c.rest = rest;
    else if (run) { g.fillStyle = rgb(rest); const inside = shapeIn(c); if (inside) shapedRing(g, inside, c, STATE.CELL); else restRing(g, c.x, c.y, face); }
    else if (c.o !== 0) { g.fillStyle = FREE_MARK; g.fillRect(c.x + mid, c.y + mid, 1, 1); }
    g.globalAlpha = 1;
  }
  const animals = H.animals;
  const marks = [];  // (where the marks over the weeks stand, for the pointer)
  // the days you marked: each its icon, painted on its tile, centred on what shows of it, the day's shade round it
  // (important enough to sit on the data; its tooltip gives the day's count)
  for (const c of cells) {
    if (!H.marked.has(c.o)) continue;
    const spr = markOf(H.marked.get(c.o)).spr, rows = spr.frames[0];
    const x0 = c.x + Math.floor((TILE_FACE - rows[0].length) / 2), y0 = c.y + Math.floor((TILE_FACE - rows.length) / 2);
    // (cut out of the tile by a line of the page's colour, as the animals are: red on Lanterns' or
    // Cherry blossom's tiles was lost)
    drawAnimal(g, Object.assign({}, spr, { pal: markPalOf(sp, H.look) }), x0, y0, null, paper.bg);
  }
  const today = cells.find(c => c.o === 0);
  const todayIn = today && !smooth ? shapeIn(today) : null;
  if (todayIn) shapedFrame(g, todayIn, today, STATE.CELL, dark, paper.bg);
  else if (today && !smooth) frame(g, today.x, today.y, TILE, dark, paper.bg);
  // the streaks: a bracket under the weeks each ran through, gold for the current one, cut at
  // the view's edges (with no end mark there)
  const by = band + ROWS * STATE.CELL + 3, brackets = [];
  for (const r of H.runs) {
    const len = r.days, live = r === H.current;
    if (len < SHOWN_STREAK && !live) continue;
    const fo = Math.max(r.from, win.from), to = Math.min(r.to, win.to);
    if (fo > to) continue;
    const a = cells[fo - win.from], b = cells[to - win.from];
    // (x0 its left end, x1 its right: right to left, its first day's at the right, as drawn mirrored)
    const x0 = rtl ? b.x : a.x + (fo === r.from ? 1 : 0), x1 = rtl ? a.x + TILE - 2 - (fo === r.from ? 1 : 0) : b.x + TILE - 2;
    g.fillStyle = rgb(live ? (dark ? P.gold : P.goldOnLight) : P.past);
    g.fillRect(x0, by, x1 - x0 + 1, 1);
    if (fo === r.from) g.fillRect(rtl ? x1 : x0, by - 2, 1, 2);
    if (to === r.to) g.fillRect(rtl ? x0 : x1, by - 2, 1, 2);
    // dotted under a week the streak passed over with nothing due (an old deck's quiet weeks)
    const weeks = new Map();
    for (let o = fo; o <= to; o++) { const c = cells[o - win.from]; weeks.set(c.col, (weeks.get(c.col) !== false) && !c.n); }
    for (const [col, off] of weeks) {
      if (!off) continue;
      const wx0 = Math.max(x0, col * STATE.CELL), wx1 = Math.min(x1, col * STATE.CELL + STATE.CELL - 1);
      g.clearRect(wx0, by, wx1 - wx0 + 1, 1);
      for (let x = wx0; x <= wx1; x += 2) g.fillRect(x, by, 1, 1);
    }
    brackets.push({ x0, x1, len, live, run: r, cut: fo > r.from });
  }
  // the streak lane: a trophy under the last day of each of your longest streaks and the goal
  // pennant under its day, below the brackets, and a dotted gold line from today on to the goal
  // (all the streak's marks together, none cutting through the weeks). On the layer shown while
  // you hover the heatmap, as the animals are (2026-10-16): the streak's own line stays in view,
  // the trophies and the goal, the gamey part, come with the pointer
  if (H.goal && H.current && H.current.to >= win.from && H.current.to <= win.to) {
    const a = cells[H.current.to - win.from], gc = H.goal.o <= win.to ? cells[H.goal.o - win.from] : cells[cells.length - 1];
    ag.fillStyle = dark ? rgb(P.gold, GOAL_LINE) : rgb(P.goldOnLight);
    // (right to left: from today's tile leftwards, the pole on the goal day's middle as mirrored)
    if (rtl) for (let x = a.x - 2; x >= gc.x + GOAL_AT_RTL; x -= 2) ag.fillRect(x, by, 1, 1);
    else for (let x = a.x + TILE; x <= gc.x + GOAL_AT; x += 2) ag.fillRect(x, by, 1, 1);
    if (H.goal.o <= win.to) ag.fillRect(gc.x + (rtl ? GOAL_AT_RTL : GOAL_AT), by - 2, 1, 2);
  }
  const lane = [];
  for (const [run, i] of H.podium) lane.push([run.to, TROPHIES[i]]);
  // (right to left, the pennant flies the other way, towards the days ahead, its pole at its right)
  if (H.goal) lane.push([H.goal.o, (rtl ? GOALS_RTL : GOALS)[H.goal.rank]]);
  for (const [o, spr] of lane) {
    if (o < win.from || o > win.to) continue;
    // (the goal's pole on the day's middle, under the dotted line's end; a trophy centred)
    const c = cells[o - win.from], w = spr.frames[0][0].length, y0 = by + 3;
    const x0 = c.x + (GOALS.includes(spr) ? GOAL_AT : GOALS_RTL.includes(spr) ? GOAL_AT_RTL - (w - 1) : Math.floor((TILE - w) / 2));
    // (on a light page in their deeper shades: pale gold and silver would fade into it)
    const metal = !dark && METALS_ON_LIGHT[spr.pal.G];
    drawAnimal(ag, metal ? Object.assign({}, spr, { pal: Object.assign({}, spr.pal, metal) }) : spr, x0, y0, null, paper.bg);
    marks.push({ x0, x1: x0 + w, y0, y1: y0 + spr.frames[0].length, c, trophy: TROPHIES.indexOf(spr) });
  }
  // on the layer shown while you hover the heatmap, each on its own day's tile: the animals, each
  // where it came (the first, where two came on one day; the tooltip names them all), and the
  // seedling of the day the forest began with a start date (the one mark the start date leaves
  // here, besides the animals coming only after it). A day you marked keeps its mark in view.
  for (const c of cells) {
    if (H.marked.has(c.o)) continue;
    const a = (animals.get(c.o) || [])[0], spr = a && (a.spr || (AF.visitorSprite ? AF.visitorSprite(sp, a.key) : AF.VISITOR_SPRITES && AF.VISITOR_SPRITES[a.key]));
    if (spr) {
      const rows = spr.frames[0];
      drawAnimal(ag, spr, c.x + Math.floor((TILE - rows[0].length) / 2), c.y + Math.floor((TILE - rows.length) / 2), sp.visitorTint, paper.bg);
    } else if (c.o === H.fs) {
      const s = seedlingOf(sp, c.ms);
      ag.drawImage(s, c.x + Math.floor((TILE - s.width) / 2), c.y + Math.floor((TILE - s.height) / 2));
    }
  }
  const radius = pal.roundTile ? H.look.smoothRadius : SMOOTH_R;  // (smooth: each tile's corners)
  const out = { cv, above, W, Hh, cells, at, pane, joined, brackets, band, marks, ring: pal.ring, key: pal.key, smooth, radius };
  if (live) {
    g0.drawImage(ov[0], 0, 0);
    // (each frame: the days drawn whole over the last frame's - a moving style fills its every pixel - and the rest over them)
    let was = null;
    out.tick = t => { if (t === was) return; was = t; live.draw(g0, t); g0.drawImage(ov[0], 0, 0); };
  }
  if (smooth) {
    // (shown on a canvas of its own at the screen's resolution, drawn again when the scale changes)
    const [hi] = layer(W, Hh);
    hi.dataset.pixels = W;  // (the heatmap's width in its own pixels, for e2e/phone_check)
    let drawnAt = 0;
    const F = pal.gapless ? STATE.CELL : TILE_FACE;  // (each tile's face: no gap of its own when the days have none)
    const grow = pal.roundTile && !pal.gapless ? H.look.smoothGrow || 0 : 0;
    out.cv = hi; out.sharpen = s => { if (s !== drawnAt) { drawnAt = s; sharpen(hi, cv, cells, H, dark, paper, s, F, radius, grow); } };
    out.sharpen(dpr());
  }
  return out;
}

Object.assign(Cal, { paint });
})();

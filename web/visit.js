/* Memory Forest — zooming in among the trees, the way you would walk into a real forest. The
 * zoom button on the forest turns it on; then the wheel (two fingers on a phone) walks in,
 * about the spot it points at, and every tree you pass is behind you: the old trees at the
 * back stand close up, each smaller the further back it stands. A drag walks along the rows
 * (sideways) or deeper in and back out (up and down), as do the arrow keys. A click selects
 * a tree, and the bar under the forest shows its day and steps to the day before or after; it
 * leads back out too (as do Esc and the mouse's back button). The scene runner (core.js)
 * builds the scene from AF.visitLayout's items, which AF.place hands to AF.visitPlace. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { esc, fmtDate, cap, clamp } = AF.u;
const { HORIZON, GROUND_BOTTOM, ROWS_TOP, SLOT_MARGIN, SLOT_SPAN, FAR_SCALE, NEAR_GAIN, DIM_HAZE } = AF.GEOM;

// The camera stands CAM in front of the depth it looks at, and each row behind that is ROW_D
// further away, so a tree DD rows back is drawn at rel = CAM / (CAM + DD * ROW_D) of the scale S
// a tree at that depth has, and stands rel of the way down from the horizon to the scene's foot.
// The forest is drawn squeezed on the deck list; up close it is spread SPREAD times wider, so
// the trees beside each other stand apart. At the forest's edge the camera sees the forest
// just as the whole forest's view does (see visitLens); over the first LENS_ROWS rows
// walked in it comes to see it as from among the trees.
const CAM = 1, ROW_D = 0.42, SPREAD = 4.2, S = 2.4, LENS_ROWS = 3;
// a tree this far off centre (a share of the width) is out of sight; one nearer than the depth
// looked at fades as the camera walks past it, gone PASS_ROWS rows on
const SIDE = 0.8, PASS_ROWS = 0.2;
// the camera sees this much of the way back to itself (times CAM) behind the depth it looks at
const BEHIND_MOST = 0.8;
// the deep forest's trees are drawn one by one this many rows ahead at most, fading in over the
// last SIGHT_FADE of them; its bands fade out as the camera walks in, gone as its first trees
// come into sight (at least a row in)
const BEHIND_SIGHT = 14, SIGHT_FADE = 2;
// zooming in from the whole forest: the camera starts START_ROWS in front of the front row and
// eases from the whole forest's view into its own (the same but for the haze) over BLEND_ROWS
const START_ROWS = 0.6, BLEND_ROWS = 0.1;
// the haze deepens this much a row back, up to this much; a faded tree on a deck screen
// (it.dim) stays as faded as it is there (DIM_HAZE)
const HAZE_PER_ROW = 0.07, MAX_HAZE = 0.85;
// the fade between one view and the next, in ms
const FADE_MS = 180;
const ease = k => k * k * (3 - 2 * k), lerp = (a, b, k) => a + (b - a) * k;
// a slot (as the camera counts them, `per` to a row) at the share `f` across the whole forest's
// view; how wide one is on the canvas (a share of it), dd rows past the depth looked at
const slotOf = (f, per) => (f - SLOT_MARGIN) / SLOT_SPAN * per, slotWidth = (lens, per, dd) => SLOT_SPAN / per * sight(lens, dd).w;

/* where zooming in from the whole forest starts: in front of its front row */
const visitStart = base => Math.max(...base.items.filter(it => !it.pond).map(it => it.row + it.jy)) + START_ROWS;
/* How the camera at depth z sees (see sight()). At the forest's edge it sees just what the
 * whole forest's view shows: the back row FAR_SCALE of the front row's size, the rows from the
 * top of the ground (ROWS_TOP) down to its foot, and as wide as there (`edge`: its rows'
 * spacing, scale, and how far down a row at each rel stands, gA + gB * rel); then over
 * LENS_ROWS it comes, k of the way, to see as from among the trees. */
function visitLens(base, z) {
  const start = visitStart(base), back = Math.min(...base.items.filter(it => !it.pond).map(it => it.row + it.jy));
  const deep = Math.max(1 + START_ROWS, start - back);  // (a lone row stands one row deep)
  const rowD = (1 / FAR_SCALE - 1) / (deep - START_ROWS / FAR_SCALE), front = CAM / (CAM + START_ROWS * rowD);
  const gB = (1 - ROWS_TOP / (GROUND_BOTTOM - HORIZON)) / (front * (1 - FAR_SCALE));
  return { k: ease(clamp((start - z) / LENS_ROWS, 0, 1)), edge: { rowD, S: base.zoom / front, gA: 1 - gB * front, gB } };
}
/* How the camera sees the ground dd rows past the depth it looks at (behind it, if less than
 * 0): `g`, how far down from the horizon to the scene's foot it is; `w`, how many times the
 * whole forest's view wide a slot there is; `s`, the scale of a tree standing there. */
function sight(lens, dd) {
  const e = lens.edge, k = lens.k;
  const near = CAM / (CAM + Math.max(dd, -BEHIND_MOST * CAM / e.rowD) * e.rowD), rel = CAM / (CAM + Math.max(dd, -BEHIND_MOST * CAM / ROW_D) * ROW_D);
  return { g: lerp(e.gA + e.gB * near, rel, k), w: lerp(1, SPREAD * S * rel, k), s: lerp(e.S * near, S * rel, k) };
}
/* how many rows past the depth looked at the ground `g` down from the horizon is (see sight());
 * null if it is further than the camera sees */
function ddAt(lens, g) {
  let lo = -BEHIND_MOST * CAM / Math.max(ROW_D, lens.edge.rowD), hi = 200;
  if (g <= sight(lens, hi).g) return null;
  for (let i = 0; i < 40; i++) { const mid = (lo + hi) / 2; if (sight(lens, mid).g > g) lo = mid; else hi = mid; }
  return (lo + hi) / 2;
}

/* The layout as camera `cam` sees it, with the deep forest's trees (`behind`, see
 * AF.layoutBehind) in the rows behind once it is in among them; `deepAlpha`, how much of the
 * deep forest's bands still shows. `xOf(it)`: where a tree stands across the forest (a share
 * of it), the landscape's squeeze of the rows (a river's banks, say) included. */
AF.visitLayout = function (base, cam, xOf = it => it.x, behind = []) {
  const per = base.perRow + 0.5, b = ease(cam.b), items = [], lens = visitLens(base, cam.z);
  const deep = cam.b >= 1 ? behind : [];
  for (const it of deep.length ? base.items.concat(deep) : base.items) {
    const dd = cam.z - (it.row + it.jy);
    if (it.behind && dd > BEHIND_SIGHT) continue;  // further than the camera draws one by one
    // a pond stays until the camera has walked over its near shore
    if (dd <= (it.pond ? -AF.POND.ROWS * (1 - AF.POND.BACK) : -PASS_ROWS)) continue;
    const sg = sight(lens, Math.max(0, dd)), slotW = SLOT_SPAN / per * sg.w, dx = (xOf(it) * per - cam.x) * slotW;
    if (b >= 1 && Math.abs(dx) > SIDE + (it.pond ? it.slots * slotW : 0)) continue;  // (while it eases, every tree is on its way somewhere)
    const alpha = (dd < 0 ? 1 + dd / PASS_ROWS : 1) * (it.behind ? Math.min(1, (BEHIND_SIGHT - dd) / SIGHT_FADE) : 1);
    items.push(Object.assign({}, it, { view: { dx, g: sg.g, dd: Math.max(0, dd), at: dd, s: sg.s, b, alpha, slotW } }));
  }
  let deepAlpha = 1;
  if (deep.length) {
    const start = visitStart(base), newest = deep[deep.length - 1], fadeRows = Math.max(1, start - (newest.row + newest.jy) - BEHIND_SIGHT);
    deepAlpha = 1 - ease(clamp((start - cam.z) / fadeRows, 0, 1));
  }
  return Object.assign({}, base, { items, zoom: lerp(base.zoom, 1, b), flatZoom: base.zoom, visiting: b >= 1, cam, lens, deepAlpha });
};

/* Where a spot of the whole forest's view (`x`, `y`, as there) stands as the camera sees it:
 * its `x`, `y`, and `k` how much bigger something standing there is drawn; null if the camera
 * has walked past it. Unchanged outside a visit. For what is placed by the scene's own
 * measure rather than by a tree: the animals along the front, the cabin, a crater. */
AF.visitProject = function (env, x, y) {
  const L = env.layout, cam = L.cam;
  if (!cam) return { x, y, k: 1 };
  const { W, H } = env, lens = L.lens, per = L.perRow + 0.5, b = ease(cam.b);
  const hor = H * HORIZON, top = hor + H * ROWS_TOP, bot = H * (env.bot || GROUND_BOTTOM);
  // what stands below the front row (the animals along the front) stays that far in front of it
  const below = Math.max(0, y - bot), dep = Math.pow(clamp((y - top) / (bot - top), 0, 1), 1 / 1.1), dd = cam.z - dep * Math.max(1, L.rows - 1);
  if (dd <= -PASS_ROWS && b >= 1) return null;
  const sg = sight(lens, Math.max(0, dd)), slotW = SLOT_SPAN / per * sg.w, k = sg.s / ((FAR_SCALE + NEAR_GAIN * dep) * (L.flatZoom || 1));
  const near = { x: W / 2 + (slotOf(x / W, per) - cam.x) * slotW * W, y: hor + (bot - hor) * sg.g + below * k, k };
  return { x: lerp(x, near.x, b), y: lerp(y, near.y, b), k: lerp(1, near.k, b) };
};
/* The ground on row y of the scene as the camera sees it (null above the horizon, or outside a
 * visit): `yFlat`, the row of the whole forest's view that is; `toX(x)`, where a spot that far
 * across the whole forest's view (a share of the width) is on this row; `perW`, how many pixels
 * here one share of the whole width is; and `b`, how far the view has eased in. For what lies
 * on the ground by the scene's own measure: a river's channel. */
AF.visitGroundAt = function (env, y) {
  const L = env.layout, cam = L.cam;
  if (!cam) return null;
  const { W, H } = env, lens = L.lens, per = L.perRow + 0.5, hor = H * HORIZON, bot = H * (env.bot || GROUND_BOTTOM);
  const dd = y > hor ? ddAt(lens, (y - hor) / (bot - hor)) : null;
  if (dd == null) return null;
  const dep = (cam.z - dd) / Math.max(1, L.rows - 1), top = hor + H * ROWS_TOP;
  const slotW = slotWidth(lens, per, dd);
  // (beyond the back row, the ground of the back row's: what lies on it runs on straight)
  return { yFlat: top + (bot - top) * Math.pow(Math.max(0, dep), 1.1), perW: per / SLOT_SPAN * slotW * W, b: ease(cam.b),
    toX: x => W / 2 + (slotOf(x, per) - cam.x) * slotW * W };
};
/* how many times bigger a sprite of a few pixels (an animal, a crow, a flower) is drawn: a
 * whole number, so its pixels stay square; 1 outside a visit (by tree p, or by its scale k) */
AF.visitK = (p, k = p && p.it && p.it.view ? p.s : 1) => Math.max(1, Math.round(k));
/* draw(), k times bigger about (ax, ay): what it draws at (ax, ay) stays there */
AF.scaledAt = function (g, k, ax, ay, draw) {
  if (k <= 1) return draw();
  ax = Math.round(ax); ay = Math.round(ay);
  g.save(); g.translate(ax - ax * k, ay - ay * k); g.scale(k, k);
  try { return draw(); } finally { g.restore(); }
};

/* Where a pond's water lies up close: its slots wide, POND_ROWS rows deep on the ground (from
 * POND_BACK of that behind its row), each edge as far off as it stands; a near shore the camera
 * has walked onto runs out under the scene's foot. */
AF.visitPondBox = function (env, p) {
  const v = p.it.view, { W, H } = env, hor = H * HORIZON, bot = H * (env.bot || GROUND_BOTTOM);
  const lens = env.layout.lens, groundY = d => hor + (bot - hor) * sight(lens, d).g;
  const back = groundY(v.at + AF.POND.ROWS * AF.POND.BACK), front = Math.min(H + 2, groundY(v.at - AF.POND.ROWS * (1 - AF.POND.BACK)));
  const w = p.it.slots * v.slotW * W * AF.POND.OVERHANG, cx = W / 2 + (v.dx + (p.it.slots - 1) / 2 * v.slotW) * W, h = Math.max(2, front - back);
  return { cx, cy: back + h / 2, w, h, x0: cx - w / 2, x1: cx + w / 2, y0: back, y1: back + h };
};

/* where a visited forest's tree stands (AF.place hands these here) */
AF.visitPlace = function (it, W, H, env) {
  const v = it.view, hor = H * HORIZON, bot = H * (env.bot || GROUND_BOTTOM);
  const near = { x: W / 2 + v.dx * W, y: hor + (bot - hor) * v.g, s: v.s, hz: it.dim ? DIM_HAZE : Math.min(MAX_HAZE, v.dd * HAZE_PER_ROW) };
  if (v.b >= 1) return near;
  const far = AF.placeFlat(it, W, H, env);  // easing out of the whole forest's view
  return { x: lerp(far.x, near.x, v.b), y: lerp(far.y, near.y, v.b), s: lerp(far.s, near.s, v.b), hz: lerp(far.hz, near.hz, v.b) };
};

/* An environment that draws the forest somewhere else entirely (a room's window) says `noVisit`. */
AF.canVisit = env => !AF.envOf(env).noVisit;

/* the little arrow over the tree picked (the hover marker's shape, a size up) */
AF.drawVisitMarker = function (g, env, index) {
  const p = env.placed.find(q => !q.it.pond && q.it.index === index);
  if (!p) return;
  const h = AF.STAGE_H[p.it.stage] * env.u * p.s, x = Math.round(p.x), y = Math.max(2, Math.round(p.y - h - 5));
  g.fillStyle = 'rgba(20,20,20,.7)'; g.fillRect(x - 4, y - 1, 9, 1);
  g.fillStyle = '#fff8e0';
  for (let r = 0; r < 4; r++) g.fillRect(x - (3 - r), y + r, 7 - 2 * r, 1);
};

// a press that moves this far (CSS pixels) is a drag, not a click, and keeps to the way it
// first went (along the rows, or in and out); a drag the canvas's height walks WALK_ROWS rows,
// a wheel's notch (~100) WHEEL_ROWS * 100 (a trackpad's pinch, a wheel with ctrl, PINCH_GAIN
// times that), and two fingers spread to twice as far apart PINCH_ROWS
const DRAG_PX = 4, WALK_ROWS = 3, WHEEL_ROWS = 0.004, PINCH_GAIN = 8, PINCH_ROWS = 2.5;
// a finger's second tap within DOUBLE_MS of the first, DOUBLE_PX from it, zooms DOUBLE_ROWS in
// (a little less than half a pinch to twice as far apart), over DOUBLE_GLIDE_MS
const DOUBLE_MS = 300, DOUBLE_PX = 30, DOUBLE_ROWS = 1, DOUBLE_GLIDE_MS = 220;
// the bar's way to the day before or after the tree selected: the camera glides there in GLIDE_MS
// (on the phone's full screen, just the arrows: there's no room for more)
const DAYS = [['prev', '‹ Previous day', '‹', 'The tree of the day before'], ['next', 'Next day ›', '›', 'The tree of the day after']];
// the arrow keys walk: ↑ and ↓ KEY_ROWS in and out (a wheel's notch), ← and → KEY_SHARE of the
// canvas's width along the rows (a key held down goes on)
const KEY_ROWS = 0.4, KEY_SHARE = 0.1;
const KEYS = { ArrowUp: [0, 1], ArrowDown: [0, -1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
const BACK = 'Back to the whole forest';
const GLIDE_MS = 420;
// A drag past the forest's end (the rows' ends, the back row) gives, ever more stiffly, up to
// BAND_SHARE of the canvas's width along the rows or BAND_ROWS deeper in, and springs back in
// SETTLE_MS when let go.
const BAND_SHARE = 0.18, BAND_ROWS = 0.8, SETTLE_MS = 320;
// the camera goes along the rows only so far that the forest's end (its nearest row) stays
// this share of the canvas's width in from its side
const END_GAP = 0.125;
// how far a drag `d` past the end goes, giving at most `most`
const band = (d, most) => most * (1 - 1 / (d / most + 1));
const MOVE_MS = 16;  // moves this close together are drawn as one
// the camera goes no further back than this in front of the back row, which stays in sight
const EDGE_ROWS = 0.3;
const BACK_BUTTON = 3;  // a mouse's back button
// the zoom button: two corners of a frame opening out, in a ring
const ZOOM_ICON = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="square" aria-hidden="true">'
  + '<path d="M8.5 3.5h4v4M3.5 8.5v4h4"/></svg>';

/* Wire zooming up for one mounted forest. It is off until the zoom button on the forest turns
 * it on (a wheel or a finger over the forest scrolls the page, as ever); then the wheel and two
 * fingers zoom in among the trees, about the spot they point at, a drag walks about, and the
 * bar under the forest says so and leads back out. A click on a tree selects it: the bar
 * shows its day and steps to the day before or after (a click on it again opens its cards, as
 * one on any tree does with zooming off); turned on (or about to be, the pointer on its
 * button), it asks Anki for the deep forest's trees, to walk on in among them. `go(cam,
 * behind)` rebuilds the scene as camera `cam` sees it (null: the whole forest); `current()`
 * says whether this forest is still the one on the page; `xOf(it)`, where a tree stands
 * across the forest; `warm()`, turned on, gets the trees ready to be drawn up close. Returns
 * `on`, `picked` (the tree selected, or null), pick(index), `state` (the view as it is) and
 * resume(state), which takes the view back there at once (the phone's forest, drawn afresh).
 * `always`: zooming is simply on, with no button to turn it on or off and nothing that leads
 * back out but zooming out (the phone's full screen, where the forest is all there is). */
AF.visits = function ({ root, data, base, animate, current, go, xOf, warm, always }) {
  const bar = root.querySelector('.af-visit'), caption = root.querySelector('.af-caption'), canvas = root.querySelector('canvas'), scene = canvas.parentNode;
  const words = AF.WORDS, per = base.perRow + 0.5, trees = base.items.filter(it => !it.pond);
  // where zooming in starts (in front of the front row), and the furthest back it goes; the
  // camera where the whole forest's view is centred, blended `b` of the way into its own
  const start = visitStart(base), backOf = list => Math.max(...list.filter(it => it.row === list[0].row).map(it => it.row + it.jy)) + EDGE_ROWS;
  const home = b => ({ x: slotOf(0.5, per), z: start, b });
  let furthest = backOf(trees);
  // the deep forest's trees, once Anki has sent them (and every tree, to step through the days)
  let behind = [], every = trees, asked = false;
  function askDeep() {
    if (asked || !data.merged || !data.channel || typeof window.pycmd !== 'function') return;  // (the phone has no Anki to ask)
    asked = true;
    const m = data.merged;
    window.pycmd(`${data.channel}:deep:${data.deckId == null ? '' : data.deckId}`, got => {
      if (!current()) return;
      // only the trees of the deep forest drawn here: Anki may have built the forest afresh
      // since (or sent nothing); asked again the next time, rather than never
      if (!Array.isArray(got) || !got.length || got.length !== m.count || got[0].ago !== m.from_ago || got[got.length - 1].ago !== m.to_ago) {
        asked = false;
        return;
      }
      behind = AF.layoutBehind(got, base); every = behind.concat(trees); furthest = backOf(behind);
      shown = undefined;  // (the bar's Previous day may lead somewhere now)
      if (cam) redraw(); else show();
    });
  }
  const touch = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'af-zoom'; button.innerHTML = ZOOM_ICON;
  if (!always) scene.appendChild(button);
  let on = !!always, cam = null, picked = null, fading = 0, gliding = 0, shown;
  // the tree of the day before ('prev') or after ('next') tree `index`'s, if there is one
  function day(index, dir) {
    const t = every.find(it => it.index === index);
    let best = null;
    for (const it of every) {
      if (dir === 'next' ? it.ago < t.ago && (!best || it.ago > best.ago) : it.ago > t.ago && (!best || it.ago < best.ago)) best = it;
    }
    return best;
  }
  function show() {
    caption.hidden = on; bar.hidden = !on;
    root.classList.toggle('af-visiting', on);
    button.classList.toggle('af-zoom-on', on);
    button.setAttribute('aria-pressed', on ? 'true' : 'false');
    button.title = on ? BACK : 'Zoom in among the trees';
    button.setAttribute('aria-label', button.title);
    const now = on ? picked : undefined;
    if (shown === now) return;
    shown = now;
    if (!on) { bar.innerHTML = ''; return; }
    const back = always ? '' : `<button type="button" class="af-visit-btn" data-act="back">${BACK}</button>`;
    if (picked == null) {
      bar.innerHTML = `<span class="af-visit-about">${touch ? 'Pinch or double tap' : 'Scroll or press ↑ ↓'} to zoom, drag${touch ? '' : ' or press ← →'} to walk around, ${touch ? 'tap' : 'click'} a ${esc(words.one)} to select it</span><span class="af-visit-acts">${back}</span>`;
      return;
    }
    // as its tooltip says it (web/tooltips.js)
    const t = every.find(it => it.index === picked), about = [cap(words.stages[t.stage]), `${t.n.toLocaleString('en')} card${t.n === 1 ? '' : 's'}`];
    if (t.stage >= AF.STAGE.YOUNG && t.remembered != null && !(t.suspended && t.suspended >= t.n)) {
      about.push(t.measured === false ? `${Math.round(t.remembered * 100)}% still going well` : `~${Math.round(t.remembered * 100)}% remembered`);
    }
    bar.innerHTML = `<span class="af-visit-about"><b>${esc(cap(words.planted))} ${esc(fmtDate(t.date))}</b> · ${esc(about.join(' · '))}</span><span class="af-visit-acts">`
      + DAYS.map(([dir, label, arrow, tip]) => `<button type="button" class="af-visit-btn" data-day="${dir}" title="${tip}" aria-label="${tip}"${day(picked, dir) ? '' : ' disabled'}>${always ? arrow : label}</button>`).join('')
      + back + '</span>';
  }
  show();
  if (always) warm();
  function enter() {
    if (!current() || on) return;
    on = true;
    clearTimeout(fading); canvas.style.opacity = '';  // (left a moment ago, and still fading out)
    show(); askDeep(); warm();
  }
  // off: back to the whole forest (fading across)
  function leave() {
    if (!current() || !on || always) return;
    on = false; picked = null;
    clearTimeout(fading); clearTimeout(gliding);
    const swap = () => { cam = null; go(null); show(); canvas.style.opacity = ''; };
    if (!animate || !cam) { swap(); return; }
    canvas.style.opacity = '0';
    fading = setTimeout(swap, FADE_MS);
  }
  button.addEventListener('click', () => { if (on) leave(); else enter(); });
  button.addEventListener('pointerenter', askDeep);  // (likely to be pressed: its answer is on its way)
  // the scene drawn again for the camera as it is now, once the moves of one frame are in (a
  // timer, not the next animation frame: the web view has none while its window is hidden)
  let queued = false;
  function redraw() {
    if (queued) return;
    queued = true;
    setTimeout(() => {
      queued = false;
      if (!current()) return;
      go(cam, behind);
      show();
    }, MOVE_MS);
  }
  /* pick tree `index` (null: none), the camera staying where it is */
  function pick(index) { if (!on || picked === index) return; picked = index; redraw(); }
  /* to the day before or after the tree picked: the camera glides to stand before it */
  function step(dir) {
    if (!on || picked == null) return;
    const t = day(picked, dir);
    if (!t) return;
    picked = t.index;
    if (!cam) cam = home(0);
    const z = Math.max(furthest, t.row + t.jy);
    glide({ x: clampX(xOf(t) * per, z), z, b: 1 }, GLIDE_MS, ease);
  }
  /* the camera glides to `to` in `ms`, along `curve` */
  function glide(to, ms, curve) {
    const from = Object.assign({}, cam), t0 = Date.now();
    clearTimeout(gliding);
    const tick = () => {
      if (!on || !cam || !current()) return;
      const k = animate ? Math.min(1, (Date.now() - t0) / ms) : 1, e = curve(k);
      cam.x = lerp(from.x, to.x, e); cam.z = lerp(from.z, to.z, e); cam.b = lerp(from.b, to.b, e);
      redraw();
      if (k < 1) gliding = setTimeout(tick, MOVE_MS);
    };
    tick();
  }
  /* a drag let go past the forest's end: back to it, slowing as it comes */
  function settle() {
    if (!on || !cam) return;
    const to = { z: Math.max(furthest, cam.z), b: cam.b };
    to.x = clampX(cam.x, to.z);
    if (to.x !== cam.x || to.z !== cam.z) glide(to, SETTLE_MS, k => 1 - Math.pow(1 - k, 3));
  }
  // how far along the rows the camera at depth z goes either way, and x kept to that (a forest
  // narrower than the room it would leave stays in the middle)
  let span = null;
  function ends(z) {
    // the camera stands mid-canvas: the end, 1 - END_GAP across, is half the width less that
    // on, along the nearest row ahead
    const ahead = z - Math.min(base.rows - 1, Math.floor(z));
    const gap = (0.5 - END_GAP) / slotWidth(visitLens(base, z), per, ahead);
    // the outermost trees, where the landscape squeezes the rows
    if (!span) { const xs = trees.map(it => xOf(it) * per); span = [Math.min(...xs), Math.max(...xs)]; }
    const [lo, hi] = span;
    return lo + gap < hi - gap ? [lo + gap, hi - gap] : [(lo + hi) / 2, (lo + hi) / 2];
  }
  const clampX = (x, z) => { const [lo, hi] = ends(z); return Math.max(lo, Math.min(hi, x)); };
  // the pointer's spot on the canvas, as shares of its width and height
  const spot = ([x, y]) => canvas.offsetWidth && canvas.offsetHeight ? [x / canvas.offsetWidth, y / canvas.offsetHeight] : [0.5, 0.5];
  // where a pointer is on the canvas, in CSS pixels of its own: the phone's full screen turns
  // the forest a quarter clockwise (web/phone.js), so a finger going along the screen there goes
  // down the forest
  const local = e => {
    const r = canvas.getBoundingClientRect();
    return canvas.closest('.af-sideways') ? [e.clientY - r.top, r.right - e.clientX] : [e.clientX - r.left, e.clientY - r.top];
  };
  // the slot (as cam.x counts) the camera sees at the spot (fx, fy) of the canvas
  const slotAt = (fx, fy) => {
    const lens = visitLens(base, cam.z), dd = ddAt(lens, clamp((fy - HORIZON) / (GROUND_BOTTOM - HORIZON), 0.02, 1));
    return (fx - 0.5) / slotWidth(lens, per, Math.max(0, dd == null ? 200 : dd));
  };
  /* Zoom `d` rows in (- out) about the spot `f` ([across, down] the canvas), which stays where
   * it is: from the whole forest, the view first eases into the camera's (which sees it just
   * as the whole forest's does), which then walks in; out, it walks back to the forest's edge,
   * and eases back into the whole forest (zooming still on). False if there is nowhere further
   * to go. */
  function zoom(d, [fx, fy]) {
    if (!on) return false;
    clearTimeout(gliding);
    if (!cam) {
      if (d <= 0) return false;
      clearTimeout(fading); canvas.style.opacity = '';
      cam = home(0);
    }
    const was = [cam.x, cam.z, cam.b];
    let rest = Math.abs(d);
    if (d > 0) {
      if (cam.b < 1) { const k = Math.min(1 - cam.b, rest / BLEND_ROWS); cam.b += k; rest -= k * BLEND_ROWS; }
      if (rest > 0) {
        const at = cam.x + slotAt(fx, fy);
        cam.z = Math.max(furthest, cam.z - rest);
        cam.x = clampX(at - slotAt(fx, fy), cam.z);
      }
    } else {
      if (cam.z < start) {
        const at = cam.x + slotAt(fx, fy), k = Math.min(start - cam.z, rest);
        cam.z += k; rest -= k;
        cam.x = clampX(at - slotAt(fx, fy), cam.z);
      }
      if (rest > 0) cam.b = Math.max(0, cam.b - rest / BLEND_ROWS);
      if (cam.b <= 0) { cam = null; redraw(); return true; }  // the whole forest again
    }
    if (was[0] === cam.x && was[1] === cam.z && was[2] === cam.b) return false;
    redraw();
    return true;
  }
  /* along the rows, `slots` further; a drag (`drag`, its press) gives past the rows' ends */
  function pan(slots, drag) {
    clearTimeout(gliding);
    let x = cam.x + slots;
    if (drag) {
      const most = BAND_SHARE / slotWidth(visitLens(base, cam.z), per, 0);
      x = drag.rawX = (drag.rawX == null ? cam.x : drag.rawX) + slots;
      const [lo, hi] = ends(cam.z);
      if (x < lo) x = lo - band(lo - x, most);
      else if (x > hi) x = hi + band(x - hi, most);
    } else x = clampX(x, cam.z);
    if (x !== cam.x) { cam.x = x; redraw(); }
  }
  /* deeper in, `rows` further, as a drag (`drag`, its press) walks: past the back row it gives */
  function walk(rows, drag) {
    const z = drag.rawZ = (drag.rawZ == null ? cam.z : drag.rawZ) - rows;
    if (z >= furthest) { zoom(cam.z - z, [0.5, 1]); return; }
    clearTimeout(gliding);
    cam.z = furthest - band(furthest - z, BAND_ROWS);
    redraw();
  }
  // a drag, once in: sideways along the rows (the forest follows the pointer), or up to walk
  // deeper in (down, back out), whichever way it set off; two fingers pinch to zoom
  const fingers = new Map();
  let press = null, pinch = null, dragged = false, tapped = null;
  // a double tap: zooms in about where it was, gliding there
  function doubleTap(at) {
    const f = spot(at), t0 = performance.now();
    let done = 0;
    const step = () => {
      if (!current() || !on) return;
      const k = Math.min(1, (performance.now() - t0) / DOUBLE_GLIDE_MS), rows = DOUBLE_ROWS * (1 - (1 - k) * (1 - k));
      zoom(rows - done, f); done = rows;
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  canvas.addEventListener('pointerdown', e => {
    if (e.button > 0) return;
    // fingers only (a mouse never pinches), and a first finger starts afresh: one whose lift
    // went unseen must not make the next touch a pinch
    if (e.isPrimary) { fingers.clear(); pinch = null; }
    if (!on) return;
    if (e.pointerType === 'touch') fingers.set(e.pointerId, local(e));
    if (fingers.size === 2) {
      const [a, b] = [...fingers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, done: 0 }; press = null; tapped = null;
      return;
    }
    const [x, y] = local(e);
    press = { id: e.pointerId, x, y, axis: null, touch: e.pointerType === 'touch' };
  });
  canvas.addEventListener('pointermove', e => {
    if (fingers.has(e.pointerId)) fingers.set(e.pointerId, local(e));
    if (pinch && fingers.size === 2) {
      const [a, b] = [...fingers.values()], rows = Math.log(Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch.d) / Math.LN2 * PINCH_ROWS;
      zoom(rows - pinch.done, spot([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]));
      pinch.done = rows; dragged = true;
      return;
    }
    if (!press || press.id !== e.pointerId || !on) return;
    const [x, y] = local(e), dx = x - press.x, dy = y - press.y;
    if (!press.axis) {
      if (Math.abs(dx) + Math.abs(dy) < DRAG_PX) return;
      // (one finger only ever goes along the rows: two pinch to walk in)
      press.axis = press.touch || Math.abs(dx) >= Math.abs(dy) ? 'x' : 'z';
      // from the whole forest: the camera at its edge, which sees it just as the whole forest's view does
      if (!cam) { clearTimeout(fading); canvas.style.opacity = ''; cam = home(1); }
      root.classList.add('af-dragging');
      try { canvas.setPointerCapture(e.pointerId); } catch { /* the pointer is gone */ }
    }
    press.x = x; press.y = y;
    if (!cam) return;  // walked back out to the whole forest
    if (press.axis === 'x') pan(-dx / ((canvas.clientWidth || 1) * slotWidth(visitLens(base, cam.z), per, 0)), press);
    else walk(-dy / (canvas.clientHeight || 1) * WALK_ROWS, press);
  });
  const release = e => {
    fingers.delete(e.pointerId);
    if (fingers.size < 2) pinch = null;
    if (press && press.id === e.pointerId) {
      if (press.axis) { dragged = true; settle(); tapped = null; }
      else if (press.touch && e.type === 'pointerup') {
        const now = performance.now();
        if (tapped && now - tapped.t < DOUBLE_MS && Math.hypot(press.x - tapped.x, press.y - tapped.y) < DOUBLE_PX) {
          tapped = null; dragged = true;  // (its click is not a tap on a tree)
          doubleTap([press.x, press.y]);
        } else tapped = { t: now, x: press.x, y: press.y };
      }
      press = null;
    }
    if (dragged) setTimeout(() => { dragged = false; }, 0);
    root.classList.remove('af-dragging');
  };
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  // the click that ends a drag is not a click on a tree
  scene.addEventListener('click', e => { if (dragged) { e.stopPropagation(); e.preventDefault(); } }, true);
  // the wheel zooms in (away from you) and back out, while zooming is on; out past the whole
  // forest the page scrolls
  canvas.addEventListener('wheel', e => {
    const rows = -e.deltaY * (e.deltaMode === 1 ? 30 : 1) * WHEEL_ROWS * (e.ctrlKey ? PINCH_GAIN : 1);
    // zoomed in, at the back row it is still the forest's (rather than scroll the page away
    // from it), and so is a trackpad's pinch in (a wheel with ctrl): passed on, it would zoom
    // the whole window
    if (zoom(rows, spot(local(e))) || (on && (cam || (e.ctrlKey && rows > 0)))) e.preventDefault();
  });
  bar.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    if (b.dataset.day) step(b.dataset.day);
    else if (b.dataset.act === 'back') leave();
  });
  // the keys, while zooming is on and nothing else on the page is being typed into (nor the
  // heatmap under the forest, whose controls the arrow keys switch: web/calendar.js)
  const onKey = e => {
    if (!current()) { document.removeEventListener('keydown', onKey); return; }
    if (!on || e.altKey || e.ctrlKey || e.metaKey || /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '')) return;
    if (e.target && e.target.closest && e.target.closest('.af-cal')) return;
    if (e.key === 'Escape') { if (picked != null) pick(null); else leave(); }
    else if (KEYS[e.key]) {
      const [along, rows] = KEYS[e.key];
      if (rows) zoom(rows * KEY_ROWS, [0.5, 0.6]);
      else {
        if (!cam) { clearTimeout(fading); canvas.style.opacity = ''; cam = home(1); }  // (as a drag sets off)
        pan(along * KEY_SHARE / slotWidth(visitLens(base, cam.z), per, 0));
      }
    }
    else return;
    e.preventDefault();
  };
  if (root.afVisitKeys) document.removeEventListener('keydown', root.afVisitKeys);  // a forest before this one's
  root.afVisitKeys = onKey;
  document.addEventListener('keydown', onKey);
  // a press anywhere else on the page turns zooming off, so the wheel and a pinch are the page's again
  const onPress = e => {
    if (!current()) { document.removeEventListener('pointerdown', onPress, true); return; }
    // (the phone card's own buttons, such as Full screen, keep the view)
    if (on && !root.contains(e.target) && !(e.target.closest && e.target.closest('.af-phone-shell'))) leave();
  };
  if (root.afVisitPress) document.removeEventListener('pointerdown', root.afVisitPress, true);
  root.afVisitPress = onPress;
  document.addEventListener('pointerdown', onPress, true);
  // the mouse's back button goes back out (and is not the page's back)
  const onBack = e => { if (e.button === BACK_BUTTON && on) { e.preventDefault(); leave(); } };
  scene.addEventListener('mouseup', onBack); bar.addEventListener('mouseup', onBack);
  return {
    get on() { return on; },
    get picked() { return picked; },
    pick,
    get state() { return on ? { cam: cam && Object.assign({}, cam), picked } : null; },
    resume(st) { if (!current() || !st) return; on = true; cam = st.cam && Object.assign({}, st.cam); picked = st.picked; go(cam, behind); show(); }
  };
};
})();

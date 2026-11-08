/* Memory Forest — the events: what the way you study brings to the forest, besides the
 * trees. Each lives in a file of its own under web/events/ and registers here with the hooks
 * it needs; the numbers come from events.py, and these only draw them. The scene calls in at
 * a few points:
 *
 *   soil(env, lg)          the bare ground, once it is painted
 *   treeBase(env, lg, p, sw, x, y)   the foot of each tree, as it is drawn
 *   ground(env, lg)        the ground, once everything on it is drawn
 *   back(g, env, t)        each frame, behind the forest
 *   grass(g, env, t)       each frame, over the forest but under the animals
 *   front(g, env, t)       each frame, in front of it all
 *   pick(env, data, mx, my, animate)   the pointer: a tooltip ({ html, replay }), or nothing
 *   caption(data, animate)             items for the line under the forest
 *   mount(root, data, opts, animate, seen)   before the forest is mounted: true to take over
 *
 * Events run in the order their files load (see catalog.SCRIPTS). */
(function () {
'use strict';
const AF = window.AnkiForest;

const list = [];
AF.events = {
  add(key, spec) { list.push(Object.assign({ key }, spec)); },
  /* every event that has this hook, in order */
  run(hook, ...args) { for (const e of list) if (e[hook]) e[hook](...args); },
  /* only these events' hook (keys), in order: the birds of one tree, for its outline (hover.js) */
  runOnly(keys, hook, ...args) { for (const e of list) if (e[hook] && keys.includes(e.key)) e[hook](...args); },
  /* the first event whose hook answers */
  first(hook, ...args) {
    for (const e of list) { const r = e[hook] && e[hook](...args); if (r) return r; }
    return null;
  },
  /* what every event's hook returns, as one list */
  collect(hook, ...args) { return list.flatMap(e => (e[hook] && e[hook](...args)) || []); },
};

/* what the events draw with: one pixel (at any position, rounded), and a steady noise */
const { hashStr } = AF.u;
AF.events.px = (g, x, y, c) => { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), 1, 1); };
AF.events.noise = (a, b) => hashStr(a + ',' + b) / 4294967296;

/* The top of a tree's crown at column x of the forest, as its sprite is drawn, for a bird to
 * stand on; null past the crown's edge. A crown's top is not its stage's full height: it
 * rounds off, and each environment draws its own. */
const crownTops = new WeakMap();  // placed tree -> its sprite's size and the first row drawn in each column
AF.events.crownTop = (env, p, x) => {
  const px = AF.pixel;
  if (!px || !px.sprite) return null;
  let spr = crownTops.get(p);
  if (!spr) {  // read once per tree, the first time a bird looks: sprites aren't kept
    const h = Math.max(3, Math.round(AF.STAGE_H[p.it.stage] * env.u * p.s));
    const cv = px.sprite(p.it, h, Math.round(p.hz * px.HAZE_STEPS), env), width = cv.width, height = cv.height;
    const d = cv.getContext('2d').getImageData(0, 0, width, height).data, tops = [];
    for (let cx = 0; cx < width; cx++) {
      let top = null;
      for (let cy = 0; cy < height && top === null; cy++) if (d[(cy * width + cx) * 4 + 3] > 0) top = cy;
      tops.push(top);
    }
    spr = { width, height, tops };
    crownTops.set(p, spr);
  }
  const x0 = Math.round(p.x - spr.width / 2), y0 = Math.round(p.y - spr.height + 1);
  let cx = Math.round(x) - x0;
  if (env.flipLight) cx = spr.width - 1 - cx;  // drawn mirrored
  const top = cx >= 0 && cx < spr.tops.length ? spr.tops[cx] : null;
  return top === null ? null : y0 + top;
};
/* A bird's colours as its tree's are: tinted, hazed with distance (or faded out, on a deck
 * screen) and veiled by the fog in front of it, as trees.js and the engine's fog veils do. A bird
 * painted in its own colours on a far tree in fog stood out like something floating there.
 * BIRD_FADE of the tree's fading: all of it lost a far crow in fog entirely, and a crow is news
 * (a leech). Worked out once a scene per tree and colour: the birds are drawn every frame. */
const BIRD_FADE = 0.6;
const birdColors = new WeakMap();  // placed tree -> colour -> 'rgb(...)'
AF.events.birdColor = (env, p) => {
  let seen = birdColors.get(p);
  if (!seen) birdColors.set(p, seen = new Map());
  return col => {
    let out = seen.get(col);
    if (out !== undefined) return out;
    const th = env.theme, pxl = AF.pixel || {}, { hex, mix, rgb } = AF.u;
    const hzq = pxl.sizeOf ? pxl.sizeOf(p, env).hzq : 0, haze = hex(th.haze);
    let c = hex(col);
    if (th.tint) c = mix(c, hex(th.tint), th.tintAmt);
    if (hzq >= (pxl.FADED_HZQ || Infinity)) { const l = c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11; c = mix(c, mix(mix([l, l, l], [142, 152, 168], 0.45), haze, 0.2), BIRD_FADE); }
    else if (hzq) c = mix(c, haze, BIRD_FADE * hzq * th.hzStep);
    const fog = env.fogVeils, after = fog && th.fog ? fog.n - (p.veilsBefore || 0) : 0;
    if (after > 0) c = mix(c, hex(th.fog), BIRD_FADE * (1 - Math.pow(1 - fog.amt, after)));
    seen.set(col, out = rgb(c));
    return out;
  };
};
/* where a bird with its feet at column x stands: on the crown there, or, past its edge, as
 * near there as the crown reaches; `fallback` when the crown can't be read */
AF.events.perch = (env, p, x, fallback) => {
  for (let k = 0; k < 16; k++) {
    const at = x + (x < p.x ? k : -k), top = AF.events.crownTop(env, p, at);
    if (top !== null) return { x: at, y: top };
  }
  return { x, y: fallback };
};
})();

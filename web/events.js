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
 *   caption(data, words, animate)      items for the line under the forest
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
const crownTops = new WeakMap();  // sprite -> the first row drawn in each of its columns
AF.events.crownTop = (env, p, x) => {
  const px = AF.pixel;
  if (!px || !px.sprite) return null;
  const h = Math.max(3, Math.round(AF.STAGE_H[p.it.stage] * env.u * p.s));
  const spr = px.sprite(p.it, h, Math.round(p.hz * px.HAZE_STEPS), env);
  let tops = crownTops.get(spr);
  if (!tops) {
    const d = spr.getContext('2d').getImageData(0, 0, spr.width, spr.height).data;
    tops = [];
    for (let cx = 0; cx < spr.width; cx++) {
      let top = null;
      for (let cy = 0; cy < spr.height && top === null; cy++) if (d[(cy * spr.width + cx) * 4 + 3] > 0) top = cy;
      tops.push(top);
    }
    crownTops.set(spr, tops);
  }
  const x0 = Math.round(p.x - spr.width / 2), y0 = Math.round(p.y - spr.height + 1);
  let cx = Math.round(x) - x0;
  if (env.flipLight) cx = spr.width - 1 - cx;  // drawn mirrored
  const top = cx >= 0 && cx < tops.length ? tops[cx] : null;
  return top === null ? null : y0 + top;
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

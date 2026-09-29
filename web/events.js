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
})();

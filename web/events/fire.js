/* Memory Forest — Wild's fire: flames on the side of each tree it has caught, high while you
 * are away and dying down each day you study, a plume of smoke rising off them, and their glow,
 * strongest at night. The day before it breaks out, a thin wisp of smoke from the trees it
 * will take (`smoke`), as a warning.
 * The trees' char is in their sprites (web/engines/pixel/trees.js). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { clamp } = AF.u;
const { px, noise, crownTop } = AF.events;
const FLAME = ['#fff3b0', '#ffc94a', '#ff8a2a', '#d9471b', '#9c2a14'];
const HEAL_DAYS = 7;  // events.FIRE_HEAL_DAYS: a tree's `burn` loses a seventh a day studied

// Flames stand on the crown up to FLAME_H of the tree's height, from a blaze (burn 1) down to
// nothing at FLAMES_UNTIL; below that it only smokes, SMOKE_PUFFS a tree. The glow reaches
// GLOW_R of the tree's height, as bright as GLOW by the time of day.
const FLAME_H = 0.35, FLAMES_UNTIL = 0.35, GLOW_R = 0.6;
// The plume: PUFFS puffs a tree, rising PLUME_H of the tree's height (and PLUME_ADD pixels),
// swelling to PUFF_R pixels across and leaning DRIFT pixels downwind as they go.
const PUFFS = 14, PLUME_H = 1.5, PLUME_ADD = 8, PUFF_R = 3, DRIFT = 7;
const SMOKE = [[78, 72, 68], [104, 98, 94], [134, 128, 124]];  // dark low down, paler as it rises
const WISP = 0.4;  // the warning's smoke: a plume as thin and low as a tree's this far burnt down
const GLOW = { night: 0.05, dusk: 0.03, dawn: 0.03 };  // (by day, the sun outshines it)

const blaze = burn => clamp((burn - FLAMES_UNTIL) / (1 - FLAMES_UNTIL), 0, 1);

/* the top of the crown in each column across the tree, read once per scene */
const tops = new WeakMap();
function crown(env, p) {
  let c = tops.get(p);
  if (!c) {
    const h = AF.STAGE_H[p.it.stage] * env.u * p.s, half = Math.max(2, Math.round(h * 0.45)), cols = [];
    for (let x = Math.round(p.x) - half; x <= Math.round(p.x) + half; x++) {
      const y = crownTop(env, p, x);
      if (y !== null) cols.push([x, y]);
    }
    // only the side the fire has taken (see AF.burnSide in trees.js), mirrored with the sprite
    const side = AF.burnSide(p.it.seed) ^ (env.flipLight ? 1 : 0), reach = AF.burnReach(AF.burnStep(p.it.burn) / 7), n = cols.length;
    c = { h, cols: cols.filter((col, i) => { const u = n > 1 ? i / (n - 1) : 0; return (side ? 1 - u : u) < reach - 0.05; }) };
    if (!c.cols.length) c.cols = cols.slice(side ? -1 : 0, side ? undefined : 1);
    tops.set(p, c);
  }
  return c;
}

function glow(g, env, p, c, k) {
  const a = (GLOW[env.mood.time] || 0) * (0.35 + 0.65 * k);
  if (!a) return;
  const r = Math.max(3, Math.round(c.h * GLOW_R * (0.6 + 0.4 * k))), cx = Math.round((c.cols[0][0] + c.cols[c.cols.length - 1][0]) / 2), cy = Math.round(p.y - c.h * 0.5);
  g.save(); g.globalCompositeOperation = 'lighter';
  for (const share of [1, 0.75, 0.5]) {  // pixel discs, one inside the other: brighter towards the middle
    const rr = Math.round(r * share);
    g.fillStyle = `rgba(255,120,40,${a.toFixed(3)})`;
    for (let dy = -rr; dy <= rr; dy++) { const w = Math.round(Math.sqrt(rr * rr - dy * dy)); g.fillRect(cx - w, cy + dy, w * 2, 1); }
  }
  g.restore();
}

function flames(g, p, c, k, f) {
  const n = c.cols.length, tall = c.h * FLAME_H * k;
  c.cols.forEach(([x, top], i) => {
    const mid = 1 - Math.abs(i - (n - 1) / 2) / (n / 2 + 0.5);  // tallest over the middle
    const hh = Math.round(tall * (0.35 + 0.65 * mid ** 0.7) * (0.6 + 0.5 * noise(x * 3 + p.it.seed, f)));
    for (let j = -1; j <= hh; j++) {
      const q = hh > 0 ? j / hh : 0;
      if (q > 0.5 && noise(x + j * 31, f + p.it.seed) < q * 0.7) continue;  // a ragged top
      px(g, x + (q > 0.6 && noise(x, j + f) < 0.3 ? 1 : 0), top + 1 - j, FLAME[Math.min(FLAME.length - 1, Math.floor(q * FLAME.length))]);
    }
  });
  // sparks, rising off the blaze
  for (let i = 0; i < 2 * k; i++) {
    const [x, top] = c.cols[Math.floor(noise(i, p.it.seed) * n)], life = (f + i * 5) % 12;
    if (noise(i, Math.floor((f + i * 5) / 12)) < 0.6) px(g, x + Math.round(Math.sin(life * 0.6 + i) * 1.5), top - tall - life, life < 6 ? FLAME[1] : FLAME[3]);
  }
}

/* the plume: dithered puffs, swelling and paling as they rise and lean downwind, from over
 * the flames */
function plume(g, p, c, burn, t) {
  const [x0, top] = c.cols[Math.floor(c.cols.length / 2)], rise = (c.h * PLUME_H + PLUME_ADD) * (0.5 + 0.5 * burn);
  const base = top - 1 - Math.round(c.h * FLAME_H * blaze(burn) * 0.5);
  for (let i = 0; i < PUFFS; i++) {
    const q = (t * 0.1 + i / PUFFS + noise(i, p.it.seed) * 0.3) % 1;
    const a = (0.6 * burn * (1 - q) ** 0.8).toFixed(2), col = SMOKE[Math.min(2, Math.floor(q * 3))];
    const cx = x0 + Math.round(Math.sin(q * 4 + i) + q * q * DRIFT), cy = Math.round(base - q * rise);
    const r = 1 + q * PUFF_R;  // a round blob, 2x2 at the smallest
    for (let dy = -Math.ceil(r); dy < r; dy++) for (let dx = -Math.ceil(r); dx < r; dx++) {
      const d = (dx + 0.5) ** 2 + (dy + 0.5) ** 2;
      if (d > r * r || (d > (r - 1) ** 2 && (cx + dx + cy + dy) & 1)) continue;  // a dithered edge
      px(g, cx + dx, cy + dy, `rgba(${col},${a})`);
    }
  }
}

AF.events.add('fire', {
  /* in front of it all: the glow and the flames, then the plumes over every tree's flames */
  front(g, env, t) {
    const f = Math.floor(t * 12), burning = env.placed.filter(p => !p.it.pond && p.it.burn);
    for (const p of burning) {
      const c = crown(env, p), k = blaze(p.it.burn);
      if (!c.cols.length) continue;
      if (k > 0) glow(g, env, p, c, k);
      if (k > 0) flames(g, p, c, k, f);
    }
    for (const p of burning) { const c = crown(env, p); if (c.cols.length) plume(g, p, c, p.it.burn, t); }
    for (const p of env.placed) if (p.it.smoke && !p.it.pond) { const c = crown(env, p); if (c.cols.length) plume(g, p, c, WISP, t); }
  },
  // the caption's item while it burns: [text, tooltip]
  caption(data, words) {
    const fire = data.fire;
    if (fire && fire.smoke) return [['Smoke: study today', smokeText]];
    if (!fire || !fire.trees) return [];
    const n = fire.trees, left = fire.left;
    return [[`Fire: ${n} ${n === 1 ? words.one : words.many}`,
      `${n} ${n === 1 ? words.one : words.many} caught fire while you were away. ${left} more day${left === 1 ? '' : 's'} of study ${left === 1 ? 'puts' : 'put'} it out.`]];
  },
});

const smokeText = 'Smoke is rising after a day without reviews. Study today, or tomorrow the forest catches fire.';

/* what a burning (or smoking) tree's tooltip adds */
AF.fireLine = t => {
  if (!t.burn) return `<b>Smoking</b>: ${smokeText}`;
  const left = Math.max(1, Math.round(t.burn * HEAL_DAYS));
  return `<b>On fire</b>: it caught while you were away · green again after ${left} more day${left === 1 ? '' : 's'} of study`;
};
})();

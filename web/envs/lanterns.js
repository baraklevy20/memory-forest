/* Memory Forest - the lantern night environment.
 * Everything this environment is lives here: delete it and lantern.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * A warm plum night with paper lanterns drifting up: a thin river of them rising from
 * the lake towards the far corner of the sky, more scattered all around, and more still
 * floating on the water, every one of them laying a streak of light on the lake. They all
 * drift slowly upward, and a still forest (animations off) still shows them; the
 * few that rise from the oldest trees (effects.js) move among them.
 *
 * The trees are plum, lit from above by the lanterns: each crown's upper edge catches a
 * coral light. Yellow stays reserved for forgetting. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rng } = AF.u;
const H6 = a => a.map(hex);

const ROUNDS = [
  H6(['#1a0c1e', '#3a1634', '#5a2244', '#7a3450', '#a44a5a']),
  H6(['#1a0c1e', '#321a3e', '#4e2650', '#6e3662', '#9a4e72']),
  H6(['#1a0c1e', '#3a1a2e', '#5e2a3e', '#84404c', '#b25a5e']),
];
const PINE = H6(['#140a1a', '#2a1230', '#421c40', '#5e2a4e', '#86405a']);
// forgetting stays plainly yellow against the plum: lemon to ochre, never coral
const SICK = [null,
  H6(['#2a2010', '#6e5418', '#c09a2c', '#e8c840', '#fae276']),
  H6(['#2a2010', '#7a5a1a', '#c09030', '#e6be48', '#f8dc76']),
  H6(['#241a0e', '#5e4418', '#9a7a2a', '#c8a23c', '#e8c860'])];
const GLOW = hex('#f58a6e'), GLOW_HI = hex('#ffb48a');

/* the lanterns in the sky and on the water, placed once per forest. Each sky lantern is
 * a place on its path, not a fixed point: `at` says where it is at a given moment. */
function lanterns(env) {
  if (env.lanternSet) return env.lanternSet;
  const { u } = env, R = rng(((env.data.forestSeed || 3) ^ 0x1a47) >>> 0);
  const sky = [], water = [];
  // the river: from low over the bridge side of the lake up to the far top corner
  for (let i = 0; i < 7; i++) sky.push({ river: true, f: R(), spread: (R() - 0.5) * 2, v: 1 / (170 + R() * 60) });
  // and a scattering across the rest of the sky, rising straight up
  for (let i = 0; i < 5; i++) sky.push({ river: false, x: R(), f: R(), v: (0.5 + R() * 0.4) * u });
  // floating lanterns on the lake
  if (env.mood.landscape === 'lake') for (let i = 0; i < 3; i++) water.push({ fx: R(), fy: R(), ph: R() * 6 });
  return (env.lanternSet = { sky, water });
}

/* where a sky lantern is at time t, or null while it is hidden by the moon */
function at(env, l, t) {
  const { W, H, u, hor } = env, o = env.theme.orb;
  let x, y;
  if (l.river) {
    const f = (l.f + t * l.v) % 1, spread = l.spread * 0.5 * (10 + 26 * f) * u;
    x = W * (0.12 + 0.72 * f) + spread * 0.6; y = hor * (0.92 - 0.84 * f) + spread;
  } else {
    const span = hor * 0.95, k = ((l.f * span + t * l.v) % span) / span;
    x = W * l.x + Math.sin(t * 0.2 + l.f * 9) * 2 * u; y = hor * 0.95 - k * span;
  }
  if (y <= 2 || y >= hor) return null;
  if (o && Math.hypot(x - W * o.x, y - H * o.y) < o.r * u + 5) return null;
  return { x: Math.round(x), y: Math.round(y) };
}

/* one lantern: the further up the sky, the further away and the smaller */
function paintLantern(g, x, y, size) {
  if (size === 0) { g.fillStyle = '#ffce6e'; g.fillRect(x, y, 1, 1); return; }
  if (size === 1) {
    g.fillStyle = 'rgba(255,170,90,.3)'; g.fillRect(x - 1, y, 4, 2); g.fillRect(x, y - 1, 2, 4);
    g.fillStyle = '#ffce6e'; g.fillRect(x, y, 2, 2); g.fillStyle = '#e8703a'; g.fillRect(x, y + 1, 2, 1);
    return;
  }
  g.fillStyle = 'rgba(255,170,90,.18)'; g.fillRect(x - 2, y, 7, 4); g.fillRect(x, y - 2, 3, 8);
  g.fillStyle = 'rgba(255,170,90,.34)'; g.fillRect(x - 1, y + 1, 5, 2); g.fillRect(x + 1, y - 1, 1, 6);
  g.fillStyle = '#b8432c'; g.fillRect(x, y, 3, 1);
  g.fillStyle = '#ffd67a'; g.fillRect(x, y + 1, 3, 2); g.fillStyle = '#fff0b8'; g.fillRect(x + 1, y + 1, 1, 1);
  g.fillStyle = '#ec783a'; g.fillRect(x, y + 3, 3, 1);
}
const sizeAt = (y, hor) => y < hor * 0.28 ? 0 : y < hor * 0.6 ? 1 : 2;

AF.env('lanterns', {
  night: true,  // with the real hour on, it keeps to the night

  look: (mood, night) => night ? AF.TIMES.plum_night : null,

  after(th, mood) {
    const night = mood.time === 'night' || mood.time === 'dusk';
    if (night) {
      // warmer and a little brighter than the plain plum night, so the plum trees read
      Object.assign(th, { g0: '#2e1a30', g1: '#1c1020', grass: '#44263e', far: '#2e1c3c', near: '#241430', haze: '#4a2a4c',
        tint: '#1d1530', tintAmt: 0.12, water: '#2e1f40', rim: null });
      th.sky = ['#0c0922', '#1c1238', '#2e1846', '#44204e', '#5e2a54', '#7a3658'];
    }
    th.lanternNight = night;
  },

  pals: { rounds: ROUNDS, pine: PINE, bark: { l: hex('#5a3a44'), m: hex('#3e2432'), d: hex('#22121e') },
    leaf: hex('#b25a5e'), leafL: hex('#f58a6e'), stem: hex('#6e3662') },
  leafColors: ['#e8c840', '#c09a2c'],

  tree: {
    sickPalette: c => SICK[c.t.health],
    // the lanterns overhead catch the top of every crown
    pixel(col, { x, y, tn, pal, c }) {
      if (tn < 2 || c.inside(x, y - 1) || pal === SICK[c.t.health]) return col;
      return tn >= 3 ? (c.inside(x, y - 2) ? GLOW : GLOW_HI) : mix(col, GLOW, 0.5);
    },
  },

  /* the lanterns in the sky, drifting slowly upward behind the trees. Drawn every frame,
   * and once when animations are off, so a still forest still has its lanterns. */
  fx: {
    back(g, env, t) {
      if (!env.theme.lanternNight) return;
      for (const l of lanterns(env).sky) {
        const p = at(env, l, t);
        if (p) paintLantern(g, p.x, p.y, sizeAt(p.y, env.hor));
      }
    },
  },

  /* on the lake: each sky lantern's streak of light, following it, and the lanterns
   * floating on the water, bobbing a little */
  frame(g, env, t) {
    const L = env.water;
    if (!env.theme.lanternNight || !L) return;
    const { W, H, hor } = env, s = lanterns(env);
    for (const l of s.sky) {
      // the streak sits where the lake mirrors that height of sky, nearer the shore the
      // higher the lantern; only the nearer, larger ones are bright enough to show
      const p = at(env, l, t);
      if (!p || sizeAt(p.y, hor) === 0) continue;
      const j = Math.round((hor - p.y) * 0.45);
      if (j >= L.lh - 3) continue;
      g.fillStyle = 'rgba(255,190,110,.5)'; g.fillRect(p.x + 1, L.y0 + j, 1, 2);
      g.fillStyle = 'rgba(255,150,90,.22)'; g.fillRect(p.x, L.y0 + j + 2, 3, 1);
    }
    for (const w of s.water) {
      const x = Math.round(W * (0.04 + 0.92 * w.fx)), y = Math.round(L.y0 + 3 + w.fy * (Math.min(H, L.y0 + L.lh) - L.y0 - 7));
      const bob = Math.round(Math.sin(t * 0.8 + w.ph) * 0.6);
      g.fillStyle = 'rgba(255,170,90,.28)'; g.fillRect(x, y + 3, 3, 3); g.fillRect(x + 1, y + 6, 1, 2);
      g.fillStyle = '#6a2a22'; g.fillRect(x - 1, y + 2 + bob, 5, 1);
      g.fillStyle = '#ffd67a'; g.fillRect(x, y + bob, 3, 2);
      g.fillStyle = '#b8432c'; g.fillRect(x, y - 1 + bob, 3, 1);
    }
  },
});
})();

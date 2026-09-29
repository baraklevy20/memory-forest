/* Memory Forest — the moving effects over the scene, and the order they run in. The
 * effects themselves live in web/effects/: weather.js (clouds, rain, snow, lightning, wind,
 * fog) and ambience.js (stars, fireflies, birds, lanterns, petals, falling leaves). Each
 * registers here as a part with any of init, back (behind the land) and front (over it);
 * an environment adds its own through its `fx`. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng } = AF.u;
const { MATURE, OLD } = AF.STAGE;

const DEFAULT_COLORS = {
  star: '232,236,255', rain: 'rgba(170,196,214,.55)', rainFar: 'rgba(170,196,214,.3)', rainLight: 'rgba(190,210,225,.45)', splash: 'rgba(200,220,235,.8)',
  snow: 'rgba(248,250,255,.92)', bolt: '#eef3ff', flyCore: '236,255,186', flyGlow: '190,240,140',
  petals: ['#f7c6d3', '#eea0b7'], glint: '255,250,235', leaf: null, sickLeaves: ['#d6c86a', '#d8924a', '#b3ad4c']
};

// The order everything is set up in and drawn in. It is part of the look: the parts share one
// random stream as they set up, and later ones draw over earlier ones. 'env' is the
// environment's own fx (at the front, in three layers).
const INIT = ['deck', 'clouds', 'stars', 'flies', 'birds', 'rain', 'splashes', 'snow', 'petals', 'lanterns', 'glints',
  'wind', 'falling', 'spores', 'rings', 'env', 'fogBanks'];
const BACK = ['env', 'stars', 'shooting', 'deck', 'clouds', 'rain', 'lightning'];
const FRONT = ['glints', 'lanterns', 'birds', 'flies', 'env:crowns', 'rings', 'env:air', 'env:sky', 'spores', 'lights',
  'falling', 'petals', 'wind', 'fogBanks', 'snow', 'rain', 'splashes'];

const PARTS = {};

AF.fx = {
  /* weather.js and ambience.js register their effects here */
  part(key, spec) { PARTS[key] = spec; },

  init(env) {
    const th = env.theme, { W, H, u, hor } = env, A = rng(11);
    const C = Object.assign({}, DEFAULT_COLORS, th.warmFlies ? { flyCore: '255,214,150', flyGlow: '255,170,90' } : {},
      th.flyCore ? { flyCore: th.flyCore, flyGlow: th.flyGlow } : {}, env.fxColors || {});
    const trees = env.placed.filter(p => !p.it.pond);
    const elders = trees.filter(p => p.it.stage >= OLD);
    const hosts = elders.length ? elders : (trees.length ? trees : [{ x: W / 2, y: H * 0.8, s: 1, it: { stage: MATURE } }]);
    const hOf = p => AF.STAGE_H[p.it.stage] * u * p.s;
    const st = { C, clouds: [], deck: [], stars: [], flies: [], birds: [], drops: [], far: [], splashes: [], flakes: [], petals: [], lanterns: [], glints: [], leaves: [], falling: [], banks: [], spores: [], lights: [], rings: [] };
    const moon = th.orb && th.orb.kind === 'moon' ? { x: W * th.orb.x, y: H * th.orb.y, r: th.orb.r * u + 3 } : null;
    // what the parts set up from: the scene, one random stream, where the trees stand
    const ctx = { env, th, A, W, H, u, hor, C, trees, elders, hosts, hOf, moon,
      floor: env.lake ? env.lake.y0 - 2 : H, puddles: env.puddles || [] };
    const spec = AF.envOf(env);
    for (const key of INIT) {
      if (key === 'env') { if (spec.fx && spec.fx.init) spec.fx.init(st, ctx); }  // the environment adds whatever is only its own
      else if (PARTS[key] && PARTS[key].init) PARTS[key].init(st, ctx);
    }
    return st;
  },

  back(g, env, t) {
    const st = env.fx, spec = AF.envOf(env);
    for (const key of BACK) {
      if (key === 'env') { if (spec.fx && spec.fx.back) spec.fx.back(g, env, t, st); }
      else if (PARTS[key] && PARTS[key].back) PARTS[key].back(g, env, t, st);
    }
  },

  front(g, env, t) {
    const st = env.fx, spec = AF.envOf(env);
    for (const key of FRONT) {
      if (key.startsWith('env:')) { if (spec.fx && spec.fx.front) spec.fx.front(g, env, t, st, key.slice(4)); }
      else if (PARTS[key] && PARTS[key].front) PARTS[key].front(g, env, t, st);
    }
  }
};
})();

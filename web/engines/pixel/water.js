/* Memory Forest — pixel engine: a lake's surface and its reflection. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, mixHex, layer } = AF.u;

// the sun or moon on a still lake: a column of glints, each lit this often
const GLITTER_CHANCE = 0.7;
// the middle of the cabin's lit window, from its left edge (visitors.js draws it there)
const CABIN_WINDOW_X = 8;
// the furthest the ripple shifts a row of the reflection, in pixels (drawWater: under 2 px of sway, rounded)
const RIPPLE_MAX = 2;
// what the weather leaves of the sun or moon on the water
const VEIL = { cloudy: 0.35, fog: 0.3, snow: 0.5 };

/* how much of the sun or moon can reach the water, 0..1: the share of its disc not behind the
 * land (trees, ridges, a landmark), times what the weather leaves of it */
function orbShows(env) {
  const o = env.theme.orb; if (!o) return 0;
  const { W, H, u } = env, ox = W * o.x, oy = H * o.y, r = Math.max(1, o.r * u);
  const x0 = Math.max(0, Math.floor(ox - r)), y0 = Math.max(0, Math.floor(oy - r)), w = Math.min(W, Math.ceil(ox + r)) - x0, h = Math.min(H, Math.ceil(oy + r)) - y0;
  let seen = 0, all = 0;
  if (w > 0 && h > 0) { const d = env.lg.getImageData(x0, y0, w, h).data;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { if (Math.hypot(x0 + x + 0.5 - ox, y0 + y + 0.5 - oy) > r) continue; all++; if (d[(y * w + x) * 4 + 3] < 128) seen++; } }
  return (all ? seen / all : 1) * (VEIL[env.mood.weather] || 1);
}

/* the surface: ripples, and the sun or moon lying on the water */
AF.drawWater = function (g, env, t) {
  const L = env.water; if (!L) return;
  const W = env.W, still = env.theme.frozen;
  // (the part shifted off one edge comes back in at the other, so no ground shows at the edges:
  // the reflection is copied once with RIPPLE_MAX columns of each edge wrapped round onto the
  // other, so a shifted row is still one copy. Copied from the reflection as it is first drawn,
  // after any environment has laid its own surface on it, at build.)
  if (!L.wrap || L.wrap.of !== L.rf) {
    const w = L.rf.width, [cv, wg] = layer(w + 2 * RIPPLE_MAX, L.rf.height);
    wg.drawImage(L.rf, RIPPLE_MAX, 0); wg.drawImage(L.rf, RIPPLE_MAX - w, 0); wg.drawImage(L.rf, RIPPLE_MAX + w, 0);
    L.wrap = { of: L.rf, cv };
  }
  for (let j = 0; j < L.lh; j++) { const off = still ? 0 : Math.round(Math.sin(t * AF.u.cyc(0.9) + j * 0.7) * (j < 3 ? 0 : 1 + j / L.lh)); g.drawImage(L.wrap.cv, RIPPLE_MAX - off, j, W, 1, 0, L.y0 + j, W, 1); }
  const o = env.theme.orb;
  if (o && !still) {
    const ox = Math.round(W * o.x), R = rng(Math.floor(t * 2));
    // a sun more than half behind the trees glitters less, one gone behind them not at all
    const lit = L.lit === undefined ? 1 : L.lit, chance = GLITTER_CHANCE * Math.min(1, lit * 2);
    const a = (o.kind === 'moon' ? 0.75 : 0.7) * Math.min(1, 0.3 + 1.4 * lit);
    // the lower the sun or moon, the wider its path on the water; the glints take its colour
    const low = Math.max(0, Math.min(1, (o.y - 0.1) / 0.15)), spread = 0.35 + 0.35 * low, per = low > 0.3 ? 3 : 2;
    const col = mix(hex(o.kind === 'moon' ? o.c : (o.glow || o.c)), [255, 255, 255], 0.35).map(Math.round).join(',');
    g.fillStyle = `rgba(${col},${a})`;
    for (let j = 1; j < L.lh; j += 2) { const hw = 1 + Math.round(j * spread); for (let k = 0; k < per; k++) if (R() < chance) g.fillRect(ox - hw + Math.round(R() * hw * 2), L.y0 + j, 1 + (R() < 0.3 ? 1 : 0), 1); }
  }
  // the cabin's lit window (dusk and night) lies on the water below it: a short stack of warm
  // strokes, wavering and fading as they go down (not in a visit, where the cabin moves)
  const way = env.frontWay, lit = env.mood.time === 'night' || env.mood.time === 'dusk';
  if (way && lit && !still && !(env.layout && env.layout.cam) && (env.data.visitors || []).some(v => v.key === 'cabin')) {
    const cx = Math.round(way.cabinX) + CABIN_WINDOW_X;
    for (let j = 2; j < Math.min(L.lh, 15); j += 2) {
      if (Math.sin(t * 0.9 + j * 1.7 + cx) < -0.5) continue;
      const wob = Math.round(Math.sin(t * 1.1 + j * 0.8 + cx));
      g.fillStyle = `rgba(255,210,122,${(0.6 * (1 - j / 16)).toFixed(2)})`; g.fillRect(cx - 1 + wob, L.y0 + j, j < 8 ? 3 : 2, 1);
    }
  }
};

/* Water in front of the forest, reflecting what stands behind it. A landscape says where
 * it sits ({ y0, deep, shore, step, tint }); an environment can lay its own surface on top
 * of the result. */
AF.buildWater = function (env, o) {
  const { W, H } = env;
  const y0 = Math.round(H * o.y0), lh = Math.round(H * o.deep) - y0, shore = Math.round(H * o.shore);
  const [src, sg] = layer(W, H); sg.drawImage(env.sky, 0, 0); sg.drawImage(env.land, 0, 0);
  const [rf, rg] = layer(W, lh);
  for (let j = 0; j < lh; j++) { const sy = shore - 1 - Math.round(j * o.step); if (sy < 0) break; rg.drawImage(src, 0, sy, W, 1, 0, j, W, 1); }
  // the sheen: pale dashes of uneven length at uneven gaps on every third row, fewer far off
  // (a regular pattern lined up into a lattice)
  const sheen = new Uint8Array(W * lh), SR = rng(9103);
  for (let y = 1; y < lh; y += 3) { const p = 0.15 + 0.2 * (y / lh);
    for (let x = Math.floor(SR() * 6); x < W;) { if (SR() < p) { const len = 1 + Math.floor(SR() * 4); for (let k = 0; k < len && x + k < W; k++) sheen[y * W + x + k] = 1; x += len + 1; } else x += 2 + Math.floor(SR() * 3); } }
  const img = rg.getImageData(0, 0, W, lh), d = img.data, wc = hex(env.theme.water), dk = [8, 14, 24];
  for (let y = 0; y < lh; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4, k = o.tint + 0.2 * (y / lh);
    let c = mix(mix([d[i], d[i + 1], d[i + 2]], wc, k), dk, 0.1);
    // (ice in the hour's own frozen colour: a fixed daylight white made the night's ice glow)
    if (env.theme.frozen) c = mix(c, wc, 0.45);
    if (sheen[y * W + x]) c = mix(c, [255, 255, 255], 0.12);
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255;
  }
  // frozen, a few long drifts of snow lie on the ice, their ends dithered, a faint cool shadow under each
  if (env.theme.frozen) { const R = rng(3301), sn = mix(hex(env.theme.g0), [255, 255, 255], 0.35), sh = mix(wc, [40, 60, 90], 0.5);
    const tint = (i, c, amt) => { for (let q = 0; q < 3; q++) d[i + q] += (c[q] - d[i + q]) * amt; };
    for (let k = 0; k < 7; k++) { const dy = 2 + Math.floor(R() * (lh - 6)), x0 = Math.floor(R() * W), len = 30 + Math.floor(R() * 80), rows = R() < 0.4 ? 3 : 2;
      for (let y = dy; y < Math.min(lh, dy + rows); y++) for (let x = x0; x < Math.min(W, x0 + len); x++) {
        const e = Math.min(x - x0, x0 + len - 1 - x); if (e < 10 && (x + y) % 2) continue; if (e < 4 && (x + y) % 4) continue;
        tint((y * W + x) * 4, sn, y === dy + 1 ? 0.6 : 0.38); }
      const sy = dy + rows; if (sy < lh) for (let x = x0 + 6; x < Math.min(W, x0 + len - 6); x++) if (!((x + sy) % 2)) tint((sy * W + x) * 4, sh, 0.2); } }
  rg.putImageData(img, 0, 0);
  // the open water, where the engine's rain rings land (weather.js): four spans at three depths,
  // kept 2 px tall (ambience.js would mirror fireflies in a taller one)
  if (!env.pools && !env.theme.frozen) { env.pools = [];
    for (const f of [0.18, 0.5, 0.8]) for (let c = 0; c < 4; c++) env.pools.push({ x: Math.round(W * (c + 0.5) / 4), y: y0 + Math.round(lh * f), w: Math.round(W / 4 / 0.7), h: 2 }); }
  const lg = env.lg; lg.fillStyle = mixHex(env.theme.g1, '#000000', 0.25); lg.fillRect(0, y0 - 1, W, 1);
  // (shore, step and tint too: a scenery whose sky moves can stain its reflection again from them)
  env.water = { y0, lh, rf, lit: orbShows(env), shore, step: o.step, tint: o.tint };
};
})();

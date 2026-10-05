/* Memory Forest — pixel engine: a lake's surface and its reflection. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, mixHex, layer } = AF.u;

// the sun or moon on a still lake: a column of glints, each lit this often
const GLITTER_CHANCE = 0.7;

/* the surface: ripples, and the sun or moon lying on the water */
AF.drawWater = function (g, env, t) {
  const L = env.water; if (!L) return;
  const W = env.W, still = env.theme.frozen;
  for (let j = 0; j < L.lh; j++) { const off = still ? 0 : Math.round(Math.sin(t * AF.u.cyc(0.9) + j * 0.7) * (j < 3 ? 0 : 1 + j / L.lh)); g.drawImage(L.rf, 0, j, W, 1, off, L.y0 + j, W, 1); }
  const o = env.theme.orb;
  if (o && !still) { const ox = Math.round(W * o.x), R = rng(Math.floor(t * 2)); g.fillStyle = o.kind === 'moon' ? 'rgba(238,241,248,.75)' : 'rgba(255,240,200,.7)';
    for (let j = 1; j < L.lh; j += 2) { const hw = 1 + Math.round(j * 0.35); for (let k = 0; k < 2; k++) if (R() < GLITTER_CHANCE) g.fillRect(ox - hw + Math.round(R() * hw * 2), L.y0 + j, 1 + (R() < 0.3 ? 1 : 0), 1); } }
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
  const img = rg.getImageData(0, 0, W, lh), d = img.data, wc = hex(env.theme.water), dk = [8, 14, 24];
  for (let y = 0; y < lh; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4, k = o.tint + 0.2 * (y / lh);
    let c = mix(mix([d[i], d[i + 1], d[i + 2]], wc, k), dk, 0.1);
    if (env.theme.frozen) c = mix(c, [226, 236, 244], 0.45);
    if (y % 3 === 1 && (x + y * 5) % 9 < 2) c = mix(c, [255, 255, 255], 0.12);
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255;
  }
  rg.putImageData(img, 0, 0);
  const lg = env.lg; lg.fillStyle = mixHex(env.theme.g1, '#000000', 0.25); lg.fillRect(0, y0 - 1, W, 1);
  env.water = { y0, lh, rf };
};
})();

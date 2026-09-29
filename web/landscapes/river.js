/* A river that rises between the far hills and winds down toward you, widening as it
 * comes, with the forest on both banks.
 *
 * It is calm and soft: a sky gradient pulled toward the banks' green the nearer it comes,
 * with no reflection of the trees, so the forest leads and the river doesn't grab the eye.
 * Its bed is painted onto the ground before the trees, so the ones in front stand over it;
 * once they are in, whatever water still shows is known (`env.river.vis`), and only that
 * carries the flecks, the glints and anything an environment floats on it.
 *
 * Depth `p` runs from the horizon (0) to the bottom edge (1); across, everything is a share
 * of the width. Environments that put things on the water use `center` and `halfWidth`. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, clamp, B4 } = AF.u;
const WHITE = [255, 255, 255], BLACK = [0, 0, 0];
const { HORIZON, ROWS_TOP, GROUND_BOTTOM } = AF.GEOM;

// how the channel winds (an S-curve drifting left as it comes) and how fast it widens:
// about a pixel at the horizon, about a quarter of the width at the front
const center = p => 0.6 + 0.24 * Math.sin(p * 3.5 + 0.25) * (0.35 + 0.65 * p) - 0.1 * p;
const halfWidth = (p, W) => (1.2 / W + Math.pow(p, 1.55) * 0.27) / 2;
const depth = (y, H) => (y / H - HORIZON) / (1 - HORIZON);
// room kept either side of the channel for a tree, and on the left bank for the deer or
// stag that grazes just to the right of its tree. They only graze in the front rows (at
// most GRAZER_ROWS from the front, see visitors.js), so further back the bank is planted
// right up to the water.
const TREE_GAP = 0.012, GRAZER_GAP = 0.045, GRAZER_ROWS = 6, POND_SIZE = 0.04;
// where the front animals stand, as a share of the height, and at most this far below the ground's edge
const ANIMALS_Y = 0.9, ANIMALS_DROP = 0.025;
// how far beyond the water an animal's centre stays: half the widest front sprite, and a
// step. Sprites are drawn one pixel per pixel at any scale, so this is not scaled.
const DRY_MARGIN = 9;
// the water's tone: the sky gradient, mixed with the water colour, then flattened toward
// the middle of the sky and pulled toward the banks' green the nearer it comes
const WATER_MIX = 0.3, FLATTEN = 0.25, BANK_NEAR = 0.12, BANK_FAR = 0.3;
const FLECKS = 34;
// the furthest a tall-grass blade leans over to the right
const GRASS_LEAN = 10;

const lum = c => c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11;
const bay = (x, y) => (B4[(y & 3) * 4 + (x & 3)] + 0.5) / 16;
const css = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a.toFixed(3)})`;
// how dark the hour is, from the sky at the horizon: 0 by day, up to 0.8 at night
const dimOf = th => { const s = th.sky; return clamp(1.05 - lum(hex(s[s.length - 1])) / 255 * 1.25, 0, 0.8); };

AF.landscape('river', {
  center, halfWidth,
  // the animals along the front stand a little higher than on open ground, where the channel
  // is narrower, and never below the ground an environment keeps (synthwave's grid is not ground)
  prepare(env) { env.visitorY = env.H * Math.min(ANIMALS_Y, (env.bot || GROUND_BOTTOM) + ANIMALS_DROP); },

  // the rows are squeezed aside so the channel stays open at every depth
  placeX(it, env) {
    // where AF.place will stand it, nudge within its row and all, or the curve moves under it
    const bot = env.bot || GROUND_BOTTOM, top = HORIZON + ROWS_TOP;
    const p = depth(top + (bot - top) * clamp(Math.pow(it.depth, 1.1) + (it.jy || 0) * (it.rowGap || 0), 0, 1), 1);
    const size = it.pond ? POND_SIZE : AF.STAGE_H[it.stage] * (0.82 + 0.18 * it.depth) * env.layout.zoom * 0.45 / 320;
    const a = clamp(center(p) - halfWidth(p, env.W) - size - TREE_GAP - (it.pond || it.fromFront > GRAZER_ROWS ? 0 : GRAZER_GAP), 0, 1);
    const b = clamp(center(p) + halfWidth(p, env.W) + size + TREE_GAP, 0, 1), gap = b - a;
    let sx = (0.02 + 0.96 * it.x) * (1 - gap);
    if (sx >= a) sx += gap;
    return (sx - 0.02) / 0.96;
  },

  // the animals along the front keep to their own bank, so none walks into the water
  dryX(env, x, y, home) {
    const { W, H, u } = env, p = depth(y, H), cx = W * center(p), hw = W * halfWidth(p, W) + DRY_MARGIN;
    return clamp(home < cx ? Math.min(x, cx - hw) : Math.max(x, cx + hw), 4 * u, W - 4 * u);
  },

  // tall grass grows along the front on both banks, never on the water: the left stretch
  // stops short by as far as a blade can lean over to the right
  grassRows(env) {
    const { W, H } = env, y = Math.round(H * env.bot), p = depth(y, H), cx = W * center(p), hw = W * halfWidth(p, W) + 2;
    return [[0, Math.floor(cx - hw - GRASS_LEAN), y, y + 1], [Math.ceil(cx + hw), W - 1, y, y + 1]];
  },

  // the channel, painted onto the ground before the deep forest and the trees
  bed(env, lg) {
    const { W, H } = env, th = env.theme, s = th.sky.map(hex), n = s.length, water = hex(th.water);
    const dim = dimOf(th), sink = mix(water, BLACK, 0.35), shade = c => mix(c, sink, dim);
    const edge = mix(hex(th.g1), BLACK, 0.2), sand = shade(mix([226, 196, 140], hex(th.haze), 0.2)), earth = shade(mix(hex(th.g1), [70, 52, 30], 0.5));
    const img = lg.getImageData(0, 0, W, H), d = img.data, mask = new Uint8Array(W * H), bed = new Uint32Array(W * H);
    for (let y = env.hor; y < H; y++) {
      const p = depth(y, H), cx = W * center(p), hw = W * halfWidth(p, W);
      // far water takes the sky near the horizon, near water the sky higher up
      const f = (n - 1) - p * (n - 1) * 0.85, i = clamp(Math.floor(f) - 1, 0, n - 2), fr = f - Math.floor(f);
      for (let x = Math.floor(cx - hw - 2); x <= cx + hw + 2; x++) {
        if (x < 0 || x >= W) continue;
        const dx = x + 0.5 - cx, a = Math.abs(dx) / hw, k = (y * W + x) * 4;
        let col;
        if (a <= 1) {
          col = mix(fr > bay(x, y) ? s[i + 1] : s[i], water, WATER_MIX);
          if (a > 0.72) col = mix(col, edge, 0.28 * (a - 0.72) / 0.28 + 0.1);  // darker toward the banks
          if (y % 3 === 1 && (x * 7 + y * 5) % 10 < 2) col = mix(col, WHITE, 0.14 * (1 - dim));
          mask[y * W + x] = 1;
        } else if (a <= 1 + 1.6 / hw) col = dx < 0 ? sand : earth;  // a sandy lip on the left bank, earth on the right
        else continue;
        d[k] = col[0]; d[k + 1] = col[1]; d[k + 2] = col[2]; d[k + 3] = 255;
        bed[y * W + x] = (d[k] << 16) | (d[k + 1] << 8) | d[k + 2];
      }
    }
    lg.putImageData(img, 0, 0);
    env.river = { dim, mask, bed };
  },

  // once the trees are in: find the water still showing, and soften it
  post(env) {
    const S = env.river; if (!S) return;
    const { W, H } = env, th = env.theme, water = hex(th.water);
    const mid = mix(hex(th.sky[Math.floor(th.sky.length / 2)]), water, WATER_MIX), bank = mix(hex(th.g0), hex(th.g1), 0.5);
    const img = env.lg.getImageData(0, 0, W, H), d = img.data, vis = new Uint8Array(W * H);
    for (let i = 0; i < W * H; i++) {
      if (!S.mask[i] || ((d[i * 4] << 16) | (d[i * 4 + 1] << 8) | d[i * 4 + 2]) !== S.bed[i]) continue;
      vis[i] = 1;
      const b = S.bed[i], p = depth(Math.floor(i / W), H);
      const col = mix(mix([b >> 16 & 255, b >> 8 & 255, b & 255], mid, FLATTEN), bank, BANK_NEAR + BANK_FAR * p);
      d[i * 4] = col[0]; d[i * 4 + 1] = col[1]; d[i * 4 + 2] = col[2];
    }
    env.lg.putImageData(img, 0, 0);
    S.vis = vis;
    S.glint = th.orb && th.orb.kind === 'moon' ? [232, 238, 252] : [255, 244, 214];
  },

  // flecks carried down toward you, and the sun or moon glinting where it stands over the water
  frame(g, env, t) {
    const S = env.river; if (!S || !S.vis || env.theme.frozen || env.still) return;
    const { W, H, u } = env, hor = env.hor, fa = 1 - S.dim * 0.4, R = rng(71);
    for (let k = 0; k < FLECKS; k++) {
      const q = (R() + t * 0.03 * (0.8 + R() * 0.4)) % 1, off = (R() - 0.5) * 1.3, p = Math.pow(q, 1.3), y = Math.round(hor + p * (H - hor));
      const x = Math.round(W * center(p) + off * W * halfWidth(p, W)), len = 1 + Math.round(p * 5 * u);
      if (y >= H || x < 0 || x >= W || !S.vis[y * W + x]) continue;
      g.fillStyle = css(S.glint, (0.25 + p * 0.35) * fa * 0.6); g.fillRect(x, y, len, 1);
    }
    const o = env.theme.orb; if (!o) return;
    const ox = W * o.x, G = rng(Math.floor(t * 3));
    g.fillStyle = css(S.glint, 0.55);
    for (let y = hor + 4; y < H; y++) {
      const spread = (3 + depth(y, H) * 14) * u;
      if (G() < 0.55) { const x = Math.round(ox - spread + G() * spread * 2); if (x >= 0 && x < W && S.vis[y * W + x]) g.fillRect(x, y, G() < 0.3 ? 2 : 1, 1); }
    }
  },
});
})();

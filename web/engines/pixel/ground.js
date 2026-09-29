/* Memory Forest — pixel engine: the ground and the hills, the landmark, what lies at each
 * tree's foot, fog, and the deep forest at the back. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, mixHex, rgb, B4, TAU } = AF.u;
const { SEEDLING, SAPLING } = AF.STAGE;
const { PXT, SNOW_L } = AF.pixel, painter = AF.painter;

/* aerial perspective: everything already drawn above a row's baseline is veiled a little,
 * so fog builds up with distance */
function fogVeil(g, W, H, yb, col, amt) {
  const y1 = Math.min(H, Math.round(yb)); if (y1 < 2) return;
  const img = g.getImageData(0, 0, W, y1), d = img.data, c = hex(col);
  for (let y = 0; y < y1; y++) { const k = amt * (0.55 + 0.45 * Math.min(1, (y1 - y) / 18)); for (let x = 0; x < W; x++) { const i = (y * W + x) * 4; if (!d[i + 3]) continue;
    d[i] += (c[0] - d[i]) * k; d[i + 1] += (c[1] - d[i + 1]) * k; d[i + 2] += (c[2] - d[i + 2]) * k; } }
  g.putImageData(img, 0, 0);
}

function ridges(env) {
  const { W, u, hor } = env, R = rng(7), p1 = R() * 6, p2 = R() * 6, p3 = R() * 6;
  // dunes, a mountain valley: an environment's own horizon wins over the landscape's
  const own = AF.envOf(env).ridges || AF.landOf(env).ridges;
  if (own) return own(env, { p1, p2, p3 });
  const far = x => { const f = x / W * TAU; return Math.round(hor - (7 * u + 5 * u * Math.sin(f * 1.3 + p1) + 3 * u * Math.sin(f * 3.7 + p2))); };
  const near = x => { const f = x / W * TAU; return Math.round(hor - (2 * u + 3 * u * Math.sin(f * 2.1 + p3) + 1.5 * u * Math.sin(f * 5.3 + p1))); };
  return { far, near };
}

/* a rounded hill rising above the tree line, for a landmark to stand on */
AF.drawMound = function (env, lg, x, halfW, topY) {
  const th = env.theme, hor = env.hor, c = hex(mixHex(th.near, th.far, 0.35)), cl = mix(c, [255, 255, 255], 0.08);
  for (let k = -halfW; k <= halfW; k++) {
    const q = k / halfW, y = Math.round(topY + (hor - topY) * (1 - Math.sqrt(Math.max(0, 1 - q * q))) * 0.9);
    lg.fillStyle = rgb((k < 0 ? cl : c)); lg.fillRect(x + k, y, 1, hor - y);
  }
};

/* A scene has at most one landmark. It is placed before anything is drawn and then drawn
 * in its own slot: behind the hills, on the land, or down at the shore.
 *
 * Placement always draws its random number, even where the landmark cannot be shown: it
 * shares the ground's generator, so skipping the call would shift every blade of grass. */
function placeMark(env, R) {
  const spec = AF.markOf(env);
  if (!spec.place) return null;
  const x = spec.place(env, R);
  return spec.not && spec.not.indexOf(env.mood.landscape) >= 0 ? null : { spec, x };
}
function drawMark(env, lg, mark, slot) {
  if (mark && (mark.spec.slot || 'land') === slot) mark.spec.draw(env, lg, mark.x);
}

const GRASS_TUFTS = 0.18;  // per column of the canvas
function drawGround(env, lg) {
  const th = env.theme, { W, H, hor } = env, R = rng(env.data.forestSeed || 7), rd = env.ridges;
  const mark = placeMark(env, R), spec = AF.envOf(env), land = AF.landOf(env);
  drawMark(env, lg, mark, 'back');
  // what stands on the horizon: the landscape's own backdrop,
  // then the environment's, and failing both the rolling hills
  if (land.backdrop) land.backdrop(env, lg, R);
  else if (spec.backdrop) spec.backdrop(env, lg, R);
  else {
    for (let x = 0; x < W; x++) {
      const far = rd.far(x); lg.fillStyle = th.far; lg.fillRect(x, far, 1, hor - far);
      if (land.far) land.far(env, lg, x, far);  // snow, on anything that rises far enough
      if (th.farLine) { lg.fillStyle = th.farLine; lg.fillRect(x, far, 1, 1); }
    }
    for (let x = 0; x < W; x++) { const near = rd.near(x); lg.fillStyle = th.near; lg.fillRect(x, near, 1, hor - near); if (th.nearLine) { lg.fillStyle = th.nearLine; lg.fillRect(x, near, 1, 1); } }
  }
  if (land.skipGround) {  // a landscape that is its own ground (drawn in its backdrop)
    AF.events.run('soil', env, lg);  // the bare ground the tall grass takes its colour from
    if (spec.ground) spec.ground(env, lg, R);  // the environment's own scenery, on that ground
    drawMark(env, lg, mark, 'land');
    drawMark(env, lg, mark, 'shore');
    return;
  }
  drawMark(env, lg, mark, 'land');
  // three flat bands with dithered seams: calmer than a full-height gradient
  const bands = [hex(th.g0), mix(hex(th.g0), hex(th.g1), 0.5), hex(th.g1)], gi = lg.getImageData(0, hor, W, H - hor), gd = gi.data;
  const groundPixel = spec.groundPixel;
  for (let y = hor; y < H; y++) {
    const tt = (y - hor) / (H - hor) * 3, b = Math.min(2, Math.floor(tt)), f = tt - b;
    for (let x = 0; x < W; x++) {
      let c = bands[b];
      if (b < 2 && f > 0.85 && B4[(y % 4) * 4 + x % 4] < 8) c = bands[b + 1];
      if (groundPixel) c = groundPixel(c, x, y, env) || c;
      const i = ((y - hor) * W + x) * 4; gd[i] = c[0]; gd[i + 1] = c[1]; gd[i + 2] = c[2]; gd[i + 3] = 255;
    }
  }
  lg.putImageData(gi, 0, hor);
  AF.events.run('soil', env, lg);
  lg.fillStyle = th.grass;
  for (let k = 0; k < W * GRASS_TUFTS; k++) { const x = Math.round(R() * W), y = Math.round(hor + 3 + R() * (H - hor - 3)); lg.fillRect(x - 1, y, 1, 1); lg.fillRect(x, y - 1, 1, 1); lg.fillRect(x + 1, y, 1, 1); }
  if (spec.ground) spec.ground(env, lg, R);
  drawMark(env, lg, mark, 'shore');
  for (const pd of env.puddles || []) AF.drawPuddle(lg, env, pd);
}

// a tree's shadow is SHADOW_ALPHA dark at the front, fading with the haze; the snow
// shading its foot is SNOW_SHADE of its crown's width; a yellowing tree drops leaves
const SHADOW_ALPHA = 0.3, SHADOW_HAZE_FADE = 0.6, SNOW_SHADE = 0.35;
const FALLEN_LEAVES = [0, 0, 4, 8];  // by health

/* shadows, fallen leaves, petals, snow shade and environment props at a tree's foot */
function groundDetails(env, lg, p, sw) {
  const th = env.theme, t = p.it, h = AF.STAGE_H[t.stage] * env.u * p.s, R = rng(t.seed ^ 99), x = Math.round(p.x), y = Math.round(p.y);
  if (th.shadow && t.stage > SEEDLING) {
    const len = Math.round(h * th.shadow), dir = env.flipLight ? -1 : 1;
    lg.fillStyle = `rgba(20,24,30,${(SHADOW_ALPHA * (1 - p.hz * SHADOW_HAZE_FADE)).toFixed(3)})`;
    lg.fillRect(dir > 0 ? x + 1 : x - len, y, len, 1);
  }
  if (th.snow && t.stage > SAPLING) { lg.fillStyle = 'rgba(160,178,205,.55)'; const hw = Math.round(sw * SNOW_SHADE); lg.fillRect(x - hw, y + 1, hw * 2 + 1, 1); }
  const spec = AF.envOf(env);
  if (t.health >= 2 && !th.snow) {
    const cols = spec.leafColors || ['#d8924a', '#b3ad4c'];
    for (let k = 0; k < FALLEN_LEAVES[t.health]; k++) { lg.fillStyle = cols[k & 1]; lg.fillRect(x + Math.round((R() - 0.5) * sw), y + (R() < 0.5 ? 0 : 1), 1, 1); }
  }
  if (spec.groundDetail) spec.groundDetail(env, lg, p, sw, R, x, y);
  if (spec.treeBase && !AF.landOf(env).skipGround) spec.treeBase(env, lg, p, sw);  // no ground, nothing to stand on
  AF.events.run('treeBase', env, lg, p, sw, x, y);  // a big day's wildflowers
}

/* The colours the forest's broadleaf crowns are drawn in (dark to light, as [r, g, b]), tinted
 * for the hour as the trees are: for anything that should match the trees, like the tall grass. */
AF.foliage = function (env) {
  const EP = AF.envOf(env).pals || {}, th = env.theme, tint = th.tint ? hex(th.tint) : null;
  const pal = EP.round || (EP.rounds && EP.rounds[0]) || (EP.base && EP.base.round) || PXT.round;
  return pal.map(c => tint ? mix(c, tint, th.tintAmt) : c);
};

// the deep forest's distant crowns, in env.u: one every LOBE_GAP (plus up to as much
// again), LOBE_R across (plus up to LOBE_R_SPREAD), LOBE_H of the band's height (plus up
// to LOBE_H_SPREAD)
const LOBE_GAP = 1.6, LOBE_R = 1.6, LOBE_R_SPREAD = 1.5, LOBE_H = 0.55, LOBE_H_SPREAD = 0.65;

/* The deep forest: the oldest trees, once there are too many to draw one by one, stand as
 * bands of canopy receding into the haze. More bands the further back the forest goes.
 * A landscape can break each band into pieces (`deepChunks`), shape a piece's crowns
 * column by column (`deepEdge`, 0 flat to 1 full height) and hang something under it
 * (`deepUnder`); without them a band runs the whole width. */
function deepForest(env, lg) {
  const th = env.theme, { W, u } = env, d = env.deep, paint = painter(lg);
  const far = d.base;  // just beyond the horizon, so it reads as forest carrying on over the hill
  const EP = AF.envOf(env).pals || {};
  // `base` replaces an environment's tree colours wholesale; the distant bands are trees too
  const pal = EP.round || (EP.rounds && EP.rounds[0]) || (EP.base && EP.base.round) || PXT.round;
  const haze = hex(th.haze), tint = th.tint ? hex(th.tint) : null;
  const R = rng((env.data.forestSeed || 11) ^ 0x5eed);
  const land = AF.landOf(env);
  d.boxes = [];  // where it really ends up, so only that is hoverable

  for (let k = d.bands - 1; k >= 0; k--) {  // furthest band first, so nearer ones sit in front
    const hz = AF.deepHaze(th, k);
    const tone = c => { const q = tint ? mix(c, tint, th.tintAmt) : c; return rgb(mix(q, haze, hz)); };
    const c1 = tone(pal[1]), c2 = tone(pal[2]), rim = tone(th.snow ? SNOW_L : pal[3]);
    const base = Math.round(far - k * AF.DEEP.rise * u), crown = (AF.DEEP.crown + k * AF.DEEP.step) * u;
    const chunks = land.deepChunks ? land.deepChunks(R, k, W) : [[0, W - 1]];
    for (const [x0, x1] of chunks) {
      // a row of distant crowns: overlapping lobes, so the skyline reads as trees, not a hedge
      const top = new Float32Array(Math.max(1, Math.round(x1 - x0) + 1)).fill(base);
      // crowns have to sit closer together on a narrow panel, or the band comes apart
      for (let cx = x0 - 2; cx <= x1 + 2; cx += Math.max(1, (LOBE_GAP + R() * LOBE_GAP) * u)) {
        const r = (LOBE_R + R() * LOBE_R_SPREAD) * u, h = crown * (LOBE_H + R() * LOBE_H_SPREAD);
        for (let x = Math.ceil(cx - r); x <= cx + r; x++) {
          const i = Math.round(x - x0); if (i < 0 || i >= top.length) continue;
          top[i] = Math.min(top[i], base - h * Math.sqrt(Math.max(0, 1 - ((x - cx) / r) ** 2)));
        }
      }
      for (let i = 0; i < top.length; i++) {
        const x = Math.round(x0) + i;
        const edge = land.deepEdge ? land.deepEdge(env, i, top.length) : 1;
        const y0 = Math.round(base - (base - top[i]) * edge);
        for (let y = y0; y <= base; y++) paint(y - y0 < 1 ? rim : ((x + y) & 1 ? c2 : c1), x, y);
        if (land.deepUnder) land.deepUnder(env, paint, x, base, i, top.length, edge);
      }
      d.boxes.push({ x0: Math.round(x0), x1: Math.round(x1), y0: Math.round(base - crown), y1: base });
    }
  }
}

Object.assign(AF.pixel, { fogVeil, ridges, drawGround, groundDetails, deepForest });
})();

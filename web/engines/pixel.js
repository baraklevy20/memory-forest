/* Memory Forest — pixel-art engine: sky, ground, tree sprites, the deep forest and the
 * water machinery the landscapes share. Environments, landscapes and landmarks hook in
 * from their own files. Everything is drawn on a low-resolution canvas and scaled up. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hashStr, hex, mix, mixHex, rgb, layer, B4, TAU } = AF.u;
const { SEEDLING, SAPLING, YOUNG, MATURE, OLD, ANCIENT } = AF.STAGE;
/* one pixel of colour on a low-res layer (coordinates here are already whole numbers) */
const painter = g => (c, x, y, w = 1, h = 1) => { g.fillStyle = rgb(c); g.fillRect(x, y, w, h); };
AF.painter = painter;  // landmarks and landscapes paint with it too
const H6 = a => a.map(hex);

const PXT = {
  round: H6(['#1c2b22', '#2d4a33', '#3f6a3c', '#5f8c4a', '#8fb35e']),
  pine: H6(['#14231e', '#1f3d30', '#2d5a3f', '#44784c', '#6a9a5a']),
  ancient: H6(['#16261c', '#24422c', '#356232', '#548a3a', '#a2c464']),
  ancientPine: H6(['#0f1f19', '#1a3529', '#26503a', '#3c6e48', '#6f9e5c']),
  sick: [null, H6(['#3d3f1e', '#5a6a2e', '#8a9338', '#b3ad4c', '#d6c86a']), H6(['#4a2a18', '#7a4a28', '#b26a32', '#d8924a', '#efbb6a']), H6(['#3e2c18', '#6a4a26', '#9a7036', '#c89a4a', '#e6c070'])],
  bark: { l: hex('#7a5c42'), m: hex('#5e4532'), d: hex('#3e2e22') },
  soil: hex('#5a4030'), soilL: hex('#74553b'), stem: hex('#6d9a4a'), leaf: hex('#8fc25a'), leafL: hex('#bfe07a')
};
const GOLD = hex('#c9d97c');
const SNOW_W = hex('#f4f7fb'), SNOW_L = hex('#d6dfeb');

const cache = new Map();  // built sprites, keyed by look; cleared when the panel resizes
AF.clearCaches = () => cache.clear();

/* crown shapes fill a tone map (0 outline .. 4 highlight) */
function roundCrown(tone, W, H, w, top, ch, cx, blobsN, R, hole, pick) {
  const rx = w / 2, ry = ch / 2, ccx = cx + 0.5, ccy = top + ry - 0.5;
  const blobs = [{ x: ccx, y: ccy, sx: rx * 0.86, sy: ry * 0.86 }];
  for (let k = 0; k < blobsN; k++) { const a = -Math.PI / 2 + (k / blobsN) * TAU + R() * 0.6; blobs.push({ x: ccx + Math.cos(a) * rx * 0.5, y: ccy + Math.sin(a) * ry * 0.5, sx: rx * 0.52, sy: ry * 0.52 }); }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const px = x + 0.5, py = y + 0.5; let best = -9;
    for (const b of blobs) { const nx = (px - b.x) / b.sx, ny = (py - b.y) / b.sy; if (nx * nx + ny * ny <= 1) best = Math.max(best, -(nx * 0.6 + ny * 0.8)); }
    if (best === -9) continue; if (hole && R() < hole) continue;
    tone[y * W + x] = pick(0.55 * best + 0.45 * -((px - ccx) / rx * 0.5 + (py - ccy) / ry * 0.7) + (R() - 0.5) * 0.3);
  }
}
function pineCrown(tone, W, w, top, ch, cx, tiers, R, hole, pick) {
  for (let y = top; y < top + ch; y++) {
    const p = (y - top + 0.5) / ch, tp = (p * tiers) % 1, hw = (w / 2) * (0.18 + 0.82 * p) * (0.5 + 0.5 * tp);
    const under = tp > 1 - 1.6 / (ch / tiers) && y < top + ch - 1;  // the shade under each skirt
    for (let x = 0; x < W; x++) { const dx = x + 0.5 - (cx + 0.5); if (Math.abs(dx) > hw) continue; if (hole && R() < hole) continue;
      const v = pick(-(dx / Math.max(hw, 1)) * 0.7 + (tp - 0.5) * 0.35 + (R() - 0.5) * 0.3);
      tone[y * W + x] = under ? Math.max(1, v - 2) : v; }
  }
}
/* a broadleaf crown shades its own underside where it hangs over the trunk */
function crownShade(tone, W, H, w, cx) {
  for (let x = 0; x < W; x++) {
    if (Math.abs(x - cx) >= w * 0.34) continue;
    let low = -1; for (let y = 0; y < H; y++) if (tone[y * W + x] >= 0) low = y;
    if (low < 2) continue;
    if (tone[(low - 1) * W + x] >= 0) tone[(low - 1) * W + x] = 1;
    if (tone[(low - 2) * W + x] >= 0) tone[(low - 2) * W + x] = Math.min(tone[(low - 2) * W + x], 2);
  }
}
/* ---------- tree sprites ---------- */
const SEEDLING_W = 7;  // a seedling is the same small sprite at any size
// a crown's width as a share of the tree's height, by crown size (small, medium, large)
const PINE_W = [0.46, 0.54, 0.62], BROAD_W = [0.66, 0.8, 0.94], ANCIENT_W = [0.9, 0.98, 1.04];
const ANCIENT_PINE_W = 1.1;  // an ancient conifer is this much wider again
// the trunk's height as a share of the tree's: a sapling's, a conifer's, a broadleaf's
const SAPLING_TRUNK = 0.45, PINE_TRUNK = 0.2, BROAD_TRUNK = 0.32;
const THICK_TRUNK_H = 16;  // a tree this tall gets a two-pixel trunk even before it is old
// sprites are cached per quarter step of haze; a faded tree on a deck screen is the only
// one that gets as far as FADED_HZQ (core.js's DIM_HAZE of 1.5, times HAZE_STEPS)
const HAZE_STEPS = 4, FADED_HZQ = 6;
const DYING_HOLES = 0.18;  // a crown at the worst health is this full of holes
// the share of a crown that yellows, by health
const SICK_SHARE = [0, 0.38, 0.62, 0.85];

function sprite(t, h, hzq, env) {
  const th = env.theme, sp = env.mood.special;
  const spec = AF.ENVS[sp] || {}, tree = spec.tree || {};
  const EP = spec.pals || {}, P = EP.base || PXT;
  const bark = EP.bark || P.bark;
  const key = [env.spriteKey, t.stage, t.kind, t.size, t.health, t.variant, t.seed, h, hzq].join('|');
  const hit = cache.get(key); if (hit) return hit;
  const R = rng(hashStr([t.stage, t.kind, t.size, t.health, t.variant, h].join('|')));
  const hz = hzq * th.hzStep, pine = t.kind === 1 && t.stage >= YOUNG, ancient = t.stage === ANCIENT;
  const tint = th.tint ? hex(th.tint) : null, haze = hex(th.haze), rim = th.rim ? hex(th.rim) : null;
  let w = 0;
  if (t.stage === SEEDLING) w = SEEDLING_W;
  else if (tree.width) w = tree.width({ t, h, pine, ancient, env }) || 0;
  if (!w) { const f = pine ? PINE_W[t.size] * (ancient ? ANCIENT_PINE_W : 1) : (ancient ? ANCIENT_W : BROAD_W)[t.size]; w = Math.max(3, Math.round(h * f)); if (w % 2 === 0) w++; }
  const W = w + 4, H = (t.stage === SEEDLING ? SEEDLING_W : h) + 2;
  const [cv, g] = layer(W, H), img = g.createImageData(W, H), d = img.data;
  // a tree faded out on a deck screen goes cool grey, not into a warm haze where it would
  // read as yellowing
  const faded = hzq >= FADED_HZQ, FADE = [142, 152, 168];
  const put = (x, y, col) => {
    if (x < 0 || y < 0 || x >= W || y >= H) return;
    let c = tint ? mix(col, tint, th.tintAmt) : col;
    if (faded) { const l = c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11; c = mix(mix([l, l, l], FADE, 0.45), haze, 0.2); }
    else if (hz) c = mix(c, haze, hz);
    const i = (y * W + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255;
  };
  const cx = Math.floor(W / 2), base = H - 1;
  if (t.stage === SEEDLING) {
    const leaf = EP.leaf || PXT.leaf, leafL = EP.leafL || PXT.leafL, stem = EP.stem || PXT.stem;
    for (let x = cx - 2; x <= cx + 2; x++) put(x, base, PXT.soil);
    for (let x = cx - 1; x <= cx + 1; x++) put(x, base - 1, th.snow ? SNOW_L : PXT.soilL);
    put(cx, base - 2, stem); put(cx, base - 3, stem); put(cx, base - 4, stem);
    put(cx - 1, base - 4, leaf); put(cx - 2, base - 5, leaf); put(cx - 1, base - 5, leafL);
    put(cx + 1, base - 5, leaf); put(cx + 2, base - 6, leafL); put(cx + 1, base - 6, leafL);
    g.putImageData(img, 0, 0); cache.set(key, cv); return cv;
  }
  const tone = new Int8Array(W * H).fill(-1), inside = (x, y) => x >= 0 && y >= 0 && x < W && y < H && tone[y * W + x] >= 0;
  const hole = t.health === 3 ? DYING_HOLES : 0, pick = l => l > 0.5 ? 4 : l > 0.15 ? 3 : l > -0.3 ? 2 : 1;
  let top = 1, ch = 0;
  // everything an environment needs to draw a tree of its own; the forest's own tree is
  // the default below
  const c = { t, h, env, th, pine, ancient, W, H, w, cx, base, tone, put, pick, R, inside, bark, P, hole, top, ch };
  const shape = tree.body && tree.body(c);
  if (shape) { top = shape.top != null ? shape.top : top; ch = shape.ch || 0; }
  else {
    const trunkH = t.stage === SAPLING ? Math.max(3, Math.round(h * SAPLING_TRUNK)) : Math.round(h * (pine ? PINE_TRUNK : BROAD_TRUNK));
    const tw = ancient ? 3 : t.stage >= OLD || h >= THICK_TRUNK_H ? 2 : 1, tx0 = cx - Math.floor(tw / 2);
    Object.assign(c, { trunkH, tw, tx0 });
    if (!(tree.trunk && tree.trunk(c))) {
      for (let y = base - trunkH; y <= base; y++) for (let x = tx0; x < tx0 + tw; x++) {
        let col = tw > 1 && x === tx0 ? bark.l : tw > 1 && x === tx0 + tw - 1 ? bark.d : bark.m;
        if (y <= base - trunkH + 3) col = bark.d;  // in the crown's shade
        else if (tw === 1 && y & 1) col = bark.l;
        put(x, y, col);
      }
      if (t.stage >= MATURE && !ancient) { put(tx0 - 1, base, bark.d); put(tx0 + tw, base, bark.d); }  // roots
      if (ancient) { put(tx0 - 1, base, bark.d); put(tx0 + tw, base, bark.d); put(tx0 - 2, base, bark.d); put(tx0 + tw + 1, base, bark.d); put(tx0 - 1, base - 1, bark.m); put(tx0 + tw, base - 1, bark.d); }
    }
    ch = pine ? h - trunkH + 1 : h - trunkH + 2;
    c.ch = ch;
    // the environment gets first refusal on both kinds of crown; returning false leaves
    // the forest's own conifer or broadleaf in place
    if (tree.crown && tree.crown(c)) { /* drawn by the environment */ }
    else if (pine) pineCrown(tone, W, w, top, ch, cx, t.stage >= OLD ? 4 : t.stage >= MATURE ? 3 : 2, R, hole, pick);
    else { roundCrown(tone, W, H, w, top, ch, cx, ancient ? 7 : t.stage >= MATURE ? 5 : 3, R, hole, pick); crownShade(tone, W, H, w, cx); }
  }
  // yellowing comes in 2x2 clusters so it reads as yellow branches, not speckle
  const pSick = SICK_SHARE[t.health], sr = hashStr(t.variant + '|' + t.size + '|' + t.seed);
  const sick = (x, y) => hashStr((x >> 1) + ',' + (y >> 1) + ',' + sr) / 4294967296 < pSick;
  let roundPal = EP.rounds ? EP.rounds[t.seed % EP.rounds.length] : EP.round || (ancient ? PXT.ancient : P.round);
  let pinePal = EP.pine || (ancient ? PXT.ancientPine : P.pine);
  const pals = tree.palette && tree.palette(c);
  if (pals) { roundPal = pals.round || roundPal; pinePal = pals.pine || pinePal; }
  const sickPal = (tree.sickPalette && tree.sickPalette(c)) || P.sick[t.health];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let tn = tone[y * W + x]; if (tn < 0) continue;
    if (!inside(x + 1, y) || !inside(x, y + 1)) tn = 0;
    const pal = t.health && sick(x, y) ? sickPal : (pine ? pinePal : roundPal);
    let col = pal[tn];
    if (th.flat && tn === 4 && (x + y) & 1) col = pal[3];
    if (ancient && !pine && tn === 4 && !inside(x, y - 1) && (x + y) % 3 !== 0 && !EP.round && !EP.rounds && !t.health) col = GOLD;
    if (EP.speck && tn >= 3 && hashStr(x + ',' + y + ',' + sr) % 7 === 0) col = EP.speck;
    if (tree.pixel) col = tree.pixel(col, { x, y, tn, sr, pal, c }) || col;
    if (rim && tn >= 1 && !inside(x - 1, y) && y < top + (ch || h) * 0.75) col = mix(col, rim, 0.7);
    if (th.snow) {
      if (!inside(x, y - 1)) col = SNOW_W;
      else if (!inside(x, y - 2) && (th.deepSnow || (x + y) & 1)) col = SNOW_L;
      else if (th.deepSnow && !inside(x, y - 3) && (x + y) & 1) col = SNOW_L;
    }
    put(x, y, col);
  }
  g.putImageData(img, 0, 0); cache.set(key, cv); return cv;
}

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

// the rainbow: centred RAINBOW.x across, its centre RAINBOW.drop below the horizon, the
// inner edge RAINBOW.r out, six bands RAINBOW.band wide (all in env.u), fading out
// RAINBOW.fade above the horizon and never more than RAINBOW.strength opaque
const RAINBOW = { x: 0.42, drop: 26, r: 62, band: 1.6, strength: 0.35, fade: 18 };

/* sky: dithered bands, sun or phased moon (soft in fog), rainbow and striped retro sun;
 * an environment paints its own sky through skyPixel and sky */
function drawSky(env) {
  const th = env.theme, { W, H, u, hor } = env;
  const [sky, sg] = layer(W, H), si = sg.createImageData(W, H), sd = si.data, stops = th.sky.map(hex), o = th.orb;
  const ox = o ? W * o.x : 0, oy = o ? H * o.y : 0, orr = o ? o.r * u : 0, oc = o ? hex(o.c) : null, oc2 = o && o.c2 ? hex(o.c2) : null, og = o ? hex(o.glow || o.c) : null;
  let shadowX = null;
  if (o && o.kind === 'moon' && o.phase != null && !o.full) { const k = o.phase * 2; shadowX = ox + (k <= 1 ? -2 * orr * k : 2 * orr * (2 - k)); }
  const rb = th.rainbow ? { x: W * RAINBOW.x, y: hor + RAINBOW.drop * u, r0: RAINBOW.r * u, cols: H6(['#e8837a', '#f0b27a', '#f1dc86', '#9fd49a', '#8fb8e0', '#b5a0d8']) } : null;
  const R = rng(91);
  // an environment may paint into the sky itself: behind the orb, and in front of it
  const spec = AF.envOf(env), skyPixel = spec.skyPixel, skyCtx = skyPixel ? { W, H, hor, u, th, B4, R } : null;
  const skyEnd = AF.landOf(env).skyEnd ? AF.landOf(env).skyEnd(env) : hor - 1;
  // the retro sun's bands: cut out of its lower half only, thin near the middle and
  // widening as they fall. Measured from a whole-pixel centre so the bands come out the
  // same thickness whatever size the panel is.
  const oyR = Math.round(oy), cutAt = y => {
    if (!o || !o.stripes || y <= oyR) return false;
    const deep = (y - oyR) / orr;
    return deep > 0.05 && (y - oyR) % 4 < Math.min(3, 1 + Math.floor(deep * 2.2));
  };
  for (let y = 0; y < H; y++) {
    const tt = Math.min(1, y / skyEnd) * (stops.length - 1), i0 = Math.min(stops.length - 2, Math.floor(tt)), f = tt - i0;
    const cut = cutAt(y);
    for (let x = 0; x < W; x++) {
      let c = f * 16 > B4[(y % 4) * 4 + x % 4] + 0.5 ? stops[i0 + 1] : stops[i0];
      if (skyPixel) c = skyPixel(c, x, y, skyCtx, 'behind') || c;
      if (rb && y < hor) { const dd = Math.hypot(x - rb.x, y - rb.y) - rb.r0, bw = RAINBOW.band * u, bi = Math.floor(dd / bw); if (bi >= 0 && bi < rb.cols.length) c = mix(c, rb.cols[bi], RAINBOW.strength * Math.min(1, (hor - y) / (RAINBOW.fade * u))); }
      if (o) {
        const dist = Math.hypot(x - ox, y - oy);
        if (dist < orr) {
          const shadowed = shadowX !== null && Math.hypot(x - shadowX, y - oy) < orr;
          const edge = o.soft && dist > orr * 0.7 && B4[(y % 4) * 4 + x % 4] < (dist - orr * 0.7) / (orr * 0.3) * 16;
          // a band is the sky showing through the sun, so it is simply left unpainted
          if (!cut && !shadowed && !edge) c = oc2 ? mix(oc, oc2, (y - (oy - orr)) / (2 * orr)) : oc;
          else if (shadowed) c = mix(c, oc, 0.08);
        } else if (o.halo && dist < orr + o.halo * u && (x + y) % 2 === 0) c = mix(c, og, 0.55);
      }
      if (skyPixel) c = skyPixel(c, x, y, skyCtx, 'over') || c;
      const i = (y * W + x) * 4; sd[i] = c[0]; sd[i + 1] = c[1]; sd[i + 2] = c[2]; sd[i + 3] = 255;
    }
  }
  sg.putImageData(si, 0, 0);
  if (spec.sky) spec.sky(env, sg, rng(env.data.forestSeed || 5));
  return sky;
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
}

// the deep forest's distant crowns, in env.u: one every LOBE_GAP (plus up to as much
// again), LOBE_R across (plus up to LOBE_R_SPREAD), LOBE_H of the band's height (plus up
// to LOBE_H_SPREAD); chunks taper over ISLAND_TAPER and hang ISLAND_ROCK deep, more mid-chunk
const LOBE_GAP = 1.6, LOBE_R = 1.6, LOBE_R_SPREAD = 1.5, LOBE_H = 0.55, LOBE_H_SPREAD = 0.65;
const ISLAND_TAPER = 6, ISLAND_ROCK = 3, ISLAND_ROCK_MID = 4;

/* The deep forest: the oldest trees, once there are too many to draw one by one, stand as
 * bands of canopy receding into the haze. More bands the further back the forest goes.
 * A landscape with `deepChunks` breaks them into floating pieces behind the nearest ones. */
function deepForest(env, lg) {
  const th = env.theme, { W, u } = env, d = env.deep, paint = painter(lg);
  const far = d.base;  // just beyond the horizon, so it reads as forest carrying on over the hill
  const EP = AF.envOf(env).pals || {};
  // `base` replaces an environment's tree colours wholesale; the distant bands are trees too
  const pal = EP.round || (EP.rounds && EP.rounds[0]) || (EP.base && EP.base.round) || PXT.round;
  const haze = hex(th.haze), tint = th.tint ? hex(th.tint) : null;
  const R = rng((env.data.forestSeed || 11) ^ 0x5eed);
  const deepChunks = AF.landOf(env).deepChunks, floating = !!deepChunks;
  const rock = hex(mixHex('#8a6a50', th.haze, 0.45)), rockD = mix(rock, [0, 0, 0], 0.25);
  d.boxes = [];  // where it really ends up, so only that is hoverable

  for (let k = d.bands - 1; k >= 0; k--) {  // furthest band first, so nearer ones sit in front
    const hz = AF.deepHaze(th, k);
    const tone = c => { const q = tint ? mix(c, tint, th.tintAmt) : c; return rgb(mix(q, haze, hz)); };
    const c1 = tone(pal[1]), c2 = tone(pal[2]), rim = tone(th.snow ? SNOW_L : pal[3]);
    const base = Math.round(far - k * AF.DEEP.rise * u), crown = (AF.DEEP.crown + k * AF.DEEP.step) * u;
    const chunks = floating ? deepChunks(R, k, W) : [[0, W - 1]];
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
        const edge = floating ? Math.min(1, Math.min(i, top.length - 1 - i) / (ISLAND_TAPER * u)) : 1;  // chunks taper at the ends
        const y0 = Math.round(base - (base - top[i]) * edge);
        for (let y = y0; y <= base; y++) paint(y - y0 < 1 ? rim : ((x + y) & 1 ? c2 : c1), x, y);
        if (floating) {
          const deep = Math.round((ISLAND_ROCK + ISLAND_ROCK_MID * edge) * u);
          for (let y = base + 1; y <= base + deep; y++) paint((y - base) % 4 === 0 || i < top.length * 0.3 ? rockD : rock, x, y);
        }
      }
      d.boxes.push({ x0: Math.round(x0), x1: Math.round(x1), y0: Math.round(base - crown), y1: base });
    }
  }
}
const FLOW_LINES = 14;
// the sun or moon on a still lake: a column of glints, each lit this often
const GLITTER_CHANCE = 0.7;

/* the surface: ripples, flow lines downstream, and the sun or moon lying on a still lake */
AF.drawWater = function (g, env, t) {
  const L = env.water; if (!L) return;
  const W = env.W, still = env.theme.frozen;
  for (let j = 0; j < L.lh; j++) { const off = still ? 0 : Math.round(Math.sin(t * 0.9 + j * 0.7) * (j < 3 ? 0 : 1 + j / L.lh)); g.drawImage(L.rf, 0, j, W, 1, off, L.y0 + j, W, 1); }
  if (L.river && !still) {  // flow lines drifting downstream
    const R = rng(29); g.fillStyle = 'rgba(255,255,255,.35)';
    for (let k = 0; k < FLOW_LINES; k++) { const y = L.y0 + 1 + Math.floor(R() * (L.lh - 2)), len = 3 + Math.floor(R() * 5), x = Math.round(((R() * W + t * (6 + R() * 6)) % (W + len)) - len); g.fillRect(x, y, len, 1); }
  }
  const o = env.theme.orb;
  if (o && !still && !L.river) { const ox = Math.round(W * o.x), R = rng(Math.floor(t * 2)); g.fillStyle = o.kind === 'moon' ? 'rgba(238,241,248,.75)' : 'rgba(255,240,200,.7)';
    for (let j = 1; j < L.lh; j += 2) { const hw = 1 + Math.round(j * 0.35); for (let k = 0; k < 2; k++) if (R() < GLITTER_CHANCE) g.fillRect(ox - hw + Math.round(R() * hw * 2), L.y0 + j, 1 + (R() < 0.3 ? 1 : 0), 1); } }
};

/* Water in front of the forest, reflecting what stands behind it. A landscape says where
 * it sits ({ y0, deep, shore, step, tint }) and whether it flows; an environment can lay
 * its own surface on top of the result. */
AF.buildWater = function (env, o) {
  const { W, H } = env, river = !!o.river;
  const y0 = Math.round(H * o.y0), lh = Math.round(H * o.deep) - (river ? 0 : y0), shore = Math.round(H * o.shore);
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
  if (river) {  // the far bank below the river
    const bank = hex(env.theme.g1), R = rng(3);
    for (let y = y0 + lh; y < H; y++) for (let x = 0; x < W; x++) { lg.fillStyle = rgb(mix(bank, [0, 0, 0], y === y0 + lh ? 0.25 : 0)); lg.fillRect(x, y, 1, 1); }
    lg.fillStyle = env.theme.grass; for (let k = 0; k < W * 0.1; k++) lg.fillRect(Math.round(R() * W), y0 + lh + 1 + Math.round(R() * (H - y0 - lh - 1)), 1, 1);
  }
  env.water = { y0, lh, rf, river };
};

// the light comes from the other side once the sun or moon is past this far across
const FLIP_LIGHT_X = 0.55;
// in fog, the land already drawn is veiled again from depth FOG_VEIL_FROM, every
// FOG_VEIL_STEP, up to FOG_VEIL_TO, by FOG_VEIL_AMT unless the theme says otherwise
const FOG_VEIL_FROM = 0.08, FOG_VEIL_STEP = 0.12, FOG_VEIL_TO = 0.85, FOG_VEIL_AMT = 0.2;
// a lightning flash lifts the land this far towards white
const FLASH_LIFT = 0.35;

AF.engines.pixel = {
  prepare(env) {
    const th = env.theme;
    const spec = AF.envOf(env);
    if (spec.prepare) spec.prepare(env, th);
    env.quantize = spec.quantize || null;
    // the landscape has the last word on how much room it takes at the front
    const land = AF.landOf(env);
    if (land.prepare) land.prepare(env);

    env.flipLight = !!(th.orb && th.orb.x > FLIP_LIGHT_X && spec.flipLight !== false);
    env.ridges = ridges(env);
    env.spriteKey = [env.mood.special, env.mood.time, env.mood.weather, th.snow ? 'w' : '', th.deepSnow ? 'W' : '', th.flat ? 'f' : ''].join('/');
  },
  sky: drawSky,
  steps(env) {
    const th = env.theme, { W, H, u } = env, steps = [lg => drawGround(env, lg)];
    // a landscape with an open horizon (`noDeep`) has nowhere for a distant treeline
    if (env.deep && !AF.landOf(env).noDeep) steps.push(lg => deepForest(env, lg));
    let nextFog = th.fog ? FOG_VEIL_FROM : Infinity;
    for (const p of env.placed) {
      if (th.fog && p.it.depth >= nextFog && nextFog < FOG_VEIL_TO) { steps.push(lg => fogVeil(lg, W, H, p.y, th.fog, th.fogAmt || FOG_VEIL_AMT)); nextFog += FOG_VEIL_STEP; }
      if (p.it.pond) { steps.push(lg => AF.drawPond(lg, env, p)); continue; }
      steps.push(lg => {
        const h = Math.max(3, Math.round(AF.STAGE_H[p.it.stage] * u * p.s)), spr = sprite(p.it, h, Math.round(p.hz * HAZE_STEPS), env);
        groundDetails(env, lg, p, spr.width - 4);
        const x0 = Math.round(p.x - spr.width / 2), y0 = Math.round(p.y - spr.height + 1);
        if (env.flipLight) { lg.save(); lg.translate(x0 + spr.width, y0); lg.scale(-1, 1); lg.drawImage(spr, 0, 0); lg.restore(); } else lg.drawImage(spr, x0, y0);
        if (env.afterItem) env.afterItem(lg, p);
      });
    }
    return steps;
  },
  post(env) {
    const { W, H } = env;
    if (env.theme.lightning) {  // a brighter copy of the land, shown while lightning flashes
      const [lit, lg] = layer(W, H); lg.drawImage(env.land, 0, 0);
      const img = lg.getImageData(0, 0, W, H), d = img.data;
      for (let i = 0; i < d.length; i += 4) if (d[i + 3]) { d[i] += (235 - d[i]) * FLASH_LIFT; d[i + 1] += (240 - d[i + 1]) * FLASH_LIFT; d[i + 2] += (255 - d[i + 2]) * FLASH_LIFT; }
      lg.putImageData(img, 0, 0); env.landLit = lit;
    }
    const land = AF.landOf(env);
    if (land.post) land.post(env);  // a lake or a river builds its reflection here
    env.lake = env.water && !env.water.river ? env.water : null;
  },
  frameBack(g, env, t) {
    const land = AF.landOf(env);
    if (land.frameBack) land.frameBack(g, env, t);  // e.g. a sea of cloud far below
  },
  frame(g, env, t) {
    const land = AF.landOf(env);
    if (land.frame) land.frame(g, env, t);          // water, glints on the sea
    const mk = AF.markOf(env);
    if (mk.frame) mk.frame(g, env, t);              // falling water, a sweeping beam
    if (land.frameFront) land.frameFront(g, env, t);  // and what falls in front of it all
    const spec = AF.envOf(env);
    if (spec.frame) spec.frame(g, env, t);
  }
};
})();

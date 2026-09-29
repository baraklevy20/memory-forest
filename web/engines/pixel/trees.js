/* Memory Forest — pixel engine, part 1: the tree sprites, their palettes, and the painter and
 * sprite cache the other parts share. Loaded before the rest of web/engines/pixel/. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hashStr, hex, mix, rgb, layer, TAU } = AF.u;
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
// how many pixels right of a placed tree's centre its trunk ends, for whatever sits beside it
AF.trunkRight = function (p, env) {
  const h = Math.max(3, Math.round(AF.STAGE_H[p.it.stage] * env.u * p.s));
  const tw = p.it.stage === ANCIENT ? 3 : p.it.stage >= OLD || h >= THICK_TRUNK_H ? 2 : 1;
  return tw - Math.floor(tw / 2);
};
// sprites are cached per quarter step of haze; a faded tree on a deck screen is the only
// one that gets as far as FADED_HZQ (layout.js's DIM_HAZE of 1.5, times HAZE_STEPS)
const HAZE_STEPS = 4, FADED_HZQ = 6;
const DYING_HOLES = 0.18;  // a crown at the worst health is this full of holes
// the share of a crown that yellows, by health
const SICK_SHARE = [0, 0.38, 0.62, 0.85];

/* A tree Wild's fire has caught (`burn`, 1 while it blazes, less for each day studied
 * since; web/events/fire.js draws the flames): the fire has taken one side of it (AF.burnSide),
 * reaching REACH_MOST of the way across at first and REACH_LEAST the last day, so the tree
 * stays itself. That side goes to char in 2x2 clusters, glowing with embers while the fire is
 * high, with a singed brown edge where it meets the green. Any environment's tree, trunk and all. */
const REACH_LEAST = 0.18, REACH_MOST = 0.42, RAGGED = 0.22, EMBERS_FROM = 0.5, EMBERS = 0.08;
const EMBER = [hex('#e0592a'), hex('#ffb347')], SINGE = [hex('#7a4a28'), hex('#9a6236')];
AF.burnStep = burn => Math.round((burn || 0) * 7);  // a step a day studied (events.FIRE_HEAL_DAYS)
AF.burnSide = seed => (seed >> 3) & 1;  // 0: from the sprite's left, 1: from its right
AF.burnReach = burn => REACH_LEAST + (REACH_MOST - REACH_LEAST) * burn;
function scorch(d, W, H, burn, seed) {
  const reach = AF.burnReach(burn), side = AF.burnSide(seed);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4;
    if (!d[i + 3]) continue;
    // how far into the tree from the burning side, a little further near the top, ragged in 2x2 clusters
    const u = (side ? W - 1 - x : x) / W, v = y / H;
    const at = u + (v - 0.5) * 0.15 + (hashStr('burn,' + (x >> 1) + ',' + (y >> 1) + ',' + seed) / 4294967296 - 0.5) * RAGGED;
    if (at >= reach + 0.08) continue;
    const l = d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11;
    let c = at >= reach ? SINGE[(x + y) & 1] : [18 + l * 0.2, 15 + l * 0.16, 13 + l * 0.14];
    if (at < reach && burn >= EMBERS_FROM && hashStr('ember,' + x + ',' + y + ',' + seed) / 4294967296 < EMBERS * burn) c = EMBER[(x + y) & 1];
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2];
  }
}

function sprite(t, h, hzq, env) {
  const th = env.theme, sp = env.mood.special;
  const spec = AF.ENVS[sp] || {}, tree = spec.tree || {};
  const EP = spec.pals || {}, P = EP.base || PXT;
  const bark = EP.bark || P.bark;
  const burn = AF.burnStep(t.burn) / 7;
  const key = [env.spriteKey, t.stage, t.kind, t.size, t.health, t.variant, t.seed, h, hzq, burn].join('|');
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
    if (burn) scorch(d, W, H, burn, t.seed);
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
  if (burn) scorch(d, W, H, burn, t.seed);
  g.putImageData(img, 0, 0); cache.set(key, cv); return cv;
}

AF.pixel = { PXT, SNOW_L, H6, sprite, HAZE_STEPS };
})();

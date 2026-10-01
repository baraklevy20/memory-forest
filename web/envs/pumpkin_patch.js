/* Memory Forest - the pumpkin patch environment.
 * Everything this environment is lives here: delete it and pumpkin_patch.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * An orange October dusk streaked with thin cloud, a huge harvest moon lifted clear of the
 * tree line, and a witch (her cat riding behind, eyes aglow) flying across it on her broom,
 * with bats looping round it, and on the left a crooked hilltop with a lone dead tree. Crooked black trees with lumpy canopies and hooked bare
 * branches, and lopsided firs whose tips bend over like a witch's hat, all rimmed on the
 * moon side. Jack-o'-lanterns of every shape, colour and carved face stand at the nearer
 * trees' feet and out on the open ground, each laying a dithered pool of light, and a few of
 * the laughing ones keep bursting into chuckles.
 * Dawn is pink with a paling moon, day a lilac autumn afternoon with a ghost of a moon and
 * unlit pumpkins, night deep violet with a cream moon and stars. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rgb, rng, hashStr, layer, B4 } = AF.u;
const H6 = a => a.map(hex);
const hashN = (...a) => hashStr(a.join(',')) / 4294967296;  // a steady random number in [0, 1)
const bayer = (x, y) => B4[(y & 3) * 4 + (x & 3)];

/* ---------- palettes ----------
 * tones run outline, shade, mid, lit, highlight. The crowns are near-black plum and wine,
 * the conifers a blue-black, so forgetting's yellow shows loudly on either. */
const HOUR_P = {
  dusk: { rounds: [H6(['#040106', '#0a040c', '#130814', '#220e24', '#381a3a']), H6(['#050106', '#0c040a', '#160812', '#26101e', '#3e1a30'])],
          pine: H6(['#030408', '#080a12', '#0e121c', '#161c2a', '#242c40']),
          bark: { l: hex('#1e0a12'), m: hex('#10050b'), d: hex('#060205') }, rim: hex('#ff7a48'), rim2: hex('#b8403a') },
  night: { rounds: [H6(['#040208', '#0a0612', '#120a1c', '#1c1028', '#2c1a3c']), H6(['#050206', '#0c0610', '#160a18', '#221024', '#341a36'])],
           pine: H6(['#020308', '#060812', '#0a0e1c', '#121828', '#1e2840']),
           bark: { l: hex('#221428'), m: hex('#100a14'), d: hex('#050308') }, rim: hex('#ffc890'), rim2: hex('#a0607a') },
  dawn: { rounds: [H6(['#0e0812', '#1c1020', '#2a182e', '#3a2240', '#523052']), H6(['#100810', '#20101a', '#301824', '#422232', '#5a2e40'])],
          pine: H6(['#080a12', '#10141e', '#18202c', '#222c3c', '#344256']),
          bark: { l: hex('#3e2830'), m: hex('#24141c'), d: hex('#10080c') }, rim: hex('#ffa8a0'), rim2: hex('#b86a80') },
  day: { rounds: [H6(['#1a0e18', '#2e1a28', '#442636', '#5c3446', '#7a4658']), H6(['#1c0e14', '#321a22', '#4a2630', '#62343e', '#824852'])],
         pine: H6(['#0e1218', '#1a2028', '#26303a', '#34424e', '#4a5c68']),
         bark: { l: hex('#4a3036'), m: hex('#2e1c22'), d: hex('#160c10') }, rim: null, rim2: null },
};
const MINE = new Set();
for (const k in HOUR_P) { HOUR_P[k].rounds.forEach(p => MINE.add(p)); MINE.add(HOUR_P[k].pine); }
const hourOf = th => th.pkHour || 'dusk';

/* ---------- the hours ---------- */
const LOOKS = {
  dusk: { sky: ['#1a0a30', '#3a1044', '#6c1a4c', '#a82c48', '#e2543a', '#ff8e3c'],
          far: '#4a1638', near: '#34102e', farLine: '#9a3448', nearLine: '#5a1c38', g0: '#6a2a48', g1: '#381430', grass: '#7a3450', haze: '#4e1c4a', hzStep: 0.08,
          water: '#4a1a38', clouds: { n: 2, top: '#d8603e', bot: '#6a1c40', a: 230 }, stars: 16, birdC: '#0a0308' },
  night: { sky: ['#05041a', '#0c0826', '#160c34', '#221040', '#321648', '#46204e'],
           far: '#24143a', near: '#1a0e2c', farLine: '#4a2e5e', nearLine: '#2c1a40', g0: '#34204a', g1: '#1a0e26', grass: '#443060', haze: '#2a1640', hzStep: 0.09,
           water: '#1e1234', clouds: { n: 2, top: '#3a2250', bot: '#1e1234', a: 210 }, stars: 70, birdC: '#05030a' },
  dawn: { sky: ['#241c4a', '#43306a', '#6e4480', '#a45a88', '#d8788a', '#f4a494'],
          far: '#5a3a6a', near: '#3e2650', farLine: '#9a6088', nearLine: '#5a3662', g0: '#3a2438', g1: '#1e1020', grass: '#5a3448', haze: '#8a5a7e', hzStep: 0.1,
          water: '#6a4a78', clouds: { n: 3, top: '#f4b8a8', bot: '#9a6a90', a: 230 }, stars: 6, birdC: '#1a1020' },
  day: { sky: ['#6a78a8', '#8a8cb4', '#aca0bc', '#c8b0bc', '#dcbcb4', '#e8c8b0'],
         far: '#8a7896', near: '#6a5a78', farLine: '#a894aa', nearLine: '#7e6a88', g0: '#6a4a4a', g1: '#3e2a2e', grass: '#7a4e4a', haze: '#b4a0b4', hzStep: 0.11,
         water: '#8a8aac', clouds: { n: 4, top: '#f4e6e0', bot: '#bca8b8', a: 235 }, birdC: '#2a1e28' },
};
const clone = o => JSON.parse(JSON.stringify(o));
const MAX_FLIES = 6;  // a few warm fireflies at most, so they never crowd the jack-o'-lanterns

/* ---------- the moon ----------
 * A huge harvest moon on the right, lifted with the tree line so the forest never covers
 * it, drawn in the static sky: a shaded face with dithered seas and a few craters, a
 * two-step dithered halo, and two thin streaks of cloud across its lower half. */
const MOON_X = 0.7, MOON_R = 24;
const MOONS = {
  dusk: { face: ['#fff4d8', '#ffe2a8', '#fcc47c', '#ec9a5a'], sea: '#f4b478', seaD: '#e09a60', glow: '#ff8a48', glow2: '#e05a40', cloud: '#4a1036', cloudL: '#f06a3e' },
  night: { face: ['#fffaec', '#fbeccc', '#ecd4ac', '#cca88a'], sea: '#dcc4a4', seaD: '#c0a08a', glow: '#8a5a8a', glow2: '#4a2a5a', cloud: '#120a20', cloudL: '#5a3a6a' },
  dawn: { face: ['#fff4f4', '#f8e2e8', '#e8c8d8', '#cca8c0'], sea: '#dcbcd0', seaD: '#c4a0b8', glow: '#f0a8b0', glow2: '#b87896', cloud: '#5a3a64', cloudL: '#f4b0a8' },
  day: { face: ['#f4f0f4', '#e8e0ec', '#d8cee0', '#c4bad2'], sea: '#d0c6dc', seaD: '#bcb2cc', glow: null, glow2: null, cloud: null, cloudL: null },
};
function moonAt(env) {
  const { W, H, u } = env, r = Math.round(MOON_R * u), line = AF.treeLine(env);
  const cy = Math.round(Math.max(r + 4 * u, Math.min(H * 0.25, line - r - 4 * u)));
  return { x: Math.round(W * MOON_X), y: cy, r };
}
const CRATERS = [[0.2, 0.42, 0.11], [0.5, -0.12, 0.09], [-0.52, 0.28, 0.08]];
const SEAS = [[-0.3, -0.14, 0.32], [0.02, -0.44, 0.18], [0.3, 0.16, 0.24]];
/* a long thin streak of cloud, tapering at both ends, lit along its underside */
function streak(g, P, y0, x0, x1, thick) {
  y0 = Math.round(y0);
  for (let x = Math.round(x0); x <= x1; x++) {
    const f = (x - x0) / (x1 - x0), taper = Math.pow(Math.sin(f * Math.PI), 0.6);
    const tk = Math.round(thick * taper + (hashN('ck', x >> 2, y0) - 0.5) * 0.9);
    g.fillStyle = P.cloud;
    if (tk < 1) { if (x & 1) g.fillRect(x, y0 + 1, 1, 1); continue; }
    const yt = y0 + Math.round((thick - tk) / 2) + (f > 0.55 ? 1 : 0);
    g.fillRect(x, yt, 1, tk);
    g.fillStyle = P.cloudL; g.fillRect(x, yt + tk, 1, 1);
  }
}
/* low streaks along the afterglow, behind the moon */
function afterglow(env, g) {
  const P = MOONS[hourOf(env.theme)], { W, hor, u } = env;
  if (!P.cloud) return;
  streak(g, P, hor * 0.5, W * 0.03, W * 0.36, 2 * u);
  streak(g, P, hor * 0.66, W * 0.2, W * 0.5, 2.6 * u);
  streak(g, P, hor * 0.79, -4, W * 0.14, 1.6 * u);
  streak(g, P, hor * 0.74, W * 0.46, W * 1.02, 2.2 * u);
}
function paintMoon(env, g) {
  const th = env.theme, m = moonAt(env), P = MOONS[hourOf(th)], { u } = env;
  const px = (c, x, y) => { g.fillStyle = typeof c === 'string' ? c : rgb(c); g.fillRect(x, y, 1, 1); };
  // the halo: an inner ring half-dithered, an outer one fading out in the ordered pattern
  if (P.glow) {
    const g1 = hex(P.glow), g2 = hex(P.glow2), R1 = 3 * u, R2 = 11 * u;
    for (let y = m.y - m.r - R2; y <= m.y + m.r + R2; y++) for (let x = m.x - m.r - R2; x <= m.x + m.r + R2; x++) {
      const d = Math.hypot(x + 0.5 - m.x, y + 0.5 - m.y) - m.r;
      if (d < 0 || d > R2) continue;
      if (d < R1) { if ((x + y) & 1) px(rgb(g1, 0.55), x, y); else px(rgb(g1, 0.3), x, y); continue; }
      const k = 1 - (d - R1) / (R2 - R1);
      if (bayer(x, y) < k * k * 12) px(rgb(k > 0.5 ? g1 : g2, 0.28), x, y);
    }
  }
  // the face: lit from the upper left (the last of the sun), shading to the lower right
  const face = P.face.map(hex), day = hourOf(th) === 'day';
  for (let y = m.y - m.r; y <= m.y + m.r; y++) for (let x = m.x - m.r; x <= m.x + m.r; x++) {
    const nx = (x + 0.5 - m.x) / m.r, ny = (y + 0.5 - m.y) / m.r, q = nx * nx + ny * ny;
    if (q > 1) continue;
    const l = -(nx * 0.55 + ny * 0.75) * 0.8 - q * 0.45 + 0.1;  // 1 bright .. -1 dim
    const lv = (l + 0.9) * 2.1, fr = lv - Math.floor(lv), lvl = Math.floor(lv) + (lv < 2 && fr > 0.72 && bayer(x, y) < (fr - 0.72) / 0.28 * 16 ? 1 : 0);
    let c = face[Math.max(0, Math.min(3, 3 - lvl))];
    for (const [sx, sy, sr] of SEAS) {
      const s = ((nx - sx) ** 2 + (ny - sy) ** 2) / (sr * sr);
      if (s < 0.75 || (s < 1 && (x + y) & 1)) c = s < 0.25 ? hex(P.seaD) : hex(P.sea);
    }
    for (const [cx, cy, cr] of CRATERS) {
      const d = Math.hypot(nx - cx, ny - cy) / cr;
      if (d < 1 && d > 0.6) c = (nx - cx) + (ny - cy) < 0 ? hex(P.seaD) : hex(P.sea);
    }
    if (q > 0.88 && nx + ny > 0.2) c = face[3];  // the dim limb
    if (day) c = mix(c, hex(th.sky[1]), 0.35);
    px(c, x, y);
  }
  // two thin streaks of cloud drifting across its lower half, lit underneath by the sunset
  if (P.cloud) {
    streak(g, P, m.y + m.r * 0.5, m.x - m.r * 1.7, m.x + m.r * 0.35, 3 * u);
    streak(g, P, m.y + m.r * 0.78, m.x - m.r * 0.2, m.x + m.r * 1.6, 2.2 * u);
  }
  return m;
}

/* ---------- the trees ----------
 * Broadleaves: a crooked trunk flaring into roots, forking into gnarled limbs that kink and
 * hook at their ends, each carrying a ragged clump of dark foliage, with bare twigs poking
 * out. Conifers: a lopsided fir with drooping, ragged tiers and a tip bent over like a witch's
 * hat. The moon side (right) of every silhouette is rimmed with its light. */
function gnarl(c) {
  const { t, h, W, H, cx, base, tone, R, hole, ancient } = c;
  const st = t.stage;
  const bark = new Uint8Array(W * H);  // 1 dark, 2 mid, 3 light; painted last, with its rim
  const B = (x, y, v) => { x = Math.round(x); y = Math.round(y); if (x >= 0 && y >= 0 && x < W && y < H) bark[y * W + x] = Math.max(bark[y * W + x], v); };
  let top = base;
  // the trunk: an S-bend, leaning a little, thick and flared when old
  const tw = ancient ? 4 : st >= 4 ? 3 : h >= 14 ? 2 : 1;
  const trunkH = Math.round(h * (st === 1 ? 0.55 : st === 2 ? 0.42 : 0.36));
  const lean = ((t.seed >> 2) % 3 - 1) * 0.12, bend = ((t.seed >> 4) & 1 ? 1 : -1) * Math.min(2, 0.6 + h * 0.05);
  const xAt = k => cx + lean * k + bend * Math.sin(k / Math.max(1, trunkH) * Math.PI);
  for (let k = 0; k <= trunkH; k++) {
    const y = base - k, x0 = Math.round(xAt(k) - (tw - 1) / 2);
    const wk = tw + (k < 2 && tw > 1 ? 1 : 0);  // flare at the foot
    for (let q = 0; q < wk; q++) B(x0 + q - (k < 2 && tw > 1 ? (k === 0 ? 1 : 0) : 0), y, q === wk - 1 ? 1 : q === 0 ? 3 : 2);
  }
  if (st >= 3) {  // roots
    const r = ancient ? 3 : 2, x0 = Math.round(xAt(0) - (tw - 1) / 2);
    for (let k = 1; k <= r; k++) { B(x0 - 1 - k, base, 1); B(x0 + tw + k, base, 1); }
    B(x0 - 2, base - 1, 2); B(x0 + tw + 1, base - 1, 1);
  }
  const fx = xAt(trunkH), fy = base - trunkH;
  // the crown: one broad, lumpy canopy over the fork, lopsided with the trunk's bend
  const rx = Math.max(2, c.w / 2 - (st >= 3 ? 1.5 : 0.5)), ry = Math.max(2, h * (st === 1 ? 0.2 : st === 2 ? 0.34 : 0.32));
  const ccx = fx + 0.5 + bend * 0.4, ccy = Math.max(1 + ry, fy - ry * (st === 1 ? 0.5 : 0.45));
  // a limb: crooked, kinking once, thinning, hooking over at its end
  const limb = (x, y, a, len, wd, depth, bare) => {
    const kink = (R() < 0.5 ? -1 : 1) * (0.3 + R() * 0.3), at = Math.round(len * (0.35 + R() * 0.25));
    const hook = (Math.cos(a) >= 0 ? 1 : -1) * (bare ? 0.35 : 0.15);
    for (let s = 0; s < len; s++) {
      if (s === at) a += kink;
      if (s > len - 3) a += hook;  // the tip curls outward and down
      a += (R() - 0.5) * 0.25;
      x += Math.cos(a); y += Math.sin(a);
      const k = Math.max(1, Math.round(wd * (1 - s / len) + 0.3));
      for (let q = 0; q < k; q++) B(x + q - (k >> 1), y, q === 0 && k > 1 ? 3 : 2);
      top = Math.min(top, Math.round(y));
      if (depth === 0 && s === at + 1 && st >= 4) limb(x, y, a - kink * 1.6, len * 0.45, 1, 1, false);
    }
  };
  const n = st <= 2 ? 2 : st === 3 ? 3 : 4;
  for (let i = 0; i < n; i++) {
    const f = n === 1 ? 0.5 : i / (n - 1), a = -Math.PI / 2 + (f - 0.5) * 1.7 + (R() - 0.5) * 0.2;
    limb(fx, fy, a, Math.hypot(Math.cos(a) * rx, Math.sin(a) * ry * 1.4) * 0.85, Math.max(1, tw - 1), 0, false);
  }
  // bare, hooked branches reaching out of the crown's sides: the gnarled silhouette
  if (st >= 3) {
    const sides = st >= 4 ? [-1, 1] : [(t.seed & 1) ? 1 : -1];
    for (const sd of sides) {
      const k = Math.round(trunkH * (0.75 + R() * 0.2));
      limb(xAt(k), base - k, -Math.PI / 2 + sd * (1.05 + R() * 0.2), rx * 1.05 + 2 + R() * 2, Math.max(1, tw - 1), 1, true);
    }
  }
  if (st >= 2) {
    const s1 = hashN('s1', t.seed) * 6.28, s2 = hashN('s2', t.seed) * 6.28;
    for (let yy = Math.floor(ccy - ry * 1.3); yy <= ccy + ry * 1.2; yy++) for (let xx = Math.floor(ccx - rx * 1.3); xx <= ccx + rx * 1.3; xx++) {
      if (xx < 0 || yy < 0 || xx >= W || yy >= base - 1) continue;
      const nx = (xx + 0.5 - ccx) / rx, ny = (yy + 0.5 - ccy) / ry, th = Math.atan2(ny, nx);
      const lump = 1 + 0.16 * Math.sin(th * 5 + s1) + 0.08 * Math.sin(th * 11 + s2) - (ny > 0.2 ? 0.25 * ny : 0);
      const q = Math.sqrt(nx * nx + ny * ny);
      if (q > lump) continue;
      // gaps in the canopy, where the limbs behind show through
      if (st >= 3 && q < lump - 0.3 && ny > -0.4 && hashN('g', xx >> 1, yy >> 1, t.seed) < 0.16) continue;
      if (hole && R() < hole) continue;
      const rim = q / lump;  // 0 at the heart .. 1 at the edge
      const l = (nx * 0.5 - ny * 0.85) * 0.75 + (rim - 0.6) * 0.5 + (hashN('l', xx, yy, t.seed) - 0.5) * 0.35;
      tone[yy * W + xx] = ny > 0.35 && rim < 0.95 ? 1 : l > 0.62 ? 4 : l > 0.28 ? 3 : l > -0.3 ? 2 : 1;
      top = Math.min(top, yy);
    }
    // bare twigs poking up out of the canopy
    for (let k = 0; k < (st >= 4 ? 4 : st === 3 ? 2 : 0); k++) {
      let a = -Math.PI / 2 + (k / 3 - 0.5) * 1.8 + (R() - 0.5) * 0.4;
      let x = ccx + Math.cos(a) * rx * 0.85, y = ccy + Math.sin(a) * ry * 0.85;
      for (let s = 0; s < 2 + Math.round(ry * 0.35); s++) { a += (R() - 0.5) * 0.9; x += Math.cos(a); y += Math.sin(a); B(x, y, 2); top = Math.min(top, Math.round(y)); }
    }
  } else {  // a sapling: two tufts on a crooked stick
    for (const [ox, oy] of [[-1.2, -0.2], [1, 0.3]]) {
      const px = ccx + ox * rx * 0.5, py = ccy + oy * ry;
      for (let yy = Math.floor(py - 2); yy <= py + 2; yy++) for (let xx = Math.floor(px - 2); xx <= px + 2; xx++) {
        if (xx < 0 || yy < 0 || xx >= W || yy >= base - 1) continue;
        const d = Math.hypot(xx + 0.5 - px, (yy + 0.5 - py) * 1.3); if (d > 1.9) continue;
        tone[yy * W + xx] = d < 1 && yy < py ? 3 : 2; top = Math.min(top, yy);
      }
    }
  }
  paintBark(c, bark);
  return { top: Math.max(0, top), ch: base - top };
}

/* a lopsided fir: ragged tiers with drooping tips, and a crooked tip bent over */
function crookedFir(c) {
  const { t, h, W, H, w, cx, base, tone, R, hole } = c;
  const bark = new Uint8Array(W * H);
  const trunkH = Math.max(2, Math.round(h * 0.16)), top = 1, ch = base - trunkH + 1 - top;
  const tw = t.stage >= 4 ? 2 : 1;
  for (let y = base - trunkH - 2; y <= base; y++) for (let q = 0; q < tw; q++) bark[y * W + cx + q - (tw >> 1)] = q === tw - 1 ? 1 : 2;
  if (t.stage >= 3) { bark[base * W + cx - (tw >> 1) - 1] = 1; bark[base * W + cx + tw - (tw >> 1)] = 1; }
  const tiers = t.stage >= 5 ? 5 : t.stage >= 4 ? 4 : t.stage >= 3 ? 3 : 2;
  const bendDir = (t.seed >> 3) & 1 ? 1 : -1, bendAmt = Math.max(1.5, w * 0.28);
  const skewL = 0.85 + hashN('sl', t.seed) * 0.3, skewR = 0.85 + hashN('sr', t.seed) * 0.3;
  for (let y = top; y < top + ch; y++) {
    const p = (y - top + 0.5) / ch, tp = (p * tiers) % 1;
    const xc = cx + 0.5 + bendDir * bendAmt * Math.pow(Math.max(0, 1 - p * 3.2), 2);  // the tip bends over
    const tier = Math.floor(p * tiers);
    const hw = (w / 2) * (0.08 + 0.92 * p) * (0.42 + 0.58 * Math.pow(tp, 0.8));
    for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - xc, side = dx < 0 ? skewL : skewR;
      const jag = (hashN('j', x, tier, t.seed) - 0.5) * 1.6;
      const lim = hw * side * (1 + (tier % 2 ? 0.08 : -0.08) * (dx < 0 ? 1 : -1)) + jag;
      if (Math.abs(dx) > lim) continue;
      if (hole && R() < hole) continue;
      const l = (dx / Math.max(hw, 1)) * 0.7 - (tp - 0.5) * 0.4 + (hashN('p', x, y, t.seed) - 0.5) * 0.3;
      const under = tp > 0.86 && p < 0.97;
      let tn = l > 0.55 ? 4 : l > 0.15 ? 3 : l > -0.35 ? 2 : 1;
      if (under) tn = Math.max(1, tn - 2);
      tone[y * W + x] = tn;
      // drooping tips: the outer ends of each tier hang a pixel lower
      if (tp > 0.8 && Math.abs(dx) > lim - 1.2 && y + 1 < base && tone[(y + 1) * W + x] < 0) tone[(y + 1) * W + x] = 1;
    }
  }
  paintBark(c, bark);
  return { top, ch: base - top };
}

/* bark goes down last, so it can be rimmed on the moon side where nothing is to its right */
function paintBark(c, bark) {
  const { W, H, put, bark: BK, inside, th } = c, P = HOUR_P[hourOf(th)];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const v = bark[y * W + x]; if (!v) continue;
    let col = v === 3 ? BK.l : v === 2 ? BK.m : BK.d;
    const open = x + 1 >= W || (!bark[y * W + x + 1] && !inside(x + 1, y));
    if (P.rim && open && v === 1 && x > 1 && bark[y * W + x - 1] && bark[y * W + x - 2] && y < c.base) col = mix(col, P.rim2, 0.55);  // only a thick trunk catches it
    put(x, y, col);
  }
}

const TREE = {
  width: ({ t, h, pine }) => {
    if (pine) return Math.max(5, Math.round(h * (0.5 + t.size * 0.06))) | 1;
    return Math.max(5, Math.round(h * (t.stage === 1 ? 0.8 : 0.98 + t.size * 0.08))) | 1;
  },
  body: c => (c.pine ? crookedFir(c) : gnarl(c)),
  palette(c) {
    const P = HOUR_P[hourOf(c.th)];
    return { round: P.rounds[(c.t.seed >> 1) % 2], pine: P.pine };
  },
  /* the moon catches the right-hand edge of every healthy crown: a bright rim, then a
   * deeper one just inside it */
  pixel(col, { x, y, tn, pal, c }) {
    if (!MINE.has(pal)) return col;  // a yellowing branch stays plainly yellow
    const P = HOUR_P[hourOf(c.th)];
    if (!P.rim || c.t.stage < 1) return col;
    if (tn < 2 && c.inside(x, y + 1)) col = pal[1];  // a crisp dark body, outlined only below
    // only the top-right contour: open to the right and above-right
    const openR = !c.inside(x + 1, y) && !c.inside(x + 1, y - 1);
    if (openR && y < c.H * 0.8) return mix(pal[2], P.rim, !c.inside(x, y - 1) ? 0.62 : 0.42);
    if (!c.inside(x, y - 1) && !c.inside(x + 1, y - 1) && tn >= 3) return mix(col, P.rim2, 0.45);
    return col;
  },
};

/* ---------- jack-o'-lanterns ----------
 * Four sizes, and no two alike: round, squat or tall; the usual orange, a deeper or paler one,
 * now and then a white ghost pumpkin or a green-striped one; a plain, curly, snapped or leafy
 * stem. The bigger ones each wear their own carved face (a classic grin, a belly laugh with
 * its eyes squeezed shut, a jagged toothy grin, a startled O, a wink, a sly smirk, a scowl with
 * fangs, a goofy one-toothed grin), drawn by hand per size so each still reads. Their faces
 * glow from inside after dusk (a dithered pool on the ground round them) and show as dark
 * holes by day. A few of the laughers chuckle: mouth snapping open, a hop, the candle flaring. */
const SKINS = {
  orange: { hi: '#ffab52', lit: '#f07e2c', mid: '#d25c1c', sh: '#9a3a12', out: '#4a1608' },
  deep:   { hi: '#f8903e', lit: '#dc6420', mid: '#b24212', sh: '#76260a', out: '#380e04' },
  pale:   { hi: '#ffd490', lit: '#fcb064', mid: '#e88c44', sh: '#ae5a2a', out: '#521e0e' },
  ghost:  { hi: '#fffaf0', lit: '#f0e4d6', mid: '#d4c4ba', sh: '#9c8692', out: '#3a2432' },
  striped: { hi: '#ffab52', lit: '#f07e2c', mid: '#d25c1c', sh: '#9a3a12', out: '#4a1608', stripe: '#6a8030', stripeD: '#3a4c1a' },
};
const GREENS = { stem: '#5e6a26', stemD: '#343a14', cut: '#b4a868', leaf: '#4e7a2a', leafD: '#2c4816', vine: '#6a7a2e' };
const DAY_TONE = hex('#8a7494');
const dayHex = c => { const m = mix(hex(c), DAY_TONE, 0.14); return rgb(m); };
const EVE_TONE = hex('#2a0818');
/* by day a touch of the lilac afternoon; after it, the skin sinks into the dusk so a lit face
 * burns out of it */
const skinOf = (name, day, lit) => {
  const S = Object.assign({}, SKINS[name], GREENS);
  if (day) for (const k in S) S[k] = dayHex(S[k]);
  else for (const k in S) S[k] = rgb(mix(hex(S[k]), EVE_TONE, lit ? 0.44 : 0.5));
  return S;
};
// body sizes, [w, h], for the four sizes; a squat one is wider and lower, a tall one the reverse
const SIZE_WH = [[5, 4], [7, 6], [10, 8], [13, 11]];
function dims(size, shape) {
  const [w, h] = SIZE_WH[size];
  if (size === 0) return [w, h];
  return shape === 'squat' ? [w + 1, h - 1] : shape === 'tall' ? [w - 1, h + 1] : [w, h];
}
/* the faces, per size: rows of carved holes, centred on the body, row numbers from its top.
 * `m` is the mouth; a laugher's `m` is two frames, [grinning, laughing]. */
const FACES = [
  { classic: { e: [[1, '#.#']], m: [[2, '###']] },
    oh: { e: [[1, '#.#']], m: [[2, '.#.']] } },
  { classic: { e: [[1, '#...#']], m: [[3, '#...#'], [4, '.###.']] },
    laugh: { e: [[1, '#...#']], m: [[[3, '#...#'], [4, '.###.']], [[3, '#####'], [4, '.###.']]] },
    oh: { e: [[1, '#...#']], m: [[3, '..#..'], [4, '..#..']] },
    wink: { e: [[1, '#..##']], m: [[3, '....#'], [4, '.###.']] },
    scary: { e: [[1, '#...#'], [2, '##.##']], m: [[4, '#.#.#']] } },
  { classic: { e: [[2, '.#....#.'], [3, '###..###']], m: [[5, '#.####.#'], [6, '.######.']] },
    laugh: { e: [[2, '.#....#.'], [3, '#.#..#.#']], m: [[[5, '#......#'], [6, '.######.']], [[4, '#......#'], [5, '########'], [6, '.######.']]] },
    toothy: { e: [[2, '.#....#.'], [3, '###..###']], m: [[5, '########'], [6, '.#.##.#.']] },
    oh: { e: [[2, '.##..##.'], [3, '.##..##.']], m: [[5, '...##...'], [6, '...##...']] },
    wink: { e: [[2, '.##...#.'], [3, '.##..#.#']], m: [[5, '.......#'], [6, '.######.']] },
    sly: { e: [[3, '###..###'], [4, '.##...##']], m: [[5, '......#.'], [6, '.#####..']] },
    scary: { e: [[2, '#......#'], [3, '##....##']], m: [[5, '########'], [6, '.#.##.#.']] },
    goofy: { e: [[2, '.##.....'], [3, '.##...#.']], m: [[[5, '#......#'], [6, '.###.##.']], [[4, '#......#'], [5, '###.####'], [6, '.######.']]] } },
  { classic: { e: [[2, '.#.....#.'], [3, '###...###'], [4, '....#....']], m: [[5, '#.......#'], [6, '##.###.##'], [7, '.#######.']] },
    laugh: { e: [[2, '.#.....#.'], [3, '#.#...#.#']], m: [[[5, '#.......#'], [6, '.#######.']], [[5, '#########'], [6, '#########'], [7, '.#######.'], [8, '..#####..']]] },
    toothy: { e: [[2, '.#.....#.'], [3, '###...###'], [4, '.#.....#.']], m: [[6, '#.#.#.#.#'], [7, '#########'], [8, '.#.#.#.#.']] },
    oh: { e: [[2, '.##...##.'], [3, '.##...##.']], m: [[5, '...###...'], [6, '..#####..'], [7, '..#####..'], [8, '...###...']] },
    wink: { e: [[2, '.##....#.'], [3, '.##...#.#']], m: [[5, '........#'], [6, '#......#.'], [7, '.######..']] },
    sly: { e: [[3, '###...###'], [4, '.##....##']], m: [[6, '.......#.'], [7, '.######..']] },
    scary: { e: [[2, '#.......#'], [3, '##.....##'], [4, '###...###']], m: [[6, '#########'], [7, '#.##.##.#'], [8, '..#...#..']] },
    goofy: { e: [[2, '.##......'], [3, '.##....#.']], m: [[[5, '#.......#'], [6, '####.####'], [7, '.#######.']], [[5, '#.......#'], [6, '####.####'], [7, '#########'], [8, '.#######.']]] } },
];
const LAUGHS = new Set(['laugh', 'goofy']);
function glow(g, cx, cy, rx, ry, strength, hot) {
  for (let y = Math.floor(cy - ry); y <= cy + ry; y++) for (let x = Math.floor(cx - rx); x <= cx + rx; x++) {
    const q = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2;
    if (q > 1) continue;
    const k = (1 - q) * strength;
    if (bayer(x, y) >= k * 22) continue;
    g.fillStyle = k > 0.55 ? (hot ? 'rgba(255,200,100,.4)' : 'rgba(255,170,70,.34)') : 'rgba(255,110,50,.26)';
    g.fillRect(x, y, 1, 1);
  }
}
/* one pumpkin, standing with the middle of its bottom row at (x, y). `mouth` picks a laugher's
 * frame; `bright` is the candle flaring as it laughs. */
function jack(g, q, day, mouth, bright) {
  const { size, w, h, lit } = q, C = skinOf(q.skin, day, lit), F = FACES[size][q.face] || FACES[size].classic;
  const x = Math.round(q.x), y = Math.round(q.y), x0 = x - (w >> 1), y0 = y - h + 1;
  const P = (c, xx, yy) => { g.fillStyle = c; g.fillRect(x0 + xx, y0 + yy, 1, 1); };
  // the body: an ellipse with bowed ribs, lit from the upper right; a squat one flatter-sided
  const ex = q.shape === 'squat' ? 3.4 : q.shape === 'tall' ? 2.1 : 2.6, rows = [];
  for (let r = 0; r < h; r++) {
    const qq = (r + 0.5) / h * 2 - 1;
    rows.push(w / 2 * Math.sqrt(Math.max(0, 1 - Math.pow(Math.abs(qq), ex) * 0.75)));
  }
  const mid = (w - 1) / 2;
  const ribs = w >= 12 ? [-0.52, -0.18, 0.18, 0.52] : w >= 9 ? [-0.46, 0, 0.46] : w >= 6 ? [-0.4, 0.4] : [];
  for (let r = 0; r < h; r++) for (let xx = 0; xx < w; xx++) {
    const dx = xx - mid; if (Math.abs(dx) > rows[r] - 0.1) continue;
    const edge = Math.abs(dx) > rows[r] - 1.1 || r === h - 1 || r === 0;
    const nx = dx / (w / 2), ny = (r + 0.5) / h * 2 - 1;
    let c = C.mid;
    const l = nx * 0.6 - ny * 0.7;
    if (l > 0.55) c = C.hi; else if (l > 0.1) c = C.lit; else if (l < -0.55) c = C.sh;
    // ribs bowing out towards the middle; a striped pumpkin's are green
    const bow = 1 - Math.abs(ny) * 0.6;
    for (const rb of ribs) if (Math.round(mid + rb * w / 2 * bow) === xx && r > 0 && r < h - 1) c = C.stripe ? (l > 0.3 ? C.stripe : C.stripeD) : l > 0.45 ? C.lit : C.sh;
    if (edge) c = r === 0 && Math.abs(dx) < rows[r] - 1.1 ? C.lit : (l > 0.5 && r < h - 1 ? C.lit : C.out);
    P(c, xx, r);
  }
  // the stem
  const sx = Math.round(mid);
  if (!q.noStem) {
    if (q.stem === 'broken') { P(C.stemD, sx, -1); P(C.cut, sx, -2); if (size >= 2) { P(C.stem, sx + 1, -1); P(C.cut, sx + 1, -2); } }
    else {
      P(C.stem, sx, -1); if (size >= 1) P(size >= 2 ? C.stem : C.stemD, sx, -2);
      if (size >= 2) P(C.stemD, sx - 1, -1);
      if (size >= 3) P(C.stemD, sx, -3);
      if (q.stem === 'plain' && size >= 2) P(C.stem, sx + 1, size >= 3 ? -3 : -2);  // the stalk bending over
      if (q.stem === 'curly') {  // a tendril curling off it
        if (size >= 2) { P(C.vine, sx + 1, -2); P(C.vine, sx + 2, -3); P(C.vine, sx + 3, -3); P(C.vine, sx + 4, -2); P(C.vine, sx + 3, -1); }
        else { P(C.vine, sx + 1, -2); P(C.vine, sx + 2, -1); }
      }
      if (q.stem === 'leafy') {  // a leaf drooping off one side
        if (size >= 2) { P(C.leaf, sx - 2, -2); P(C.leaf, sx - 3, -2); P(C.leafD, sx - 2, -1); P(C.leafD, sx - 3, -1); P(C.leaf, sx - 1, -2); P(C.leafD, sx - 4, -1); }
        else { P(C.leaf, sx - 1, -2); P(C.leafD, sx - 1, -1); }
      }
    }
  }
  // the carved face
  const mouthRows = Array.isArray(F.m[0][0]) ? F.m[mouth ? 1 : 0] : F.m, all = F.e.concat(mouthRows);
  const maxR = Math.max(...all.map(f => f[0])), [, bh] = SIZE_WH[size];
  const shift = h > bh ? 1 : maxR > h - 2 ? h - 2 - maxR : 0;
  const holeAt = new Set();
  for (const [r, s] of all) { const off = Math.round(mid - (s.length - 1) / 2); for (let i = 0; i < s.length; i++) if (s[i] === '#') holeAt.add((r + shift) * 64 + off + i); }
  const hole = day ? '#2a0c06' : bright ? '#ffe88a' : '#ffd25a', hot = day ? '#2a0c06' : bright ? '#fffce8' : '#fff0a8',
    wall = day ? '#541a0a' : bright ? '#ffc048' : '#ffae34';
  for (const k of holeAt) {
    const r = Math.floor(k / 64), xx = k % 64;
    if (!lit) { P(day ? hole : C.out, xx, r); continue; }
    // the inside wall at the top of each hole catches less light; the lower holes burn hottest
    P(!holeAt.has(k - 64) ? wall : (size >= 2 && r >= 3 ? hot : hole), xx, r);
  }
}

/* ---------- the witch ----------
 * She crosses the moon every EVERY seconds, taking CROSS to fly the width of the sky: hat
 * with its tip flopped back, hair streaming, cape flapping (two frames), a pointed boot,
 * a broom with bound bristles, and her cat riding behind her, eyes glowing. */
const EVERY = 36, CROSS = 16, OVER_MOON_AT = 12.3;  // she is over the moon at this moment (and in a still forest)
const WW = 40;  // the sprite's width
const WITCH_OFF = 35, WITCH_ABOVE = 17;  // sprite pixels: how far off the sky she starts and ends, and how high over the moon's middle she flies
// '#' her, the broom and the cat; 'A' the cape, which flaps a pixel up and down; 'e' the cat's eye
const WITCH = [
  '...............##.......................',
  '................##......................',
  '................###.....................',
  '.................###....................',
  '.................####...................',
  '.................#####..................',
  '................######..................',
  '............###########.................',
  '...............#######..................',
  '...............#########...............',
  '.............####.###..................',
  '...........AAA###..####.................',
  '..........AAAAA########.................',
  '.........AAAAAA#########................',
  '....#.#..AAAAA##########................',
  '...####..AAAA############..#............',
  '...##e#...AA..###########.##............',
  '..#####......############.#.............',
  '.######..................#..............',
  '########################################',
  '.#######........##....###...............',
  '#.#.#.#........###.....####.............',
  '..............##........................',
];
function drawWitch(g, x0, y0, s, frame, col, eye) {
  g.fillStyle = col;
  for (let r = 0; r < WITCH.length; r++) {
    const row = WITCH[r];
    for (let i = 0; i < row.length; i++) {
      const ch = row[i];
      if (ch === '#') g.fillRect(x0 + i * s, y0 + r * s, s, s);
      else if (ch === 'A') g.fillRect(x0 + (i - frame) * s, y0 + (r - frame) * s, s, s);
    }
  }
  for (let r = 0; r < WITCH.length; r++) { const i = WITCH[r].indexOf('e'); if (i >= 0) { g.fillStyle = eye; g.fillRect(x0 + i * s, y0 + r * s, s, s); } }
}

/* bats: a few flutter in slow loops about the moon */
const BATS = 4;
function bat(g, x, y, up) {
  g.fillRect(x - 1, y, 3, 1); g.fillRect(x, y + 1, 1, 1);
  if (up) { g.fillRect(x - 2, y - 1, 1, 1); g.fillRect(x + 2, y - 1, 1, 1); g.fillRect(x - 3, y - 1, 1, 1); g.fillRect(x + 3, y - 1, 1, 1); }
  else { g.fillRect(x - 2, y, 1, 1); g.fillRect(x + 2, y, 1, 1); g.fillRect(x - 3, y + 1, 1, 1); g.fillRect(x + 3, y + 1, 1, 1); }
}

/* ---------- the pumpkin patch ----------
 * Where every jack-o'-lantern stands, and what it looks like, worked out once: some beside
 * the nearer trees' feet (drawn with that tree, just before it) and a few out on the open
 * ground (drawn in depth order between the trees), now and then with a little one leaning on
 * it or sat on top. Their light is laid on the bare ground first, as a dithered pool, so it
 * never washes over the trees. */
const BIG_FACES = ['laugh', 'classic', 'toothy', 'oh', 'scary', 'laugh', 'wink', 'goofy', 'sly', 'classic', 'toothy', 'laugh'];
const SMALL_FACES = ['classic', 'laugh', 'oh', 'wink', 'classic', 'scary'];
const MAX_LAUGHERS = 5;
const LOOSE_EVERY = 42;  // one pumpkin out on the open ground per this many pixels of width
function dress(q, key, env) {
  const h1 = hashN('pkS', key), h2 = hashN('pkC', key), h3 = hashN('pkT', key);
  q.shape = q.size === 0 ? 'round' : h1 < 0.3 ? 'squat' : h1 < 0.55 ? 'tall' : 'round';
  q.skin = h2 < 0.07 ? 'ghost' : h2 < 0.14 ? 'striped' : h2 < 0.36 ? 'pale' : h2 < 0.58 ? 'deep' : 'orange';
  q.stem = h3 < 0.22 ? 'curly' : h3 < 0.36 ? 'broken' : h3 < 0.56 ? 'leafy' : 'plain';
  if (q.size >= 2) q.face = BIG_FACES[env.pkBig++ % BIG_FACES.length];
  else if (q.size === 1) q.face = SMALL_FACES[Math.floor(hashN('pkF', key) * SMALL_FACES.length)];
  else q.face = hashN('pkF', key) < 0.75 ? 'classic' : 'oh';
  [q.w, q.h] = dims(q.size, q.shape);
  return q;
}
/* a big pumpkin sometimes has a small one leaning on its side or sat on top of it */
function friends(q, key, env, out, away) {
  if (q.size < 2) return;
  const k = hashN('pkM', key);
  if (k < 0.16 && q.size === 3) {  // a small one sat on top, in the dip round the stem
    q.noStem = true;
    const s = dress({ size: 1, lit: q.lit, ky: q.ky + 0.2 }, key + 'top', env);
    s.x = q.x; s.y = q.y - q.h + 2 + (s.h >> 2); s.onTop = true; q.stacked = true;
    out.push(s);
  } else if (k < 0.42) {  // a little one leaning on its flank, just in front
    const side = away || (hashN('pkL', key) < 0.5 ? -1 : 1), size = q.size === 3 && k < 0.3 ? 1 : 0;
    const s = dress({ size, lit: q.lit && k > 0.2, ky: q.ky + 0.4 }, key + 'lean', env);
    s.x = q.x + side * ((q.w >> 1) + (s.w >> 1) - 1); s.y = q.y + 1;
    out.push(s);
  }
}
function patch(env) {
  if (env.pkPatch) return env.pkPatch;
  const { W, H, hor, u } = env, th = env.theme, byTree = new Map(), loose = [];
  env.pkBig = Math.floor(hashN('pkB', env.data.forestSeed || 5) * BIG_FACES.length);
  const R = rng(((env.data.forestSeed || 5) ^ 0x9a7c) >>> 0), n = Math.round(W / LOOSE_EVERY);
  // the open ground first, so its bigger ones, right at the front, get the first faces
  for (let i = 0; i < n; i++) {
    const x = Math.round(W * (i + 0.2 + R() * 0.6) / n), qq = 0.35 + R() * 0.62, y = Math.round(hor + (H - hor) * (0.06 + 0.9 * qq));
    loose.push({ x, y, ky: y, size: qq > 0.8 ? (R() < 0.5 ? 3 : 2) : qq > 0.55 ? 2 : 1, lit: th.pkLit && R() < 0.8, key: 'L' + i });
  }
  loose.sort((a, b) => b.y - a.y);
  for (const q of loose.slice()) { dress(q, q.key, env); friends(q, q.key, env, loose); }
  for (const p of (env.placed || []).slice().reverse()) {
    const t = p.it;
    if (t.pond || t.fromFront > 7 || t.stage < 1 || hashN('pk', t.seed) > 0.3) continue;
    const h = Math.max(3, Math.round(AF.STAGE_H[t.stage] * u * p.s)), pine = t.kind === 1 && t.stage >= 2;
    const sw = TREE.width({ t, h, pine });
    const near = t.fromFront <= 2, side = (t.seed & 2) ? 1 : -1, x = Math.round(p.x), y = Math.round(p.y);
    const size = near ? (t.seed % 3 === 0 ? 3 : 2) : t.fromFront <= 5 ? (t.seed % 2 ? 2 : 1) : (t.seed % 3 ? 1 : 0);
    const a = dress({ y: y + 1, size, lit: th.pkLit, ky: 0 }, 'T' + t.seed, env);
    a.x = x + side * Math.round(sw / 2 + a.w / 2 + 1);
    const list = [a];
    if (near && t.seed % 4 === 1) {
      const b = dress({ y: y + 2, size: size - 1, lit: th.pkLit && t.seed % 8 !== 1, ky: 1 }, 'T2' + t.seed, env);
      b.x = x - side * Math.round(sw / 2 + b.w / 2 + 1); list.push(b);
    } else friends(a, 'T' + t.seed, env, list, side);
    list.sort((m, k) => m.ky - k.ky);
    byTree.set(p, list);
  }
  loose.sort((a, b) => a.ky - b.ky);
  // the laughers: the nearest lit ones with a laughing face, never one with another sat on it
  const laughers = [];
  if (th.pkLit) {
    const all = loose.concat(...byTree.values()).filter(q => q.lit && q.size >= 2 && LAUGHS.has(q.face) && !q.stacked && q.x - q.w > 1 && q.x + q.w < W - 2);
    all.sort((a, b) => b.y - a.y);
    for (const q of all) {  // a few spares: one mostly hidden behind a trunk is dropped later
      if (laughers.length >= MAX_LAUGHERS + 3 || laughers.some(o => Math.abs(o.x - q.x) < 22 && Math.abs(o.y - q.y) < 12)) continue;
      const k = laughers.length;
      q.laugh = { per: 7 + hashN('pkP', q.x, q.y) * 5, ph: hashN('pkH', q.x, q.y) * 12 + k * 2.3, burst: 1.3 + hashN('pkU', q.x) * 0.8 };
      laughers.push(q);
    }
  }
  return (env.pkPatch = { byTree, loose, laughers });
}
function pools(env, lg) {
  const P = patch(env), all = [...P.loose];
  for (const l of P.byTree.values()) all.push(...l);
  for (const q of all) if (q.lit && !q.onTop) glow(lg, q.x + 0.5, q.y - q.h * 0.2, q.w * 1.15 + 2, q.h * 0.6 + 1.5, 0.85);
  const { W, H } = env;
  if (P.laughers.length) env.pkGround = lg.getImageData(0, 0, W, H);  // the bare, lit ground, for a laugher's flare
}
/* a pumpkin goes into the land; a laugher also keeps what lay under it and what it looked
 * like, so its frames can be built once the land is finished (see laughFrames) */
function place(env, lg, q) {
  const day = env.theme.pkHour === 'day';
  if (!q.laugh) return jack(lg, q, day, true, false);  // a laugh that never stops
  const { W, H } = env, fr = q.w * 0.9 + 2, fry = q.h * 0.45 + 2;
  const x0 = Math.max(0, Math.floor(Math.min(q.x - (q.w >> 1) - 5, q.x - fr))), x1 = Math.min(W, Math.ceil(Math.max(q.x + (q.w >> 1) + 6, q.x + fr + 1)));
  const y0 = Math.max(0, Math.round(q.y) - q.h - 5), y1 = Math.min(H, Math.ceil(q.y + fry));
  const box = q.box = { x0, y0, w: x1 - x0, h: y1 - y0 };
  q.under = lg.getImageData(x0, y0, box.w, box.h);
  jack(lg, q, day, false, false);
  q.drawn = lg.getImageData(x0, y0, box.w, box.h);
}
function plantLoose(env, lg) {
  const out = patch(env).loose, placed = env.placed || [];
  let i = 0;
  const upTo = (g, y) => { while (i < out.length && out[i].ky < y) place(env, g, out[i++]); };
  if (!placed.length) return upTo(lg, Infinity);
  upTo(lg, placed[0].y);
  const next = new Map(placed.map((p, k) => [p, k + 1 < placed.length ? placed[k + 1].y : Infinity]));
  const prev = env.afterItem;
  env.afterItem = (g, p) => { if (prev) prev(g, p); if (next.has(p)) upTo(g, next.get(p)); };
}
/* A laugher's frames, built once from the finished land: what lay under it, a flare of
 * candlelight on the bare ground (only there), the pumpkin itself, and then whatever was
 * drawn in front of it afterwards (a trunk, another pumpkin), so it keeps its place in depth.
 * 0 grinning, 1 laughing (hopped up a pixel), 2 between chuckles, 3 laughing on the ground. */
function laughFrames(env, q) {
  const { box } = q, fin = env.lg.getImageData(box.x0, box.y0, box.w, box.h), G = env.pkGround, n = box.w * box.h;
  const same = (A, i, B, j) => A[i] === B[j] && A[i + 1] === B[j + 1] && A[i + 2] === B[j + 2] && A[i + 3] === B[j + 3];
  const [ocv, og] = layer(box.w, box.h), occ = og.createImageData(box.w, box.h);
  let hid = 0;
  const bx0 = q.x - (q.w >> 1) - box.x0, by0 = q.y - q.h + 1 - box.y0;
  for (let i = 0; i < n * 4; i += 4) if (!same(fin.data, i, q.drawn.data, i)) {
    for (let c = 0; c < 4; c++) occ.data[i + c] = fin.data[i + c];
    const xx = (i >> 2) % box.w - bx0, yy = Math.floor((i >> 2) / box.w) - by0;
    if (xx >= q.w * 0.2 && yy >= q.h * 0.2 && xx < q.w * 0.8 && yy < q.h * 0.85) hid++;
  }
  if (hid > q.w * q.h * 0.36 * 0.3) return false;  // its face half hidden behind something: it stays a still grin
  og.putImageData(occ, 0, 0);
  const frame = (mouth, bob, flare) => {
    const [cv, g] = layer(box.w, box.h);
    g.putImageData(q.under, 0, 0);
    if (flare) {
      const [fcv, fg] = layer(box.w, box.h);
      fg.translate(-box.x0, -box.y0);
      glow(fg, q.x + 0.5, q.y - q.h * 0.2, q.w * 0.9 + 2, q.h * 0.45 + 1.5, flare, true);
      const img = fg.getImageData(0, 0, box.w, box.h);
      for (let yy = 0; yy < box.h; yy++) for (let xx = 0; xx < box.w; xx++) {
        const i = (yy * box.w + xx) * 4, j = ((box.y0 + yy) * env.W + box.x0 + xx) * 4;
        if (!G || !same(q.under.data, i, G.data, j)) img.data[i + 3] = 0;
      }
      fg.putImageData(img, 0, 0);
      g.drawImage(fcv, 0, 0);
    }
    g.save(); g.translate(-box.x0, -box.y0 - bob);
    jack(g, q, false, mouth, !!flare);
    g.restore();
    g.drawImage(ocv, 0, 0);
    return cv;
  };
  q.frames = [frame(false, 0, 0), frame(true, 1, 0.9), frame(false, 0, 0.55), frame(true, 0, 0.7)];
  return true;
}
/* each laugher now and then has a fit of chuckles: its mouth snapping open and shut, a hop on
 * every "ha", the candle flaring; staggered, so they never laugh together */
function drawLaughers(g, env, t) {
  const P = env.pkPatch;
  if (!P || !P.laughers.length || !P.laughers[0].box) return;
  if (!P.built) { P.built = true; P.laughers = P.laughers.filter(q => laughFrames(env, q)).slice(0, MAX_LAUGHERS); }
  for (const q of P.laughers) {
    let f = 0;
    if (env.still) f = 3;
    else {
      const k = ((t + q.laugh.ph) % q.laugh.per + q.laugh.per) % q.laugh.per;
      if (k < q.laugh.burst) f = Math.floor(k * 5) % 2 ? 2 : 1;
    }
    g.drawImage(q.frames[f], q.box.x0, q.box.y0);
  }
}

/* ---------- the hill on the left ----------
 * A crooked hilltop on the left horizon with a lone gnarled dead tree, a crow watching from
 * a limb, black against the dusk and rimmed on its moon side: it balances the moon on the
 * right. Lifted with the tree line, so a big forest never swallows it. Drawn once. */

/* the highest the forest's back rows (and the deep forest behind them) reach */
function backRowTop(env) {
  const { u, hor } = env, d = env.deep;
  let top = hor - 3 * u;
  if (d) top = Math.min(top, d.base - (d.bands - 1) * AF.DEEP.rise * u - (AF.DEEP.crown + (d.bands - 1) * AF.DEEP.step) * u * 1.2);
  for (const p of env.placed || []) if (!p.it.pond && p.it.depth > 0.55) top = Math.min(top, p.y - AF.STAGE_H[p.it.stage] * u * p.s);
  return Math.round(top);
}

/* per hour: the hill's body and its crest, the tree's ink, the moon-side rim */
const HILL_COLS = {
  dusk: { hill: '#16050f', hillL: '#2a0a1e', ink: '#080207', rim: '#ff7a48', rim2: '#b8403a', grass: '#3a1228' },
  night: { hill: '#0e0818', hillL: '#1a1028', ink: '#040208', rim: '#e8b88a', rim2: '#7a4a6a', grass: '#20142e' },
  dawn: { hill: '#2a1a32', hillL: '#3c2644', ink: '#120a14', rim: '#ffa8a0', rim2: '#a8607a', grass: '#46304e' },
  day: { hill: '#5e4e6c', hillL: '#6e5c7a', ink: '#2a1e2a', rim: null, rim2: null, grass: '#6e5e7a' },
};
const TREE_SEED = 57;  // picked from a sheet of seeds: wide, gnarled, crooked

/* the hill's crest, in u from the peak: [dx, dy], dy down. A long shoulder off the left edge,
 * a knobbly top, and a crag jutting out over a steep drop on the moon side. */
const PROFILE = [[-110, 30], [-92, 26], [-80, 21], [-72, 19], [-64, 19], [-56, 16], [-46, 12], [-36, 9], [-28, 7], [-20, 5], [-13, 3], [-8, 1], [-4, 0], [2, -1], [6, 0],
  [9, 0], [11, 2], [12, 4], [15, 5], [17, 7], [19, 8], [21, 11], [25, 14], [31, 18], [40, 23], [54, 30], [72, 40]];

function hillAt(env) {
  const { W, u, hor } = env;
  // the peak stands well clear above the forest's top, rising as the forest grows
  const line = Math.min(backRowTop(env), AF.treeLine(env));
  const top = Math.round(Math.max(30 * u, Math.min(hor - 24 * u, line - 8 * u)));
  return { cx: Math.round(W * 0.15), top };
}
function crest(at, u) {
  return x => {
    const d = (x + 0.5 - at.cx) / u;
    let i = 0; while (i < PROFILE.length - 2 && PROFILE[i + 1][0] < d) i++;
    const [x0, y0] = PROFILE[i], [x1, y1] = PROFILE[i + 1], f = Math.max(-3, Math.min(3, (d - x0) / (x1 - x0)));
    let y = y0 + (y1 - y0) * f;
    y += (hashN('hb', Math.floor(x / 3)) - 0.5) * 1.3;  // a rough, stony line
    return Math.round(at.top + y * u);
  };
}

function drawHill(env, lg, at) {
  const { W, u, hor } = env, C = HILL_COLS[hourOf(env.theme)], yAt = crest(at, u);
  const body = hex(C.hill), lit = hex(C.hillL), rim = C.rim && hex(C.rim), rim2 = C.rim2 && hex(C.rim2), near = hex(env.theme.near);
  const crack = mix(body, [0, 0, 0], 0.35);
  for (let x = 0; x < W; x++) {
    const y0 = yAt(x); if (y0 >= hor) continue;
    const yR = yAt(x + 1);
    for (let y = y0; y < hor; y++) {
      let c = body;
      const dy = y - y0;
      // the lit skin of the crest, dithered away beneath it (stronger on the moon's side)
      const moonSide = x > at.cx - 4 * u;
      if (dy < 5 * u && bayer(x, y) < (moonSide ? 8 : 4) * (1 - dy / (5 * u))) c = lit;
      // a few thin ledges of rock across the face, shadowed under their lips
      const ledge = LEDGES.find(L => Math.abs(x - (at.cx + L[0] * u)) < L[2] * u && y === Math.round(at.top + (L[1] + (x - at.cx - L[0] * u) * L[3] / u) * u));
      if (ledge && dy > 1) c = crack;
      // down near the horizon it fades into the rolling hills
      const k = (y - (hor - 7 * u)) / (7 * u);
      if (k > 0 && bayer(x, y) < k * 16) c = mix(body, near, 0.5);
      if (rim) {
        // a dark skin against the bright sky, and the moon's light just inside it
        const moonFace = y < yR || (yAt(x + 2) > y && y < yAt(x + 2) - 1);
        if (dy === 0) c = moonFace ? mix(body, rim2, 0.5) : mix(body, rim2, 0.25);
        else if (y < yR) c = mix(body, rim2, 0.55);
        else if (dy === 1 || (moonFace && dy <= 2)) c = mix(body, rim, moonSide ? 0.7 : 0.35);
        else if (moonSide && dy <= 3 * u && bayer(x, y) < 10 - dy * 3) c = mix(body, rim, 0.4);  // the moonlit shoulder
      }
      lg.fillStyle = rgb(c); lg.fillRect(x, y, 1, 1);
    }
    // dead grass along the crest
    const h = hashN('tuft', x);
    if (h < 0.22 && y0 < hor - 2) { lg.fillStyle = C.grass; lg.fillRect(x, y0 - 1, 1, 1); if (h < 0.06) lg.fillRect(x + (h < 0.03 ? 1 : -1), y0 - 2, 1, 1); }
  }
  // boulders heaped along the crest, the crag's lip on the moon side
  for (const [dx, rw, rh] of BOULDERS) {
    const bx = Math.round(at.cx + dx * u), by = yAt(bx) + 1, w = Math.round(rw * u), hh = Math.round(rh * u);
    if (by >= hor) continue;
    for (let yy = 0; yy < hh; yy++) for (let xx = -w; xx <= w; xx++) {
      const q = (xx / (w + 0.5)) ** 2 + ((yy - hh) / hh) ** 2; if (q > 1) continue;
      const X = bx + xx, Y = by - yy - 1;
      const openR = ((xx + 1) / (w + 0.5)) ** 2 + ((yy - hh) / hh) ** 2 > 1, openT = (xx / (w + 0.5)) ** 2 + ((yy + 1 - hh) / hh) ** 2 > 1;
      let c = xx < -w * 0.3 ? mix(body, [0, 0, 0], 0.25) : body;
      if (rim) { if (openR) c = mix(body, rim, 0.75); else if (openT) c = mix(body, rim, xx > 0 ? 0.55 : 0.3); else if (xx > w * 0.3 && bayer(X, Y) < 6) c = mix(body, rim2, 0.4); }
      else if (openT) c = lit;
      lg.fillStyle = rgb(c); lg.fillRect(X, Y, 1, 1);
    }
  }
}
const LEDGES = [[18, 12, 5, 0.25], [-22, 11, 9, -0.12], [-48, 19, 8, 0.08], [30, 21, 5, 0.3]];  // [dx, dy, half-length, slope] in u
const BOULDERS = [[-9, 2.2, 2.4], [12, 2.6, 3], [15.5, 1.6, 1.8], [-40, 1.6, 1.6], [26, 1.4, 1.4]];

/* the dead tree: a crooked trunk flaring into roots, twisting up into a few gnarled limbs
 * that fork and end in hooked twigs; one crow sits on the long low limb */
function treeMask(u, seed) {
  const px = new Map(), R = rng(seed);
  const S = Math.max(1, u);
  const put = (x, y, w) => { x = Math.round(x); y = Math.round(y); const k = y * 1000 + x; px.set(k, Math.max(px.get(k) || 0, w)); };
  const tips = [];
  // a gnarled bough: it wanders and kinks, thins as it goes, forks at its end, and its last
  // twigs curl over like fingers
  const bough = (x, y, a, len, wd, depth) => {
    const kink = (R() < 0.5 ? -1 : 1) * (0.25 + R() * 0.3), at = Math.round(len * (0.4 + R() * 0.25));
    const curl = Math.cos(a) >= 0 ? 1 : -1;
    for (let s = 0; s < len; s++) {
      if (s === at) a += kink;
      a += (R() - 0.5) * 0.28;
      a = Math.max(-Math.PI + 0.3, Math.min(-0.3, a));  // reaching up and out
      if (wd <= 1 && s === len - 2) a += curl * 0.7;  // a twig's tip crooks over like a finger
      x += Math.cos(a); y += Math.sin(a);
      const w = Math.max(1, Math.round(wd * (1 - 0.45 * s / len)));
      for (let q = 0; q < w; q++) put(x + q - (w >> 1), y, w);
      // a short side twig now and then
      if (wd <= 2 && s > 1 && s < len - 1 && R() < 0.14) {
        let tx = x, ty = y, ta = a + (R() < 0.5 ? -1 : 1) * (0.7 + R() * 0.4);
        for (let k = 0; k < 2 + R() * 3; k++) { tx += Math.cos(ta); ty += Math.sin(ta); put(tx, ty, 1); ta += (Math.cos(ta) > 0 ? 1 : -1) * 0.25; }
      }
    }
    if (len < 3.5 * S || depth > 3) { tips.push([x, y]); return; }
    // fork: one arm bends outward, the other climbs
    const out = Math.cos(a) >= 0 ? 1 : -1;
    bough(x, y, a + out * (0.35 + R() * 0.3), len * (0.6 + R() * 0.15), Math.max(1, wd - 1), depth + 1);
    bough(x, y, a - out * (0.3 + R() * 0.3), len * (0.5 + R() * 0.15), Math.max(1, wd - 1), depth + 1);
  };
  // the trunk: an S-bend leaning away from the moon, wide at the foot
  const trunkH = Math.round(12 * S), tw = Math.max(3, Math.round(4 * S));
  const xAt = k => -k * 0.2 + Math.sin(k / trunkH * Math.PI * 1.4) * 1.8 * S;
  for (let k = 0; k <= trunkH; k++) {
    const w = tw + (k < 1 ? 3 : k < 3 ? 1 : 0) - (k > trunkH * 0.6 ? 1 : 0);
    for (let q = 0; q < w; q++) put(xAt(k) + q - (w >> 1), -k, w >= 3 ? 3 : w);
  }
  // roots clawing over the rock
  for (const [dx, dy] of [[-4, 0], [-5, 1], [-6, 1], [3, 0], [4, 0], [5, 1], [6, 1], [7, 2], [-3, 0]]) put(dx * S, dy, 2);
  const fx = xAt(trunkH), fy = -trunkH;
  bough(fx - 1, fy + 1, -Math.PI + 0.55, 11 * S, 2.6, 0);   // the left arm, reaching wide
  bough(fx, fy, -Math.PI / 2 - 0.2, 9 * S, 2.6, 0);         // the crooked leader
  bough(fx + 1, fy, -1.05, 8 * S, 2.2, 1);                  // up toward the moon
  // a long low limb reaching out toward the moon: the crow's perch
  let x = xAt(trunkH * 0.5) + 1, y = -trunkH * 0.5, a = -0.55;
  for (let s = 0; s < 13 * S; s++) {
    a += (s < 5 ? 0.06 : -0.03) + (R() - 0.5) * 0.12; x += Math.cos(a); y += Math.sin(a);
    const w = s < 6 ? 2 : 1; for (let q = 0; q < w; q++) put(x, y + q, w);
    if (s === 8) { let tx = x, ty = y, ta = -1.9; for (let k = 0; k < 5; k++) { tx += Math.cos(ta); ty += Math.sin(ta); put(tx, ty, 1); ta += 0.18; } }
  }
  const perch = [x - 1, y];
  for (let k = 0; k < 3; k++) put(x + 1 + k * 0.6, y + 1 + k, 1);  // its tip droops
  // a snapped stub on the other side
  for (let k = 0; k < 4; k++) put(xAt(trunkH * 0.3) - 2 - k, -trunkH * 0.3 - k * 0.6, k < 2 ? 2 : 1);
  return { px, perch };
}

function drawTree(env, lg, x0, y0) {
  const { u } = env, C = HILL_COLS[hourOf(env.theme)], M = treeMask(u, TREE_SEED);
  const ink = hex(C.ink), rim = C.rim && hex(C.rim), rim2 = C.rim2 && hex(C.rim2);
  const has = (x, y) => M.px.has(y * 1000 + x);
  for (const [k, w] of M.px) {
    const y = Math.round(k / 1000), x = k - y * 1000;
    let c = ink;
    if (rim) {
      const openR = !has(x + 1, y), openT = !has(x, y - 1);
      if (openR && w >= 2) c = mix(ink, rim, 0.7);          // the trunk and big limbs catch the moon
      else if (openR && openT) c = mix(ink, rim2, 0.5);     // twigs only a glint
      else if (openR) c = mix(ink, rim2, 0.3);
    }
    lg.fillStyle = rgb(c); lg.fillRect(x0 + x, y0 + y, 1, 1);
  }
  // a crow on the low limb, hunched, facing the moon
  const [cx, cy] = M.perch, bx = x0 + Math.round(cx), by = y0 + Math.round(cy) - 1;
  const CROW = ['....##.', '...###>', '.#####.', '######.', '.####..', '..#.#..'];
  for (let r = 0; r < CROW.length; r++) for (let i = 0; i < CROW[r].length; i++) {
    const ch = CROW[r][i]; if (ch === '.') continue;
    let c = ink;
    if (rim && (i + 1 >= CROW[r].length || CROW[r][i + 1] === '.') && r < 4) c = mix(ink, rim, 0.5);
    lg.fillStyle = rgb(c); lg.fillRect(bx + i - 3, by + r - 5, 1, 1);
  }
  if (hourOf(env.theme) !== 'day') { lg.fillStyle = '#ffb040'; lg.fillRect(bx + 1, by - 4, 1, 1); }  // its eye catching the light
}

function drawHillside(env, lg) {
  const at = hillAt(env);
  drawHill(env, lg, at);
  const tx = at.cx + Math.round(1 * env.u);
  drawTree(env, lg, tx, crest(at, env.u)(tx) - 1);
}

AF.env('pumpkin_patch', {
  /* an orange dusk; the other hours keep the same scene in their own light */
  look(mood) {
    const k = mood.time === 'night' ? 'night' : mood.time === 'dawn' ? 'dawn' : mood.time === 'day' || mood.time === 'golden_hour' ? 'day' : 'dusk';
    return Object.assign(clone(LOOKS[k]), { pkHour: k, orb: null, tint: null, tintAmt: 0, rim: null, shadow: 0, warmFlies: true });
  },
  after(th) {
    th.orb = null;  // the moon is painted into the sky, lifted clear of the trees
    th.rim = null; th.shadow = 0;
    th.pkLit = th.pkHour !== 'day';
    th.flies = Math.min(th.flies || 0, MAX_FLIES);
    if (th.pkHour !== 'day' && th.clouds && th.clouds.n <= 3) th.clouds = null;  // its own streaks, painted into the sky
    th.rainbow = false;
  },
  // warm orange fireflies, to go with the candlelight
  prepare(env) { env.fxColors = { flyCore: '255,196,120', flyGlow: '255,120,60' }; },
  pals: { rounds: HOUR_P.dusk.rounds, roundAt: th => HOUR_P[hourOf(th)].rounds[0], pine: HOUR_P.dusk.pine, bark: HOUR_P.dusk.bark,
    leaf: hex('#2c1020'), leafL: hex('#4a1a30'), stem: hex('#2a1018') },
  tree: TREE,
  sky(env, g) { afterglow(env, g); env.pkMoon = paintMoon(env, g); },
  ground(env, lg) { drawHillside(env, lg); pools(env, lg); plantLoose(env, lg); },
  /* jack-o'-lanterns at the feet of the nearer trees */
  groundDetail(env, lg, p) {
    const list = patch(env).byTree.get(p);
    if (list) for (const q of list) place(env, lg, q);
  },
  /* the laughers, over the land but under the animals at the front */
  frame(g, env, t) { drawLaughers(g, env, t); },
  /* the bats looping round the moon, and the witch crossing it */
  fx: {
    init(st, { A }) {
      st.bats = [];
      for (let i = 0; i < BATS; i++) st.bats.push({ a: A() * 6.28, sp: (0.25 + A() * 0.2) * (A() < 0.5 ? -1 : 1), rx: 1.3 + A() * 0.5, ry: 0.5 + A() * 0.3, ph: A() * 9 });
    },
    front(g, env, t, st, where) {
      if (where !== 'sky' || !env.pkMoon) return;
      const m = env.pkMoon, { W, u } = env, th = env.theme;
      if (!st.pkStarsFiltered) { st.stars = st.stars.filter(q => Math.hypot(q.x - m.x, q.y - m.y) > m.r + 4); st.pkStarsFiltered = true; }  // no stars on the moon
      const ink = th.pkHour === 'day' ? '#2a1a26' : th.pkHour === 'dawn' ? '#1a0e1c' : '#0e040c';
      // the bats, in slow loops round the moon
      g.fillStyle = ink;
      for (const b of st.bats) {
        const a = b.a + t * b.sp;
        const bx = Math.round(m.x + Math.cos(a) * m.r * b.rx), by = Math.round(m.y - m.r * 0.2 + Math.sin(a) * m.r * b.ry * 1.6);
        bat(g, bx, by, Math.sin(t * 10 + b.ph) > 0);
      }
      // the witch
      const tt = env.still ? OVER_MOON_AT : t, s = Math.max(1, Math.round(u));
      const span = W + 2 * WITCH_OFF * s, pm = (m.x + WITCH_OFF * s) / span;
      const k = ((tt - OVER_MOON_AT + pm * CROSS) % EVERY + EVERY) % EVERY;
      if (k > CROSS) return;
      const p = k / CROSS;
      const x = Math.round(-WITCH_OFF * s + p * span - WW / 2 * s), y = Math.round(m.y - WITCH_ABOVE * s - Math.sin((p - pm) * 2.2) * 6 * s + Math.round(Math.sin(tt * 2.2)) * s);
      // her two frames are drawn once, then only stamped
      if (!env.pkWitch) env.pkWitch = [0, 1].map(f => { const [cv, cg] = layer(WW * s, WITCH.length * s); drawWitch(cg, 0, 0, s, f, ink, th.pkHour === 'day' ? '#b8c860' : '#e8f070'); return cv; });
      g.drawImage(env.pkWitch[env.still ? 0 : (Math.floor(tt * 4) & 1)], x, y);
    }
  },
});
})();

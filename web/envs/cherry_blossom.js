/* Memory Forest - the cherry blossom environment.
 * Everything this environment is lives here: delete it and cherry_blossom.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * Hanami under Fuji. Somei-yoshino cherries (a dark gnarled trunk forking into spreading
 * limbs, each carrying its own clump of pale, nearly white blossom) with a few small
 * garden pines among them. Over the scene, two great flowering boughs frame the sky with a
 * string of paper lanterns tied between them, and petals drift on a light breeze. Fuji
 * stands between the boughs, lifted with the tree line so its snow cap always shows. At
 * dusk and night the lanterns and the bonbori by the water are lit, and the blossom's
 * undersides catch their light in coral; on a clear night a big moon rises behind the
 * right-hand bough. Fallen petals drift on the water. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rgb, layer, rng, hashStr } = AF.u;
const H6 = a => a.map(hex);
const PETALS = ['#fbe0e8', '#f4b8ca', '#e892b0', '#ffffff'];

/* ---------- the trees ---------- */
// tones run outline, shade, mid, lit, highlight
const DAY_P = [
  H6(['#5a3040', '#cc98b0', '#eec6d4', '#fce6ee', '#ffffff']),
  H6(['#56304e', '#c286a6', '#e4acc6', '#f8cee0', '#fff0f6']),
];
const DUSK_P = [
  H6(['#3a1e36', '#8e5078', '#bc7496', '#e0a0b6', '#f6ccd6']),
  H6(['#361630', '#7c3866', '#aa5a84', '#d084a4', '#eeb0c4']),
];
const NIGHT_P = [
  H6(['#140c26', '#3a2656', '#7a4a86', '#d690b8', '#fcdcec']),
  H6(['#140c26', '#342050', '#6a3e7e', '#c47cac', '#f4c4dc']),
];
const NIWAKI = H6(['#1a3032', '#2a4a4a', '#3a6660', '#56867a', '#86b0a0']);
const NIWAKI_DUSK = H6(['#10221f', '#1b3634', '#284e4a', '#3a6a60', '#5e8c80']);
const NIWAKI_N = H6(['#060c18', '#0c1a26', '#142a36', '#1e3c48', '#3a5e6a']);
const PINES = new Set([NIWAKI, NIWAKI_DUSK, NIWAKI_N]);
const BARK = { l: hex('#6a4a58'), m: hex('#3e2834'), d: hex('#22141e') };
const WOOD = hex('#2e1c22'), WOOD_L = hex('#5a3a44');
// the lamplight on the undersides: coral and peach, never yellow
const GLOW = hex('#ff9e86'), GLOW_HI = hex('#ffc2a4');

/* a garden pine: a crooked trunk carrying flat pads of needles, one above another */
function niwaki(c) {
  const { t, W, H, cx, base, tone, put, pick, R, ancient } = c;
  const h = Math.max(6, Math.round(c.h * PINE_SCALE));
  const trunkTop = base - Math.round(h * 0.82);
  let x = cx, k = 0;
  for (let y = base; y >= trunkTop; y--, k++) {
    if (k > 2 && k % Math.max(3, Math.round(h / 6)) === 0) x += (R() < 0.5 ? -1 : 1);
    put(x, y, (k & 1) ? BARK.m : BARK.d);
    if (ancient || h >= 20) put(x + 1, y, BARK.d);
  }
  const n = t.stage >= 4 ? 3 : 2, Wc = W * PINE_SCALE;
  const pads = [{ x: x + 0.5, y: trunkTop + 1, rx: Wc * 0.22, ry: Math.max(1.6, h * 0.08) }];
  for (let i = 0; i < n; i++) {
    const y = trunkTop + Math.round((i + 1) * h * 0.55 / (n + 0.5)), side = i % 2 ? 1 : -1;
    const rx = Wc * (0.2 + 0.05 * i), ox = cx + 0.5 + side * (Wc * 0.2 + i * 0.6);
    for (let xx = Math.min(x, Math.round(ox)); xx <= Math.max(x, Math.round(ox)); xx++) put(xx, y + 1, BARK.m);
    pads.push({ x: ox, y, rx, ry: Math.max(1.4, h * 0.065) });
  }
  let top = H;
  for (const p of pads) {
    for (let yy = Math.floor(p.y - p.ry - 1); yy <= p.y + p.ry; yy++) for (let xx = Math.floor(p.x - p.rx - 1); xx <= p.x + p.rx + 1; xx++) {
      if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
      const nx = (xx + 0.5 - p.x) / p.rx, ny = (yy + 0.5 - p.y) / p.ry;
      if (nx * nx + ny * ny > 1) continue;
      tone[yy * W + xx] = pick(-ny * 0.9 - nx * 0.3 + (R() - 0.5) * 0.3);
      top = Math.min(top, yy);
    }
  }
  return { top, ch: base - top };
}

/* a pixel line of bark, `th` thick at its start and thinning towards the end */
function limbLine(put, x0, y0, x1, y1, th0, th1, col, colL) {
  const n = Math.max(1, Math.round(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0))));
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const f = i / n, x = Math.round(x0 + (x1 - x0) * f), y = Math.round(y0 + (y1 - y0) * f), tk = Math.max(1, Math.round(th0 + (th1 - th0) * f));
    for (let q = 0; q < tk; q++) put(x + q, y, q === 0 && tk > 1 ? colL : col);
    pts.push([x, y, f]);
  }
  return pts;
}

// tones run outline, shade, mid, lit, highlight
const T_DAY = [
  H6(['#6e4a5c', '#d6b4c6', '#eed6e0', '#fbeef3', '#ffffff']),
  H6(['#6a4052', '#d0a6ba', '#eacad8', '#f9e4ec', '#ffffff']),
];
const T_DUSK = [
  H6(['#3c2240', '#9c6488', '#d2a0bc', '#f4ccdc', '#fff0f4']),
  H6(['#381e3a', '#925a80', '#c890b0', '#eebed2', '#fce4ec']),
];
const T_NIGHT = [
  H6(['#120e26', '#3c3060', '#76679a', '#c6b2d8', '#f4ecf8']),
  H6(['#120e26', '#382a5a', '#6c5a8e', '#baa2cc', '#ece0f4']),
];
const T_MINE = new Set([...T_DAY, ...T_DUSK, ...T_NIGHT]);
const TBARK = { l: hex('#5e4050'), m: hex('#36222e'), d: hex('#1c1018') };
const PINE_SCALE = 0.7;
const isPine = c => c.pine && (c.t.seed % 4) === 0;

/* the lamplight from below: the underside of the crown glows coral. Only the crown's own
 * underside (c.low, the lowest blossom in each column) catches it, not every clump's. */
function glowPixel(col, { x, y, tn, pal, c }) {
  if (tn === 0 && T_MINE.has(pal) && c.inside(x, y + 1)) col = pal[1];
  if (!c.th.lampsLit || c.t.health) return col;
  const pine = PINES.has(pal);
  if (!T_MINE.has(pal) && !pine) return col;
  const low = c.low ? c.low[x] : -1;
  if (c.low && !pine) {
    if (y === low) return c.th.yoru ? mix(col, GLOW, 0.75) : GLOW;
    if (y === low - 1) return mix(col, GLOW_HI, 0.4);
    return col;
  }
  if (!c.inside(x, y + 1)) return pine ? mix(col, GLOW, 0.4) : c.th.yoru ? mix(col, GLOW, 0.75) : GLOW;
  if (!c.inside(x, y + 2)) return mix(col, GLOW_HI, pine ? 0.2 : 0.4);
  return col;
}
/* for each column, the lowest crown pixel above `floor` (-1 if none) */
function lowest(c, floor) {
  const { W, tone } = c, low = new Int16Array(W).fill(-1);
  for (let x = 0; x < W; x++) for (let y = floor; y >= 0; y--) if (tone[y * W + x] >= 0) { low[x] = y; break; }
  c.low = low;
}

/* The somei-yoshino: a short dark trunk, kinked, forking into a fan of limbs that spread
 * wide and a little upward. The limbs end in round clumps of blossom set on a broad arch,
 * kept apart so the silhouette breaks into the cherry's familiar lumpy cloud; a second,
 * darker row of clumps behind them fills the middle and shows as shadow between. */
function yoshino(c) {
  const { t, h, W, H, w, cx, base, tone, put, R, hole, ancient } = c;
  if (t.stage < 1) return null;
  const st = t.stage, tw = ancient ? 3 : h >= 15 ? 2 : 1;
  const trunkH = Math.max(3, Math.round(h * 0.36));
  // the trunk: leaning once, flared at the root
  const lean = (t.seed >> 3) % 3 - 1, fy = base - trunkH, fx = cx + lean;
  let x = cx;
  for (let y = base, k = 0; y >= fy; y--, k++) {
    if (k === Math.round(trunkH * 0.5)) x += lean;
    for (let q = 0; q < tw; q++) put(x - (tw >> 1) + q, y, q === 0 && tw > 1 ? TBARK.l : (y + q) % 3 === 0 ? TBARK.d : TBARK.m);
  }
  put(cx - (tw >> 1) - 1, base, TBARK.d); put(cx - (tw >> 1) + tw, base, TBARK.d);
  if (tw > 1) { put(cx - (tw >> 1) - 1, base - 1, TBARK.m); put(cx - (tw >> 1) - 2, base, TBARK.d); }
  // the clumps, on an arch
  const n = ancient ? 7 : st >= 4 ? 6 : st >= 3 ? 5 : 3;
  const r0 = Math.max(2, w * (n >= 6 ? 0.125 : n >= 5 ? 0.14 : 0.18));
  const top = 1, RX = w / 2 - 1 - r0 * 1.05, RY = Math.max(1, (fy - top - r0 * 1.9) / 1.31), cy = fy - r0 * 0.95 - 0.31 * RY;
  const J = (i, k) => (hashStr(i + k + t.seed) % 100) / 100 - 0.5;
  const clumps = [];
  for (let i = 0; i < n; i++) {
    const ang = Math.PI * (1.1 - 1.2 * i / (n - 1)) + J(i, 'a') * 0.12;
    clumps.push({ x: cx + 0.5 + Math.cos(ang) * RX + J(i, 'x'), y: cy - Math.sin(ang) * RY + J(i, 'y') * 1.4, r: r0 * (0.92 + J(i, 'r') * 0.3), limb: true });
  }
  // the back row: fewer, darker, higher in the middle
  const back = [];
  for (let i = 0; i < n - 2; i++) {
    const f = n - 3 ? i / (n - 3) : 0.5, ang = Math.PI * (0.85 - 0.7 * f);
    back.push({ x: cx + 0.5 + Math.cos(ang) * RX * 0.6, y: cy - Math.sin(ang) * RY * 0.62, r: r0 * 1.05, back: true });
  }
  // the limbs: from the fork to each clump, bending on the way
  const lt = Math.max(1, tw - (ancient ? 1 : 0));
  for (const k of clumps) {
    const mx = (fx + k.x) / 2 + (k.x > fx ? -1 : 1), my = fy - (fy - k.y) * 0.6;
    limbLine(put, fx, fy, mx, my, lt, lt, TBARK.m, TBARK.l);
    limbLine(put, mx, my, k.x, k.y + k.r * 0.3, lt, 1, TBARK.m, TBARK.m);
    if (st >= 3 && Math.abs(k.x - fx) > 3) put(Math.round(k.x + (k.x > fx ? 1 : -1) * (k.r + 1)), Math.round(k.y + k.r * 0.7), TBARK.m);
  }
  clumps.sort((a, b) => a.y - b.y);
  let t0 = H;
  const tex = st >= 3;
  for (const k of back.concat(clumps)) {
    const kx = k.r * 1.12, ky = k.r * 0.98;
    for (let y = Math.floor(k.y - ky - 1); y <= k.y + ky + 1; y++) for (let x = Math.floor(k.x - kx - 1); x <= k.x + kx + 1; x++) {
      if (x < 0 || y < 0 || x >= W || y >= fy) continue;
      const nx = (x + 0.5 - k.x) / kx, ny = (y + 0.5 - k.y) / ky, q = nx * nx + ny * ny;
      const edge = 1 + ((hashStr(x + ',' + y + ',' + t.seed) % 5) - 2) * 0.09;
      if (q > edge) continue;
      if (hole && R() < hole) continue;
      const was = tone[y * W + x];
      const l = -(nx * 0.35 + ny * 0.95) * 0.85 + (R() - 0.5) * 0.25 - (k.back ? 0.45 : 0);
      let tn = l > 0.5 ? 4 : l > 0.05 ? 3 : l > -0.45 ? 2 : 1;
      // little flowers and little shadows, so a big clump reads as blossom and not felt
      if (tex && tn >= 2 && tn <= 3) { const hh = hashStr(x + ':' + y + ':' + t.seed) % 13; if (hh === 0) tn = 4; else if (hh === 1 && q < 0.6) tn = 1; }
      // where a front clump overlaps one behind it, its rim is lit and the seam shaded
      if (!k.back && was >= 0 && q > 0.62 && ny < 0.2) tn = ny < -0.3 ? 4 : 3;
      tone[y * W + x] = tn;
      t0 = Math.min(t0, y);
    }
  }
  lowest(c, fy - 1);
  return { top: Math.min(t0, fy), ch: base - Math.min(t0, fy) };
}

const TREE = {
  pals: { rounds: T_DUSK, pine: NIWAKI, bark: TBARK, leaf: hex('#d8a8c0'), leafL: hex('#f4d4e2') },
  tree: {
    width: c => isPine(c) ? Math.max(5, Math.round(c.h * 0.78 * PINE_SCALE)) | 1 : Math.max(5, Math.round(c.h * 1.3)) | 1,
    body: c => (isPine(c) ? niwaki(c) : yoshino(c)),
    palette(c) {
      const th = c.th, s = c.t.seed, P = th.yoru ? T_NIGHT : th.dusk ? T_DUSK : T_DAY;
      const round = P[(s >> 1) % 2];
      return { round, pine: isPine(c) ? (th.yoru ? NIWAKI_N : th.dusk ? NIWAKI_DUSK : NIWAKI) : round };
    },
    pixel: glowPixel,
  },
};

/* ---------- Fuji ----------
 * A broad concave cone centred between the boughs, its peak kept just under the lantern
 * string and lifted with the tree line as the forest grows, so the snow cap always shows.
 * It can't rise past the lanterns, so as the far treeline climbs its slopes it widens
 * instead, up to FUJI_WIDEN again as wide once the treeline reaches its peak. */
const FUJI_X = 0.55, FUJI_WIDEN = 0.9;
function fujiAt(env) {
  const { W, H, hor } = env, line = AF.treeLine(env);
  const y = Math.round(Math.max(H * 0.105, Math.min(H * 0.16, line - H * 0.25)));
  const cover = Math.max(0, Math.min(1, (hor - line) / Math.max(1, hor - y)));
  return { x: Math.round(W * FUJI_X), y, rise: hor - y, widen: 1 + FUJI_WIDEN * cover };
}
const FUJI = {
  day: { snowL: '#ffffff', snowLs: '#dbe9fb', snowS: '#b7d0f1', snowSs: '#94b3e4', bodyL: '#86a6de', bodyLs: '#7797d4', bodyS: '#6485cc', bodySs: '#5775bd', rim: 0.15 },
  dusk: { snowL: '#fde6e6', snowLs: '#f2c8d2', snowS: '#b8aad8', snowSs: '#9c90c8', bodyL: '#7c6aa6', bodyLs: '#6e5e9a', bodyS: '#5c4e8a', bodySs: '#50447c', rim: 0.12 },
  night: { snowL: '#c8d0ec', snowLs: '#aeb8e0', snowS: '#8a94c8', snowSs: '#7680b8', bodyL: '#34406e', bodyLs: '#2e3864', bodyS: '#262e58', bodySs: '#20284e', rim: 0.1 },
};
function toner(th) {
  const tint = th.tint ? hex(th.tint) : null, fog = th.fog ? hex(th.fog) : null, wet = th.rain || th.flat, grey = hex('#8a93a6');
  return (h, depth = 0) => {
    let c = typeof h === 'string' ? hex(h) : h;
    if (wet) c = mix(c, grey, 0.3 - depth * 0.1);
    if (fog) c = mix(c, fog, 0.6 - depth * 0.3);
    if (tint) c = mix(c, tint, Math.min(0.8, th.tintAmt * (0.6 + depth * 0.5)));
    return c;
  };
}
const hash2 = (a, b) => ((a * 73856093) ^ (b * 19349663)) >>> 0;

function fuji(env, lg) {
  const th = env.theme, { W, u, hor } = env, C = toner(th), F = fujiAt(env);
  const paint = (c, x, y) => { lg.fillStyle = rgb(c); lg.fillRect(x, y, 1, 1); };
  const P = FUJI[th.yoru ? 'night' : th.dusk ? 'dusk' : 'day'];
  const snowL = C(P.snowL), snowLs = C(P.snowLs), snowS = C(P.snowS), snowSs = C(P.snowSs);
  const bodyL = C(P.bodyL), bodyLs = C(P.bodyLs), bodyS = C(P.bodyS), bodySs = C(P.bodySs);
  const PK = F.x, PY = F.y, rise = F.rise, crater = Math.max(3, Math.round(4.5 * u)), half = rise * 2.7 * F.widen;
  for (let x = 0; x < W; x++) {
    const d = Math.abs(x + 0.5 - PK) - crater;
    let top;
    if (d < 0) top = PY + (Math.abs(x + 0.5 - PK) < crater * 0.5 && (x & 1) ? 1 : 0);
    else { const s = d / half; if (s >= 1) continue; top = PY + rise * (1 - Math.pow(1 - s, 1.9)); }
    top = Math.round(top);
    const xu = x / u, snowTo = PY + rise * 0.3 + rise * 0.14 * Math.pow(Math.abs(Math.sin(xu * 0.23 + 0.7)), 3) + rise * 0.06 * Math.abs(Math.sin(xu * 0.61));
    const lit = x + 0.5 < PK - crater * 0.3;
    for (let y = top; y < hor; y++) {
      const a = (x + 0.5 - PK) / (y - PY + 5 * u), streak = ((a * 7 % 1) + 1) % 1 < 0.14;
      const inSnow = y < snowTo || (y < snowTo + 3 * u && streak) || (y < snowTo + 1 && (x + y) & 1);
      let c = inSnow ? (lit ? (streak ? snowLs : snowL) : (streak ? snowSs : snowS)) : (lit ? (streak ? bodyLs : bodyL) : (streak ? bodySs : bodyS));
      if (y === top && !inSnow) c = mix(c, [255, 255, 255], P.rim);
      paint(c, x, y);
    }
  }
  /* two low ridges of little conifer tips at its foot, in the hills' own colours */
  const ridge = (f, amp, ph, col, depth) => {
    const base = PY + rise * f, cc = C(col, depth), ct = C(mix(hex(col), [255, 255, 255], 0.14), depth), cd = C(mix(hex(col), [0, 0, 0], 0.12), depth);
    for (let x = 0; x < W; x++) {
      const xu = x / u, tip = Math.abs(((xu + ph * 3) % 3) - 1.5) / 1.5;
      const y0 = Math.round(base + rise * amp * Math.sin(xu * 0.031 + ph) + rise * amp * 0.5 * Math.sin(xu * 0.093 + ph * 2) + tip * 2 * u);
      for (let y = Math.max(0, y0); y < hor; y++) paint(y - y0 < 1 ? ct : (hash2(Math.floor(xu / 3 + ph), y >> 1) % 4 === 0 ? cd : cc), x, y);
    }
  };
  ridge(0.66, 0.07, 1.1, th.far, 0.3);
  ridge(0.8, 0.06, 2.4, th.near, 0.5);
  env.fujiAt = F;
}

/* ---------- the moon (clear nights only), clear of the peak ---------- */
function moonAt(env) {
  const { W, H, u } = env, line = AF.treeLine(env);
  const r = Math.round(17 * u);
  const cy = Math.max(r + Math.round(4 * u), Math.min(Math.round(H * 0.2), Math.round(line - r * 1.1)));
  return { x: Math.round(W * 0.86), y: cy, r };
}
function paintMoon(env, g) {
  const th = env.theme, m = moonAt(env), { u } = env;
  const face = hex('#f6f0f2'), dim = mix(face, hex(th.sky[2]), 0.09), glow = hex('#a8a0d8');
  const gr = Math.round(10 * u);
  for (let y = m.y - m.r - gr; y <= m.y + m.r + gr; y++) for (let x = m.x - m.r - gr; x <= m.x + m.r + gr; x++) {
    const d = Math.hypot(x + 0.5 - m.x, y + 0.5 - m.y);
    if (d < m.r) continue;
    const k = (d - m.r) / gr; if (k > 1) continue;
    if (k < 0.35 ? (x + y) % 2 : (x % 2 || y % 2)) continue;
    g.fillStyle = rgb(glow, k < 0.35 ? 0.45 : 0.3); g.fillRect(Math.round(x), Math.round(y), 1, 1);
  }
  const maria = [[-0.32, -0.18, 0.3], [-0.12, -0.42, 0.18], [0.3, 0.12, 0.17], [0.42, -0.3, 0.1]];
  for (let y = m.y - m.r; y <= m.y + m.r; y++) for (let x = m.x - m.r; x <= m.x + m.r; x++) {
    const nx = (x + 0.5 - m.x) / m.r, ny = (y + 0.5 - m.y) / m.r, q = nx * nx + ny * ny;
    if (q > 1) continue;
    let c = face;
    for (const [mx, my, mr] of maria) if ((nx - mx) ** 2 + (ny - my) ** 2 < mr * mr * ((x + y) & 1 ? 1 : 0.55)) c = dim;
    if (q > 0.86 && nx > 0.2) c = mix(c, dim, 0.5);
    g.fillStyle = rgb(c); g.fillRect(x, y, 1, 1);
  }
  return m;
}

/* ---------- the boughs ----------
 * A great limb entering on the left and arching up out of the top of the frame, and a
 * second reaching in from the right, each throwing out sprays hung with blossom. Drawn once
 * per panel size. Where the right one crosses the moon it is a silhouette, backlit. */
const BOUGHS = [
  { c: [-0.02, 0.2, 0.2, 0.1, 0.46, -0.04, 7], sprays: [[0.18, 0.2, 0.3, 3], [0.36, 0.3, 0.2, 3], [0.28, 0.08, 0.34, 2], [0.62, 0.3, -0.02, 2]] },
  { c: [1.02, 0.08, 0.88, 0.02, 0.7, 0.06, 4.5], sprays: [[0.3, 0.9, 0.27, 2.5], [0.62, 0.76, 0.22, 2], [0.1, 0.99, 0.2, 2], [0.85, 0.68, 0.14, 1.5]] },
];
const TIE = [[0, 0.72], [1, 0.8]];
const quad = (a, b, c, f) => (1 - f) * (1 - f) * a + 2 * (1 - f) * f * b + f * f * c;
const boughAt = (env, i, f) => { const [x0, y0, cx, cy, x1, y1] = BOUGHS[i].c; return [quad(x0, cx, x1, f) * env.W, quad(y0, cy, y1, f) * env.H]; };

function buildBoughs(env, m) {
  const { W, H, u } = env, th = env.theme, night = th.yoru;
  const [cv, g] = layer(W, H), R = rng(4242);
  const tint = th.tint ? hex(th.tint) : null;
  const dim = col => rgb(tint && !night ? mix(col, tint, th.tintAmt * 0.6) : col);
  const onMoon = (x, y) => m && Math.hypot(x + 0.5 - m.x, y + 0.5 - m.y) < m.r;
  const SIL = hex('#0c0a1e'), BACK = hex('#4a2e5a'), RIM = hex('#d8a8cc');
  const paint = (col, x, y, w = 1, h = 1) => { g.fillStyle = dim(col); g.fillRect(Math.round(x), Math.round(y), w, h); };
  const wood = (col, x, y) => paint(onMoon(Math.round(x), Math.round(y)) ? SIL : col, x, y);
  const clusters = [];
  const limb = (x0, y0, cx, cy, x1, y1, t0, t1) => {
    const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 1.3), pts = [];
    for (let i = 0; i <= n; i++) {
      const f = i / n, x = quad(x0, cx, x1, f), y = quad(y0, cy, y1, f) + Math.sin(f * 17 + x0) * 0.8 * u;
      const tk = Math.max(1, Math.round(t0 + (t1 - t0) * f)), y0r = y - (tk >> 1);
      for (let q = 0; q < tk; q++) wood(q === 0 ? WOOD_L : q === tk - 1 && tk > 2 ? BARK.d : WOOD, x, y0r + q);
      pts.push([x, y, f]);
      if (f > 0.25 && R() < 0.13) clusters.push([x, y, 2.2 + R() * 1.6]);
    }
    clusters.push([x1, y1, 3 + R() * 1.2]);
    return pts;
  };
  for (const b of BOUGHS) {
    const [x0, y0, cx, cy, x1, y1, t] = b.c;
    const pts = limb(x0 * W, y0 * H, cx * W, cy * H, x1 * W, y1 * H, t * u, t * u * 0.4);
    for (const [f, sx, sy, st] of b.sprays) {
      const p = pts[Math.round(f * (pts.length - 1))];
      const ex = sx * W, ey = sy * H, mx = (p[0] + ex) / 2, my = Math.min(p[1], ey) - 3 * u;
      const sp = limb(p[0], p[1], mx, my, ex, ey, st * u, 1);
      for (const tf of [0.45, 0.75]) {
        const q = sp[Math.round(tf * (sp.length - 1))], dx = (ex - p[0]) > 0 ? 1 : -1;
        limb(q[0], q[1], q[0] + dx * 3 * u, q[1] + 1 * u, q[0] + dx * (5 + R() * 4) * u, q[1] + (3 + R() * 4) * u, 1, 1);
      }
    }
  }
  const P = night ? NIGHT_P : th.dusk ? DUSK_P : DAY_P;
  const pal = P[0], pale = night ? NIGHT_P[0] : th.dusk ? DUSK_P[0] : DAY_P[0], deep = P[1];
  const puffs = [];
  for (const [bx, by, r0] of clusters) { puffs.push([bx, by, r0]); if (r0 > 2.6) { puffs.push([bx - r0 * 0.8, by + r0 * 0.5, r0 * 0.65]); puffs.push([bx + r0 * 0.8, by + r0 * 0.4, r0 * 0.6]); } }
  puffs.sort((a, b) => a[1] - b[1]);
  for (const [bx, by, r0] of puffs) {
    const r = r0 * u, v = hashStr(Math.round(bx) + ',' + Math.round(by)) % 4, C = v === 0 ? pale : pal;
    for (let yy = -Math.ceil(r); yy <= r; yy++) for (let xx = -Math.ceil(r); xx <= r; xx++) {
      const q = (xx * xx + yy * yy) / (r * r); if (q > 1 || (q > 0.6 && R() < 0.25)) continue;
      const x = Math.round(bx + xx), y = Math.round(by + yy);
      if (onMoon(x, y)) { paint(q > 0.5 && R() < 0.6 ? RIM : BACK, x, y); continue; }
      const lit = -yy / r - xx / r * 0.3 + (R() - 0.5) * 0.4;
      paint(q > 0.65 && yy > 0 ? deep[2] : lit > 0.5 ? C[4] : lit > -0.1 ? C[3] : C[2], x, y);
    }
    for (let k = 0; k < 2; k++) {
      const x = Math.round(bx + (R() - 0.5) * r), y = Math.round(by + (R() - 0.5) * r);
      if (!onMoon(x, y)) paint(deep[1], x, y);
    }
  }
  return cv;
}

/* ---------- the lantern string, tied bough to bough, high over the peak ----------
 * Two lanterns each side, none over the summit, so the peak shows in the gap. */
const LAMP_AT = [0.08, 0.28, 0.72, 0.92];
function garland(env) {
  if (env.garland && env.garland.W === env.W) return env.garland;
  const { W, H } = env, [ax, ay] = boughAt(env, ...TIE[0]), [bx, by] = boughAt(env, ...TIE[1]);
  const sag = H * 0.02, pts = [], lamps = [];
  const n = Math.ceil(bx - ax);
  for (let i = 0; i <= n; i++) {
    const f = i / n;
    pts.push([Math.round(ax + (bx - ax) * f), Math.round(ay + (by - ay) * f + sag * 4 * f * (1 - f))]);
  }
  LAMP_AT.forEach((f, j) => { const p = pts[Math.round(n * f)]; lamps.push({ x: p[0], y: p[1], red: j % 2 === 0, ph: j * 1.7 }); });
  return (env.garland = { W, pts, lamps });
}

/* one chochin: a paper lantern with black caps, glowing from inside after dusk */
function chochin(g, x, y, red, lit, t, ph) {
  const flick = lit ? 0.85 + 0.15 * Math.sin(t * 2.3 + ph) : 0;
  const body = red ? (lit ? '#f0604a' : '#d0463c') : (lit ? '#fff0d8' : '#f4ead8');
  const core = red ? (lit ? '#ffb08a' : '#e45e4a') : (lit ? '#fffaf0' : '#fdf6ea');
  const rib = red ? '#a83028' : '#d8b89a';
  const hgt = 9, ly = y + 2, ROWS = [3, 5, 7, 7, 7, 7, 7, 5, 3];
  if (lit) {
    for (let dy = -5; dy <= hgt + 5; dy++) for (let dx = -8; dx <= 8; dx++) {
      const q = (dx / 7.5) ** 2 + ((dy - 4) / 8.5) ** 2; if (q > 1 || (q > 0.45 && (x + dx + ly + dy) & 1)) continue;
      g.fillStyle = `rgba(255,150,110,${(q > 0.45 ? 0.2 : 0.26) * flick})`; g.fillRect(x + dx, ly + dy, 1, 1);
    }
  }
  g.fillStyle = '#2a1a22'; g.fillRect(x, y, 1, 2);
  ROWS.forEach((w, r) => {
    const x0 = x - (w >> 1), cap = r === 0 || r === hgt - 1;
    g.fillStyle = cap ? '#2a1a22' : (r === 3 || r === 5) ? rib : body; g.fillRect(x0, ly + r, w, 1);
    if (!cap && w === 7) { g.fillStyle = rib; g.fillRect(x0, ly + r, 1, 1); g.fillRect(x0 + 6, ly + r, 1, 1); }
  });
  if (!lit) { g.fillStyle = red ? '#b83a32' : '#e6d6c0'; g.fillRect(x + 1, ly + 2, 2, 5); }
  g.fillStyle = core; g.fillRect(x - 1, ly + 2, 2, 5); g.fillRect(x - 2, ly + 3, lit ? 5 : 3, 3);
  if (!red) { g.fillStyle = '#d0403a'; g.fillRect(x - 1, ly + 3, 3, 3); g.fillStyle = core; g.fillRect(x, ly + 4, 1, 1); }
  g.fillStyle = red ? '#2a1a22' : '#c03a30'; g.fillRect(x, ly + hgt, 1, 2);
}

/* ---------- the breeze: sparse petals drifting on a gentle diagonal, each bobbing a little ---------- */
const WIND_P = ['#ffffff', '#fde4ee', '#f8c8d8', '#f4a8c4', '#d0608e'];
const NIGHT_WIND_P = ['#fbeefa', '#f0d0e6', '#dcb0d4', '#c898c4', '#9a6a9e'];
const windCols = env => env.theme.yoru ? NIGHT_WIND_P : WIND_P;
function dot(g, p, x, y, t, cols) {
  const flip = Math.sin(t * 4 + p.ph) > 0;
  g.fillStyle = cols[p.c];
  if (p.big) { g.fillRect(Math.round(x), Math.round(y), 2, 2); g.fillStyle = cols[4]; g.fillRect(Math.round(x) + (flip ? 1 : 0), Math.round(y) + 1, 1, 1); }
  else g.fillRect(Math.round(x), Math.round(y), flip ? 2 : 1, 1);
}
const seedOf = (env, k) => (((env.data.forestSeed || 9) ^ k) >>> 0);

const BREEZE_PETALS = 20;
function breeze(g, env, t) {
  const { W, H, u } = env, cols = windCols(env);
  const S = env.cfWind || (env.cfWind = (() => {
    const R = rng(seedOf(env, 0xb2ee)), n = Math.round(80 * (env.theme.yoru ? 0.6 : 1)), ps = [];
    for (let i = 0; i < n; i++) ps.push({ x: R(), y: R(), vx: (16 + R() * 10) * u, vy: (5 + R() * 4) * u, ph: R() * 6, c: (R() * 4) | 0, big: R() < 0.1 });
    return ps;
  })());
  const top = H * 0.7;
  for (const p of S) {
    const x = ((p.x * (W + 20) + t * p.vx) % (W + 20)) - 10;
    const y = ((p.y * top + t * p.vy) % top) + Math.sin(t * 1.1 + p.ph) * 2.5 * u;
    dot(g, p, x, y, t, cols);
  }
}

/* ---------- times of day ---------- */
const DAY = {
  sky: ['#5a92d2', '#74a6da', '#90b8e2', '#b0c8e8', '#d0d6ec', '#f0dce8'],
  far: '#a49cc4', near: '#8c8ab0', g0: '#8cb07a', g1: '#5e8a62', grass: '#eab8cc', haze: '#e4d8ea', hzStep: 0.12, water: '#a8c0e4',
  clouds: { n: 3, top: '#ffffff', bot: '#ecdcea', a: 235, speed: 3 },
};
const DUSK = {
  sky: ['#2a2250', '#46326a', '#6e437e', '#9c5488', '#cc728e', '#eea094'],
  orb: null, far: '#5e4a7a', near: '#4a3c62', g0: '#566450', g1: '#344238', grass: '#b0849a', haze: '#a888a8', hzStep: 0.11,
  water: '#6a5888', tint: '#4a2e58', tintAmt: 0.1, rim: null, shadow: 0,
  clouds: { n: 3, top: '#f2b0aa', bot: '#b0809e', a: 235 }, stars: 24, birdC: '#3a2a44',
};
const NIGHT = {
  sky: ['#050a1e', '#0a1232', '#121c48', '#1c2658', '#2a3066', '#3a3a70'],
  orb: null, far: '#1c2046', near: '#161a3a', g0: '#1c2434', g1: '#111826', grass: '#6a4a78', haze: '#2a2e5e', hzStep: 0.1,
  tint: '#141a3c', tintAmt: 0.1, water: '#1a2248', clouds: { n: 2, top: '#2e3468', bot: '#222858', a: 200 }, stars: 110, birdC: '#2a3148',
};
const clone = o => JSON.parse(JSON.stringify(o));


/* ---------- on the river ----------
 * The river winds down toward you (landscapes/river.js); its `center` and `halfWidth`
 * say where the water is at each depth p, from the horizon (0) to the bottom edge (1). */
const wcx = (env, p) => AF.landOf(env).center(p);
const whw = (env, p) => AF.landOf(env).halfWidth(p, env.W);
const rowOf = (env, p) => Math.round(env.hor + p * (env.H - env.hor));
const depthOf = (env, y) => (y - env.hor) / (env.H - env.hor);

/* bonbori stand along both banks, staggered, just outside the water's edge. Each is moved
 * up or down its bank to a spot no tree in front of it would cover, or left out. */
const BANK_P = { '-1': [0.3, 0.58, 0.87], '1': [0.42, 0.72, 0.95] };
function lampAt(env, side, p0) {
  const { W, H } = env, y = Math.min(H - 1, rowOf(env, p0)), p = depthOf(env, y), big = p > 0.5;
  const edge = W * (wcx(env, p) + side * whw(env, p)), x = Math.round(edge + side * (big ? 4.6 : 3.6)) - (big ? 1 : 0);
  // its box: the big lamp's pixels run x-1..x+3 and y-12..y, the small one's x-1..x+1 and y-6..y
  return { x, y, p, side, big, box: big ? [x - 1, y - 12, x + 4, y + 1] : [x - 1, y - 6, x + 2, y + 1] };
}
function hidden(env, b) {
  const [x0, y0, x1, y1] = b.box;
  for (const q of env.placed || []) {
    if (q.y <= b.y) continue;  // behind the lamp: drawn first, so it can't cover it
    const h = q.it.pond ? 4 : AF.STAGE_H[q.it.stage] * env.u * q.s, w = q.it.pond ? h * 4 : h * 1.25;
    if (q.x + w / 2 > x0 && q.x - w / 2 < x1 && q.y - h < y1 && q.y > y0) return true;
  }
  return false;
}
function bankLamps(env) {
  const out = [];
  for (const side of [-1, 1]) {
    const taken = [];
    for (const p0 of BANK_P[side]) {
      let best = null;
      for (let d = 0; d <= 0.1 && !best; d += 0.015) for (const s of d ? [1, -1] : [1]) {
        const p = Math.min(0.975, p0 + s * d);
        if (p < 0.2 || taken.some(t => Math.abs(t - p) < 0.14)) continue;
        const b = lampAt(env, side, p);
        if (!hidden(env, b)) { best = b; break; }
      }
      if (best) { out.push(best); taken.push(best.p); }
    }
  }
  return out.sort((a, b) => a.y - b.y);
}
/* a soft pixel halo: solid in the middle, dithered at the rim */
function halo(g, cx, cy, rx, ry, a) {
  const inner = `rgba(255,160,110,${a})`, outer = `rgba(255,160,110,${(a * 0.6).toFixed(3)})`;
  for (let y = Math.floor(cy - ry); y <= cy + ry; y++) for (let x = Math.floor(cx - rx); x <= cx + rx; x++) {
    const q = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2;
    if (q > 1 || (q > 0.5 && (x + y) & 1)) continue;
    g.fillStyle = q > 0.5 ? outer : inner; g.fillRect(x, y, 1, 1);
  }
}
/* one lamp: a paper box on a dark post, drawn into the land so trees in front hide it */
function paintLamp(g, b, lit) {
  const { x, y } = b;
  const paper = lit ? '#ffe4c4' : '#efe2cc', band = lit ? '#ff9a78' : '#c85a48', wood = '#2a1a22';
  if (!b.big) {
    if (lit) halo(g, x + 0.5, y - 4, 4, 4.5, 0.24);
    g.fillStyle = wood; g.fillRect(x, y - 2, 1, 3); g.fillRect(x - 1, y, 3, 1); g.fillRect(x - 1, y - 6, 3, 1);
    g.fillStyle = paper; g.fillRect(x - 1, y - 5, 3, 2);
    g.fillStyle = band; g.fillRect(x - 1, y - 3, 3, 1);
    return;
  }
  if (lit) halo(g, x + 1.5, y - 7.5, 6.5, 7, 0.24);
  g.fillStyle = wood; g.fillRect(x + 1, y - 5, 1, 6); g.fillRect(x - 1, y, 5, 1);
  g.fillRect(x - 1, y - 11, 5, 1); g.fillRect(x, y - 12, 3, 1);
  g.fillStyle = paper; g.fillRect(x, y - 10, 3, 5);
  g.fillStyle = band; g.fillRect(x, y - 6, 3, 1);
}
/* lamps go into the land in depth order, between the trees, through the engine's afterItem */
function plantLamps(env, lg) {
  const lamps = bankLamps(env), lit = env.theme.lampsLit, placed = env.placed || [];
  env.cfLamps = lamps;
  let i = 0;
  const upTo = (g, y) => { while (i < lamps.length && lamps[i].y < y) paintLamp(g, lamps[i++], lit); };
  if (!placed.length) return upTo(lg, Infinity);
  upTo(lg, placed[0].y);
  const next = new Map(placed.map((p, k) => [p, k + 1 < placed.length ? placed[k + 1].y : Infinity]));
  const prev = env.afterItem;
  env.afterItem = (g, p) => { if (prev) prev(g, p); if (next.has(p)) upTo(g, next.get(p)); };
}

/* on the river: petal rafts down the channel, the lamps' light on the water, the moon */
function riverFrame(g, env, t) {
  const S = env.river, th = env.theme;
  if (!S || !S.vis || th.frozen) return;
  const { W, H, u } = env, hor = env.hor, tt = env.still ? 0 : t;
  const seen = (x, y) => x >= 0 && x < W && y >= hor && y < H && S.vis[y * W + x];
  // the moon's light, scattered on the reach of the channel nearest it (the river only lays
  // glints under a sky orb, and the big moon here is painted, not an orb, so nothing doubles)
  const m = env.moonAt;
  if (m && !th.orb) {
    const R = rng(Math.floor(tt * 3) + 11), sig = W * 0.22;
    for (let y = hor + 3; y < H; y++) {
      const p = depthOf(env, y), cx = W * wcx(env, p), hw = W * whw(env, p), near = Math.exp(-(((cx - m.x) / sig) ** 2));
      for (let k = 0, n = 1 + Math.round(hw / 10); k < n; k++) {
        const r0 = R(), r1 = R(), r2 = R(), r3 = R();
        if (r0 > near * 0.7) continue;
        const x = Math.round(cx + (Math.sign(m.x - cx) * 0.35 + (r1 - 0.5) * 1.3) * hw);
        if (!seen(x, y)) continue;
        g.fillStyle = r2 < 0.3 ? 'rgba(255,250,255,.8)' : 'rgba(226,222,248,.5)';
        g.fillRect(x, y, r3 < 0.35 ? 2 : 1, 1);
      }
    }
  }
  // the lamps' warm light spilling onto the water beside them
  if (th.lampsLit && env.cfLamps) {
    const tick = Math.floor(tt * 3);
    for (const b of env.cfLamps) {
      const reach = Math.round((4 + b.p * 8) * u), y0 = b.y - (b.big ? 7 : 4);
      for (let y = y0; y < b.y + reach; y++) {
        const j = y - y0, f = 1 - j / (reach + b.y - y0);
        if (j > 4 && (y + tick) % 3 === 0) continue;
        const p = depthOf(env, y), edge = W * (wcx(env, p) + b.side * whw(env, p));
        const wob = j > 2 ? Math.round(Math.sin(tt * 1.4 + y * 0.9 + b.x) * 0.8) : 0;
        const len = 2 + Math.round((1.5 + b.p * 4) * f), x0 = b.side < 0 ? Math.ceil(edge) + 1 + wob : Math.floor(edge) - 1 - len + wob;
        g.fillStyle = j < 3 ? `rgba(255,226,184,${(0.95 * f).toFixed(3)})` : `rgba(255,180,128,${(0.8 * f).toFixed(3)})`;
        for (let x = x0; x < x0 + len; x++) if (seen(x, y)) g.fillRect(x, y, 1, 1);
      }
    }
  }
  // hanaikada: rafts of fallen blossom drifting down the channel toward you, growing as they come
  const R = rng(77), rafts = [], N = 13;
  for (let k = 0; k < N; k++) {
    const q = ((k + R() * 0.7) / N + tt * 0.014 * (0.85 + R() * 0.3)) % 1;
    rafts.push({ p: 0.05 + Math.pow(q, 1.25) * 0.95, lane: (R() - 0.5) * 1.2, seed: R() * 100, k, w: 0.8 + R() * 0.5 });
  }
  rafts.sort((a, b) => a.p - b.p);
  const cols = th.yoru ? ['#d8b0d0', '#b890b8', '#9a7aa8', '#ecd0e4'] : ['#f4b8ca', '#e892b0', '#f8c8d8', '#fff0f4'];
  for (const r of rafts) {
    const p = r.p, y = rowOf(env, p), hwp = W * whw(env, p);
    const len = Math.max(1, Math.round((1 + p * 9) * r.w * u)), cx = W * wcx(env, p) + r.lane * Math.max(0, hwp - len / 2 - 1);
    const x0 = Math.round(cx - len / 2 + Math.sin(tt * 0.7 + r.k) * 0.6 * p), two = p > 0.3 && len > 3;
    g.globalAlpha = p < 0.25 ? 0.4 + p * 2.4 : 1;
    for (let i = 0; i < len; i++) {
      const n = Math.sin(i * 1.7 + r.seed) + Math.sin(i * 0.6 + r.seed * 2);
      if (len > 3 && n < -1.1) continue;
      g.fillStyle = cols[(i + r.k) % 3];
      if (seen(x0 + i, y)) g.fillRect(x0 + i, y, 1, 1);
      if (two && i > 0 && i < len - 1 && n > -0.3 && seen(x0 + i, y - 1)) { g.fillStyle = n > 0.9 ? cols[3] : cols[(i + r.k + 1) % 3]; g.fillRect(x0 + i, y - 1, 1, 1); }
    }
    g.globalAlpha = 1;
  }
}
/* on a lake: the moon's column and petal rafts drifting across */
function bandFrame(g, env, t) {
  const { W, u } = env, L = env.water, th = env.theme;
  const m = env.moonAt;
  if (m) {  // the moon's column broken on the current
    const R = rng(Math.floor(t * 3));
    for (let j = 1; j < L.lh - 1; j++) {
      const hw = 2 + Math.round(j * 0.5 * u);
      for (let k = 0; k < 3; k++) if (R() < 0.6) {
        g.fillStyle = k ? 'rgba(236,230,250,.55)' : 'rgba(255,250,255,.85)';
        g.fillRect(m.x - hw + Math.round(R() * hw * 2), L.y0 + j, 1 + (R() < 0.4 ? 1 : 0), 1);
      }
    }
  }
  const R = rng(77), v = 0.6 * u;
  for (let k = 0; k < 9; k++) {
    const len = Math.round((7 + R() * 12) * u), y = L.y0 + 1 + Math.floor(R() * Math.max(1, L.lh - 3));
    const x0 = ((R() * W + t * v * (0.7 + R() * 0.6)) % (W + len)) - len, seed = R() * 100;
    for (let i = 0; i < len; i++) {
      const n = Math.sin(i * 1.7 + seed) + Math.sin(i * 0.6 + seed * 2);
      if (n < -0.6) continue;
      g.fillStyle = th.yoru ? ['#b890b8', '#d8a8cc', '#9a7aa8'][(i + k) % 3] : PETALS[(i + k) % 3];
      g.fillRect(Math.round(x0 + i), y + (n > 1.2 ? -1 : 0), 1, 1);
      if (n > 0.4 && i % 2 === 0) g.fillRect(Math.round(x0 + i), y + 1, 1, 1);
    }
  }
}
/* elsewhere, a row of bonbori along the front (the lake's shore, or the meadow's front edge) */
function rowLamps(env) {
  const { W, H } = env, L = env.water, y = L ? L.y0 - 1 : Math.round(H * 0.96), out = [];
  const n = Math.max(4, Math.round(W / 60));
  for (let i = 0; i < n; i++) out.push({ x: Math.round(W * (i + 0.5) / n + (hashStr('b' + i) % 9 - 4)), y });
  return out;
}
function rowFrame(g, env, t) {
  const L = env.water, th = env.theme, lit = th.lampsLit, wet = L && !th.frozen;
  for (const b of rowLamps(env)) {
    if (lit && wet) for (let j = 1; j < L.lh - 1; j++) {
      if ((j + Math.floor(t * 3)) % 3 === 0) continue;
      const wob = Math.round(Math.sin(t * 1.4 + j * 0.9 + b.x) * (1 + j * 0.08));
      g.fillStyle = `rgba(255,170,120,${0.55 * (1 - j / L.lh)})`; g.fillRect(b.x + wob, L.y0 + j, j < 4 ? 3 : 2, 1);
    }
    paintLamp(g, Object.assign({ big: true }, b), lit);
  }
}

AF.env('cherry_blossom', {
  pals: TREE.pals,
  look(mood, night) { return night ? clone(Object.assign({}, AF.TIMES.night, NIGHT)) : null; },
  theme(th, mood) {
    th.sakura = true;
    th.yoru = mood.time === 'night';
    th.dusk = mood.time === 'dusk';
    if (mood.time === 'day') Object.assign(th, clone(DAY));
    else if (th.dusk) Object.assign(th, clone(DUSK));
    th.lampsLit = th.dusk || th.yoru;
    th.wind = false;  // the breeze is its own; no gusting leaves on top of it
  },
  after(th) {
    const calm = !th.rain && !th.snowfall;
    if (calm) th.petals = Math.round(BREEZE_PETALS * (th.yoru ? 0.7 : 1));
    th.cfWind = calm && !th.fog;
    th.bigMoon = th.yoru && !th.rain && !th.fog && !th.deck;
    if (th.yoru && !th.bigMoon && !th.orb && !th.deck) th.orb = clone(AF.TIMES.night.orb);
    if (th.orb && th.orb.kind === 'sun') th.orb = null;  // Fuji is the day's centrepiece
    if (th.orb) { th.orb.x = 0.86; th.orb.y = 0.12; }
    if (th.clouds && !th.rain) { th.clouds.n = Math.min(th.clouds.n, 3); }
    th.rainbow = false;
    th.flies = th.lampsLit ? Math.min(th.flies || 0, 4) : th.flies;
  },
  prepare(env) { env.fxColors = { petals: ['#fbe0e8', '#f4b8ca', '#e892b0'], leaf: '#f4b8ca' }; env.cfWind = null; env.garland = null; env.cfLamps = null; },
  tree: TREE.tree,
  sky(env, g) { env.moonAt = env.theme.bigMoon ? paintMoon(env, g) : null; },
  backdrop(env, lg) { fuji(env, lg); },
  groundDetail(env, lg, p, sw, R, x, y) {
    if (p.it.kind !== 0 || p.it.stage < 2 || env.theme.snow) return;
    for (let k = 0; k < 6; k++) { lg.fillStyle = PETALS[k % 3]; lg.fillRect(x + Math.round((R() - 0.5) * sw * 1.2), y + Math.round(R() * 2), 1, 1); }
  },
  ground(env, lg, R) {
    if (AF.landOf(env).center) plantLamps(env, lg);  // the ground comes before the river's bed, so ask the landscape
    if (env.theme.snow) return;
    const { W, H, hor } = env;
    for (let k = 0; k < W * 0.3; k++) {
      const x = Math.round(R() * W), y = Math.round(hor + 3 + R() * (H - hor - 3));
      lg.fillStyle = PETALS[k % 3]; lg.fillRect(x, y, 1 + (k % 4 === 0 ? 1 : 0), 1);
    }
  },
  fx: {
    front(g, env, t, st, pass) {
      if (pass !== 'sky' || !env.theme.cfWind) return;
      breeze(g, env, t);
    },
  },
  frame(g, env, t) {
    if (env.river) riverFrame(g, env, t);
    else {
      if (env.water && !env.theme.frozen) bandFrame(g, env, t);
      rowFrame(g, env, t);
    }
    const { W } = env, lit = env.theme.lampsLit;
    const key = W + ':' + env.H + ':' + (env.moonAt ? env.moonAt.y : '-');
    if (!env.boughs || env.boughsKey !== key) { env.boughs = buildBoughs(env, env.moonAt); env.boughsKey = key; }
    g.drawImage(env.boughs, 0, 0);
    const G = garland(env);
    g.fillStyle = '#2a1a22';
    for (const [x, y] of G.pts) g.fillRect(x, y, 1, 1);
    for (const l of G.lamps) chochin(g, l.x, l.y, l.red, lit, t, l.ph);
  },
});
})();

/* Memory Forest - the starry night environment.
 * Everything this environment is lives here: delete it and starry_night.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * After Van Gogh's The Starry Night. The whole sky is laid on in short, directional
 * brushstrokes that follow a flow field: a great swirl on the left third and a smaller one
 * beside the moon, the far half of the lake mirroring the painted sky, each star wrapped in rings of strokes, a crescent moon in a golden halo.
 * The bright strokes shimmer slowly along the arms of the swirls. Flame-shaped cypresses
 * and trees whose crowns are spirals of strokes, a village asleep on the hills, and one
 * great cypress rising at the left edge the way it does in the painting. */
(function () {
'use strict';
const AF = window.AnkiForest;
const CFG = {"clear": 10, "low": 0.29, "ksMin": 0.85, "kvMin": 0.95, "vort": [{"x": 0.35, "y": 0.17, "R": 36, "rot": 1, "arms": 1.8, "s": 1.15, "eye": 0.35}, {"x": 0.63, "y": 0.12, "R": 19, "rot": -1, "arms": 1.6, "s": 0.95}], "stars": [[0.07, 0.09, 1.2], [0.19, 0.21, 1.6], [0.24, 0.05, 1.0], [0.11, 0.28, 0.8], [0.5, 0.04, 0.9], [0.55, 0.27, 1.3], [0.73, 0.06, 1.2], [0.76, 0.22, 1.5], [0.95, 0.27, 1.0], [0.27, 0.31, 0.8]], "orb": [0.87, 0.12, 6.5], "band": [0.24, 7], "bandGain": 0.42, "armGain": 0.8, "jit": 0.25, "len": 1.2, "shimCap": 1600, "shimAt": 0.4, "shimSpeed": 0.7, "halo": 1.3, "moonHalo": 2.8, "deepBands": 1, "hillsOver": 2, "skyMirror": [0.45, 0.26], "vClamp": 0.55, "armBias": -0.12, "flatHills": 0.5};
const { hex, mix, mixHex, rgb, rng, hashStr, layer } = AF.u;
const H6 = a => a.map(hex);
const TAU = Math.PI * 2;

/* Each hour: ramp is the swirl's paint, dark to light; base the sky under the strokes;
 * teal the green-blue the painting slips into its swirls; orb its moon or sun. */
const LOOKS = {
  night: { ramp: ['#0b1644', '#14286e', '#1d3d92', '#2c58ad', '#4d80c6', '#8fb6da', '#dfeade'], base: ['#0a1238', '#0f1d56', '#172f72', '#1f4288', '#285298', '#325e9c'],
    teal: ['#1f6a80', '#3a8ea0'], orb: 'moon', gold: ['#fff6c0', '#f4d450', '#dca030'], hills: ['#1c3264', '#14264e'], ground: ['#15294e', '#0c1a34'],
    tint: '#0a1440', tintAmt: 0.16, haze: '#1a2c5c', water: '#12265a', windows: '#f4c850' },
  dusk: { ramp: ['#1a1a52', '#2a2c78', '#40449a', '#6a5cae', '#a078a8', '#e0a890', '#f8dcb0'], base: ['#141a4a', '#1e2866', '#2e3a82', '#4a4a92', '#7a5a96', '#a06a8a'],
    teal: ['#2e6a86', '#4a90a0'], orb: 'moon', gold: ['#fff0c0', '#f8c850', '#e08a30'], hills: ['#2a2e62', '#1e2450'], ground: ['#1e2c48', '#121c34'],
    tint: '#2a2050', tintAmt: 0.14, haze: '#4a4878', water: '#2a3066', windows: '#f8c850' },
  dawn: { ramp: ['#2a3a7a', '#3e5698', '#5a78b4', '#86a0c8', '#b8b8d0', '#eac8c0', '#fff0d8'], base: ['#26366e', '#34508c', '#4c6ca8', '#7a8cbc', '#b0a8c4', '#e0bcb8'],
    teal: ['#4a8aa0', '#78b0b8'], orb: 'sun', gold: ['#fffae0', '#ffe090', '#f4b060'], hills: ['#50608e', '#3a4a78'], ground: ['#3e5a6a', '#2a4250'],
    tint: '#6a5a8a', tintAmt: 0.08, haze: '#9aa0c0', water: '#5a70a0', windows: '#f8d070' },
  day: { ramp: ['#1e4a9a', '#2a62b4', '#3c7cc8', '#5c9ad6', '#88bce2', '#bcdcec', '#f2f6ec'], base: ['#1c4690', '#265aa8', '#3470bc', '#4a88c8', '#6aa2d4', '#8cb8dc'],
    teal: ['#3a9aa8', '#6ac0c0'], orb: 'sun', gold: ['#fffcec', '#fff0a0', '#f8d060'], hills: ['#3a64a0', '#2c5088'], ground: ['#2e6a5a', '#1e4c44'],
    tint: null, tintAmt: 0, haze: '#8ab0d0', water: '#3a70b0', windows: null },
  golden_hour: { ramp: ['#1e3272', '#2e4a92', '#4a68aa', '#7a88b4', '#c0a090', '#f0c070', '#fff0b0'], base: ['#1c2e68', '#2a4486', '#42609e', '#7082a8', '#b09a94', '#e0b480'],
    teal: ['#3a8098', '#5aa0a8'], orb: 'sun', gold: ['#fff8d0', '#ffd870', '#f09a40'], hills: ['#3e4a80', '#2e3a6a'], ground: ['#2e5250', '#1e3a3a'],
    tint: '#6a4a3a', tintAmt: 0.06, haze: '#a09aa8', water: '#3e5a90', windows: '#f8c850' },
};

// the trees: tones run outline, shade, mid, lit, highlight. Swirl crowns come in three
// greens that lean blue; cypresses are near black. Nothing healthy is ever yellow.
const ROUNDS = [
  H6(['#07141a', '#12343c', '#1e5552', '#2f7a68', '#5aa88c']),
  H6(['#08121e', '#142c4a', '#1f4a68', '#2e6e84', '#5c9cb4']),
  H6(['#0a160f', '#153a2a', '#23583e', '#377a50', '#64a078']),
];
const CYPRESS = H6(['#03090b', '#0c2220', '#153a30', '#235a44', '#3a8060']);
const BARK = { l: hex('#3a3a4a'), m: hex('#26263a'), d: hex('#141626') };

/* ---------- the sky: a flow field and the brushstrokes laid along it ---------- */

function field(env) {
  const { W, H, u, hor } = env, line = AF.treeLine(env);
  // The sky is one composition, its lowest stars at 0.29 of the height. Above a forest
  // (and the hills risen with it) that leaves less room, it is scaled down as a whole,
  // pieces and all, rather than having the low pieces pile up in a row along the tree tops.
  const lift = env.ridges && env.ridges.lift ? env.ridges.lift() : 0;
  const k = Math.min(1, (Math.min(line, hor - lift) - CFG.clear * u) / (CFG.low * H)), ks = Math.max(CFG.ksMin, k);
  // the swirls keep more of their size than the sky's height does: they are the point
  const kv = Math.max(CFG.kvMin, k);
  const sy = y => y * H * k;
  // (a big swirl never slides up off the top of the picture: it keeps most of itself in view)
  const vort = CFG.vort.map(v => ({ x: v.x * W, y: Math.max(sy(v.y), v.R * u * kv * CFG.vClamp), R: v.R * u * kv, rot: v.rot, arms: v.arms, s: v.s, eye: v.eye || 0 }));
  const stars = CFG.stars
    .map(([x, y, s]) => ({ x: x * W, y: sy(y), R: (6 + 3 * s) * u * ks, rot: 1, s, star: true }));
  const orb = { x: CFG.orb[0] * W, y: sy(CFG.orb[1]), r: CFG.orb[2] * u * ks };
  return { vort, stars, orb, ks, k, all: vort.concat(stars, [{ x: orb.x, y: orb.y, R: orb.r * 2.4, rot: -1, s: 0.8 }]), band: x => sy(CFG.band[0]) + Math.sin(x / W * TAU * 1.1 + 0.8) * CFG.band[1] * u * k, hor };
}

/* the direction the paint goes at a point, and how light it is there (0 dark .. 1 light) */
function flow(F, env, x, y) {
  const { W, u, hor } = env;
  const a0 = 0.22 * Math.sin(x / W * TAU * 1.2 + y / (9 * u));
  let vx = Math.cos(a0) * 0.7, vy = Math.sin(a0) * 0.7;
  let b = 0.1 + 0.32 * Math.max(0, y / hor), ph = x * 0.05;
  // the long wave rolling across the sky under the swirls
  const bd = Math.abs(y - F.band(x)) / (4.5 * u);
  if (bd < 1.6) { b += CFG.bandGain * Math.max(0, 1 - bd * bd / 2.6); vy += Math.cos(x / env.W * TAU * 1.1 + 0.8) * 0.25; }
  for (const v of F.all) {
    const dx = x - v.x, dy = y - v.y, d = Math.hypot(dx, dy) + 0.01, q = d / v.R, w = Math.exp(-q * q * 1.1);
    if (w < 0.01) continue;
    vx += (-dy / d * v.rot - dx / d * 0.3) * w * 2.4; vy += (dx / d * v.rot - dy / d * 0.3) * w * 2.4;
    if (!v.star && v.arms) {  // spiral arms: bands of light winding in
      const th = Math.atan2(dy, dx), arm = 0.5 + 0.5 * Math.cos(q * TAU * v.arms - th * v.rot);
      const flat = Math.exp(-Math.pow(q / 1.05, 4));
      b += flat * (arm * CFG.armGain + CFG.armBias) * v.s; ph = q * 5 - th * v.rot;
      // the eye of the swirl: a pale knot of paint at its heart
      if (v.eye && q < 0.32) b += v.eye * (1 - q / 0.32);
    }
  }
  return { a: Math.atan2(vy, vx), b: Math.max(0, Math.min(1, b)), ph };
}

/* a short dash of paint, pixel by pixel */
function dashPx(x, y, a, len) {
  const out = [], cx = Math.cos(a), cy = Math.sin(a);
  let lx = null, ly = null;
  for (let s = 0; s < len; s += 0.7) {
    const px = Math.round(x + cx * s), py = Math.round(y + cy * s);
    if (px !== lx || py !== ly) { out.push(px, py); lx = px; ly = py; }
  }
  return out;
}

function paintSky(env, g) {
  const th = env.theme, look = th.piLook; if (!look) return;
  const { W, u, hor } = env, R = rng(1889), F = field(env);
  const dim = th.piDim, grey = th.piGrey;
  const shade = c => dim ? mix(hex(c), hex(grey), dim) : hex(c);
  const ramp = look.ramp.map(shade), teal = look.teal.map(shade), gold = look.gold.map(shade);
  const top = hor + 1, list = [], shimmer = [];
  const put = (px, col) => { g.fillStyle = rgb(col); for (let i = 0; i < px.length; i += 2) if (px[i + 1] < top) g.fillRect(px[i], px[i + 1], 1, 1); };
  // strokes on a jittered grid, laid down in a shuffled order so they overlap like paint
  const step = Math.max(1.6, 1.9 * u * 0.5 + 1);
  for (let y = -1; y < top; y += step) for (let x = -2; x < W + 2; x += step * 1.4) list.push([x + R() * step * 1.4, y + R() * step, R()]);
  list.sort((p, q) => p[2] - q[2]);
  for (const [x, y] of list) {
    const f = flow(F, env, x, y);
    let k = Math.round(f.b * (ramp.length - 1) + (R() - 0.5) * 1.3);
    k = Math.max(0, Math.min(ramp.length - 1, k));
    let col = ramp[k];
    if (k >= 2 && k <= 4 && R() < 0.22) col = teal[k > 3 ? 1 : 0];
    const px = dashPx(x, y, f.a + (R() - 0.5) * CFG.jit, (2.6 + R() * 2.2) * CFG.len * Math.max(1, u * 0.8));
    put(px, col);
    // the light strokes of the swirls shimmer later, a shade lighter, in waves along the arms
    if (k >= 4 && k < ramp.length - 1 && shimmer.length < CFG.shimCap) shimmer.push({ px, c: rgb(ramp[k + 1]), ph: f.ph });
  }
  // the stars: a hot core and rings of strokes wound round it
  const ring = (cx, cy, r0, r1, cols, sh) => {
    for (let r = r0; r <= r1; r += 1.3) {
      const n = Math.max(6, Math.round(TAU * r / 2.6)), off = R() * TAU;
      for (let i = 0; i < n; i++) {
        const a = off + i / n * TAU, x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
        const col = cols[(i + Math.round(r)) % cols.length], px = dashPx(x, y, a + Math.PI / 2 + 0.15, 2.4 + R() * 1.5);
        put(px, col);
        if (sh && shimmer.length < CFG.shimCap + 500) shimmer.push({ px, c: rgb(mix(col, [255, 255, 240], 0.45)), ph: a * 2 + r });
      }
    }
  };
  const disc = (cx, cy, r, colF) => {
    for (let y = Math.floor(cy - r); y <= cy + r; y++) for (let x = Math.floor(cx - r); x <= cx + r; x++) {
      const c = colF(x + 0.5 - cx, y + 0.5 - cy); if (!c) continue;
      g.fillStyle = rgb(c); g.fillRect(x, y, 1, 1);
    }
  };
  const night = look.orb === 'moon';
  env.piStars = [];
  for (const s of F.stars) {
    if (!night) break;  // by day the swirls have the sky to themselves
    const su = u * F.ks, rc = (0.9 + s.s * 0.9) * su;
    ring(s.x, s.y, rc + 1, rc + 2.4 * su, [gold[1], gold[2], gold[1]], true);
    ring(s.x, s.y, rc + 2.6 * su, rc + (3.2 + s.s * 1.6) * CFG.halo * su, [ramp[5], gold[1], ramp[6], ramp[4]], s.s > 1.1);
    disc(s.x, s.y, rc, (dx, dy) => Math.hypot(dx, dy) < rc * 0.55 ? [255, 255, 240] : gold[0]);
    env.piStars.push({ x: s.x, y: s.y, r: rc, s: s.s });
  }
  // the moon: a fat crescent inside a disc of halo, or the sun wrapped in its own rings
  const o = F.orb, r = o.r;
  ring(o.x, o.y, r + 1.5, r * 1.55, [gold[1], gold[2], gold[1], gold[0]], true);
  ring(o.x, o.y, r * 1.6, r * 2.15, [ramp[6], gold[1], ramp[5], gold[0]], true);
  ring(o.x, o.y, r * 2.2, r * CFG.moonHalo, [ramp[5], gold[1], ramp[6], ramp[4], gold[2]], true);
  if (night) {
    disc(o.x, o.y, r * 1.35, (dx, dy) => {
      const d = Math.hypot(dx, dy); if (d > r * 1.35) return null;
      const cut = Math.hypot(dx - r * 0.5, dy + r * 0.35) < r * 0.92;
      if (d < r && !cut) return d > r - 1.2 ? gold[2] : mix(gold[0], gold[1], Math.max(0, Math.min(1, (d / r - 0.4) * 1.4)));  // the crescent
      if (d < r) return mix(gold[2], ramp[1], 0.55);  // the dark of the moon, glowing orange
      return mix(gold[2], ramp[3], 0.35);  // its glow
    });
  } else {
    disc(o.x, o.y, r * 1.15, (dx, dy) => { const d = Math.hypot(dx, dy); return d < r * 0.8 ? [255, 255, 236] : d < r * 1.15 ? gold[0] : null; });
  }
  env.piOrb = { x: o.x, y: o.y, r, night };
  env.piField = F;
  env.piShimmer = shimmer;
}

/* ---------- the sky in the lake, and paint gliding along the swirls ---------- */

/* The lake holds the painted sky: past the trees' reflection, the rows further out reflect
 * the swirls themselves, stained less by the water so their blues and golds still read. */
function mirrorSky(env) {
  const { W, H } = env, L = env.water, lh = L.lh, shore = Math.round(H * 0.765);
  const line = Math.max(2, Math.round(Math.min(AF.treeLine(env), env.ridges.far(Math.round(W / 2)))));
  const [, kg] = layer(W, H); kg.drawImage(env.sky, 0, 0);
  const rg = L.rf.getContext('2d'), wc = hex(env.theme.water), dim = env.theme.piDim || 0;
  // the land's reflection keeps the rows the engine gave it; from the row it reaches the
  // tree tops on, the sky follows, from its foot up to its top
  let j0 = lh;
  for (let j = 0; j < lh; j++) if (shore - 1 - Math.round(j * 2.9) <= line) { j0 = j; break; }
  j0 = Math.min(j0, Math.round(lh * CFG.skyMirror[0]));
  const rows = lh - j0; if (rows < 3) return;
  const sd = kg.getImageData(0, 0, W, H).data, img = rg.getImageData(0, 0, W, lh), d = img.data;
  const stain = CFG.skyMirror[1] + dim * 0.2;
  for (let j = j0; j < lh; j++) {
    const f = (j - j0) / Math.max(1, rows - 1), sy = Math.max(0, Math.round(line - 1 - f * (line - 1)));
    // each row of water is a stroke combed sideways
    const off = Math.round(Math.sin(j * 1.7) * 1.5);
    for (let x = 0; x < W; x++) {
      const sx = Math.max(0, Math.min(W - 1, x + off)), i = (sy * W + sx) * 4, o = (j * W + x) * 4;
      const blend = Math.min(1, (j - j0 + 1) / 3);  // eased in over the first rows
      let c = mix([sd[i], sd[i + 1], sd[i + 2]], wc, stain + 0.12 * (1 - f));
      c = mix([d[o], d[o + 1], d[o + 2]], c, blend);
      if (j % 3 === 1 && (x + j * 5) % 9 < 2) c = mix(c, [255, 255, 255], 0.1);
      d[o] = c[0]; d[o + 1] = c[1]; d[o + 2] = c[2];
    }
  }
  rg.putImageData(img, 0, 0);
}

/* the shimmer's pixel buffer, as tall as its lowest stroke reaches, cleared for a frame */
function shimBuffer(env, S) {
  let b = env.piShimBuf;
  if (!b) {
    let h = 1;
    for (const s of S) for (let i = 1; i < s.px.length; i += 2) h = Math.max(h, s.px[i] + 1);
    const c = document.createElement('canvas'); c.width = env.W; c.height = h;
    const g = c.getContext('2d'), img = g.createImageData(env.W, h);
    b = env.piShimBuf = { w: env.W, h, c, g, img, px: new Uint32Array(img.data.buffer) };
  }
  b.px.fill(0);
  return b;
}
/* an opaque 'rgba(r,g,b,1)' as one pixel of a Uint32Array over ImageData (bytes r, g, b, a) */
const packed = c => { const [r, g, b] = c.match(/\d+/g).map(Number); return ((255 << 24) | (b << 16) | (g << 8) | r) >>> 0; };

/* ---------- the land: hills in strokes, a village asleep on them ---------- */

const strokeOf = (x, y) => {
  const off = hashStr('r' + y) % 5, id = Math.floor((x + off + Math.sin(y * 0.4) * 2) / 4);
  return hashStr(id + ',' + y) % 5;
};
function stroke(c, x, y, k = 1) {
  const v = strokeOf(x, y);
  return v === 0 ? mix(c, [200, 220, 255], 0.14 * k) : v === 1 ? mix(c, [0, 0, 10], 0.22 * k) : v === 2 ? mix(c, [60, 140, 150], 0.12 * k) : c;
}

function backdrop(env, g) {
  const th = env.theme, look = th.piLook, { W, u, hor } = env, rd = env.ridges;
  const tint = c => th.tint ? mix(hex(c), hex(th.tint), th.tintAmt * 0.4) : hex(c);
  const far = tint(th.far), near = tint(th.near);
  for (let x = 0; x < W; x++) {
    const f = rd.far(x), n = rd.near(x);
    for (let y = f; y < hor; y++) {
      const c = y >= n ? near : far;
      g.fillStyle = rgb(stroke(y === f || y === n ? mix(c, [255, 255, 255], 0.12) : c, x, y)); g.fillRect(x, y, 1, 1);
    }
  }
  // the village: little houses on the near hill, and the church with its needle spire
  const R = rng(1853), wall = mix(near, [0, 0, 0], 0.35), roof = mix(near, [0, 0, 0], 0.55), lit = look.windows && !th.fog ? hex(look.windows) : null;
  const x0 = Math.round(W * 0.28), x1 = Math.round(W * 0.66), church = Math.round(W * 0.47);
  for (let x = x0; x < x1; x += Math.round((3 + R() * 3) * u)) {
    const w = Math.round((2.5 + R() * 2.5) * u), h = Math.round((1.8 + R() * 1.8) * u), b = rd.near(x + (w >> 1)) + Math.round(u);
    g.fillStyle = rgb(wall); g.fillRect(x, b - h, w, h);
    g.fillStyle = rgb(roof);
    for (let k = 0; k <= Math.ceil(w / 2); k++) g.fillRect(x + k, b - h - Math.min(k, w - k) * 0.6 | 0, 1, Math.max(1, (Math.min(k, w - k) * 0.6) | 0));
    if (lit && R() < 0.7) { g.fillStyle = rgb(lit); g.fillRect(x + 1 + Math.floor(R() * Math.max(1, w - 2)), b - h + 1 + Math.floor(R() * Math.max(1, h - 2)), 1, 1); }
  }
  const cb = rd.near(church) + Math.round(u), cw = Math.round(3 * u), sh = Math.round(14 * u);
  g.fillStyle = rgb(roof); g.fillRect(church - cw, cb - Math.round(4 * u), cw * 3, Math.round(4 * u));
  for (let k = 0; k < sh; k++) { const hw = Math.max(0, Math.round((cw / 2) * (k / sh))); g.fillRect(church - hw, cb - Math.round(4 * u) - sh + k, hw * 2 + 1, 1); }
  if (lit) { g.fillStyle = rgb(lit); g.fillRect(church, cb - Math.round(2 * u), 1, 1); }
}

/* The hills with the village on them always stand clear of the tree tops: a bigger
 * forest stands taller, so the hills rise with it instead of disappearing behind it.
 * Their foot sits this far above the top of the forest (in env.u). */
const HILLS_OVER_TREES = CFG.hillsOver;
function hillRidges(env, p) {
  const { W, u, hor } = env, own = AF.landOf(env).ridges;
  const base = own ? own(env, p) : {
    far: x => { const f = x / W * TAU; return Math.round(hor - (7 * u + 5 * u * Math.sin(f * 1.3 + p.p1) + 3 * u * Math.sin(f * 3.7 + p.p2))); },
    near: x => { const f = x / W * TAU; return Math.round(hor - (2 * u + 3 * u * Math.sin(f * 2.1 + p.p3) + 1.5 * u * Math.sin(f * 5.3 + p.p1))); },
  };
  // measured on first use: the ground is drawn after the trees are placed
  let lift = null;
  const up = () => {
    if (lift !== null) return lift;
    if (!env.placed) return 0;
    lift = Math.max(0, Math.round(hor + HILLS_OVER_TREES * u - AF.treeLine(env)));
    return lift;
  };
  // risen over a big forest, the far hills lie lower behind the near ones, so the sky keeps its room
  const fl = () => 1 - CFG.flatHills * Math.min(1, up() / (8 * u));
  return Object.assign({}, base, { far: x => Math.round(base.near(x) - up() - (base.near(x) - base.far(x)) * fl()), near: x => base.near(x) - up(), lift: up });
}

/* ---------- the trees ---------- */

/* a cypress: a tall dark flame, licked at its edges, painted in twisting upward strokes */
function cypress(c) {
  const { t, h, W, w, cx, base, tone, put, pick, R, bark, hole } = c;
  const top = 1, foot = base - Math.max(1, Math.round(h * 0.06)), n = foot - top + 1;
  for (let y = foot; y <= base; y++) put(cx, y, bark.d);
  const ph = (t.seed % 11) * 0.7, lean = ((t.seed % 5) - 2) * 0.22;
  for (let y = top; y <= foot; y++) {
    const p = (y - top + 0.5) / n;
    const prof = p < 0.68 ? Math.pow(p / 0.68, 0.7) : 1 - (p - 0.68) / 0.32 * 0.3;
    const off = Math.sin(p * 8 + ph) * w * 0.1 * (1 - p * 0.6) + lean * (1 - p) * w * 0.45;
    const hw = Math.max(0.6, (w / 2) * prof + Math.sin(p * 19 + ph * 2) * 0.55);
    for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - (cx + 0.5 + off); if (Math.abs(dx) > hw) continue;
      if (hole && R() < hole) continue;
      const sid = Math.floor(dx / Math.max(1, hw) * 2.2 + Math.sin(p * 11 + ph) * 0.7 + 4);
      const seg = Math.floor((y + sid * 2) / 3);
      const mod = (sid + seg) & 1 ? 0.35 : -0.25;
      tone[y * W + x] = pick(-dx / Math.max(1, hw) * 0.55 + 0.05 - p * 0.15 + mod + (R() - 0.5) * 0.2);
    }
  }
  return { top, ch: foot - top };
}

/* a broadleaf whose crown is a spiral of strokes winding into its middle */
function swirlCrown(c) {
  const { t, W, H, w, ch, cx, top, tone, pick, R, hole } = c;
  const rx = w / 2, ry = ch / 2, ox = cx + 0.5, oy = top + ry - 0.5, rot = t.seed & 1 ? 1 : -1, ph = (t.seed % 7) * 0.9;
  const rmin = Math.min(rx, ry);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const nx = (x + 0.5 - ox) / rx, ny = (y + 0.5 - oy) / ry, r = Math.hypot(nx, ny), a = Math.atan2(ny, nx);
    if (r > 1 + 0.1 * Math.sin(a * 5 + ph) - 0.05) continue;
    if (hole && R() < hole) continue;
    const rp = r * rmin, k = Math.floor(rp / 1.7 + rot * a / TAU * 1.2 + ph);
    const seg = Math.floor((a * rp + k * 2.3) / 3.1);
    const mod = (k + seg) & 1 ? 0.28 : -0.3;
    tone[y * W + x] = pick(-(nx * 0.55 + ny * 0.75) * 0.55 + mod + (R() - 0.5) * 0.15);
  }
  return true;
}

/* the great cypress in front of it all, rising at the left edge into the sky: a few
 * tongues of dark flame twisting up together, painted in long curving strokes */
function buildCypress(env) {
  const { W, H, u } = env, th = env.theme, [cv, g] = layer(W, H);
  const tint = th.tint ? hex(th.tint) : null, dim = th.piDim ? hex(th.piGrey) : null;
  const pal = H6(['#020607', '#061214', '#0b201e', '#13322a', '#1f4a3a', '#34684e']).map(c => { const q = tint ? mix(c, tint, th.tintAmt * 0.4) : c; return dim ? mix(q, dim, th.piDim * 0.4) : q; });
  const cx = W * 0.05, topY = H * 0.04;
  // tongues: sideways offset at the foot, where the tip is (share of the height), width, sway
  const tongues = [{ dx: 0, tip: 0, w: 7, sw: 1, out: 0 }, { dx: 5, tip: 0.12, w: 4, sw: -1, out: 5 }, { dx: -4, tip: 0.22, w: 4, sw: 1, out: -5 }, { dx: 7, tip: 0.34, w: 4, sw: 1, out: 6 }, { dx: -6, tip: 0.45, w: 4, sw: -1, out: -6 }, { dx: 8, tip: 0.56, w: 4.5, sw: 1, out: 6 }, { dx: -7, tip: 0.66, w: 4.5, sw: -1, out: -5 }];
  const cover = new Int8Array(W * H).fill(-1);
  tongues.forEach((tg, ti) => {
    const y0 = topY + (H - topY) * tg.tip;
    for (let y = Math.max(0, Math.round(y0)); y < H; y++) {
      const p = (y - y0) / (H - y0);
      const prof = ti ? Math.min(1, Math.pow(p / 0.25, 0.7)) * (1 - p * 0.3) : p < 0.4 ? Math.pow(p / 0.4, 0.6) : 1 - (p - 0.4) * 0.3;
      // the tip curls over; lower down the tongue sways
      const off = (tg.dx + tg.sw * Math.sin(p * 6.5 + ti) * 1.6 * (1 - p * 0.4) + tg.out * Math.pow(Math.max(0, 1 - p * 4), 2) + (ti ? 0 : (1 - p) * (1 - p) * 4)) * u;
      const hw = (tg.w * prof + Math.sin(p * 30 + ti * 2) * 0.9) * u;
      for (let x = Math.floor(cx + off - hw); x <= cx + off + hw; x++) {
        if (x < 0 || x >= W) continue;
        const dx = (x + 0.5 - cx - off) / Math.max(1, hw);
        // strokes run up the tongue, bending with it; each stroke a few pixels long
        const sid = Math.floor(dx * 2.6 + Math.sin(p * 16 + ti) * 0.9 + 8);
        const seg = Math.floor((y / u + (hashStr('s' + ti + ',' + sid) % 6)) / 5);
        const hsh = hashStr(ti + ',' + sid + ',' + seg) % 100 / 100;
        const l = -dx * 0.55 - ti * 0.06 + (hsh - 0.5) * 0.9;
        const k = Math.abs(dx) > 0.9 ? 0 : l > 0.5 ? 5 : l > 0.2 ? 4 : l > -0.1 ? 3 : l > -0.45 ? 2 : 1;
        cover[y * W + x] = k;
      }
    }
  });
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let k = cover[y * W + x]; if (k < 0) continue;
    if (x + 1 >= W || cover[y * W + x + 1] < 0 || y === 0 || cover[(y - 1) * W + x] < 0) k = 0;  // a dark rim where it meets the sky
    g.fillStyle = rgb(pal[k]); g.fillRect(x, y, 1, 1);
  }
  return cv;
}

/* the study calendar's tiles laid on as the painted sky is: rows of short strokes in three tones
 * (the shade, its darker tone and a touch of moonlight), offset row to row, a stroke's end now and
 * then short of the tile's side */
const MOONLIGHT = hex('#faecaa');
const tileNoise = (x, y, s) => (hashStr(s + ',' + x + ',' + y) % 1000) / 1000;
function calendarTile(g, pal, edge, v, T) {
  // (its own darker tone and more moonlight than the page's shades give: on the paler 2026-10-14
  // shades the strokes otherwise all but vanished)
  const n = T - 1, tones = [pal[0], mix(pal[0], [16, 16, 16], 0.16), mix(pal[0], MOONLIGHT, 0.22), pal[0]];  // (the last row and column: the gap)
  for (let y = 0; y < n; y++) {
    for (let x = (y + v) % 2 ? -1 : -2 - (v & 1), k = 0; x < n; k++) {
      const len = tileNoise(x, y, v) < 0.5 ? 3 : 4, c = tones[(y * 3 + k + v) % 4];
      for (let i = 0; i < len; i++) {
        const px = x + i;
        if (px < 0 || px >= n) continue;
        if ((px === 0 && i === 0 || px === n - 1 && i === len - 1) && tileNoise(px, y, 9 + v) < 0.5) continue;
        g.fillStyle = rgb(c); g.fillRect(px, y, 1, 1);
      }
      x += len;
    }
  }
}

AF.env('starry_night', {
  calendar: '#3a5aa8',  // the study calendar in the painting's night blue (its cypresses' green said nothing of it)
  calendarDay: ['#3c7cc8', '#5aa88c'],  // and by day, from the daylit sky's blue to the trees' green (calendar.js hourOf)
  calendarTile,
  pals: { rounds: ROUNDS, pine: CYPRESS, bark: BARK, leaf: hex('#2f7a68'), leafL: hex('#5aa88c'), stem: hex('#1e5552') },
  flipLight: false,
  // the far forest stops at two bands, so a big forest leaves the painted sky its room
  deepBands: CFG.deepBands,
  // the great cypress stands in front of everything at the left edge: no animal nor the
  // cabin hides behind it
  keepClear: [[0, 0.11]],

  after(th, mood) {
    const look = LOOKS[mood.time] || LOOKS.night;
    th.piLook = look;
    // bad weather greys the paint down rather than trading the swirls away
    const w = mood.weather, night = look.orb === 'moon';
    th.piGrey = night ? '#1a2030' : '#8a94a0';
    th.piDim = w === 'storm' ? 0.5 : w === 'rain' ? 0.42 : w === 'fog' ? 0.5 : w === 'cloudy' ? 0.3 : w === 'snow' ? 0.22 : 0;
    const dimHex = c => th.piDim ? mixHex(c, th.piGrey, th.piDim) : c;
    th.sky = look.base.map(dimHex);
    Object.assign(th, { far: dimHex(look.hills[0]), near: dimHex(look.hills[1]), haze: dimHex(look.haze), water: dimHex(look.water), hzStep: 0.1, rim: null, shadow: 0 });
    if (!th.snow) Object.assign(th, { g0: dimHex(look.ground[0]), g1: dimHex(look.ground[1]), grass: dimHex(mixHex(look.ground[0], '#3a7a8a', 0.4)) });
    th.tint = look.tint ? (th.rain ? mixHex(look.tint, '#3a4a55', 0.4) : look.tint) : (th.rain ? '#3a4a55' : null);
    th.tintAmt = (look.tintAmt || 0) + (th.rain ? 0.12 : 0);
    if (th.fog) { th.fog = dimHex(mixHex(look.base[4], '#c8d0dc', 0.5)); th.haze = th.fog; th.fogAmt = 0.14; }
    th.orb = null; th.stars = 0; th.rainbow = false;
    // a cloudy sky keeps the engine's clouds and deck drifting over the paint
    if (w !== 'cloudy') { th.clouds = null; th.deck = null; }
  },

  tree: {
    width: ({ h, pine, t }) => pine && t.stage >= 2 ? Math.max(3, Math.round(h * 0.34)) | 1 : 0,
    body: c => (c.pine && c.t.stage >= 2 ? cypress(c) : null),
    crown: c => (!c.pine ? swirlCrown(c) : false),
  },

  ridges: hillRidges,
  sky(env, g) { paintSky(env, g); },
  backdrop(env, g) { backdrop(env, g); },
  groundPixel(c, x, y) { return stroke(c, x, y); },

  /* the bright strokes brighten in slow waves winding along the swirls, the stars' rings pulse */
  fx: {
    init(st, ctx) {
      const env = ctx.env;
      if (CFG.skyMirror && env.water && !env.water.river) mirrorSky(env);
    },
    back(g, env, t) {
      const S = env.piShimmer; if (!S) return;
      // the lit strokes go into a pixel buffer of their own, laid over the sky in one
      // drawImage: a call for every pixel of every stroke was ~2000 calls a frame. A later
      // stroke covers an earlier one, as it did painted one by one (their colours are opaque)
      const b = shimBuffer(env, S);
      for (const s of S) {
        if (Math.sin(t * CFG.shimSpeed - s.ph) < CFG.shimAt) continue;
        const v = s.u32 || (s.u32 = packed(s.c));
        for (let i = 0; i < s.px.length; i += 2) {
          const x = s.px[i], y = s.px[i + 1];
          if (x >= 0 && x < b.w && y >= 0 && y < b.h) b.px[y * b.w + x] = v;
        }
      }
      b.g.putImageData(b.img, 0, 0);
      g.drawImage(b.c, 0, 0);
    },
  },

  frame(g, env, t) {
    const { W, u } = env, L = env.water;
    // the moon and the stars in the water: stacks of wavering gold strokes
    if (L && !L.river && !env.theme.frozen && env.piOrb) {
      const col = (a, k) => `rgba(244,212,80,${a * k})`, dimK = env.theme.piDim ? 0.5 : 1;
      const lights = [{ x: env.piOrb.x, w: env.piOrb.r * 1.3, a: 0.8 }].concat((env.piStars || []).filter(s => s.s >= 1.2).map(s => ({ x: s.x, w: s.r * 1.4, a: 0.55 })));
      for (const l of lights) for (let j = 1; j < L.lh; j += 2) {
        const wob = Math.round(Math.sin(t * 1.1 + j * 0.8 + l.x) * 1.5), hw = Math.round(l.w * (0.6 + j / L.lh * 0.6));
        if (Math.sin(t * 0.9 + j * 1.7 + l.x) < -0.3) continue;
        g.fillStyle = col(l.a, dimK); g.fillRect(Math.round(l.x - hw + wob + ((j * 7) % 3) - 1), L.y0 + j, Math.max(2, hw), 1);
      }
      // and long pale strokes combed across the water
      g.fillStyle = 'rgba(160,200,230,.25)';
      const R = rng(5);
      for (let k = 0; k < 18; k++) { const y = L.y0 + 1 + Math.floor(R() * (L.lh - 1)), len = Math.round((4 + R() * 6) * u), x = Math.round((R() * W + t * 1.5 * u) % (W + len)) - len; g.fillRect(x, y, len, 1); }
    }
    if (!env.piCypress || env.piCypress.width !== W) env.piCypress = buildCypress(env);
    g.drawImage(env.piCypress, 0, 0);
  },
});
})();

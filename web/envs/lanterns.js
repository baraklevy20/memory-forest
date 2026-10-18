/* Memory Forest - the lantern night environment.
 * Everything this environment is lives here: delete it and lanterns.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * A warm plum night with paper lanterns drifting up: a river of them rising from the red
 * moon bridge on the left third towards a big full moon on the right third, more scattered
 * all over the sky, and more floating on the lake, each laying a streak of light on the
 * water. A garland of chochin sags across the top left. By day unlit paper lanterns rise
 * along the same path and slip behind the sun where they meet it; rain, fog and snow grey
 * the night sky as they do any other. The bridge is drawn larger than the shared
 * moon_bridge landmark, with a third lamp on its apex (moon_bridge_lanterns, below), swapped
 * in by `prepare`.
 * Yellow stays reserved for forgetting. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rgb, rng, layer, B4 } = AF.u;
const H6 = a => a.map(hex);
const bayer = (x, y) => B4[(y & 3) * 4 + (x & 3)];

const CFG = {"riverSpread": 1.4, "river": 12, "scatter": 24, "lean": 0.45, "water": 8, "drift": 0.5, "dayShare": 0.6, "moon": {"x": 0.76, "y": 0.15, "r": 9, "minR": 6, "halo": 9}, "bridge": "moon_bridge_lanterns", "garland": {"spans": [[-0.02, 0.46, 1, -1, 13]], "every": 12}};

const ROUNDS = [
  H6(['#1a0c1e', '#3a1634', '#5a2244', '#7a3450', '#a44a5a']),
  H6(['#1a0c1e', '#321a3e', '#4e2650', '#6e3662', '#9a4e72']),
  H6(['#1a0c1e', '#3a1a2e', '#5e2a3e', '#84404c', '#b25a5e']),
];
const PINE = H6(['#140a1a', '#2a1230', '#421c40', '#5e2a4e', '#86405a']);
const SICK = [null,
  H6(['#2a2010', '#6e5418', '#c09a2c', '#e8c840', '#fae276']),
  H6(['#2a2010', '#7a5a1a', '#c09030', '#e6be48', '#f8dc76']),
  H6(['#241a0e', '#5e4418', '#9a7a2a', '#c8a23c', '#e8c860'])];
const GLOW = hex('#f58a6e'), GLOW_HI = hex('#ffb48a');

const isLit = mood => mood.time === 'night' || mood.time === 'dusk';
const wetOf = w => w === 'rain' || w === 'storm';
// the engine's pull of a night sky towards each weather (theme.js). Our own night sky replaces
// the mixed one, so the weather goes back on top, or rain would fall through a clear plum sky
const NIGHT_WEATHER = { cloudy: ['#1a2030', 0.6], rain: ['#10151c', 0.5], storm: ['#10151c', 0.65], fog: ['#3a4458', 0.55],
  snow: ['#26314a', 0.45], deep_winter: ['#1e2432', 0.65], after_rain: ['#b8bcc8', 0.18] };

/* where the top of the forest is: the sky lanterns live above it, where they can be seen */
const lineOf = env => env.lnLine != null ? env.lnLine : (env.lnLine = Math.round(AF.treeLine(env)));

/* ---------- the moon (CFG.moon): a full festival moon on the right third ----------
 * Painted into the sky, so the lake mirrors it like everything else. Lifted with the tree
 * line, so a big forest never covers it. */
const MOONS = {
  night: { face: ['#fff8e6', '#f8e8c8', '#e8d0aa', '#c8a88c'], sea: '#e2c8a6', seaD: '#cfae90', glow: '#c8786a', glow2: '#6e3458' },
  dusk: { face: ['#fff2dc', '#ffe0b8', '#f4c49a', '#d89a80'], sea: '#f0c09c', seaD: '#dca486', glow: '#e88a6e', glow2: '#94486a' },
};
const SEAS = [[-0.3, -0.14, 0.32], [0.02, -0.44, 0.18], [0.3, 0.16, 0.24]];
const CRATERS = [[0.2, 0.42, 0.11], [-0.52, 0.28, 0.08]];

function moonAt(env) {
  if (env.lnMoon !== undefined) return env.lnMoon;
  const M = CFG.moon, th = env.theme;
  if (!th.lnMoon) return (env.lnMoon = null);
  const { W, H, u } = env, line = lineOf(env), gap = 3 * u, top = 3 * u;
  const r = Math.round(Math.max(M.minR * u, Math.min(M.r * u, (line - top - gap) / 2)));
  const y = Math.round(Math.max(r + top, Math.min(H * M.y, line - r - gap)));
  return (env.lnMoon = { x: Math.round(W * M.x), y, r });
}

function paintMoon(env, g) {
  const m = moonAt(env); if (!m) return;
  const th = env.theme, P = MOONS[env.mood.time === 'dusk' ? 'dusk' : 'night'], w = env.mood.weather;
  const skyAt = y => hex(th.sky[Math.max(0, Math.min(th.sky.length - 1, Math.floor(y / env.hor * th.sky.length)))]);
  const veil = w === 'fog' ? 0.5 : w === 'cloudy' ? 0.4 : w === 'snow' ? 0.35 : 0;
  const px = (c, x, y) => { g.fillStyle = rgb(c); g.fillRect(x, y, 1, 1); };
  // the halo: warm air over the lanterns, a half-dithered inner ring and an outer one fading
  if (veil < 0.45) {
    const g1 = hex(P.glow), g2 = hex(P.glow2), R1 = 2 * env.u, R2 = CFG.moon.halo * env.u;
    for (let y = m.y - m.r - R2; y <= m.y + m.r + R2; y++) for (let x = m.x - m.r - R2; x <= m.x + m.r + R2; x++) {
      const d = Math.hypot(x + 0.5 - m.x, y + 0.5 - m.y) - m.r;
      if (d < 0 || d > R2 || y < 0) continue;
      const base = skyAt(y);
      if (d < R1) { px(mix(base, g1, (x + y) & 1 ? 0.45 : 0.25), x, y); continue; }
      const k = 1 - (d - R1) / (R2 - R1);
      if (bayer(x, y) < k * k * 12) px(mix(base, k > 0.5 ? g1 : g2, 0.25), x, y);
    }
  }
  const face = P.face.map(hex);
  for (let y = m.y - m.r; y <= m.y + m.r; y++) for (let x = m.x - m.r; x <= m.x + m.r; x++) {
    const nx = (x + 0.5 - m.x) / m.r, ny = (y + 0.5 - m.y) / m.r, q = nx * nx + ny * ny;
    if (q > 1) continue;
    const l = -(nx * 0.5 + ny * 0.7) * 0.8 - q * 0.45 + 0.15;
    const lv = (l + 0.9) * 2.1, fr = lv - Math.floor(lv), lvl = Math.floor(lv) + (lv < 2 && fr > 0.72 && bayer(x, y) < (fr - 0.72) / 0.28 * 16 ? 1 : 0);
    let c = face[Math.max(0, Math.min(3, 3 - lvl))];
    for (const [sx, sy, sr] of SEAS) {
      const s = ((nx - sx) ** 2 + (ny - sy) ** 2) / (sr * sr);
      if (s < 0.75 || (s < 1 && (x + y) & 1)) c = s < 0.25 ? hex(P.seaD) : hex(P.sea);
    }
    for (const [cx, cy, cr] of CRATERS) {
      const d = Math.hypot(nx - cx, ny - cy) / cr;
      if (d < 1 && d > 0.55) c = (nx - cx) + (ny - cy) < 0 ? hex(P.seaD) : hex(P.sea);
    }
    if (q > 0.86 && nx + ny > 0.3) c = face[3];
    if (veil) c = mix(c, skyAt(y), veil);
    if (veil > 0.3 && q > 0.7 && bayer(x, y) < (q - 0.7) / 0.3 * 16) continue;
    px(c, x, y);
  }
}

/* the moon the lanterns rise towards: our own, or the engine's orb */
function moonDisc(env) {
  const m = moonAt(env);
  if (m) return m;
  const o = env.theme.orb;
  return o && o.kind === 'moon' ? { x: env.W * o.x, y: env.H * o.y, r: o.r * env.u } : null;
}
/* the disc the lanterns hide behind: the moon, or by day the sun, so none is drawn across it */
function discOf(env) {
  const m = moonDisc(env), o = env.theme.orb;
  return m || (o ? { x: env.W * o.x, y: env.H * o.y, r: o.r * env.u } : null);
}

/* ---------- the lanterns, in the sky and on the water, placed once per forest ---------- */
function lanterns(env) {
  if (env.lanternSet) return env.lanternSet;
  const { u } = env, R = rng(((env.data.forestSeed || 3) ^ 0x1a47) >>> 0);
  const sky = [], water = [];
  const lit = env.theme.lanternNight, keep = lit ? 1 : CFG.dayShare;
  // the river: from low over the bridge side of the lake up towards the moon's corner
  for (let i = 0; i < CFG.river; i++) sky.push({ river: true, f: R(), spread: (R() - 0.5) * 2, v: 1 / (170 + R() * 60), show: R() < keep });
  // and a scattering across the rest of the sky, rising straight up; a little thicker on
  // the bridge side, where they are let go, and thinning towards the moon
  for (let i = 0; i < CFG.scatter; i++) {
    let x = R();
    for (let k = 0; k < 6 && R() > 1 - CFG.lean * x; k++) x = R();
    sky.push({ river: false, x: 0.02 + 0.96 * x, f: R(), v: (0.5 + R() * 0.4) * u, show: R() < keep });
  }
  // floating lanterns on the lake, spread across it in loose columns so they never pile up
  if (env.mood.landscape === 'lake') for (let i = 0; i < CFG.water; i++) {
    water.push({ fx: (i + 0.15 + R() * 0.7) / CFG.water, fy: R(), ph: R() * 6, v: (0.4 + R() * 0.5) * u * CFG.drift });
  }
  const river = sky.filter(l => l.river).sort((a, b) => a.f - b.f);
  river.forEach((l, i) => { l.next = river[(i + 1) % river.length]; l.wrap = i === river.length - 1 ? 1 : 0; });
  return (env.lanternSet = { sky, water });
}

/* the river runs from over the bridge to just under the moon */
function riverEnds(env) {
  if (env.lnRiver) return env.lnRiver;
  const { W, hor } = env, b = env.moonBridge, m = moonDisc(env);
  const x0 = b ? b.x + b.W / 2 - W * 0.04 : W * 0.12, x1 = m ? m.x - m.r * 1.2 : W * 0.84, y1 = m ? m.y + m.r * 0.6 : hor * 0.08;
  return (env.lnRiver = { x0, x1, y0: hor * 0.92, y1 });
}

/* where a sky lantern is at time t, or null while it is hidden */
function at(env, l, t) {
  const { W, u, hor } = env, line = lineOf(env);
  let x, y;
  if (l.river) {
    const P = riverEnds(env);
    const h = AF.LOOP ? AF.u.handover(0, t) : 0, n = l.next;
    const f = AF.LOOP ? (l.f + (n.f + l.wrap - l.f) * h) % 1 : (l.f + t * l.v) % 1;
    const spread = (AF.LOOP ? l.spread + (n.spread - l.spread) * h : l.spread) * 0.5 * CFG.riverSpread * (10 + 26 * Math.sin(Math.PI * Math.min(1, f * 1.3))) * u;
    x = P.x0 + (P.x1 - P.x0) * f + spread * 0.6; y = P.y0 + (P.y1 - P.y0) * Math.pow(f, 0.9) + spread;
  } else {
    // they rise out of the canopy, so every one of them spends its whole way in open sky
    const y0 = Math.min(hor * 0.95, line + 8 * u), span = y0;
    const k = ((l.f * span + t * AF.u.trip(l.v, span)) % span) / span;
    x = W * l.x + Math.sin(t * AF.u.cyc(0.2) + l.f * 9) * 2 * u; y = y0 - k * span;
  }
  if (y <= 2 || y >= hor) return null;
  const m = discOf(env);
  if (m && Math.hypot(x - m.x, y - m.y) < m.r + 4) return null;
  return { x: Math.round(x), y: Math.round(y) };
}

/* nearer (lower in the open sky) is larger: sized against the sky you can see */
const sizeAt = (y, env) => { const s = lineOf(env); return y < s * 0.3 ? 0 : y < s * 0.66 ? 1 : 2; };

/* one sky lantern: lit after dusk; by day a paper lantern with its candle showing warm */
function paintLantern(g, x, y, size, lit) {
  if (lit) {
    if (size === 0) { g.fillStyle = '#ffce6e'; g.fillRect(x, y, 1, 1); return; }
    if (size === 1) {
      g.fillStyle = 'rgba(255,170,90,.3)'; g.fillRect(x - 1, y, 4, 2); g.fillRect(x, y - 1, 2, 4);
      g.fillStyle = '#ffce6e'; g.fillRect(x, y, 2, 2); g.fillStyle = '#e8703a'; g.fillRect(x, y + 1, 2, 1);
      return;
    }
    g.fillStyle = 'rgba(255,170,90,.18)'; g.fillRect(x - 2, y, 7, 4); g.fillRect(x, y - 2, 3, 8);
    g.fillStyle = 'rgba(255,170,90,.34)'; g.fillRect(x - 1, y + 1, 5, 2); g.fillRect(x + 1, y - 1, 1, 6);
    g.fillStyle = '#b8432c'; g.fillRect(x, y, 3, 1);
    g.fillStyle = '#ffd67a'; g.fillRect(x, y + 1, 3, 2); g.fillStyle = '#fff0b8'; g.fillRect(x + 1, y + 1, 1, 1);
    g.fillStyle = '#ec783a'; g.fillRect(x, y + 3, 3, 1);
    return;
  }
  if (size === 0) { g.fillStyle = '#fff2e0'; g.fillRect(x, y, 1, 1); return; }
  if (size === 1) { g.fillStyle = '#fff6e8'; g.fillRect(x, y, 2, 1); g.fillStyle = '#f0966a'; g.fillRect(x, y + 1, 2, 1); return; }
  g.fillStyle = '#a8382a'; g.fillRect(x, y, 3, 1);
  g.fillStyle = '#fff6e6'; g.fillRect(x, y + 1, 3, 1);
  g.fillStyle = '#ffd2a0'; g.fillRect(x, y + 2, 3, 1); g.fillStyle = '#ffe6bc'; g.fillRect(x + 1, y + 2, 1, 1);
  g.fillStyle = '#e06a3a'; g.fillRect(x, y + 3, 3, 1);
}

/* a round chochin: red paper, black caps, lit after dusk with a dithered glow round it */
function chochin(g, x, y, lit, big) {
  const ROWS = big ? [3, 5, 5, 5, 3] : [3, 3, 3];
  const n = ROWS.length;
  if (lit) {
    const rx = big ? 6 : 4, ry = big ? 7 : 5, cy = (n + 1) / 2;
    for (let dy = -ry; dy <= ry; dy++) for (let dx = -rx; dx <= rx; dx++) {
      const q = (dx / rx) ** 2 + (dy / ry) ** 2; if (q > 1 || (q > 0.45 && (x + dx + y + dy) & 1)) continue;
      g.fillStyle = q > 0.45 ? 'rgba(255,150,110,.13)' : 'rgba(255,160,110,.2)'; g.fillRect(x + dx, Math.round(y + cy + dy), 1, 1);
    }
  }
  g.fillStyle = '#1a0c10'; g.fillRect(x - 1, y, 3, 1); g.fillRect(x - 1, y + n + 1, 3, 1);
  ROWS.forEach((w, i) => {
    const hw = w >> 1;
    g.fillStyle = lit ? '#f0604a' : '#c8402e'; g.fillRect(x - hw, y + 1 + i, w, 1);
    g.fillStyle = lit ? (i >= 1 && i <= n - 3 || n === 3 && i === 1 ? '#ffd0a0' : '#ff9a78') : '#e25a44';
    g.fillRect(x - hw + (w > 2 ? 1 : 0), y + 1 + i, Math.max(1, w - 2), 1);
  });
  if (big) { g.fillStyle = lit ? '#b83a2c' : '#a03024'; g.fillRect(x - 2, y + 3, 5, 1); }
}

/* ---------- the garland (CFG.garland): a sagging festival string across the top ---------- */
function garland(env) {
  if (env.lnGarland) return env.lnGarland;
  const { W, u } = env, G = CFG.garland, out = { cord: [], lamps: [] };
  for (const s of G.spans) {
    const x0 = W * s[0], x1 = W * s[1], ya = s[2] * u, yb = s[3] * u, sag = s[4] * u;
    const y = x => { const q = (x - x0) / (x1 - x0); return ya + (yb - ya) * q + sag * 4 * q * (1 - q); };
    for (let x = Math.max(0, Math.round(x0)); x <= Math.min(W - 1, Math.round(x1)); x++) out.cord.push([x, Math.round(y(x))]);
    const n = Math.max(2, Math.round((x1 - x0) / (G.every * u)));
    for (let i = 1; i < n; i++) { const x = Math.round(x0 + (x1 - x0) * i / n); if (x > 1 && x < W - 2) out.lamps.push({ x, y: Math.round(y(x)) + 1, big: false }); }
  }
  return (env.lnGarland = out);
}

/* nothing on the garland moves: it is painted once, cord and lamps, and laid over each frame
 * in one go (drawn straight onto the forest, its dotted glows took ~700 calls a frame) */
function garlandImg(env, lit) {
  const c = env.lnGarlandImg;
  if (c && c.lit === lit) return c.cv;
  const G = garland(env), h = Math.max(0, ...G.cord.map(p => p[1]), ...G.lamps.map(l => l.y)) + 16;
  const [cv, g] = layer(env.W, h);
  g.fillStyle = lit ? '#1a0c14' : '#3a2428';
  for (const [x, y] of G.cord) g.fillRect(x, y, 1, 1);
  for (const l of G.lamps) chochin(g, l.x, l.y, lit, l.big);
  env.lnGarlandImg = { lit, cv };
  return cv;
}

AF.env('lanterns', {

  look: (mood, night) => night ? AF.TIMES.plum_night : null,

  prepare(env) {
    // the lanterns' own moon bridge (below): the same red arch, larger (stood in through
    // env.landmarkKey, see AF.markOf; the scene's data keeps its own landmark)
    if (CFG.bridge && env.mood.landmark === 'moon_bridge') env.landmarkKey = CFG.bridge;
  },

  after(th, mood) {
    const night = isLit(mood), w = mood.weather;
    // (by day a richer sky: a deeper blue at the top, warmer low down, so the crowns and the
    // lantern strings have more to stand against)
    if (mood.time === 'day' && (!w || w === 'clear')) th.sky = ['#5c92c8', '#6f9fce', '#9cc6e6', '#b5d4ea', '#d8e0dd', '#e7e9dc'];
    if (night) {
      Object.assign(th, { g0: '#2e1a30', g1: '#1c1020', grass: '#44263e', far: '#2e1c3c', near: '#241430', haze: '#4a2a4c',
        tint: '#1d1530', tintAmt: 0.12, water: '#2e1f40', rim: null });
      th.sky = ['#0a081e', '#170f2f', '#2e1846', '#44204e', '#57305b', '#6d395e'];  // (a deeper top, a faint glow low down: a richer sky to frame the lanterns)
      const wx = NIGHT_WEATHER[w];
      if (wx) {
        const grey = (c, k) => AF.u.mixHex(c, wx[0], k);
        th.sky = th.sky.map(c => grey(c, wx[1]));
        if (w !== 'after_rain') { th.far = grey(th.far, 0.4); th.near = grey(th.near, 0.4); th.haze = grey(th.haze, 0.5); }
      }
      // a full festival moon on the right third, painted by this environment; the engine's
      // orb only keeps the glitter on the water under it (gone where the weather hides it)
      const hidden = wetOf(w) || w === 'deep_winter' || !th.orb;
      th.lnMoon = !hidden;
      th.orb = hidden ? null : { kind: 'moon', x: CFG.moon.x, y: CFG.moon.y, r: 0.01, c: '#ffffff', halo: 0, full: true };
    }
    th.lanternNight = night;
  },

  calendar: ['#7a3450', '#ff9a6a'],  // the study calendar from the night's plum to the lanterns' glow
  pals: { rounds: ROUNDS, pine: PINE, bark: { l: hex('#5a3a44'), m: hex('#3e2432'), d: hex('#22121e') },
    leaf: hex('#b25a5e'), leafL: hex('#f58a6e'), stem: hex('#6e3662') },
  leafColors: ['#e8c840', '#c09a2c'],

  tree: {
    sickPalette: c => SICK[c.t.health],
    // the lanterns overhead catch the top of every crown
    pixel(col, { x, y, tn, pal, c }) {
      if (tn < 2 || c.inside(x, y - 1) || pal === SICK[c.t.health]) return col;
      return tn >= 3 ? (c.inside(x, y - 2) ? GLOW : GLOW_HI) : mix(col, GLOW, 0.5);
    },
  },

  // the full moon goes into the sky itself, so the lake reflects it
  sky(env, sg) { paintMoon(env, sg); },

  fx: {
    init(st, { env }) {
      const m = moonAt(env);
      if (m) st.stars = st.stars.filter(s => Math.hypot(s.x - m.x, s.y - m.y) > m.r + 4 * env.u);
    },
    /* the sky lanterns, drifting slowly upward behind the trees */
    back(g, env, t) {
      const lit = env.theme.lanternNight;
      if (!lit && !CFG.dayShare) return;
      for (const l of lanterns(env).sky) {
        if (!l.show) continue;
        const p = at(env, l, t);
        if (p) paintLantern(g, p.x, p.y, sizeAt(p.y, env), lit);
      }
    },
    /* the framing over everything: the garland */
    front(g, env, t, st, where) {
      if (where !== 'sky') return;
      if (CFG.garland) g.drawImage(garlandImg(env, env.theme.lanternNight), 0, 0);
    },
  },

  /* on the lake: each sky lantern's streak of light, and the floating lanterns */
  frame(g, env, t) {
    const L = env.water;
    if (!L) return;
    const lit = env.theme.lanternNight;
    const { W, H, hor } = env, s = lanterns(env), still = env.theme.frozen;
    if (lit) for (const l of s.sky) {
      const p = at(env, l, t);
      if (!p || sizeAt(p.y, env) === 0) continue;
      const j = Math.round((hor - p.y) * 0.45);
      if (j >= L.lh - 3) continue;
      g.fillStyle = 'rgba(255,190,110,.5)'; g.fillRect(p.x + 1, L.y0 + j, 1, 2);
      g.fillStyle = 'rgba(255,150,90,.22)'; g.fillRect(p.x, L.y0 + j + 2, 3, 1);
    }
    if (still && !lit) return;
    const bot = Math.min(H, L.y0 + L.lh), span = W + 10;
    for (const w of s.water) {
      const drift = still ? 0 : t * AF.u.trip(w.v, span);
      const x = Math.round(((W * w.fx + drift) % span + span) % span - 5);
      const y = Math.round(L.y0 + 3 + w.fy * (bot - L.y0 - 8));
      const bob = Math.round(Math.sin(t * AF.u.cyc(0.8) + w.ph) * 0.6);
      if (lit) { g.fillStyle = 'rgba(255,170,90,.28)'; g.fillRect(x, y + 3, 3, 3); g.fillRect(x + 1, y + 6, 1, 2); }
      else { g.fillStyle = 'rgba(200,70,56,.22)'; g.fillRect(x, y + 3, 3, 2); }
      g.fillStyle = lit ? '#6a2a22' : '#5a2a22'; g.fillRect(x - 1, y + 2 + bob, 5, 1);
      g.fillStyle = lit ? '#ffd67a' : '#fff0dc'; g.fillRect(x, y + bob, 3, 2);
      if (!lit) { g.fillStyle = '#ffc890'; g.fillRect(x + 1, y + 1 + bob, 1, 1); }
      g.fillStyle = '#b8432c'; g.fillRect(x, y - 1 + bob, 3, 1);
    }
  },
});
})();

/* The lanterns' moon bridge: the shared red moon bridge (landmarks/moon_bridge.js), about
 * 1.4x the size, with a third lamp on its apex. */
(() => {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, layer } = AF.u;

const B = {"scale": 1.4, "apex": true, "from": 0.15, "span": 0.08};
const LACQUER = hex('#d8402e'), LACQUER_D = hex('#8a2420'), RAIL = hex('#2a1a18'), LAMP = hex('#ffd27a');
const onWater = env => env.mood.landscape === 'lake';
const radius = u => Math.max(12, Math.round(19 * B.scale * u));

function build(env) {
  const th = env.theme, u = env.u, R0 = radius(u), thick = Math.max(2, Math.round(2.5 * B.scale * u));
  const rail = Math.max(2, Math.round(3 * B.scale * u)), top = 4, W = R0 * 2 + 3, H = R0 + rail + top, cx = W / 2, cy = H;
  const [cv, g] = layer(W, H), img = g.createImageData(W, H), d = img.data;
  const night = th.tint ? hex(th.tint) : null, dim = c => (night ? mix(c, night, th.tintAmt * 0.45) : c);
  const lit = env.mood.time === 'night' || env.mood.time === 'dusk';
  const put = (x, y, c) => { if (x < 0 || y < 0 || x >= W || y >= H) return; const i = (y * W + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255; };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const r = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
    if (r <= R0 && r > R0 - thick) put(x, y, dim(r > R0 - 1 ? mix(LACQUER, [255, 235, 210], 0.16) : r < R0 - thick + 1 ? LACQUER_D : LACQUER));
  }
  // posts along the deck and the handrail joining their tops
  for (let a = 0.12; a < Math.PI - 0.1; a += 0.22 / Math.sqrt(B.scale)) {
    const x = Math.round(cx - Math.cos(a) * R0), y0 = Math.round(cy - Math.sin(a) * R0);
    for (let k = 1; k <= rail; k++) put(x, y0 - k, dim(RAIL));
  }
  for (let a = 0.08; a < Math.PI - 0.06; a += 0.015) put(Math.round(cx - Math.cos(a) * (R0 + rail)), Math.round(cy - Math.sin(a) * (R0 + rail)), dim(LACQUER));
  const angles = B.apex ? [0.2, Math.PI / 2, Math.PI - 0.2] : [0.2, Math.PI - 0.2];
  const lamps = angles.map(a => ({ x: Math.round(cx - Math.cos(a) * R0), y: Math.round(cy - Math.sin(a) * R0) - rail - 2 }));
  for (const l of lamps) for (let y = 0; y < 3; y++) for (let x = -1; x <= 1; x++) put(l.x + x, l.y + y, y === 0 ? dim(RAIL) : lit ? LAMP : dim(hex('#e8d8b0')));
  g.putImageData(img, 0, 0);
  const [rv, rg] = layer(W, H), wc = hex(th.water || '#3a4a6a');
  rg.drawImage(cv, 0, 0);
  const ri = rg.getImageData(0, 0, W, H), rd = ri.data;
  for (let i = 0; i < rd.length; i += 4) if (rd[i + 3]) { const c = mix([rd[i], rd[i + 1], rd[i + 2]], wc, 0.35); rd[i] = c[0]; rd[i + 1] = c[1]; rd[i + 2] = c[2]; }
  rg.putImageData(ri, 0, 0);
  return { img: cv, refl: rv, W, H, lamps, lit };
}

function glow(g, x, y, u, t) {
  const a = 0.2 + 0.05 * Math.sin(t * AF.u.cyc(2) + x), r = Math.max(2, Math.round(2 * u));
  g.fillStyle = `rgba(255,210,122,${a})`; g.fillRect(x - r, y - 1, 2 * r + 1, r + 3);
  g.fillStyle = `rgba(255,210,122,${a * 0.6})`; g.fillRect(x - r - 1, y, 2 * r + 3, r + 1); g.fillRect(x - 1, y - r, 3, 2 * r + 3);
}

AF.landmark('moon_bridge_lanterns', {
  slot: 'land',
  // still on the left of the lake, its middle near the left third
  place: (env, R) => Math.round(env.W * (onWater(env) ? B.from + R() * B.span : 0.12 + R() * 0.22)),
  draw(env, lg, x) {
    const b = env.moonBridge = Object.assign(build(env), { x });
    if (onWater(env)) return;
    const y0 = Math.round(env.hor - 8 * env.u);
    AF.drawMound(env, lg, x + (b.W >> 1), Math.round(b.W * 0.7), y0);
    lg.drawImage(b.img, x, y0 - b.H + 1);
    b.fixed = { x, y: y0 - b.H + 1 };
  },
  frame(g, env, t) {
    const b = env.moonBridge; if (!b) return;
    const u = env.u, L = env.water;
    if (b.fixed) {
      if (b.lit) for (const l of b.lamps) glow(g, b.fixed.x + l.x, b.fixed.y + l.y, u, t);
      return;
    }
    if (!L) return;
    const top = L.y0 - b.H, still = env.theme.frozen;
    for (let j = 0; j < b.H && j < L.lh; j++) {
      const off = still ? 0 : Math.round(Math.sin(t * AF.u.cyc(0.9) + j * 0.7) * (j < 2 ? 0 : 1));
      g.globalAlpha = 0.75 - 0.4 * j / b.H;
      g.drawImage(b.refl, 0, b.H - 1 - j, b.W, 1, b.x + off, L.y0 + j, b.W, 1);
    }
    g.globalAlpha = 1;
    g.drawImage(b.img, b.x, top);
    if (b.lit) for (const l of b.lamps) {
      glow(g, b.x + l.x, top + l.y, u, t);
      g.fillStyle = 'rgba(255,210,122,.35)'; g.fillRect(b.x + l.x, L.y0 + (b.H - l.y) - 2, 1, 2);
    }
  },
});
})();

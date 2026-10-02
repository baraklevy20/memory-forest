/* Memory Forest - the aurora environment.
 * Everything this environment is lives here: delete it and aurora.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * The far north in deep winter. Curtains of green light hang across the whole sky, over
 * a jagged snowy range lit by the moon and a dark ridge fringed with spruce. The forest is
 * all winter: heavy snow-laden crowns ("snow ghosts") and dark spruces with snow on every
 * tier. On a lake, the water holds the aurora's reflection as it moves. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, hashStr, B4, rng } = AF.u;
const H6 = a => a.map(hex);

// snow ghosts: crowns buried in snow, dark branches showing only in the deepest shade
const GHOST = H6(['#141d2c', '#3e5272', '#627a9c', '#8ca2c0', '#bccce0']);
const SPRUCE = H6(['#07161a', '#143430', '#1f4e44', '#2f6e58', '#58b48a']);
const NEEDLES = hex('#1d3a34');
const SNOW = hex('#dce8f4'), SNOW_SHADE = hex('#9fb4cc');  // moonlit snow lying on the branches
// yellowing, kept yellow-ochre in every tone: the forest's own goes olive and brown in
// the dark tones, which disappears against a night palette
const SICK = [null, H6(['#2a2410', '#8a7a24', '#b09a30', '#d4bc48', '#f0dc78']), H6(['#2e1a0c', '#9a6420', '#c4822e', '#e0a044', '#f4c870']), H6(['#2a1e10', '#7a5a24', '#a07a34', '#c49a48', '#e0c070'])];
const BARK = { l: hex('#4a4652'), m: hex('#2e2a36'), d: hex('#1a1822') };
const dark = mood => mood.time === 'night' || mood.time === 'dusk';

/* a boreal spruce: narrow, many short drooping tiers, a spike at the top */
function spruce(c) {
  const { t, h, W, w, cx, base, tone, put, pick, R, bark } = c;
  const top = 1, foot = base - Math.max(1, Math.round(h * 0.08)), tiers = Math.max(3, Math.round(h / 3.2));
  for (let y = foot; y <= base; y++) put(cx, y, bark.d);
  for (let y = top; y <= foot; y++) {
    const p = (y - top + 0.5) / (foot - top + 1), tp = (p * tiers) % 1;
    const hw = (w / 2) * (0.1 + 0.9 * Math.pow(p, 0.85)) * (0.45 + 0.55 * tp) + (t.seed % 3 === 0 && p > 0.5 ? 0.4 : 0);
    for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - (cx + 0.5); if (Math.abs(dx) > hw) continue;
      // lit from above: the top of each tier catches the light, the underside is in shadow
      tone[y * W + x] = pick(0.55 - tp * 1.1 - dx / Math.max(1, hw) * 0.25 + (R() - 0.5) * 0.2);
    }
  }
  return { top, ch: foot - top };
}

/* The mountains: a jagged range with snow down its upper slopes, the faces towards the
 * moon lit and the rest in shade, and in front a low dark ridge fringed with spruce.
 * As the far treeline climbs, the range grows with it, so the highest peak always stands
 * RANGE_CLEAR above the trees (up to RANGE_TOP from the top of the sky); the peaks
 * spread a little less than they rise, so a big range stays as steep as a small one. */
const MAIN_PEAK = 46, RANGE_CLEAR = 30, RANGE_TOP = 0.1, RANGE_SPREAD = 0.7;
function range(env, g) {
  const { W, H, hor, u } = env, R = rng(52), night = dark(env.mood);
  const S = Math.min((hor - H * RANGE_TOP) / (MAIN_PEAK * u), Math.max(1, (hor - AF.treeLine(env) + RANGE_CLEAR * u) / (MAIN_PEAK * u)));
  const SW = 1 + (S - 1) * RANGE_SPREAD;
  const rock = night ? ['#3a4e6c', '#1e2c44'] : ['#7a8ca4', '#56687e'];
  const snow = night ? ['#d8e8ee', '#8ea2c0'] : ['#ffffff', '#c4d2e4'];
  // a handful of peaks of very different sizes, one of them clearly the highest, each
  // with its own steep and gentle side
  const peaks = [], n = Math.max(4, Math.round(W / (55 * u)));
  for (let i = 0; i < n; i++) {
    const main = i === Math.floor(n * 0.45);
    peaks.push({ x: (i + 0.2 + R() * 0.6) / n * W, h: (main ? MAIN_PEAK : 12 + R() * 26) * u * S,
                 wl: (main ? 60 : 26 + R() * 40) * u * SW, wr: (main ? 70 : 26 + R() * 40) * u * SW, bend: 0.75 + R() * 0.6 });
  }
  const r1 = R() * 6, r2 = R() * 6;
  const rough = x => (Math.sin(x * 0.37 + r1) * 1.2 + Math.sin(x * 0.11 + r2) * 1.6) * u;  // a broken ridgeline
  const height = x => {
    let best = 0;
    for (const p of peaks) {
      const q = (x - p.x) / (x < p.x ? p.wl : p.wr);
      if (Math.abs(q) < 1) best = Math.max(best, p.h * Math.pow(1 - Math.abs(q), p.bend));
    }
    return best > 0 ? Math.max(0, best + rough(x) * Math.min(1, best / (10 * u))) : 0;
  };
  const hs = Array.from({ length: W + 2 }, (_, i) => height(i - 1));
  for (let x = 0; x < W; x++) {
    const hgt = hs[x + 1], top = Math.round(hor - hgt);
    const lit = hs[x + 2] < hs[x];  // this face slopes down towards the moon on the right
    const snowDepth = hgt > 14 * u ? hgt * (0.35 + 0.15 * Math.sin(x * 0.3)) : 0;
    for (let y = top; y < hor; y++) {
      const inSnow = y - top < snowDepth || (y - top < snowDepth + 2 && B4[(y % 4) * 4 + x % 4] < 8);
      g.fillStyle = inSnow ? snow[lit ? 0 : 1] : rock[lit ? 0 : 1];
      g.fillRect(x, y, 1, 1);
    }
  }
  // the near ridge, with a treeline of little spruces along it
  const ridgeC = night ? '#0e1826' : '#2c3c3a', p1 = R() * 6, p2 = R() * 6;
  const ridge = x => Math.round(hor - (4 + 3 * Math.sin(x / W * 5 + p1) + 1.5 * Math.sin(x / W * 13 + p2)) * u);
  g.fillStyle = ridgeC;
  for (let x = 0; x < W; x++) g.fillRect(x, ridge(x), 1, hor - ridge(x) + 1);
  for (let x = Math.round(R() * 3); x < W; x += Math.max(2, Math.round((2 + R() * 3) * u))) {
    const th = Math.round((2 + R() * 4) * u), y0 = ridge(x);
    for (let k = 0; k < th; k++) { const hw = Math.floor(k * 0.4); g.fillRect(x - hw, y0 - th + k, hw * 2 + 1, 1); }
  }
}

/* One column of a curtain at a moment: where its hem hangs, how tall it is, and which
 * of its four brightness steps it is at. The sky and its reflection both use this. */
function column(a, x, ts, u) {
  const xs = x / u;
  // the hem folds back on itself: two waves at different speeds
  const y0 = Math.round(a.yb + Math.sin(xs * 0.018 + ts * a.sp * 3 + a.ph) * a.amp * u + Math.sin(xs * 0.047 - ts * a.sp * 5) * 3 * u);
  // thin rays, drifting sideways along the curtain, over brighter and dimmer stretches
  const ray = 0.45 + 0.3 * Math.sin(xs * 0.7 + ts * 0.9 + Math.sin(xs * 0.05 + ts * 0.3) * 3) + 0.25 * Math.sin(xs * 1.9 - ts * 0.6);
  const fade = 0.5 + 0.5 * Math.sin(xs * 0.011 + a.ph + ts * 0.15);
  const b = Math.max(0, Math.min(3, Math.round(ray * (0.65 + fade * 0.6) * 3)));
  const hh = Math.round(a.hpx * (0.6 + 0.4 * Math.sin(xs * 0.021 + ts * 0.4 + a.ph)));
  return { y0, hh, col: a.cols[b] };
}


AF.env('aurora', {
  night: true,  // with the real hour on, it keeps to the night

  /* a cold, dark night over snow */
  theme(th, mood, night) {
    Object.assign(th, night || mood.time === 'dusk'
      ? { sky: ['#01050b', '#030d17', '#05141f', '#071a26', '#081d2a', '#0a202e'],
          g0: '#6e8cae', g1: '#46628a', grass: '#a8c0d8', haze: '#22384c', hzStep: 0.09, tint: '#0a1a2a', tintAmt: 0.08, water: '#0e1e30' }
      : { g0: '#e4ecf4', g1: '#c4d2e2', grass: '#f4f8fc' });
    if (th.clouds) th.clouds.n = 0;  // nothing drifting across the lights
  },
  pals: { round: GHOST, pine: SPRUCE, bark: BARK, leaf: hex('#23604c'), leafL: hex('#7af0b4'), stem: hex('#4a4652') },

  tree: {
    width: ({ h, pine, t, ancient }) => t.stage < 2 ? 0 : pine ? Math.max(3, Math.round(h * (ancient ? 0.48 : 0.42))) | 1 : 0,
    body(c) { return c.pine && c.t.stage >= 2 ? spruce(c) : null; },
    sickPalette: c => SICK[c.t.health],
    pixel(col, { x, y, tn, pal, c }) {
      if (pal !== GHOST && pal !== SPRUCE) return col;  // yellowing shows as it is
      if (pal === GHOST) {
        // a snow ghost: dark needles only peek out of the shaded side
        if (tn >= 1 && tn <= 2 && hashStr(x + ',' + y + ',' + c.t.seed) % 4 === 0) return NEEDLES;
        return col;
      }
      // spruce: snow lies on every upper edge, the top of each tier
      if (tn >= 1 && !c.inside(x, y - 1)) return (x + y) % 3 ? SNOW : SNOW_SHADE;
      if (tn >= 1 && !c.inside(x, y - 2) && (x + y) % 2) return SNOW_SHADE;
      return col;
    },
  },

  /* the range and the treeline, in place of the plain hills */
  backdrop(env, g) { range(env, g); },

  /* clean snow, a few ice glints, and the lights' green glow lying on the far snow */
  ground(env, g) {
    const th = env.theme, { W, H, hor } = env, R = rng(41);
    for (let i = 0; i < W * (H - hor) / 700; i++) {
      g.fillStyle = R() < 0.3 ? '#9ff0d0' : '#ffffff';
      g.fillRect(Math.round(R() * W), Math.round(hor + 2 + R() * (H - hor - 2)), 1, 1);
    }
    if (!th.aurora || !dark(env.mood)) return;
    const depth = Math.round((H - hor) * 0.5);
    g.fillStyle = 'rgba(110,240,170,.2)';
    for (let y = hor; y < hor + depth; y++) {
      const k = 1 - (y - hor) / depth;
      for (let x = 0; x < W; x++) if (B4[(y % 4) * 4 + x % 4] < k * 12) g.fillRect(x, y, 1, 1);
    }
  },

  /* curtains of light hanging from the top of the sky: a bright lower hem, folding and
   * rippling slowly, green fading upward into violet. A second, fainter one behind. */
  fx: {
    init(st, { env, th, H, u }) {
      if (!th.aurora) return;  // bad weather can rule it out
      st.aur = [
        { y: 0.11, amp: 5, hh: 20, sp: -0.13, ph: 2.1, hem: '200,160,255', body: '140,110,240', top: '120,80,200', a: 0.55 },
        { y: 0.185, amp: 5, hh: 32, sp: 0.18, ph: 0, hem: '190,255,215', body: '70,230,150', top: '170,90,220', a: 1 },
      ];
      for (const a of st.aur) {
        // four brightness steps, each a fixed set of colours: hem, lower, middle and top of the curtain
        a.cols = [0, 1, 2, 3].map(s => [`rgba(${a.hem},${a.a * (0.4 + s * 0.18)})`, `rgba(${a.body},${a.a * (0.14 + s * 0.12)})`,
          `rgba(${a.body},${a.a * (0.07 + s * 0.07)})`, `rgba(${a.top},${a.a * (0.05 + s * 0.05)})`]);
        a.yb = Math.round(H * a.y); a.hpx = a.hh * u;
      }
      env.curtains = st.aur;  // the water's reflection draws them too
    },
    back(g, env, t, st) {
      if (!st.aur) return;
      const { W, u } = env, ts = t * 0.2, hem = Math.max(1, Math.round(u * 1.5));
      // each curtain's columns, kept for the frame: the water's reflection draws the same ones
      const cols = st.aur.map(a => { const out = []; for (let x = 0; x < W; x++) out.push(column(a, x, ts, u)); return out; });
      env.curtainCols = { t, cols };
      st.aur.forEach((a, i) => { for (let x = 0; x < W; x++) {
        const { y0, hh, col } = cols[i][x], s1 = Math.round(hh * 0.3), s2 = Math.round(hh * 0.62);
        g.fillStyle = col[0]; g.fillRect(x, y0 - hem, 1, hem);
        g.fillStyle = col[1]; g.fillRect(x, y0 - s1, 1, s1 - hem);
        g.fillStyle = col[2]; g.fillRect(x, y0 - s2, 1, s2 - s1);
        g.fillStyle = col[3]; g.fillRect(x, y0 - hh, 1, hh - s2);
      } });
    },
  },

  /* the aurora in the lake: each column of the curtain mirrored upside down, a little
   * dimmer, rippling with the water */
  frame(g, env, t) {
    const L = env.water;
    if (!env.curtains || !L || env.theme.frozen) return;
    // the whole sky folds into the water, the horizon at the shore and the top of the
    // sky at the near edge, so the curtains land in view
    const { W, u, hor } = env, ts = t * 0.2, end = L.y0 + L.lh;
    const row = y => L.y0 + Math.round((hor - y) * (L.lh - 2) / hor);
    const kept = env.curtainCols && env.curtainCols.t === t ? env.curtainCols.cols : null;
    g.save(); g.globalAlpha = 0.55;
    env.curtains.forEach((a, i) => { for (let x = 0; x < W; x++) {
      const { y0, hh, col } = kept ? kept[i][x] : column(a, x, ts, u), wob = Math.round(Math.sin(t * 0.9 + x * 0.3));
      const spans = [[y0 - 1, y0, col[0]], [y0 - Math.round(hh * 0.3), y0 - 1, col[1]], [y0 - Math.round(hh * 0.62), y0 - Math.round(hh * 0.3), col[2]]];
      for (const [ya, yb, c] of spans) {
        const r0 = Math.max(L.y0, row(yb)), r1 = Math.min(end, row(ya) + 1);
        if (r1 <= r0) continue;
        g.fillStyle = c; g.fillRect(x + wob, r0, 1, r1 - r0);
      }
    } });
    g.restore();
  },
});
})();

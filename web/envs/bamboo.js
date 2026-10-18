/* Memory Forest - the bamboo grove environment.
 * Everything this environment is lives here: delete it and bamboo.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * Tall jointed canes in soft jade rain, stone lanterns lit at the foot of the grove, and
 * on the water a slow procession of floating paper lanterns, their light running down
 * into the river - the one warm thing in a green, wet afternoon. Every clump has its own
 * character (a lone stem to a dense stand, thin or thick canes, a lean, more or fewer
 * leaves, fresh, pale old or dark culms, three leaf greens), the far hills are grown over
 * with misty bamboo, and the night is a lighter green-blue so the grove still reads. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, mixHex, px, ellipseFill, rng, layer, hashStr, rgb } = AF.u;
const H6 = a => a.map(hex);

// fresh jade, a deeper green and a cool sage for the leaves; a blue-green for the second kind.
// Tones run outline, shade, mid, lit, highlight; the canes use them too, so they yellow as well.
const JADE = H6(['#163424', '#2a6040', '#3f8a4e', '#6cb45c', '#a8d87a']);
const DEEP = H6(['#0e2419', '#1a4228', '#286236', '#468a44', '#7cb262']);
const SAGE = H6(['#182e28', '#335646', '#517a64', '#7aa286', '#b0cca8']);
const TEAL = H6(['#10302c', '#1f5448', '#2e7a62', '#4ea27a', '#8ccc98']);
const LAMP = '#ffcf7a', LAMP_D = '#e0763a';

/* ---------- the canes ----------
 * Each clump has a character of its own, from its seed, so it keeps it as it grows: how many
 * canes (a lone stem to a dense stand), how thick, how far the clump fans out, how leafy, and
 * whether its culms are young and fresh, old and pale, or dark. */
function character(t, h) {
  const S = rng(hashStr('bamboo-clump|' + t.seed));
  const form = S(), thickR = S(), lean = (S() - 0.5) * 0.36, splay = 0.02 + S() * 0.08, leafy = 0.5 + S() * 0.45,
    leafLen = 0.7 + S() * 0.7, shadeR = S(), spread = S(), low = 0.35 + S() * 0.25, jit = S(), tall = 0.82 + S() * 0.18;
  let n = h < 10 ? 1 : h < 18 ? 2 : h < 30 ? 3 : 4;
  if (form < 0.2) n = Math.max(1, n - 2);
  else if (form > 0.72 && h >= 10) n += h >= 22 ? 2 : 1;
  const thick = h >= 28 && thickR < 0.28 ? 3 : h >= 22 ? (thickR > 0.88 ? 1 : 2) : h >= 15 && thickR < 0.22 ? 2 : 1;
  const gap = thick + 1 + Math.round(spread * 2.4);
  const shade = shadeR < 0.2 ? 2 : shadeR < 0.38 ? 1 : 0;  // 0 fresh, 1 old and pale, 2 dark
  const reach = Math.round(2 + (thick + 2) * leafLen) + 1;
  const tilt = Math.ceil((Math.abs(lean) + splay * (n - 1) / 2) * h);
  const w = (n - 1) * gap + thick + tilt * 2 + reach * 2;
  return { n, thick, gap, lean, splay, leafy, leafLen, shade, low, jit, tall, w: Math.max(7, w) | 1 };
}

function clump(c) {
  const { h, W, H, cx, tone, pick, R, hole, t } = c;
  const ch = character(t, h);
  const cane = c.cane = new Uint8Array(W * H), base = H - 1;
  c.caneShade = ch.shade;
  const leaf = (x, y, dir, len) => {
    for (let e = 1; e <= len; e++) {
      const xx = x + dir * e, yy = y + (e > 1 ? 1 : 0) + (e > 3 ? 1 : 0) + (e > 6 ? 1 : 0);
      if (xx < 0 || xx >= W || yy < 0 || yy >= H || (hole && R() < hole)) continue;
      if (!cane[yy * W + xx]) tone[yy * W + xx] = pick(dir < 0 ? 0.55 - e * 0.12 : -0.05 - e * 0.1);
    }
  };
  const { n, thick, gap } = ch, mid = (n - 1) / 2, tallest = Math.round(ch.jit * (n - 1));
  const H2 = rng(hashStr('bamboo-canes|' + t.seed));
  let top = H;
  for (let k = 0; k < n; k++) {
    const hk = H2(), jk = H2(), ok = H2();
    const x0 = cx - Math.floor(thick / 2) + Math.round((k - mid) * gap + (jk - 0.5) * 0.8);
    const hh = Math.min(H - 2, Math.round(h * ch.tall * (k === tallest ? 1 : 0.48 + hk * 0.44)));
    const slope = ch.lean + (k - mid) * ch.splay;      // the clump fans out a little from its foot
    const joint = Math.max(3, Math.round(h / 7) + (ok < 0.5 ? 0 : 1)), off = Math.floor(ok * joint);
    let tx = x0;
    for (let s = 0; s < hh; s++) {
      const y = base - s, f = s / Math.max(1, hh);
      const x = x0 + Math.round(slope * s * (0.6 + 0.4 * f));  // straight at the foot, bowing near the top
      const node = (s + off) % joint === 0 && s > 1;
      for (let q = 0; q < thick; q++) {
        if (x + q < 0 || x + q >= W) continue;
        const i = y * W + x + q;
        tone[i] = 2; cane[i] = node ? 3 : q === 0 ? 1 : q === thick - 1 && thick > 2 ? 4 : 2;
      }
      // leaves from the upper joints, longer higher up
      if (node && f > ch.low) {
        const len = 2 + Math.round(f * (thick + 2) * ch.leafLen * (0.6 + R() * 0.5));
        if (R() < ch.leafy) leaf(x, y, -1, len);
        if (R() < ch.leafy) leaf(x + thick - 1, y, 1, len);
      }
      top = Math.min(top, y); tx = x;
    }
    // the tip: a small drooping fan
    const tipx = tx + (thick >> 1), ty = base - hh;
    leaf(tipx, ty, -1, 2 + thick); leaf(tipx, ty, 1, 2 + thick);
    if (ty >= 0 && tipx >= 0 && tipx < W && !(hole && R() < hole)) tone[ty * W + tipx] = pick(0.6);
  }
  return { top: Math.max(0, top - 1), ch: h };
}

// cane colours by kind of culm: lit side, body, joint, shaded side, sheen above a joint
const CANE_TONES = [[3, 2, 1, 1, 4], [4, 4, 2, 3, 4], [2, 1, 0, 0, 2]];

/* ---------- the far hills, grown over with bamboo ----------
 * A hazy grove far off behind the hills, then the hills themselves; each skyline fringed with
 * little cane tops and the slopes striped with stems, so the band of sky over the grove reads
 * as more bamboo, fading into the rain. */
function grove(env, lg, col, ridge, seed, density) {
  const { W, hor } = env, dark = mix(col, [0, 0, 0], 0.12), lite = mix(col, [255, 255, 255], 0.06);
  for (let x = 0; x < W; x++) {
    const y0 = ridge(x), hs = hashStr(seed + ',' + x);
    const stem = hs % density === 0, tuft = stem ? 1 + (hs >> 8) % 3 : 0;
    lg.fillStyle = rgb(col); lg.fillRect(x, y0, 1, hor - y0);
    if (stem) {
      lg.fillStyle = rgb(dark); lg.fillRect(x, y0 - tuft, 1, hor - y0 + tuft);
      // a feathery top: leaves out to both sides
      lg.fillStyle = rgb(col); lg.fillRect(x - 1, y0 - tuft + 1, 3, 1);
      if ((hs >> 12) % 2) lg.fillRect(x - 2, y0 - tuft + 2, 1, 1); else lg.fillRect(x + 2, y0 - tuft + 2, 1, 1);
    } else if ((x + y0) % 3 === 0) { lg.fillStyle = rgb(lite); lg.fillRect(x, y0, 1, 1); }
  }
}
function groveRidge(env, lift, amp, ph) {
  const { W, u, hor } = env, rd = env.ridges;
  return x => {
    const f = x / W * Math.PI * 2;
    return Math.min(hor, Math.round(rd.far(x) - u * (lift + amp * (0.5 + 0.5 * Math.sin(f * 1.7 + ph)) + amp * 0.4 * Math.sin(f * 4.3 + ph * 2))));
  };
}
function backdrop(env, lg) {
  const th = env.theme, rd = env.ridges;
  const skyLow = hex(th.sky[Math.max(0, th.sky.length - 3)]), far = hex(th.far), near = hex(th.near);
  grove(env, lg, mix(far, skyLow, th.rain ? 0.6 : 0.45), groveRidge(env, 8, 9, 1.3), 'g0', 4);
  grove(env, lg, mix(far, skyLow, th.rain ? 0.32 : 0.22), groveRidge(env, 2, 6, 4.1), 'g1', 3);
  grove(env, lg, far, x => rd.far(x), 'g2', 3);
  grove(env, lg, near, x => rd.near(x), 'g3', 2);
}

/* ---------- the water and its lanterns ----------
 * Rain-dark water: the reflection is reduced to three soft tones of the river's own
 * colour, so the grove lies in it as a shadow and the lanterns' light is what shows. */
function calmWater(env) {
  const L = env.water;
  if (!L || L.calmed) return;
  L.calmed = true;
  const w = hex(env.theme.water), sky = hex(env.theme.sky[env.theme.sky.length - 1]);
  const tones = [mix(w, [0, 0, 0], 0.2), w, mix(w, sky, 0.3)];
  const [cv, g] = layer(L.rf.width, L.rf.height);
  g.drawImage(L.rf, 0, 0);
  const img = g.getImageData(0, 0, cv.width, cv.height), d = img.data, Wd = cv.width, Hd = cv.height;
  const lum = new Float32Array(Wd * Hd);
  for (let i = 0; i < lum.length; i++) lum[i] = d[i * 4] * 0.3 + d[i * 4 + 1] * 0.55 + d[i * 4 + 2] * 0.15;
  for (let y = 0; y < Hd; y++) for (let x = 0; x < Wd; x++) {
    let l = 0, n = 0;
    for (let xx = Math.max(0, x - 2); xx <= Math.min(Wd - 1, x + 2); xx++) { l += lum[y * Wd + xx]; n++; }
    l /= n;
    const c = tones[l < 70 ? 0 : l < 105 ? 1 : 2], i = (y * Wd + x) * 4;
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2];
  }
  g.putImageData(img, 0, 0);
  L.rf = cv;
}

/* one floating lantern on its raft, with a broken warm streak running down from it;
 * `seen(x, y)` says where the water shows */
function floatingLantern(g, x, y, lw, flick, reach, k, seen) {
  const lh = lw + 1;
  for (let j = 1; j < reach; j++) {
    if ((j + k) % 3 === 2 || !seen(x + (j % 2), y + j + 1)) continue;
    g.fillStyle = `rgba(255,190,100,${(0.5 * (1 - j / reach) * flick).toFixed(3)})`;
    g.fillRect(x + (j % 2), y + j + 1, Math.max(1, lw - 1), 1);
  }
  g.fillStyle = `rgba(255,200,120,${(0.12 * flick).toFixed(3)})`; g.fillRect(x - lw, y - lh - 2, lw * 3, lh * 2 + 2);
  g.fillStyle = `rgba(255,200,120,${(0.18 * flick).toFixed(3)})`; g.fillRect(x - 2, y - lh, lw + 4, lh + 2);
  g.fillStyle = '#3a2a22'; g.fillRect(x - 1, y + 1, lw + 2, 1);            // the little raft
  g.fillStyle = LAMP; g.fillRect(x, y - lh + 1, lw, lh);
  if (lw < 3) return;
  g.fillStyle = '#fff0c0'; g.fillRect(x + (lw >> 1) - (lw > 3 ? 1 : 0), y - lh + 2, lw > 3 ? 2 : 1, lh - 2);  // the flame inside
  g.fillStyle = LAMP_D; g.fillRect(x, y, lw, 1);
  g.fillStyle = '#4a3024'; g.fillRect(x, y - lh, lw, 1);                  // its dark top
}

/* on a river, nine lanterns come down the channel, and one a tree stands in front of is hidden */
function riverLanterns(g, env, t) {
  const S = env.river, land = AF.landOf(env); if (!S.vis) return;
  const { W, H, u, hor } = env, R = rng(505), tt = env.still ? 0 : t;
  const seen = (x, y) => x >= 0 && x < W && y >= 0 && y < H && S.vis[y * W + x] === 1;
  const boats = [], gaps = [], lanes = [];
  for (let k = 0; k < 9; k++) { gaps.push(R()); lanes.push(R()); }
  for (let k = 0; k < 9; k++) {
    // in loop mode a lantern floats down into the next one's place and takes on its lane (handover)
    const at = AF.u.handover(k, tt), lane = (AF.u.along(lanes, at) - 0.5) * 0.9;
    const q = ((at + AF.u.along(gaps, at) * 0.6) / 9 + (AF.LOOP ? 0 : tt * 0.012)) % 1;
    boats.push({ p: 0.06 + Math.pow(q, 1.2) * 0.94, lane, at });
  }
  boats.sort((a, b) => a.p - b.p);
  for (const { p, lane, at } of boats) {
    // (in loop mode the ninth lantern's place wraps back to the first, so its bob and
    // flicker carry on across the seam; the reflection's broken rows don't move along)
    const ph = AF.LOOP ? at % 9 : at;
    const y = Math.round(hor + p * (H - hor) + Math.sin(tt * AF.u.cyc(0.8) + ph) * 0.5), lw = Math.max(1, Math.round((0.8 + p * 3) * u));
    const x = Math.round(W * land.center(p, env) + lane * W * land.halfWidth(p, W, env) - lw / 2);
    if (!seen(x + (lw >> 1), y + 1)) continue;  // behind a tree, or off the water
    floatingLantern(g, x, y, lw, 0.8 + 0.2 * Math.sin(tt * AF.u.cyc(2.3) + ph * 1.7), Math.round((2 + p * 8) * u), AF.LOOP ? 0 : at, seen);
  }
}

AF.env('bamboo', {
  fx: { init(st, { env }) { calmWater(env); } },

  theme(th) { Object.assign(th, { g0: mixHex(th.g0, '#5e8a48', 0.55), g1: mixHex(th.g1, '#3a6436', 0.55), grass: mixHex(th.grass, '#7aa85a', 0.5) }); },
  /* rain here is soft and green, not grey: a jade mist, and the hills gone blue-green */
  after(th, mood, nightTime) {
    if (!th.rain) return;
    const dusk = mood.time === 'dusk';
    // night is a deep green-blue, light enough that the canes and the far groves still read
    th.sky = nightTime ? ['#162a32', '#1c343a', '#223e40', '#2a4846', '#3a564c', '#4c6452']
      : dusk ? ['#3a4a50', '#4e5e5c', '#687468', '#8a8a74', '#a8987c', '#b8a484']
      : ['#62807e', '#7a9894', '#96b0a4', '#b8c8ae', '#d8d6b0', '#ece2b8'];  // (light breaking low through the rain: warm and bright behind the grove)
    Object.assign(th, nightTime
      ? { far: '#30504a', near: '#28463c', haze: '#3a5a52', g0: '#2e4c34', g1: '#203826', grass: '#3e5e40', tint: '#14302a', tintAmt: 0.16 }
      : { far: dusk ? '#647470' : '#9cb8b6', near: dusk ? '#506656' : '#78a28e', haze: dusk ? '#909690' : '#c6d8d4', tint: '#3e5a48', tintAmt: 0.12 });  // (further is paler and bluer: atmospheric perspective)
    // dark, still water, so the lanterns floating on it are the brightest thing in the scene
    th.water = nightTime ? '#142e30' : dusk ? '#23403c' : '#2a5048';
    th.clouds = { n: 5, top: nightTime ? '#2a4042' : '#c4d2c8', bot: nightTime ? '#1c3032' : '#9eb2a8', a: 235, y0: 0, dy: 0.12, speed: 0.8 };
    th.deck = { n: 3, top: nightTime ? '#20343a' : '#b0c2b6', bot: nightTime ? '#162828' : '#8ea49a', a: 245 };
    th.rain = 170; th.splashes = 30;  // steady, not a downpour
  },
  prepare(env) {
    const night = env.mood.time === 'night';
    if (env.theme.rain) env.fxColors = { rain: night ? 'rgba(150,190,170,.4)' : 'rgba(225,240,228,.5)', rainFar: night ? 'rgba(150,190,170,.2)' : 'rgba(225,240,228,.28)', splash: 'rgba(235,245,238,.8)' };
  },
  calendar: '#4aa070',  // the study calendar in jade, the grove's own (its lime was Natural's green again)
  pals: { rounds: [JADE, DEEP, SAGE], pine: TEAL, bark: { l: hex('#6a9a4a'), m: hex('#4a7a3a'), d: hex('#2e5428') },
    leaf: hex('#6cb45c'), leafL: hex('#a8d87a'), stem: hex('#3f8a4e') },

  tree: {
    width: ({ h, t }) => t.stage >= 1 ? character(t, h).w : 0,
    body: c => (c.t.stage >= 1 ? clump(c) : null),
    /* canes keep a lit side and a shaded side and pale rings at the joints, in whatever
     * palette the pixel is in (its tones by the kind of culm) - so a cane that is being
     * forgotten goes yellow too */
    pixel(col, { x, y, pal, c }) {
      const k = c.cane && c.cane[y * c.W + x];
      if (!k) return col;
      const T = CANE_TONES[c.caneShade || 0];
      if (k === 3) return pal[T[2]];                                   // a joint
      if (k === 1 && c.cane[(y + 1) * c.W + x] === 3) return pal[T[4]];  // the sheen just above it
      return k === 1 ? pal[T[0]] : k === 4 ? pal[T[3]] : pal[T[1]];
    },
  },

  backdrop(env, lg) { backdrop(env, lg); },

  /* stepping stones up the middle */
  ground(env, g, _R) {
    const { W, H, hor } = env;
    let x = W * 0.3, y = H - 2;
    while (y > hor + 6) {
      const s = 1 + (y - hor) / (H - hor) * 2.5;
      ellipseFill(g, x, y, 4 * s, 2 * s, q => q > 0.6 ? '#5e6a60' : '#8a968a');
      y -= 5 * s; x += Math.sin(y * 0.08) * 3 * s + 1.5;
    }
  },

  /* a stone lantern, lit, beside a few of the nearer clumps */
  treeBase(env, g, p) {
    const t = p.it;
    if (t.stage < 2 || t.fromFront > 4 || t.seed % 6 !== 0) return;
    const x = Math.round(p.x + (t.seed % 2 ? 4 : -7)), y = Math.round(p.y), stone = '#8a9088', dark = '#5a605a';
    g.fillStyle = 'rgba(255,200,120,.16)'; g.fillRect(x - 2, y - 7, 7, 7);
    px(g, dark, x, y - 1, 3, 1); px(g, stone, x + 1, y - 3, 1, 2);          // foot and post
    px(g, stone, x, y - 5, 3, 2); px(g, LAMP, x + 1, y - 5, 1, 1);          // the lit firebox
    px(g, dark, x - 1, y - 6, 5, 1); px(g, stone, x + 1, y - 7, 1, 1);     // the cap
  },

  /* the floating lanterns: a slow procession downstream, each with its light running
   * down into the water beneath it. On a lake they cross in two lanes; on a river they
   * come down the channel toward you, growing as they come. */
  frame(g, env, t) {
    if (!env.theme.frozen) {
      if (env.river) riverLanterns(g, env, t);
      else if (env.water) {
        const L = env.water, { W, u } = env, R = rng(505), n = 13, v = 0.4 * u;
        for (let k = 0; k < n; k++) {
          // two lanes: small lanterns far out, bigger ones close to this bank
          const near = k % 2 === 0, lw = near ? Math.max(4, Math.round(3.6 * u)) : 3;
          const lane = near ? 0.55 + R() * 0.3 : 0.05 + R() * 0.25, y = Math.round(L.y0 + 2 + lane * Math.max(1, L.lh - 4));
          const x = Math.round(((k / n) * (W + 12) + R() * 10 + (AF.LOOP ? t * AF.u.drift(v * (near ? 1 : 0.7), W + 12) : t * v * (near ? 1 : 0.7))) % (W + 12)) - 6;
          const flick = 0.8 + 0.2 * Math.sin(t * AF.u.cyc(2.3) + k * 1.7), yb = y + Math.round(Math.sin(t * AF.u.cyc(0.8) + k) * 0.5);
          floatingLantern(g, x, yb, lw, flick, Math.min((near ? 10 : 5) * u, L.y0 + L.lh - yb - 2), k, () => true);
        }
      }
    }
  },
});
})();

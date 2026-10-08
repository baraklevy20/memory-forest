/* Memory Forest - the bamboo grove environment.
 * Everything this environment is lives here: delete it and bamboo.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * Tall jointed canes in soft jade rain, stone lanterns lit at the foot of the grove, and
 * on the water a slow procession of floating paper lanterns, their light running down
 * into the river - the one warm thing in a green, wet afternoon. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, mixHex, px, ellipseFill, rng, layer } = AF.u;
const H6 = a => a.map(hex);

// fresh jade leaves and canes, and a darker blue-green for the second kind. Tones run
// outline, shade, mid, lit, highlight; the canes use them too, so they yellow as well.
const JADE = H6(['#163424', '#2a6040', '#3f8a4e', '#6cb45c', '#a8d87a']);
const TEAL = H6(['#10302c', '#1f5448', '#2e7a62', '#4ea27a', '#8ccc98']);
const LAMP = '#ffcf7a', LAMP_D = '#e0763a';

/* a clump of a few tall, slim canes, well apart, each with its own joints and a
 * feathery spray of leaves towards the top */
function clump(c) {
  const { h, W, H, cx, tone, pick, R, hole } = c;
  const cane = c.cane = new Uint8Array(W * H), base = H - 1;
  const n = h < 10 ? 1 : h < 18 ? 2 : h < 30 ? 3 : 4, thick = h >= 22 ? 2 : 1, gap = thick + 2;
  const leaf = (x, y, dir, len) => {
    for (let e = 1; e <= len; e++) {
      const xx = x + dir * e, yy = y + (e > 1 ? 1 : 0) + (e > 3 ? 1 : 0);
      if (xx < 0 || xx >= W || yy < 0 || yy >= H || (hole && R() < hole)) continue;
      if (!cane[yy * W + xx]) tone[yy * W + xx] = pick(dir < 0 ? 0.55 - e * 0.12 : -0.05 - e * 0.1);
    }
  };
  let top = H;
  for (let k = 0; k < n; k++) {
    const x0 = cx + Math.round((k - (n - 1) / 2) * gap + (R() - 0.5) * 0.8), hh = Math.round(h * (k === (n >> 1) ? 1 : 0.72 + R() * 0.24));
    const joint = Math.max(3, Math.round(h / 7) + (R() < 0.5 ? 0 : 1)), off = Math.floor(R() * joint);
    for (let s = 0; s < hh; s++) {
      const y = base - s, x = x0 + (s > hh * 0.8 && k !== (n >> 1) ? (x0 < cx ? -1 : x0 > cx ? 1 : 0) : 0);
      const node = (s + off) % joint === 0 && s > 1;
      for (let q = 0; q < thick; q++) {
        if (x + q < 0 || x + q >= W) continue;
        const i = y * W + x + q;
        tone[i] = 2; cane[i] = node ? 3 : q === 0 ? 1 : 2;
      }
      // leaves from the upper joints, longer higher up
      if (node && s > hh * 0.5) {
        const len = 2 + Math.round((s / hh) * (thick + 2) * (0.6 + R() * 0.5));
        if (R() < 0.8) leaf(x, y, -1, len);
        if (R() < 0.8) leaf(x + thick - 1, y, 1, len);
      }
      top = Math.min(top, y);
    }
    // the tip: a small drooping fan
    const tx = x0 + (thick >> 1), ty = base - hh;
    leaf(tx, ty, -1, 2 + thick); leaf(tx, ty, 1, 2 + thick);
    if (ty >= 0 && !(hole && R() < hole)) tone[ty * W + tx] = pick(0.6);
  }
  return { top: Math.max(0, top - 1), ch: h };
}

/* Rain-dark water: the reflection is reduced to three soft tones of the river's own
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
    const x = Math.round(W * land.center(p) + lane * W * land.halfWidth(p, W) - lw / 2);
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
    th.sky = nightTime ? ['#0c1a1c', '#122426', '#182e2e', '#1e3834', '#26423a', '#2e4c40']
      : dusk ? ['#3a4a50', '#4e5e5c', '#687468', '#8a8a74', '#a8987c', '#b8a484']
      : ['#6e8c84', '#82a096', '#98b2a6', '#b0c4b2', '#c8d4bc', '#dad8bc'];
    Object.assign(th, nightTime
      ? { far: '#1e3434', near: '#1a302c', haze: '#2a4040', g0: '#223a2a', g1: '#16281e', grass: '#2e4a32', tint: '#10241e', tintAmt: 0.3 }
      : { far: dusk ? '#5e6e66' : '#8aa89c', near: dusk ? '#4e6454' : '#6e9a80', haze: dusk ? '#8a8e80' : '#b8ccbc', tint: '#3e5a48', tintAmt: 0.12 });
    // dark, still water, so the lanterns floating on it are the brightest thing in the scene
    th.water = nightTime ? '#0e2426' : dusk ? '#23403c' : '#2a5048';
    th.clouds = { n: 5, top: nightTime ? '#24383a' : '#c4d2c8', bot: nightTime ? '#182a2c' : '#9eb2a8', a: 235, y0: 0, dy: 0.12, speed: 0.8 };
    th.deck = { n: 3, top: nightTime ? '#1c2e30' : '#b0c2b6', bot: nightTime ? '#122224' : '#8ea49a', a: 245 };
    th.rain = 170; th.splashes = 30;  // steady, not a downpour
  },
  prepare(env) {
    const night = env.mood.time === 'night';
    if (env.theme.rain) env.fxColors = { rain: night ? 'rgba(150,190,170,.4)' : 'rgba(225,240,228,.5)', rainFar: night ? 'rgba(150,190,170,.2)' : 'rgba(225,240,228,.28)', splash: 'rgba(235,245,238,.8)' };
  },
  pals: { rounds: [JADE], pine: TEAL, bark: { l: hex('#6a9a4a'), m: hex('#4a7a3a'), d: hex('#2e5428') },
    leaf: hex('#6cb45c'), leafL: hex('#a8d87a'), stem: hex('#3f8a4e') },

  tree: {
    width: ({ h, t }) => t.stage >= 1 ? Math.max(7, Math.round(h * 0.6)) | 1 : 0,
    body: c => (c.t.stage >= 1 ? clump(c) : null),
    /* canes keep a lit side and a shaded side and pale rings at the joints, in whatever
     * palette the pixel is in - so a cane that is being forgotten goes yellow too */
    pixel(col, { x, y, pal, c }) {
      const k = c.cane && c.cane[y * c.W + x];
      if (!k) return col;
      if (k === 3) return pal[1];                                   // a joint
      if (k === 1 && c.cane[(y + 1) * c.W + x] === 3) return pal[4];  // the sheen just above it
      return k === 1 ? pal[3] : pal[2];
    },
  },

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
    if (env.theme.frozen) return;
    if (env.river) return riverLanterns(g, env, t);
    const L = env.water;
    if (!L) return;
    const { W, u } = env, R = rng(505), n = 13, v = 0.4 * u;
    for (let k = 0; k < n; k++) {
      // two lanes: small lanterns far out, bigger ones close to this bank
      const near = k % 2 === 0, lw = near ? Math.max(4, Math.round(3.6 * u)) : 3;
      const lane = near ? 0.55 + R() * 0.3 : 0.05 + R() * 0.25, y = Math.round(L.y0 + 2 + lane * Math.max(1, L.lh - 4));
      const x = Math.round(((k / n) * (W + 12) + R() * 10 + (AF.LOOP ? t * AF.u.drift(v * (near ? 1 : 0.7), W + 12) : t * v * (near ? 1 : 0.7))) % (W + 12)) - 6;
      const flick = 0.8 + 0.2 * Math.sin(t * AF.u.cyc(2.3) + k * 1.7), yb = y + Math.round(Math.sin(t * AF.u.cyc(0.8) + k) * 0.5);
      floatingLantern(g, x, yb, lw, flick, Math.min((near ? 10 : 5) * u, L.y0 + L.lh - yb - 2), k, () => true);
    }
  },
});
})();

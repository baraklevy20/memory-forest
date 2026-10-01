/* Memory Forest - the frozen market environment.
 * Everything this environment is lives here: delete it and frozen_market.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * The Christmas market has moved onto the ice. An old town lines the far bank of a frozen
 * river: half-timbered and step-gabled houses with lit windows, a twin-spired cathedral, the
 * great town tree on the quay in silver, red and blue, strings of lights running from its
 * crown to two poles out on the ice. Below the quay the river is frozen hard: a stone bridge
 * of arches standing on the ice with lanterns and dark statues on its parapet and a gatehouse
 * at its end, stalls and a turning carousel out on the ice, skaters gliding, twirling, going
 * under the arches, and a beginner who wobbles and now and then sits down hard. The ice
 * mirrors the town, its lights lying on it as long warm streaks, with gloss, cracks and drifts
 * of snow. The whole riverside stands on the tree line, so the biggest forest never hides it;
 * the river winding through the forest (or a lake, or the ponds) is frozen too, with skaters
 * of its own. Every few minutes Santa's sleigh and his four reindeer cross the sky above the
 * roofs and spires (and across the moon, when it shows), a trail of sparkles behind.
 * The park: clipped yew and holly topiary wrapped in fairy lights (broadleaf) and dark firs
 * tied with red bows (conifer). Nothing on a tree is ever yellow, gold or orange. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rgb, rng, hashStr, layer, B4 } = AF.u;
const H6 = a => a.map(hex);
const bay = (x, y) => B4[(y & 3) * 4 + (x & 3)];
const hourOf = t => t === 'night' ? 'night' : (t === 'dusk' || t === 'golden_hour') ? 'dusk' : t === 'dawn' ? 'dawn' : 'day';
// how far each hour is from the night's colours toward the day's
const DAYNESS = { night: 0, dusk: 0.3, dawn: 0.58, day: 1 };
const dk = th => DAYNESS[th.xh] == null ? 0.3 : DAYNESS[th.xh];
const blend = (a, b, k) => a.map((c, i) => mix(c, b[i], k));
const lampsOn = th => th.xh !== 'day';
const FOLK = 22, BRIDGE_FOLK = 4;            // people strolling along the quay, and crossing the bridge
const ICE_GLINTS = 26, SNOW_GLINTS = 40;     // twinkles on the river's ice, and in the park's snow
// seconds: how often Santa's sleigh crosses the sky, how long it takes, and when in a session it
// is right of the sky's middle (so the first crossing comes a few seconds after the forest opens)
const SLEIGH_EVERY = 210, SLEIGH_SECS = 26, SLEIGH_FIRST = 12.345;
const SLEIGH_AT = 0.9, SLEIGH_RISE = 0.07;   // where across it that moment is, and how steeply it climbs going left
const SLEIGH_SLENDER = 6;                    // anything on the skyline narrower than twice this the sleigh may pass behind

/* ---------- the hours ---------- */
const LOOKS = {
  dusk: {
    sky: ['#0c1230', '#171d48', '#26285c', '#3e326e', '#633f78', '#91537c'],
    far: '#3a3662', near: '#2c2a50', g0: '#8c8ab8', g1: '#5c5a8c', grass: '#aeacd2', haze: '#5c5684', hzStep: 0.1,
    water: '#4a4a7a', clouds: null, stars: 0, birdC: '#1a1830', shadow: 0 },
  night: {
    sky: ['#03060f', '#060c1c', '#0a1328', '#0f1a36', '#162240', '#1e2a4c'],
    far: '#141c34', near: '#10162a', g0: '#4c5c84', g1: '#2e3a5c', grass: '#6c7ca4', haze: '#1e2848', hzStep: 0.1,
    water: '#1d2a4a', clouds: null, stars: 0, birdC: '#0a0e1c', shadow: 0 },
  dawn: {
    sky: ['#2a3258', '#464c78', '#6e668e', '#a07e98', '#cc9ca0', '#e8c0b0'],
    far: '#6a6a90', near: '#56587e', g0: '#b6bad6', g1: '#8a8eb2', grass: '#d2d4e8', haze: '#9c96b6', hzStep: 0.11,
    water: '#9a9ac0', clouds: { n: 3, top: '#f6dcd6', bot: '#b89cb4', a: 225 }, stars: 0, birdC: '#3a3450', shadow: 0 },
  day: {
    sky: ['#6a94c6', '#82a8d2', '#9cbcdc', '#b4cee6', '#cadcee', '#dce8f2'],
    far: '#9aaccc', near: '#8ea0bc', g0: '#e0e8f3', g1: '#bcc9de', grass: '#f0f4fa', haze: '#c4d2e2', hzStep: 0.12,
    water: '#a8c0dc', clouds: { n: 4, top: '#ffffff', bot: '#d8e2ee', a: 240 }, stars: 0, birdC: '#3d4a5a', shadow: 0.5 },
};
const clone = o => JSON.parse(JSON.stringify(o));
const SNOW_SKY = {
  dusk: ['#1a1f4c', '#282c62', '#3c3a74', '#584884', '#7c5889', '#a2708e'],
  night: ['#04070f', '#08101f', '#0e182e', '#14213c', '#1c2a48', '#253454'],
  dawn: ['#3a4270', '#565a88', '#7c7298', '#a28aa8', '#c6a2b0', '#dcbcbc'],
};

/* ---------- the park's trees: 5 tones, outline, shade, mid, lit, highlight ---------- */
const YEW_N = H6(['#040b0d', '#0b1e22', '#12302e', '#1b453a', '#2a5f48']), YEW_D = H6(['#10221c', '#1c3c2e', '#28583e', '#3a764c', '#58985e']);
const HOL_N = H6(['#050b07', '#0c2214', '#16361c', '#214c26', '#326a32']), HOL_D = H6(['#122814', '#1e441e', '#2c6228', '#3e8034', '#5ca24c']);
const FIR_N = H6(['#03070b', '#07141a', '#0d2226', '#153232', '#1f4640']), FIR_D = H6(['#0b181a', '#142e2c', '#1c443e', '#285c50', '#3c7866']);
const BARK_N = H6(['#08060a', '#1a1216', '#2e2224']), BARK_D = H6(['#2a1e18', '#4a3426', '#6a4c36']);
const PALS = {};
function palsFor(th) {
  const k = dk(th), key = String(k);
  if (!PALS[key]) {
    PALS[key] = { yew: blend(YEW_N, YEW_D, k), holly: blend(HOL_N, HOL_D, k), fir: blend(FIR_N, FIR_D, k), bark: blend(BARK_N, BARK_D, k) };
    MINE.add(PALS[key].yew); MINE.add(PALS[key].holly); MINE.add(PALS[key].fir);
  }
  return PALS[key];
}
const MINE = new Set();
// the fairy lights, the bows and the berries: only ever white, ice, blue and red
const FAIRY_ON = H6(['#f4f8ff', '#b4dcff', '#6e9cff', '#ff5e6e']), FAIRY_OFF = H6(['#c4ccd8', '#8ea6c0', '#4e66a0', '#a84a54']);
const BOW = { on: H6(['#5e0c18', '#b01c2c', '#e8404c', '#ff8a90']), off: H6(['#4a0e16', '#8e1a26', '#c0343e', '#e06a70']) };
const RIMC = { dusk: hex('#d8a0b4'), night: hex('#7a8cc8'), dawn: hex('#f0c8c8'), day: null };

/* a clipped ball of leaves: clean edges, lit from the upper left, a crisp dithered sheen */
function ball(c, px, py, rx, ry) {
  const { W, H, tone, hole, R } = c;
  let top = H;
  for (let y = Math.floor(py - ry - 1); y <= py + ry + 1; y++) for (let x = Math.floor(px - rx - 1); x <= px + rx + 1; x++) {
    if (x < 0 || y < 0 || x >= W || y >= H) continue;
    const nx = (x + 0.5 - px) / rx, ny = (y + 0.5 - py) / ry, q = nx * nx + ny * ny;
    if (q > 1) continue;
    if (hole && R() < hole) continue;
    const l = -(nx * 0.55 + ny * 0.8) + Math.sqrt(1 - q) * 0.35;
    let tn = l > 0.62 ? 4 : l > 0.2 ? 3 : l > -0.3 ? 2 : 1;
    if (tn === 3 && l > 0.5 && bay(x, y) < 6) tn = 4;
    if (tn === 2 && l > 0.13 && bay(x, y) < 5) tn = 3;
    if (tn === 1 && l > -0.4 && bay(x, y) < 5) tn = 2;
    tone[y * W + x] = tn;
    top = Math.min(top, y);
  }
  return top;
}
/* a clipped topiary on a straight stem: a lollipop, then two and three stacked balls */
function topiary(c) {
  const { t, h, w, cx, base, put, ancient } = c;
  const B = palsFor(c.th).bark, st = t.stage;
  const tw = ancient ? 2 : h >= 20 ? 2 : 1;
  const stem = (y0, y1) => { for (let y = y0; y <= y1; y++) for (let q = 0; q < tw; q++) put(cx - (tw >> 1) + q, y, q === 0 ? B[2] : (y & 1 ? B[1] : B[0])); };
  c.lights = [];
  let top;
  if (st <= 1) {  // a whip with a little ball, tied to a stake
    const r = Math.max(1.6, h * 0.24);
    stem(Math.round(base - h * 0.5), base);
    for (let y = base - Math.round(h * 0.62); y <= base; y++) put(cx + 2, y, B[2]);
    put(cx + 1, base - Math.round(h * 0.3), B[0]);
    top = ball(c, cx + 0.5, base - h + r + 0.5, r, r);
  } else if (st === 2 || st === 3) {  // a lollipop on a stem (a stake beside the young one)
    const r = w / 2 - 0.6, ry = r * 0.92, cy = base - h + ry + 1;
    stem(Math.round(cy), base);
    if (st === 2) { for (let y = base - Math.round(h * 0.42); y <= base; y++) put(cx + 2, y, B[2]); put(cx + 1, base - Math.round(h * 0.36), B[0]); }
    top = ball(c, cx + 0.5, cy, r, ry);
  } else if (st === 4) {  // two tiers: a big ball, the stem, a smaller one above
    const r1 = w / 2 - 0.6, r2 = r1 * 0.64, y2 = base - h + r2 + 1, y1 = y2 + r2 + r1 * 0.85 + 2;
    stem(Math.round(y2), base);
    top = ball(c, cx + 0.5, y2, r2, r2 * 0.95);
    ball(c, cx + 0.5, y1, r1, r1 * 0.84);
  } else {  // ancient: three stacked tiers, largest at the foot, a finial knob on top
    const r1 = w / 2 - 0.6, r2 = r1 * 0.74, r3 = r1 * 0.5;
    const y3 = base - h + r3 + 2.5, y2 = y3 + r3 + r2 * 0.8 + 1.5, y1 = y2 + r2 * 0.8 + r1 * 0.78 + 1.5;
    stem(Math.round(y3) - 1, base);
    ball(c, cx + 0.5, y3 - r3 - 1, 1.2, 1.2);
    top = Math.min(ball(c, cx + 0.5, y3, r3, r3 * 0.95), base - h + 1);
    ball(c, cx + 0.5, y2, r2, r2 * 0.82);
    ball(c, cx + 0.5, y1, r1, r1 * 0.78);
    put(cx - 2, base, B[0]); put(cx + 2, base, B[0]);
  }
  if (st >= 3) { put(cx - (tw >> 1) - 1, base, B[0]); put(cx - (tw >> 1) + tw, base, B[0]); }
  return { top: Math.max(0, top), ch: base - top };
}

/* a dark fir: drooping tiers, a straight leader, red bows at the tips of the tiers */
function fir(c) {
  const { t, h, W, H, w, cx, base, tone, put, R, hole, ancient } = c;
  const B = palsFor(c.th).bark, st = t.stage;
  const tw = ancient || h >= 24 ? 2 : 1, trunkH = Math.max(1, Math.round(h * 0.1));
  for (let y = base; y >= base - trunkH - 2; y--) for (let q = 0; q < tw; q++) put(cx - (tw >> 1) + q, y, q ? B[0] : B[1]);
  put(cx - (tw >> 1) - 1, base, B[0]); put(cx - (tw >> 1) + tw, base, B[0]);
  const topY = st >= 5 ? 3 : 1, lowY = base - trunkH;
  const tiers = st <= 1 ? 2 : st === 2 ? 3 : st === 3 ? 4 : st === 4 ? 5 : 6, span = (lowY - topY) / tiers;
  const tips = [];
  for (let i = tiers - 1; i >= 0; i--) {
    const f = (i + 1) / tiers, ty = topY + span * (i + 0.6);
    const hw = Math.max(1.5, (w / 2 - 0.5) * (0.2 + 0.8 * f)), thick = Math.max(2.2, span * 1.15);
    for (let x = Math.floor(cx - hw); x <= Math.ceil(cx + hw); x++) {
      const dx = x + 0.5 - (cx + 0.5), d = Math.abs(dx) / hw;
      if (d > 1) continue;
      if (d > 0.82 && hashStr(x + '|' + i + '|' + t.seed) % 3 === 0) continue;
      const droop = Math.pow(d, 1.6) * Math.min(hw * 0.45, span * 0.9);
      const yT = Math.round(ty + droop - (1 - d) * thick * 0.62), yB = Math.round(ty + droop + (d < 0.7 ? 1 : 0));
      for (let y = yT; y <= yB; y++) {
        if (x < 0 || y < 0 || x >= W || y >= H) continue;
        if (hole && R() < hole) continue;
        const l = -(dx / hw) * 0.6 + (y === yT ? 0.55 : y === yB ? -0.5 : 0) + (R() - 0.5) * 0.22;
        tone[y * W + x] = l > 0.62 ? 4 : l > 0.14 ? 3 : l > -0.35 ? 2 : 1;
      }
      if (d > 0.88) tips.push([x, yB, i, dx < 0 ? -1 : 1]);
    }
  }
  // the leader
  for (let y = 0; y < topY + 2; y++) if (y >= topY - 1) tone[y * W + cx] = 3;
  // bows on the tier tips, alternating sides, and one on the leader of the oldest
  c.bows = new Map();
  if (st >= 4) {
    const seen = new Set();
    let n = 0;
    for (const [x, y, i, side] of tips) {
      const key = i + ':' + side;
      if (seen.has(key) || i < 2 || ((i + (side > 0 ? 1 : 0) + t.seed) & 1) || n >= (ancient ? 3 : 2)) continue;
      seen.add(key); n++;
      bow(c, x - side, y - 1);
    }
    if (ancient) bow(c, cx, topY - 2);
  }
  return { top: 0, ch: base };
}
function bow(c, x, y) {
  const { W, H, tone } = c;
  // loops, knot, tails: 0 dark, 1 mid, 2 lit, 3 glint
  for (const [dx, dy, k] of [[-1, 0, 2], [1, 0, 1], [-1, -1, 3], [1, -1, 1], [0, 0, 0], [-1, 1, 1], [1, 1, 0]]) {
    const X = x + dx, Y = y + dy;
    if (X < 0 || Y < 0 || X >= W || Y >= H) continue;
    if (tone[Y * W + X] < 0) tone[Y * W + X] = 2;
    c.bows.set(Y * W + X, k);
  }
}
function sprout(c) {
  const { h, cx, base, put, tone, W } = c, B = palsFor(c.th).bark;
  for (let y = base; y >= base - 1; y--) put(cx, y, B[1]);
  const top = Math.max(0, base - h + 1);
  for (let y = top; y < base - 1; y++) {
    const hw = Math.floor((y - top) / 2.2);
    for (let x = cx - hw; x <= cx + hw; x++) tone[y * W + x] = x < cx ? 3 : x === cx ? 2 : 1;
  }
  return { top, ch: base - top };
}

const TREE = {
  width(c) {
    const { t, h, ancient } = c;
    if (t.kind === 1) return Math.max(5, Math.round(h * (ancient ? 0.7 : t.stage <= 1 ? 0.55 : 0.6))) | 1;
    return Math.max(5, Math.round(h * (ancient ? 0.66 : t.stage <= 1 ? 0.5 : t.stage === 4 ? 0.6 : 0.64))) | 1;
  },
  body(c) {
    palsFor(c.th);
    if (c.t.kind === 1) return c.t.stage <= 1 ? sprout(c) : fir(c);
    return topiary(c);
  },
  palette(c) {
    const P = palsFor(c.th);
    return { round: (c.t.seed >> 2) % 3 === 0 ? P.holly : P.yew, pine: P.fir };
  },
  pixel(col, { x, y, tn, pal, sr, c }) {
    if (!MINE.has(pal)) return col;  // yellowing branches keep their own colours, untouched
    const on = lampsOn(c.th);
    if (c.bows) { const b = c.bows.get(y * c.W + x); if (b != null) return (on ? BOW.on : BOW.off)[b]; }
    const P = palsFor(c.th);
    const edgeL = !c.inside(x - 1, y);
    if (pal !== P.fir && c.t.stage >= 2 && tn >= 1) {
      // fairy lights wound round the clipped balls in a spiral, and holly berries
      const band = (y * 2 + x + (sr & 7)) % 7;
      const k = hashStr(x + '*' + y + '*' + sr);
      if (band === 0 && k % 3 !== 0) return (on ? FAIRY_ON : FAIRY_OFF)[k % 7 === 0 ? 3 : k % 5 === 0 ? 2 : (k >> 3) % 3 === 0 ? 1 : 0];
      if (pal === P.holly && band === 4 && tn >= 2 && k % 5 === 0) return (on ? BOW.on : BOW.off)[k & 1 ? 2 : 1];
    } else if (pal === P.fir && c.t.stage >= 3 && tn >= 2) {
      const k = hashStr(x + '#' + y + '#' + sr);
      if (k % 23 === 0) return (on ? FAIRY_ON : FAIRY_OFF)[k & 1 ? 0 : 2];  // a few silver and blue baubles
    }
    const rim = RIMC[c.th.xh];
    if (rim && tn >= 1 && edgeL && y < c.H * 0.8) return mix(col, rim, c.th.xh === 'night' ? 0.35 : 0.45);
    return col;
  },
};

/* ================= the old town ================= */
// materials in the town's plan
const M = { PL: 1, TIM: 2, ROOF: 3, WL: 4, WD: 5, SNOW: 6, CHIM: 7, DOOR: 8, ST: 9, SPIRE: 10, ROSE: 11, LAN: 12, FIR: 13, GL: 14, STAR: 15,
  WOOD: 16, AWN: 17, SLIT: 18, BULB: 19, HOLE: 20, GOODS: 21, BRICK: 22, IRON: 23, CLOCK: 24, SIGN: 25, SNOWS: 26,
  QUAY: 27, BST: 28, LAMP: 29, STAT: 30 };
// what shines, and so lies on the ice as a long warm streak
const SHINES = new Set([M.WL, M.SLIT, M.BULB, M.GL, M.STAR, M.ROSE, M.LAN, M.LAMP, M.HOLE]);

/* the ice for each hour: far (under the quay), near, the gloss, a crack's light and dark */
const ICE = {
  dusk: { far: '#3c4a86', near: '#6e86c0', gloss: '#b2caee', crack: '#d6e4fa', crackD: '#2a3264', trail: '#9cb4e0' },
  night: { far: '#101a3a', near: '#243a6a', gloss: '#5e7cb4', crack: '#8eaad6', crackD: '#080e22', trail: '#46628e' },
  dawn: { far: '#6c78a8', near: '#9eb2d6', gloss: '#e4ecf8', crack: '#f4f6fc', crackD: '#4c5484', trail: '#c8d6ee' },
  day: { far: '#6e9ac4', near: '#a4c8e6', gloss: '#e8f4fc', crack: '#f8fcff', crackD: '#4a78a8', trail: '#cfe4f4' },
};
const ICEP = {};
function icePal(th) {
  const h = ICE[th.xh] ? th.xh : 'dusk';
  if (!ICEP[h]) { ICEP[h] = {}; for (const k in ICE[h]) ICEP[h][k] = hex(ICE[h][k]); }
  return ICEP[h];
}

/* colours: [night, day]; the hour mixes between them */
const TC = {
  plaster: [['#352c3c', '#e6dac2'], ['#3a2834', '#d8a8a0'], ['#26304a', '#a6bcd4'], ['#2c3638', '#b4c6a4'], ['#3a2e2c', '#d8bc98'], ['#302a40', '#c4b4d4']],
  timber: ['#120c12', '#4c3226'], roof: [['#2c1418', '#8e3c30'], ['#171b28', '#50596a'], ['#26181a', '#7a4636'], ['#1a2224', '#4a6a66']],
  brick: ['#2c1618', '#9c4e3c'], brickL: ['#3a1e1e', '#b8664e'],
  snow: ['#848ebc', '#f6f8fc'], snowS: ['#555e8a', '#c6d2e6'],
  stone: ['#262434', '#b6ac9e'], stoneS: ['#18161f', '#8c8278'], stoneL: ['#34304a', '#d2c8b8'], stoneJ: ['#1e1c28', '#a09686'],
  spire: ['#15232a', '#5e8e80'], spireS: ['#0b1317', '#436a5e'], spireL: ['#22363e', '#82b0a0'],
  winD: ['#0c1020', '#44586e'], winR: ['#26304c', '#aac0d6'], door: ['#170c0c', '#4a2c22'], iron: ['#07070b', '#2a2a30'],
  wood: ['#2a1a16', '#7c5436'], woodS: ['#170e0c', '#583a26'], woodL: ['#402a20', '#9e6c46'],
  awnR: ['#7a1a26', '#cc323e'], awnG: ['#123e2a', '#2e7c4c'], awnW: ['#9a94ae', '#f2eee6'],
  slitOff: ['#1c1214', '#5a4034'], goods: ['#2a1414', '#6a2a24'],
  gfir: [['#02070a', '#0b1c18'], ['#061418', '#143024'], ['#0b2224', '#1e4630'], ['#12302e', '#2a5e3c'], ['#1c443a', '#40784c']],
  clock: ['#6a6a7c', '#e8e4d8'],
};
const LIT = { core: hex('#ffd98c'), edge: hex('#f2a656'), deep: hex('#c8703a'), spill: hex('#8a5a48') };
const GLASS = H6(['#e8404c', '#4a78ff', '#a050d8', '#ffc870', '#40b0c8']);
const TREE_LIGHTS = H6(['#f4f8ff', '#ff4e5e', '#5a8cff', '#c8e4ff']), TREE_LIGHTS_DIM = H6(['#8a9ab4', '#8a2a36', '#2e4a8a', '#7e9ab8']);
function colours(th) {
  const k = th.xh === 'dusk' ? 0.4 : dk(th), o = {};  // at dusk the facades keep a little more of their colour
  for (const key in TC) {
    const v = TC[key];
    o[key] = Array.isArray(v[0]) ? v.map(p => mix(hex(p[0]), hex(p[1]), k)) : mix(hex(v[0]), hex(v[1]), k);
  }
  return o;
}

/* where the town stands: on the far bank of the frozen river, the river's ice between the
 * quay and the forest's tree line, so the market on the ice always clears the biggest forest */
function townAt(env) {
  const { W, u, hor } = env;
  const k = u < 0.8 ? u : 1;
  const L = Math.min(hor, Math.round(AF.treeLine(env)));
  const iceH = Math.round(Math.max(11, Math.min(16, (L - 20) * 0.4)) * k);
  const base = Math.min(hor - Math.round(16 * u), L + Math.round(1 * u) - iceH);
  const VW = Math.round(W / k), VB = Math.round(base / k), VL = Math.round(L / k), VE = Math.round((hor + 2) / k);
  // everything is built to this scale of height; a very big forest squeezes the town
  const f = Math.max(0.5, Math.min(1, (VB - 3) / 60));
  return { k, base, VW, VB, VL, VE, f };
}

/* the plan: a grid of materials, filled back to front */
function townPlan(T, th) {
  const { VW, VB, VL, VE, f } = T, VH = VE + 1;
  const G = new Uint8Array(VW * VH), P = new Uint8Array(VW * VH), D = new Uint8Array(VW * VH);  // D: 1 back row
  const OB = new Int16Array(VW * VH);  // for what stands out on the ice: the row its foot is on
  const R = rng(1224);
  let depth = 0, obj = 0;
  const set = (x, y, m, p = 0) => { x = Math.round(x); y = Math.round(y); if (x >= 0 && y >= 0 && x < VW && y < VH) { const i = y * VW + x; G[i] = m; P[i] = p; D[i] = depth; OB[i] = obj; } };
  const get = (x, y) => (x >= 0 && y >= 0 && x < VW && y < VH ? G[y * VW + x] : 0);
  const rect = (x0, y0, x1, y1, m, p = 0) => { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) set(x, y, m, p); };
  const S = v => Math.max(1, Math.round(v * f));
  const lit = (x, y, p) => lampsOn(th) && (hashStr('w' + x + ',' + y) % 100) < p;
  const litP = th.xh === 'night' ? 82 : th.xh === 'dusk' ? 74 : th.xh === 'dawn' ? 30 : 0;
  const B = VB;
  // the quay: its snowy top, two rows of wall, then the ice; the stalls stand a few rows out on it
  const I0 = B + 4, SB = Math.min(VE - 3, I0 + Math.max(3, Math.min(6, Math.round((VL - I0) * 0.4))));
  const big = VB >= 48;
  const out = { chimneys: [], stalls: [], lights: [], I0, SB };

  /* a window of w x h panes-worth, lit or dark, with a sill */
  const win = (x, y, w, h, on) => {
    rect(x, y, x + w - 1, y + h - 1, on ? M.WL : M.WD);
    if (!on) set(x, y, M.WD, 1);  // a glint of sky in the top corner
  };
  /* a front-gabled half-timbered house */
  const gableHouse = (x0, w, floors, pl, roof) => {
    const fh = 6, wallH = floors * fh, top = B - wallH, gh = Math.round(w / 2 * 1.2) + 1, peak = top - gh;
    rect(x0, top, x0 + w - 1, B, M.PL, pl);
    // the gable: plaster, a verge of tiles on each slope, snow on the verge
    for (let y = peak; y < top; y++) {
      const hw = (y - peak) / gh * (w / 2 + 0.5);
      for (let x = Math.floor(x0 + w / 2 - hw - 1); x <= Math.ceil(x0 + w / 2 + hw); x++) {
        const d = Math.abs(x + 0.5 - (x0 + w / 2));
        if (d > hw + 0.5) continue;
        set(x, y, d > hw - 1.2 ? M.ROOF : M.PL, d > hw - 1.2 ? roof : pl);
      }
    }
    // the timbers: posts at the corners, a beam on every floor, braces in the end panels
    for (let y = top; y <= B; y++) { set(x0, y, M.TIM); set(x0 + w - 1, y, M.TIM); }
    for (let fl = 0; fl <= floors; fl++) rect(x0, top + fl * fh, x0 + w - 1, top + fl * fh, M.TIM);
    const cols = w >= 13 ? 3 : 2, gap = (w - 2 - cols * 2) / (cols + 1);
    for (let fl = 0; fl < floors - 1; fl++) {
      const y0 = top + fl * fh + 1;
      for (let ci = 0; ci < cols; ci++) {
        const wx = Math.round(x0 + 1 + gap * (ci + 1) + ci * 2);
        win(wx, y0 + 1, 2, 3, lit(wx, y0, litP));
        set(wx - 1, y0 + 4, M.TIM); set(wx + 2, y0 + 4, M.TIM);  // posts beside each window, down to the rail
        for (let yy = y0; yy < y0 + fh - 1; yy++) { set(wx - 1, yy, M.TIM); set(wx + 2, yy, M.TIM); }
      }
      // a St Andrew's cross under the middle window of the first floor, braces at the ends
      set(x0 + 1, y0 + 3, M.TIM); set(x0 + 2, y0 + 2, M.TIM); set(x0 + w - 2, y0 + 3, M.TIM); set(x0 + w - 3, y0 + 2, M.TIM);
    }
    // the gable's own timbers: a king post, a collar, a little lit attic window
    const mx = Math.floor(x0 + w / 2 - 0.5);
    rect(x0 + 1, top - Math.round(gh * 0.45), x0 + w - 2, top - Math.round(gh * 0.45), M.TIM);
    for (let y = peak + 2; y < top; y++) if (get(mx, y) === M.PL) set(mx, y, M.TIM);
    const ay = top - Math.round(gh * 0.3);
    if (get(mx - 1, ay) === M.PL) { win(mx - 1, ay, 1, 2, lit(mx, ay, litP - 10)); win(mx + 1, ay, 1, 2, lit(mx + 1, ay, litP - 10)); }
    // the ground floor: a shop window and an arched door
    const gy = B - fh + 1, dl = hashStr('d' + x0) & 1;
    const dx = dl ? x0 + 2 : x0 + w - 4;
    rect(dx, gy + 1, dx + 1, B, M.DOOR); set(dx, gy, M.TIM);
    const sx = dl ? x0 + 5 : x0 + 2, sw = w - 8;
    if (sw >= 2) win(sx, gy + 1, sw, 3, lampsOn(th));
    return peak;
  };
  /* a step-gabled brick house */
  const stepHouse = (x0, w, floors, pl) => {
    const fh = 6, wallH = floors * fh, top = B - wallH;
    rect(x0, top, x0 + w - 1, B, M.BRICK, pl);
    const steps = Math.floor(w / 4);
    let peak = top;
    for (let s = 0; s <= steps; s++) {
      const ins = s * 2, y1 = top - s * 3;
      if (x0 + ins > x0 + w - 1 - ins) break;
      rect(x0 + ins, y1 - 2, x0 + w - 1 - ins, y1, M.BRICK, pl);
      set(x0 + ins, y1 - 3, M.SNOW); set(x0 + ins + 1, y1 - 3, M.SNOW); set(x0 + w - 1 - ins, y1 - 3, M.SNOW); set(x0 + w - 2 - ins, y1 - 3, M.SNOW);
      peak = y1 - 3;
    }
    rect(Math.floor(x0 + w / 2) - 1, peak, Math.floor(x0 + w / 2), peak, M.SNOW);
    const cols = w >= 12 ? 3 : 2, gap = (w - cols * 2) / (cols + 1);
    for (let fl = 0; fl < floors; fl++) {
      const y0 = top + fl * fh + 1;
      for (let ci = 0; ci < cols; ci++) {
        const wx = Math.round(x0 + gap * (ci + 1) + ci * 2);
        if (fl === floors - 1 && ci === 1) { rect(wx, y0 + 1, wx + 1, B, M.DOOR); set(wx, y0, M.TIM); set(wx + 1, y0, M.TIM); continue; }
        win(wx, y0 + 1, 2, 3, fl === floors - 1 ? lampsOn(th) : lit(wx, y0, litP));
        rect(wx - 1, y0 + 4, wx + 2, y0 + 4, M.ST);  // a stone sill
        rect(wx, y0, wx + 1, y0, M.ST);               // and lintel
      }
    }
    const ay = top - 4;
    if (steps >= 2) win(Math.floor(x0 + w / 2) - 1, ay, 2, 2, lit(x0, ay, litP));
    return peak;
  };
  /* a house with its eaves to the street: a steep tiled roof, a dormer, a chimney */
  const eaveHouse = (x0, w, floors, pl, roof) => {
    const fh = 6, wallH = floors * fh, top = B - wallH, rh = Math.round(w * 0.55) + 1;
    rect(x0, top, x0 + w - 1, B, M.PL, pl);
    for (let y = top - rh; y < top; y++) {
      const ins = Math.round((y - (top - rh)) === 0 ? 3 : 3 * (1 - (y - (top - rh)) / rh));
      for (let x = x0 - 1 + ins; x <= x0 + w - ins; x++) set(x, y, M.ROOF, roof);
      set(x0 - 1 + ins, y, M.SNOW); if (y === top - rh) for (let x = x0 - 1 + ins; x <= x0 + w - ins; x++) set(x, y, M.SNOW);
    }
    rect(x0 - 1, top - 1, x0 + w, top - 1, M.SNOWS);  // snow along the gutter
    const dxm = Math.floor(x0 + w / 2) - 1, dy = top - Math.round(rh * 0.6);
    rect(dxm - 1, dy - 1, dxm + 2, dy + 3, M.PL, pl); set(dxm - 1, dy - 2, M.SNOW); rect(dxm, dy - 3, dxm + 1, dy - 3, M.SNOW); set(dxm + 2, dy - 2, M.SNOW);
    rect(dxm, dy - 2, dxm + 1, dy - 2, M.ROOF, roof);
    win(dxm, dy, 2, 2, lit(dxm, dy, litP));
    const chx = x0 + w - 4;
    rect(chx, top - rh - 3, chx + 1, top - rh + 2, M.CHIM); rect(chx - 1, top - rh - 4, chx + 2, top - rh - 4, M.SNOW);
    if (!depth) out.chimneys.push([chx + 1, top - rh - 5]);
    for (let y = top; y <= B; y++) { set(x0, y, M.TIM); set(x0 + w - 1, y, M.TIM); }
    const cols = Math.max(2, Math.floor((w - 1) / 4)), gap = (w - cols * 2) / (cols + 1);
    for (let fl = 0; fl < floors; fl++) {
      const y0 = top + fl * fh + 1;
      rect(x0, y0 - 1, x0 + w - 1, y0 - 1, M.TIM);
      for (let ci = 0; ci < cols; ci++) {
        const wx = Math.round(x0 + gap * (ci + 1) + ci * 2);
        if (fl === floors - 1 && ci === 0) { rect(wx, y0 + 1, wx + 1, B, M.DOOR); continue; }
        win(wx, y0 + 1, 2, 3, fl === floors - 1 ? lampsOn(th) : lit(wx, y0, litP));
      }
    }
    return top - rh;
  };

  /* ---- the back row: taller roofs further off, a haze over them ---- */
  depth = 1;
  for (let x = -6; x < VW + 6;) {
    const w = 10 + Math.floor(R() * 6), fl = (big ? 3 : 2) + (R() < 0.4 ? 1 : 0), pl = Math.floor(R() * 6), rf = Math.floor(R() * 4);
    const r = R();
    if (r < 0.5) gableHouse(x, w | 1, fl, pl, rf); else if (r < 0.75) eaveHouse(x, w, fl, pl, rf); else stepHouse(x, w, fl, pl);
    x += w + (R() < 0.3 ? 2 : 0) - 2;
  }
  depth = 0;

  /* ---- the cathedral: twin towers and spires, a gabled front with its rose window ---- */
  const cat = Math.round(VW * 0.2), tw = 9, gp = 11;
  const tH = S(34), sH = S(22), nH = S(25);
  const lx0 = cat - (gp >> 1) - tw, rx0 = cat + (gp >> 1) + 1;
  // the front between the towers, up into a steep gable
  rect(lx0 + tw, B - nH, rx0 - 1, B, M.ST, 3);
  for (let y = B - nH - 7; y < B - nH; y++) { const hw = (y - (B - nH - 7)) / 7 * (gp / 2 + 0.5); for (let x = Math.floor(cat - hw); x <= Math.ceil(cat + hw); x++) set(x, y, M.ST, Math.abs(x + 0.5 - cat - 0.5) > hw - 1 ? 1 : 3); }
  for (let y = B - nH - 6; y < B - nH; y += 2) { const hw = (y - (B - nH - 7)) / 7 * (gp / 2 + 0.5); set(Math.floor(cat - hw) - 1, y, M.ST, 1); set(Math.ceil(cat + hw) + 1, y, M.ST, 2); }  // crockets
  set(cat, B - nH - 9, M.IRON); set(cat, B - nH - 8, M.IRON); set(cat - 1, B - nH - 8, M.IRON); set(cat + 1, B - nH - 8, M.IRON);
  // the rose window
  const ry = B - nH + 5, rr = 3.2;
  for (let y = ry - 4; y <= ry + 4; y++) for (let x = cat - 4; x <= cat + 4; x++) {
    const d = Math.hypot(x - cat, y - ry);
    if (d <= rr + 0.9 && d > rr - 0.1) set(x, y, M.ST, 2);  // its stone ring
    else if (d <= rr - 0.1) {
      const a = Math.atan2(y - ry, x - cat), spoke = Math.round((a + Math.PI) / (Math.PI / 4)) % 8;
      set(x, y, M.ROSE, d < 1 ? 3 : (spoke % 3));
      if (Math.abs(Math.sin(a * 4)) < 0.25 && d > 1) set(x, y, M.ST, 2);  // tracery
    }
  }
  // a tall lancet under it, the portal hidden by the houses
  for (let x = cat - 4; x <= cat + 4; x++) { set(x, ry + 6, M.ST, 1); set(x, ry + 7, M.ST, (x & 1) ? 2 : 3); set(x, ry + 8, M.ST, (x & 1) ? 2 : 3); }  // a gallery of niches
  // the great west door standing open, candlelight inside, under a pointed arch of stone
  rect(cat - 4, B - 10, cat + 4, B, M.ST, 1);
  rect(cat - 2, B - 7, cat + 2, B, M.SLIT); set(cat - 1, B - 8, M.SLIT); set(cat, B - 8, M.SLIT); set(cat + 1, B - 8, M.SLIT); set(cat, B - 9, M.SLIT);
  rect(cat - 3, B - 3, cat - 3, B, M.DOOR); rect(cat + 3, B - 3, cat + 3, B, M.DOOR);
  for (let y = B - 6; y <= B; y++) set(cat, y, M.TIM);
  // the towers
  for (const x0 of [lx0, rx0]) {
    rect(x0, B - tH, x0 + tw - 1, B, M.ST, 0);
    for (const yy of [B - Math.round(tH * 0.35), B - Math.round(tH * 0.7)]) rect(x0 - 1, yy, x0 + tw, yy, M.ST, 1);  // string courses
    // belfry: two tall lancets
    const by0 = B - tH + 3, by1 = B - Math.round(tH * 0.7) - 2;
    for (const lx of [x0 + 2, x0 + tw - 3]) { rect(lx, by0 + 1, lx, by1, M.LAN, 1); rect(lx - 1, by0 + 1, lx - 1, by1, M.ST, 2); }
    // a lower window, and the clock on the right spire
    const wy = B - Math.round(tH * 0.7) + 3;
    if (x0 === rx0) {
      const ccx = x0 + (tw >> 1), ccy = wy + 2;
      for (let y = ccy - 2; y <= ccy + 2; y++) for (let x = ccx - 2; x <= ccx + 2; x++) if (Math.hypot(x - ccx, y - ccy) < 2.6) set(x, y, M.CLOCK, Math.hypot(x - ccx, y - ccy) > 1.9 ? 1 : 0);
      set(ccx, ccy - 1, M.IRON); set(ccx, ccy, M.IRON); set(ccx + 1, ccy, M.IRON);
    } else { rect(x0 + 3, wy + 1, x0 + 3, wy + 5, M.LAN); rect(x0 + 5, wy + 1, x0 + 5, wy + 5, M.LAN); set(x0 + 4, wy, M.ST, 1); }
    rect(x0 + 4, B - Math.round(tH * 0.35) + 3, x0 + 4, B - 3, M.LAN);  // a tall lancet low in each spire
    for (let y = B - tH; y <= B; y++) { if (G[y * VW + x0] === M.ST) P[y * VW + x0] = 1; if (G[y * VW + x0 + tw - 1] === M.ST) P[y * VW + x0 + tw - 1] = 2; }  // buttress edges
    // parapet with corner pinnacles
    rect(x0 - 1, B - tH - 1, x0 + tw, B - tH - 1, M.ST, 1);
    for (const px of [x0 - 1, x0 + tw]) { rect(px, B - tH - 4, px, B - tH - 2, M.ST, 1); set(px, B - tH - 5, M.SPIRE); }
    // the spire: an octagon tapering to a finial, crockets up its edges
    const scx = x0 + (tw - 1) / 2, sb = B - tH - 2;
    for (let j = 0; j < sH; j++) {
      const hw = (tw / 2 - 0.5) * (1 - j / sH), y = sb - j;
      for (let x = Math.floor(scx - hw); x <= Math.ceil(scx + hw); x++) {
        const d = x + 0.5 - (scx + 0.5);
        if (Math.abs(d) > hw + 0.3) continue;
        set(x, y, M.SPIRE, d < -hw * 0.25 ? 2 : d > hw * 0.35 ? 1 : 0);
      }
      if (j % 4 === 2 && hw > 1) { set(Math.floor(scx - hw) - 1, y, M.SPIRE, 2); set(Math.ceil(scx + hw) + 1, y, M.SPIRE, 1); }
      if (j === Math.round(sH * 0.35)) { set(Math.round(scx), y, M.LAN, 1); }  // a lucarne
    }
    const fx = Math.round(scx), fy = sb - sH;
    rect(fx, fy - 3, fx, fy, M.IRON); set(fx - 1, fy - 2, M.IRON); set(fx + 1, fy - 2, M.IRON);
  }
  out.cathedral = { x: cat, top: B - tH - sH - 5 };

  /* ---- the front row of houses along the quay ---- */
  const treeX = Math.round(VW * 0.5);
  const carX = Math.round(VW * 0.855);
  for (let x = -4; x < VW + 4;) {
    const w = 11 + Math.floor(R() * 5), fl = 2 + (big && R() < 0.45 ? 1 : 0), pl = Math.floor(R() * 6), rf = Math.floor(R() * 4);
    // the cathedral's front stands clear above them
    if (x + w > lx0 - 1 && x < rx0 + tw + 1) { x = rx0 + tw + 1; continue; }
    const r = R();
    if (r < 0.55) gableHouse(x, w | 1, fl, pl, rf); else if (r < 0.8) eaveHouse(x, w, fl, pl, rf); else stepHouse(x, w, fl, pl);
    x += (w | 1) + (R() < 0.25 ? 3 : 0);
  }

  /* ---- the great tree on the quay, over the rink ---- */
  const gH = S(50), gW = Math.round(gH * 0.62) | 1, gTop = B - gH, tiers = 5;
  const tone = (x, y, tn) => set(x, y, M.FIR, tn);
  for (let y = gTop + 3; y <= B - 3; y++) {
    const p = (y - gTop - 3 + 0.5) / (B - 3 - gTop - 3), tp = (p * tiers) % 1, ti = Math.floor(p * tiers);
    const hw = (gW / 2) * (0.1 + 0.9 * p) * (0.55 + 0.45 * tp) + 0.5;
    const under = tp > 0.8 && y < B - 4;
    for (let x = Math.floor(treeX - hw); x <= Math.ceil(treeX + hw); x++) {
      const dx = x + 0.5 - (treeX + 0.5); if (Math.abs(dx) > hw) continue;
      if (Math.abs(dx) > hw - 1 && hashStr('gt' + x + ',' + y) % 3 === 0) continue;
      const l = -(dx / hw) * 0.7 + (0.5 - tp) * 0.5 + ((hashStr('g' + x + ':' + y) % 100) / 100 - 0.5) * 0.3;
      let tn = l > 0.55 ? 4 : l > 0.15 ? 3 : l > -0.3 ? 2 : 1;
      if (under) tn = Math.max(1, tn - 1);
      tone(x, y, tn);
      if (tp < 0.12 && ti > 0 && Math.abs(dx) < hw - 1.5 && bay(x, y) < 4 && dx < hw * 0.3) set(x, y, M.SNOW);
    }
    for (const [at, reach, dip] of [[0.3, 0.72, 1.2], [0.72, 0.95, 1.8]]) {
      const ty = gTop + 3 + (ti + at) / tiers * (B - 6 - gTop);
      if (y !== Math.round(ty)) continue;
      const hwT = (gW / 2) * (0.1 + 0.9 * ((ti + at + 0.25) / tiers)) * reach;
      const q0 = treeX - hwT;
      for (let x = Math.ceil(q0 + 1); x <= treeX + hwT - 1; x += 2) {
        const q = (x - q0) / (2 * hwT), yy = Math.round(ty + 4 * q * (1 - q) * (dip + ti * 0.45));
        out.lights.push([x, yy, (x + ti * 3 + (at > 0.5 ? 1 : 0)) & 3]);
      }
    }
  }
  for (const [x, y] of out.lights) set(x, y, M.GL);
  for (let i = 0; i < 26; i++) {
    const y = gTop + 8 + Math.floor(R() * (gH - 12)), p = (y - gTop - 3) / (gH - 6), hw = gW / 2 * (0.1 + 0.9 * p) * 0.7;
    const x = Math.round(treeX + (R() * 2 - 1) * hw);
    if (get(x, y) === M.FIR) set(x, y, M.GL, 8 + (i % 3));
  }
  rect(treeX - 1, B - 3, treeX + 1, B, M.WOOD, 0);
  const star = [[0, -3], [0, -2], [-1, -1], [0, -1], [1, -1], [-3, 0], [-2, 0], [-1, 0], [0, 0], [1, 0], [2, 0], [3, 0], [-1, 1], [0, 1], [1, 1], [-1, 2], [1, 2], [0, 4], [0, 3]];
  for (const [dx, dy] of star) set(treeX + dx, gTop + 1 + dy, M.STAR, dx === 0 && dy === 0 ? 1 : 0);
  out.tree = { x: treeX, top: gTop - 2, star: [treeX, gTop + 1] };

  /* ---- the quay: a snowy top, a stone wall, lamps along it ---- */
  for (let x = 0; x < VW; x++) { set(x, B + 1, M.QUAY, 2); set(x, B + 2, M.QUAY, 0); set(x, B + 3, M.QUAY, 1); }
  const tw2 = 9, tx = Math.round(VW * 0.27), D0 = B - 2, PB = SB, rampEnd = tx + tw2 + (PB - D0);
  const lamp = (x, y) => {  // a lantern on a post, its foot at y
    rect(x, y - 2, x, y, M.IRON); set(x - 1, y - 3, M.IRON); set(x, y - 3, M.LAMP); set(x + 1, y - 3, M.IRON);
    set(x, y - 4, M.LAMP, 1); rect(x - 1, y - 5, x + 1, y - 5, M.IRON); set(x, y - 6, M.SNOW); set(x - 1, y - 6, M.SNOW, 1);
  };
  for (let x = rampEnd + 8; x < VW - 3; x += 26 + (hashStr('ql' + x) % 9)) if (Math.abs(x - treeX) > 11) lamp(x, B);
  // stone steps down from the quay onto the ice, either side of the rink
  for (const sx of [Math.round(VW * 0.4), Math.round(VW * 0.6)]) for (let s = 1; s <= 3; s++) { set(sx + s, B + s, M.QUAY, 2); set(sx + s, B + s + 1, M.QUAY, 3); }

  /* ---- the stone bridge: arches standing on the ice, lanterns over the piers and dark statues
   *      over the arches, a gatehouse at its end and a stair down onto the ice ---- */
  obj = PB;
  const pw = 4, span = Math.max(10, Math.round(9 + 5 * f)), crown = D0 + 3;
  const arches = [];
  for (let aR = tx - 2 - pw; aR > -span; aR -= span + pw) arches.push([aR - span + 1, aR]);
  const openTop = x => {  // the arch's soffit over column x, or null where a pier stands
    for (const [a0, a1] of arches) if (x >= a0 && x <= a1) {
      const c = (a0 + a1 + 1) / 2, q = (x + 0.5 - c) / (span / 2);
      return { yTop: PB - 1 - Math.round((PB - 1 - crown) * Math.sqrt(Math.max(0, 1 - q * q))), a0, a1 };
    }
    return null;
  };
  for (let x = -2; x < tx; x++) {
    const o = openTop(x);
    for (let y = D0; y <= PB; y++) {
      const starling = o && ((x === o.a0 || x === o.a1) && y >= PB - 1 || (x === o.a0 + 1 || x === o.a1 - 1) && y === PB);
      if (o && y > o.yTop + 1 && !starling) continue;  // open under the arch
      let p = y === D0 ? 3 : y === D0 + 2 ? 1 : 0;
      if (o && y === o.yTop + 1 && !starling) p = 2;                 // the vault's underside, in shadow
      else if (o && y === o.yTop && !starling) p = (x & 1) ? 1 : 5;  // the voussoirs round the arch
      if (starling) p = 6;
      set(x, y, M.BST, p);
    }
    if (x % 7) set(x, D0 - 1, M.SNOW, x % 3 === 0 ? 1 : 0);  // snow along the parapet
    if (o && (x === o.a0 || x === o.a1)) set(x, PB - 2, M.SNOW);
  }
  // lanterns over the piers, statues over the arches
  for (const [a0] of arches) if (a0 - 2 > 0) lamp(a0 - 2, D0 - 1);
  for (const [a0, a1] of arches) {
    const x = Math.round((a0 + a1) / 2);
    if (x < 2) continue;
    rect(x - 1, D0 - 2, x + 1, D0 - 1, M.BST, 1); set(x, D0 - 2, M.BST, 3);
    rect(x - 1, D0 - 5, x + 1, D0 - 5, M.STAT); rect(x, D0 - 4, x + 1, D0 - 3, M.STAT); set(x - 1, D0 - 3, M.STAT, 1);
    set(x, D0 - 6, M.STAT); set(x + ((a0 >> 1) & 1 ? 2 : -2), D0 - 6, M.STAT, 1); set(x + ((a0 >> 1) & 1 ? 2 : -2), D0 - 7, M.STAT, 1);
    set(x, D0 - 7, M.SNOW); set(x - 1, D0 - 6, M.SNOW, 1);
  }
  // the gatehouse, on a broad pier of its own
  const tTop = D0 - Math.max(12, S(22));
  rect(tx, tTop, tx + tw2 - 1, PB, M.BST, 7);
  rect(tx - 1, tTop, tx + tw2, tTop, M.BST, 3); rect(tx - 1, tTop + 1, tx + tw2, tTop + 1, M.BST, 1);
  rect(tx - 1, D0 + 2, tx + tw2, D0 + 2, M.BST, 1);
  rect(tx - 1, PB - 2, tx + tw2, PB, M.BST, 0); rect(tx - 1, PB - 3, tx + tw2, PB - 3, M.SNOW);
  const wy = tTop + 3;
  for (const lx of [tx + 2, tx + tw2 - 3]) { rect(lx, wy + 1, lx, wy + 4, M.LAN); set(lx, wy, M.BST, 1); }
  rect(tx + 3, D0 - 4, tx + tw2 - 4, D0 + 1, M.SLIT); set(tx + 4, D0 - 5, M.SLIT);  // the gateway, lit within
  const rh = Math.max(8, S(14));
  for (let j = 0; j < rh; j++) {
    const hw = (tw2 / 2 + 0.5) * Math.pow(1 - j / rh, 0.9), y = tTop - 1 - j;
    for (let x = Math.floor(tx + tw2 / 2 - hw); x <= Math.ceil(tx + tw2 / 2 - 1 + hw); x++) set(x, y, M.ROOF, 1);
  }
  const mid = tx + (tw2 >> 1);
  rect(mid, tTop - rh - 3, mid, tTop - rh, M.IRON); set(mid - 1, tTop - rh - 2, M.IRON); set(mid + 1, tTop - rh - 2, M.IRON);
  for (const px of [tx - 1, tx + tw2]) { rect(px, tTop - 4, px, tTop - 1, M.SPIRE, px < tx ? 2 : 1); set(px, tTop - 5, M.IRON); set(px, tTop - 6, M.IRON); }
  // the stair down onto the ice
  for (let x = tx + tw2 + 1; x <= rampEnd; x++) {
    const top = D0 + (x - tx - tw2 - 1);
    rect(x, top, x, PB, M.BST, x === rampEnd ? 2 : 0);
    set(x, top, M.SNOW);
  }
  out.bridge = { x0: 0, x1: rampEnd, tx, tw: tw2, PB, D0 };

  /* ---- strings of lights from the great tree's crown out to two poles on the ice, over the rink ---- */
  obj = SB + 1;
  for (const [dxq, side] of [[-0.14, -1], [0.14, 1]]) {
    const px = Math.round(treeX + VW * dxq), top = SB + 1 - Math.max(9, S(12));
    rect(px, top, px, SB + 1, M.IRON); set(px, top - 1, M.LAMP); set(px - 1, top, M.IRON); set(px + 1, top, M.IRON); set(px, top - 2, M.SNOW);
    set(px, SB + 1, M.WOOD, 2); set(px - 1, SB + 1, M.WOOD, 0); set(px + 1, SB + 1, M.WOOD, 0);
    for (const [fy, sag] of [[0.34, 3], [0.55, 4]]) {
      const x0 = treeX + side * Math.round(gW * (0.12 + fy * 0.45)), y0 = Math.round(gTop + gH * fy), x1 = px, y1 = top + 1;
      const n = Math.abs(x1 - x0);
      for (let s2 = 1; s2 < n; s2++) {
        const q = s2 / n, x = x0 + side * s2, y = Math.round(y0 + (y1 - y0) * q + sag * 4 * q * (1 - q));
        const m = get(x, y); if (m === M.FIR || m === M.GL || m === M.STAR) continue;
        if (s2 % 2 === 0) set(x, y, M.BULB, s2 % 4 === 0 ? 1 : 0); else set(x, y, M.IRON, 1);
      }
    }
  }
  obj = 0;

  /* ---- the carousel out on the ice (drawn live through a hole: its shape is fixed, its content turns) ---- */
  const CB = Math.min(VE - 2, SB + 1);
  obj = CB;
  const cw = 25, ch = S(23), cTop = CB - ch;
  const car = { x: carX, top: cTop, w: cw, h: ch, pts: [], base: CB };
  const cone = Math.round(ch * 0.44), val = 2, plat = 2;
  for (let y = cTop; y <= CB; y++) {
    const j = y - cTop;
    let hw;
    if (j < 3) hw = 0.6;
    else if (j < cone) hw = 1 + (cw / 2 - 1) * Math.pow((j - 3) / (cone - 3), 0.8);
    else if (j < cone + val) hw = cw / 2;
    else if (j > CB - cTop - plat) hw = cw / 2 + 0.5;
    else hw = cw / 2 - 1;
    for (let x = Math.floor(carX - hw); x <= Math.ceil(carX + hw); x++) if (Math.abs(x + 0.5 - (carX + 0.5)) <= hw + 0.01) { set(x, y, M.HOLE); car.pts.push([x, y]); }
  }
  car.cone = cone; car.val = val; car.plat = plat;
  set(carX + 1, cTop, M.SIGN, 0); set(carX + 2, cTop, M.SIGN, 0); set(carX + 1, cTop + 1, M.SIGN, 0);
  out.carousel = car;

  /* ---- the market stalls on the ice, and their lamp strings ---- */
  obj = SB;
  const sh = Math.max(13, S(15)), stalls = [];
  for (let x = Math.round(VW * 0.625); x < VW - 8;) {
    const w = 11 + (hashStr('sw' + x) % 3), cx = x + w / 2;
    const blocked = Math.abs(cx - carX) < cw / 2 + w / 2 + 2;
    if (!blocked) stalls.push({ x0: x, w, cx });
    x += blocked ? 3 : w + 4 + (hashStr('sg' + x) % 5);
  }
  stalls.forEach((s, i) => {
    const { x0, w } = s, x1 = x0 + w - 1, top = SB - sh, rh = 4;
    const awn = i % 3 === 1 ? 2 : 1;
    for (let y = top; y < top + rh; y++) {
      const hw = 1 + (y - top) / (rh - 1) * (w / 2);
      for (let x = Math.floor(s.cx - hw); x <= Math.ceil(s.cx + hw - 1); x++) {
        if (y === top + rh - 1) set(x, y, M.WOOD, 2);
        else set(x, y, M.SNOW, x + 0.5 > s.cx + 0.5 ? 1 : 2);
      }
    }
    set(Math.floor(s.cx - 1), top - 1, M.SNOW); set(Math.floor(s.cx), top - 1, M.SNOW, 1);
    rect(Math.floor(s.cx) - 1, top + 1, Math.floor(s.cx), top + 2, M.SIGN, i % 4);
    const ay = top + rh;
    for (let x = x0 - 1; x <= x1 + 1; x++) {
      const stripe = ((x - x0 + 1) >> 1) & 1;
      set(x, ay, M.AWN, stripe ? 0 : awn);
      if (((x - x0 + 1) & 1) === 0 || x === x0 - 1 || x === x1 + 1) set(x, ay + 1, M.AWN, stripe ? 0 : awn);
    }
    const oy0 = ay + 1, oy1 = SB - 4;
    rect(x0, oy0 + 1, x1, oy1, M.SLIT, 0);
    for (let x = x0 + 1; x < x1; x++) {
      const g = hashStr('g' + x + ',' + i) % 5;
      if (g < 3) set(x, oy1, M.GOODS, g === 2 ? 3 : g); if (g === 0) set(x, oy1 - 1, M.GOODS, 1);
    }
    for (let x = x0 + 1; x < x1; x += 3) set(x, oy0 + 1, M.GOODS, 2);
    for (let x = x0; x <= x1; x += 2) set(x, ay - 1, M.BULB, 0);
    rect(x0 - 1, SB - 3, x1 + 1, SB - 3, M.WOOD, 2);
    rect(x0, SB - 2, x1, SB, M.WOOD, 0);
    for (let y = oy0; y <= SB; y++) { set(x0 - 1, y, M.WOOD, 1); set(x1 + 1, y, M.WOOD, 1); }
    s.top = top; s.ay = ay;
    if (i % 2 === 0) out.chimneys.push([Math.round(s.cx) + 1, oy0, 'steam']);
  });
  for (let i = 0; i + 1 < stalls.length; i++) {
    const a = stalls[i], b = stalls[i + 1];
    if (b.x0 - (a.x0 + a.w) > 22) continue;
    const xa = Math.round(a.cx), xb = Math.round(b.cx), ya = a.top, yb = b.top, sagD = 4;
    for (let x = xa + 1; x < xb; x++) {
      const q = (x - xa) / (xb - xa), y = Math.round(ya + (yb - ya) * q + sagD * 4 * q * (1 - q));
      if (get(x, y) === M.SNOW) continue;
      if ((x - xa) % 3 === 0) set(x, y, M.BULB, 1); else set(x, y, M.IRON, 1);
    }
  }
  obj = 0;
  out.stalls = stalls;
  return { G, P, D, OB, VW, VH, get, out };
}

/* paints the plan: returns the canvas and the holes to be drawn live */
function paintTown(env, T) {
  const th = env.theme, C = colours(th), plan = townPlan(T, th), { G, P, D, VW, VH, get } = plan;
  const [cv, g] = layer(VW, VH), img = g.createImageData(VW, VH), d = img.data;
  const on = lampsOn(th);
  const rim = RIMC[th.xh], rimA = th.xh === 'day' ? 0 : th.xh === 'night' ? 0.28 : 0.4;
  const hazeC = mix(hex(th.sky[th.sky.length - 1]), hex(th.sky[th.sky.length - 2]), 0.3);
  const empty = (x, y) => { const m = get(x, y); return !m || m === M.IRON; };
  const holes = [];
  for (let y = 0; y < VH; y++) for (let x = 0; x < VW; x++) {
    const i = y * VW + x, m = G[i]; if (!m) continue;
    if (m === M.HOLE || (m === M.GL && on && P[i] < 8)) { holes.push(i); continue; }
    const p = P[i], L = empty(x - 1, y), Tp = empty(x, y - 1);
    let c;
    switch (m) {
      case M.PL: {
        c = C.plaster[p];
        if (!Tp && get(x, y - 1) === M.ROOF) c = mix(c, C.timber, 0.35);  // under the verge
        break;
      }
      case M.BRICK: c = (y % 2 === 0) || ((x + (y >> 1) * 2) % 4 === 0) ? mix(C.brick, C.timber, 0.35) : C.brick; if (L) c = C.brickL; break;
      case M.TIM: c = C.timber; break;
      case M.ROOF: { const r = C.roof[p]; c = (y & 1) || ((x + (y >> 1) * 3) % 4 === 0) ? mix(r, C.timber, 0.3) : r; if (Tp) c = C.snow; else if (empty(x, y - 2) && (x + y) & 1) c = C.snowS; break; }
      case M.SNOW: c = p === 1 ? (Tp && (x & 1) ? C.snow : mix(C.snow, C.snowS, 0.6)) : p === 2 ? (bay(x, y) < 3 ? mix(C.snow, C.snowS, 0.4) : C.snow) : L || Tp ? C.snow : C.snowS; if (th.xh === 'dusk' && L) c = mix(C.snow, rim, 0.3); break;
      case M.SNOWS: c = (x + y) & 1 ? C.snow : C.snowS; break;
      case M.WL: {
        if (!on) { c = C.winD; break; }
        const e = get(x - 1, y) !== M.WL || get(x, y - 1) !== M.WL;
        c = e ? LIT.edge : LIT.core;
        if (th.xh === 'dawn') c = mix(c, C.winD, 0.25);
        break;
      }
      case M.WD: c = p === 1 ? C.winR : C.winD; break;
      case M.CHIM: c = (y & 1) ? mix(C.brick, C.timber, 0.4) : C.brick; if (L) c = C.brickL; break;
      case M.DOOR: c = (x & 1) ? C.door : mix(C.door, C.timber, 0.5); break;
      case M.ST: {
        c = p === 1 ? C.stoneL : p === 2 ? C.stoneS : p === 3 ? mix(C.stone, C.stoneS, 0.55) : C.stone;
        if (p === 3 && (y % 3 === 0)) c = mix(C.stoneJ, C.stoneS, 0.6);
        if (p === 0 && ((y % 3 === 0) || ((x + (Math.floor(y / 3) & 1) * 2) % 4 === 0))) c = C.stoneJ;
        if (L) c = C.stoneL; else if (empty(x + 1, y)) c = C.stoneS;
        break;
      }
      case M.SPIRE: c = p === 2 ? C.spireL : p === 1 ? C.spireS : C.spire; if ((y & 1) && p === 0) c = mix(C.spire, C.spireS, 0.5); break;
      case M.ROSE: c = on ? GLASS[p] : mix(C.winD, GLASS[p], 0.3); if (on && th.xh === 'dawn') c = mix(c, C.winD, 0.3); break;
      case M.LAN: c = on ? (p === 1 ? LIT.deep : mix(LIT.edge, GLASS[2], (y & 1) ? 0.4 : 0.15)) : C.winD; break;
      case M.CLOCK: c = p ? C.stoneS : (on ? mix(C.clock, LIT.core, 0.5) : C.clock); break;
      case M.IRON: c = p === 1 ? mix(C.iron, C.wood, 0.5) : C.iron; break;
      case M.FIR: c = C.gfir[p]; if (L && p >= 2 && rim) c = mix(c, rim, 0.3); break;
      case M.GL: {
        if (p >= 8) { c = [hex('#c8283a'), hex('#d0d8e8'), hex('#2e5ad8')][p - 8]; if (!on) c = mix(c, C.gfir[1], 0.3); }
        else c = TREE_LIGHTS_DIM[p];
        break;
      }
      case M.STAR: c = p ? hex('#ffffff') : hex(on ? '#dce8ff' : '#c8d0dc'); break;
      case M.WOOD: c = p === 2 ? C.woodL : p === 1 ? ((x + (y >> 1)) % 3 === 0 ? C.woodS : C.wood) : ((x & 1) ? C.wood : C.woodS); break;
      case M.AWN: c = p === 2 ? C.awnG : p === 1 ? C.awnR : C.awnW; if (on && get(x, y + 1) !== M.AWN) c = mix(c, LIT.core, 0.25); break;
      case M.SLIT: { const deep = y > 0 && get(x, y - 1) !== M.SLIT; c = on ? (deep ? LIT.deep : bay(x, y) < 8 ? LIT.core : LIT.edge) : C.slitOff; break; }
      case M.GOODS: c = p === 3 ? hex(on ? '#4a8a5a' : '#2a4a34') : p === 2 ? hex(on ? '#a8502c' : '#6a3a28') : p === 1 ? (on ? hex('#c83040') : C.goods) : (on ? hex('#6a3424') : C.goods); break;
      case M.BULB: c = on ? (p === 1 ? hex('#fff0b8') : ((x >> 1) & 1 ? hex('#ffe08a') : hex('#ffb870'))) : mix(C.iron, C.snow, 0.3); break;
      case M.SIGN: c = [hex('#c02838'), hex('#1e5a3a'), hex('#2a3e7a'), hex('#6a2a4a')][p]; if (!on) c = mix(c, C.timber, 0.3); break;
      case M.QUAY: {
        if (p === 2) { c = bay(x, y) < 11 ? C.snow : C.snowS; break; }
        if (p === 3) { c = C.stoneS; break; }
        const joint = (x + (y & 1) * 3) % 6 === 0;
        c = p === 0 ? (joint ? C.stoneJ : C.stone) : (joint ? C.stoneS : mix(C.stoneS, C.stoneJ, 0.5));
        break;
      }
      case M.BST: {
        if (p === 1 || p === 3) { c = p === 3 && (x & 1) ? mix(C.stoneL, C.stone, 0.4) : C.stoneL; break; }
        if (p === 2) { c = mix(C.stoneS, C.iron, 0.45); break; }
        if (p === 5) { c = mix(C.stoneJ, C.stoneS, 0.5); break; }
        if (p === 6) { c = x & 1 ? C.stoneS : mix(C.stone, C.stoneS, 0.5); break; }
        if (p === 7) {  // the gatehouse's old, darkened stone
          c = (y % 3 === 0) || ((x + Math.floor(y / 3) * 3) % 4 === 0) ? mix(C.stoneS, C.iron, 0.45) : mix(C.stone, C.stoneS, 0.6);
          if (L) c = C.stone; else if (empty(x + 1, y)) c = mix(C.stoneS, C.iron, 0.3);
          break;
        }
        c = (y % 3 === 0) || ((x + Math.floor(y / 3) * 3) % 5 === 0) ? mix(C.stoneJ, C.stoneS, 0.4) : ((x * 7 + y * 3) % 11 === 0 ? mix(C.stone, C.stoneL, 0.5) : C.stone);
        if (empty(x + 1, y)) c = C.stoneS;
        break;
      }
      case M.LAMP: c = on ? (p === 1 ? LIT.edge : LIT.core) : mix(C.iron, C.snow, 0.35); break;
      case M.STAT: c = mix(C.iron, C.timber, 0.55); if (p) c = C.iron; break;
      default: c = C.timber;
    }
    if (rim && rimA && L && m !== M.WL && m !== M.BULB && m !== M.GL && m !== M.STAR && m !== M.SLIT && m !== M.LAMP) c = mix(c, rim, rimA);
    if (D[i]) {  // the back row sits in the evening haze, its lit windows still bright
      if (m === M.WL && on) c = mix(c, LIT.deep, 0.25);
      else c = mix(c, hazeC, th.xh === 'day' ? 0.4 : 0.32);
    }
    const j = i * 4; d[j] = c[0]; d[j + 1] = c[1]; d[j + 2] = c[2]; d[j + 3] = 255;
  }
  // lit windows spill a little warm light onto the plaster round them: two dithered steps
  if (on) for (let y = 1; y < VH - 1; y++) for (let x = 1; x < VW - 1; x++) {
    const i = y * VW + x, m = G[i];
    if (m !== M.PL && m !== M.BRICK && m !== M.TIM && m !== M.SNOWS && m !== M.WOOD && m !== M.ST && m !== M.BST && m !== M.QUAY && m !== M.SNOW) continue;
    let near = 9;
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) { const q = G[(y + dy) * VW + x + dx]; if (q === M.WL || q === M.SLIT || q === M.LAMP) near = Math.min(near, Math.max(Math.abs(dx), Math.abs(dy))); }
    if (near > 2 || bay(x, y) >= (near === 1 ? 9 : 4)) continue;
    const j = i * 4, c = mix([d[j], d[j + 1], d[j + 2]], LIT.spill, D[i] ? 0.35 : 0.55);
    d[j] = c[0]; d[j + 1] = c[1]; d[j + 2] = c[2];
  }
  const car = carouselFrames(env, T, plan.out.carousel, C);
  paintIce(env, T, plan, d, car);
  g.putImageData(img, 0, 0);
  return { cv, plan, holes, C, car };
}

/* the frozen river between the quay and the forest: dithered bands from the dark water under
 * the quay to the pale near ice, the town and the market mirrored in it (their lights as long
 * warm streaks), slanting gloss, cracks, drifts of snow, skate trails round the rink, and a
 * snowy near bank */
function paintIce(env, T, plan, d, car) {
  const th = env.theme, { G, P, OB, VW, VH } = plan, { I0, SB } = plan.out, on = lampsOn(th), IP = icePal(th);
  const sky = hex(th.sky[th.sky.length - 2]), snowA = hex(th.g0), snowB = mix(hex(th.g0), hex(th.g1), 0.45);
  const foot = new Int16Array(VW);
  for (let i = 0; i < VW * VH; i++) if (OB[i]) { const x = i % VW; foot[x] = Math.max(foot[x], OB[i]); }
  const f0 = car.frames[0], fw = f0.width, fd = f0.getContext('2d').getImageData(0, 0, fw, f0.height).data;
  const src = (x, y) => {  // what the ice mirrors from (x, y): its colour, and whether it shines
    if (y < 0) return [sky, false];
    const i = y * VW + x, m = G[i], j = i * 4;
    if (m === M.HOLE) { const q = ((y - car.y0) * fw + (x - car.x0)) * 4; return [[fd[q], fd[q + 1], fd[q + 2]], on]; }
    if (m === M.GL && !d[j + 3]) return [TREE_LIGHTS[P[i] & 3], on];
    if (!d[j + 3]) return [sky, false];
    return [[d[j], d[j + 1], d[j + 2]], on && SHINES.has(m) && !(m === M.GL && P[i] >= 8)];
  };
  // the near bank: a wavy lip of snow the ice runs up to
  const lip = x => VH - 3 - Math.round(1 + Math.sin(x * 0.09) + Math.sin(x * 0.23 + 1) * 0.6);
  const n = VH - I0, midR = I0 + Math.round(n * 0.5);
  const L1 = mix(IP.far, IP.near, 0.5);
  for (let y = I0; y < VH; y++) for (let x = 0; x < VW; x++) {
    const i = y * VW + x; if (G[i]) continue;
    const j = i * 4, yb = lip(x);
    let c;
    if (y > yb) c = bay(x, y) < 5 ? snowB : snowA;
    else {
      // three flat bands: the shadow under the quay, the ice, the paler ice toward the near bank
      c = y < I0 + 2 || (y === I0 + 2 && bay(x, y) < 8) ? IP.far : y < midR || (y === midR && bay(x, y) < 8) ? L1 : IP.near;
      const fb = foot[x] && foot[x] < y ? foot[x] : 0, ml = fb || I0 - 1, dist = y - ml;
      const [sc, shine] = src(x, 2 * ml + 1 - y);
      if (shine) { if (dist <= 3 || ((x + (hashStr('st' + x) & 1)) & 1) === 0 && (y + x * 3) % (9 - Math.min(5, dist >> 1)) !== 0) c = mix(c, sc, dist <= 3 ? 0.78 : dist <= 6 ? 0.6 : 0.45); }
      else {
        c = mix(c, sc, Math.max(0.07, 0.2 - dist * 0.012));
        // a light's reflection runs on down the ice as a long streak
        const [s2, sh2] = src(x, Math.round(ml + 1 - dist * 0.45));
        if (sh2 && hashStr('ls' + x) % 3 === 0 && (y + x) % 5 !== 0 && dist < 12) c = mix(c, s2, 0.5 - dist * 0.025);
      }
      if (y === I0 && hashStr('qd' + x) % 3 === 0) c = mix(snowA, IP.far, 0.3);  // snow blown against the quay
      else if (fb && y === fb + 1 && bay(x, y) < 9) c = snowB;                  // and round the feet of what stands on the ice
      if (y === yb) c = mix(c, IP.crackD, 0.3);
    }
    d[j] = c[0]; d[j + 1] = c[1]; d[j + 2] = c[2]; d[j + 3] = 255;
  }
  const iceAt = (x, y) => x >= 0 && x < VW && y > I0 && y < lip(x) && !G[y * VW + x];
  const tint = (x, y, c, a) => { if (!iceAt(x, y)) return; const j = (y * VW + x) * 4, o = mix([d[j], d[j + 1], d[j + 2]], c, a); d[j] = o[0]; d[j + 1] = o[1]; d[j + 2] = o[2]; };
  // skate trails round the rink in front of the great tree
  const rinkY = Math.round((SB + Math.min(T.VL, VH - 4)) / 2);
  [[0.5, 0.11, 2.2, 0], [0.47, 0.07, 1.5, 1], [0.54, 0.08, 1.8, 2]].forEach(([cq, rq, ry, s]) => {
    const cx = VW * cq, rx = VW * rq, steps = Math.round(rx * 7);
    for (let k = 0; k < steps; k++) {
      if ((k + s) % 5 === 0) continue;
      const a = k / steps * Math.PI * 2, x = Math.round(cx + Math.cos(a) * rx), y = Math.round(rinkY + s - 1 + Math.sin(a) * ry);
      tint(x, y, IP.trail, 0.55);
    }
  });
  const R = rng(77), spot = () => [Math.floor(R() * VW), I0 + 3 + Math.floor(R() * Math.max(1, VH - I0 - 7))];
  // drifts of snow lying loose on the ice
  for (let k = 0; k < Math.round(VW / 30); k++) {
    const [cx, cy] = spot(), rx = 2 + R() * 4;
    for (let y = cy - 1; y <= cy + 1; y++) for (let x = Math.floor(cx - rx); x <= cx + rx; x++) {
      const q = ((x - cx) / rx) ** 2 + (y - cy) ** 2 * 0.8;
      if (q < 1 && (q < 0.45 || bay(x, y) < 8)) tint(x, y, y > cy || q > 0.45 ? snowB : snowA, 1);
    }
  }
  // the gloss: little pairs of slanting highlights
  for (let k = 0; k < Math.round(VW / 16); k++) {
    const [x0, y0] = spot(), len = 3 + Math.floor(R() * 4);
    for (let s = 0; s < len; s++) tint(x0 + s, y0 - (s >> 1), IP.gloss, s === 0 || s === len - 1 ? 0.45 : 0.75);
    if (len > 4) for (let s = 0; s < len - 3; s++) tint(x0 + 3 + s, y0 + 1 - (s >> 1), IP.gloss, 0.5);
  }
  // cracks, a light line with its dark lip
  for (let c = 0; c < Math.round(VW / 45); c++) {
    let [x, y] = spot();
    const len = 5 + Math.floor(R() * 9), dir = R() < 0.5 ? -1 : 1;
    for (let s = 0; s < len; s++) {
      tint(x, y, IP.crack, 0.7); tint(x, y + 1, IP.crackD, 0.35);
      x += dir; if (R() < 0.3) y += R() < 0.5 ? -1 : 1;
    }
  }
}

/* ---------- the carousel's frames: the canopy's panels turn, the horses rise and fall ---------- */
const CAR_FRAMES = 24;
// a horse facing right: X body, H head and mane, S saddle, L legs
const HORSE = ['....HH', 'T..HH.', 'XXSXX.', 'L...L.'];
function carouselFrames(env, T, car, C) {
  const th = env.theme, on = lampsOn(th), frames = [];
  const x0 = Math.floor(car.x - car.w / 2) - 1, y0 = car.top, w = car.w + 3, h = car.h + 1;
  const inside = new Set(car.pts.map(([x, y]) => (y - y0) * w + (x - x0)));
  const red = C.awnR, cream = mix(C.awnW, hex('#fff4e0'), on ? 0.3 : 0), green = C.awnG, rimC = RIMC[th.xh];
  const bulbOn = hex('#fff0b8'), bulbWarm = hex('#ffc47a');
  const hC = { T: hex(on ? '#b8a8a0' : '#9a908a'), X: hex(on ? '#f2ece4' : '#e4e0d8'), H: hex(on ? '#d8d0c8' : '#c8c4bc'), S: red, L: hex(on ? '#a89890' : '#8a8480') };
  const yTop = car.top + car.cone + car.val, yBot = car.top + car.h - car.plat;
  for (let f = 0; f < CAR_FRAMES; f++) {
    const [cv, g] = layer(w, h), ph = f / CAR_FRAMES;
    const P = (c, x, y) => { const i = (y - y0) * w + (x - x0); if (!inside.has(i)) return; g.fillStyle = rgb(c); g.fillRect(x - x0, y - y0, 1, 1); };
    for (const [x, y] of car.pts) {
      const j = y - car.top, dx = x + 0.5 - (car.x + 0.5);
      let c;
      if (j < 3) c = C.iron;
      else if (j < car.cone) {  // the canopy: red and cream panels converging on the top, turning
        const hw = 1 + (car.w / 2 - 1) * Math.pow((j - 3) / (car.cone - 3), 0.8);
        const a = Math.asin(Math.max(-1, Math.min(1, dx / (hw + 0.5))));
        const s = Math.floor((a / Math.PI + 0.5) * 6 + ph * 3) & 1;
        c = s ? red : cream;
        if (dx > hw * 0.5) c = mix(c, C.timber, 0.35);
        else if (dx < -hw * 0.55 && rimC) c = mix(c, rimC, 0.3);
        if (j === car.cone - 1 || (Math.abs(dx) > hw - 1 && j > 4)) c = mix(c, C.timber, 0.2);
      } else if (j < car.cone + car.val) {  // the valance: scallops and chasing bulbs
        const a = Math.asin(Math.max(-1, Math.min(1, dx / (car.w / 2 + 0.5))));
        const s = Math.floor((a / Math.PI + 0.5) * 12 + ph * 6) & 1;
        if (j === car.cone) c = on && ((x + f) % 3 === 0) ? bulbOn : green;
        else c = s ? green : mix(green, C.timber, 0.5);
      } else if (j > car.h - car.plat) {  // the platform, bulbs chasing round its rim
        c = j === car.h - car.plat + 1 ? (on && ((x - f) % 4 === 0) ? bulbWarm : C.woodL) : C.wood;
      } else {  // inside: the lit drum with its mirrors, warm dusk behind
        const q = (y - yTop) / Math.max(1, yBot - yTop);
        c = on ? mix(hex('#b4583a'), hex('#5a2a2a'), q) : mix(C.woodS, C.wood, q);
        if (Math.abs(dx) < 2.5) c = on ? ((y & 1) ? LIT.core : LIT.edge) : C.woodL;  // the drum, lit mirrors
        if (Math.abs(dx) >= car.w / 2 - 1.5) c = C.woodS;
      }
      P(c, x, y);
    }
    // the horses on their brass-less silver poles: going round, rising and falling
    const list = [];
    for (let n = 0; n < 6; n++) {
      const a = (n / 6 + ph / 6) * Math.PI * 2, z = Math.cos(a), xx = car.x + Math.sin(a) * (car.w / 2 - 4);
      list.push({ a, z, xx, n });
    }
    list.sort((p, q) => p.z - q.z);
    for (const hs of list) {
      if (hs.z < -0.15) continue;
      const bob = Math.round(Math.sin(hs.a * 3 + hs.n * 2)), hx = Math.round(hs.xx), hy = Math.round(yTop + (yBot - yTop) / 2 - 2 + bob);
      for (let y = yTop; y < yBot; y++) P(on ? hex('#dce0ea') : hex('#9aa0aa'), hx, y);
      const dir = Math.cos(hs.a) >= 0 ? -1 : 1;  // the front ones run left, as it turns
      HORSE.forEach((row, ry) => { for (let rx = 0; rx < 6; rx++) { const ch = row[rx]; if (ch === '.') continue; P(hC[ch], hx + (dir > 0 ? rx - 2 : 2 - rx), hy + ry); } });
    }
    frames.push(cv);
  }
  return { frames, x0, y0 };
}

/* ---------- where it all is: worked out once per scene ---------- */
function town(env) {
  if (env.market) return env.market;
  const T = townAt(env);
  env.market = T;
  T.paint = paintTown(env, T);
  // the highest roof over each column, for whatever hangs in the sky above the town
  const { G, VW, VH } = T.paint.plan;
  T.roofAt = new Int16Array(VW).fill(VH);
  for (let x = 0; x < VW; x++) for (let y = 0; y < VH; y++) if (G[y * VW + x]) { T.roofAt[x] = y; break; }
  return T;
}

/* ---------- the sky: the town's glow over its roofs, the moon, stars, thin lit cloud ---------- */
const MOONS = {
  dusk: { x: 0.9, y: 0.2, r: 8, c: '#f4dcd4', lo: '#c8a4b4', glow: '#8a5a86', stars: 22 },
  night: { x: 0.9, y: 0.14, r: 7, c: '#eef2fa', lo: '#b4bcd4', glow: '#34406e', stars: 80 },
  dawn: { x: 0.08, y: 0.18, r: 6, c: '#f4e6ea', lo: '#d0bcc8', glow: null, stars: 6 },
  day: null,
};
function paintSky(env, g) {
  const th = env.theme, { W, H, u } = env, T = town(env), hr = th.xh;
  const img = g.getImageData(0, 0, W, H), d = img.data;
  const get = (x, y) => { const i = (y * W + x) * 4; return [d[i], d[i + 1], d[i + 2]]; };
  const set = (x, y, c) => { if (x < 0 || y < 0 || x >= W || y >= H) return; const i = (y * W + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; };
  // the market's glow rising off the roofs: warm dithered steps, strongest over the square
  if (hr !== 'day') {
    const gc = hex(hr === 'dusk' ? '#e88c78' : hr === 'night' ? '#5a3a5a' : '#f0b8a8'), reach = (hr === 'night' ? 30 : 26) * u;
    const sq = W * 0.6;
    for (let y = Math.max(0, Math.round(T.base - reach - 30 * u)); y < Math.min(H, T.base + 2); y++) for (let x = 0; x < W; x++) {
      const up = (T.base - y) / reach, over = Math.exp(-(((x - sq) / (W * 0.45)) ** 2)) * 0.6 + 0.4;
      const kk = Math.max(0, 1 - up) * over;
      if (kk * 16 > bay(x, y) + 0.5) set(x, y, mix(get(x, y), gc, hr === 'night' ? 0.45 : 0.32));
    }
  }
  const MN = MOONS[hr] && !th.rain && !th.snow && !th.fog && !th.deck ? MOONS[hr] : null;
  const R = rng(2412);
  if (MN) {
    // stars, clear of the moon and fading toward the glow
    const n = th.snow ? Math.round(MN.stars * 0.3) : MN.stars;
    for (let i = 0; i < n; i++) {
      const x = Math.floor(R() * W), y = Math.floor(Math.pow(R(), 1.5) * T.base * 0.7), b = R();
      set(x, y, mix(get(x, y), hex('#f4f0ff'), b > 0.85 ? 0.95 : b > 0.5 ? 0.6 : 0.35));
      if (b > 0.97) { for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) set(x + dx, y + dy, mix(get(x + dx, y + dy), hex('#c8d0ff'), 0.4)); }
    }
    // the moon, nearly full, with a dithered halo and a darker lower limb
    let r = MN.r * u;
    const gr = 9 * u, mx = Math.round(W * MN.x);
    let roofs = H;
    for (let x = Math.round((mx - r - 2) / T.k); x <= (mx + r + 2) / T.k; x++) if (x >= 0 && x < T.VW) roofs = Math.min(roofs, T.base - Math.round((T.VB - T.roofAt[x]) * T.k));
    // a big forest lifts the town: the moon shrinks a little rather than sink behind the roofs
    const room = roofs - 7 * u;
    if (2 * r > room) r = Math.max(4.5 * u, room / 2);
    const my = Math.round(Math.max(r + 2 * u, Math.min(H * MN.y, roofs - r - 5 * u)));
    env.marketMoon = { x: mx, y: my, r };
    if (MN.glow) for (let y = Math.round(my - r - gr); y <= my + r + gr; y++) for (let x = Math.round(mx - r - gr); x <= mx + r + gr; x++) {
      const dd = Math.hypot(x + 0.5 - mx, y + 0.5 - my) - r; if (dd < 0 || dd > gr) continue;
      const kk = dd / gr, on = kk < 0.3 ? (x + y) % 2 === 0 : kk < 0.65 ? (x % 2 === 0 && y % 2 === 0) : (x % 4 === 0 && y % 2 === 0);
      if (on) set(x, y, mix(get(x, y), hex(MN.glow), kk < 0.3 ? 0.55 : 0.45));
    }
    const face = hex(MN.c), lo = hex(MN.lo);
    for (let y = Math.floor(my - r); y <= my + r; y++) for (let x = Math.floor(mx - r); x <= mx + r; x++) {
      const nx = (x + 0.5 - mx) / r, ny = (y + 0.5 - my) / r, q = nx * nx + ny * ny; if (q > 1) continue;
      let c = face;
      const maria = [[-0.3, -0.2, 0.3], [0.2, 0.25, 0.26], [0.3, -0.35, 0.16]];
      for (const [ax, ay, ar] of maria) if (((nx - ax) ** 2 + (ny - ay) ** 2) < ar * ar) c = mix(face, lo, 0.6);
      if (nx + ny > 0.8 && bay(x, y) < (nx + ny - 0.8) * 16) c = mix(c, lo, 0.7);
      if (q > 0.8 && hr === 'dusk' && ny > 0) c = mix(c, hex('#e8a098'), 0.4);
      set(x, y, c);
    }
  }
  // long thin clouds at dusk, their undersides lit rose by the sun gone down
  if (hr === 'dusk' && !th.rain && !th.snow && !th.fog) {
    const body = hex('#4a3e74'), top = hex('#34305e'), lit = hex('#b86c8c'), lit2 = hex('#e29aa0');
    const banks = [[0.42, 0.12, 0.16, 7, 1.3], [0.75, 0.1, 0.1, 5, 2.2]];
    for (const [cq, yq, lq, tk, ph] of banks) {
      const cx = W * cq, half = W * lq, y0 = Math.round(H * yq);
      for (let x = Math.floor(cx - half); x <= cx + half; x++) {
        const f = (x - (cx - half)) / (2 * half), bump = 0.45 + 0.4 * Math.abs(Math.sin(x * 0.16 / u + ph)) + 0.12 * Math.sin(x * 0.7 + ph * 2);
        const n = Math.round(tk * u * Math.pow(Math.sin(Math.PI * f), 0.6) * bump);
        if (n < 1) continue;
        const yb = y0 + Math.round(Math.sin(x * 0.04 + ph) * 1.5 * u);  // the flat, lit underside
        for (let r = 0; r < n; r++) {
          const y = yb - r;
          if (MN && env.marketMoon && Math.hypot(x - env.marketMoon.x, y - env.marketMoon.y) < env.marketMoon.r + 2) continue;
          let c = r === 0 ? lit : r === 1 && n > 2 ? mix(body, lit, 0.4) : r === n - 1 ? top : body;
          if (r >= 2 && r < n - 1 && bay(x, y) < 3) c = mix(body, lit, 0.3);
          if (r === 0 && f > 0.3 && f < 0.75 && bay(x, y) < 6) c = lit2;
          const edge = Math.min(f, 1 - f);
          if (edge < 0.12 && bay(x, y) > edge / 0.12 * 16) continue;  // frayed ends
          set(x, y, c);
        }
      }
    }
  }
  g.putImageData(img, 0, 0);
}

/* ---------- the town, the quay and the river's ice, laid on the land before the forest ---------- */
function drawTown(env, lg) {
  const T = town(env), P = T.paint, { k, VW, VB } = T, VH = P.plan.VH;
  const y0 = T.base - Math.round(VB * k);
  if (k === 1) {
    lg.drawImage(P.cv, 0, y0);
    // the holes: the carousel and the great tree's lights, drawn live behind the land
    for (const i of P.holes) lg.clearRect(i % VW, y0 + Math.floor(i / VW), 1, 1);
    T.y0 = y0;
    T.live = true;
    T.car = P.car;
    T.lights = P.plan.out.lights.map(([x, y, c]) => [x, y + y0, c, hashStr('l' + x + y) % 628 / 100]);
    T.star = P.plan.out.tree.star;
  } else {
    // a small panel: the town drawn scaled, still (the carousel's first frame baked in)
    const F = P.car;
    const [tmp, tg] = layer(VW, VH);
    tg.drawImage(P.cv, 0, 0); tg.drawImage(F.frames[0], F.x0, F.y0);
    for (const [x, y, c] of P.plan.out.lights) { tg.fillStyle = rgb(TREE_LIGHTS[c]); tg.fillRect(x, y, 1, 1); }
    lg.imageSmoothingEnabled = false;
    lg.drawImage(tmp, 0, y0, Math.round(VW * k), Math.round(VH * k));
    T.live = false;
  }
  let chim = 0;
  T.smoke = P.plan.out.chimneys.filter(c => c[2] === 'steam' || chim++ % 2 === 0).map(([x, y, kind]) => ({ x: Math.round(x * k), y: y0 + Math.round(y * k), steam: kind === 'steam' }));
}

/* which pixels round the town are open sky or the town still showing (trees in front hide it):
 * found once, on the first frame, from the finished land */
function townMask(env) {
  const T = env.market; if (!T || T.mask) return T;
  const plan = T.paint.plan, VH = plan.VH, y0 = T.y0 || 0;
  const { W } = env, y1 = Math.min(env.H, y0 + VH), land = env.land.getContext('2d').getImageData(0, 0, W, y1).data;
  const town = T.paint.cv.getContext('2d').getImageData(0, 0, T.VW, VH).data;
  const mask = new Uint8Array(W * y1), ob = new Int16Array(W * y1);  // 1 sky, 2 town or ice showing; ob: the foot of what stands on the ice there
  for (let y = 0; y < y1; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x, j = i * 4, ty = y - y0;
    if (T.k === 1 && ty >= 0 && ty < VH && x < T.VW) { const o = plan.OB[ty * T.VW + x]; if (o) ob[i] = o + y0; }
    if (!land[j + 3]) { mask[i] = 1; continue; }
    if (T.k === 1 && ty >= 0 && ty < VH && x < T.VW) { const q = (ty * T.VW + x) * 4; if (land[j] === town[q] && land[j + 1] === town[q + 1] && land[j + 2] === town[q + 2]) mask[i] = 2; }
  }
  T.mask = { a: mask, h: y1, ob };
  return T;
}

/* ---------- the park: lamps and benches, the lamps' light pooled on the snow ---------- */
function parkCols(th) {
  const k = dk(th);
  return { iron: rgb(mix(hex('#0a0c14'), hex('#2a2c34'), k)), ironL: rgb(mix(hex('#3a4058'), hex('#6a7080'), k)), wood: rgb(mix(hex('#2a1c18'), hex('#7a5436'), k)),
    snow: rgb(mix(hex('#8c96c0'), hex('#f6f8fc'), k)) };
}

/* the river through the forest, frozen too: ice by depth, darker under the banks, gloss,
 * skate tracks running with the channel, cracks, and snow drifted in along its edges */
function freezeRiver(env) {
  const S = env.river, RL = AF.LANDSCAPES.river;
  if (!S || !S.vis || S.iced || !RL || !RL.center) return;
  S.iced = true;
  const { W, H, hor } = env, IP = icePal(env.theme), { HORIZON } = AF.GEOM;
  const lg = env.land.getContext('2d'), img = lg.getImageData(0, 0, W, H), d = img.data;
  const snowA = hex(env.theme.g0), snowB = mix(hex(env.theme.g0), hex(env.theme.g1), 0.45);
  const across = (x, y) => { const p = (y / H - HORIZON) / (1 - HORIZON), cx = W * RL.center(p), hw = W * RL.halfWidth(p, W); return [p, (x + 0.5 - cx) / Math.max(0.5, hw), hw]; };
  const lipL = mix(snowA, [255, 255, 255], 0.12), lipR = mix(hex(env.theme.g1), IP.crackD, 0.35);
  for (let y = hor; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x, j0 = i * 4;
    if (!S.vis[i]) {  // the sandy lip of the bank, where no tree hides it, is a ridge of snow
      if (S.bed[i] && !S.mask[i] && ((d[j0] << 16) | (d[j0 + 1] << 8) | d[j0 + 2]) === S.bed[i]) {
        const c = across(x, y)[1] < 0 ? lipL : lipR; d[j0] = c[0]; d[j0 + 1] = c[1]; d[j0 + 2] = c[2];
      }
      continue;
    }
    const [p, a, hw] = across(x, y), q = Math.min(1, p * 1.15), lv = Math.min(4, Math.floor(q * 4 + bay(x, y) / 16));
    let c = mix(IP.far, IP.near, lv / 4);
    if (Math.abs(a) > 0.72 && bay(x, y) < 10) c = mix(c, IP.far, 0.4);
    const gq = x + y * 2;
    if (gq % 23 === 0 && hashStr('rg' + Math.floor(gq / 23) + ',' + (y >> 2)) % 3 === 0) c = mix(c, IP.gloss, 0.6);
    for (let k = 0; k < 3; k++) {
      const at = 0.55 * Math.sin(p * 11 + k * 2.1) + (k - 1) * 0.2;
      if (Math.abs(a - at) * hw < 0.55 && (x + y + k) % 4) c = mix(c, IP.trail, 0.5);
    }
    const nz = Math.sin(x * 0.13 + y * 0.8) + Math.sin(x * 0.041 - y * 0.37 + 0.7) + 0.5 * Math.sin(x * 0.31 + y * 1.3);
    const edge = Math.abs(a) - 0.84 - nz * 0.06;
    if (edge > 0) c = edge > 0.06 || bay(x, y) < 9 ? snowA : snowB;
    else if (nz > 1.8) c = bay(x, y) < 8 ? snowA : mix(snowA, c, 0.5);
    const j = i * 4; d[j] = c[0]; d[j + 1] = c[1]; d[j + 2] = c[2];
  }
  const CR = rng(313), tint = (x, y, c, k) => { if (x < 0 || x >= W || y < hor || y >= H || !S.vis[y * W + x]) return; const j = (y * W + x) * 4, o = mix([d[j], d[j + 1], d[j + 2]], c, k); d[j] = o[0]; d[j + 1] = o[1]; d[j + 2] = o[2]; };
  for (let n = 0; n < 14; n++) {
    const y0 = Math.round(hor + (0.35 + 0.6 * CR()) * (H - hor)), [p] = across(0, y0), hw = W * RL.halfWidth(p, W);
    let x = Math.round(W * RL.center(p) + (CR() - 0.5) * hw * 1.2), y = y0;
    const len = 4 + Math.floor(CR() * 9), dir = CR() < 0.5 ? -1 : 1;
    for (let s = 0; s < len; s++) { tint(x, y, IP.crack, 0.75); tint(x, y + 1, IP.crackD, 0.4); x += dir; if (CR() < 0.4) y += CR() < 0.5 ? -1 : 1; }
  }
  lg.putImageData(img, 0, 0);
}

/* ---------- the skaters: little sprites, facing right, their feet on the bottom row ---------- */
// p pompom, h hat, f face, s scarf, c coat, l legs, b blades
const POSES = {
  glideA: ['....p.', '...hh.', '...fs.', '..ccc.', '.c.cc.', 'll..l.', '...bbb'],
  glideB: ['....p.', '...hh.', '...fs.', '..ccc.', '..cccc', '..l.l.', '.bb.bb'],
  front: ['.hph.', '..f..', '.sss.', 'ccccc', '.ccc.', '.l.l.', 'bb.bb'],
  back: ['.hph.', '.hhh.', '.sss.', 'ccccc', '.ccc.', '.l.l.', 'bb.bb'],
  wobA: ['c..p..', '.chh..', '..fs.c', '..ccc.', '..cc..', '.l..l.', 'bb..bb'],
  wobB: ['...p..', '..hh.c', 'c.fsc.', '.ccc..', '..cc..', '..l.l.', '.bb.bb'],
  fallen: ['p......', 'hf.....', 'sc....b', 'ccclll.'],
  kneel: ['..p..', '.hh..', '.fs..', '.ccl.', 'cc.lb'],
};
const SKATE_COATS = ['#b8202e', '#1e3a78', '#1e5a3a', '#6a2a5a', '#e8e2d6', '#2a6a8a', '#8a1a2a'];
const SKATE_HATS = ['#e8e4dc', '#c02838', '#2e5ad0', '#1e5a3a', '#f0f0f4', '#c02838'];
const SKATERS = {};
/* each pose as a list of [dx, dy, colour], for one outfit and one hour, facing either way */
function skaterSprites(th, n) {
  const key = th.xh + '|' + n;
  if (SKATERS[key]) return SKATERS[key];
  const k = dk(th), night = hex('#0e1430');
  const shade = c => rgb(mix(hex(c), night, (1 - k) * 0.4));
  const pal = { p: shade('#f6f6fa'), h: shade(SKATE_HATS[n % SKATE_HATS.length]), f: rgb(mix(hex('#6a4a48'), hex('#eac4ac'), Math.max(k, 0.55))),
    s: shade(n % 2 ? '#e8e4dc' : '#c02838'), c: shade(SKATE_COATS[n % SKATE_COATS.length]), l: shade('#1c1a2a'), b: k > 0.5 ? '#46546e' : '#d4deee' };
  const out = {};
  for (const name in POSES) {
    const rows = POSES[name], h = rows.length, w = rows[0].length, R = [], L = [];
    rows.forEach((row, y) => { for (let x = 0; x < w; x++) { const ch = row[x]; if (ch === '.') continue; R.push([x - (w >> 1), y - h + 1, pal[ch]]); L.push([(w >> 1) - x - (w & 1 ? 0 : 1), y - h + 1, pal[ch]]); } });
    out[name] = { R, L };
  }
  return (SKATERS[key] = out);
}
/* where a skater is at time t, and how it stands: { x, y (feet), pose, right } */
function skaterAt(s, t) {
  if (s.kind === 'loop' || s.kind === 'pair') {
    const a = s.w * t + s.ph, x = s.cx + s.rx * Math.cos(a), y = s.cy + s.ry * Math.sin(a), right = -Math.sin(a) * s.w > 0;
    return { x, y, right, pose: (Math.floor(t * 1.6 + s.ph) & 1) ? 'glideA' : 'glideB' };
  }
  if (s.kind === 'line') {  // straight across and round again
    const span = s.x1 - s.x0, x = s.x0 + (((t * s.v + s.ph * span) % span) + span) % span;
    return { x, y: s.cy, right: s.v > 0, pose: (Math.floor(t * 1.4 + s.ph * 5) & 1) ? 'glideA' : 'glideB' };
  }
  if (s.kind === 'twirl') {  // spins on the spot, then glides a little arc
    const c = (t + s.ph * 10) % 10;
    if (c < 5) { const f = Math.floor(t * 7) % 4; return { x: s.cx, y: s.cy, right: f === 1, pose: f === 0 ? 'front' : f === 2 ? 'back' : 'glideB' }; }
    const a = (c - 5) / 5 * Math.PI * 2;
    return { x: s.cx + Math.sin(a) * s.rx, y: s.cy - (1 - Math.cos(a)) * 0.8, right: Math.cos(a) > 0, pose: 'glideA' };
  }
  // the beginner: wobbles along, arms going, and every so often sits down hard on the ice
  const c = (t + s.ph * s.period) % s.period, fall = s.period - 2.6;
  const x = s.cx + Math.sin(Math.min(c, fall) * 0.55) * s.rx;
  if (c > fall + 1.7) return { x, y: s.cy, right: true, pose: 'kneel' };
  if (c > fall) return { x, y: s.cy, right: true, pose: 'fallen' };
  return { x, y: s.cy, right: Math.cos(c * 0.55) > 0, pose: (Math.floor(t * 3.3) & 1) ? 'wobA' : 'wobB' };
}
function drawSkater(g, spr, st, ok) {
  const X = Math.round(st.x), Y = Math.round(st.y), px = spr[st.pose][st.right ? 'R' : 'L'];
  for (const [dx, dy, c] of px) { const x = X + dx, y = Y + dy; if (!ok(x, y, Y)) continue; g.fillStyle = c; g.fillRect(x, y, 1, 1); }
}

/* ---------- Santa's sleigh: four reindeer and a laden sleigh, two frames, built once per hour ---------- */
// a antler, h head, n nose, b body, t tail, l leg; runs left
const DEER = [
  ['a.a......', '.a.a.....', '.hh......', 'nhhb.....', '..bbbbbbt', '..bbbbbb.', '.l.....l.', 'l.......l'],
  ['.a.a.....', '..a.a....', '.hh......', 'nhhb.....', '..bbbbbbt', '..bbbbbb.', '...l..l..', '..l..l...'],
];
// H hat, W its trim, f face, S suit, P sack, K sleigh, k its rim, r runner
const SLEIGH = [
  '.......W.......',
  '......HH...PP..',
  '.....HWW..PPPP.',
  '.....fSS.PPPPPP',
  'kk...SSSkPPPPPk',
  'k.kkkkkkkkkkkkk',
  'k..KKKKKKKKKKKK',
  '.k..KKKKKKKKKK.',
  '..r...r....r...',
  '.rrrrrrrrrrrrrr',
];
const SLEIGH_W = 60, SLEIGH_H = 12;
/* each frame as a list of [dx, dy, colour]: full colour by day, a silhouette against the evening
 * sky with the moonlight on its top edges (and Rudolph's nose still red) after it */
function sleighSprites(th) {
  const day = th.xh === 'day';
  const ink = th.xh === 'dawn' ? '#28304e' : '#080d20', edge = th.xh === 'night' ? '#4a5a94' : th.xh === 'dusk' ? '#4e4a82' : '#4a5480';
  const C = day
    ? { a: '#ece2cc', h: '#7a5438', n: '#e8283c', b: '#7a5438', t: '#e8dcc8', l: '#4a3222', H: '#d02838', W: '#f4f4f8', f: '#f0c8b0', S: '#c8243a', P: '#8a6a4c', K: '#b8203a', k: '#e8ecf4', r: '#b8c0cc', rein: '#4a3222' }
    : { a: ink, h: ink, n: '#ff3a4a', b: ink, t: ink, l: ink, H: ink, W: ink, f: ink, S: ink, P: ink, K: ink, k: ink, r: ink, rein: ink };
  return [0, 1].map(fr => {
    const grid = new Array(SLEIGH_W * SLEIGH_H).fill(null);
    const put = (x, y, c) => { if (x >= 0 && y >= 0 && x < SLEIGH_W && y < SLEIGH_H) grid[y * SLEIGH_W + x] = c; };
    for (let d = 0; d < 4; d++) {
      const S = DEER[(fr + d) & 1], ox = d * 10, oy = 1 + ((fr + d) & 1 ? 0 : 1);
      for (let r = 0; r < S.length; r++) for (let k = 0; k < S[r].length; k++) { const ch = S[r][k]; if (ch === '.') continue; put(ox + k, oy + r, ch === 'n' && d > 0 ? C.h : C[ch]); }
      if (d < 3) for (let x = ox + 9; x < ox + 12; x++) put(x, oy + 4, C.rein);  // the harness to the next one back
    }
    for (let x = 39; x < 45; x++) put(x, 5 + (x > 42 ? 1 : 0), C.rein);  // the reins
    for (let r = 0; r < SLEIGH.length; r++) for (let k = 0; k < SLEIGH[r].length; k++) { const ch = SLEIGH[r][k]; if (ch !== '.') put(44 + k, r + 2, C[ch]); }
    const px = [];
    for (let y = 0; y < SLEIGH_H; y++) for (let x = 0; x < SLEIGH_W; x++) {
      let c = grid[y * SLEIGH_W + x]; if (!c) continue;
      if (!day && c === ink && (y === 0 || !grid[(y - 1) * SLEIGH_W + x])) c = edge;
      px.push([x, y, c]);
    }
    return px;
  });
}
/* the sleigh's path: its sprite's top-left at progress p (0 entering on the right, 1 gone off the
 * left), kept above the roofs and climbing gently as it goes. The sky over the town is shallow, so
 * the slender things (the spires, the gatehouse, the great tree's crown and star) may rise past
 * it: it passes behind them, the skyline's mask keeping them whole. */
function sleighPath(env, T) {
  const { W, u } = env, m = env.marketMoon;
  // the top of the skyline under each screen column, and the broad roofline, slender peaks left out
  const roof = x => { const vx = Math.floor(x / T.k); return vx < 0 || vx >= T.VW ? T.base : T.base - Math.round((T.VB - T.roofAt[vx]) * T.k); };
  const sharp = new Int16Array(W), broad = new Int16Array(W), reach = Math.round(SLEIGH_SLENDER * T.k);
  for (let x = 0; x < W; x++) sharp[x] = roof(x);
  for (let x = 0; x < W; x++) { let r = 0; for (let q = Math.max(0, x - reach); q <= Math.min(W - 1, x + reach); q++) r = Math.max(r, sharp[q]); broad[x] = r; }
  let top = T.base;
  for (let x = 0; x < W; x++) top = Math.min(top, broad[x]);
  const clear = Math.max(1, Math.round(2 * u)), x0 = -42, x1 = W + 38;  // the sprite's centre from off the left to off the right
  // highest the sprite's top may be over each centre: the broad roofline under its span, less a margin
  const lim = new Int16Array(x1 - x0 + 1);
  for (let xc = x0; xc <= x1; xc++) {
    let r = T.base;
    for (let x = Math.max(0, xc - SLEIGH_W / 2 - 2); x <= Math.min(W - 1, xc + SLEIGH_W / 2 + 2); x++) r = Math.min(r, broad[x]);
    lim[xc - x0] = r - clear - SLEIGH_H;
  }
  // across the moon's face when it shows, otherwise midway up the sky over the spires
  const xA = m ? m.x : Math.round(W * SLEIGH_AT);
  let yA = m ? m.y - 7 : Math.round(top * 0.45) - 6, rise = SLEIGH_RISE;
  for (let pass = 0; pass < 3; pass++) {
    rise = Math.max(0, Math.min(SLEIGH_RISE, (yA - 1) / (xA - x0)));  // never off the top at the far left
    let over = 0;
    for (let xc = x0; xc <= x1; xc++) over = Math.max(over, yA + (xc - xA) * rise + 1 - lim[xc - x0]);
    yA -= Math.ceil(over);
  }
  return p => { const x = W + 8 - p * (W + 80); return [x, Math.max(0, yA + (x + SLEIGH_W / 2 - xA) * rise + Math.sin(p * 9) * 0.8)]; };  // a big forest's squeezed sky: its runners may just pass behind a roof, never its antlers off the top
}

/* ---------- Santa hats ----------
 * The fox wears a Santa hat, set on the top of its ears and flopping back, away from
 * where it faces. Rows from
 * the band upward, drawn facing right: w fur, r red, R its shade, p the pompom. */
const HAT_WEARERS = new Set(['fox']);
const HAT = ['p...', '.rR.', '.rrR', 'wwww'];
const HAT_COLS = { w: '#f2f0ec', r: '#c8282e', R: '#8e1a22', p: '#ffffff' };

function santaHat(g, env, { key, rows, x0, y0, flip, facesLeft, color }) {
  if (!HAT_WEARERS.has(key)) return;
  // the ears: the topmost pixels on the head's side of the sprite, as drawn
  const n = rows[0].length, half = n / 2, drawn = xx => flip ? n - 1 - xx : xx;
  let top = -1;
  const xs = [];
  for (let yy = 0; yy < rows.length && top < 0; yy++) {
    for (let xx = 0; xx < n; xx++) {
      const at = drawn(xx);
      if (rows[yy][xx] !== '.' && (facesLeft ? at < half : at >= half)) xs.push(at);
    }
    if (xs.length) top = yy;
  }
  if (top < 0) return;
  const cx = Math.round((Math.min(...xs) + Math.max(...xs)) / 2), by = y0 + top - 1;
  HAT.forEach((row, i) => {
    for (let k = 0; k < row.length; k++) {
      const ch = row[k]; if (ch === '.') continue;
      const dx = facesLeft ? 1 - k : k - 2;  // the tip flops back, behind the head
      g.fillStyle = color(HAT_COLS[ch], ch);
      g.fillRect(x0 + cx + dx, by - (HAT.length - 1 - i), 1, 1);
    }
  });
}

AF.env('frozen_market', {
  look: mood => clone(LOOKS[hourOf(mood.time)]),
  theme(th, mood) { th.xh = hourOf(mood.time); },
  after(th) {
    th.orb = null;           // the moon is painted with the sky, clear of the town
    th.stars = 0;            // and so are the stars
    th.rim = null; th.rainbow = false;
    th.tint = null; th.tintAmt = 0;  // the trees have their own colours for every hour
    th.flies = 0;
    th.frozen = true;         // the river, the lake and the ponds are ice
    th.water = { dusk: '#7c90c4', night: '#34466e', dawn: '#b0bede', day: '#c4dcee' }[th.xh] || th.water;
    // snow greys the sky; the market's hours keep their colour behind the falling flakes
    if (th.snow && SNOW_SKY[th.xh]) th.sky = SNOW_SKY[th.xh].slice();
    if (th.snow && th.xh === 'dusk') th.clouds = { n: 3, top: '#7a7298', bot: '#5a5680', a: 235 };
    if (th.snow && th.xh === 'dawn') th.clouds = { n: 3, top: '#e8dce4', bot: '#b8aac4', a: 235 };
    if (th.snow && th.xh !== 'day') { th.g0 = th.xh === 'night' ? '#5c6c94' : '#9a98c4'; th.g1 = th.xh === 'night' ? '#36446a' : '#6a6a9a'; th.grass = th.xh === 'night' ? '#7c8cb4' : '#bab8dc'; }
  },
  pals: {
    rounds: [YEW_N], pine: FIR_N, roundAt: th => palsFor(th).fir,
    bark: { l: BARK_N[2], m: BARK_N[1], d: BARK_N[0] },
    leaf: hex('#2a6a44'), leafL: hex('#4a9060'), stem: hex('#3a2e2a'),
  },
  tree: TREE,
  dressVisitor: santaHat,
  sky(env, g) { paintSky(env, g); },
  backdrop() { /* the town is the horizon: drawn in ground() */ },
  ground(env, lg) { drawTown(env, lg); },
  groundPixel(c, x, y, env) {
    // drifts: soft blue hollows in the snow, dithered
    const n = Math.sin(x * 0.07 + y * 0.29) + Math.sin(x * 0.023 - y * 0.17 + 1.3) + 0.6 * Math.sin((x + y * 2) * 0.05);
    if (n > 1.4 && bay(x, y) < 7) return mix(c, hex(env.theme.g1), 0.4);
    if (n < -1.6 && bay(x, y) < 5) return mix(c, hex(env.theme.grass), 0.5);
    return c;
  },
  /* park lamps and benches among the front rows */
  groundDetail(env, lg, p, sw, R, x, y) {
    const t = p.it; if (t.fromFront > 6 || t.stage < 2) return;
    const kind = t.seed % 17, C = parkCols(env.theme), on = lampsOn(env.theme);
    const gx = x + ((t.seed >> 4) & 1 ? -Math.round(sw / 2) - 4 : Math.round(sw / 2) + 3);
    const P = (col, a, b, w = 1, h = 1) => { lg.fillStyle = col; lg.fillRect(gx + a, y + b, w, h); };
    if (kind === 2) {  // a lamp post, its light pooled on the snow
      if (on) for (let dy = -2; dy <= 2; dy++) for (let dx = -7; dx <= 7; dx++) {
        const q = (dx / 7) ** 2 + (dy / 2.2) ** 2; if (q > 1) continue;
        if ((1 - q) * 14 > bay(gx + dx, y + dy)) P(q < 0.35 ? 'rgba(255,214,150,.55)' : 'rgba(255,190,130,.35)', dx, dy);
      }
      P(C.iron, 0, -11, 1, 12); P(C.iron, -1, 0, 3, 1); P(C.ironL, 0, -9, 1, 1);
      P(C.iron, -1, -13, 3, 1); P(C.iron, 0, -14, 1, 1);
      P(on ? '#ffe2a0' : '#8a96a8', -1, -12, 3, 1); P(on ? '#fff4d0' : '#aab4c4', 0, -12, 1, 1);
      if (on) { P('rgba(255,220,160,.35)', -2, -13, 1, 2); P('rgba(255,220,160,.35)', 2, -13, 1, 2); P('rgba(255,220,160,.3)', -1, -14, 1, 1); P('rgba(255,220,160,.3)', 1, -14, 1, 1); }
      P(C.snow, -1, -14, 1, 1); P(C.snow, 1, -14, 1, 1);
    } else if (kind === 9 && t.kind === 1 && t.stage >= 4) {  // presents under an old fir
      const G = [['#c02838', '#f0f0f4'], ['#2e5ad0', '#e8404c'], ['#e8ecf4', '#c02838']];
      [[-3, 3, 3], [1, 4, 2], [-1, 2, 2]].forEach(([dx, w, hh], j) => {
        const [box, rib] = G[(t.seed + j) % 3], bx = x + dx - gx, by = -hh + 1 - (j === 2 ? 3 : 0);
        P(box, bx, by, w, hh); P(rib, bx + (w >> 1), by, 1, hh); P(rib, bx + (w >> 1) - 1, by - 1, 1, 1); P(rib, bx + (w >> 1) + 1, by - 1, 1, 1);
      });
    } else if (kind === 13 && t.fromFront <= 3 && (t.seed >> 5) % 3 === 0) {  // a snowman with a red scarf
      P(C.snow, 0, -3, 4, 4); P(C.snow, 1, -6, 2, 3); P(C.snow, -1, -2, 6, 2);
      P('#c02838', 0, -4, 4, 1); P('#c02838', 3, -3, 1, 2); P(C.iron, 1, -5, 1, 1); P(C.iron, 0, -7, 4, 1); P(C.iron, 1, -9, 2, 2);
    } else if (kind === 5) {  // a bench with snow on its seat
      P(C.iron, 0, -1, 1, 2); P(C.iron, 5, -1, 1, 2);
      P(C.wood, 0, -2, 6, 1); P(C.wood, 0, -4, 6, 1); P(C.iron, 0, -3, 1, 1); P(C.iron, 5, -3, 1, 1);
      P(C.snow, 1, -3, 4, 1); P(C.snow, 0, -5, 3, 1);
    }
  },

  fx: {
    init(st, { A, env }) {
      freezeRiver(env);
      const T = env.market; st.puffs = [];
      if (!T) return;
      // people strolling along the stalls, and a few stopped at the counters
      const COATS = ['#5a1a22', '#1e2a4a', '#1e3a2a', '#3a2a22', '#2a2438', '#6a2a2a'], HATS = ['#c02838', '#e8e4dc', '#2e5ad0', '#1e5a3a', '#6a2a4a'];
      st.folk = [];
      if (T.live) for (let i = 0; i < FOLK; i++) {
        const still = A() < 0.35;
        st.folk.push({ x: A() * env.W, v: still ? 0 : (A() < 0.5 ? -1 : 1) * (1.2 + A() * 2.2) * env.u, coat: COATS[i % COATS.length], hat: HATS[(i * 3) % HATS.length], tall: A() < 0.7 ? 5 : 4, ph: A() * 6, kid: A() < 0.15 });
      }
      // and a few crossing the bridge
      if (T.live) for (let i = 0; i < BRIDGE_FOLK; i++) st.folk.push({ bridge: true, x: A() * T.paint.plan.out.bridge.tx, v: (A() < 0.5 ? -1 : 1) * (1 + A() * 1.5), coat: COATS[(i + 2) % COATS.length], hat: HATS[i % HATS.length], tall: 5, ph: A() * 6 });
      for (const s of T.smoke || []) { const n = s.steam ? 6 : 7; for (let i = 0; i < n; i++) st.puffs.push({ s, ph: i / n + A() * 0.05, sw: A() * 6 }); }
      // Santa's sleigh: its two frames and its path over the roofs, worked out once
      st.sleigh = { spr: sleighSprites(env.theme), at: sleighPath(env, T) };
      // the skaters: round the rink, along the stalls, under and in front of the bridge
      st.skaters = []; st.riverSk = []; st.lakeSk = false;
      if (T.live) {
        const o = T.paint.plan.out, y0 = T.y0, W = env.W, b = o.bridge;
        const yLo = y0 + o.I0 + 5, yHi = Math.max(yLo + 2, y0 + Math.min(T.VL + 2, T.paint.plan.VH - 5)), mid = (yLo + yHi) / 2, ry = (yHi - yLo) / 2;
        let n = 0;
        const add = sk => { sk.n = n++; st.skaters.push(sk); };
        add({ kind: 'loop', cx: W * 0.5, rx: W * 0.1, cy: mid, ry, w: 0.45, ph: 0 });
        add({ kind: 'loop', cx: W * 0.46, rx: W * 0.065, cy: mid, ry: ry * 0.7, w: -0.6, ph: 2 });
        add({ kind: 'pair', cx: W * 0.53, rx: W * 0.085, cy: mid, ry: ry * 0.8, w: 0.36, ph: 4 });
        add({ kind: 'twirl', cx: W * 0.43, cy: yHi - 1, rx: 5, ph: 0.3 });
        add({ kind: 'beginner', cx: W * 0.585, cy: yHi, rx: 6, period: 11, ph: 0.2 });
        add({ kind: 'loop', cx: W * 0.8, rx: W * 0.17, cy: yHi - 0.5, ry: 1, w: 0.22, ph: 1 });
        add({ kind: 'loop', cx: W * 0.78, rx: W * 0.15, cy: yHi, ry: 1, w: -0.27, ph: 3.5 });
        add({ kind: 'line', x0: -8, x1: b.tx + 2, cy: y0 + o.SB - 1, v: 5, ph: 0.1 });
        add({ kind: 'line', x0: -8, x1: b.tx + 2, cy: y0 + o.SB - 2, v: -4, ph: 0.6 });
        add({ kind: 'loop', cx: W * 0.16, rx: W * 0.12, cy: yHi, ry: 1, w: 0.3, ph: 5 });
      }
      // glints on the ice, catching the lamps
      st.iceGlint = [];
      if (T.live) {
        const plan = T.paint.plan, o = plan.out;
        for (let k = 0; k < 200 && st.iceGlint.length < ICE_GLINTS; k++) {
          const x = Math.floor(A() * plan.VW), y = o.I0 + 1 + Math.floor(A() * (plan.VH - o.I0 - 4));
          if (!plan.G[y * plan.VW + x]) st.iceGlint.push([x, y + T.y0, A() * 6.28, 0.6 + A() * 1.2]);
        }
      }
      // and on a frozen lake, if the forest has one
      const LK = env.water;
      if (LK && LK.lh > 8) {
        const W = env.W, cy = LK.y0 + LK.lh * 0.55;
        [[0.3, 0.12, 0.3, 'loop', 11], [0.62, 0.1, -0.4, 'pair', 12], [0.8, 0.06, 0.5, 'loop', 13], [0.47, 0, 0, 'beginner', 14], [0.15, 0, 0, 'twirl', 15]].forEach(([xq, rq, w, kind, n], i) => {
          const y = cy + (i % 3 - 1) * LK.lh * 0.22;
          st.riverSk.push(kind === 'beginner' ? { kind, n, cx: W * xq, cy: y, rx: 5, period: 12, ph: 0.4 } : kind === 'twirl' ? { kind, n, cx: W * xq, cy: y, rx: 5, ph: 0.7 } : { kind, n, cx: W * xq, cy: y, rx: W * rq, ry: 1.5, w, ph: n });
        });
        st.lakeSk = true;
      }
      // and on the frozen river through the forest, where it opens out at the front
      const S = env.river, RL = AF.LANDSCAPES.river;
      if (S && S.vis && RL && RL.center) {
        const { W, H } = env;
        [[0.8, 0.5, 0.35, 'loop', 7], [0.9, 0.45, -0.28, 'pair', 8], [0.86, 0, 0, 'beginner', 9]].forEach(([p, rq, w, kind, n]) => {
          const cx = W * RL.center(p), rx = W * RL.halfWidth(p, W) * rq, cy = H * (AF.GEOM.HORIZON + (1 - AF.GEOM.HORIZON) * p);
          st.riverSk.push(kind === 'beginner' ? { kind, n, cx: cx + W * RL.halfWidth(p, W) * 0.3, cy, rx: 4, period: 13, ph: 0.6 } : { kind, n, cx, cy, rx, ry: 1.5, w, ph: n });
        });
      }
      // the fairy lights on the nearest trees, to twinkle: found in the finished land
      st.tw = [];
      const { W, H, hor } = env, land = env.land.getContext('2d').getImageData(0, hor, W, H - hor).data;
      // glints in the snow of the park, where no tree stands
      st.glint = [];
      const gc = [hex(env.theme.g0), hex(env.theme.g1), hex(env.theme.grass)];
      for (let n = 0; n < 400 && st.glint.length < SNOW_GLINTS; n++) {
        const x = Math.floor(A() * W), y = hor + 3 + Math.floor(A() * (H - hor - 4)), j = ((y - hor) * W + x) * 4;
        const c = [land[j], land[j + 1], land[j + 2]];
        if (gc.some(q => Math.abs(q[0] - c[0]) + Math.abs(q[1] - c[1]) + Math.abs(q[2] - c[2]) < 36)) st.glint.push([x, y, A() * 6.28, 0.7 + A() * 1.4]);
      }
      const on = lampsOn(env.theme); if (!on) return;
      const keys = new Map(FAIRY_ON.map((c, i) => [c.join(','), i]));
      for (let y = 0; y < H - hor; y++) for (let x = 0; x < W; x++) {
        const j = (y * W + x) * 4; if (!land[j + 3]) continue;
        const kk = keys.get(land[j] + ',' + land[j + 1] + ',' + land[j + 2]);
        if (kk != null && A() < 0.6) st.tw.push([x, y + hor, kk, A() * 6.28, 0.8 + A() * 2]);
      }
    },
    back(g, env, t) {
      const T = env.market; if (!T || !T.live) return;
      // the carousel, turning slowly (a full turn every few seconds)
      const F = T.car, f = Math.floor(t * 3) % CAR_FRAMES;
      g.drawImage(F.frames[f], F.x0, T.y0 + F.y0);
      // the great tree's lights: slow waves of silver, red and blue
      const on = lampsOn(env.theme);
      for (const [x, y, c, ph] of T.lights) {
        const a = Math.sin(t * 1.3 + ph + x * 0.2);
        const col = !on ? TREE_LIGHTS_DIM[c] : a > 0.2 ? TREE_LIGHTS[c] : a > -0.6 ? mix(TREE_LIGHTS[c], TREE_LIGHTS_DIM[c], 0.5) : TREE_LIGHTS_DIM[c];
        g.fillStyle = rgb(col); g.fillRect(x, y, 1, 1);
      }
    },
    front(g, env, t, st, layer) {
      if (layer === 'air') {
        const S = env.river, LK = env.water;
        if (st.riverSk && st.riverSk.length && (S && S.vis || st.lakeSk)) {
          const W = env.W, H = env.H, ok = st.lakeSk ? (x, y) => x >= 0 && x < W && y >= LK.y0 && y < LK.y0 + LK.lh : (x, y) => x >= 0 && x < W && y >= 0 && y < H && S.vis[y * W + x];
          for (const sk of st.riverSk) {
            const at = skaterAt(sk, t), spr = skaterSprites(env.theme, sk.n);
            drawSkater(g, spr, at, ok);
            if (sk.kind === 'pair') drawSkater(g, skaterSprites(env.theme, sk.n + 3), { x: at.x + (at.right ? -4 : 4), y: at.y + 1, right: at.right, pose: at.pose === 'glideA' ? 'glideB' : 'glideA' }, ok);
          }
        }
        g.fillStyle = env.theme.xh === 'day' ? '#ffffff' : '#e8eeff';
        for (const [x, y, ph, sp] of st.glint || []) { const a = Math.sin(t * sp + ph); if (a > 0.82) { g.fillRect(x, y, 1, 1); if (a > 0.96) { g.fillRect(x - 1, y, 1, 1); g.fillRect(x + 1, y, 1, 1); } } }
        return;
      }
      if (layer === 'crowns') {
        // fairy lights on the near trees, twinkling
        for (const [x, y, c, ph, sp] of st.tw || []) {
          const a = Math.sin(t * sp + ph);
          if (a > -0.3) continue;
          g.fillStyle = rgb(FAIRY_OFF[c]); g.fillRect(x, y, 1, 1);
        }
        return;
      }
      if (layer !== 'sky') return;
      const T = townMask(env); if (!T || !T.mask) return;
      const M2 = T.mask, W = env.W, u = env.u;
      // Santa's sleigh crossing the sky every few minutes, a trail of sparkles behind; only on open sky
      if (st.sleigh) {
        const dur = SLEIGH_SECS, pAt = (W + 8 + SLEIGH_W / 2 - W * SLEIGH_AT) / (W + 80);
        const k = (((t - SLEIGH_FIRST + pAt * dur) % SLEIGH_EVERY) + SLEIGH_EVERY) % SLEIGH_EVERY;
        if (k <= dur) {
          const sky = (x, y) => x >= 0 && x < W && y >= 0 && y < M2.h && M2.a[y * W + x] === 1;
          const p = k / dur, [sx, sy] = st.sleigh.at(p);
          const trail = env.theme.xh === 'day' ? ['#ffffff', '#dce8ff'] : ['#ffffff', '#b4c8ff'];
          for (let q = 1; q <= 16; q++) {
            const [tx, ty] = st.sleigh.at(p - q * 0.006), hsh = hashStr(q + ':' + Math.floor(t * 8));
            if (hsh % 3 === 0 || q > 10 && hsh % 2) continue;
            const x = Math.round(tx + 54 + (hsh >>> 4) % 3), y = Math.round(ty + 8 + q * 0.35 + ((hsh >>> 6) % 3) - 1);
            if (sky(x, y)) { g.fillStyle = trail[q > 6 ? 1 : hsh & 1]; g.fillRect(x, y, 1, 1); }
          }
          const X = Math.round(sx), Y = Math.round(sy);
          for (const [dx, dy, c] of st.sleigh.spr[Math.floor(t * 7) & 1]) { const x = X + dx, y = Y + dy; if (sky(x, y)) { g.fillStyle = c; g.fillRect(x, y, 1, 1); } }
        }
      }
      // steam off the mulled wine and smoke from the chimneys, a pixel at a time
      const SM = { dusk: ['#a498c0', '#f2dcd4'], night: ['#5c5a7c', '#e8cbbc'], dawn: ['#d8ccdc', '#f6eaea'], day: ['#e8edf4', '#f6f8fb'] }[env.theme.xh];
      for (const p of st.puffs) {
        const s = p.s, a = ((t * (s.steam ? 0.2 : 0.09)) + p.ph) % 1;
        const rise = (s.steam ? 10 : 15) * u;
        const x = s.x + Math.sin(a * 4 + p.sw) * (s.steam ? 1 : 1.4) * a * 2 + a * a * (s.steam ? 2 : 9) * u, y = s.y - a * rise;
        const r = (s.steam ? 0.7 + a * 1.4 : 0.9 + a * 2.4) * u, dens = (1 - a) * (1 - a) * (s.steam ? 14 : 15);
        g.fillStyle = s.steam ? SM[1] : SM[0];
        for (let Y = Math.floor(y - r); Y <= y + r; Y++) for (let X = Math.floor(x - r); X <= x + r; X++) {
          if (X < 0 || X >= W || Y < 0 || Y >= M2.h || !M2.a[Y * W + X]) continue;
          const q = ((X + 0.5 - x) ** 2 + (Y + 0.5 - y) ** 2) / (r * r);
          if (q > 1 || bay(X, Y) >= dens * (1 - q * 0.5)) continue;
          g.fillRect(X, Y, 1, 1);
        }
      }
      // glints on the ice
      if (st.iceGlint) {
        g.fillStyle = env.theme.xh === 'day' ? '#ffffff' : '#f4f0ff';
        for (const [x, y, ph, sp] of st.iceGlint) {
          const a = Math.sin(t * sp + ph), i = y * W + x;
          if (a < 0.8 || y >= M2.h || M2.a[i] !== 2) continue;
          g.fillRect(x, y, 1, 1);
          if (a > 0.95) for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const j = (y + dy) * W + x + dx; if (y + dy < M2.h && M2.a[j] === 2 && !M2.ob[j]) g.fillRect(x + dx, y + dy, 1, 1); }
        }
      }
      // the skaters on the ice, nearest last; hidden by the trees, and by a stall or the bridge they are behind
      if (st.skaters && st.skaters.length) {
        const ok = (x, y, fy) => { if (x < 0 || x >= W || y < 0 || y >= M2.h) return false; const i = y * W + x; return M2.a[i] && !(M2.ob[i] && fy <= M2.ob[i]); };
        const now = st.skaters.map(sk => [sk, skaterAt(sk, t)]).sort((a, b) => a[1].y - b[1].y);
        for (const [sk, at] of now) {
          const spr = skaterSprites(env.theme, sk.n);
          drawSkater(g, spr, at, ok);
          if (sk.kind === 'pair') {  // a partner alongside, hand in hand
            const at2 = { x: at.x + (at.right ? -4 : 4), y: at.y + 1, right: at.right, pose: at.pose === 'glideA' ? 'glideB' : 'glideA' };
            drawSkater(g, skaterSprites(env.theme, sk.n + 3), at2, ok);
            const hx = Math.round((at.x + at2.x) / 2), hy = Math.round(at.y) - 3;
            if (ok(hx, hy, hy + 3)) { g.fillStyle = rgb(mix(hex(SKATE_COATS[sk.n % SKATE_COATS.length]), hex('#0e1430'), (1 - dk(env.theme)) * 0.4)); g.fillRect(hx, hy, 1, 1); }
          }
        }
      }
      // the folk: little silhouettes against the lit stalls, a warm edge from the stall lights
      if (st.folk && st.folk.length) {
        const on = lampsOn(env.theme), dk2 = dk(env.theme), o = T.paint.plan.out, yQ = T.y0 + T.VB + 1, yBr = T.y0 + o.bridge.D0 - 2;
        const skin = rgb(mix(hex('#6a4a48'), hex('#e8c0a8'), Math.max(dk2, on ? 0.45 : 0)));
        const warm = on ? '#f2b074' : null, W2 = env.W;
        for (const f of st.folk) {
          const span = f.bridge ? o.bridge.tx + 2 : W2 + 8, yB = f.bridge ? yBr : yQ;
          let x = f.x + f.v * t; x = ((x % span) + span) % span - (f.bridge ? 2 : 4);
          const X = Math.round(x), h = f.kid ? 3 : f.tall, step = f.v ? Math.floor(t * 4 + f.ph) & 1 : 0;
          const px = (col, dx, dy) => { const xx = X + dx, yy = yB - dy; if (xx < 0 || xx >= W2 || yy < 0 || yy >= M2.h) return; const i = yy * W2 + xx; if (M2.a[i] !== 2 || (!f.bridge && M2.ob[i] && M2.ob[i] > yB)) return; g.fillStyle = col; g.fillRect(xx, yy, 1, 1); };
          // legs, coat, a woolly hat, a face
          px(f.coat, step ? 0 : 1, 0); if (!f.kid) px(f.coat, step ? 1 : 0, 0);
          for (let k = 1; k < h - 1; k++) { px(f.coat, 0, k); px(f.coat, 1, k); }
          px(skin, f.v < 0 ? 0 : 1, h - 1); px(f.coat, f.v < 0 ? 1 : 0, h - 1);
          px(f.hat, 0, h); px(f.hat, 1, h); if (!f.kid) px(f.hat, 0, h + 1);
          if (warm) { px(warm, f.v < 0 ? 0 : 1, h - 2); }
        }
      }
      // the star on the great tree glints now and then
      if (T.star && T.live) {
        const [sx, sy] = T.star, X = sx, Y = sy + T.y0, k = Math.sin(t * 0.9);
        if (k > 0.6 && lampsOn(env.theme)) {
          g.fillStyle = 'rgba(240,246,255,.85)';
          for (const [dx, dy] of [[0, -5], [0, 5], [-5, 0], [5, 0], [0, -4], [-4, 0], [4, 0]]) { const xx = X + dx, yy = Y + dy; if (yy >= 0 && yy < M2.h && M2.a[yy * W + xx]) g.fillRect(xx, yy, 1, 1); }
        }
      }
    },
  },
});
})();

/* Memory Forest - the bamboo grove environment.
 * Everything this environment is lives here: delete it and bamboo.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * Tall jointed canes in soft jade rain, stone lanterns lit at the foot of the grove, and
 * on the water a slow procession of floating paper lanterns, their light running down
 * into the river - the one warm thing in a green, wet afternoon. Every clump has its own
 * character (a lone stem to a dense stand, thin or thick canes, a lean, more or fewer
 * leaves, fresh, pale old or dark culms, three leaf greens), the far hills are grown over
 * with misty bamboo, and the night is a lighter green-blue so the grove still reads.
 * FEATURES are drafts kept off (a tea pavilion, framing canes, a lantern boat). */
(function () {
'use strict';
const FEATURES = { pavilion: false, framing: false, boat: false };

const AF = window.AnkiForest;
const { hex, mix, mixHex, px, ellipseFill, rng, layer, hashStr, rgb, B4, clamp } = AF.u;
const H6 = a => a.map(hex);

// fresh jade, a deeper green and a cool sage for the leaves; a blue-green for the second kind.
// Tones run outline, shade, mid, lit, highlight; the canes use them too, so they yellow as well.
const JADE = H6(['#163424', '#2a6040', '#3f8a4e', '#6cb45c', '#a8d87a']);
const DEEP = H6(['#0e2419', '#1a4228', '#286236', '#468a44', '#7cb262']);
const SAGE = H6(['#182e28', '#335646', '#517a64', '#7aa286', '#b0cca8']);
const TEAL = H6(['#10302c', '#1f5448', '#2e7a62', '#4ea27a', '#8ccc98']);
const LAMP = '#ffcf7a', LAMP_D = '#e0763a';
const nightOf = env => env.mood.time === 'night';

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
  if (FEATURES.pavilion) pavilionHill(env, lg);
  grove(env, lg, near, x => rd.near(x), 'g3', 2);
  if (FEATURES.pavilion) pavilion(env, lg, env.pav);
}

/* ---------- b: the tea pavilion on its hill ----------
 * On the left third, on a bamboo hill whose top clears the tree line, so the forest never
 * hides it: an open little tea house on stilts, its paper screens lit warm in the rain. */
const PAV_X = 0.27, PAV_H = 15, PAV_CLEAR = 9, PAV_TOP = 0.08, HILL_MIN = 12;
function pavAt(env) {
  const { H, u, hor } = env, line = AF.treeLine(env);
  let base = Math.min(hor - HILL_MIN * u, line - PAV_CLEAR * u);
  const room = base - H * PAV_TOP, s = clamp(room / (PAV_H * u), 0.8, 1.15);
  base = Math.max(base, Math.round(H * PAV_TOP + PAV_H * u * s));
  return { x: Math.round(env.W * PAV_X), base: Math.round(base), s: s * u };
}
function pavilionHill(env, lg) {
  const th = env.theme, { W, u, hor } = env, P = env.pav = pavAt(env);
  const body = mix(mix(hex(th.far), hex(th.near), 0.8), hex(th.g1), 0.25), dark = mix(body, [0, 0, 0], 0.16), lite = mix(body, [255, 255, 255], 0.08);
  const rise = hor - P.base, half = Math.max(52 * u, rise * 2.6);
  for (let x = Math.floor(P.x - half); x <= P.x + half; x++) {
    if (x < 0 || x >= W) continue;
    const q = (x + 0.5 - P.x) / half, aq = Math.abs(q);
    const f = aq < 0.2 ? 0 : Math.pow((aq - 0.2) / 0.8, 1.5);
    const hs = hashStr('ph,' + x), stem = aq > 0.24 && hs % 3 === 0, tuft = stem ? 1 + (hs >> 8) % 3 : 0;
    const y0 = Math.round(P.base + rise * Math.min(1, f)) - tuft;
    for (let y = y0; y < hor; y++) {
      let c = q < 0 ? lite : body;
      if (stem || (y > y0 + 4 && B4[(y & 3) * 4 + (x & 3)] < 3)) c = dark;
      lg.fillStyle = rgb(c); lg.fillRect(x, y, 1, 1);
    }
  }
}
function pavilion(env, lg, P) {
  const th = env.theme, s = P.s, cx = P.x, night = nightOf(env), dusk = env.mood.time === 'dusk';
  const haze = hex(th.haze || th.far), C = (c, k = 1) => mix(hex(c), haze, (night ? 0.04 : 0.16) * k);
  const WOOD = C('#4a3226'), WOOD_D = C('#2e1e18'), WOOD_L = C('#7a5640'), ROOF = C('#2a3034', 0.5), ROOF_L = C('#5e6c70', 0.6);
  const PAPER = hex(night || dusk ? '#ffd88e' : '#f4dca4'), PAPER_D = hex(night || dusk ? '#e6a860' : '#d8b880');
  const paint = (c, x, y, w = 1, h = 1) => { lg.fillStyle = rgb(c); lg.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h))); };
  const r = v => Math.max(1, Math.round(v * s));
  const half = r(7), stilt = r(3), wallH = r(5), eave = half + r(4), roofH = r(4);
  let y = P.base;
  // a glow round the screens, stepped and soft
  const gy = y - stilt - Math.round(wallH / 2);
  for (const [rr, al] of [[16, 0.04], [11, 0.06], [7.5, 0.08]]) {
    const rx = Math.round(rr * s * 1.3), ry = Math.round(rr * s * 0.75);
    lg.fillStyle = `rgba(255,200,120,${(night ? al * 1.7 : dusk ? al * 1.3 : al).toFixed(3)})`;
    for (let dy = -ry; dy <= ry; dy++) { const w = Math.round(rx * Math.sqrt(1 - (dy / ry) ** 2)); lg.fillRect(cx - w, gy + dy, w * 2 + 1, 1); }
  }
  // stilts down into the hill, and the deck on them
  for (const sx of [-half + 1, -Math.round(half / 3), Math.round(half / 3), half - 1]) paint(WOOD_D, cx + sx, y - stilt + 1, 1, stilt);
  y -= stilt;
  paint(WOOD, cx - half - r(2), y, half * 2 + r(2) * 2 + 1, 1);
  paint(WOOD_L, cx - half - r(2), y - 1, half * 2 + r(2) * 2 + 1, 1);
  y -= 1;
  // paper screens between posts: warm, with their dark lattice
  for (let k = 0; k < wallH; k++) for (let dx = -half; dx <= half; dx++) {
    const post = dx === -half || dx === half || dx === 0;
    const latt = !post && (((dx + half) % 3 === 0) || k === Math.floor(wallH / 2));
    paint(post ? WOOD_D : latt ? PAPER_D : PAPER, cx + dx, y - k);
  }
  y -= wallH;
  // the roof: a wide dark hip with a wet sheen along its lower edge, the tips turned up
  for (let k = 0; k < roofH; k++) {
    const e = eave - Math.round(k * (eave - r(2)) / roofH);
    paint(k === 0 ? ROOF_L : ROOF, cx - e, y - k, e * 2 + 1, 1);
  }
  paint(ROOF, cx - eave - 1, y - 1); paint(ROOF, cx + eave + 1, y - 1);
  paint(ROOF_L, cx - eave - 1, y - 2); paint(ROOF_L, cx + eave + 1, y - 2);
  paint(ROOF, cx - r(2), y - roofH, r(2) * 2 + 1, 1);       // the ridge
  // a red lantern hanging from the right-hand eave, and a stove pipe on the roof
  paint(hex('#c44a2e'), cx + eave - 1, y + 1, 2, 2); paint(hex(LAMP), cx + eave, y + 1);
  paint(WOOD_D, cx + eave - 1, y + 3);
  P.smoke = { x: cx - r(4), y: y - roofH + 1 };
  paint(WOOD_D, P.smoke.x, P.smoke.y - 1, 1, 2);
}
/* thin smoke from the stove, rising and leaning off with the rain's wind */
function smoke(g, env, t) {
  const P = env.pav;
  if (!P || !P.smoke) return;
  const { u } = env, night = nightOf(env), n = 9, life = AF.u.per(6), tt = env.still ? 0 : t;
  for (let i = 0; i < n; i++) {
    const f = ((tt / life) + i / n) % 1, rise = f * 14 * u;
    const x = Math.round(P.smoke.x - f * 5 * u + Math.sin(f * 5 + i) * 0.8), y = Math.round(P.smoke.y - 2 - rise);
    const a = (1 - f) * (night ? 0.28 : 0.4);
    g.fillStyle = night ? `rgba(150,170,165,${a.toFixed(3)})` : `rgba(96,112,108,${(a * 0.9).toFixed(3)})`;
    g.fillRect(x, y, f > 0.35 ? 2 : 1, f > 0.6 ? 2 : 1);
  }
}

/* ---------- c: near canes framing the right edge ----------
 * Three big canes standing close, just inside the frame on the right, leaning in, with
 * long narrow leaves hanging into the sky; a heavy dark mass the boat on the left balances. */
function buildFraming(env) {
  const { W, H, u } = env, th = env.theme, night = nightOf(env);
  const [cv, g] = layer(W, H);
  const tint = th.tint ? hex(th.tint) : null, k = night ? 0.45 : (th.tintAmt || 0) * 1.4;
  const T = c => tint ? mix(hex(c), tint, k) : hex(c);
  const DK = T('#183a28'), MD = T('#2c6038'), LT = T('#4e8a4a'), HI = T('#86b46c'), JN = T('#10281c');
  const LF = [T('#163e28'), T('#265c36'), T('#3c7c44'), T('#62a058')];
  const SNOW = hex(night ? '#b8c6d4' : '#eef3f6');
  const canes = [{ x: W - 33 * u, w: 2, lean: -0.07 }, { x: W - 12 * u, w: 5, lean: -0.03 }, { x: W - 22 * u, w: 3, lean: -0.05 }, { x: W - 4 * u, w: 6, lean: -0.01 }];
  /* a bamboo leaf: long and narrow, hanging from its twig at a slant, widest a third along */
  const leafAt = (x0, y0, ang, len) => {
    const dx = Math.cos(ang), dy = Math.sin(ang);
    for (let e = 0; e <= len; e++) {
      const f = e / len, x = Math.round(x0 + dx * e), y = Math.round(y0 + dy * e + f * f * 2);
      g.fillStyle = rgb(LF[f < 0.45 ? 2 : 1]); g.fillRect(x, y, 1, 1);
      if (f > 0.12 && f < 0.6) { g.fillStyle = rgb(th.snow && f < 0.45 ? SNOW : f < 0.35 ? LF[3] : LF[2]); g.fillRect(x, y - 1, 1, 1); }
      g.fillStyle = rgb(LF[0]); g.fillRect(x, y + 1, 1, 1);
    }
  };
  const sprays = [];
  for (const cn of canes) {
    const w = Math.max(3, Math.round(cn.w * u)), joint = Math.round(17 * u);
    for (let y = H - 1; y >= -2; y--) {
      const x = Math.round(cn.x + (H - y) * cn.lean);
      const node = (y % joint) === 0;
      for (let q = 0; q < w; q++) {
        const c = node ? JN : q === 0 ? DK : q === 1 ? LT : q === 2 && w > 4 ? HI : q === w - 1 ? DK : MD;
        g.fillStyle = rgb(c); g.fillRect(x + q, y, 1, 1);
      }
      if (node) { g.fillStyle = rgb(th.snow ? SNOW : HI); g.fillRect(x + 1, y - 1, w - 2, 1); }
      if (node && y < H * 0.5 && y > -joint) sprays.push([x, y]);
    }
  }
  // from the upper joints a thin twig reaches in toward the picture, and its leaves hang in a fan
  const R = rng(91);
  for (const [x, y] of sprays) {
    const tw = Math.round((5 + R() * 12) * u), ty = y + Math.round(R() * 3 * u);
    g.fillStyle = rgb(DK); AF.u.pxLine(g, x - 1, y, x - tw, ty);
    const m = 4 + Math.floor(R() * 3);
    for (let i = 0; i < m; i++) {
      const at = x - Math.round(tw * (0.45 + 0.55 * (i / m))), ay = Math.round(y + (ty - y) * (0.45 + 0.55 * (i / m)));
      const ang = Math.PI * (0.62 + R() * 0.3) + (R() < 0.25 ? -0.5 : 0);  // down and out, a few lifted
      leafAt(at, ay, ang, Math.round((6 + R() * 6) * u));
    }
  }
  return cv;
}

/* ---------- c: the lantern boat ----------
 * A small flat boat moored by the left bank of the river, someone under a red paper umbrella
 * in it and a lantern hung from a pole at the bow, its light running down into the water. */
function boatSpot(env) {
  const S = env.river, land = AF.landOf(env), { W, H, hor, u } = env;
  if (!S || !S.vis) return null;
  const seen = (x, y) => x >= 0 && x < W && y >= 0 && y < H && S.vis[y * W + x] === 1;
  for (let p = 0.95; p > 0.5; p -= 0.03) for (const lane of [-0.5, -0.42, -0.34]) {
    const y = Math.round(hor + p * (H - hor)), x = Math.round(W * land.center(p) + lane * W * land.halfWidth(p, W));
    const L = Math.round((14 + p * 12) * u);
    if (x / W > 0.46 || y > H - 5 * u) continue;
    const a = Math.round(x - L / 2), b = Math.round(x + L / 2);
    if (seen(a, y + 1) && seen(b, y + 1) && seen(a, y - 1) && seen(x, y + 3)) return { x, y, L, p, seen };
  }
  return null;
}
function boat(g, env, t, B) {
  const night = nightOf(env), tt = env.still ? 0 : t, s = B.L / 16;
  const flick = 0.82 + 0.18 * Math.sin(tt * AF.u.cyc(2.1) + 1.3);
  const r = v => Math.max(1, Math.round(v * s));
  const { x, y, L, seen } = B, x0 = Math.round(x - L / 2);
  const HULL = night ? '#24160f' : '#3a2618', HULL_L = night ? '#4a3220' : '#6a4a30', RIM = night ? '#5e4430' : '#8a6a48';
  // the boat's shadow in the water, broken by the rain
  for (let j = 1; j <= r(3); j++) for (let dx = 0; dx < L; dx++) if ((dx + j) % 3 && seen(x0 + dx, y + j + 1)) { g.fillStyle = `rgba(10,24,22,${(0.35 - j * 0.06).toFixed(3)})`; g.fillRect(x0 + dx, y + j + 1, 1, 1); }
  // the hull: a low flat boat, the ends rising
  px(g, HULL, x0 + 1, y, L - 2, 1);
  px(g, HULL, x0, y - 1, L, 1);
  px(g, RIM, x0, y - 2, L, 1);
  px(g, HULL_L, x0 - 1, y - 3, 2, 1); px(g, HULL_L, x0 + L - 1, y - 3, 2, 1);
  px(g, HULL_L, x0 - 2, y - 4, 1, 1); px(g, HULL_L, x0 + L + 1, y - 4, 1, 1);
  // the figure, sitting towards the stern, in a dark blue coat
  const fx = x0 + Math.round(L * 0.62);
  px(g, night ? '#1a2234' : '#2a3654', fx - r(1), y - 2 - r(3), r(3), r(3));
  px(g, night ? '#c8a080' : '#e0b890', fx, y - 2 - r(3) - r(1), r(1) + (s > 1.2 ? 1 : 0), r(1));
  // the umbrella over them: oiled red paper with pale ribs
  const uy = y - 2 - r(3) - r(2) - 1, uw = r(5);
  const UR = night ? '#8a2c22' : '#b8402c', UL = night ? '#b04a34' : '#dc6a46';
  px(g, '#2a1a14', fx, uy, 1, r(3) + 1);                    // the handle
  px(g, UR, fx - uw, uy, uw * 2 + 1, 1);
  px(g, UR, fx - uw + 1, uy - 1, uw * 2 - 1, 1);
  px(g, UL, fx - uw + 3, uy - 2, uw * 2 - 5, 1);
  px(g, '#3a1e16', fx, uy - 3, 1, 1);
  for (let k = -uw + 1; k < uw; k += 3) px(g, UL, fx + k, uy, 1, 1);
  // the lantern on its pole at the bow
  const lx = x0 + r(2), ly = y - r(10);
  g.fillStyle = '#3a2a22'; g.fillRect(lx, ly, 1, y - 2 - ly); g.fillRect(lx, ly, r(3), 1);
  const ax = lx + r(3) - 1, ay = ly + 1, lw = Math.max(2, r(2)), lh = lw + 1;
  g.fillStyle = `rgba(255,200,120,${(0.14 * flick).toFixed(3)})`; g.fillRect(ax - lw - 1, ay - 2, lw * 3 + 2, lh + 5);
  g.fillStyle = `rgba(255,200,120,${(0.2 * flick).toFixed(3)})`; g.fillRect(ax - 2, ay - 1, lw + 4, lh + 3);
  px(g, LAMP, ax, ay, lw, lh); px(g, LAMP_D, ax, ay + lh - 1, lw, 1); px(g, '#4a3024', ax, ay - 1, lw, 1);
  if (lw > 2) px(g, '#fff0c0', ax + (lw >> 1), ay + 1, 1, lh - 2);
  // its light running down the water from under the boat
  const reach = Math.round(9 * s);
  for (let j = 1; j < reach; j++) {
    if (j % 3 === 2 || !seen(ax + (j % 2), y + j + 1)) continue;
    g.fillStyle = `rgba(255,190,100,${(0.45 * (1 - j / reach) * flick).toFixed(3)})`;
    g.fillRect(ax + (j % 2), y + j + 1, Math.max(1, lw - 1), 1);
  }
  // and two pale ripples along the hull where the rain meets it
  const ph = Math.floor(tt * 1.2) % 2;
  px(g, night ? 'rgba(150,190,170,.35)' : 'rgba(225,240,228,.5)', x0 - 3 + ph, y + 1, 2, 1);
  px(g, night ? 'rgba(150,190,170,.35)' : 'rgba(225,240,228,.5)', x0 + L + 1 - ph, y + 1, 2, 1);
}

/* ---------- the water and its lanterns (as shipped) ---------- */
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

function floatingLantern(g, x, y, lw, flick, reach, k, seen) {
  const lh = lw + 1;
  for (let j = 1; j < reach; j++) {
    if ((j + k) % 3 === 2 || !seen(x + (j % 2), y + j + 1)) continue;
    g.fillStyle = `rgba(255,190,100,${(0.5 * (1 - j / reach) * flick).toFixed(3)})`;
    g.fillRect(x + (j % 2), y + j + 1, Math.max(1, lw - 1), 1);
  }
  g.fillStyle = `rgba(255,200,120,${(0.12 * flick).toFixed(3)})`; g.fillRect(x - lw, y - lh - 2, lw * 3, lh * 2 + 2);
  g.fillStyle = `rgba(255,200,120,${(0.18 * flick).toFixed(3)})`; g.fillRect(x - 2, y - lh, lw + 4, lh + 2);
  g.fillStyle = '#3a2a22'; g.fillRect(x - 1, y + 1, lw + 2, 1);
  g.fillStyle = LAMP; g.fillRect(x, y - lh + 1, lw, lh);
  if (lw < 3) return;
  g.fillStyle = '#fff0c0'; g.fillRect(x + (lw >> 1) - (lw > 3 ? 1 : 0), y - lh + 2, lw > 3 ? 2 : 1, lh - 2);
  g.fillStyle = LAMP_D; g.fillRect(x, y, lw, 1);
  g.fillStyle = '#4a3024'; g.fillRect(x, y - lh, lw, 1);
}

function riverLanterns(g, env, t) {
  const S = env.river, land = AF.landOf(env); if (!S.vis) return;
  const { W, H, u, hor } = env, R = rng(505), tt = env.still ? 0 : t;
  const seen = (x, y) => x >= 0 && x < W && y >= 0 && y < H && S.vis[y * W + x] === 1;
  if (FEATURES.boat && env.boatAt === undefined) env.boatAt = boatSpot(env);
  const B = FEATURES.boat ? env.boatAt : null;
  let boatDone = !B;
  const boats = [], gaps = [], lanes = [];
  for (let k = 0; k < 9; k++) { gaps.push(R()); lanes.push(R()); }
  for (let k = 0; k < 9; k++) {
    const at = AF.u.handover(k, tt), lane = (AF.u.along(lanes, at) - 0.5) * 0.9;
    const q = ((at + AF.u.along(gaps, at) * 0.6) / 9 + (AF.LOOP ? 0 : tt * 0.012)) % 1;
    boats.push({ p: 0.06 + Math.pow(q, 1.2) * 0.94, lane, at });
  }
  boats.sort((a, b) => a.p - b.p);
  for (const { p, lane, at } of boats) {
    if (!boatDone && p > B.p) { boat(g, env, t, B); boatDone = true; }
    const ph = AF.LOOP ? at % 9 : at;
    const y = Math.round(hor + p * (H - hor) + Math.sin(tt * AF.u.cyc(0.8) + ph) * 0.5), lw = Math.max(1, Math.round((0.8 + p * 3) * u));
    const x = Math.round(W * land.center(p) + lane * W * land.halfWidth(p, W) - lw / 2);
    if (!seen(x + (lw >> 1), y + 1)) continue;
    if (B && Math.abs(y - B.y) < 7 * u && x + lw > B.x - B.L / 2 - 3 && x < B.x + B.L / 2 + 3) continue;  // passing behind the boat
    floatingLantern(g, x, y, lw, 0.8 + 0.2 * Math.sin(tt * AF.u.cyc(2.3) + ph * 1.7), Math.round((2 + p * 8) * u), AF.LOOP ? 0 : at, seen);
  }
  if (!boatDone) boat(g, env, t, B);
}

AF.env('bamboo', {
  fx: { init(st, { env }) { calmWater(env); } },

  theme(th) { Object.assign(th, { g0: mixHex(th.g0, '#5e8a48', 0.55), g1: mixHex(th.g1, '#3a6436', 0.55), grass: mixHex(th.grass, '#7aa85a', 0.5) }); },
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
    th.water = nightTime ? '#142e30' : dusk ? '#23403c' : '#2a5048';
    th.clouds = { n: 5, top: nightTime ? '#2a4042' : '#c4d2c8', bot: nightTime ? '#1c3032' : '#9eb2a8', a: 235, y0: 0, dy: 0.12, speed: 0.8 };
    th.deck = { n: 3, top: nightTime ? '#20343a' : '#b0c2b6', bot: nightTime ? '#162828' : '#8ea49a', a: 245 };
    th.rain = 170; th.splashes = 30;  // steady, not a downpour (as shipped)
  },
  prepare(env) {
    const night = env.mood.time === 'night';
    if (env.theme.rain) env.fxColors = { rain: night ? 'rgba(150,190,170,.4)' : 'rgba(225,240,228,.5)', rainFar: night ? 'rgba(150,190,170,.2)' : 'rgba(225,240,228,.28)', splash: 'rgba(235,245,238,.8)' };
  },
  pals: { rounds: [JADE, DEEP, SAGE], pine: TEAL, bark: { l: hex('#6a9a4a'), m: hex('#4a7a3a'), d: hex('#2e5428') },
    leaf: hex('#6cb45c'), leafL: hex('#a8d87a'), stem: hex('#3f8a4e') },

  tree: {
    width: ({ h, t }) => t.stage >= 1 ? character(t, h).w : 0,
    body: c => (c.t.stage >= 1 ? clump(c) : null),
    pixel(col, { x, y, pal, c }) {
      const k = c.cane && c.cane[y * c.W + x];
      if (!k) return col;
      const T = CANE_TONES[c.caneShade || 0];
      if (k === 3) return pal[T[2]];
      if (k === 1 && c.cane[(y + 1) * c.W + x] === 3) return pal[T[4]];
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

  treeBase(env, g, p) {
    const t = p.it;
    if (t.stage < 2 || t.fromFront > 4 || t.seed % 6 !== 0) return;
    const x = Math.round(p.x + (t.seed % 2 ? 4 : -7)), y = Math.round(p.y), stone = '#8a9088', dark = '#5a605a';
    g.fillStyle = 'rgba(255,200,120,.16)'; g.fillRect(x - 2, y - 7, 7, 7);
    px(g, dark, x, y - 1, 3, 1); px(g, stone, x + 1, y - 3, 1, 2);
    px(g, stone, x, y - 5, 3, 2); px(g, LAMP, x + 1, y - 5, 1, 1);
    px(g, dark, x - 1, y - 6, 5, 1); px(g, stone, x + 1, y - 7, 1, 1);
  },

  frame(g, env, t) {
    if (FEATURES.pavilion) smoke(g, env, t);
    if (!env.theme.frozen) {
      if (env.river) riverLanterns(g, env, t);
      else if (env.water) {
        const L = env.water, { W, u } = env, R = rng(505), n = 13, v = 0.4 * u;
        for (let k = 0; k < n; k++) {
          const near = k % 2 === 0, lw = near ? Math.max(4, Math.round(3.6 * u)) : 3;
          const lane = near ? 0.55 + R() * 0.3 : 0.05 + R() * 0.25, y = Math.round(L.y0 + 2 + lane * Math.max(1, L.lh - 4));
          const x = Math.round(((k / n) * (W + 12) + R() * 10 + (AF.LOOP ? t * AF.u.drift(v * (near ? 1 : 0.7), W + 12) : t * v * (near ? 1 : 0.7))) % (W + 12)) - 6;
          const flick = 0.8 + 0.2 * Math.sin(t * AF.u.cyc(2.3) + k * 1.7), yb = y + Math.round(Math.sin(t * AF.u.cyc(0.8) + k) * 0.5);
          floatingLantern(g, x, yb, lw, flick, Math.min((near ? 10 : 5) * u, L.y0 + L.lh - yb - 2), k, () => true);
        }
      }
    }
    if (FEATURES.framing) {
      if (!env.framing) env.framing = buildFraming(env);
      g.drawImage(env.framing, 0, 0);
    }
  },
});
})();

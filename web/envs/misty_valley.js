/* Memory Forest - the misty valley environment.
 * Everything this environment is lives here: delete it and misty_valley.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * A valley that has not woken up yet: dew-blue trees rimed with frost on their tops, and
 * the low sun breaking through the fog in long dithered beams that fan out over the sky
 * and fall across the whole forest. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, layer, B4, TAU } = AF.u;
const BEAM_CYCLE = 150;  // seconds for the light to shift to the other beams and back
const H6 = a => a.map(hex);

// dew blue-green, and a colder blue for every other tree; tones run outline .. highlight
const ROUNDS = [H6(['#16283a', '#23405a', '#316068', '#468478', '#72a898']),
  H6(['#182a40', '#26405e', '#345c7a', '#4a7e96', '#7aa6b8'])];
const PINE = H6(['#122236', '#1c3448', '#284c5c', '#3a6a72', '#62948e']);
const MINE = new Set(ROUNDS.concat([PINE]));
const FROST0 = hex('#e6f4f2'), FROST_D0 = hex('#b8d8d8');
// the rime catching the hour's light (the day's is the white above)
const FROSTS = { dawn: H6(['#f8e2dc', '#d8c4cc']), golden_hour: H6(['#f8ecd0', '#d8ccb4']), dusk: H6(['#e8d8ec', '#bcb0cc']), night: H6(['#e2eafc', '#aebcdc']) };

/* The beams: a fan of rays from the sun, lit wherever the ray pattern beats the Bayer
 * threshold, so they come out as dithered pixel light rather than a smooth wash. Built
 * once per panel size (two sets, offset in angle, so the light can shift very slowly). */
function beams(env, phase) {
  const { W, H, u, hor } = env, o = env.theme.orb;
  const sx = W * o.x, sy = H * o.y, [cv, g] = layer(W, H), img = g.createImageData(W, H), d = img.data;
  const warm = hex(o.kind === 'moon' ? '#e8eefa' : '#fff8dc'), cool = hex(o.kind === 'moon' ? '#1a2440' : '#9a8aa8'), reach = W * 0.95;
  // eleven rays of uneven width, fixed per panel so they never flicker
  const rays = [];
  for (let k = 0; k < 11; k++) rays.push({ a: k * TAU / 11 + phase + Math.sin(k * 7.3) * 0.12, w: 0.035 + 0.03 * Math.abs(Math.sin(k * 3.1)), s: 0.6 + 0.4 * Math.abs(Math.sin(k * 5.7)) });
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const dx = x - sx, dy = y - sy, dist = Math.hypot(dx, dy);
    if (dist < o.r * u * 1.6 || dist > reach) continue;
    let a = Math.atan2(dy, dx); a = ((a % TAU) + TAU) % TAU;
    let best = 0, gap = 1;
    for (const r of rays) {
      let da = Math.abs(a - ((r.a % TAU) + TAU) % TAU); da = Math.min(da, TAU - da);
      if (da < r.w) best = Math.max(best, (1 - da / r.w) * r.s);
      gap = Math.min(gap, da / (r.w * 2.4));
    }
    // strongest near the sun, fading out; weaker below the horizon so the trees stay clear
    const fall = Math.pow(1 - dist / reach, 1.1) * (y > hor ? 0.15 : 1), th = B4[(y % 4) * 4 + x % 4] + 0.5;
    const i = (y * W + x) * 4;
    if (best) {
      const v = best * fall;
      if (v * 16 * 1.5 <= th) continue;
      d[i] = warm[0]; d[i + 1] = warm[1]; d[i + 2] = warm[2];
      d[i + 3] = v > 0.45 ? 175 : v > 0.22 ? 130 : 90;  // three steps of light, never a gradient
    } else if (o.kind !== 'moon' && gap >= 1 && y < hor && fall * 16 * 0.55 > th) {
      // the fog left in shadow between the beams, so the light has something to cut through
      d[i] = cool[0]; d[i + 1] = cool[1]; d[i + 2] = cool[2]; d[i + 3] = 60;
    }
  }
  g.putImageData(img, 0, 0);
  return cv;
}

/* ---------- the peak ----------
 * The scene's snow-capped peak, its own (stood in for the shared `peak` through env.landmarkKey,
 * see AF.markOf): placed as that one is, so the ground's random numbers stay the same. */
AF.landmark('misty_peak', {
  slot: 'back',
  place: (env, R) => env.W * (0.55 + R() * 0.25),
  draw(env, lg, px) {
    // lifted with the tree line as the forest grows, so its cap and shoulders always show
    const th = env.theme, { W, H, u, hor } = env, py = Math.round(Math.max(H * 0.1, Math.min(hor - 44 * u, AF.treeLine(env) - 30 * u)));
    const cap = hex(AF.u.mixHex('#f4f7fb', th.haze, 0.15));
    const body = hex(AF.u.mixHex(th.far, th.sky[th.sky.length - 1], 0.25));
    // the far side in shadow, away from the light: cooler, a step darker, taking the sky's own blue
    const sunLeft = !th.orb || th.orb.x * W < px, shadeOf = (c, k) => AF.u.mix(AF.u.mix(c, hex(th.sky[1]), k), [20, 26, 44], k * 0.35);
    const capS = shadeOf(cap, 0.3), bodyS = shadeOf(body, 0.22);
    const paint = (c, x, y) => { lg.fillStyle = AF.u.rgb(c); lg.fillRect(x, y, 1, 1); };
    for (let x = 0; x < W; x++) {
      const yTop = Math.round(py + Math.abs(x - px) * 0.62 + (Math.abs(x - px) < 3 * u ? 1.2 * u : 0));
      if (yTop >= hor) continue;
      const lit = (sunLeft ? x <= px : x >= px) !== (Math.abs(x - px) <= 1 && (x + yTop) % 2 === 0);  // (a dithered seam down the ridge)
      const snowTo = py + 14 * u - Math.sin(x * 0.9) * 1.5 * u;
      for (let y = yTop; y < hor; y++) {
        const snow = y < snowTo;
        let c = snow ? (lit ? cap : capS) : (lit ? body : bodyS);
        if (lit && snow && y === yTop && Math.abs(x - px) > 1) c = AF.u.mix(c, [255, 255, 255], 0.35);  // the lit ridge, in the snow
        paint(c, x, y);
      }
    }
  },
});

/* the study calendar's tiles rimed like the crowns: a broken line of frost along the top edge and
 * a few crystals of it below, on the shade's own face, its corners left off as the plain tiles' are */
const RIME = [236, 248, 246];
function calendarTile(g, pal, edge, v, T) {
  const n = T - 1;  // (the last row and column: the gap between tiles)
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    if ((x === 0 || x === n - 1) && (y === 0 || y === n - 1)) continue;
    const frost = y === 0 ? ((x + v) % 3 === 2 ? 0.25 : 0.62) : y === 1 && (x + v) % 4 === 1 ? 0.32 : 0;
    g.fillStyle = AF.u.rgb(frost ? AF.u.mix(pal[0], RIME, frost) : pal[0]);
    g.fillRect(x, y, 1, 1);
  }
}

AF.env('misty_valley', {
  // (its own peak, above)
  calendarTile,
  deepBands: 3,  // the oldest forest stays low enough to leave the peak and the sun their sky
  prepare(env) { if (env.mood.landmark === 'peak') env.landmarkKey = 'misty_peak'; },


  pals: { rounds: ROUNDS, pine: PINE, bark: { l: hex('#6a6a70'), m: hex('#4a4c56'), d: hex('#2e3040') },
    leaf: hex('#6aa0a0'), leafL: hex('#c8e8e4'), stem: hex('#4a7a7a') },

  /* rime on everything the cold air touches first: the top edge of every crown, and a
   * dither of frost across its lit side */
  tree: {
    pixel(col, { x, y, tn, pal, c }) {
      if (!MINE.has(pal) || tn === 0) return col;
      const [FROST, FROST_D] = (c.th.mvHour && FROSTS[c.th.mvHour]) || [FROST0, FROST_D0];
      if (!c.inside(x, y - 1)) return tn >= 2 ? FROST : FROST_D;
      if (!c.inside(x, y - 2) && tn >= 2 && (x + y) & 1) return FROST_D;
      if (tn === 4 && (x * 3 + y) % 7 === 0) return FROST_D;
      return col;
    },
  },

  after(th, mood) {
    th.mvHour = th.snow ? null : mood.time;  // (whose light the rime catches; snow keeps it white)
    // by day and by night a richer sky behind the mist: a deeper top, a warmer (by night, a faintly
    // lit) band low down, so the sun's rays and the peaks have more to stand against. Only with
    // the sun or moon out: under an overcast, rain or storm sky there is nothing to light it
    if ((mood.time === 'day' || mood.time === 'night') && th.orb && !th.deck) {
      const night = mood.time === 'night', n = th.sky.length;
      th.sky = th.sky.map((c, i) => i < 2 ? AF.u.mixHex(c, night ? '#02030c' : '#24448a', 0.2) : i >= n - 2 ? AF.u.mixHex(c, night ? '#3e4474' : '#ffe0b0', 0.22) : c);
    }
    // a sunrise worth getting up for: the fog warms to peach and gold low in the sky,
    // and stays pale enough that the dark dew-blue trees stand out against it
    if (mood.time === 'dawn' || mood.time === 'golden_hour') {
      th.sky = th.sky.map((c, i) => AF.u.mixHex(c, ['#aab4d0', '#c4bcd6', '#e8c8c8', '#f6d2b4', '#fadcb0', '#fce6c4'][i] || c, 0.55));
      if (th.orb) { th.orb.c = '#fff4d8'; th.orb.soft = false; th.orb.r = 9; }
    }
    if (th.fog) {  // a light morning mist: enough to layer the valley, not to hide the trees
      const FOG = { night: ['#3a4670', '#33405f'], dusk: ['#a898b8', '#9a8cae'], dawn: ['#e0ccd0', '#d4c4cc'], golden_hour: ['#e6d2bc', '#d8c8b6'] }[mood.time] || ['#c4d0da', '#bcc8d4'];
      th.fog = AF.u.mixHex(th.fog, FOG[0], 0.7); th.haze = AF.u.mixHex(th.haze, FOG[1], 0.6);
      th.fogAmt = 0.12; th.hzStep = Math.min(th.hzStep, 0.11);
    }
    // the sun on the left third by day, so the light and the peak balance across the view
    if (th.orb && th.orb.kind === 'sun' && (mood.time === 'day' || mood.time === 'golden_hour')) th.orb.x = 0.24;
    th.glints = Math.max(th.glints || 0, th.rain || th.snow ? 0 : 18);  // dew catching the light
    th.beams = !!th.orb && !th.rain;
    if (th.rain && th.clouds) { th.clouds.top = AF.u.mixHex(th.clouds.top, '#8c9ab8', 0.45); th.clouds.bot = AF.u.mixHex(th.clouds.bot, '#4a5674', 0.45); }
  },

  frame(g, env, t) {
    if (!env.theme.beams) return;
    if (!env.mvBeams) env.mvBeams = [beams(env, 0), beams(env, 0.12)];
    // the light shifts from one set of beams to the other over a couple of minutes
    // moonbeams are only a ghost of the dawn's
    const k = 0.5 + 0.5 * Math.sin(AF.LOOP ? t * AF.u.cyc(TAU / BEAM_CYCLE) : t * TAU / BEAM_CYCLE), m = env.theme.orb.kind === 'moon' ? 0.35 : 0.8;
    g.save();
    g.globalAlpha = (1 - k * 0.8) * m; g.drawImage(env.mvBeams[0], 0, 0);
    g.globalAlpha = (0.2 + k * 0.8) * m; g.drawImage(env.mvBeams[1], 0, 0);
    g.restore();
  },
});
})();

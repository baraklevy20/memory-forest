/* A five-tiered temple far off in the mist: upturned eaves with deep shadow beneath them,
 * a lit and a shaded side to every wall, a ringed spire, and a lantern at each eave tip. Its
 * foot is lost in a bank of mist, so only the upper roofs show over the forest. It is lifted
 * with the tree line, so a big forest never hides it (and it keeps the far forest to a few
 * bands, `deepBands`, for the same reason). Its windows and lanterns glow faintly by day and
 * warm after dusk; snow settles on its roofs; fog takes it, as fog takes all far things.
 * Every colour comes from the scene's own theme, so it sits in any scenery. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, rgb, hashStr } = AF.u;

// its height in env.u at full size, and how near the top edge its spire may come (share of
// the height); a forest too tall for that makes the temple a little smaller instead
const TALL = 50, TOP = 0.06, MIN_SCALE = 0.7;
// how much of it may sink behind the canopy, and how high it stands over the horizon at least
const SUNK = 0.3, OVER_HORIZON = 4;
// how far its colours fade toward the far haze: in rain, by day, at night
const AWAY_RAIN = 0.42, AWAY = 0.3, AWAY_NIGHT = 0.3;
const WALL = '#8a3a2c', WALL_D = '#5e2620', ROOF = '#1e2428', ROOF_L = '#56646a', UNDER = '#14181a';
const GLOW = '#ffc874', WIN = '#ffd890', DIM_GLOW = '#e0a060', DIM_WIN = '#c88a50', GILT = '#c09a50';
const SNOW = '#eef3f6', SNOW_NIGHT = '#b8c6d4';

function placeOf(env, x) {
  const { H, u, hor } = env, line = AF.treeLine(env);
  const base = Math.round(Math.min(hor - OVER_HORIZON * u, line + TALL * u * SUNK));
  const top = base - TALL * u, s = top < H * TOP ? Math.max(MIN_SCALE, (base - H * TOP) / (TALL * u)) : 1;
  return { x, base, s: s * u };
}

AF.landmark('pagoda', {
  slot: 'land',
  deepBands: 2,
  // (mirrored to the right third when the moon or sun hangs over the left one, as the natural night moon
  // does at 0.22: behind the spire the two read as one shape. One R() either way, so nothing else moves)
  place: (env, R) => { const x = 0.16 + R() * 0.1, o = env.theme.orb; return Math.round(env.W * (o && o.y < 0.3 && Math.abs(o.x - 0.21) < 0.18 ? 1 - x : x)); },
  draw(env, lg, x) {
    const th = env.theme, P = placeOf(env, x), s = P.s, cx = P.x, paint = AF.painter(lg);
    const time = env.mood.time, night = time === 'night', lit = night || time === 'dusk';
    const skyLow = hex(th.sky[Math.max(0, th.sky.length - 3)]), haze = mix(hex(th.haze || th.far), skyLow, 0.5);
    const away = night ? AWAY_NIGHT : th.rain ? AWAY_RAIN : AWAY, tint = th.tint ? hex(th.tint) : null;
    const C = (c, k = 1) => {
      let col = mix(hex(c), haze, away * k);
      if (tint) col = mix(col, tint, Math.min(0.6, (th.tintAmt || 0) * 1.2));
      return col;
    };
    const wall = C(WALL), wallD = C(WALL_D), roof = C(ROOF, 0.8), roofL = C(ROOF_L, 0.8), under = C(UNDER, 0.7);
    const glow = lit ? hex(GLOW) : C(DIM_GLOW, 0.6), win = lit ? hex(WIN) : C(DIM_WIN, 0.7);
    const snow = th.snow ? C(night ? SNOW_NIGHT : SNOW, 0.5) : null;
    const r = v => Math.max(1, Math.round(v * s));
    if (lit) {  // a soft warm light round the temple, in stepped ovals
      const gy = P.base - Math.round(TALL * s * 0.55);
      for (const [rr, al] of [[22, 0.035], [15, 0.05], [9, 0.07]]) {
        const rx = Math.round(rr * s * 0.8), ry = Math.round(rr * s * 1.2);
        lg.fillStyle = `rgba(255,196,120,${(night ? al * 1.5 : al).toFixed(3)})`;
        for (let dy = -ry; dy <= ry; dy++) { const w = Math.round(rx * Math.sqrt(1 - (dy / ry) ** 2)); lg.fillRect(cx - w, gy + dy, w * 2 + 1, 1); }
      }
    }
    let y = P.base, half = r(7);
    const wallH = r(4.2), roofH = r(3);
    for (let tier = 0; tier < 5; tier++) {
      // the wall: a lit side, a shaded side, a window in the middle
      for (let k = 0; k < wallH; k++) {
        paint(wall, cx - half, y - k, half + Math.floor(half / 3) + 1, 1);
        paint(wallD, cx + Math.floor(half / 3) + 1, y - k, half - Math.floor(half / 3), 1);
      }
      paint(win, cx - 1, y - Math.round(wallH * 0.6), 2, Math.max(1, wallH - 2));
      y -= wallH;
      // the roof: deep shadow under the eave, a concave sweep up to the next wall, the tips turned up
      const eave = half + r(3.2);
      paint(under, cx - eave + 1, y, eave * 2 - 1, 1);
      for (let k = 1; k <= roofH; k++) {
        const e = Math.round(eave - (eave - half + 1) * Math.pow((k - 1) / roofH, 0.7));
        paint(snow && k === roofH ? snow : k === 1 ? roofL : roof, cx - e, y - k, e * 2 + 1, 1);
        paint(snow && k === roofH ? snow : roofL, cx - e, y - k);  // the lit edge
      }
      paint(roof, cx - eave - 1, y - 1); paint(roof, cx + eave + 1, y - 1);
      paint(roofL, cx - eave - 2, y - 2); paint(roofL, cx + eave + 2, y - 2);
      paint(glow, cx - eave, y + 1); paint(glow, cx + eave, y + 1);  // a lantern at each eave tip
      y -= roofH;
      half = Math.max(2, Math.round(half - s));
    }
    // the spire, with its rings and a gilt tip
    const sp = r(7);
    paint(roofL, cx, y - sp + 1, 1, sp);
    for (let k = 1; k < sp - 2; k += 2) paint(roof, cx - 1, y - k, 3, 1);
    paint(lit ? glow : C(GILT, 0.5), cx, y - sp);
    // the mist it stands in: long thin streaks across its lower tiers, each row its own
    // length, thickening toward the foot (thinner on a clear day)
    const mist = mix(skyLow, hex(th.haze || th.far), 0.25), y0 = P.base - Math.round(TALL * s * 0.45);
    const thick = th.rain || th.fog ? 1 : 0.75;
    for (let yy = y0; yy <= P.base + 2; yy++) {
      const f = (yy - y0) / (P.base + 2 - y0), hs = hashStr('pagoda mist,' + yy);
      const span = Math.round((16 + 16 * f + (hs % 9)) * s), off = Math.round(((hs >> 5) % 7 - 3) * s);
      const a = Math.min(0.92, 0.25 + f * 0.75) * ((yy & 1) && f < 0.6 ? 0.6 : 1) * thick;
      lg.fillStyle = rgb(mist, a.toFixed(3));
      lg.fillRect(cx - span + off, yy, span * 2, 1);
    }
  },
});
})();

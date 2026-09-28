/* Memory Forest — pixel engine: the sky, with its sun or phased moon, rainbow and retro sun. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, layer, B4 } = AF.u;
const { H6 } = AF.pixel;

// the rainbow: centred RAINBOW.x across, its centre RAINBOW.drop below the horizon, the
// inner edge RAINBOW.r out, six bands RAINBOW.band wide (all in env.u), fading out
// RAINBOW.fade above the horizon and never more than RAINBOW.strength opaque
const RAINBOW = { x: 0.42, drop: 26, r: 62, band: 1.6, strength: 0.35, fade: 18 };

/* sky: dithered bands, sun or phased moon (soft in fog), rainbow and striped retro sun;
 * an environment paints its own sky through skyPixel and sky */
function drawSky(env) {
  const th = env.theme, { W, H, u, hor } = env;
  const [sky, sg] = layer(W, H), si = sg.createImageData(W, H), sd = si.data, stops = th.sky.map(hex), o = th.orb;
  const ox = o ? W * o.x : 0, oy = o ? H * o.y : 0, orr = o ? o.r * u : 0, oc = o ? hex(o.c) : null, oc2 = o && o.c2 ? hex(o.c2) : null, og = o ? hex(o.glow || o.c) : null;
  let shadowX = null;
  if (o && o.kind === 'moon' && o.phase != null && !o.full) { const k = o.phase * 2; shadowX = ox + (k <= 1 ? -2 * orr * k : 2 * orr * (2 - k)); }
  const rb = th.rainbow ? { x: W * RAINBOW.x, y: hor + RAINBOW.drop * u, r0: RAINBOW.r * u, cols: H6(['#e8837a', '#f0b27a', '#f1dc86', '#9fd49a', '#8fb8e0', '#b5a0d8']) } : null;
  const R = rng(91);
  // an environment may paint into the sky itself: behind the orb, and in front of it
  const spec = AF.envOf(env), skyPixel = spec.skyPixel, skyCtx = skyPixel ? { W, H, hor, u, th, B4, R } : null;
  const skyEnd = AF.landOf(env).skyEnd ? AF.landOf(env).skyEnd(env) : hor - 1;
  // the retro sun's bands: cut out of its lower half only, thin near the middle and
  // widening as they fall. Measured from a whole-pixel centre so the bands come out the
  // same thickness whatever size the panel is.
  const oyR = Math.round(oy), cutAt = y => {
    if (!o || !o.stripes || y <= oyR) return false;
    const deep = (y - oyR) / orr;
    return deep > 0.05 && (y - oyR) % 4 < Math.min(3, 1 + Math.floor(deep * 2.2));
  };
  for (let y = 0; y < H; y++) {
    const tt = Math.min(1, y / skyEnd) * (stops.length - 1), i0 = Math.min(stops.length - 2, Math.floor(tt)), f = tt - i0;
    const cut = cutAt(y);
    for (let x = 0; x < W; x++) {
      let c = f * 16 > B4[(y % 4) * 4 + x % 4] + 0.5 ? stops[i0 + 1] : stops[i0];
      if (skyPixel) c = skyPixel(c, x, y, skyCtx, 'behind') || c;
      if (rb && y < hor) { const dd = Math.hypot(x - rb.x, y - rb.y) - rb.r0, bw = RAINBOW.band * u, bi = Math.floor(dd / bw); if (bi >= 0 && bi < rb.cols.length) c = mix(c, rb.cols[bi], RAINBOW.strength * Math.min(1, (hor - y) / (RAINBOW.fade * u))); }
      if (o) {
        const dist = Math.hypot(x - ox, y - oy);
        if (dist < orr) {
          const shadowed = shadowX !== null && Math.hypot(x - shadowX, y - oy) < orr;
          const edge = o.soft && dist > orr * 0.7 && B4[(y % 4) * 4 + x % 4] < (dist - orr * 0.7) / (orr * 0.3) * 16;
          // a band is the sky showing through the sun, so it is simply left unpainted
          if (!cut && !shadowed && !edge) c = oc2 ? mix(oc, oc2, (y - (oy - orr)) / (2 * orr)) : oc;
          else if (shadowed) c = mix(c, oc, 0.08);
        } else if (o.halo && dist < orr + o.halo * u && (x + y) % 2 === 0) c = mix(c, og, 0.55);
      }
      if (skyPixel) c = skyPixel(c, x, y, skyCtx, 'over') || c;
      const i = (y * W + x) * 4; sd[i] = c[0]; sd[i + 1] = c[1]; sd[i + 2] = c[2]; sd[i + 3] = 255;
    }
  }
  sg.putImageData(si, 0, 0);
  if (spec.sky) spec.sky(env, sg, rng(env.data.forestSeed || 5));
  return sky;
}

AF.pixel.drawSky = drawSky;
})();

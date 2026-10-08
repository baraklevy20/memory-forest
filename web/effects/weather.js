/* Memory Forest — the weather's effects: clouds and cloud decks, rain in two depths with
 * its splashes and rings on still water, lightning, snow, wind gusts, drifting fog banks
 * and the glints after rain. Each registers with effects.js, which runs them in order. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, layer, pxLine, B4 } = AF.u;
const part = AF.fx.part;

// seconds: lightning and a gust of wind each get one roll of the dice per window
const LIGHTNING_WINDOW = 17, GUST_WINDOW = 23, GUST_SECS = 2.6;
// the chance that a window brings lightning, or a gust
const LIGHTNING_CHANCE = 0.15, GUST_CHANCE = 0.2;
// rain falls sideways this much (of its speed), more in a storm
const RAIN_DRIFT = 0.18, STORM_DRIFT = 0.35;
// the share of the drops that fall behind the land, slower and fainter
const FAR_RAIN_SHARE = 0.4, FAR_RAIN_SPEED = 0.7;
// the chance that a flake is a big one, and in deep snow
const BIG_FLAKE_CHANCE = 0.22, DEEP_BIG_FLAKE_CHANCE = 0.4;
// clouds drift in the top of the sky unless the theme says where
const CLOUD_TOP = 0.04, CLOUD_DEPTH = 0.22;
// wind-blown leaves on a gust, fog banks drifting through, raindrops ringing on still water
const WIND_LEAVES = 26, FOG_BANKS = 5, RINGS = 24;
const FOG_BANK_STRENGTH = 0.24, FOG_BANK_ALPHA = 110;

function pxCloud(R, w, h, topC, botC, alpha, sparkle) {
  const [cv, g] = layer(w, h), img = g.createImageData(w, h), d = img.data;
  const blobs = []; for (let k = 0; k < 4; k++) blobs.push({ x: w * (0.2 + 0.6 * R()), y: h * (0.45 + 0.25 * R()), rx: w * (0.18 + 0.16 * R()), ry: h * (0.3 + 0.2 * R()) });
  blobs.push({ x: w / 2, y: h * 0.7, rx: w * 0.48, ry: h * 0.3 });
  const top = hex(topC), bot = hex(botC);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (!blobs.some(b => ((x + 0.5 - b.x) / b.rx) ** 2 + ((y + 0.5 - b.y) / b.ry) ** 2 <= 1)) continue;
    let c = y > h * 0.62 ? bot : top;
    if (sparkle) {  // sugar floss: a soft swirl of the lighter colour and a few sugar sparkles
      if (Math.sin(x * 0.35 + y * 0.9) > 0.75 && y <= h * 0.62) c = mix(top, [255, 255, 255], 0.45);
      if (((x * 7 + y * 13) % 29) === 0) c = [255, 255, 255];
    }
    const i = (y * w + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = alpha;
  }
  g.putImageData(img, 0, 0); return cv;
}

function fogBank(w, h, col, strength) {
  const [cv, g] = layer(w, h), im = g.createImageData(w, h), c = hex(col);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const q = ((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2; if (q > 1) continue;
    if ((1 - q) * strength * 16 < B4[(y % 4) * 4 + x % 4] + 0.5) continue;
    const i = (y * w + x) * 4; im.data[i] = c[0]; im.data[i + 1] = c[1]; im.data[i + 2] = c[2]; im.data[i + 3] = FOG_BANK_ALPHA;
  }
  g.putImageData(im, 0, 0); return cv;
}

part('deck', {
  init(st, { th, A, W, H, u }) {
    if (th.deck && th.deck.n) for (let i = 0; i < th.deck.n; i++) {
      const w = Math.round((60 + A() * 30) * u), h = Math.round((8 + A() * 4) * u);
      st.deck.push({ img: pxCloud(A, w, h, th.deck.top, th.deck.bot, th.deck.a), x: A() * W, y: Math.round(H * A() * 0.06), v: (0.3 + A() * 0.2) * u });
    }
  },
  back(g, env, t, st) {
    const { W } = env;
    for (const c of st.deck) { const x = ((c.x + t * AF.u.drift(c.v, W + c.img.width)) % (W + c.img.width)) - c.img.width; g.drawImage(c.img, Math.round(x), c.y); }
  },
});

part('clouds', {
  init(st, { th, A, W, H, u }) {
    if (th.clouds && th.clouds.n) for (let i = 0; i < th.clouds.n; i++) {
      const w = Math.round((26 + A() * 26) * u), h = Math.round((6 + A() * 6) * u);
      const pair = th.cloudPairs ? th.cloudPairs[i % th.cloudPairs.length] : [th.clouds.top, th.clouds.bot];
      st.clouds.push({ img: pxCloud(A, w, h, pair[0], pair[1], th.clouds.a, th.cloudSparkle), x: A() * W, y: Math.round(H * (th.clouds.y0 != null ? th.clouds.y0 : CLOUD_TOP) + A() * H * (th.clouds.dy || CLOUD_DEPTH)), v: (0.8 + A() * 0.8) * u * (th.clouds.speed || 1) });
    }
  },
  back(g, env, t, st) {
    const { W } = env;
    for (const c of st.clouds) { const x = ((c.x + (AF.LOOP ? t * AF.u.drift(c.v * 0.9, W + c.img.width) : t * c.v * 0.9)) % (W + c.img.width)) - c.img.width; g.drawImage(c.img, Math.round(x), c.y); }
  },
});

/* Where a raindrop is at time t: falling at d.v and drifting sideways at `drift` times that.
 * In loop mode (AF.LOOP) its sideways place follows how far it has fallen, so it keeps its
 * slant and starts again at the top of its own line; only the fall then needs rounding to the
 * loop, where a drift rounded on its own would race across the scene. */
function dropAt(d, t, drift, W, H) {
  const fall = (d.y + t * AF.u.drift(d.v, H)) % H;
  const x = AF.LOOP ? d.x - fall * drift : d.x - t * d.v * drift;
  return { x: Math.round((x % W + W) % W), y: Math.round(fall) };
}

/* the drops behind the land (drawn at the back) and in front of it */
part('rain', {
  init(st, { th, A, W, H, u }) {
    st.drift = th.lightning ? STORM_DRIFT : RAIN_DRIFT;
    const nRain = th.rain || 0;
    for (let i = 0; i < nRain; i++) (i < nRain * FAR_RAIN_SHARE ? st.far : st.drops).push({ x: A() * W, y: A() * H, v: (95 + A() * 40) * u * (i < nRain * FAR_RAIN_SHARE ? FAR_RAIN_SPEED : 1) });
  },
  back(g, env, t, st) {
    const { W, H } = env;
    if (st.far.length) {
      g.fillStyle = st.C.rainFar;
      for (const d of st.far) { const { x, y } = dropAt(d, t, st.drift, W, H); g.fillRect(x, y, 1, 2); }
    }
  },
  front(g, env, t, st) {
    const th = env.theme, { W, H } = env, C = st.C;
    if (st.drops.length) {
      g.fillStyle = th.rainLight ? C.rainLight : C.rain;
      const dx = st.drift > 0.2 ? 2 : 1;
      for (const d of st.drops) { const { x, y } = dropAt(d, t, st.drift, W, H); g.fillRect(x, y, 1, 2); g.fillRect(x - dx, y + 2, 1, 2); }
    }
  },
});

part('splashes', {
  init(st, { th, A, W, H, floor }) {
    for (let i = 0; i < (th.splashes || 0); i++) st.splashes.push({ x: (A() * W) | 0, y: Math.min(floor, Math.round(H * (0.86 + A() * 0.13))), per: 0.6 + A() * 1.2, ph: A() * 3 });
  },
  front(g, env, t, st) {
    for (const s of st.splashes) {
      const ph = ((t + s.ph) % AF.u.per(s.per)) / AF.u.per(s.per); if (ph > 0.14) continue;
      g.fillStyle = st.C.splash;
      if (ph < 0.07) g.fillRect(s.x, s.y - 1, 1, 1);
      else { g.fillRect(s.x - 1, s.y - 1, 1, 1); g.fillRect(s.x + 1, s.y - 1, 1, 1); g.fillRect(s.x, s.y - 2, 1, 1); }
    }
  },
});

part('snow', {
  init(st, { th, A, W, H, u }) {
    for (let i = 0; i < (th.snowfall || 0); i++) st.flakes.push({ x: A() * W, y: A() * H, v: (6 + A() * 9) * u, ph: A() * 10, big: A() < (th.deepSnow ? DEEP_BIG_FLAKE_CHANCE : BIG_FLAKE_CHANCE) });
  },
  front(g, env, t, st) {
    const { W, H, u } = env;
    if (st.flakes.length) {
      g.fillStyle = st.C.snow;
      for (const f of st.flakes) {
        const y = Math.round((f.y + t * AF.u.drift(f.v, H)) % H), x = Math.round((((f.x + Math.sin(t * AF.u.cyc(0.6) + f.ph) * 4 * u + t * AF.u.drift(2 * u, W)) % W) + W) % W), s = f.big ? 2 : 1;
        g.fillRect(x, y, s, s);
      }
    }
  },
});

/* after rain, points of light on the wet ground and in the puddles */
part('glints', {
  init(st, { th, A, W, H, floor, puddles }) {
    for (let i = 0; i < (th.glints || 0); i++) {
      if (puddles.length && i % 2 === 0) { const pd = puddles[i % puddles.length]; st.glints.push({ x: Math.round(pd.x + (A() - 0.5) * pd.w * 0.8), y: Math.round(pd.y), ph: A() * 10, sp: 0.8 + A() * 1.4 }); }
      else st.glints.push({ x: (A() * W) | 0, y: Math.min(floor, Math.round(H * (0.84 + A() * 0.15))), ph: A() * 10, sp: 0.8 + A() * 1.4 });
    }
  },
  front(g, env, t, st) {
    const C = st.C;
    for (const gl of st.glints) {
      const a = Math.max(0, Math.sin(t * AF.u.cyc(gl.sp) + gl.ph)); if (a < 0.6) continue;
      g.fillStyle = `rgba(${C.glint},${a})`; g.fillRect(gl.x, gl.y, 1, 1);
      if (a > 0.9) { g.fillStyle = `rgba(${C.glint},${a * 0.4})`; g.fillRect(gl.x - 1, gl.y, 3, 1); g.fillRect(gl.x, gl.y - 1, 1, 3); }
    }
  },
});

/* leaves blown across on a gust, now and then, never on a rhythm */
part('wind', {
  init(st, { th, A, H, C }) {
    if (th.wind) for (let i = 0; i < WIND_LEAVES; i++) st.leaves.push({ y: H * (0.3 + A() * 0.6), off: A(), ph: A() * 10, c: C.leaf || (A() < 0.5 ? th.grass : th.g0) });
  },
  front(g, env, t, st) {
    const { W, u } = env;
    if (st.leaves.length && !env.still && !AF.LOOP) {  // (a gust would come round every loop)
      const per = GUST_WINDOW, gi = Math.floor(t / per), ph = (t - gi * per) / GUST_SECS;
      if (rng(gi * 11 + 1)() < GUST_CHANCE && ph < 1) for (const l of st.leaves) {
        const q = ph * 1.3 - l.off * 0.3; if (q < 0 || q > 1) continue;
        const x = Math.round(q * (W + 40 * u) - 20 * u), y = Math.round(l.y + Math.sin(q * 9 + l.ph) * 4 * u);
        g.fillStyle = l.c; g.fillRect(x, y, 2, 1);
        if (l.off < 0.3) { g.fillStyle = 'rgba(255,255,255,.18)'; g.fillRect(x - Math.round(14 * u), y, Math.round(10 * u), 1); }
      }
    }
  },
});

/* raindrops ringing on still water: a lake's pools, or the puddles */
part('rings', {
  init(st, { env, th, A }) {
    if (th.rain && (env.pools || (env.puddles && env.puddles.length))) {
      const spots = (env.pools || []).map(p => [p.x, p.y, p.w * 0.35]).concat((env.puddles || []).map(p => [p.x, p.y + 1, p.w * 0.35]));
      // an empty pools array is still truthy, so check there is somewhere to ring
      for (let i = 0; spots.length && i < RINGS; i++) { const sp = spots[(A() * spots.length) | 0]; st.rings.push({ x: Math.round(sp[0] + (A() - 0.5) * sp[2] * 2), y: Math.round(sp[1]), per: 1.2 + A() * 1.6, ph: A() * 3 }); }
    }
  },
  front(g, env, t, st) {
    for (const r of st.rings) {
      const q = ((t + r.ph) % AF.u.per(r.per)) / AF.u.per(r.per); if (q > 0.5) continue;
      const rad = 1 + Math.round(q * 6); g.fillStyle = `rgba(230,240,250,${0.7 * (1 - q * 2)})`;
      g.fillRect(r.x - rad, r.y, 1, 1); g.fillRect(r.x + rad, r.y, 1, 1); g.fillRect(r.x - (rad >> 1), r.y - 1, rad, 1); g.fillRect(r.x - (rad >> 1), r.y + 1, rad, 1);
    }
  },
});

part('fogBanks', {
  init(st, { th, A, W, H, u }) {
    if (th.fog) for (let k = 0; k < FOG_BANKS; k++) {
      const w = Math.round((70 + A() * 60) * u), h = Math.round((10 + A() * 6) * u);
      st.banks.push({ cv: fogBank(w, h, th.fog, FOG_BANK_STRENGTH), x: A() * W, y: Math.round(H * (0.5 + A() * 0.3)), v: (1 + A()) * u });
    }
  },
  front(g, env, t, st) {
    const { W } = env;
    for (const b of st.banks) { const x = ((b.x + t * AF.u.drift(b.v, W + b.cv.width)) % (W + b.cv.width)) - b.cv.width; g.drawImage(b.cv, Math.round(x), b.y); }
  },
});

/* lightning strikes at no fixed rhythm, a couple of times a minute at most and usually much
 * less; a still forest never freezes a flash */
part('lightning', {
  back(g, env, t, st) {
    const th = env.theme, { W, H, u, hor } = env;
    st.flash = 0;
    if (th.lightning && !env.still && !AF.LOOP) {
      const per = LIGHTNING_WINDOW, i = Math.floor(t / per), ph = t - i * per - rng(i * 7 + 3)() * 12;
      if (rng(i * 13 + 5)() < LIGHTNING_CHANCE && (ph >= 0 && ph < 0.07 || (ph > 0.16 && ph < 0.22))) {
        st.flash = 1;
        const R = rng(i * 31 + 7); let x = W * (0.15 + R() * 0.7), y = H * 0.14;
        g.fillStyle = st.C.bolt;
        while (y < hor - 8 * u) { const nx = x + (R() - 0.5) * 7 * u, ny = y + (3 + R() * 4) * u; pxLine(g, x, y, nx, ny); x = nx; y = ny; }
      }
    }
  },
});
})();

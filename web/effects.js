/* Memory Forest — ambient pixel effects: clouds, stars, aurora, shooting stars and meteor
 * showers, rain in two depths, lightning, snow, petals, lanterns, fireflies, birds,
 * glints, wind gusts, drifting fog banks and leaves falling from struggling trees. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, layer, pxLine, B4 } = AF.u;
const { MATURE, OLD, ANCIENT } = AF.STAGE;
// only the front-most of the yellowing trees shed leaves, so a big forest stays cheap
const MAX_SHEDDING_TREES = 40;

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

const DEFAULT_COLORS = {
  star: '232,236,255', rain: 'rgba(170,196,214,.55)', rainFar: 'rgba(170,196,214,.3)', rainLight: 'rgba(190,210,225,.45)', splash: 'rgba(200,220,235,.8)',
  snow: 'rgba(248,250,255,.92)', bolt: '#eef3ff', flyCore: '236,255,186', flyGlow: '190,240,140',
  petals: ['#f7c6d3', '#eea0b7'], glint: '255,250,235', leaf: null, sickLeaves: ['#d6c86a', '#d8924a', '#b3ad4c']
};

// seconds: a shooting star every few minutes on a clear night, one after another in a
// meteor shower, each crossing in under a second
const SHOOTING_STAR_EVERY = 150, METEOR_EVERY = 1.3, STREAK_SECS = 0.9;
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

AF.fx = {
  init(env) {
    const th = env.theme, { W, H, u, hor } = env, A = rng(11);
    const C = Object.assign({}, DEFAULT_COLORS, th.warmFlies ? { flyCore: '255,214,150', flyGlow: '255,170,90' } : {},
      th.flyCore ? { flyCore: th.flyCore, flyGlow: th.flyGlow } : {}, env.fxColors || {});
    const trees = env.placed.filter(p => !p.it.pond);
    const elders = trees.filter(p => p.it.stage >= OLD);
    const hosts = elders.length ? elders : (trees.length ? trees : [{ x: W / 2, y: H * 0.8, s: 1, it: { stage: MATURE } }]);
    const hOf = p => AF.STAGE_H[p.it.stage] * u * p.s;
    const st = { C, clouds: [], deck: [], stars: [], flies: [], birds: [], drops: [], far: [], splashes: [], flakes: [], petals: [], lanterns: [], glints: [], leaves: [], falling: [], banks: [], spores: [], lights: [], rings: [] };
    const drift = th.lightning ? STORM_DRIFT : RAIN_DRIFT;
    st.drift = drift;

    if (th.deck && th.deck.n) for (let i = 0; i < th.deck.n; i++) {
      const w = Math.round((60 + A() * 30) * u), h = Math.round((8 + A() * 4) * u);
      st.deck.push({ img: pxCloud(A, w, h, th.deck.top, th.deck.bot, th.deck.a), x: A() * W, y: Math.round(H * A() * 0.06), v: (0.3 + A() * 0.2) * u });
    }
    if (th.clouds && th.clouds.n) for (let i = 0; i < th.clouds.n; i++) {
      const w = Math.round((26 + A() * 26) * u), h = Math.round((6 + A() * 6) * u);
      const pair = th.cloudPairs ? th.cloudPairs[i % th.cloudPairs.length] : [th.clouds.top, th.clouds.bot];
      st.clouds.push({ img: pxCloud(A, w, h, pair[0], pair[1], th.clouds.a, th.cloudSparkle), x: A() * W, y: Math.round(H * (th.clouds.y0 != null ? th.clouds.y0 : CLOUD_TOP) + A() * H * (th.clouds.dy || CLOUD_DEPTH)), v: (0.8 + A() * 0.8) * u * (th.clouds.speed || 1) });
    }
    const moon = th.orb && th.orb.kind === 'moon' ? { x: W * th.orb.x, y: H * th.orb.y, r: th.orb.r * u + 3 } : null;
    for (let i = 0; i < (th.stars || 0); i++) {
      const x = (A() * W) | 0, y = (A() * hor * 0.85) | 0;
      if (moon && Math.hypot(x - moon.x, y - moon.y) < moon.r + 2) continue;
      st.stars.push({ x, y, ph: A() * 10, sp: 0.5 + A() * 1.5 });
    }
    // fireflies hover low, near the ground between the trunks, never up in a crown where
    // a warm dot would read as a yellowing leaf
    for (let i = 0; i < (th.flies || 0); i++) {
      const e = hosts[(A() * hosts.length) | 0], h = hOf(e);
      st.flies.push({ x: e.x + (A() - 0.5) * h * 1.6, y: e.y - A() * Math.min(4 * u, h * 0.2), ph: A() * 10, sp: 0.6 + A() * 0.8 });
    }
    for (let i = 0; i < (th.birds || 0); i++) st.birds.push({ x: A() * W, y: H * (0.1 + A() * 0.2), v: (3 + A() * 3) * u, ph: A() * 6 });
    const nRain = th.rain || 0;
    for (let i = 0; i < nRain; i++) (i < nRain * FAR_RAIN_SHARE ? st.far : st.drops).push({ x: A() * W, y: A() * H, v: (95 + A() * 40) * u * (i < nRain * FAR_RAIN_SHARE ? FAR_RAIN_SPEED : 1) });
    const floor = env.lake ? env.lake.y0 - 2 : H;
    for (let i = 0; i < (th.splashes || 0); i++) st.splashes.push({ x: (A() * W) | 0, y: Math.min(floor, Math.round(H * (0.86 + A() * 0.13))), per: 0.6 + A() * 1.2, ph: A() * 3 });
    for (let i = 0; i < (th.snowfall || 0); i++) st.flakes.push({ x: A() * W, y: A() * H, v: (6 + A() * 9) * u, ph: A() * 10, big: A() < (th.deepSnow ? DEEP_BIG_FLAKE_CHANCE : BIG_FLAKE_CHANCE) });
    for (let i = 0; i < (th.petals || 0); i++) st.petals.push({ x: A() * W, y: A() * H, v: (5 + A() * 6) * u, wind: (8 + A() * 8) * u, ph: A() * 10, c: C.petals[i % C.petals.length] });
    // lanterns rise from above the crowns of the oldest trees, clear of the moon
    const anc = trees.filter(p => p.it.stage === ANCIENT), lh = anc.length ? anc : hosts;
    for (let i = 0; i < (th.lanterns || 0); i++) {
      const e = lh[(A() * lh.length) | 0]; let x = e.x + (A() - 0.5) * 6 * u;
      if (moon && Math.abs(x - moon.x) < 10) x += x < moon.x ? -12 : 12;
      st.lanterns.push({ x, y0: e.y - hOf(e) - 2, v: (3 + A() * 3) * u, off: A() * H * 1.2, ph: A() * 10 });
    }
    const puddles = env.puddles || [];
    for (let i = 0; i < (th.glints || 0); i++) {
      if (puddles.length && i % 2 === 0) { const pd = puddles[i % puddles.length]; st.glints.push({ x: Math.round(pd.x + (A() - 0.5) * pd.w * 0.8), y: Math.round(pd.y), ph: A() * 10, sp: 0.8 + A() * 1.4 }); }
      else st.glints.push({ x: (A() * W) | 0, y: Math.min(floor, Math.round(H * (0.84 + A() * 0.15))), ph: A() * 10, sp: 0.8 + A() * 1.4 });
    }
    if (th.wind) for (let i = 0; i < WIND_LEAVES; i++) st.leaves.push({ y: H * (0.3 + A() * 0.6), off: A(), ph: A() * 10, c: C.leaf || (A() < 0.5 ? th.grass : th.g0) });
    // a leaf or two drifting down from each struggling tree: yellowing you can spot at any depth
    if (!th.snow) for (const p of trees.filter(q => q.it.health > 0 && q.it.stage >= MATURE).slice(-MAX_SHEDDING_TREES)) {
      const h = hOf(p);
      for (let k = 0; k < Math.min(2, p.it.health); k++) st.falling.push({ x: p.x + (A() - 0.5) * h * 0.6, top: p.y - h * (0.5 + A() * 0.3), bottom: p.y, per: 6 + A() * 5, ph: A() * 10, c: C.sickLeaves[(A() * 3) | 0] });  // yellowing trees shed yellow, even in blossom
    }
    for (let i = 0; i < (th.spores || 0); i++) { const e = hosts[(A() * hosts.length) | 0]; st.spores.push({ x: e.x + (A() - 0.5) * 30 * u, y0: e.y, v: (1.5 + A() * 2) * u, off: A() * H, ph: A() * 10 }); }
    if (th.rain && (env.pools || (env.puddles && env.puddles.length))) {  // raindrops ringing on still water
      const spots = (env.pools || []).map(p => [p.x, p.y, p.w * 0.35]).concat((env.puddles || []).map(p => [p.x, p.y + 1, p.w * 0.35]));
      // an empty pools array is still truthy, so check there is somewhere to ring
      for (let i = 0; spots.length && i < RINGS; i++) { const sp = spots[(A() * spots.length) | 0]; st.rings.push({ x: Math.round(sp[0] + (A() - 0.5) * sp[2] * 2), y: Math.round(sp[1]), per: 1.2 + A() * 1.6, ph: A() * 3 }); }
    }
    // the environment adds whatever is only its own
    const spec = AF.envOf(env);
    if (spec.fx && spec.fx.init) spec.fx.init(st, { env, th, A, W, H, u, hor, trees, hosts, elders, hOf, moon, C });
    if (th.fog) for (let k = 0; k < FOG_BANKS; k++) {
      const w = Math.round((70 + A() * 60) * u), h = Math.round((10 + A() * 6) * u);
      st.banks.push({ cv: fogBank(w, h, th.fog, FOG_BANK_STRENGTH), x: A() * W, y: Math.round(H * (0.5 + A() * 0.3)), v: (1 + A()) * u });
    }
    return st;
  },

  back(g, env, t) {
    const st = env.fx, th = env.theme, { W, H, u, hor } = env, C = st.C;
    const spec = AF.envOf(env);
    if (spec.fx && spec.fx.back) spec.fx.back(g, env, t, st);
    for (const s of st.stars) { g.fillStyle = `rgba(${C.star},${0.35 + 0.65 * Math.abs(Math.sin(t * s.sp + s.ph))})`; g.fillRect(s.x, s.y, 1, 1); }
    if (th.shooting || th.meteors) {
      const per = th.meteors ? METEOR_EVERY : SHOOTING_STAR_EVERY, dur = env.still ? 0 : STREAK_SECS, i = Math.floor(t / per), ph = t - i * per;
      if (ph < dur) {
        const R = rng(i * 7919 + 3), sx = W * (0.1 + R() * 0.65), sy = H * (0.04 + R() * 0.18), p = ph / dur, bright = th.meteors || (th.bigStar && i % 3 === 0);
        for (let k = 0; k < (bright ? 12 : 8); k++) { const q = p - k * 0.03; if (q < 0) continue; g.fillStyle = `rgba(255,255,240,${(1 - k / (bright ? 12 : 8)) * (1 - p * 0.6)})`; g.fillRect(Math.round(sx + q * 34 * u), Math.round(sy + q * 12 * u), bright && k === 0 ? 2 : 1, 1); }
      }
    }
    for (const c of st.deck) { const x = ((c.x + t * c.v) % (W + c.img.width)) - c.img.width; g.drawImage(c.img, Math.round(x), c.y); }
    for (const c of st.clouds) { const x = ((c.x + t * c.v * 0.9) % (W + c.img.width)) - c.img.width; g.drawImage(c.img, Math.round(x), c.y); }
    if (st.far.length) {
      g.fillStyle = C.rainFar;
      for (const d of st.far) { const y = Math.round((d.y + t * d.v) % H), x = Math.round(((d.x - t * d.v * st.drift) % W + W) % W); g.fillRect(x, y, 1, 2); }
    }
    st.flash = 0;
    // lightning strikes at no fixed rhythm, a couple of times a minute at most and
    // usually much less; a still forest never freezes a flash
    if (th.lightning && !env.still) {
      const per = LIGHTNING_WINDOW, i = Math.floor(t / per), ph = t - i * per - rng(i * 7 + 3)() * 12;
      if (rng(i * 13 + 5)() < LIGHTNING_CHANCE && (ph >= 0 && ph < 0.07 || (ph > 0.16 && ph < 0.22))) {
        st.flash = 1;
        const R = rng(i * 31 + 7); let x = W * (0.15 + R() * 0.7), y = H * 0.14;
        g.fillStyle = C.bolt;
        while (y < hor - 8 * u) { const nx = x + (R() - 0.5) * 7 * u, ny = y + (3 + R() * 4) * u; pxLine(g, x, y, nx, ny); x = nx; y = ny; }
      }
    }
  },

  front(g, env, t) {
    const st = env.fx, th = env.theme, { W, H, u } = env, C = st.C;
    for (const gl of st.glints) {
      const a = Math.max(0, Math.sin(t * gl.sp + gl.ph)); if (a < 0.6) continue;
      g.fillStyle = `rgba(${C.glint},${a})`; g.fillRect(gl.x, gl.y, 1, 1);
      if (a > 0.9) { g.fillStyle = `rgba(${C.glint},${a * 0.4})`; g.fillRect(gl.x - 1, gl.y, 3, 1); g.fillRect(gl.x, gl.y - 1, 1, 3); }
    }
    // lanterns: a small warm light with a pixel glow, shrinking as it rises instead of fading
    for (const l of st.lanterns) {
      const y = Math.round(l.y0 - ((t * l.v + l.off) % (H * 1.2))), x = Math.round(l.x + Math.sin(t * 0.5 + l.ph) * 3 * u);
      if (y < -4) continue;
      const k = y / H, flick = 0.85 + 0.15 * Math.sin(t * 3 + l.ph);
      if (k > 0.1) {
        g.fillStyle = `rgba(255,190,100,${0.18 * flick})`; g.fillRect(x - 2, y + 1, 1, 2); g.fillRect(x + 4, y + 1, 1, 2); g.fillRect(x + 1, y - 2, 1, 1); g.fillRect(x + 1, y + 5, 1, 1);
        g.fillStyle = `rgba(255,190,100,${0.35 * flick})`; g.fillRect(x - 1, y + 1, 1, 2); g.fillRect(x + 3, y + 1, 1, 2); g.fillRect(x + 1, y - 1, 1, 1); g.fillRect(x + 1, y + 4, 1, 1);
        g.fillStyle = '#b8432c'; g.fillRect(x, y, 3, 1); g.fillStyle = '#ffce6e'; g.fillRect(x, y + 1, 3, 2); g.fillStyle = '#ec783a'; g.fillRect(x, y + 3, 3, 1);
      } else if (k > 0.03) { g.fillStyle = '#ffce6e'; g.fillRect(x, y, 2, 2); g.fillStyle = 'rgba(255,190,100,.25)'; g.fillRect(x - 1, y, 4, 2); }
      else { g.fillStyle = '#ffce6e'; g.fillRect(x, y, 1, 1); }
    }
    g.fillStyle = C.bird || th.birdC || '#3a3a4a';
    for (const b of st.birds) {
      const x = Math.round(((b.x + t * b.v) % (W + 20)) - 10), y = Math.round(b.y + Math.sin(t * 0.6 + b.ph) * 2 * u), up = Math.sin(t * 5 + b.ph) > 0;
      if (up) { g.fillRect(x, y, 1, 1); g.fillRect(x - 1, y - 1, 1, 1); g.fillRect(x + 1, y - 1, 1, 1); g.fillRect(x - 2, y - 2, 1, 1); g.fillRect(x + 2, y - 2, 1, 1); }
      else g.fillRect(x - 1, y, 3, 1);
    }
    const night = env.mood.time === 'night';
    for (const f of st.flies) {
      const a = Math.pow(Math.max(0, Math.sin(t * f.sp + f.ph * 3)), 2); if (a < 0.03) continue;
      const x = Math.round(f.x + Math.sin(t * 0.3 + f.ph) * 3 * u), y = Math.round(f.y + Math.cos(t * 0.23 + f.ph) * 2 * u);
      if (night) { g.fillStyle = `rgba(${C.flyGlow},${a * 0.18})`; g.fillRect(x - 2, y - 1, 5, 3); g.fillRect(x - 1, y - 2, 3, 5); }
      g.fillStyle = `rgba(${C.flyGlow},${a * 0.4})`; g.fillRect(x - 1, y, 3, 1); g.fillRect(x, y - 1, 1, 3);
      g.fillStyle = `rgba(${C.flyCore},${a})`; g.fillRect(x, y, 1, 1);
      if (env.pools) for (const p of env.pools) {
        if (Math.abs(x - p.x) > p.w / 2 || p.y < y || p.y - y > 30) continue;
        const ry = Math.round(p.y + (p.y - y) * 0.15); if (Math.abs(ry - p.y) > p.h / 2) continue;
        g.fillStyle = `rgba(${C.flyCore},${a * 0.45})`; g.fillRect(x, ry, 1, 1); break;
      }
    }
    const spec = AF.envOf(env);
    if (spec.fx && spec.fx.front) spec.fx.front(g, env, t, st, 'crowns');
    for (const r of st.rings) {
      const q = ((t + r.ph) % r.per) / r.per; if (q > 0.5) continue;
      const rad = 1 + Math.round(q * 6); g.fillStyle = `rgba(230,240,250,${0.7 * (1 - q * 2)})`;
      g.fillRect(r.x - rad, r.y, 1, 1); g.fillRect(r.x + rad, r.y, 1, 1); g.fillRect(r.x - (rad >> 1), r.y - 1, rad, 1); g.fillRect(r.x - (rad >> 1), r.y + 1, rad, 1);
    }
    if (spec.fx && spec.fx.front) spec.fx.front(g, env, t, st, 'air');
    if (spec.fx && spec.fx.front) spec.fx.front(g, env, t, st, 'sky');
    for (const s of st.spores) {  // glowing spores rising slowly from the forest floor
      const y = Math.round(s.y0 - ((t * s.v + s.off) % (H * 0.7))), x = Math.round(s.x + Math.sin(t * 0.6 + s.ph) * 3 * u), a = 0.45 + 0.4 * Math.sin(t * 1.3 + s.ph);
      g.fillStyle = `rgba(${th.sporeColor},${a * 0.3})`; g.fillRect(x - 1, y, 3, 1); g.fillRect(x, y - 1, 1, 3);
      g.fillStyle = `rgba(${th.sporeColor},${a})`; g.fillRect(x, y, 1, 1);
    }
    for (const l of st.lights) {
      const a = 0.55 + 0.45 * Math.sin(t * 2 + l.ph);
      if (night) { g.fillStyle = `rgba(${l.c},${a * 0.25})`; g.fillRect(l.x - 1, l.y, 3, 1); g.fillRect(l.x, l.y - 1, 1, 3); }
      g.fillStyle = `rgba(${l.c},${Math.max(0.35, a)})`; g.fillRect(l.x, l.y, 1, 1);
    }
    for (const l of st.falling) {
      const q = ((t + l.ph) % l.per) / l.per, y = Math.round(l.top + (l.bottom - l.top) * q), x = Math.round(l.x + Math.sin(q * 9 + l.ph) * 2);
      g.fillStyle = l.c; g.fillRect(x, y, Math.sin(t * 2 + l.ph) > 0 ? 2 : 1, 1);
    }
    for (const p of st.petals) {
      const y = Math.round((p.y + t * p.v) % H), x = Math.round((((p.x + t * p.wind + Math.sin(t * 1.2 + p.ph) * 4 * u) % W) + W) % W);
      g.fillStyle = p.c; g.fillRect(x, y, Math.sin(t * 3 + p.ph) > 0 ? 2 : 1, 1);
    }
    if (st.leaves.length && !env.still) {  // a gust now and then, never on a rhythm
      const per = GUST_WINDOW, gi = Math.floor(t / per), ph = (t - gi * per) / GUST_SECS;
      if (rng(gi * 11 + 1)() < GUST_CHANCE && ph < 1) for (const l of st.leaves) {
        const q = ph * 1.3 - l.off * 0.3; if (q < 0 || q > 1) continue;
        const x = Math.round(q * (W + 40 * u) - 20 * u), y = Math.round(l.y + Math.sin(q * 9 + l.ph) * 4 * u);
        g.fillStyle = l.c; g.fillRect(x, y, 2, 1);
        if (l.off < 0.3) { g.fillStyle = 'rgba(255,255,255,.18)'; g.fillRect(x - Math.round(14 * u), y, Math.round(10 * u), 1); }
      }
    }
    for (const b of st.banks) { const x = ((b.x + t * b.v) % (W + b.cv.width)) - b.cv.width; g.drawImage(b.cv, Math.round(x), b.y); }
    if (st.flakes.length) {
      g.fillStyle = C.snow;
      for (const f of st.flakes) {
        const y = Math.round((f.y + t * f.v) % H), x = Math.round((((f.x + Math.sin(t * 0.6 + f.ph) * 4 * u + t * 2 * u) % W) + W) % W), s = f.big ? 2 : 1;
        g.fillRect(x, y, s, s);
      }
    }
    if (st.drops.length) {
      g.fillStyle = th.rainLight ? C.rainLight : C.rain;
      const dx = st.drift > 0.2 ? 2 : 1;
      for (const d of st.drops) { const y = Math.round((d.y + t * d.v) % H), x = Math.round(((d.x - t * d.v * st.drift) % W + W) % W); g.fillRect(x, y, 1, 2); g.fillRect(x - dx, y + 2, 1, 2); }
    }
    for (const s of st.splashes) {
      const ph = ((t + s.ph) % s.per) / s.per; if (ph > 0.14) continue;
      g.fillStyle = C.splash;
      if (ph < 0.07) g.fillRect(s.x, s.y - 1, 1, 1);
      else { g.fillRect(s.x - 1, s.y - 1, 1, 1); g.fillRect(s.x + 1, s.y - 1, 1, 1); g.fillRect(s.x, s.y - 2, 1, 1); }
    }
  }
};
})();

/* Memory Forest — the ambience's effects: stars, shooting stars and meteor showers,
 * fireflies, birds, falling petals, rising lanterns, spores, an environment's small lights,
 * and leaves falling from struggling trees. Each registers with effects.js, which runs
 * them in order. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng } = AF.u;
const { MATURE, ANCIENT } = AF.STAGE;
const part = AF.fx.part;

// only the front-most of the yellowing trees shed leaves, so a big forest stays cheap
const MAX_SHEDDING_TREES = 40;
// seconds: a shooting star every few minutes on a clear night, one after another in a
// meteor shower, each crossing in under a second
const SHOOTING_STAR_EVERY = 150, METEOR_EVERY = 1.3, STREAK_SECS = 0.9;

part('stars', {
  init(st, { th, A, W, hor, moon }) {
    for (let i = 0; i < (th.stars || 0); i++) {
      const x = (A() * W) | 0, y = (A() * hor * 0.85) | 0;
      if (moon && Math.hypot(x - moon.x, y - moon.y) < moon.r + 2) continue;
      st.stars.push({ x, y, ph: A() * 10, sp: 0.5 + A() * 1.5 });
    }
  },
  back(g, env, t, st) {
    for (const s of st.stars) { g.fillStyle = `rgba(${st.C.star},${0.35 + 0.65 * Math.abs(Math.sin(t * s.sp + s.ph))})`; g.fillRect(s.x, s.y, 1, 1); }
  },
});

part('shooting', {
  back(g, env, t) {
    const th = env.theme, { W, H, u } = env;
    if (th.shooting || th.meteors) {
      const per = th.meteors ? METEOR_EVERY : SHOOTING_STAR_EVERY, dur = env.still ? 0 : STREAK_SECS, i = Math.floor(t / per), ph = t - i * per;
      if (ph < dur) {
        const R = rng(i * 7919 + 3), sx = W * (0.1 + R() * 0.65), sy = H * (0.04 + R() * 0.18), p = ph / dur, bright = th.meteors || (th.bigStar && i % 3 === 0);
        for (let k = 0; k < (bright ? 12 : 8); k++) { const q = p - k * 0.03; if (q < 0) continue; g.fillStyle = `rgba(255,255,240,${(1 - k / (bright ? 12 : 8)) * (1 - p * 0.6)})`; g.fillRect(Math.round(sx + q * 34 * u), Math.round(sy + q * 12 * u), bright && k === 0 ? 2 : 1, 1); }
      }
    }
  },
});

/* fireflies hover low, near the ground between the trunks, never up in a crown where a
 * warm dot would read as a yellowing leaf */
part('flies', {
  init(st, { th, A, u, hosts, hOf }) {
    for (let i = 0; i < (th.flies || 0); i++) {
      const e = hosts[(A() * hosts.length) | 0], h = hOf(e);
      st.flies.push({ x: e.x + (A() - 0.5) * h * 1.6, y: e.y - A() * Math.min(4 * u, h * 0.2), ph: A() * 10, sp: 0.6 + A() * 0.8 });
    }
  },
  front(g, env, t, st) {
    const { u } = env, C = st.C, night = env.mood.time === 'night';
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
  },
});

part('birds', {
  init(st, { th, A, W, H, u }) {
    for (let i = 0; i < (th.birds || 0); i++) st.birds.push({ x: A() * W, y: H * (0.1 + A() * 0.2), v: (3 + A() * 3) * u, ph: A() * 6 });
  },
  front(g, env, t, st) {
    const th = env.theme, { W, u } = env;
    g.fillStyle = st.C.bird || th.birdC || '#3a3a4a';
    for (const b of st.birds) {
      const x = Math.round(((b.x + t * b.v) % (W + 20)) - 10), y = Math.round(b.y + Math.sin(t * 0.6 + b.ph) * 2 * u), up = Math.sin(t * 5 + b.ph) > 0;
      if (up) { g.fillRect(x, y, 1, 1); g.fillRect(x - 1, y - 1, 1, 1); g.fillRect(x + 1, y - 1, 1, 1); g.fillRect(x - 2, y - 2, 1, 1); g.fillRect(x + 2, y - 2, 1, 1); }
      else g.fillRect(x - 1, y, 3, 1);
    }
  },
});

part('petals', {
  init(st, { th, A, W, H, u, C }) {
    for (let i = 0; i < (th.petals || 0); i++) st.petals.push({ x: A() * W, y: A() * H, v: (5 + A() * 6) * u, wind: (8 + A() * 8) * u, ph: A() * 10, c: C.petals[i % C.petals.length] });
  },
  front(g, env, t, st) {
    const { W, H, u } = env;
    for (const p of st.petals) {
      const y = Math.round((p.y + t * p.v) % H), x = Math.round((((p.x + t * p.wind + Math.sin(t * 1.2 + p.ph) * 4 * u) % W) + W) % W);
      g.fillStyle = p.c; g.fillRect(x, y, Math.sin(t * 3 + p.ph) > 0 ? 2 : 1, 1);
    }
  },
});

/* lanterns rise from above the crowns of the oldest trees, clear of the moon: a small warm
 * light with a pixel glow, shrinking as it rises instead of fading */
part('lanterns', {
  init(st, { th, A, H, u, trees, hosts, hOf, moon }) {
    const anc = trees.filter(p => p.it.stage === ANCIENT), lh = anc.length ? anc : hosts;
    for (let i = 0; i < (th.lanterns || 0); i++) {
      const e = lh[(A() * lh.length) | 0]; let x = e.x + (A() - 0.5) * 6 * u;
      if (moon && Math.abs(x - moon.x) < 10) x += x < moon.x ? -12 : 12;
      st.lanterns.push({ x, y0: e.y - hOf(e) - 2, v: (3 + A() * 3) * u, off: A() * H * 1.2, ph: A() * 10 });
    }
  },
  front(g, env, t, st) {
    const { H, u } = env;
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
  },
});

/* a leaf or two drifting down from each struggling tree: yellowing you can spot at any depth */
part('falling', {
  init(st, { th, A, trees, hOf, C }) {
    if (!th.snow) for (const p of trees.filter(q => q.it.health > 0 && q.it.stage >= MATURE).slice(-MAX_SHEDDING_TREES)) {
      const h = hOf(p);
      for (let k = 0; k < Math.min(2, p.it.health); k++) st.falling.push({ x: p.x + (A() - 0.5) * h * 0.6, top: p.y - h * (0.5 + A() * 0.3), bottom: p.y, per: 6 + A() * 5, ph: A() * 10, c: C.sickLeaves[(A() * 3) | 0] });  // yellowing trees shed yellow, even in blossom
    }
  },
  front(g, env, t, st) {
    for (const l of st.falling) {
      const q = ((t + l.ph) % l.per) / l.per, y = Math.round(l.top + (l.bottom - l.top) * q), x = Math.round(l.x + Math.sin(q * 9 + l.ph) * 2);
      g.fillStyle = l.c; g.fillRect(x, y, Math.sin(t * 2 + l.ph) > 0 ? 2 : 1, 1);
    }
  },
});

/* glowing spores rising slowly from the forest floor */
part('spores', {
  init(st, { th, A, H, u, hosts }) {
    for (let i = 0; i < (th.spores || 0); i++) { const e = hosts[(A() * hosts.length) | 0]; st.spores.push({ x: e.x + (A() - 0.5) * 30 * u, y0: e.y, v: (1.5 + A() * 2) * u, off: A() * H, ph: A() * 10 }); }
  },
  front(g, env, t, st) {
    const th = env.theme, { H, u } = env;
    for (const s of st.spores) {
      const y = Math.round(s.y0 - ((t * s.v + s.off) % (H * 0.7))), x = Math.round(s.x + Math.sin(t * 0.6 + s.ph) * 3 * u), a = 0.45 + 0.4 * Math.sin(t * 1.3 + s.ph);
      g.fillStyle = `rgba(${th.sporeColor},${a * 0.3})`; g.fillRect(x - 1, y, 3, 1); g.fillRect(x, y - 1, 1, 3);
      g.fillStyle = `rgba(${th.sporeColor},${a})`; g.fillRect(x, y, 1, 1);
    }
  },
});

/* small lights an environment scatters (st.lights), twinkling */
part('lights', {
  front(g, env, t, st) {
    const night = env.mood.time === 'night';
    for (const l of st.lights) {
      const a = 0.55 + 0.45 * Math.sin(t * 2 + l.ph);
      if (night) { g.fillStyle = `rgba(${l.c},${a * 0.25})`; g.fillRect(l.x - 1, l.y, 3, 1); g.fillRect(l.x, l.y - 1, 1, 3); }
      g.fillStyle = `rgba(${l.c},${Math.max(0.35, a)})`; g.fillRect(l.x, l.y, 1, 1);
    }
  },
});
})();

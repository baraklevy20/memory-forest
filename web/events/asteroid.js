/* Memory Forest — Merciless's asteroid: on its way on a day with no reviews yet, the strike
 * (a meteor shower, then the forest blown apart), and the crater it leaves, healing over
 * the months. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hashStr, mixHex, clamp } = AF.u;
const { px, noise } = AF.events;
const FIRE = ['#5a1208', '#9c2a14', '#d9471b', '#ff8a2a', '#ffc94a', '#fff3b0'];
const STEP = 1000 / 12;  // the strike animates at 12 frames a second, like a sprite

/* ---------- where a crater lies ----------
 * Worked out from the strike's date, never stored: the same spot on every redraw and
 * every restart, and each strike its own. The rock lands exactly there too. (`spot`, when
 * a crater carries one, stands in for the date - the debug timeline's strikes do, as
 * their dates shift with every day it skips.) */
const craterR = lost => Math.round(6 + 5 * Math.log2(1 + lost / 10));
// Anywhere across the middle of the ground (CRATER_ACROSS of the width, CRATER_DOWN of the
// way from the horizon to the front row), or on the ground a landscape names (its craterGround).
// A landscape with water on the ground slides it, and the earth it throws out (CRATER_SPRAY
// of its radius), onto the nearer bank (its dryX).
const CRATER_ACROSS = [0.14, 0.86], CRATER_DOWN = [0.5, 0.8], CRATER_SPRAY = 1.5;
function spot(c, env) {
  const h = hashStr('crater|' + (c.spot || c.date)), land = AF.landOf(env);
  // (null when that landscape has no ground to hold one just now)
  if (land.craterGround && !land.craterGround(env)) return null;
  const box = land.craterGround ? land.craterGround(env) : {
    x0: env.W * CRATER_ACROSS[0], x1: env.W * CRATER_ACROSS[1],
    y0: env.hor + (env.H * env.bot - env.hor) * CRATER_DOWN[0], y1: env.hor + (env.H * env.bot - env.hor) * CRATER_DOWN[1],
  };
  const x = box.x0 + (box.x1 - box.x0) * (h % 1000) / 1000, y = Math.round(box.y0 + (box.y1 - box.y0) * ((h >>> 10) % 1000) / 1000);  // (>>>: the hash is unsigned)
  return { x: Math.round(land.dryX ? land.dryX(env, x, y, x, craterR(c.lost) * CRATER_SPRAY) : x), y };
}

/* A crater heals, in days since the strike: a scorched pit ringed with thrown-out earth
 * (fresh), bare dirt (a week on), grass closing in from the rim as the dirt shrinks to
 * nothing (by HEALED), then a grassy dip with a ring of flowers, flattening from FADE and
 * gone at GONE. The grass is the scene's own ground colour, so it matches any hour. */
const CRATER_FRESH = 5, CRATER_EJECTA = 30, CRATER_HEAL_FROM = 7, CRATER_HEALED = 90, CRATER_FLOWERS = 90, CRATER_FADE = 200, CRATER_GONE = 400;
const DIRT = { pit: '#161110', dark: '#2a1f18', mid: '#4a3828', light: '#6e5638', scorch: '#1f1814', thrown: '#7a6244' };
function crater(g, cx, cy, lost, age, env) {
  if (age > CRATER_GONE) return;
  const th = env.theme, rx = craterR(lost), ry = Math.max(3, Math.round(rx * 0.32));
  const depth = clamp((cy - env.hor) / (env.H - env.hor), 0, 1) * 2;  // the ground's colour where the crater lies
  const grass = mixHex(th.g0, th.g1, clamp(depth - 0.5, 0, 1)), shade = mixHex(grass, '#000000', 0.22), lit = mixHex(grass, '#ffffff', 0.14);
  const heal = clamp((age - CRATER_HEAL_FROM) / (CRATER_HEALED - CRATER_HEAL_FROM), 0, 1);
  const fade = age < CRATER_FADE ? 1 : 1 - (age - CRATER_FADE) / (CRATER_GONE - CRATER_FADE);
  for (let y = -ry - 3; y <= ry + 3; y++) for (let x = -rx - 5; x <= rx + 5; x++) {
    const r = Math.sqrt((x / rx) ** 2 + (y / ry) ** 2), odd = (x + y) & 1;
    let c = null;
    if (r > 1) {
      continue;  // outside it (the earth it threw out is scattered below)
    } else if (age >= CRATER_FADE) {  // a shallow dip, fading to nothing
      if (r > 0.75 && odd && noise(x, y) < fade) c = y < 0 ? shade : lit;
    } else if (r < 1 - heal) {  // the bare dirt, shrinking as the grass closes in
      const edge = r > (1 - heal) - 0.12 && heal > 0 && odd;  // a dithered line where grass meets dirt
      if (edge) c = shade;
      else if (age < CRATER_FRESH) c = r < 0.4 ? DIRT.pit : y < 0 ? DIRT.scorch : (odd ? DIRT.dark : DIRT.scorch);
      else c = r < 0.35 ? DIRT.dark : y < 0 ? (odd ? DIRT.dark : DIRT.mid) : (odd ? DIRT.mid : DIRT.light);
    } else {  // grassed over: a dip, its far wall in shadow and its near lip catching the light
      c = r > 0.85 ? (y < 0 ? shade : lit) : y < -ry * 0.2 ? (odd ? shade : grass) : grass;
    }
    if (c) px(g, cx + x, cy + y, c);
  }
  // the earth it threw out: clumps scattered round the rim, fewer as the weeks go by
  const spray = 1 - age / CRATER_EJECTA;
  for (let i = 0; spray > 0 && i < rx * 2; i++) {
    if (noise(i, 3) > spray) continue;
    const a = noise(i, rx + 1) * 6.283, rr = 1.08 + noise(i, 5) * 0.35, ex = Math.round(cx + Math.cos(a) * rx * rr), ey = Math.round(cy + Math.sin(a) * ry * rr);
    px(g, ex, ey, DIRT.thrown); if (noise(i, 7) < 0.5) px(g, ex + 1, ey, DIRT.light);
  }
  // once it has healed, a ring of flowers (white, pink and violet: never yellow)
  if (age >= CRATER_FLOWERS && age < CRATER_GONE) {
    const n = Math.round(rx * 1.6 * Math.min(1, (age - CRATER_FLOWERS) / 60) * fade);
    for (let i = 0; i < n; i++) {
      const a = noise(i, rx) * 6.283, rr = 1.05 + (noise(i, 9) - 0.5) * 0.2, fx = cx + Math.cos(a) * rx * rr, fy = cy + Math.sin(a) * ry * rr;
      px(g, fx, fy, ['#ffffff', '#ff9ec8', '#c49af0'][i % 3]); px(g, fx, fy + 1, '#4f7a3a');
    }
  }
}

/* ---------- tooltips ---------- */
const fmt = iso => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
// (how to watch the latest one again is for the pointer to say: a click, or a tap and a button)
const craterHtml = c => `<b>A crater</b><br>${c.lost} tree${c.lost === 1 ? '' : 's'} lost on ${fmt(c.date)}${c.streak ? `, after a ${c.streak}-day streak` : ''}`;
const doomText = () => 'An asteroid strikes when Anki\'s day ends, unless you review before then.';
const fmtShort = iso => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

/* ---------- the strike: a meteor shower, then the forest blown apart ---------- */
// The page first draws the forest as it stood, lets the shower fall on it, then puts up the
// forest as it is now and tears the old one apart over it, pixel by pixel, from the point
// where the rock came down.
const SHOWER_SECS = 2.4, BLAST_SECS = 3.2, BLAST_REACH = 0.12;
function fireball(g, W, H, q, f, cx, cy, from, st) {
  const x = from.x + (cx - from.x) * q, y = from.y + (cy - from.y) * q, len = Math.hypot(cx - from.x, cy - from.y);
  const ux = (from.x - cx) / len, uy = (from.y - cy) / len, X = Math.round(x), Y = Math.round(y);
  for (let i = 40; i < 70; i++) if (noise(i, f >> 1) < 0.5) px(g, x + ux * i * 1.6 + (noise(i, 7) - 0.5) * 3, y + uy * i * 1.6 + (noise(i, 8) - 0.5) * 3, `rgba(120,110,105,${(0.35 - (i - 40) * 0.01).toFixed(2)})`);
  for (let i = 3; i < 42; i++) {
    const k = i / 42, w = Math.max(1, Math.round(6 * (1 - k) ** 0.8));
    for (let j = -w; j <= w; j++) {
      if (noise(i * 13 + j, f) > (1 - k) * (1 - Math.abs(j) / (w + 1)) * 1.6) continue;
      const band = Math.max(0, Math.min(5, Math.round(5 - k * 5 - Math.abs(j) / w * 1.5 + noise(i, j + f) * 0.8)));
      px(g, x + ux * i * 1.5 - uy * j + (noise(i, f) - 0.5), y + uy * i * 1.5 + ux * j, FIRE[band]);
    }
  }
  st.sparks = (st.sparks || []).filter(p => (p.life -= 1) > 0);
  for (let i = 0; i < 3; i++) st.sparks.push({ x: x + ux * 6, y: y + uy * 6, vx: ux * 0.8 + (noise(i, f) - 0.5) * 1.6, vy: uy * 0.8 + (noise(f, i) - 0.5) * 1.6 + 0.3, life: 8 });
  for (const p of st.sparks) { p.x += p.vx; p.y += p.vy; px(g, p.x, p.y, FIRE[Math.min(5, 2 + (p.life >> 1))]); }
  for (let dy = -9; dy <= 9; dy++) for (let dx = -9; dx <= 9; dx++) {
    const d = Math.hypot(dx, dy), front = -(dx * ux + dy * uy) / (d || 1);
    if (d < 9 && d > 5 && front > 0.2 && noise(dx + 30, dy + f) < (front - 0.2) * 0.8) px(g, X + dx, Y + dy, d < 7 ? '#fff3b0' : '#ffc94a');
  }
  const LUMP = [6, 5, 6, 7, 5, 6, 5, 7], spin = f * 0.15;
  for (let dy = -7; dy <= 7; dy++) for (let dx = -7; dx <= 7; dx++) {
    const ang = Math.atan2(dy, dx) - spin, r = LUMP[(((Math.round(ang / (Math.PI / 4)) % 8) + 8) % 8)], d = Math.hypot(dx, dy);
    if (d > r) continue;
    const front = -(dx * ux + dy * uy) / (d || 1);
    px(g, X + dx, Y + dy, d > r - 1.3 && front > 0.3 ? (front > 0.7 ? '#ffffff' : '#fff3b0') : d > r - 1.3 && front > -0.2 ? '#ff8a2a'
      : (dx - dy) * 0.5 + noise(dx + 9, dy + 9) * 2 > 1 ? '#6a5e56' : ((dx + dy) & 1 ? '#3e3430' : '#342b27'));
  }
}
function shower(g, W, H, q, f, cx, cy, st) {
  g.fillStyle = `rgba(25,20,55,${(0.3 * q).toFixed(3)})`; g.fillRect(0, 0, W, H);
  for (let m = 0; m < 7; m++) {  // small ones first, landing in the distance
    const mq = (q - m * 0.1) / 0.25;
    if (mq < 0 || mq > 1.2) continue;
    const sx = W * (0.2 + noise(m, 1) * 0.7) + 40, ex = sx - 40, ey = H * (0.38 + noise(m, 2) * 0.05);
    const x = sx + (ex - sx) * Math.min(1, mq), y = -5 + (ey + 5) * Math.min(1, mq);
    if (mq <= 1) for (let i = 0; i < 10; i++) px(g, x + i * 1.2, y - i * 1.3, FIRE[Math.max(1, 5 - (i >> 1))]);
    else for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, -1]]) px(g, ex + dx, ey + dy, '#fff3b0');
  }
  if (q > 0.5) fireball(g, W, H, (q - 0.5) / 0.5, f, cx, cy, { x: W + 30, y: -35 }, st);  // then the big one
}
function blownApart(g, W, H, a, f, cx, cy, st, src) {
  // the blast reaches past the far edge, wherever the rock came down (BLAST_REACH beyond it)
  const top = Math.round(H * 0.25), ground = Math.round(H * 0.8), e = 1 - (1 - Math.min(1, a / 1.5)) ** 2, R = e * (Math.max(cx, W - cx) + W * BLAST_REACH);
  if (!st.data) { st.data = src.getContext('2d').getImageData(0, 0, W, H).data; st.bits = []; st.done = new Set(); }
  for (let x = 0; x < W; x++) {
    if (Math.abs(x - cx) > R) { g.drawImage(src, x, top, 1, ground - top, x, top, 1, ground - top); continue; }
    if (st.done.has(x)) continue;
    st.done.add(x);  // just reached: tear this column up
    for (let y = top; y < ground; y += 2) {
      const i = (y * W + x) * 4, r = st.data[i], gg = st.data[i + 1], b = st.data[i + 2];
      if (st.data[i + 3] < 200 || (gg < r * 0.7 && b > gg)) continue;  // not the sky
      st.bits.push({ x, y, vx: (x < cx ? -1 : 1) * (1 + noise(x, y) * 2.5), vy: -1 - noise(y, x) * 2.4, c: `rgb(${r},${gg},${b})`, life: 30 + (noise(x, y + 1) * 20 | 0) });
    }
  }
  st.bits = st.bits.filter(p => (p.life -= 1) > 0 && p.x > -2 && p.x < W + 2);
  for (const p of st.bits) { p.x += p.vx; p.y += p.vy; p.vy += 0.12; p.vx *= 0.97; if (p.y > ground) { p.y = ground; p.vy *= -0.3; } px(g, p.x, p.y, p.c); }
  if (a < 2 * STEP / 1000) { g.fillStyle = 'rgba(255,255,255,0.85)'; g.fillRect(0, 0, W, H); }
}

function overlayOn(root) {
  const scene = root.querySelector('.af-scene'), canvas = scene.querySelector('canvas.af-canvas');
  const c = document.createElement('canvas');
  c.className = 'af-strike'; c.width = canvas.width; c.height = canvas.height;
  Object.assign(c.style, { position: 'absolute', left: canvas.offsetLeft + 'px', top: canvas.offsetTop + 'px', width: canvas.style.width, height: canvas.style.height, pointerEvents: 'none', imageRendering: 'pixelated' });
  scene.appendChild(c);
  return c;
}
function run(draw, done) {
  let t0 = null, last = -1;
  const tick = now => {
    if (t0 === null) t0 = now;
    const f = Math.floor((now - t0) / STEP);
    if (f !== last) { last = f; if (draw(f * STEP / 1000, f) === false) { done(); return; } }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* Whether the strike `s` can be played again: the page has the forest it took, or can
 * ask Anki for it (the phone can't). */
const replayable = s => Boolean(s && (s.before || AF.u.canBrowse()));

/* Show `data`'s latest strike happening: the forest it took, the shower, the blast, and
 * then the forest as it is now. `done` runs at the end (to say it has been seen). */
function playStrike (root, data, done) {
  const s = data.strike, latest = (data.craters || [])[data.craters.length - 1];
  const before = Object.assign({}, data, { trees: s.before, merged: s.merged || null, craters: (data.craters || []).slice(0, -1), strike: null, doom: null,
    stats: Object.assign({}, data.stats, { trees: s.lost, streak: latest ? latest.streak : data.stats.streak }) });
  root.afPlaying = true;  // one at a time: a second click mid-strike waits for the next
  AF.mount(root, before, { now: true, noStrike: true });
  const env0 = root.afEnv, W = env0.W, H = env0.H, st = {}, at = spot(latest, env0) || { x: W / 2, y: env0.hor };
  let g = overlayOn(root).getContext('2d');
  run((t, f) => {
    g.clearRect(0, 0, W, H);
    shower(g, W, H, Math.min(1, t / SHOWER_SECS), f, at.x, at.y, st);
    return t < SHOWER_SECS;
  }, () => {
    // the rock is down: the forest as it is now goes up, and the old one is torn apart over it
    const src = document.createElement('canvas'); src.width = W; src.height = H;
    src.getContext('2d').drawImage(root.querySelector('canvas.af-canvas'), 0, 0);
    AF.mount(root, data, { now: true, noStrike: true });
    const over = overlayOn(root), blast = {};
    g = over.getContext('2d');
    run((t, f) => {
      g.clearRect(0, 0, W, H);
      blownApart(g, W, H, t, f, at.x, at.y, blast, src);
      return t < BLAST_SECS;
    }, () => { over.remove(); root.afPlaying = false; if (done) done(); });
  });
};

AF.events.add('asteroid', {
  /* the ground: the craters */
  ground(env, lg) {
    env.craterBoxes = [];
    for (const c of env.data.craters || []) {
      const s = spot(c, env), rx = craterR(c.lost);
      if (!s) continue;
      crater(lg, s.x, s.y, c.lost, c.ago, env);
      if (c.ago <= CRATER_GONE) env.craterBoxes.push({ c, x0: s.x - rx, x1: s.x + rx, y0: s.y - rx * 0.4, y1: s.y + rx * 0.4 });
    }
  },
  /* behind the forest: the asteroid on its way */
  back(g, env, t) {
    const doom = env.data.doom, { W, H } = env;
    if (doom) {
      const k = clamp(doom.missed / doom.grace, 0, 1), f = Math.floor(t * 12);
      if (k > 0.3) { g.fillStyle = `rgba(150,40,20,${((k - 0.3) * 0.22).toFixed(3)})`; g.fillRect(0, 0, W, Math.round(H * 0.5)); }  // the sky reddens
      const x = Math.round(W * (0.78 - 0.2 * k)), y = Math.round(H * (0.07 + 0.2 * k)), r = Math.round(1 + k * 6);
      for (let i = 1; i < 6 + k * 30; i++) if (noise(i, f) < 1 - i / (8 + k * 32)) px(g, x + i * 1.2, y - i * 0.9, FIRE[Math.max(0, 5 - Math.floor(i / (2 + k * 5)))]);
      const disc = (rr, c) => { for (let dy = -rr; dy <= rr; dy++) for (let dx = -rr; dx <= rr; dx++) if (dx * dx + dy * dy <= rr * rr + rr * 0.6) px(g, x + dx, y + dy, c); };
      if (r >= 2) disc(r + 1, `rgba(255,170,80,${(0.25 + 0.3 * k).toFixed(2)})`);
      disc(r, r > 2 ? '#3a3230' : '#fff3b0');
      if (r > 2) { px(g, x - 1, y - 1, '#6a605a'); disc(Math.max(0, r - 3), '#2a2320'); }
      env.doomBox = { x0: x - r - 3, x1: x + r + 3, y0: y - r - 3, y1: y + r + 3 };
    }
  },
  /* in front of it: a fresh crater still smokes */
  front(g, env, t) {
    if (!env.still) for (const c of env.data.craters || []) {
      if (c.ago >= CRATER_FRESH) continue;
      const s = spot(c, env), f = Math.floor(t * 12);
      if (s) for (let i = 0; i < 9; i++) if (noise(i, f) < 0.75) px(g, s.x - 2 + Math.round(Math.sin(f * 0.25 + i) * 2 + i * 0.4), s.y - 3 - i * 2, `rgba(90,80,74,${(0.6 - i * 0.06).toFixed(2)})`);
    }
  },
  // what the pointer is over, if it is the asteroid or a crater: its tooltip, and whether a
  // click plays the strike again (the latest one can be watched again)
  pick(env, data, mx, my, animate) {
    const inBox = b => b && mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1;
    if (data.doom && inBox(env.doomBox)) return { html: doomText(data.doom) };
    const craters = data.craters || [], latest = replayable(data.strike) && craters[craters.length - 1];
    for (const b of env.craterBoxes || []) {
      if (!inBox(b)) continue;
      const replay = Boolean(animate && latest && b.c === latest);
      return { html: craterHtml(b.c), replay };
    }
    return null;
  },
  // the caption's items: [text, tooltip, a click (given the forest's root), if any]
  caption(data, words, animate) {
    const items = [], s = data.strike;
    if (s && s.news) {
      const again = animate && replayable(s);
      items.push([`Asteroid struck ${fmtShort(s.date)}`, `${s.lost} ${s.lost === 1 ? words.one : words.many} lost.`
        + (again ? ' Its crater can play it again too.' : animate ? '' : data.animations === 'system'
          ? ' Your system asks for less motion: set Animate the forest to On to watch it.'
          : ' Turn on animations in the forest settings to watch it.'),
      again ? root => root.afReplay() : undefined]);
    }
    const d = data.doom;
    if (d) items.push(['Asteroid: tonight', doomText(d)]);
    return items;
  },
  // Ready `root` to replay `data`'s latest strike, and play it now if it hasn't been seen
  // (`seen` says it has). True while it plays: it mounts the forest itself as it goes.
  mount(root, data, opts, animate, seen) {
    const s = data.strike;
    root.afReplay = () => {
      if (!s || root.afPlaying) return;
      if (s.before) { playStrike(root, data); return; }
      // the forest it took isn't on the page (it would be a second forest to carry): ask for it
      root.afPlaying = true;
      pycmd(`${data.channel}:strike:${s.seen}`, got => {
        root.afPlaying = false;
        if (got && got.before && root.afEnv && root.afEnv.data.strike === s) { s.before = got.before; s.merged = got.merged; playStrike(root, data); }
      });
    };
    if (!s || !s.fresh || (opts && opts.noStrike)) return false;
    if (!animate) { seen(); return false; }  // nothing to watch: seen, not saved up for the day animations come on
    playStrike(root, data, seen);
    return true;
  },
});
})();

/* Memory Forest — tumbleweeds for review hell: more overdue reviews than about twice a usual
 * day's (events.review_hell), and tumbleweeds roll across the front of the forest, more of
 * them the deeper it goes. On Merciless, more come to rest against the trees. The day the
 * backlog is cleared, the last of them blow away on the wind. Peaceful never has them. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { mixHex, clamp } = AF.u;
const { noise } = AF.events;

const MOST_ROLLING = 6;         // at the deepest review hell
const MOST_RESTING = 8;         // on Merciless, against the trees
const ROLL_SPEED = [0.05, 0.035];   // the forest's widths a second: the slowest, and how much faster some go
const BLOW_SPEED = 0.45;        // and when the wind takes them
// dark to light: the outer tangle, then the stems inside
const WEED = ['#6e5230', '#8a6a3c', '#a88652', '#d4b474'];

// in the light of the hour: the scene's tint, and darker on a dark meadow, as the flowers are
function palette(env) {
  if (env.tumblePal) return env.tumblePal;
  const th = env.theme, [r, g, b] = [1, 3, 5].map(i => parseInt(th.g0.slice(i, i + 2), 16) / 255);
  const dusk = clamp(0.6 - (0.3 * r + 0.59 * g + 0.11 * b), 0, 0.45);
  return (env.tumblePal = WEED.map(c => {
    if (th.tint) c = mixHex(c, th.tint, th.tintAmt);
    return dusk ? mixHex(c, th.g0, dusk) : c;
  }));
}

// a ball of dry stems about 7 pixels across, turned by `rot`
function weed(g, cx, cy, rot, pal) {
  cx = Math.round(cx); cy = Math.round(cy);
  for (let dy = -3; dy <= 3; dy++) for (let dx = -3; dx <= 3; dx++) {
    const r = Math.hypot(dx, dy);
    if (r > 3.4) continue;
    const s = Math.sin((Math.atan2(dy, dx) + rot) * 3 + r * 1.9);
    const c = r > 2.7 ? pal[s > -0.3 ? 1 : 0] : s > 0.25 ? pal[s > 0.75 ? 3 : 2] : null;
    if (c) { g.fillStyle = c; g.fillRect(cx + dx, cy + dy, 1, 1); }
  }
}

// where they roll: the front of the ground, or what a landscape names instead (as the tall grass)
function lanes(env) {
  const bot = Math.round(env.H * env.bot), land = AF.landOf(env);
  return land.grassRows ? land.grassRows(env) : [[0, env.W - 1, bot, bot + 1]];
}

// how many roll at this depth of review hell
const count = hell => 1 + Math.round(hell * (MOST_ROLLING - 1));

// each rolling tumbleweed at time t: its lane, how far it has come, and where it is
function rolling(env, t, n) {
  const rows = lanes(env), out = [];
  for (let k = 0; k < n; k++) {
    const [x0, x1, y] = rows[k % rows.length], span = x1 - x0 + 16;
    const speed = env.W * (ROLL_SPEED[0] + ROLL_SPEED[1] * noise(k, 'speed'));
    const dist = (env.still ? 0 : t * speed) + noise(k, 'start') * span;
    const bounce = env.still ? 0 : Math.abs(Math.sin(dist * 0.18)) * 3;
    out.push({ x: x0 - 8 + (dist % span), y: y - 4 - (k * 5) % 7 - bounce, ground: y - (k * 5) % 7, rot: dist / 3.4 });
  }
  return out;
}

// the day the backlog is cleared, the tumbleweeds of the review hell it `was` blow away, once
// (a day, or for each `replay` the Debug group asks for), as the forest opens
function blowing(env, t) {
  const data = env.data;
  if (env.still || !data.backlog || !data.backlog.cleared || !data.nature || data.nature === 'peaceful') return null;
  if (env.blowFrom === undefined) {
    let seen = false;
    const key = 'memory-forest-blown-' + (data.backlog.replay || data.dayNumber);
    try { seen = window.localStorage.getItem(key) === '1'; window.localStorage.setItem(key, '1'); } catch { /* no storage: it blows on every opening */ }
    env.blowFrom = seen ? null : t;
  }
  if (env.blowFrom === null) return null;
  const gone = rolling(env, env.blowFrom, count(data.backlog.was || 0.5)).map(w => {
    const dx = (t - env.blowFrom) * env.W * BLOW_SPEED * (1 + (w.x % 7) / 14);
    return Object.assign({}, w, { x: w.x + dx, y: w.ground - 4 - Math.abs(Math.sin(dx * 0.12)) * 5, rot: w.rot + dx / 3.4 });
  });
  if (gone.every(w => w.x > env.W + 8)) env.blowFrom = null;
  return gone;
}
AF.events.add('tumbleweeds', {
  // on Merciless they come to rest against the trees, the deeper the hell the more of them
  treeBase(env, lg, p, sw, x, y) {
    const b = env.data.backlog;
    if (!b || !b.hell || env.data.nature !== 'merciless' || p.it.pond) return;
    if (noise(p.it.seed, 'rest') > b.hell * MOST_RESTING / Math.max(1, env.placed.length)) return;
    weed(lg, x - sw / 2 - 2, y - 3, p.it.seed, palette(env));
  },
  // in front of the trees, and behind the animals, as the tall grass
  grass(g, env, t) {
    const b = env.data.backlog, pal = palette(env), shadow = 'rgba(20,24,12,0.22)';
    const weeds = b && b.hell ? rolling(env, t, count(b.hell)) : blowing(env, t) || [];
    env.tumbleBoxes = b && b.hell ? weeds.map(w => ({ x0: w.x - 4, x1: w.x + 4, y0: w.y - 4, y1: w.ground + 1 })) : [];
    for (const w of weeds) {
      g.fillStyle = shadow; g.fillRect(Math.round(w.x) - 2, Math.round(w.ground), 5, 1);
      weed(g, w.x, w.y, w.rot, pal);
    }
  },
  pick(env, data, mx, my) {
    const b = data.backlog;
    if (!b || !b.hell || !(env.tumbleBoxes || []).some(r => mx >= r.x0 && mx <= r.x1 && my >= r.y0 && my <= r.y1)) return null;
    return { html: `<b>Review hell</b>: ${b.overdue} reviews overdue${b.usual ? `, where a usual day has ${b.usual}` : ''}. Clear them and the tumbleweeds blow away.` };
  },
});
})();

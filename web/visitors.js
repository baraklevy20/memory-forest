/* Memory Forest — the milestone animals and the cabin: where they stand and how they move. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, hex, mix, rgb } = AF.u;
const { MATURE, OLD, ANCIENT } = AF.STAGE;
const { GROUND_BOTTOM } = AF.GEOM;

const VISITORS = {
  rabbit: { pal: { b: '#b9a38a', d: '#7a6450', e: '#2a2018', l: '#f1ebe2' }, frames: [
    ['..d.d...', '..d.d...', '..b.b...', '.bbbb...', 'bebbbbb.', '.blllbbl', '..d..d..'],
    ['...d.d..', '..d.d...', '..b.b...', '.bbbb...', 'bebbbbb.', '.blllbbl', '..d..d..']] },
  deer: { pal: { b: '#9a653f', d: '#5a3a26', l: '#c9a07a', w: '#f4ede4' }, frames: [
    ['.......d.d.', '........d..', '.......bbb.', '.......bbbl', 'lbbbbbbbb..', '.bbbbbbbb..', '.d.d..d.d..', '.d.d..d.d..'],
    ['...........', '...........', '...........', '.......d.d.', 'wbbbbbbbd..', '.bbbbbbbbb.', '.d.d..d.bbl', '.d.d..d.d..']] },
  stag: { pal: { b: '#8a5a38', d: '#4e3220', l: '#c9a07a', w: '#f4ede4' }, frames: [
    ['......d...d', '......dd.dd', '.......ddd.', '.......bbb.', '.......bbbl', 'lbbbbbbbb..', '.bbbbbbbb..', '.d.d..d.d..', '.d.d..d.d..'],
    ['...........', '...........', '...........', '...........', '......d.d.d', 'wbbbbbbbdd.', '.bbbbbbbbb.', '.d.d..d.bbl', '.d.d..d.d..']] },
  fox: { pal: { o: '#d9772e', w: '#f3ece2', d: '#3a2418', e: '#1a1008' }, frames: [
    ['........o.o', '........ooo', '........oeow', 'ww.oooooooo', '.wooooooo..', '..d.d..d.d.'],
    ['........o.o', '........ooo', '........oeow', '.w.oooooooo', 'w.ooooooo..', '..d.d..d.d.']] },
  // (the animals perched or sitting in the forest are painted once, into the land: one frame)
  // its eyes are orange, not yellow: yellow on a tree means forgetting
  owl: { pal: { b: '#8a7458', d: '#3e3226', y: '#e8703a', l: '#d8c8a8' }, frames: [
    ['d...d', 'bbbbb', 'bybyb', 'bbdbb', 'blllb', 'blllb', '.b.b.']] },
  heron: { pal: { g: '#9aa4ae', e: '#1a1a1a', d: '#e0a33a', w: '#e6eaee', k: '#4a4f55' }, frames: [
    ['..gg....', '.gegddd.', '..g.....', '..g.....', '.ggg....', 'gggww...', '.gggw...', '..ggg...', '...k....', '...k....', '..kk....']] },
  // sitting up at the foot of its tree with an acorn in its paws, 6 px like the fox; red-brown,
  // its tail curled behind it below the ears, so nothing reads as a yellowing crown
  squirrel: { pal: { r: '#8a3e1c', R: '#6a2c12', t: '#a04a22', T: '#70301a', l: '#e2bf94', e: '#140a04', d: '#3e1a0a', a: '#9a6a36', c: '#4e3016' }, frames: [
    ['.tt..d.d', 'tTTt.rrr', 'tTt.Rrer', '.tTRrrlc', '..tRrrla', '...d.dd.']] },
  // walking with its nose to the ground
  bear: { pal: { b: '#5a3e2c', h: '#7a5a40', d: '#3a271a', e: '#0c0604', l: '#c4a47c', n: '#120a06' }, frames: [
    ['....hhhhhhh......', '..hhbbbbbbbbh....', '.hbbbbbbbbbbbbd.d', '.bbbbbbbbbbbbbddd', '.bbbbbbbbbbbbbbeb', '.bbbbbbbbbbb.bbll', '..bbb..bbb....bln', '..ddd..ddd.......'],
    ['....hhhhhhh......', '..hhbbbbbbbbh....', '.hbbbbbbbbbbbbd.d', '.bbbbbbbbbbbbbddd', '.bbbbbbbbbbbbbbeb', '.bbbbbbbbbbb.bbll', '...bbb..bbb...bln', '...ddd..ddd......']] },
  // gliding, and with its wings raised: d dark wings, b body, h its white head and tail, y beak
  eagle: { flies: true, pal: { d: '#2a2018', b: '#4e3c2c', h: '#f4ede4', y: '#e8b030' }, frames: [
    ['......hh.....', 'dd...bbhy....', '.dddbbbbbbdd.', '...ddbbbbdd..', '......hh.....'],
    ['d..........d.', '.dd..hh...dd.', '...dbbhy.d...', '....bbbbbb...', '......hh.....']] },
  cabin: { pal: { c: '#6e6a70', r: '#7a3a2e', R: '#5a2a22', w: '#9a7250', W: '#7a5a3e', o: '#3e2a1c', n: '#2e3a4a' }, frames: [
    ['......cc....', '......cc....', '...rrrrrrr..', '..rrrrrrrrR.', '.rrrrrrrrrRR', 'RRRRRRRRRRRR', '.wWwWwWwWwW.', '.woowWwnnwW.', '.woowWwnnwW.', '.woowWwWwWw.']] }
};
const FRONT_SLOTS = [0.9, 0.22, 0.75, 0.38, 0.6];
// seconds: each animal at the front moves on every ROAM_EVERY (plus a little more per
// animal, and offset by ROAM_OFFSET each, so they never set off together) and takes
// WALK_SECS to get there, stepping WALK_FPS frames a second
const ROAM_EVERY = 150, ROAM_STAGGER = 41, ROAM_OFFSET = 37, WALK_SECS = 4, WALK_FPS = 4;
// how far either side of its spot an animal wanders, as a share of the width
const ROAM_REACH = 0.045;
// a resting animal shows its second frame (a glance, a nibble) while a slow wave is above this
const IDLE_GLANCE = 0.93;
// a rabbit covers its walk in RABBIT_HOPS hops, RABBIT_HOP_PX high
const RABBIT_HOPS = 5, RABBIT_HOP_PX = 3;
// the animals stand this far below the front row (of the height), never off the canvas
const VISITOR_DROP = 0.025, VISITOR_LOWEST = 0.995;
const CABIN_X = 0.05, CABIN_SMOKE_PUFFS = 4;
// the owl's eyes catching the light at night (warm, never yellow)
const OWL_NIGHT_EYES = '#ffa070';
// a pond this near the front (within FRONT_TALLEST pixels above the animals' feet) is in
// their way; they and the cabin keep FRONT_CLEAR pixels off its water
const FRONT_TALLEST = 11, FRONT_CLEAR = 1;
// a flying animal circles SKY_X, SKY_Y (of the width and height), SKY_RX and SKY_RY across,
// SKY_TURN radians a second, raising its wings one beat in SKY_FLAP_EVERY (SKY_FLAP_FPS a second)
const SKY_X = 0.66, SKY_Y = 0.16, SKY_RX = 0.09, SKY_RY = 0.04, SKY_TURN = 0.35, SKY_FLAP_FPS = 2.5, SKY_FLAP_EVERY = 5;
const FACES_LEFT = { rabbit: true };  // which way each sprite is drawn looking

function paintSprite(g, rows, x0, y0, pal, colorOf, flip = false) {
  let style = null;
  rows.forEach((row, yy) => {
    for (let xx = 0; xx < row.length; xx++) {
      const ch = row[xx]; if (ch === '.') continue;
      const c = colorOf(pal[ch] || '#000000', ch);
      if (c !== style) g.fillStyle = style = c;
      g.fillRect(x0 + (flip ? row.length - 1 - xx : xx), y0 + yy, 1, 1);
    }
  });
}
/* the line the animals at the front and the cabin stand on */
const frontY = env => Math.round(env.visitorY || env.H * Math.min(VISITOR_LOWEST, (env.bot || GROUND_BOTTOM) + VISITOR_DROP));
/* A new arrangement every day, the same all day: the date mixed into the forest's seed. */
const daySeed = env => ((env.data.forestSeed || 3) ^ Math.imul((env.data.dayNumber || 0) + 1, 2654435761)) >>> 0;
function visitorColor(env, hz) {
  const th = env.theme, tint = th.tint ? hex(th.tint) : null, haze = hex(th.haze);
  // worked out once a scene for each colour and haze: the animals are drawn every frame
  const seen = env.visitorColors || (env.visitorColors = new Map());
  return col => {
    if (env.visitorTint) return env.visitorTint;
    const key = hz + '|' + col;
    let out = seen.get(key);
    if (out === undefined) {
      let c = hex(col); if (tint) c = mix(c, tint, th.tintAmt); if (hz) c = mix(c, haze, hz * th.hzStep * 4);
      seen.set(key, out = rgb(c));
    }
    return out;
  };
}

/* An environment may keep stretches of the scene clear of animals and the cabin
 * (`keepClear`: [from, to] pairs, as shares of the width), e.g. where something of its own
 * stands in front of everything. In pixels here. */
const clearSpans = env => (AF.envOf(env).keepClear || []).map(([a, b]) => [a * env.W, b * env.W]);
const inClear = (env, x0, x1) => clearSpans(env).some(([a, b]) => x1 > a && x0 < b);

/* animals that live inside the forest are drawn into the land at the right depth */
AF.placeVisitors = function (env) {
  const list = env.data.visitors || [], keys = list.map(v => v.key);
  // no animal's tree (nor pond) stands in a stretch the environment keeps clear
  const open = p => !inClear(env, p.x - 6, p.x + 10);
  const trees = env.placed.filter(p => !p.it.pond && open(p));
  const inForest = {}, front = [];
  const R = rng(daySeed(env)), any = pool => pool[Math.floor(R() * pool.length)];
  // the owl perches on one of the oldest trees, the heron wades at one of the ponds
  const old = trees.filter(p => p.it.stage === ANCIENT), older = old.length ? old : trees.filter(p => p.it.stage === OLD);
  if (keys.includes('owl') && older.length) inForest.owl = { host: any(older) };
  const ponds = env.placed.filter(p => p.it.pond && p.it.first && open(p));
  if (keys.includes('heron') && ponds.length) inForest.heron = { host: any(ponds) };
  // the squirrels sit at the foot of a grown tree the owl hasn't taken
  const grown = trees.filter(p => p.it.stage >= MATURE && (!inForest.owl || p !== inForest.owl.host));
  if (keys.includes('squirrel') && grown.length) inForest.squirrel = { host: any(grown) };
  const band = (lo, hi) => trees.filter(p => p.it.fromFront >= lo && p.it.fromFront <= hi);
  for (const [key, lo, hi] of [['deer', 2, 4], ['stag', 4, 6]]) {
    if (!keys.includes(key)) continue;
    // never on a tree another animal already took
    const taken = new Set(Object.values(inForest).map(s => s.host));
    const free = list => list.filter(p => !taken.has(p));
    const pool = free(band(lo, hi)).length ? free(band(lo, hi)) : free(band(0, 2));
    if (pool.length) inForest[key] = { host: any(pool), graze: true };
  }
  // the rest stand at the front, but the cabin (which has its own corner) and those that fly
  for (const v of list) if (!inForest[v.key] && v.key !== 'cabin' && !(VISITORS[v.key] || {}).flies) front.push(v);
  env.inForest = inForest; env.frontVisitors = front; env.flyers = list.filter(v => (VISITORS[v.key] || {}).flies); env.staticBoxes = [];
  const byHost = new Map();
  for (const [key, spot] of Object.entries(inForest)) byHost.set(spot.host, (byHost.get(spot.host) || []).concat([key]));
  env.afterItem = (lg, p) => {
    const keysHere = byHost.get(p); if (!keysHere) return;
    for (const key of keysHere) {
      const spr = VISITORS[key], v = list.find(x => x.key === key), frame = spr.frames[inForest[key].graze ? 1 : 0];
      let x0, y0;
      if (key === 'owl') { const h = AF.STAGE_H[p.it.stage] * env.u * p.s; x0 = Math.round(p.x - 2); y0 = Math.round(p.y - h - frame.length + 3); }
      else if (key === 'squirrel') { x0 = Math.round(p.x) + (AF.trunkRight ? AF.trunkRight(p, env) : 1); y0 = Math.round(p.y - frame.length + 1); }  // on the roots, just right of the trunk
      else if (key === 'heron') { const b = AF.pondBox(env, p); x0 = Math.round(b.cx + b.w * 0.2); y0 = Math.round(b.cy - frame.length + 1); }
      else { x0 = Math.round(p.x + 4); y0 = Math.round(p.y - frame.length + 1); }
      paintSprite(lg, frame, x0, y0, spr.pal, visitorColor(env, p.hz));
      if (key === 'owl' && env.mood.time === 'night') { lg.fillStyle = OWL_NIGHT_EYES; lg.fillRect(x0 + 1, y0 + 2, 1, 1); lg.fillRect(x0 + 3, y0 + 2, 1, 1); }
      env.staticBoxes.push({ v, x0, y0, x1: x0 + frame[0].length, y1: y0 + frame.length });
    }
  };
};

/* the eagle circles high over the forest, behind the trees */
AF.drawFlyers = function (g, env, t) {
  const { W, H } = env, color = visitorColor(env, 0);
  env.skyBoxes = [];
  (env.flyers || []).forEach(v => {
    const spr = VISITORS[v.key], a = env.still ? 1 : t * SKY_TURN;
    const cx = Math.round(W * SKY_X + Math.cos(a) * W * SKY_RX), cy = Math.round(H * SKY_Y + Math.sin(a) * H * SKY_RY);
    const frame = spr.frames[!env.still && Math.floor(t * SKY_FLAP_FPS) % SKY_FLAP_EVERY === 0 ? 1 : 0];
    const x0 = cx - Math.floor(frame[0].length / 2), y0 = cy - Math.floor(frame.length / 2);
    paintSprite(g, frame, x0, y0, spr.pal, color, Math.sin(a) > 0);  // it faces the way it circles
    env.skyBoxes.push({ v, x0: x0 - 1, y0: y0 - 1, x1: x0 + frame[0].length + 1, y1: y0 + frame.length + 1 });
  });
};

/* The ponds that reach the front, and where the cabin stands: in its corner, or the other
 * one if a pond is there. Worked out on the first frame, once the land (an island's edge)
 * has said where the front is. */
function frontWay(env, baseY) {
  if (env.frontWay) return env.frontWay;
  const cw = VISITORS.cabin.frames[0][0].length, ch = VISITORS.cabin.frames[0].length;
  const ponds = env.placed.filter(p => p.it.pond && p.it.first).map(p => AF.pondBox(env, p)).filter(b => b.y1 > baseY - FRONT_TALLEST);
  const pondAt = x0 => ponds.some(b => x0 + cw + FRONT_CLEAR > b.x0 && x0 - FRONT_CLEAR < b.x1 && baseY > b.y0 && baseY - ch < b.y1);
  const takenAt = x0 => pondAt(x0) || inClear(env, x0, x0 + cw);
  const left = Math.round(env.W * CABIN_X), right = env.W - left - cw;
  return (env.frontWay = { ponds, cabinX: takenAt(left) && !takenAt(right) ? right : left });
}

/* the rest stand at the edge of the forest; the cabin sits front-left after a year (or front-right) */
AF.drawVisitors = function (g, env, t) {
  const list = env.frontVisitors || [], color = visitorColor(env, 0);
  env.visitorBoxes = (env.staticBoxes || []).concat(env.skyBoxes || []);
  const baseY = frontY(env), way = frontWay(env, baseY);
  const cabin = (env.data.visitors || []).find(v => v.key === 'cabin');
  if (cabin) {
    const spr = VISITORS.cabin, frame = spr.frames[0], x0 = way.cabinX, y0 = baseY - frame.length, lit = env.mood.time === 'night' || env.mood.time === 'dusk';
    paintSprite(g, frame, x0, y0, spr.pal, (col, ch) => ch === 'n' && lit ? '#ffd27a' : color(col));
    if (lit) { g.fillStyle = 'rgba(255,210,122,.18)'; g.fillRect(x0 + 6, y0 + 6, 4, 4); }
    else if (!env.theme.rain) for (let k = 0; k < CABIN_SMOKE_PUFFS; k++) { const q = (t * 0.25 + k / CABIN_SMOKE_PUFFS) % 1, sx = x0 + 6 + Math.round(Math.sin(q * 6 + k) * 1.5 + q * 4), sy = y0 - Math.round(q * 12); g.fillStyle = `rgba(220,220,225,${0.55 * (1 - q)})`; g.fillRect(sx, sy, q > 0.5 ? 2 : 1, 1); }
    env.visitorBoxes.push({ v: cabin, x0, y0, x1: x0 + frame[0].length, y1: baseY });
  }
  // Each animal has its own stretch of the front, shuffled daily. Every few minutes it
  // wanders to a new spot in that stretch, then stays there a while.
  const slots = FRONT_SLOTS.slice(), SR = rng(daySeed(env) ^ 0x51ed);
  for (let i = slots.length - 1; i > 0; i--) { const j = Math.floor(SR() * (i + 1)); [slots[i], slots[j]] = [slots[j], slots[i]]; }
  list.forEach((v, i) => {
    const spr = VISITORS[v.key]; if (!spr || i >= slots.length) return;
    const W = env.W, roam = W * ROAM_REACH, period = ROAM_EVERY + i * ROAM_STAGGER, walk = WALK_SECS, k = Math.floor((t + i * ROAM_OFFSET) / period), ph = (t + i * ROAM_OFFSET) - k * period;
    // a landscape with water across the front keeps each animal to its own bank
    const home = W * slots[i], land = AF.landOf(env);
    // ...and off any pond at the front, and the cabin: stepped aside to its nearer edge
    const half = spr.frames[0][0].length / 2 + FRONT_CLEAR, lo = half, hi = W - half, cabinW = VISITORS.cabin.frames[0][0].length;
    const blocks = way.ponds.map(b => [b.x0 - half, b.x1 + half]);
    if (cabin) blocks.push([way.cabinX - half, way.cabinX + cabinW + half]);
    for (const [a, b] of clearSpans(env)) blocks.push([a - half, b + half]);
    const blocked = x => blocks.some(([a, b]) => x > a && x < b) || (land.wet && land.wet(env, x - half, x + half, baseY));
    const aside = x => {
      const hit = blocks.find(([a, b]) => x > a && x < b); if (!hit) return x;
      const ok = [hit[0], hit[1]].filter(c => c >= lo && c <= hi && !blocked(c)).sort((a, b) => Math.abs(a - x) - Math.abs(b - x));
      return ok.length ? ok[0] : x;
    };
    const spot = n => { const s = home + (rng((daySeed(env) + n * 7919 + i * 104729) >>> 0)() - 0.5) * 2 * roam; return aside(land.dryX ? land.dryX(env, s, baseY, home, roam) : s); };
    // (two spots the same, or all but, and it stays put rather than walking on the spot)
    const from = spot(k - 1), to = spot(k), moving = !env.still && ph < walk && Math.abs(to - from) >= 1, q = moving ? ph / walk : 1;
    const x = from + (to - from) * q, dir = to >= from ? 1 : -1;
    let frame = spr.frames[moving ? Math.floor(ph * WALK_FPS) % spr.frames.length : (Math.sin(t * 0.7 + i * 2.1) > IDLE_GLANCE ? spr.frames.length - 1 : 0)], dy = 0;
    // a rabbit hops rather than walks
    if (v.key === 'rabbit') { frame = spr.frames[0]; if (moving) dy = -Math.round(Math.abs(Math.sin(q * Math.PI * RABBIT_HOPS)) * RABBIT_HOP_PX); }
    const flip = FACES_LEFT[v.key] ? dir > 0 : dir < 0;  // face the way it last went
    const x0 = Math.round(x - frame[0].length / 2), y0 = baseY - frame.length + dy;
    paintSprite(g, frame, x0, y0, spr.pal, color, flip);
    // an environment may dress the animal up (it gets the frame as drawn, and which way it faces)
    const dress = AF.envOf(env).dressVisitor;
    if (dress) dress(g, env, { key: v.key, rows: frame, x0, y0, flip, facesLeft: !!FACES_LEFT[v.key] !== flip, color });
    env.visitorBoxes.push({ v, x0, y0, x1: x0 + frame[0].length, y1: baseY });
  });
};
})();

/* Memory Forest — tall grass: a week and more without new cards while you keep reviewing,
 * and the grass grows tall at the front of the forest, taller the longer it goes on. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, clamp } = AF.u;
const { px } = AF.events;

// Long blades bending over the same way, as if in a breeze: more of them, and taller, the
// longer it goes on. Each blade takes the colour of the ground it grows from, with a touch of
// the trees' (so it reads as that ground's grass: plum on a lantern night, not green), darker
// at the root and lighter at the tip. It grows where there is ground at the front - on
// the front of the ground, or along what a landscape names instead (its grassRows) - and leaves
// a path through the scenery clear.
// the trees' greens, for an engine that doesn't say what colours its crowns are
const GRASS_GREENS = [[28, 43, 34], [45, 74, 51], [63, 106, 60], [95, 140, 74], [143, 179, 94]];
const GRASS_TREE = 0.2;                  // how much of the trees' colour goes into a blade
const GRASS_SHADE = [0.92, 1.12, 1.25];  // root, middle and tip, against the ground
// [x0, x1, y the blades grow from, y of the ground they take their colour from]
function grassRows(env) {
  const bot = Math.round(env.H * env.bot), land = AF.landOf(env);
  return land.grassRows ? land.grassRows(env) : [[0, env.W - 1, bot, bot + 1]];
}
// whether a blade rooted on row y at x0, leaning to x1 and reaching up to row top, would cover a flower
function hides(flowers, x0, x1, top, y) {
  for (let x = Math.floor(x0) - 1; x <= Math.ceil(x1) + 1; x++) { const f = flowers.get(x); if (f !== undefined && f >= top - 1 && f <= y + 1) return true; }
  return false;
}
function drawGrass(g, env, s, t) {
  const pal = AF.foliage ? AF.foliage(env) : GRASS_GREENS, R = rng(0x9a55), gust = env.still ? 0 : Math.sin(t * 0.8) * 0.15;
  const spec = AF.envOf(env), path = spec.pathAt && (y => spec.pathAt(env, y)), flowers = env.flowerCols;
  for (const [x0, x1, y, groundY] of grassRows(env)) {
    const ground = (env.grassSoil && env.grassSoil.get(groundY)) || g.getImageData(0, groundY, env.W, 1).data;
    for (let x = x0; x <= x1; x++) {
      if (R() > 0.25 + s * 0.6) continue;
      const h = 2 + Math.round(R() * (3 + s * 9)), bend = 0.5 + gust;
      if (path) { const [a, b] = path(y); if (x + h * bend >= a - 1 && x <= b + 1) continue; }
      if (flowers && hides(flowers, x, x + h * bend, y - h, y)) continue;  // a big day's flowers stay in sight
      const root = [ground[x * 4], ground[x * 4 + 1], ground[x * 4 + 2]];
      for (let k = 0; k < h; k++) {
        const part = k > h - 2 ? 2 : k > h * 0.4 ? 1 : 0, leaf = pal[part + 2], f = GRASS_SHADE[part];
        const c = root.map((v, i) => clamp(Math.round((v * (1 - GRASS_TREE) + leaf[i] * GRASS_TREE) * f), 0, 255));
        px(g, x + Math.round((k / h) ** 2 * h * bend), y - k, `rgb(${c[0]},${c[1]},${c[2]})`);
      }
    }
  }
}

AF.events.add('grass', {
  // Read once, from the bare ground as it is painted: the live frame would lend the blades
  // whatever happens to be there (a lantern's light, a passing animal, the grass itself).
  soil(env, lg) {
    env.flowerCols = new Map();  // filled in as a big day's flowers draw (flowers.js), which the grass leaves clear
    env.grassSoil = new Map(grassRows(env).map(([, , , gy]) => [gy, lg.getImageData(0, gy, env.W, 1).data]));
  },
  // drawn after the forest but before the animals, so they stand in it
  grass(g, env, t) {
    const s = env.data.stagnation || 0;
    if (s > 0) drawGrass(g, env, s, t);
  },
});
})();

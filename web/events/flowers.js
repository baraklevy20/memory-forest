/* Memory Forest — wildflowers for a big day of learning: flowers at the foot of that day's
 * tree, one kind to a tree. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { rng, mixHex, clamp } = AF.u;
const { px } = AF.events;

// A big day's flowers, one kind to a tree, taking turns by the tree's seed: daisies, tulips,
// poppies and bluebells. Nothing yellow but a daisy's pinprick of a heart - yellow means forgetting.
const STEM = '#3f6a30', LEAF = '#5a8a3e';
const FLOWERS = [
  (put, x, y, R, sw) => {  // daisies: long white petals round a golden heart, each on its own stem
    // few and spaced out, so each reads as a flower and not a white smudge
    const n = 5, span = Math.max(sw + 14, 30);
    for (let k = 0; k < n; k++) {
      const fx = Math.round(x - span / 2 + (k + 0.5) * span / n + (R() - 0.5) * 2), fy = Math.round(y + R() * 3) - 4 - (k % 2);
      for (let s = 3; s <= 4 + (k % 2); s++) put(fx, fy + s, STEM);
      put(fx + (k % 2 ? 1 : -1), fy + 4, LEAF);
      for (const [dx, dy] of [[0, -2], [0, -1], [-2, 0], [-1, 0], [1, 0], [2, 0], [0, 1], [0, 2]]) put(fx + dx, fy + dy, Math.abs(dx + dy) === 2 ? '#ececf0' : '#ffffff');
      put(fx, fy, '#f0c040');
    }
  },
  (put, x, y, R, sw) => {  // tulips: upright cups of pink and red on tall stems
    const cups = ['#ff6a8a', '#e8405a', '#ff9ab4'];
    for (let k = 0; k < 7; k++) { const fx = Math.round(x + (R() - 0.5) * (sw + 12)), fy = Math.round(y + R() * 2), h = 3 + Math.round(R() * 2), c = cups[k % 3];
      for (let s = 1; s <= h; s++) put(fx, fy - s, STEM);
      put(fx - 1, fy - 1, LEAF); put(fx - 1, fy - 2, LEAF);
      put(fx - 1, fy - h - 1, c); put(fx + 1, fy - h - 1, c); put(fx, fy - h - 1, c); put(fx - 1, fy - h - 2, c); put(fx + 1, fy - h - 2, c); }
  },
  (put, x, y, R, sw) => {  // poppies: scarlet cups with a dark centre, on thin stems
    for (let k = 0; k < 8; k++) { const fx = Math.round(x + (R() - 0.5) * (sw + 14)), fy = Math.round(y + R() * 2), h = 2 + Math.round(R() * 2);
      for (let s = 1; s <= h; s++) put(fx, fy - s, STEM);
      put(fx - 1, fy - h - 1, '#e8341c'); put(fx + 1, fy - h - 1, '#e8341c'); put(fx, fy - h - 2, '#ff5a3a'); put(fx, fy - h - 1, '#2a1410'); }
  },
  (put, x, y, R, sw) => {  // bluebells: curved stems with little bells hanging down one side
    for (let k = 0; k < 6; k++) { const fx = Math.round(x + (R() - 0.5) * (sw + 12)), fy = Math.round(y + R() * 2);
      for (let s = 1; s <= 4; s++) put(fx, fy - s, STEM);
      put(fx + 1, fy - 5, STEM);
      for (let b = 0; b < 3; b++) put(fx + 2, fy - 4 + b, '#6a8ae8');
      put(fx + 2, fy - 1, '#4a6ad0'); }
  },
];
// In the light of the hour, and fading into the distance, as the trees and animals do. The
// darker the ground, the more of it the petals take on: a daisy's white would glare like a
// lamp on a night meadow.
const FLOWER_DUSK = 0.6;  // ground this bright or brighter leaves the petals their own colour
const FLOWER_DUSK_MAX = 0.35;  // however dark it gets, the petals keep most of their colour
function tone(env, hz) {
  const th = env.theme, fade = hz ? hz * th.hzStep * 4 : 0, [r, g, b] = [1, 3, 5].map(i => parseInt(th.g0.slice(i, i + 2), 16) / 255);
  const dusk = clamp(FLOWER_DUSK - (0.3 * r + 0.59 * g + 0.11 * b), 0, FLOWER_DUSK_MAX);
  return c => {
    if (th.tint) c = mixHex(c, th.tint, th.tintAmt);
    if (dusk) c = mixHex(c, th.g0, dusk);
    return fade ? mixHex(c, th.haze, Math.min(1, fade)) : c;
  };
}

AF.events.add('flowers', {
  treeBase(env, lg, p, sw, x, y) {
    if (!p.it.big) return;
    const tint = tone(env, p.hz), cols = env.flowerCols || (env.flowerCols = new Map());
    FLOWERS[p.it.seed % FLOWERS.length]((fx, fy, c) => {
      px(lg, fx, fy, tint(c));
      fx = Math.round(fx); cols.set(fx, Math.min(cols.get(fx) ?? Infinity, Math.round(fy)));  // the tall grass leaves them room
    }, x, y, rng(p.it.seed ^ 0xf10e), sw);
  },
});
})();

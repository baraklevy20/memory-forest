/* Memory Forest — crows for leeches: a crow on each tree that holds a leech (up to three
 * a tree), staying until the leech is fixed. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { px, noise } = AF.events;

// a crow perched, and with its wings up; k black, s a blue-black sheen, b its beak, e an eye's glint
const CROW = ['....kk.', '...kkeb', 'ksskkk.', '.kkkkk.', '..k.k..'], CROW_UP = ['k...kk.', '.k.kkeb', '..skkk.', '.kkkkk.', '..k.k..'];
const CROW_PAL = { k: '#18161e', s: '#3a3a56', b: '#2e2c34', e: '#cfd2e0' };

AF.events.add('crows', {
  front(g, env, t) {
    const trees = env.placed.filter(p => !p.it.pond);
    // crows on the trees that hold leeches, one per leech (up to three a tree)
    for (const p of trees) {
      if (!p.it.leeches) continue;
      const h = AF.STAGE_H[p.it.stage] * env.u * p.s, n = Math.min(3, p.it.leeches);
      for (let i = 0; i < n; i++) {
        const x = Math.round(p.x - 6 + i * 5 + (i % 2)), y = Math.round(p.y - h - 3 + (i % 2)), flap = !env.still && noise(p.it.seed + i, Math.floor(t / 2)) < 0.08;
        const flip = (p.it.seed >> i) & 1;  // some look left, some right
        (flap ? CROW_UP : CROW).forEach((row, yy) => { for (let xx = 0; xx < row.length; xx++) { const ch = row[xx]; if (ch !== '.') px(g, x + (flip ? row.length - 1 - xx : xx), y + yy - (flap ? 1 : 0), CROW_PAL[ch]); } });
      }
    }
  },
});
})();

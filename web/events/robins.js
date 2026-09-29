/* Memory Forest — a robin for a leech cured: it sits on the tree that held the leech, where
 * its crow was, for a week after (events.CURED_DAYS). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { px, noise, perch } = AF.events;

// perched, facing right: h its head, w a wing, T the tail, o the orange breast (O where it
// catches the light), W a pale belly, e an eye, y the beak, d a leg
const ROBIN = ['.....hh..', '....hheoy', '..wwhooo.', 'TwwwwooO.', 'TT.wwWW..', '.....d...'];
const ROBIN_PAL = { h: '#7a6452', w: '#5a4838', T: '#4a3a2e', o: '#e0602a', O: '#f07a40', W: '#f0e0d0', e: '#101010', y: '#e8b030', d: '#3a2a1a' };

AF.events.add('robins', {
  front(g, env, t) {
    for (const p of env.placed) {
      if (p.it.pond || !p.it.cured) continue;
      const h = AF.STAGE_H[p.it.stage] * env.u * p.s, crows = Math.min(3, p.it.leeches || 0);
      // now and then it hops, or turns to look the other way
      const hop = !env.still && noise(p.it.seed + 7, Math.floor(t * 1.6)) < 0.12 ? 1 : 0;
      const flip = !env.still && noise(p.it.seed + 9, Math.floor(t / 3.5)) < 0.35;
      // standing on the crown's top (its leg, the sprite's bottom row, sixth column), left of any
      // crows still there for other leeches (crows.js puts them from the middle rightwards)
      const at = perch(env, p, Math.round(p.x) - (crows ? 10 : 0), Math.round(p.y - h + 1));
      const x = at.x - (flip ? 3 : 5), y = at.y - ROBIN.length + 1 - hop;  // its leg stays put when it turns
      ROBIN.forEach((row, yy) => { for (let xx = 0; xx < row.length; xx++) { const ch = row[xx]; if (ch !== '.') px(g, x + (flip ? row.length - 1 - xx : xx), y + yy, ROBIN_PAL[ch]); } });
    }
  },
});
})();

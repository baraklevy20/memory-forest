/* Memory Forest - the heatmap's Canes tiles (the Heatmap tab's Tiles; canes.json, Bamboo grove's own):
 * each day two short canes side by side, as the grove's: each a lit side, a body and a shaded side, a
 * dark joint ring across it at its own height (the variant moves them) and a pale sheen just above.
 * Every tone is a multiple of the shade, so the shades keep their distance (mixed toward white, they
 * drew together). Not in the page's own scripts: the heatmap loads it when it is drawn in it
 * (heatmap_look.page_look's `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { rgb } = AF.u;
const scaled = (c, k) => c.map(q => Math.max(0, Math.min(255, q * k)));
const JOINTS = [[2, 5], [4, 1], [1, 5], [5, 3]];
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.canes = {
  draw(g, pal, edge, v, T) {
    const n = T - 1, s = pal[0];  // (the last row and column: the gap between tiles)
    const J = JOINTS[v % 4];  // (each cane's joint row)
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if ((x === 0 || x === n - 1) && (y === 0 || y === n - 1)) continue;
      const cx = x & 3, j = J[x < 4 ? 0 : 1];
      let c = cx === 0 ? scaled(s, 1.14) : cx === 3 ? scaled(s, 0.78) : cx === 2 ? scaled(s, 0.84) : s;
      if (y === j) c = scaled(s, 0.7);
      else if (y === j - 1 && cx < 3) c = scaled(s, 1.2);
      g.fillStyle = rgb(c); g.fillRect(x, y, 1, 1);
    }
  },
};
})();

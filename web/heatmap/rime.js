/* Memory Forest - the heatmap's Rime tiles (the Heatmap tab's Tiles; rime.json, Misty valley's own):
 * each day's tile rimed like the scenery's crowns, a broken line of frost along the top edge and a few
 * crystals of it below, on the shade's own face, its corners left off as the plain tiles' are. Not in
 * the page's own scripts: the heatmap loads it when it is drawn in it (heatmap_look.page_look's
 * `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { mix, rgb } = AF.u;
const RIME = [236, 248, 246];
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.rime = {
  draw(g, pal, edge, v, T) {
    const n = T - 1;  // (the last row and column: the gap between tiles)
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if ((x === 0 || x === n - 1) && (y === 0 || y === n - 1)) continue;
      const frost = y === 0 ? ((x + v) % 3 === 2 ? 0.25 : 0.62) : y === 1 && (x + v) % 4 === 1 ? 0.32 : 0;
      g.fillStyle = rgb(frost ? mix(pal[0], RIME, frost) : pal[0]);
      g.fillRect(x, y, 1, 1);
    }
  },
};
})();

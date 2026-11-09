/* Memory Forest - the heatmap's Pumpkins tiles (the Heatmap tab's Tiles; pumpkin.json, Witch across the
 * moon's own, in its week only): each day's tile a pumpkin, round at the corners, ribbed down, with a
 * dip at the top where the stem sits. Not in the page's own scripts: the heatmap loads it when it is
 * drawn in it (heatmap_look.page_look's `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { mix, rgb } = AF.u;
const RIB_LIGHT = [255, 250, 235];
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.pumpkin = {
  draw(g, pal, edge, v, T) {
    const n = T - 1;  // (the last row and column: the gap between tiles)
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if ((x === 0 || x === n - 1) && (y === 0 || y === n - 1) || y === 0 && (x === 3 || x === 4)) continue;
      g.fillStyle = rgb(x === 2 || x === 5 ? pal[1] : x === 1 || x === 4 ? mix(pal[0], RIB_LIGHT, 0.1) : pal[0]);
      g.fillRect(x, y, 1, 1);
    }
  },
};
})();

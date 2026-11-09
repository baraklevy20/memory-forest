/* Memory Forest - the heatmap's Ice blocks tiles (the Heatmap tab's Tiles; ice.json, Frozen river
 * market's own, in its week only): each day's tile as clear ice, a bright shine across one corner,
 * frosted corners, and deeper towards the far corner. Not in the page's own scripts: the heatmap loads
 * it when it is drawn in it (heatmap_look.page_look's `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { mix, rgb } = AF.u;
const ICE_SHINE = [255, 250, 235];
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.ice = {
  draw(g, pal, edge, v, T) {
    const n = T - 1;  // (the last row and column: the gap between tiles)
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const d = x + y;
      // (a chip of light in the near corner and one clean streak: the two thin diagonals, with the frosted
      // corners under the smooth rounding, read as a checker at true size)
      g.fillStyle = rgb(d <= 1 ? mix(pal[0], ICE_SHINE, 0.3) : d === 3 + (v & 1) ? mix(pal[0], ICE_SHINE, 0.2) : d > 9 ? pal[1] : pal[0]);
      g.fillRect(x, y, 1, 1);
    }
  },
};
})();

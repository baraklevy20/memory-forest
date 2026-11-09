/* Memory Forest - the heatmap's Scanlines tiles (the Heatmap tab's Tiles; scanlines.json, Synthwave's
 * own): each day's tile in scanlines, every other row darker as on an old monitor. Not in the page's
 * own scripts: the heatmap loads it when it is drawn in it (heatmap_look.page_look's `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { mix, rgb } = AF.u;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.scanlines = {
  draw(g, pal, edge, v, T) {
    const n = T - 1;  // (the last row and column: the gap between tiles)
    // (the dark rows a shade of the tile's own colour: towards one shared indigo, the shades met in the middle)
    for (let y = 0; y < n; y++) { g.fillStyle = rgb(y % 2 ? mix(pal[0], [0, 0, 0], 0.2) : pal[0]); g.fillRect(0, y, n, 1); }
  },
};
})();

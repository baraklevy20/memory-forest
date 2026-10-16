/* Memory Forest - the heatmap's Flat tiles (the Heatmap tab's Tiles; flat.json): each day a square in
 * one colour, with its edge. The default, drawn with smooth corners (heatmap_look.TILE_STYLE). */
(function () {
'use strict';
const AF = window.AnkiForest, { rgb } = AF.u;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.flat = {
  draw(g, pal, edge, v, T) {
    g.fillStyle = rgb(pal[0]); g.fillRect(0, 0, T - 1, T - 1);
    g.fillStyle = rgb(edge); g.fillRect(T - 1, 0, 1, T); g.fillRect(0, T - 1, T, 1);
  },
};
})();

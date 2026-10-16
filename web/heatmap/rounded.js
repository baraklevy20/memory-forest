/* Memory Forest - the heatmap's Round tiles (the Heatmap tab's Tiles; rounded.json): a joined shape
 * (calendar.js shapesPass) of the days studied and the days ahead, each pixel in its day's shade in
 * the plain tile's two-tone texture. With spaces between the days (as it is drawn) each day is a
 * little round tile, its corners cut two pixels round; with smooth corners too, it is drawn as a
 * tile at the screen's resolution, `smoothRadius` round, its edge antialiased. A missed day stays a
 * hole. */
(function () {
'use strict';
const AF = window.AnkiForest;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.rounded = {
  fields: ['soil', 'grass'],
  smoothRadius: 3.2,
  paint(ctx, c, x, y) {
    const t = c.shade;
    return t.pal[(ctx.hashStr(t.v + ',' + ((x - c.x) >> 1) + ',' + ((y - c.y) >> 1)) & 3) === 0 ? 1 : 0];
  },
};
})();

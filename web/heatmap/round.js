/* Memory Forest - the heatmap's Round tiles (the Heatmap tab's Tiles; round.json): a joined shape
 * (calendar.js shapesPass) of the days studied and the days ahead, each in its day's one colour,
 * as Flat's are. With spaces between the days (as it is drawn) each day is a
 * little round tile, its corners cut two pixels round; with smooth corners too, it is drawn as a
 * tile at the screen's resolution, round.json's `smoothRadius` round and `smoothGrow` bigger, its edge antialiased. A missed day stays a
 * hole. */
(function () {
'use strict';
const AF = window.AnkiForest;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.round = {
  fields: ['soil', 'grass'],
  paint(ctx, c) {
    return c.shade.pal[0];
  },
};
})();

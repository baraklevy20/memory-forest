/* Memory Forest - the heatmap's Brush tiles (the Heatmap tab's Tiles; brush.json, Starry night's own):
 * each day's tile laid on as the painted sky is, rows of short strokes in three tones (the shade, its
 * darker tone and a touch of moonlight), offset row to row, a stroke's end now and then short of the
 * tile's side. Not in the page's own scripts: the heatmap loads it when it is drawn in it
 * (heatmap_look.page_look's `files`). */
(function () {
'use strict';
const AF = window.AnkiForest, { hex, mix, rgb, hashStr } = AF.u;
const MOONLIGHT = hex('#faecaa');
const tileNoise = (x, y, s) => (hashStr(s + ',' + x + ',' + y) % 1000) / 1000;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.brush = {
  draw(g, pal, edge, v, T) {
    // (its own darker tone and more moonlight than the page's shades give: on the paler 2026-10-14
    // shades the strokes otherwise all but vanished)
    const n = T - 1, tones = [pal[0], mix(pal[0], [16, 16, 16], 0.16), mix(pal[0], MOONLIGHT, 0.22), pal[0]];  // (the last row and column: the gap)
    for (let y = 0; y < n; y++) {
      for (let x = (y + v) % 2 ? -1 : -2 - (v & 1), k = 0; x < n; k++) {
        const len = tileNoise(x, y, v) < 0.5 ? 3 : 4, c = tones[(y * 3 + k + v) % 4];
        for (let i = 0; i < len; i++) {
          const px = x + i;
          if (px < 0 || px >= n) continue;
          if ((px === 0 && i === 0 || px === n - 1 && i === len - 1) && tileNoise(px, y, 9 + v) < 0.5) continue;
          g.fillStyle = rgb(c); g.fillRect(px, y, 1, 1);
        }
        x += len;
      }
    }
  },
};
})();

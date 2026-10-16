/* Memory Forest - the heatmap's Contours tiles (the Heatmap tab's Tiles; contours.json; the blob study's
 * "Iso-bands"): a joined shape (calendar.js shapesPass) of the days studied, the days ahead and the
 * empty days, each filled with flat bands of its days' shades, like a contour map: each pixel's shade
 * the days round it weighted by nearness (fieldLv), rounded to the four, a line in the higher band's
 * edge colour where a band rises, the shape outlined. Drawn with no spaces between the days, so the
 * bands run on through them. */
(function () {
'use strict';
const AF = window.AnkiForest;
AF.heatmapTiles = AF.heatmapTiles || {};
AF.heatmapTiles.contours = {
  fields: ['blank', 'soil', 'grass'],
  // (each pixel's band first, to find where a band rises)
  prepare({ out, cells, W, Hh, get, fieldLv }) {
    const band = new Int8Array(W * Hh);
    for (let i = 0; i < W * Hh; i++) if (out[i] >= 0 && !cells[out[i]].shade.blank) band[i] = Math.round(fieldLv(cells[out[i]], i % W, Math.floor(i / W), get));
    return { band, out, W };
  },
  // (a pixel's shade for a hover's highlight: its band, so a shade of the key lights its bands)
  level: (state, i) => state.band[i],
  paint(ctx, c, x, y, edge, i, { band, out, W }) {
    const t = c.shade, { pal, dark, mix, DARK } = ctx;
    if (t.blank) return pal.blank;
    if (edge) return ctx.outlineOf(t, pal, dark);
    const lv = band[i];
    if ([1, -1, W, -W].some(s => out[i + s] >= 0 && band[i + s] > lv)) return t.soil ? mix(pal.tills[Math.min(3, lv + 1)], DARK, 0.2) : pal.edge[Math.min(3, lv + 1)];
    return t.soil ? pal.tills[lv] : pal.grass[lv][0];
  },
};
})();

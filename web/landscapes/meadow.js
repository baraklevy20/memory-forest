/* Open meadow: the plain forest floor, with rolling hills behind it.
 *
 * It is the landscape every other one is a departure from, so it lets the engine draw its
 * defaults, and only softens where the ground's three bands meet. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, B4 } = AF.u;

// the ground's three bands meet over a wider ordered dither (SEAM of a band each side) instead of
// a single checkered stripe, which read as two stripes across the field
const SEAM = 0.16;

AF.landscape('meadow', {
  bed(env, lg) {
    // an environment that paints its own ground (starry strokes, chalk, snow) keeps it as it is
    if (AF.envOf(env).groundPixel) return;
    const th = env.theme, { W, H, hor } = env, h = H - hor, img = lg.getImageData(0, hor, W, h), d = img.data;
    const g0 = hex(th.g0), g1 = hex(th.g1), bands = [g0, mix(g0, g1, 0.5), g1].map(c => c.map(Math.round));
    // (only the pixels still in one of the engine's plain band colours: tufts and anything drawn
    // on the ground stay as they are)
    const bandOf = i => bands.findIndex(c => Math.abs(d[i] - c[0]) <= 1 && Math.abs(d[i + 1] - c[1]) <= 1 && Math.abs(d[i + 2] - c[2]) <= 1);
    for (let y = hor; y < H; y++) {
      const tt = (y - hor) / h * 3, b = Math.min(2, Math.floor(tt));
      for (let x = 0; x < W; x++) {
        const i = ((y - hor) * W + x) * 4; if (bandOf(i) < 0) continue;
        let c = b;
        for (const edge of [1, 2]) {
          const q = (tt - (edge - SEAM)) / (2 * SEAM);
          if (q > 0 && q < 1) c = (B4[(y % 4) * 4 + x % 4] + 0.5) / 16 < q ? edge : edge - 1;
        }
        d[i] = bands[c][0]; d[i + 1] = bands[c][1]; d[i + 2] = bands[c][2];
      }
    }
    lg.putImageData(img, 0, hor);
  },
});
})();

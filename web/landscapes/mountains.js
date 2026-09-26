/* A mountain valley: a taller, sharper horizon than the rolling hills, with snow on
 * anything that rises far enough above the treeline. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mixHex, rgb, TAU } = AF.u;
// snow lies on anything rising more than SNOW_LINE (in env.u) above the horizon, the more
// the higher it goes
const SNOW_LINE = 22, SNOW_DEPTH = 0.6;

AF.landscape('mountains', {
  /* the same seeds as the default hills, folded into peaks instead of swells */
  ridges(env, { p1, p2, p3 }) {
    const { W, u, hor } = env;
    return {
      far: x => { const f = x / W * TAU; return Math.round(hor - (14 * u + 16 * u * Math.abs(Math.sin(f * 1.6 + p1)) * (0.6 + 0.4 * Math.sin(f * 4.3 + p2)) + 3 * u * Math.sin(f * 9 + p3))); },
      near: x => { const f = x / W * TAU; return Math.round(hor - (5 * u + 6 * u * Math.abs(Math.sin(f * 2.4 + p3)) + 1.5 * u * Math.sin(f * 7 + p1))); },
    };
  },
  /* snow, drawn on each far column as it is laid down */
  far(env, lg, x, far) {
    const { u, hor } = env, peak = hor - far;
    if (peak <= SNOW_LINE * u) return;
    lg.fillStyle = rgb(hex(mixHex('#f4f7fb', env.theme.haze, 0.2)));
    lg.fillRect(x, far, 1, Math.round((peak - SNOW_LINE * u) * SNOW_DEPTH + 2));
  },
});
})();

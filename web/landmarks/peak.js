/* A snow-capped peak standing above the treeline, drawn behind everything else. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mixHex, rgb } = AF.u;

AF.landmark('peak', {
  slot: 'back',
  place: (env, R) => env.W * (0.55 + R() * 0.25),
  draw(env, lg, px) {
    const th = env.theme, { W, u, hor } = env, py = hor - 44 * u;
    const cap = hex(mixHex('#f4f7fb', th.haze, 0.15));
    const body = hex(mixHex(th.far, th.sky[th.sky.length - 1], 0.25));
    for (let x = 0; x < W; x++) {
      const yTop = Math.round(py + Math.abs(x - px) * 0.62 + (Math.abs(x - px) < 3 * u ? 1.2 * u : 0));
      if (yTop >= hor) continue;
      for (let y = yTop; y < hor; y++) {
        const c = y < py + 14 * u - Math.sin(x * 0.9) * 1.5 * u ? cap : body;
        lg.fillStyle = rgb(c); lg.fillRect(x, y, 1, 1);
      }
    }
  },
});
})();

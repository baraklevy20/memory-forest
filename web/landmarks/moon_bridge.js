/* A red moon bridge: a steep, near-round arch with a lantern at each end. On a lake or a
 * river it stands at the water's edge in front of the forest, and its reflection closes
 * the arch into a full circle; anywhere else it stands on the far hills. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, layer } = AF.u;

const LACQUER = hex('#d8402e'), LACQUER_D = hex('#8a2420'), RAIL = hex('#2a1a18'), LAMP = hex('#ffd27a');
const onWater = env => env.mood.landscape === 'lake' || env.mood.landscape === 'river';

/* the bridge as a small sprite, and the lamp positions within it */
function build(env) {
  const th = env.theme, u = env.u, R0 = Math.max(10, Math.round(19 * u)), thick = Math.max(2, Math.round(2.5 * u));
  const rail = Math.max(2, Math.round(3 * u)), W = R0 * 2 + 3, H = R0 + rail + 3, cx = W / 2, cy = H;
  const [cv, g] = layer(W, H), img = g.createImageData(W, H), d = img.data;
  const night = th.tint ? hex(th.tint) : null, dim = c => (night ? mix(c, night, th.tintAmt * 0.45) : c);
  const put = (x, y, c) => { if (x < 0 || y < 0 || x >= W || y >= H) return; const i = (y * W + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255; };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const r = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
    if (r <= R0 && r > R0 - thick) put(x, y, dim(r > R0 - 1 ? mix(LACQUER, [255, 255, 255], 0.12) : r < R0 - thick + 1 ? LACQUER_D : LACQUER));
  }
  // posts along the deck and the handrail joining their tops
  for (let a = 0.12; a < Math.PI - 0.1; a += 0.22) {
    const x = Math.round(cx - Math.cos(a) * R0), y0 = Math.round(cy - Math.sin(a) * R0);
    for (let k = 1; k <= rail; k++) put(x, y0 - k, dim(RAIL));
  }
  for (let a = 0.08; a < Math.PI - 0.06; a += 0.02) put(Math.round(cx - Math.cos(a) * (R0 + rail)), Math.round(cy - Math.sin(a) * (R0 + rail)), dim(LACQUER));
  const lit = env.mood.time === 'night' || env.mood.time === 'dusk';
  const lamps = [0.2, Math.PI - 0.2].map(a => ({ x: Math.round(cx - Math.cos(a) * R0), y: Math.round(cy - Math.sin(a) * R0) - rail - 2 }));
  for (const l of lamps) for (let y = 0; y < 3; y++) for (let x = -1; x <= 1; x++) put(l.x + x, l.y + y, y === 0 ? dim(RAIL) : lit ? LAMP : dim(hex('#e8d8b0')));
  g.putImageData(img, 0, 0);
  // the reflection: the same bridge, stained by the water
  const [rv, rg] = layer(W, H), wc = hex(th.water || '#3a4a6a');
  rg.drawImage(cv, 0, 0);
  const ri = rg.getImageData(0, 0, W, H), rd = ri.data;
  for (let i = 0; i < rd.length; i += 4) if (rd[i + 3]) { const c = mix([rd[i], rd[i + 1], rd[i + 2]], wc, 0.35); rd[i] = c[0]; rd[i + 1] = c[1]; rd[i + 2] = c[2]; }
  rg.putImageData(ri, 0, 0);
  return { img: cv, refl: rv, W, H, lamps, lit };
}

function glow(g, x, y, u, t) {
  const a = 0.2 + 0.05 * Math.sin(t * 2 + x), r = Math.max(2, Math.round(2 * u));
  g.fillStyle = `rgba(255,210,122,${a})`; g.fillRect(x - r, y - 1, 2 * r + 1, r + 3);
  g.fillStyle = `rgba(255,210,122,${a * 0.6})`; g.fillRect(x - r - 1, y, 2 * r + 3, r + 1); g.fillRect(x - 1, y - r, 3, 2 * r + 3);
}

AF.landmark('moon_bridge', {
  slot: 'land',
  place: (env, R) => Math.round(env.W * (onWater(env) ? 0.14 + R() * 0.16 : 0.12 + R() * 0.22)),
  draw(env, lg, x) {
    const b = env.moonBridge = Object.assign(build(env), { x });
    if (onWater(env)) return;  // drawn over the water every frame instead, with its reflection
    const y0 = Math.round(env.hor - 8 * env.u);
    AF.drawMound(env, lg, x + (b.W >> 1), Math.round(b.W * 0.7), y0);
    lg.drawImage(b.img, x, y0 - b.H + 1);
    b.fixed = { x, y: y0 - b.H + 1 };
  },
  frame(g, env, t) {
    const b = env.moonBridge; if (!b) return;
    const u = env.u, L = env.water;
    if (b.fixed) {
      if (b.lit) for (const l of b.lamps) glow(g, b.fixed.x + l.x, b.fixed.y + l.y, u, t);
      return;
    }
    if (!L) return;
    // feet on the waterline; the reflection hangs below, row by row, rippling like the rest
    const top = L.y0 - b.H, still = env.theme.frozen;
    for (let j = 0; j < b.H && j < L.lh; j++) {
      const off = still ? 0 : Math.round(Math.sin(t * 0.9 + j * 0.7) * (j < 2 ? 0 : 1));
      g.globalAlpha = 0.75 - 0.4 * j / b.H;
      g.drawImage(b.refl, 0, b.H - 1 - j, b.W, 1, b.x + off, L.y0 + j, b.W, 1);
    }
    g.globalAlpha = 1;
    g.drawImage(b.img, b.x, top);
    if (b.lit) for (const l of b.lamps) {
      glow(g, b.x + l.x, top + l.y, u, t);
      g.fillStyle = 'rgba(255,210,122,.35)'; g.fillRect(b.x + l.x, L.y0 + (b.H - l.y) - 2, 1, 2);  // the lamp in the water
    }
  },
});
})();

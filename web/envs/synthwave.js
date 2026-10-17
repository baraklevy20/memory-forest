/* Memory Forest - the synthwave environment.
 * Everything this environment is lives here: delete it and synthwave.json beside
 * it, and nothing in the add-on mentions it any more.
 *
 * Unlike the others this one repaints the trees themselves (`pals.base`) and puts a neon
 * grid where the water would be, so it also uses the prepare and frame hooks. Two palm
 * silhouettes frame the edges, a neon edge on their trunks only. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hex, mix, mixHex, rgb, pxLine } = AF.u;

const H6 = a => a.map(hex);

/* The hours with a look of their own: a violet-to-peach dawn with a pale gold sun rising, a
 * lavender-haze day with a soft lilac sky, and an amber golden hour with a low gold-to-red
 * sun. Dusk and night keep the scene's original colours. */
const HOURS = {
  dawn: { sky: ['#1a1040', '#3a2a6a', '#6a4a8a', '#c06a9a', '#ff9a9a', '#ffc4a0'], sun: { y: 0.37, r: 21, c: '#fff0b0', c2: '#ff7a8a' },
          far: '#3a2a5a', farLine: '#ffb0d0', near: '#2a1a4a', nearLine: '#ff8ab0', g0: '#1e0f38', g1: '#120826', clouds: ['#ffb8c8', '#c07aa0'] },
  // (day: a deeper top, a warmer horizon under the sun)
  day: { sky: ['#423c8a', '#5c54a2', '#8c78c0', '#b098d4', '#ddc1d9', '#f0d7e0'], sun: { y: 0.22, r: 21, c: '#fff4d0', c2: '#ffc0a0' },
         far: '#5a4a90', farLine: '#f0e0ff', near: '#3e3070', nearLine: '#ff9ad8', g0: '#241a4a', g1: '#160e34', clouds: ['#f4ecff', '#c8b8e8'] },
  golden_hour: { sky: ['#140430', '#3a0a50', '#7a1e5a', '#c0405a', '#f07a50', '#ffb060'], sun: { y: 0.31, r: 21, c: '#ffe070', c2: '#ff5a3a' },
                 far: '#3a0e40', farLine: '#ffb04a', near: '#240830', nearLine: '#ff6a8a', g0: '#1a0428', g1: '#0e0118', clouds: ['#ff9a6a', '#8a2a5a'] },
};

// how far rain, snow and fog pull an hour's own sky towards grey
const WET_GREY = '#2a2238', WET_MIX = 0.45;

/* The neon grid follows the hour too: its floor, the far lines and the near ones. Dusk has
 * the original hot pink; night goes electric cyan. */
const GRIDS = {
  dawn: { floor: '#120826', far: '#8a4a8a', near: '#ffa0c8' },
  day: { floor: '#160e34', far: '#7a5ab0', near: '#ff9ad8' },
  golden_hour: { floor: '#0e0118', far: '#a0304a', near: '#ff8a3a' },
  dusk: { floor: '#0a0118', far: '#8a1f78', near: '#ff3ec8' },
  night: { floor: '#04010f', far: '#1a4a8a', near: '#35e0ff' },
};

const SYNTH = {
  round: H6(['#07011a', '#150833', '#1d0c44', '#2a1158', '#ff4fa3']),
  pine: H6(['#07011a', '#12072e', '#1a0a3e', '#241050', '#35e0ff']),
  sick: [null, H6(['#07011a', '#1d0c44', '#2a1158', '#4a2466', '#ffd166']), H6(['#07011a', '#1d0c44', '#2a1158', '#4a2466', '#ff8a3d']), H6(['#07011a', '#150833', '#1d0c44', '#2a1158', '#9a86b0'])],
  bark: { l: hex('#3a1a5a'), m: hex('#26103e'), d: hex('#170828') }
};

const OPT = {palms: [{ x: 0.025, tx: 0.13, ty: 0.12, trunk: 5, len: 26, droop: 16, leaf: 5, fronds: [-178, -152, -125, -98, -70, -42, -15, 12] },
          { x: 0.99, tx: 0.93, ty: 0.34, trunk: 3.5, len: 17, droop: 10, leaf: 4.5, fronds: [-185, -155, -125, -95, -62, -30, 0] }] };

function palmLayer(env) {
  const { W, H, u } = env, th = env.theme, [cv, pg] = AF.u.layer(W, H);
  const dark = th.g1 || '#0a0118', rim = env.theme.grid.near;
  pg.fillStyle = dark;
  for (const p of OPT.palms) {
    const bx = p.x * W, by = H + 2, tx = p.tx * W, ty = p.ty * H, cx = bx + (tx - bx) * 0.15, cy = (by + ty) / 2;
    const n = Math.ceil(by - ty) * 2;
    for (let i = 0; i <= n; i++) {  // the trunk, a quadratic curve that thins as it climbs
      const s = i / n, x = (1 - s) * (1 - s) * bx + 2 * (1 - s) * s * cx + s * s * tx, y = (1 - s) * (1 - s) * by + 2 * (1 - s) * s * cy + s * s * ty;
      const w = Math.max(1.6, (p.trunk * (1 - s) + 1.6 * s) * u), ring = Math.floor(y) % 4 === 0;
      pg.fillRect(Math.round(x - w / 2) - (ring ? 1 : 0), Math.round(y), Math.round(w) + (ring ? 1 : 0), 1);
    }
    for (const a of p.fronds) {  // fronds: an arching rib, leaflets hanging from both sides of it
      const ang = a * Math.PI / 180, L = p.len * u, dx = Math.cos(ang), dy = Math.sin(ang);
      const steps = Math.ceil(L * 1.5), at = s => [tx + dx * L * s, ty + dy * L * s + p.droop * u * s * s];
      for (let i = 0; i <= steps; i++) {
        const s = i / steps, [x, y] = at(s), [x2, y2] = at(Math.min(1, s + 0.02));
        let ex = x2 - x, ey = y2 - y; const el = Math.hypot(ex, ey) || 1; ex /= el; ey /= el;
        pg.fillRect(Math.round(x), Math.round(y), 1, s < 0.35 ? 2 : 1);
        if (s < 0.08 || i % 2) continue;
        const ll = (Math.sin(Math.PI * Math.min(1, s * 1.15)) * 0.75 + 0.25) * p.leaf * u;
        for (const side of [1, -1]) {
          let lx = -ey * side, ly = ex * side; lx += ex * 0.6; ly += ey * 0.6 + 1.1;  // swept back and drooping
          const ln = Math.hypot(lx, ly); lx /= ln; ly /= ln;
          const len = side * Math.sign(dx || 1) > 0 ? ll : ll * 0.8;
          for (let k = 1; k <= len; k += 0.7) pg.fillRect(Math.round(x + lx * k), Math.round(y + ly * k), 1, 1);
        }
      }
    }
    for (let k = -2; k <= 2; k++) for (let j = -1; j <= 2; j++) if (Math.abs(k) + Math.abs(j) < 3) pg.fillRect(Math.round(tx + k), Math.round(ty + j), 1, 1);
  }
  // the neon edge: a filled pixel whose neighbour towards the sun (and above) is open
  const img = pg.getImageData(0, 0, W, H), d = img.data, solid = (x, y) => x >= 0 && x < W && y >= 0 && y < H && d[(y * W + x) * 4 + 3] > 0;
  // only the trunks are edged: the crowns stay plain black cut-outs against the sky
  const lit = [], mid = W / 2;
  for (const p of OPT.palms) {
    const from = Math.round(p.ty * H + 3 * u), x0 = Math.round(Math.min(p.x, p.tx) * W) - 6, x1 = Math.round(Math.max(p.x, p.tx) * W) + 6;
    for (let y = from; y < H; y++) for (let x = Math.max(0, x0); x < Math.min(W, x1); x++) {
      const dir = x < mid ? 1 : -1;
      if (solid(x, y) && !solid(x + dir, y) && solid(x, y - 1)) lit.push([x, y]);
    }
  }
  pg.fillStyle = rim; for (const [x, y] of lit) pg.fillRect(x, y, 1, 1);
  return cv;
}

const DEF = {
  calendar: ['#2e2a7a', '#ff4fa3'],  // the study calendar from the night's indigo to the neon's hot pink
  // `base` replaces the forest's own palette wholesale: trees, sick leaves and bark
  pals: Object.assign({ base: SYNTH, round: SYNTH.round, pine: SYNTH.pine, bark: SYNTH.bark },
    { leaf: hex('#ff4fa3'), leafL: hex('#ff9fd0'), stem: hex('#c0307a') }),
  flipLight: false,  // the sun sits dead centre, so nothing is lit from one side

  /* neon lights only the outermost edge of a crown, so the highlight is pulled back
   * wherever a pixel has neighbours above and to the left */
  tree: {
    pixel(col, { x, y, tn, pal, c }) {
      return tn === 4 && c.inside(x - 1, y) && c.inside(x, y - 1) ? pal[3] : col;
    }
  },

  /* the whole sky, once the weather has had its say */
  after(th, mood) {
    // the sun is the heart of synthwave, so it never leaves - but it sits lower and colder
    // after dark, and the sky goes from hot magenta to deep indigo
    const late = mood.time === 'night', evening = mood.time === 'golden_hour';  // dusk wears the day look
    const dim = th.rain || th.snow || th.fog;
    // The sun darkens towards its foot while the sky brightens towards the horizon, and
    // the two used to cross: over the bottom quarter of the disc the sky behind it was the
    // brighter of the two, so the sun dissolved there and only the bands cut in it were
    // left - stripes with no sun around them. The horizon keeps its glow, but stays below
    // the sun standing in front of it.
    Object.assign(th, { sky: late ? ['#04010f', '#0c0325', '#1b0640', '#2e0b55', '#4a1260', '#6a1e66']
                              : evening ? ['#08021a', '#17052e', '#330a4e', '#4e1060', '#7a1e6e', '#94286e']
                              : ['#0b0120', '#1c0636', '#3a0b55', '#5e1268', '#8a2470', '#a03070'],
      // the sun is painted by the `sky` hook below, not the engine, so it can climb clear
      // of a large forest and carry its bands up with it
      orb: null,
      synthSun: { y: late ? 0.35 : evening ? 0.33 : 0.29, r: late ? 19 : 21,
             c: dim ? '#c89a5a' : late ? '#9ad8ff' : evening ? '#ffb45c' : '#ffd35c',
             c2: dim ? '#a0406a' : late ? '#6a3ad8' : evening ? '#ff3a6a' : '#ff4f9a' },
      far: '#2a0b4a', farLine: '#35e0ff', near: '#1c0736', nearLine: '#ff4fd8', g0: '#14032c', g1: '#0a0118', grass: '#1d0640', haze: '#3a1060', hzStep: 0.1, tint: null, tintAmt: 0, rim: null, shadow: 0, water: '#3a1a6a' });
    if (th.clouds) th.clouds = { n: th.rain ? 6 : 3, top: late ? '#2e0d4a' : '#5a1a78', bot: late ? '#1a0630' : '#3a0d5a', a: 230 };
    if (late) th.stars = Math.max(th.stars || 0, 70);
    if (th.deck) th.deck = { n: 3, top: '#4a1466', bot: '#2e0a4a', a: 245 };
    if (th.fog) th.fog = '#4a1a6a';
    th.rainbow = false;
    th.grid = GRIDS[mood.time] || GRIDS.dusk;
    // dawn, day and golden hour each get a look of their own; bad weather greys it down
    // rather than trading it for another hour's
    const L = HOURS[mood.time];
    if (L) {
      const grey = c => dim ? mixHex(c, WET_GREY, WET_MIX) : c;
      Object.assign(th, { sky: L.sky.map(grey), far: grey(L.far), farLine: L.farLine, near: grey(L.near), nearLine: L.nearLine, g0: L.g0, g1: L.g1 });
      if (!dim) {
        th.synthSun = Object.assign({}, L.sun);
        if (th.clouds) th.clouds = Object.assign({}, th.clouds, { top: L.clouds[0], bot: L.clouds[1] });
      }
    }
  },

  /* The banded sun. It stands on the horizon as long as the forest leaves room, and
   * climbs as the forest (and the deep forest behind it) grows, so its bands always show
   * above the trees. The bands follow it up: they always start a little above the tree line. */
  sky(env, g) {
    const s = env.theme.synthSun; if (!s) return;
    const { W, H, u } = env, line = AF.treeLine(env);
    const r = Math.round(s.r * u), cx = Math.round(W * 0.5), home = Math.round(H * s.y);
    // keep at least the top 60% of the disc above the trees, and never leave the frame
    const cy = Math.max(r - Math.round(3 * u), Math.min(home, Math.round(line - r * 0.25)));
    const bandFrom = Math.min(cy, Math.round(line - r * 0.7));
    const c1 = hex(s.c), c2 = hex(s.c2), halo = hex(s.c2);
    for (let y = cy - r - 4; y <= cy + r + 4; y++) {
      if (y < 0 || y >= H) continue;
      const deep = (y - bandFrom) / r;
      const cut = deep > 0.05 && (y - bandFrom) % 4 < Math.min(3, 1 + Math.floor(deep * 2.2));
      for (let x = cx - r - 4; x <= cx + r + 4; x++) {
        const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
        if (d < r) { if (!cut) { g.fillStyle = rgb(mix(c1, c2, (y - (cy - r)) / (2 * r))); g.fillRect(x, y, 1, 1); } }
        else if (d < r + 3 * u && (x + y) % 2 === 0 && y < bandFrom) { g.fillStyle = rgb(halo, 0.35); g.fillRect(x, y, 1, 1); }
      }
    }
    env.synthSunAt = { x: cx, y: cy, r };
  },

  prepare(env) {
    env.fxColors = { bird: '#ff4fd8', rain: 'rgba(53,224,255,.45)', rainFar: 'rgba(53,224,255,.25)', splash: 'rgba(255,79,216,.85)' };
    env.visitorTint = '#35e0ff';
    // water and the grid are the same idea here, so a lake keeps its own room and the
    // grid only takes over when there is no water to reflect the sun in
    env.bot = env.mood.landscape === 'lake' ? 0.74 : 0.8;
  },

  /* the grid itself, scrolling towards the horizon. With a lake in front it runs over
   * the far bank only, and the water carries the sun's reflection instead. Then the palms,
   * painted once a scene, over everything. */
  frame(g, env, t) {
    const { W, H } = env, top = Math.round(env.water ? 0 : H * 0.835);
    if (env.water) {  // chrome water: the sun's stripes lying on it, shivering
      const L = env.water, cx = Math.round(W * 0.5);
      for (let i = 0; i < 9; i++) {
        const y = Math.round(L.y0 + 2 + i * 2.2), wob = Math.sin(t * AF.u.cyc(1.3) + i * 0.7) * 2;
        if (y > L.y0 + L.lh) break;
        g.fillStyle = i % 2 ? 'rgba(255,79,154,.5)' : 'rgba(255,211,92,.45)';
        g.fillRect(Math.round(cx - 20 + wob), y, 40, 1);
      }
      g.fillStyle = 'rgba(53,224,255,.35)';
      for (let k = -6; k <= 6; k++) {
        const x0 = W / 2 + k * W / 26, x1 = W / 2 + k * W / 5;
        pxLine(g, x0, L.y0, x1, L.y0 + L.lh);
      }
    } else {
      const grid = env.theme.grid;
      g.fillStyle = grid.floor; g.fillRect(0, top, W, H - top);
      g.fillStyle = grid.far; pxLine(g, 0, top, W, top);
      let last = top;
      for (let k = 0; k < 7; k++) {
        const z = ((k + t * AF.u.drift(0.6, 1)) % 7) / 7, y = Math.round(top + (H - top) * z * z);
        if (y - last < 3) continue;
        g.fillStyle = z < 0.45 ? grid.far : grid.near; pxLine(g, 0, y, W, y); last = y;
      }
      g.fillStyle = grid.near;
      for (let k = -10; k <= 10; k++) pxLine(g, W / 2 + k * W / 40, top, W / 2 + k * W / 9, H);
    }
    if (!env._palms) env._palms = palmLayer(env);
    g.drawImage(env._palms, 0, 0);
  },
};
/* the study calendar's tiles in scanlines, every other row darker as on an old monitor */
const SCANLINE = [18, 10, 40];
DEF.calendarTile = (g, pal, edge, v, T) => {
  const n = T - 1;  // (the last row and column: the gap between tiles)
  for (let y = 0; y < n; y++) { g.fillStyle = rgb(y % 2 ? mix(pal[0], SCANLINE, 0.28) : pal[0]); g.fillRect(0, y, n, 1); }
};

AF.env('synthwave', DEF);
})();

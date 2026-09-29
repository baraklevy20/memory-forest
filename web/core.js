/* Memory Forest — the scene runner: mounts a forest on the page, draws it frame by frame,
 * and swaps in a new one in place. What it draws comes from the other scripts: layout.js,
 * theme.js, visitors.js, ponds.js, tooltips.js, caption.js, the effects and the pixel
 * engine (web/engines/pixel/); hover.js answers the pointer. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { layer, send, animates } = AF.u;
const { HORIZON, GROUND_BOTTOM } = AF.GEOM;

/* ---------- the scene runner ---------- */
AF.mount = function (root, data, opts) {
  // a night-only environment (`night: true`) keeps to the night while the hour is the real one
  if (data.mood.clock && (AF.ENVS[data.mood.special] || {}).night) data = Object.assign({}, data, { mood: Object.assign({}, data.mood, { time: 'night' }) });
  const engine = AF.engines.pixel;
  // the add-on redraws this forest through the panel itself, never through the shared name
  root.afSwap = (d, srcs) => AF.swap(root.id, d, srcs);
  const animate = animates(data);
  // an asteroid's strike plays first, if it hasn't been seen (and the page says when it has)
  if (AF.events.first('mount', root, data, opts, animate, () => send(`${data.channel}:struck:${data.strike.seen}`))) return;
  // a later mount on the same root (a settings change, swapped in place) retires this one
  const token = {};
  root.afToken = token;
  const current = () => root.afToken === token;
  root.innerHTML = (data.inAnki ? '<div class="af-top"><button type="button" class="af-cog" title="Memory Forest settings" aria-label="Memory Forest settings">' + COG + '</button></div>' : '')
    + '<div class="af-scene"><canvas class="af-canvas" aria-label="Your study forest"></canvas><div class="af-tip" hidden></div></div>'
    + '<div class="af-caption"><span class="af-journal"></span><span class="af-meta"></span></div>';
  const cog = root.querySelector('.af-cog');
  if (cog) cog.addEventListener('click', () => send(`${data.channel}:settings`));
  const sceneEl = root.querySelector('.af-scene'), canvas = root.querySelector('canvas'), tip = root.querySelector('.af-tip');
  root.style.maxWidth = data.maxWidth + 'px';
  AF.caption(root, data);
  AF.captionTips(root);

  const layout = AF.layout(data.trees);
  // with animations off the forest is one still moment: every redraw uses this time
  const stillAt = performance.now();
  let env = null, visible = true, running = false;

  function build() {
    const cssW = Math.max(MIN_CSS_W, Math.min(sceneEl.clientWidth || data.maxWidth, data.maxWidth));
    const k = Math.max(MIN_PIXEL_SCALE, Math.floor(cssW / CSS_W_PER_SCALE)), W = Math.floor(cssW / k), H = Math.floor(W / ASPECT);
    canvas.style.width = W * k + 'px'; canvas.style.height = H * k + 'px';
    canvas.width = W; canvas.height = H;
    env = { W, H, u: W / BASE_W, hor: Math.round(H * HORIZON), mood: data.mood, data, layout, engine, bot: GROUND_BOTTOM };
    env.theme = AF.theme(data.mood, data.stats, data.events);
    env.still = !animate;  // one calm moment: nothing brief (a flash, a hop, a blink) is caught in it
    engine.prepare(env);
    env.deep = data.merged ? AF.deepForest(data.merged, env) : null;
    env.placed = layout.items.map(it => Object.assign({ it }, AF.place(it, W, H, env))).sort((a, b) => a.y - b.y);
    env.puddles = AF.findPuddles(env);
    AF.placeVisitors(env);
    env.sky = engine.sky(env);
    const [land, lg] = layer(W, H); env.land = land; env.lg = lg;
    engine.steps(env).forEach(s => s(lg));
    engine.post(env);
    env.fx = AF.fx.init(env);
    env.g = canvas.getContext('2d', env.quantize ? { willReadFrequently: true } : {});
    // anniversary trees, resolved once instead of scanned for on every frame
    env.glowing = (data.anniversaries || []).map(idx => env.placed.find(q => !q.it.pond && q.it.index === idx)).filter(Boolean);
    root.afEnv = env;  // for an animation laid over the forest (the asteroid's strike, web/events/asteroid.js)
  }

  function frame(ts) {
    if (!env) return;
    const g = env.g, t = ts / 1000;
    env.t = t;  // the moment being drawn, for an engine that hit-tests moving things
    g.clearRect(0, 0, env.W, env.H);
    g.drawImage(env.sky, 0, 0);
    if (env.fx) AF.fx.back(g, env, t);
    AF.events.run('back', g, env, t);  // the asteroid on its way
    AF.drawFlyers(g, env, t);
    if (engine.frameBack) engine.frameBack(g, env, t);
    g.drawImage(env.fx && env.fx.flash && env.landLit ? env.landLit : env.land, 0, 0);
    engine.frame(g, env, t);
    AF.events.run('grass', g, env, t);  // tall grass, which the animals stand in
    AF.drawVisitors(g, env, t);
    drawGlow(g, t);
    AF.events.run('front', g, env, t);  // crows, a fresh crater's smoke
    if (env.fx) AF.fx.front(g, env, t);
    if (env.quantize) env.quantize(g, env.W, env.H);
    pointer.drawMarker(g);
  }

  /* an anniversary tree glows: two faint pixel discs of warm light and a few gold
   * sparkles twinkling round its crown */
  const GLOW_DISCS = [0.85, 0.55], GLOW_SPARKLES = 6;  // disc radii as shares of the tree's height
  function drawGlow(g, t) {
    env.glowing.forEach(p => {
      const h = AF.STAGE_H[p.it.stage] * env.u * p.s, cx = Math.round(p.x), cy = Math.round(p.y - h * 0.55);
      g.save(); g.globalCompositeOperation = 'lighter';
      g.fillStyle = `rgba(255,226,150,${0.06 + 0.03 * Math.sin(t * 1.4)})`;
      for (const k of GLOW_DISCS) {
        const r = Math.max(2, Math.round(h * k));
        for (let dy = -r; dy <= r; dy++) { const w = Math.round(Math.sqrt(r * r - dy * dy)); g.fillRect(cx - w, cy + dy, w * 2, 1); }
      }
      g.restore();
      for (let i = 0; i < GLOW_SPARKLES; i++) {
        const a = i / GLOW_SPARKLES * Math.PI * 2 + t * 0.3, on = Math.sin(t * 2.2 + i * 1.7) > 0.2;
        if (!on) continue;
        g.fillStyle = '#ffe6a0';
        g.fillRect(Math.round(cx + Math.cos(a) * h * 0.6), Math.round(cy + Math.sin(a) * h * 0.5), 1, 1);
      }
    });
  }
  // pointing at the forest: tooltips, the marker over a tree, a click to see its cards
  const pointer = AF.hover({ root, canvas, tip, sceneEl, data, animate, env: () => env, redraw: () => { if (!animate) frame(stillAt); } });

  // ~15 frames a second is plenty for drifting clouds and fireflies; pauses when hidden
  function loop() {
    let last = 0;
    const tick = ts => {
      if (!current()) return;  // swapped out: let this forest's loop end
      if (visible && !document.hidden && ts - last > FRAME_MS) { last = ts; frame(ts); }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  function start() {
    build();
    frame(animate ? performance.now() : stillAt);
    if (animate && !running) { running = true; loop(); }
  }
  if ('IntersectionObserver' in window) new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(sceneEl);
  let lastW = 0, rt;
  if ('ResizeObserver' in window) new ResizeObserver((_es, obs) => {
    if (!current()) { obs.disconnect(); return; }
    const w = sceneEl.clientWidth; if (!env || Math.abs(w - lastW) < RESIZE_MIN_PX) return; lastW = w;
    clearTimeout(rt); rt = setTimeout(() => { if (AF.clearCaches) AF.clearCaches(); build(); frame(animate ? performance.now() : stillAt); }, RESIZE_DEBOUNCE_MS);
  }).observe(sceneEl);
  // build after the deck list has painted, so the forest never delays it - unless this is a
  // swap, where the old forest was just cleared and waiting would show an empty panel
  if (opts && opts.now) { lastW = sceneEl.clientWidth; start(); return; }
  const idle = window.requestIdleCallback || (cb => setTimeout(cb, IDLE_FALLBACK_MS));
  requestAnimationFrame(() => idle(() => { lastW = sceneEl.clientWidth; start(); }, { timeout: IDLE_TIMEOUT_MS }));
};

/* Redraw a forest already on the page with new data, without reloading the page: load any
 * scripts the new scene needs that the page does not have yet, then mount over the old
 * one. False when that forest is not on this page, so the add-on reloads it instead. */
AF.swap = function (id, data, srcs) {
  const root = document.getElementById(id);
  if (!root) return false;
  const have = new Set([...document.scripts].map(s => s.src));
  // only a new scene's parts: this copy's own scripts are already running (a changed one,
  // after an update, waits for the next full redraw rather than run beside the old)
  const part = /\/(envs|landscapes|landmarks)\//;
  const missing = srcs.filter(s => part.test(s) && !have.has(new window.URL(s, window.location.href).href));
  const other = window.AnkiForest;
  const next = i => {
    if (i < missing.length) {
      // a new scene's file registers itself on whatever object has the name: this copy's
      window.AnkiForest = AF;
      const el = document.createElement('script');
      el.src = missing[i];
      el.onload = el.onerror = () => next(i + 1);
      document.head.appendChild(el);
      return;
    }
    window.AnkiForest = other;
    if (AF.clearCaches) AF.clearCaches();  // sprites were drawn for the old scene
    AF.mount(root, data, { now: true });
  };
  next(0);
  return true;
};

const FRAME_MS = 66;  // ~15 frames a second
// the canvas is drawn at a few hundred pixels across and scaled up by a whole number:
// one step per CSS_W_PER_SCALE CSS pixels, at least MIN_PIXEL_SCALE; env.u is one
// BASE_W-th of its width, so everything is sized the same at any scale
const MIN_CSS_W = 240, CSS_W_PER_SCALE = 300, MIN_PIXEL_SCALE = 2, BASE_W = 320, ASPECT = 2;
// a resize rebuilds the scene once the width has moved this much and settled this long
const RESIZE_MIN_PX = 8, RESIZE_DEBOUNCE_MS = 200;
// the first build waits for an idle moment, however busy, no longer than IDLE_TIMEOUT_MS
const IDLE_FALLBACK_MS = 30, IDLE_TIMEOUT_MS = 300;
const COG = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6a.5.5 0 0 0 .1-.6l-2-3.5a.5.5 0 0 0-.6-.2l-2.5 1a7.3 7.3 0 0 0-1.7-1l-.4-2.6a.5.5 0 0 0-.5-.4h-4a.5.5 0 0 0-.5.4l-.4 2.6c-.6.3-1.2.6-1.7 1l-2.5-1a.5.5 0 0 0-.6.2l-2 3.5a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6a.5.5 0 0 0-.1.6l2 3.5c.1.2.4.3.6.2l2.5-1c.5.4 1.1.7 1.7 1l.4 2.6c0 .2.3.4.5.4h4c.2 0 .5-.2.5-.4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1c.2.1.5 0 .6-.2l2-3.5a.5.5 0 0 0-.1-.6L19.4 13zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>';
})();

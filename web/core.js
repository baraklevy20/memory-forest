/* Memory Forest — the scene runner: mounts a forest on the page, draws it frame by frame,
 * answers hover and click, and swaps in a new one in place. What it draws comes from
 * the other scripts: layout.js, theme.js, visitors.js, ponds.js, tooltips.js, caption.js,
 * effects.js and the pixel engine (web/engines/pixel/). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { layer, send } = AF.u;
const { HORIZON, GROUND_BOTTOM } = AF.GEOM;

/* ---------- the scene runner ---------- */
AF.mount = function (root, data, opts) {
  // a night-only environment (`night: true`) keeps to the night while the hour is the real one
  if (data.mood.clock && (AF.ENVS[data.mood.special] || {}).night) data = Object.assign({}, data, { mood: Object.assign({}, data.mood, { time: 'night' }) });
  const engine = AF.engines.pixel, words = AF.WORDS;
  // a later mount on the same root (a settings change, swapped in place) retires this one
  const token = {};
  root.afToken = token;
  const current = () => root.afToken === token;
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animate = data.animations && !reduce;
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
  let env = null, hover = null, deepHover = null, visible = true, running = false;

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
  }

  function frame(ts) {
    if (!env) return;
    const g = env.g, t = ts / 1000;
    env.t = t;  // the moment being drawn, for an engine that hit-tests moving things
    g.clearRect(0, 0, env.W, env.H);
    g.drawImage(env.sky, 0, 0);
    if (env.fx) AF.fx.back(g, env, t);
    if (engine.frameBack) engine.frameBack(g, env, t);
    g.drawImage(env.fx && env.fx.flash && env.landLit ? env.landLit : env.land, 0, 0);
    engine.frame(g, env, t);
    AF.drawVisitors(g, env, t);
    drawGlow(g, t);
    if (env.fx) AF.fx.front(g, env, t);
    if (env.quantize) env.quantize(g, env.W, env.H);
    drawMarker(g);
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
  function drawMarker(g) {
    if (!hover) return;
    const x = Math.round(hover.x), y = Math.round(hover.top - 3);
    g.fillStyle = 'rgba(20,20,20,.7)'; g.fillRect(x - 3, y - 1, 7, 1);
    g.fillStyle = '#fff8e0';
    for (let r = 0; r < 3; r++) g.fillRect(x - (2 - r), y + r, 5 - 2 * r, 1);
  }

  function boxOf(p) {
    const h = AF.STAGE_H[p.it.stage] * env.u * p.s, w = Math.max(h * 0.8, 4 * env.u);
    return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - h, y1: p.y + env.u };
  }
  function pick(mx, my) {
    for (const b of env.visitorBoxes || []) if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { visitor: b.v };
    for (let i = env.placed.length - 1; i >= 0; i--) {
      const p = env.placed[i];
      if (p.it.pond) {
        if (!p.it.first) continue;
        const b = AF.pondBox(env, p);
        if (((mx - b.cx) / (b.w / 2)) ** 2 + ((my - b.cy) / (b.h / 2)) ** 2 <= 1) return { p, pond: true };
        continue;
      }
      const b = boxOf(p);
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { p, b };
    }
    return deepPick(mx, my);
  }
  function deepPick(mx, my) {  // the distant canopy, wherever the engine actually drew it
    for (const b of (env.deep && env.deep.boxes) || []) {
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { deep: env.deep.merged, b };
    }
    return null;
  }
  if (data.tooltips) {
    canvas.addEventListener('mousemove', e => {
      if (!env) return;
      const r = canvas.getBoundingClientRect();
      const scale = env.W / (r.width || env.W), mx = (e.clientX - r.left) * scale, my = (e.clientY - r.top) * scale;
      const hit = pick(mx, my);
      deepHover = null;
      if (!hit) { hover = null; tip.hidden = true; canvas.style.cursor = ''; return; }
      if (hit.visitor) { hover = null; tip.innerHTML = AF.tips.visitor(hit.visitor); canvas.style.cursor = ''; }
      else if (hit.deep) {
        hover = null;
        tip.innerHTML = AF.tips.deep(hit.deep, words);
        canvas.style.cursor = data.inAnki && !data.testForest ? 'pointer' : '';
        deepHover = hit.deep;
      }
      else {
        hover = { x: hit.p.x, top: hit.b ? hit.b.y0 : hit.p.y - 4 * env.u, tree: hit.pond ? null : hit.p.it };
        tip.innerHTML = hit.pond ? AF.tips.pond(hit.p.it) : AF.tips.tree(hit.p.it, words);
        canvas.style.cursor = !hit.pond && data.inAnki && !data.testForest ? 'pointer' : '';
      }
      tip.hidden = false;
      const sr = sceneEl.getBoundingClientRect();
      let left = e.clientX - sr.left + TIP_OFFSET, top = e.clientY - sr.top + TIP_OFFSET;
      if (left + tip.offsetWidth > sr.width - TIP_MARGIN) left = e.clientX - sr.left - tip.offsetWidth - TIP_OFFSET;
      if (top + tip.offsetHeight > sr.height - TIP_MARGIN) top = e.clientY - sr.top - tip.offsetHeight - TIP_OFFSET;
      tip.style.left = Math.max(TIP_MARGIN, left) + 'px'; tip.style.top = Math.max(TIP_MARGIN, top) + 'px';
      if (!animate) frame(stillAt);  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { hover = null; deepHover = null; tip.hidden = true; canvas.style.cursor = ''; if (!animate) frame(stillAt); });
    canvas.addEventListener('click', () => {
      if (data.testForest) return;
      if (deepHover) send(`${data.channel}:browse:${deepHover.from_ago}:${AF.deckFor(data)}:${deepHover.to_ago}`);
      else if (hover && hover.tree) send(`${data.channel}:browse:` + hover.tree.ago + ':' + (data.deckId && !hover.tree.dim ? data.deckId : ''));
    });
  }

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
  const missing = srcs.filter(s => !have.has(new window.URL(s, window.location.href).href));
  const next = i => {
    if (i < missing.length) {
      const el = document.createElement('script');
      el.src = missing[i];
      el.onload = el.onerror = () => next(i + 1);
      document.head.appendChild(el);
      return;
    }
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
// the tooltip sits this far from the pointer, and this far inside the scene's edges
const TIP_OFFSET = 14, TIP_MARGIN = 6;
// a resize rebuilds the scene once the width has moved this much and settled this long
const RESIZE_MIN_PX = 8, RESIZE_DEBOUNCE_MS = 200;
// the first build waits for an idle moment, however busy, no longer than IDLE_TIMEOUT_MS
const IDLE_FALLBACK_MS = 30, IDLE_TIMEOUT_MS = 300;
const COG = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6a.5.5 0 0 0 .1-.6l-2-3.5a.5.5 0 0 0-.6-.2l-2.5 1a7.3 7.3 0 0 0-1.7-1l-.4-2.6a.5.5 0 0 0-.5-.4h-4a.5.5 0 0 0-.5.4l-.4 2.6c-.6.3-1.2.6-1.7 1l-2.5-1a.5.5 0 0 0-.6.2l-2 3.5a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6a.5.5 0 0 0-.1.6l2 3.5c.1.2.4.3.6.2l2.5-1c.5.4 1.1.7 1.7 1l.4 2.6c0 .2.3.4.5.4h4c.2 0 .5-.2.5-.4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1c.2.1.5 0 .6-.2l2-3.5a.5.5 0 0 0-.1-.6L19.4 13zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>';
})();

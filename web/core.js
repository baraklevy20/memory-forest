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
  const engine = AF.engines.pixel;
  root.afPointTreeDay = null;
  // the add-on redraws this forest through the panel itself, never through the shared name
  root.afSwap = (d, srcs) => AF.swap(root.id, d, srcs);
  // one listener a forest: the one before goes now (left until the page was next hidden, it
  // kept each retired forest - and its canvas - alive, one more at every swap; a swap to the
  // calendar alone must let go of it too)
  if (root.afShown) { document.removeEventListener('visibilitychange', root.afShown); root.afShown = null; }
  // the forest switched off on this screen, the study calendar on: only the calendar, drawn
  // straight away in the scenery's colours (web/calendar.js)
  if (data.showForest === false) {
    root.afToken = {};  // (a forest mounted here before stops drawing, and leaves nothing behind)
    root.afEnv = root.afVisits = null;
    // its settings cog stays, so the settings are still a click away
    root.innerHTML = cogHtml(data);
    hookCog(root, data);
    root.style.maxWidth = data.maxWidth + 'px';
    AF.calendar(root, data, null);
    return;
  }
  const animate = animates(data);
  AF.LOOP = data.loop || null;  // seconds, for a recording that loops (util.js); never set by the add-on
  // an asteroid's strike plays first, if it hasn't been seen (and the page says when it has)
  if (AF.events.first('mount', root, data, opts, animate, () => send(`${data.channel}:struck:${data.strike.seen}`))) return;
  // a later mount on the same root (a settings change, swapped in place) retires this one
  const token = {};
  root.afToken = token;
  const current = () => root.afToken === token;
  // (the settings cog on the forest's top right corner, the zoom button beside it: no row of its own)
  root.innerHTML = '<div class="af-scene' + (data.inAnki ? ' af-has-cog' : '') + '">' + cogHtml(data)
    + '<canvas class="af-canvas" aria-label="Your study forest"></canvas><div class="af-tip" hidden></div></div>'
    + '<div class="af-visit" aria-live="polite" hidden></div><div class="af-caption"><span class="af-journal"></span><span class="af-meta"></span></div>';
  const sceneEl = root.querySelector('.af-scene'), canvas = root.querySelector('canvas'), tip = root.querySelector('.af-tip');
  root.style.maxWidth = data.maxWidth + 'px';
  AF.caption(root, data);
  AF.captionTips(root);
  // the study calendar's room, kept from the start: drawn once the forest is, it would
  // otherwise push the page down a moment after it appears (the caption first: its journal
  // ends up in the calendar's footer, and a long one wraps there)
  if (data.calendar) {
    const cal = document.createElement('div'); cal.className = 'af-cal'; root.append(cal);
    cal.style.width = AF.calendarWidth(data.calendar);  // (its own width, which sets its scale: measured at the panel's it kept too much)
    cal.style.minHeight = AF.calendarHeight(data.calendar, cal.clientWidth, root) + 'px';
  }
  hookCog(root, data);

  // the whole forest's layout, and the one being drawn: it, or a visit's close-up (web/visit.js)
  const base = AF.layout(data.trees);
  let layout = base;
  // with animations off the forest is one still moment: every redraw uses this time
  const stillAt = performance.now();
  const idle = window.requestIdleCallback || (cb => setTimeout(cb, IDLE_FALLBACK_MS));
  let env = null, visible = true, running = false, asleep = true, refining = 0, calendarDrawn = false;
  // zoomed in, the trees' sprites are kept between redraws (AF.spriteCache)
  const sprites = AF.spriteCache(), zoomOn = () => !!(root.afVisits && root.afVisits.on);

  function build() {
    clearTimeout(refining);
    const cssW = Math.max(MIN_CSS_W, Math.min(sceneEl.clientWidth || data.maxWidth, data.maxWidth));
    const k = Math.max(MIN_PIXEL_SCALE, Math.floor(cssW / CSS_W_PER_SCALE)), W = Math.floor(cssW / k), H = Math.floor(W / ASPECT);
    canvas.style.width = W * k + 'px'; canvas.style.height = H * k + 'px';
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }  // (each frame clears it anyway)
    env = { W, H, u: W / BASE_W, hor: Math.round(H * HORIZON), mood: data.mood, data, layout, engine, bot: GROUND_BOTTOM };
    env.theme = AF.theme(data.mood, data.stats, data.events);
    env.still = !animate;  // one calm moment: nothing brief (a flash, a hop, a blink) is caught in it
    if (zoomOn()) env.sprites = sprites; else sprites.clear();
    engine.prepare(env);
    // (zoomed in among its trees, which stand one by one, its bands fade: web/visit.js)
    env.deepAlpha = layout.deepAlpha == null ? 1 : layout.deepAlpha;
    env.deep = data.merged && env.deepAlpha > 0 ? AF.deepForest(data.merged, env) : null;
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
    // the study calendar under it (web/calendar.js), once a mount: it draws with this scene's trees
    if (data.calendar && !calendarDrawn) {
      calendarDrawn = true;
      try { AF.calendar(root, data, env); } catch (e) { console.error('Memory Forest calendar', e); }
    }
    // some trees stood in at another size (no time to draw them all): drawn again shortly
    if (env.spritesPending) refining = setTimeout(() => { if (current()) { build(); frame(animate ? performance.now() : stillAt); } }, REFINE_MS);
  }
  /* zooming turned on: each tree's sprites drawn ahead, in idle moments, for the first moves to
   * start from (up close, in a visit's shape, then as it stands now, for easing in) */
  function warm() {
    const at = env, list = at ? at.placed.filter(p => !p.it.pond) : [];
    const shapes = [Object.assign({}, at, { layout: Object.assign({}, layout, { visiting: true }) }), at];
    let i = 0;
    const run = () => {
      if (!current() || !zoomOn()) return;
      const t0 = performance.now();
      for (; i < list.length * 2 && performance.now() - t0 < WARM_MS; i++) {
        const p = list[i % list.length], e = shapes[i < list.length ? 0 : 1], { h, hzq } = AF.pixel.sizeOf(p, e);
        sprites.make(p.it, h, hzq, e);
      }
      if (i < list.length * 2) idle(run, { timeout: IDLE_TIMEOUT_MS });
    };
    idle(run, { timeout: IDLE_TIMEOUT_MS });
  }

  function frame(ts) {
    if (!env || !env.g) return;  // (a build that failed part way)
    // in loop mode (AF.LOOP, see util.js) the clock wraps, so the recording repeats exactly
    const g = env.g, t = AF.LOOP ? (ts / 1000) % AF.LOOP : ts / 1000;
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
    if (root.afVisits && root.afVisits.picked != null) AF.drawVisitMarker(g, env, root.afVisits.picked);
    AF.events.run('front', g, env, t);  // crows, a fresh crater's smoke, the fire
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
      g.fillStyle = `rgba(255,226,150,${0.06 + 0.03 * Math.sin(t * AF.u.cyc(1.4))})`;
      // each disc one fill of its rows, which never overlap: a call a row was a hundred a frame
      for (const k of GLOW_DISCS) {
        const r = Math.max(2, Math.round(h * k)), disc = new Path2D();
        for (let dy = -r; dy <= r; dy++) { const w = Math.round(Math.sqrt(r * r - dy * dy)); if (w) disc.rect(cx - w, cy + dy, w * 2, 1); }
        g.fill(disc);
      }
      g.restore();
      for (let i = 0; i < GLOW_SPARKLES; i++) {
        const a = i / GLOW_SPARKLES * Math.PI * 2 + t * AF.u.cyc(0.3), on = Math.sin(t * AF.u.cyc(2.2) + i * 1.7) > 0.2;
        if (!on) continue;
        g.fillStyle = '#ffe6a0';
        g.fillRect(Math.round(cx + Math.cos(a) * h * 0.6), Math.round(cy + Math.sin(a) * h * 0.5), 1, 1);
      }
    });
  }
  // pointing at the forest: tooltips, the marker over a tree, a click to see its cards
  const pointer = AF.hover({ root, canvas, tip, sceneEl, data, animate, env: () => env, redraw: () => { if (!animate) frame(stillAt); } });
  // zooming in among the trees (web/visit.js), once its button turns it on. Where a tree stands
  // across the whole forest, after the landscape's squeeze (a river's banks, say),
  // worked out against the whole forest's layout: the camera walks that ground
  // (each tree's, kept for the scene's width: every move asks again)
  const land = AF.landOf({ mood: data.mood }), xs = new Map();
  let xsAt = null;
  const xOf = it => {
    if (!land.placeX || !env) return it.x;
    if (!xsAt || xsAt.W !== env.W) { xs.clear(); xsAt = Object.assign({}, env, { layout: base }); }
    if (!xs.has(it)) xs.set(it, land.placeX(it, xsAt));
    return xs.get(it);
  };
  // (`opts.zoom`: false, none here; 'always', simply on, as in the phone's full screen; none
  // at all while the add-on holds zooming back, data.zoom false: payload.ZOOM_RELEASED)
  const zoom = data.zoom ? opts && opts.zoom : false;
  root.afVisits = zoom !== false && AF.canVisit({ mood: data.mood }) && base.items.some(it => !it.pond) ? AF.visits({ root, data, base, animate, current, xOf, warm, always: zoom === 'always', go: (cam, behind) => {
    layout = cam ? AF.visitLayout(base, cam, xOf, behind) : base;
    pointer.clear();
    build();
    frame(animate ? performance.now() : stillAt);
  } }) : null;

  // ~15 frames a second is plenty for falling rain and a strike, and a calm scene, where
  // nothing moves more than a pixel in a tenth of a second, takes 10 (AF.busy): every frame
  // costs Chrome the same, however little changed in it. Each is drawn straight from a timer:
  // waiting on a refresh of the screen as well cost Chrome a second, empty frame of its own
  // for every one drawn. Off screen, or on a hidden page, it stops altogether until the
  // forest is seen again (wake)
  function loop() {
    if (!asleep) return;
    asleep = false;
    const tick = () => {
      if (!current() || !visible || document.hidden) { asleep = true; return; }  // swapped out, or unseen
      const ts = performance.now();
      // (one frame that throws must not stop the forest for good)
      try { frame(ts); } finally { setTimeout(tick, Math.max(0, (AF.LOOP || AF.busy(env) ? FRAME_MS : CALM_FRAME_MS) - (performance.now() - ts))); }
    };
    tick();
  }
  const wake = () => { if (running && current()) loop(); };
  function start() {
    build();
    frame(animate ? performance.now() : stillAt);
    if (animate && !running) { running = true; loop(); }
  }
  if ('IntersectionObserver' in window) new IntersectionObserver((es, obs) => {
    if (!current()) { obs.disconnect(); return; }  // a later mount took over: let this scene go
    visible = es[es.length - 1].isIntersecting;  // several queued: the latest is how it stands now
    if (visible) wake();
  }).observe(sceneEl);
  const shown = () => { if (current() && !document.hidden) wake(); };
  root.afShown = shown;
  document.addEventListener('visibilitychange', shown);
  let lastW = 0, rt;
  if ('ResizeObserver' in window) new ResizeObserver((_es, obs) => {
    if (!current()) { obs.disconnect(); return; }
    const w = sceneEl.clientWidth; if (!env || Math.abs(w - lastW) < RESIZE_MIN_PX) return; lastW = w;
    clearTimeout(rt); rt = setTimeout(() => { if (current()) { build(); frame(animate ? performance.now() : stillAt); } }, RESIZE_DEBOUNCE_MS);  // (not after a swap: a retired build would take root.afEnv)
  }).observe(sceneEl);
  // build after the deck list has painted, so the forest never delays it - unless this is a
  // swap, where the old forest was just cleared and waiting would show an empty panel
  if (opts && opts.now) { lastW = sceneEl.clientWidth; start(); return; }
  requestAnimationFrame(() => idle(() => { lastW = sceneEl.clientWidth; start(); }, { timeout: IDLE_TIMEOUT_MS }));
};

/* Whether a scene has anything fast in it - rain, falling petals, a strike - that wants the
 * full ~15 frames a second; a calm one is drawn at 10. Each part says so for itself with a
 * `busy`: an effect (a function of its state), an environment, landscape or landmark (true,
 * or a function of the scene), an event (a hook). Asked before every frame: some are only
 * fast for a while (a tumbleweed blowing away). */
AF.busy = env => {
  const says = spec => typeof spec.busy === 'function' ? spec.busy(env) : spec.busy;
  // (a scene a failed build left half made can't say: calm, so the loop it is asked from goes on)
  try {
    return Boolean(AF.fx.busy(env) || says(AF.envOf(env)) || says(AF.landOf(env)) || says(AF.markOf(env)) || AF.events.first('busy', env));
  } catch {
    return false;
  }
};

/* Load scripts onto this copy of the add-on - a scene's environment, landscape and landmark -
 * one at a time and each once, however many ask: a scene's file registers itself on whatever
 * object window.AnkiForest is while it runs, so that is this copy until they are all in, and
 * whatever it was before after. A promise, rejected if one could not be loaded. */
const loads = new Map();  // src -> its promise
let queue = Promise.resolve(), waiting = 0, outside;
AF.loadScripts = srcs => Promise.all(srcs.map(src => {
  if (!loads.has(src)) {
    if (waiting++ === 0) outside = window.AnkiForest;
    const p = queue.catch(() => {}).then(() => new Promise((ok, fail) => {
      const el = document.createElement('script');
      el.src = src;
      el.charset = 'utf-8';
      // once run, let go: kept, each loaded file held on to the forest that asked for it
      el.onload = () => { el.onload = el.onerror = null; ok(); };
      el.onerror = () => { el.onload = el.onerror = null; loads.delete(src); fail(new Error(`could not load ${src}`)); };
      window.AnkiForest = AF;
      document.head.appendChild(el);
    })).finally(() => { if (--waiting === 0) window.AnkiForest = outside; });
    loads.set(src, p);
    queue = p;
  }
  return loads.get(src);
}));

/* Redraw a forest already on the page with new data, without reloading the page: load any
 * scripts the new scene needs that the page does not have yet, then mount over the old
 * one - the latest swap asked for, if several overlap. False when that forest is not on this
 * page, so the add-on reloads it instead. */
AF.swap = function (id, data, srcs) {
  const root = document.getElementById(id);
  if (!root) return false;
  const have = new Set([...document.scripts].map(s => s.src));
  // only a new scene's parts: this copy's own scripts are already running (a changed one,
  // after an update, waits for the next full redraw rather than run beside the old)
  const part = /\/(envs|landscapes|landmarks)\//;
  // each as the page resolves a script's src (a link does it the same way); not new URL()
  // against location.href, which before Anki 2.1.50 is no URL at all
  const absolute = s => { const a = document.createElement('a'); a.href = s; return a.href; };
  const missing = srcs.filter(s => part.test(s) && !have.has(absolute(s)));
  const mine = root.afSwaps = (root.afSwaps || 0) + 1;
  // a part that won't load: the forest is drawn without it, as before
  AF.loadScripts(missing).catch(() => {}).then(() => { if (root.afSwaps === mine) AF.mount(root, data, { now: true }); });
  return true;
};

const FRAME_MS = 66;  // ~15 frames a second
const CALM_FRAME_MS = 100;  // 10 a second, in a scene with nothing fast in it
// the canvas is drawn at a few hundred pixels across and scaled up by a whole number:
// one step per CSS_W_PER_SCALE CSS pixels, at least MIN_PIXEL_SCALE; env.u is one
// BASE_W-th of its width, so everything is sized the same at any scale
const MIN_CSS_W = 240, CSS_W_PER_SCALE = 300, MIN_PIXEL_SCALE = 2, BASE_W = 320, ASPECT = 2;
// a resize rebuilds the scene once the width has moved this much and settled this long
const RESIZE_MIN_PX = 8, RESIZE_DEBOUNCE_MS = 200;
// the first build waits for an idle moment, however busy, no longer than IDLE_TIMEOUT_MS
const IDLE_FALLBACK_MS = 30, IDLE_TIMEOUT_MS = 300;
// zoomed in: trees that stood in at another size are drawn again REFINE_MS after; sprites are
// drawn ahead WARM_MS at a time
const REFINE_MS = 40, WARM_MS = 8;
// the settings cog (in Anki only), and what clicking it does; with what's new: its dot, and a
// note on the forest (web/news.js)
const cogHtml = data => data.inAnki
  ? '<div class="af-top"><button type="button" class="af-cog" title="Change scenery and settings" aria-label="Change scenery and settings">' + COG + '</button></div>' : '';
function hookCog(root, data) {
  const cog = root.querySelector('.af-cog');
  if (cog) cog.addEventListener('click', () => send(`${data.channel}:settings`));
  AF.news(root, data);
}
const COG = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6a.5.5 0 0 0 .1-.6l-2-3.5a.5.5 0 0 0-.6-.2l-2.5 1a7.3 7.3 0 0 0-1.7-1l-.4-2.6a.5.5 0 0 0-.5-.4h-4a.5.5 0 0 0-.5.4l-.4 2.6c-.6.3-1.2.6-1.7 1l-2.5-1a.5.5 0 0 0-.6.2l-2 3.5a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6a.5.5 0 0 0-.1.6l2 3.5c.1.2.4.3.6.2l2.5-1c.5.4 1.1.7 1.7 1l.4 2.6c0 .2.3.4.5.4h4c.2 0 .5-.2.5-.4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1c.2.1.5 0 .6-.2l2-3.5a.5.5 0 0 0-.1-.6L19.4 13zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>';
})();

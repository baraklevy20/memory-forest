/* Memory Forest — the scene runner: mounts a forest on the page, draws it frame by frame,
 * and swaps in a new one in place. What it draws comes from the other scripts: layout.js,
 * theme.js, visitors.js, ponds.js, tooltips.js, caption.js, the effects and the pixel
 * engine (web/engines/pixel/); hover.js answers the pointer. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { layer, send, animates, esc, oklab, fromOklab, cssColor, contrast, onTheme, pageBg, appBg } = AF.u;
const { HORIZON, GROUND_BOTTOM } = AF.GEOM;

/* ---------- the scene runner ---------- */
AF.mount = function (root, data, opts) {
  AF.i18n.use(data.i18n);  // (its words, dates and numbers in Anki's language)
  AF.i18n.dirOn(root);  // (and their direction: the panel right to left for a language that reads so, forest.css .af-rtl)
  const engine = AF.engines.pixel;
  root.afPointTreeDay = null;
  root.afLightTreeDays = null;
  root.afCalView = null;  // (the heatmap's view in view: AF.calendar sets it once drawn)
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
    root.classList.remove('af-cal-first');
    hookCog(root, data);
    AF.panelWidth(root, data);
    AF.arrange(root, data);
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
  // (the forest and its caption in a box of their own, which the deck list's layout can place apart
  // from the heatmap: AF.arrange)
  root.innerHTML = '<div class="af-forest"><div class="af-scene' + (data.inAnki ? ' af-has-cog' : '') + '">' + cogHtml(data)
    + `<canvas class="af-canvas" aria-label="${esc(AF.t('panel.your_study_forest'))}"></canvas>`
    + '<div class="af-tip" hidden></div></div>'
    // (the sky's colours, for the cards' over the forest, Layout's Background: AF.skyFill; after the
    // scene, so the forest's canvas stays the panel's first)
    + '<canvas class="af-sky-fill" aria-hidden="true"></canvas>'
    + '<div class="af-visit" aria-live="polite" hidden></div><div class="af-caption"><span class="af-journal"></span><span class="af-meta"></span></div></div>';
  const sceneEl = root.querySelector('.af-scene'), canvas = root.querySelector('canvas'), tip = root.querySelector('.af-tip');
  AF.panelWidth(root, data);
  AF.caption(root, data);
  AF.captionTips(root);
  // the study calendar's room, kept from the start: drawn once the forest is, it would
  // otherwise push the page down a moment after it appears (the caption first: its journal
  // ends up in the calendar's footer, and a long one wraps there)
  // (the heatmap first, Layout's Heatmap first: then the forest and its caption under it, the
  // journal staying the panel's last line, in the caption)
  const calFirst = !!(data.calendar && data.layout && data.layout.first === 'heatmap');
  root.classList.toggle('af-cal-first', calFirst);
  if (data.calendar) {
    const cal = document.createElement('div'); cal.className = 'af-cal';
    if (calFirst) root.prepend(cal); else root.append(cal);
    AF.arrange(root, data);  // (placed before its room is measured: a side column is narrower)
    AF.calendarFit(cal, data.calendar, null, data.maxWidth, data.inAnki);  // (its own width, which sets its scale: measured at the panel's it kept too much)
    cal.style.minHeight = AF.calendarHeight(data.calendar, cal.clientWidth, root) + 'px';
  } else AF.arrange(root, data);
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
    // (Layout's Background: the scene covers the window and Anki's bars, AF.cover; elsewhere the
    // Forest width, or the room it has)
    const cover = root.afBehind ? AF.cover(data) : null;
    const cssW = cover ? cover.w : Math.max(MIN_CSS_W, Math.min(sceneEl.clientWidth || data.maxWidth, data.maxWidth));
    const k = Math.max(MIN_PIXEL_SCALE, Math.floor(cssW / CSS_W_PER_SCALE));
    const W = cover ? Math.ceil(cssW / k) : Math.floor(cssW / k), H = Math.floor(W / ASPECT);
    canvas.style.width = W * k + 'px'; canvas.style.height = H * k + 'px';
    if (cover) {
      // (its sides past the window's, for the buttons kept at the window's corner)
      AF.coverVars(root, W * k, H * k);
      root.afCover = cover.w;
    }
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
    if (root.afBehind) AF.skyFill(root, env.sky);
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
    // (Layout's Background: Anki's bars take the sky's and the scene's foot's colours, once it is drawn)
    if (root.afBehind) {
      root.afBarsAgain = () => { if (current() && root.afBehind) AF.barEdges(data, root, canvas); };  // (and on a theme change: AF.cardTones)
      requestAnimationFrame(root.afBarsAgain);
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
    if (root.afBehind) return;  // (its size is the window's: below)
    const w = sceneEl.clientWidth; if (!env || Math.abs(w - lastW) < RESIZE_MIN_PX) return; lastW = w;
    clearTimeout(rt); rt = setTimeout(() => { if (current()) { build(); frame(animate ? performance.now() : stillAt); } }, RESIZE_DEBOUNCE_MS);  // (not after a swap: a retired build would take root.afEnv)
  }).observe(sceneEl);
  // (Layout's Background: built again as the window's size changes the scene that covers it)
  const onWindow = () => {
    if (!current()) { window.removeEventListener('resize', onWindow); return; }
    if (!root.afBehind || !env) return;
    AF.coverVars(root, canvas.offsetWidth, canvas.offsetHeight);  // (a taller window, the same scene: the cog moves with its top)
    if (Math.abs(AF.cover(data).w - (root.afCover || 0)) < RESIZE_MIN_PX) return;
    clearTimeout(rt); rt = setTimeout(() => { if (current()) { build(); frame(animate ? performance.now() : stillAt); } }, RESIZE_DEBOUNCE_MS);
  };
  window.addEventListener('resize', onWindow);
  // build after the deck list has painted, so the forest never delays it - unless this is a
  // swap, where the old forest was just cleared and waiting would show an empty panel
  if (opts && opts.now) { lastW = sceneEl.clientWidth; start(); return; }
  requestAnimationFrame(() => idle(() => { lastW = sceneEl.clientWidth; start(); }, { timeout: IDLE_TIMEOUT_MS }));
};

/* the panel's widest: the Forest width, and in Anki the panel's own padding round it (forest.css
 * .af-panel, 12px a side), so the forest is the Forest width under the list as it is beside it */
const PANEL_PAD = 24;
/* (and wider when the heatmap asks to be, stacked under the list or on a deck's screen: Full width,
 * or Fixed wider than the Forest width; the forest then keeps its width in the middle, forest.css
 * .af-heat-wider) */
/* (the panel's width under the list, its padding left out, in a row `room` css px across) */
const panelWant = (data, room) => {
  const want = data.calendar ? AF.calendarWant(data.calendar) : 0;
  return data.calendar && AF.calendarFull(data.calendar) ? room : Math.max(data.maxWidth, typeof want === 'number' ? want : 0);
};
AF.panelWidth = (root, data) => {
  const pad = data.inAnki ? PANEL_PAD : 0;
  const want = data.inAnki && data.calendar ? AF.calendarWant(data.calendar) : 0;
  const full = data.inAnki && data.calendar && AF.calendarFull(data.calendar);
  const wider = full || (typeof want === 'number' && want > data.maxWidth);
  root.style.maxWidth = full ? 'none' : Math.max(data.maxWidth, wider ? want : 0) + pad + 'px';
  root.classList.toggle('af-heat-wider', wider && data.showForest !== false);
  root.style.setProperty('--af-forest-w', data.maxWidth + 'px');
};

/* Where the forest and the heatmap sit round Anki's deck list (data.layout: each one's place,
 * "below" | "above" | "left" | "right"; payload.py, state.layout).
 * Anki's deck list is <center><table>decks</table><br>stats</center>, the panel first among the
 * stats (panel.py); it is left as Anki made it: our stylesheet makes its <center> a wrapping row
 * (forest.css, body.af-lay) and orders each of our parts round the deck table. Two parts in one
 * place stand as one box, the panel; apart, the panel steps aside (display: contents) and each is a
 * box of its own. Their widths: the forest's the Forest width (data.maxWidth); the heatmap's its
 * Width (85% of the forest by default, 85% of the room its place has, or 680 px: calendar.js
 * AF.calendarWant) in the room it has: stacked, the panel; apart, the row under or over the list (the
 * list and its side column, or the window's whole room) or its column beside the list. Narrower than
 * that room, it stands in its middle. A side column takes the
 * room the window has up to its width, and under its least (SIDE_MIN, SIDE_SHARE, HEAT_MIN) falls
 * under the list (af-lay-narrow), checked again on each resize of the window. Anywhere else (a deck's screen, the
 * finished-deck page, Onigiri's tile, the phone) the panel stays as it is. */
// css px between the list and a side column; the least a column with the forest, and a heatmap of its own, may shrink to (about half a year of it); the room kept at the window's edges (the panel's own padding)
// (a forest beside the list keeps at least SIDE_SHARE of its Forest width: at 360 px of 800 it read as a
// thumbnail beside the list, smaller than it stands under it)
const SIDE_GAP = 32, SIDE_MIN = 360, SIDE_SHARE = 0.6, HEAT_MIN = 480, EDGE = 12;
/* Background: the cards over the forest take the colour of its sky (AF.cardTones): its average, read
 * from SKY_FILL_COLS columns of the sky's top SKY_FILL_ROWS rows (.af-sky-fill, never shown: the
 * scene covers the window, AF.cover) */
/* Each column goes SKY_FLATTEN of the way to their average, so one bright spot in the sky's top rows
 * (Starry night's swirl) isn't a lit pillar up the window; the average, and so the cards' colour,
 * stays the same. */
const SKY_FILL_COLS = 12, SKY_FILL_ROWS = 3, SKY_FLATTEN = 0.5;
const CARD_REACH = 36;  // css px the heatmap's card reaches past it each side (forest.css .af-slot-below.af-cal::before)
/* The cards' blur only where Chromium draws it right: Anki 2.1.45's (Chromium 77, Qt 5) drew each
 * blurred card's content upside down (e2e/old_anki_check.py, 2026-10-31). Every Qt 5 Anki is before
 * BLUR_FROM; there the cards are their tint alone, which is nearly solid anyway (forest.css af-no-blur) */
const BLUR_FROM = 90;
const chromium = () => { const m = /Chrome\/(\d+)/.exec(window.navigator.userAgent); return m ? +m[1] : 0; };
AF.skyFill = (root, sky) => {
  const fill = root.querySelector('.af-sky-fill');
  if (!fill || !sky || !sky.width) return;
  if (fill.width !== SKY_FILL_COLS) { fill.width = SKY_FILL_COLS; fill.height = 1; }
  const g = fill.getContext('2d');
  g.imageSmoothingEnabled = true;
  g.clearRect(0, 0, SKY_FILL_COLS, 1);
  g.drawImage(sky, 0, 0, sky.width, Math.min(SKY_FILL_ROWS, sky.height), 0, 0, SKY_FILL_COLS, 1);
  const img = g.getImageData(0, 0, SKY_FILL_COLS, 1), px = img.data, avg = [0, 0, 0];
  for (let i = 0; i < px.length; i += 4) for (let c = 0; c < 3; c++) avg[c] += px[i + c] / SKY_FILL_COLS;
  for (let i = 0; i < px.length; i += 4) for (let c = 0; c < 3; c++) px[i + c] = Math.round(px[i + c] + (avg[c] - px[i + c]) * SKY_FLATTEN);
  g.putImageData(img, 0, 0);
  root.afSky = avg;
  AF.cardTones(root);
  // (again when Anki's theme or a themer's colours change: the cards and their words follow)
  if (!root.afToneWatch) root.afToneWatch = onTheme(() => { if (root.isConnected && root.afBehind) AF.cardTones(root); });
};
/* The cards' colour and the words on them (forest.css, Background), all from the theme's own colours
 * as the page has them (Anki's variables, or a themer's: Onigiri, AnKing's, ReColor), never fixed
 * ones, and done again when they change (onTheme). The card: the theme's page colour (--canvas)
 * at its lightness, its hue plus the sky's (CARD.sky of the sky's OKLab colour), so every scenery and
 * hour gives the contrasts the theme was made for; CARD.alpha opaque, and set so that over the sky
 * that shows through it the card comes out at that colour (mixed toward fixed near black and near
 * white, a dawn sky made a mid-grey dark card and its counts fell to 2.7:1; a themer's page colour
 * was lost, 2026-10-31). Where nothing blurs behind it (af-no-blur) nearly solid, NO_BLUR_ALPHA: the
 * scene's stars and branches showed through sharp. On it: the secondary words (the heatmap's labels,
 * the zoom's, a deck's description) the theme's text colour faded toward the card to TEXT_2 (Anki's
 * --fg-subtle is a grey for its flat page: 2.8:1 on a dawn card), a count's 0 to ZERO, Anki's New,
 * Learn and Due colours moved in lightness alone to COUNTS where they fall short (light Anki's green
 * Due was 2.4:1 on a night sky's card), the current row's veil and the header's rule the text colour
 * faint. */
const CARD = { dark: { sky: 0.35, alpha: 0.9 }, light: { sky: 0.15, alpha: 0.95 } }, NO_BLUR_ALPHA = 0.97;
const TEXT_2 = 5, ZERO = 2.3, COUNTS = 4.5, VEIL = { dark: 0.1, light: 0.07 }, RULE = 0.16;
const COUNT_KINDS = ['new', 'learn', 'review'];
const rgba = (c, a) => 'rgba(' + c.slice(0, 3).map(v => Math.round(v)).join(',') + ',' + a + ')';
const toward = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
// the theme's colour for `name` (Anki 2.1.50+'s variable, or an older Anki's), or what the page shows
const themed = (names, fallback) => {
  const css = window.getComputedStyle(document.body);
  for (const n of names) { const c = cssColor(css.getPropertyValue(n)); if (c) return c; }
  return fallback();
};
// `from` faded toward `to` as far as it goes while still standing at `ratio` on `to`
const fadedTo = (from, to, ratio) => {
  let lo = 0, hi = 1;
  for (let i = 0; i < 16; i++) { const m = (lo + hi) / 2; if (contrast(toward(from, to, m), to) >= ratio) lo = m; else hi = m; }
  return toward(from, to, lo);
};
// (a class set only when it changes: setting it again is a mutation onTheme would hear)
const setClass = (el, name, on) => { if (el.classList.contains(name) !== on) el.classList.toggle(name, on); };
const probes = {};
const countProbe = kind => {
  if (!probes[kind] || !probes[kind].isConnected) {
    const s = probes[kind] = document.createElement('span');
    s.className = kind + '-count'; s.setAttribute('aria-hidden', 'true');
    s.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;left:-99px;top:0';
    document.body.appendChild(s);
  }
  return probes[kind];
};
const setVar = (el, name, value) => { if (el.style.getPropertyValue(name) !== value) el.style.setProperty(name, value); };  // (unchanged: no new mutation for onTheme)
AF.cardTones = root => {
  const sky = root.afSky, body = document.body;
  if (!sky || !body) return;
  const page = themed(['--canvas', '--window-bg'], () => pageBg([body]) || appBg());
  const fg = themed(['--fg', '--text-fg'], () => cssColor(window.getComputedStyle(body).color) || [0, 0, 0]);
  const p = oklab(page.slice(0, 3)), s = oklab(sky), side = p[0] < 0.6 ? 'dark' : 'light';
  const alpha = body.classList.contains('af-no-blur') ? NO_BLUR_ALPHA : CARD[side].alpha;
  const want = fromOklab(p[0], p[1] + s[1] * CARD[side].sky, p[2] + s[2] * CARD[side].sky);
  const tint = want.map((v, i) => Math.max(0, Math.min(255, (v - (1 - alpha) * sky[i]) / alpha)));
  const card = toward(sky, tint, alpha);  // (as it comes out over the sky)
  setVar(body, '--af-card', rgba(tint, alpha));
  root.afCardTint = { tint, alpha };  // (the bottom bar wears it as it comes out at the window's foot: AF.barEdges)
  if (root.afBarsAgain) root.afBarsAgain();
  setVar(body, '--af-card-clear', rgba(tint, 0));
  setVar(body, '--af-text', rgba(fg, 1));
  setVar(body, '--af-text-2', rgba(fadedTo(fg, card, TEXT_2), 1));
  setVar(body, '--af-text-0', rgba(fadedTo(fg, card, ZERO), 1));
  setVar(body, '--af-veil', rgba(fg, VEIL[side]));
  setVar(body, '--af-rule', rgba(fg, RULE));
  setClass(body, 'af-card-light', side === 'light');
  // (Anki's counts: each read as Anki draws it, on a stand-in of ours outside the cards, then moved
  // in lightness alone until it reads on the card)
  COUNT_KINDS.forEach(kind => {
    const c = cssColor(window.getComputedStyle(countProbe(kind)).color);
    if (!c) { body.style.removeProperty(`--af-${kind}`); return; }
    const k = oklab(c.slice(0, 3)), step = side === 'light' ? -0.01 : 0.01;
    let moved = c;
    for (let i = 1; i <= 60 && contrast(moved, card) < COUNTS; i++) moved = fromOklab(k[0] + step * i, k[1], k[2]);
    setVar(body, `--af-${kind}`, rgba(moved, 1));
  });
  setClass(body, 'af-counts', true);
};
/* Background a tree's tooltip stands on a layer of its own, fixed over the scene and above our
 * row (forest.css .af-tip-layer): inside the forest, behind the page, the cards and pills covered it.
 * hover.js places it in the scene's own coordinates as ever: the layer has the scene's box. */
AF.tipLayer = root => {
  const scene = root.querySelector('.af-scene'), tip = scene && scene.querySelector(':scope > .af-tip');
  let layer = root.afTipLayer;
  if (root.afTipPlace) { window.removeEventListener('resize', root.afTipPlace); root.afTipPlace = null; }
  if (!root.afBehind || !scene) {
    if (layer) { layer.remove(); root.afTipLayer = null; }
    return;
  }
  if (!layer) { layer = root.afTipLayer = document.createElement('div'); layer.className = 'af-tip-layer'; document.body.appendChild(layer); }
  layer.textContent = '';  // (an earlier mount's tip)
  AF.i18n.dirOn(layer);
  if (tip) layer.appendChild(tip);
  const place = () => { const r = scene.getBoundingClientRect(); layer.style.top = r.top + 'px'; layer.style.height = r.height + 'px'; };
  root.afTipPlace = place;
  window.addEventListener('resize', place);
  scene.addEventListener('mouseenter', place);  // (drawn after the layout: its height is known by then)
  place();
};
/* Background: the forest's caption, at the window's foot, steps aside (fades, forest.css
 * af-caption-under) while any of the page's cards or lines lies over it: in a window just tall enough
 * the last pill sat on the caption at first sight, two lines of words on each other; back once the
 * page has scrolled past it. Asked again as the page scrolls and the window resizes. */
AF.captionClear = root => {
  if (root.afCaptionCheck) {
    window.removeEventListener('scroll', root.afCaptionCheck); window.removeEventListener('resize', root.afCaptionCheck); root.afCaptionCheck = null;
  }
  const caption = root.querySelector('.af-caption'), center = root.parentElement;
  if (caption) caption.classList.remove('af-caption-under');
  if (!root.afBehind || !caption) return;
  const check = () => {
    const c = caption.getBoundingClientRect();
    if (!c.height) return;
    const parts = Array.prototype.filter.call(center ? center.children : [], el => el !== root).concat(Array.from(root.querySelectorAll('.af-slot-below')));
    const over = parts.some(el => { const r = el.getBoundingClientRect(); return r.height && r.bottom > c.top - CAPTION_AIR && r.top < c.bottom && r.right > c.left && r.left < c.right; });
    if (caption.classList.contains('af-caption-under') !== over) caption.classList.toggle('af-caption-under', over);
  };
  root.afCaptionCheck = check;
  window.addEventListener('scroll', check, { passive: true });
  window.addEventListener('resize', check);
  requestAnimationFrame(check);
};
const CAPTION_AIR = 6;  // css px kept clear over the caption
/* Layout's Background: the scene covers the window as a wallpaper does: as wide as the window, or
 * wider and cut at both sides where the window is taller than half its width, its foot on the
 * window's. So no stretched sky over it (2026-10-31: it looked smeared). The window only: laid out
 * under Anki's bars as well it grew too large, and what walked there (a fox) was hidden. COVER_SLACK:
 * a few px more, as the canvas is a whole number of its pixels. */
const COVER_SLACK = 8;
AF.cover = () => ({ w: Math.max(window.innerWidth, ASPECT * window.innerHeight + COVER_SLACK) });
/* (how far the scene reaches past the window's sides, and over its top, for the cog and the zoom
 * button kept at the window's top corner: forest.css) */
AF.coverVars = (root, w, h) => {
  const box = root.querySelector('.af-forest');
  if (!box) return;
  box.style.setProperty('--af-side', Math.max(0, (w - window.innerWidth) / 2) + 'px');
  box.style.setProperty('--af-over', Math.max(0, h - window.innerHeight) + 'px');
};
/* Anki's toolbar over the page and its bottom bar under it, pages of their own, wear the scene's edge
 * beside them, blurred and still (bars.py): the window's top BAR_ROWS rows of the scene, and its
 * foot's, each squeezed to BAR_COLS columns and drawn smoothly across the bar, as a soft band of its
 * colours, never its pictures (slices of the scene itself looked broken at the seam, 2026-10-31). Sent
 * as the scene is drawn, when they change; the clear when the layout is no longer Background
 * (AF.arrange). */
const BAR_ROWS = 4, BAR_COLS = 16;
const hex = rgb => '#' + rgb.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
const rowsAverage = (c, y, rows) => {
  const px = c.getContext('2d').getImageData(0, y, c.width, rows).data, avg = [0, 0, 0], n = px.length / 4;
  for (let i = 0; i < px.length; i += 4) for (let k = 0; k < 3; k++) avg[k] += px[i + k] / n;
  return avg;
};
AF.barEdges = (data, root, canvas) => {
  if (!canvas || !canvas.width || !canvas.height) return;
  try {
    const r = canvas.getBoundingClientRect(), kx = canvas.width / r.width, ky = canvas.height / r.height;
    // (the window's columns of the scene, its rows y0 (css px from the window's top) down BAR_ROWS
    // of its pixels, squeezed to BAR_COLS columns smoothly: a soft band of their colours, as a PNG)
    const edge = y0 => {
      const sx = Math.max(0, -r.left * kx), sw = Math.min(canvas.width - sx, window.innerWidth * kx);
      const sy = Math.min(canvas.height - BAR_ROWS, Math.max(0, (y0 - r.top) * ky));
      const c = document.createElement('canvas'), g = c.getContext('2d');
      c.width = BAR_COLS; c.height = 1;
      g.imageSmoothingEnabled = true;
      g.drawImage(canvas, sx, sy, sw, BAR_ROWS, 0, 0, BAR_COLS, 1);
      return c.toDataURL('image/png');
    };
    // (the bottom bar the cards' colour, solid, as the caption's band darkens into it at the window's
    // foot: one dim from the forest down into the bar, 2026-10-31; the scene's own colours there
    // stood out as a lighter strip)
    const ground = rowsAverage(canvas, canvas.height - BAR_ROWS, BAR_ROWS), c = root.afCardTint;
    const foot = c ? ground.map((v, i) => v + (c.tint[i] - v) * c.alpha) : ground;
    const msg = `${data.channel}:bars:` + JSON.stringify({ top: edge(0), bottom: '', topColour: hex(rowsAverage(canvas, 0, 1)), bottomColour: hex(foot) });
    if (msg !== AF.barsSent) { AF.barsSent = msg; send(msg); }
  } catch { /* (a canvas that can't be read: Anki's bars stay as they are) */ }
};
/* (a line of another add-on's plain text in Anki's row, behind the list: on a card of its own,
 * forest.css .af-pill; anything with pictures, tables or controls in it is left as it draws itself) */
const PILL_SKIP = /^(TABLE|BR|SCRIPT|STYLE|LINK|H3)$/, PILL_MAX_CHARS = 200;
const pillRow = el => !PILL_SKIP.test(el.tagName) && el.id !== 'studiedToday' && !el.classList.contains('af-panel') && !el.classList.contains('description')
  && !el.querySelector('img, canvas, svg, table, iframe, video, button, input, select')
  && el.textContent.trim().length > 0 && el.textContent.length < PILL_MAX_CHARS;
const SLOTS = /\s*af-(slot-\w+|apart)\b/g;
AF.arrange = function (root, data) {
  const L = data.layout, center = root.parentElement;
  const parts = [root, root.querySelector('.af-forest'), root.querySelector('.af-cal')];
  parts.forEach(el => { if (el) { el.className = el.className.replace(SLOTS, ''); el.style.removeProperty('--af-row'); } });
  if (root.afFit) { window.removeEventListener('resize', root.afFit); root.afFit = null; }
  if (root.afStick) { window.removeEventListener('scroll', root.afStick); root.afStick = null; document.body.classList.remove('af-lay-sticky'); }
  const forest = data.showForest !== false, cal = !!data.calendar;
  const places = L ? [forest && L.forest, cal && L.heatmap].filter(Boolean) : [];
  const sides = places.filter(p => p === 'left' || p === 'right');
  const table = center && center.tagName === 'CENTER' && center.querySelector(':scope > table');
  // (where Anki's <center> holds a table: the deck list, and a deck's screen, its counts and Study
  // now; or on a finished deck's page, the panel in a box of its own under its message: AF.arrange
  // leaves Anki's page as it is there, forest.css af-behind-page. Anywhere else, Onigiri's tile, the
  // forest stays in the panel)
  const finished = !table && !!root.closest('.af-finished');
  root.afBehind = !!((table || finished) && forest && L && L.forest === 'behind');
  document.body.classList.toggle('af-lay-behind', root.afBehind);
  document.body.classList.toggle('af-behind-page', root.afBehind && finished);
  document.body.classList.toggle('af-no-blur', root.afBehind && chromium() < BLUR_FROM);
  if (center) {
    // (and what Anki puts before the table, a deck screen's name and description, stays over it)
    let before = !!table;
    Array.prototype.forEach.call(center.children, el => {
      if (el === table) before = false;
      el.classList.toggle('af-pill', root.afBehind && pillRow(el));
      el.classList.toggle('af-lay-before', root.afBehind && before);
    });
    // (a deck screen's name, the title of its counts' card, as wide as that card: forest.css)
    const title = table && center.querySelector(':scope > h3');
    if (title) title.style.width = root.afBehind ? table.offsetWidth + 'px' : '';
    if (table) table.classList.toggle('af-titled', !!(root.afBehind && title));
  }
  AF.tipLayer(root);
  AF.captionClear(root);
  if (!root.afBehind) document.body.classList.remove('af-behind-zooming');
  if (!root.afBehind && AF.barsSent) { AF.barsSent = null; send(`${data.channel}:bars`); }
  if (!sides.length && !places.includes('above') && !root.afBehind || !(table || root.afBehind)) {
    if (root.afArranged) { document.body.classList.remove('af-lay', 'af-lay-narrow'); root.afArranged = false; }
    return;
  }
  root.afArranged = true;
  document.body.classList.add('af-lay');
  const put = (el, place) => el.classList.add('af-slot-' + place);
  // (behind the list the forest always stands apart, the heatmap shown or not: the panel steps aside)
  const apart = forest && (cal && L.forest !== L.heatmap || root.afBehind);
  if (apart) { root.classList.add('af-apart'); put(parts[1], L.forest); if (cal) put(parts[2], L.heatmap); } else put(root, places[0]);
  const cols = new Set(sides).size;
  const heatSide = apart && (L.heatmap === 'left' || L.heatmap === 'right');
  const size = (el, w) => el.style.setProperty('--af-row', Math.floor(w) + 'px');
  const fit = () => {
    // (a side column's width and its least: the heatmap's alone the width it asks for, or all the
    // room there is (calendar.js AF.calendarMost); the panel's, or the forest's, the Forest width)
    const most = heatSide ? AF.calendarMost(data.calendar, data.maxWidth) : data.maxWidth;
    const least = Math.min(most, heatSide || !forest ? HEAT_MIN : Math.max(SIDE_MIN, SIDE_SHARE * data.maxWidth));
    const room = center.clientWidth - 2 * EDGE;
    // (Full width beside the list alone: 85% of the room there, AF.calendarColumnShare)
    const share = heatSide ? AF.calendarColumnShare(data.calendar) : 1;
    const col = cols ? Math.min(most, Math.floor(share * ((room - table.offsetWidth) / cols - SIDE_GAP))) : 0;
    const narrow = cols ? col < least : false;
    document.body.classList.toggle('af-lay-narrow', narrow);
    center.style.setProperty('--af-col', Math.max(col, 0) + 'px');
    // (the row under or over the list: the list and its side column, or all the window's room)
    const row = narrow || !cols ? room : table.offsetWidth + cols * (SIDE_GAP + col);
    const forestW = Math.min(row, data.maxWidth);
    // (the panel in a row, over the list or fallen under it: as wide as it is under the list, wider
    // than the forest for a heatmap that asks to be, AF.panelWidth; in a column, the column's width)
    if (!apart) size(root, cols && !narrow ? forestW : Math.min(row, panelWant(data, row)));
    else {
      size(parts[1], forestW);
      // (the heatmap: its column beside the list, or in the row it stands in the width it asks for,
      // never more than the row (calendar.js AF.calendarWidthIn), in the row's middle as everything
      // on the page is (forest.css .af-slot-below, .af-slot-above))
      const lone = heatSide && !narrow;
      // (behind the list, less its card's reach each side, so the card keeps the window's gutter)
      if (cal) size(parts[2], lone ? col : AF.calendarWidthIn(data.calendar, data.maxWidth, Math.min(row, room) - (root.afBehind ? 2 * CARD_REACH : 0)));
    }
  };
  // a side column that fits the window stays in view while a longer deck list scrolls by (forest.css
  // af-lay-sticky): asked again as the page scrolls, by then with the forest drawn at its height
  const column = (apart ? [parts[1], parts[2]] : [root]).filter(el => el && /af-slot-(left|right)/.test(el.className));
  const stick = () => {
    const tall = column.reduce((h, el) => Math.max(h, el.offsetHeight), 0);
    document.body.classList.toggle('af-lay-sticky', !!column.length && !document.body.classList.contains('af-lay-narrow')
      && tall + 2 * EDGE <= window.innerHeight && table.offsetHeight > tall);
  };
  root.afStick = stick;
  window.addEventListener('scroll', stick, { passive: true });
  fit();
  stick();
  // (again as the window is resized: the list's room is the window's. Not a ResizeObserver on the
  // row, whose size the switch itself changes: Chromium 77 stopped on "ResizeObserver loop limit
  // exceeded" as the window crossed the breakpoint)
  root.afFit = () => { fit(); stick(); };
  window.addEventListener('resize', root.afFit);
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
  ? `<div class="af-top"><button type="button" class="af-cog" title="${esc(AF.t('panel.change_scenery_and_settings'))}" aria-label="${esc(AF.t('panel.change_scenery_and_settings'))}">${COG}</button></div>` : '';
function hookCog(root, data) {
  const cog = root.querySelector('.af-cog');
  if (cog) cog.addEventListener('click', () => send(`${data.channel}:settings`));
  AF.news(root, data);
}
const COG = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6a.5.5 0 0 0 .1-.6l-2-3.5a.5.5 0 0 0-.6-.2l-2.5 1a7.3 7.3 0 0 0-1.7-1l-.4-2.6a.5.5 0 0 0-.5-.4h-4a.5.5 0 0 0-.5.4l-.4 2.6c-.6.3-1.2.6-1.7 1l-2.5-1a.5.5 0 0 0-.6.2l-2 3.5a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6a.5.5 0 0 0-.1.6l2 3.5c.1.2.4.3.6.2l2.5-1c.5.4 1.1.7 1.7 1l.4 2.6c0 .2.3.4.5.4h4c.2 0 .5-.2.5-.4l.4-2.6c.6-.3 1.2-.6 1.7-1l2.5 1c.2.1.5 0 .6-.2l2-3.5a.5.5 0 0 0-.1-.6L19.4 13zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/></svg>';
})();

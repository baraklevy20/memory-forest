/* Memory Forest — pointing at the forest: what is under the pointer (an animal, a tree, a
 * pond, the deep forest, the asteroid or a crater), its tooltip, the marker over the tree
 * pointed at, and a click that opens that tree's cards in Anki's browser (or replays a strike). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { send } = AF.u;
// the tooltip sits this far from the pointer, and this far inside the scene's edges
const TIP_OFFSET = 14, TIP_MARGIN = 6;
// Something that can be watched again (a strike) says so: with a mouse, a click does it; on
// a touch screen, where a tap is a hover and a click at once, the first tap only opens the
// tooltip, and a second tap on the same thing does it.
AF.watchHint = touched => `<br><span class="af-hint">${touched ? AF.t('hover.tap_again_to_watch_it_again') : AF.t('hover.click_to_watch_it_again')}</span>`;

/* Wire up one mounted forest. `env()` is the scene as currently built (it is rebuilt on a
 * resize), and `redraw()` draws a still forest's moment again. Returns what the runner
 * draws of it each frame. */
AF.hover = function ({ root, canvas, tip, sceneEl, data, animate, env: current, redraw }) {
  let hover = null, deepHover = null, eventHover = null, touched = false, armed = null, shown = null;  // armed: what one more tap replays; shown: the tip as written
  let linkedAgo = null, liftedMine = null;
  const plantedDays = new Set((data.calendar && data.calendar.planted || []).map(t => t[0]));
  root.afPointTreeDay = ago => {
    if (linkedAgo === ago) return;
    linkedAgo = ago; liftedMine = null; redraw();
  };
  // the days selected on the heatmap, as `ago`s (null: none): their trees stand out, the rest of the
  // forest dimmed under them
  let litDays = null, litKey = '', litTrees = null;
  root.afLightTreeDays = agos => {
    const key = agos ? [...agos].sort((a, b) => a - b).join(',') : '';
    if (key === litKey) return;
    litKey = key; litDays = agos ? new Set(agos) : null; litTrees = null; redraw();
  };
  // the rest of the forest this far into black: by the scene's own lightness, lightly by day (0.55
  // turned a golden hour into dusk), more by night (where the lit trees, night-coloured, barely
  // stood out of it): its land's mean lightness `L` from LIT_DIM_AT[0] up to LIT_DIM_AT[1]
  const LIT_DIM = [0.45, 0.75], LIT_DIM_AT = [0.4, 0.15];
  const litDimOf = env => {
    const [, cg] = AF.u.layer(64, 32);
    let d;
    try { cg.drawImage(env.land, 0, 0, 64, 32); d = cg.getImageData(0, 0, 64, 32).data; } catch { return 0.55; }
    let s = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 200) { s += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]; n++; }
    const t = Math.max(0, Math.min(1, ((n ? s / n / 255 : 0.5) - LIT_DIM_AT[0]) / (LIT_DIM_AT[1] - LIT_DIM_AT[0])));
    return LIT_DIM[0] + (LIT_DIM[1] - LIT_DIM[0]) * t;
  };
  function drawLit(g, env) {
    if (!litDays || !env) return;
    // (each tree's own copy, kept until the scene or the stretch changes: sprite() borrows a scratch
    // canvas), back to front as the forest stands: a nearer tree over a lit one drawn again over
    // it, dimmed with the rest, so a lit tree stays behind what stands before it
    if (!litTrees || litTrees.env !== env) {
      const trees = [], boxes = [], dim = litDimOf(env);
      for (const p of env.placed) {
        if (p.it.pond) continue;
        const lit = litDays.has(p.it.ago);
        if (!lit && !boxes.length) continue;
        const { h, hzq } = AF.pixel.sizeOf(p, env), spr = AF.pixel.sprite(p.it, h, hzq, env);
        const x = Math.round(p.x - spr.width / 2), y = Math.round(p.y - spr.height + 1), hb = p.pose && p.hitBox, box = hb ? [hb.x0, hb.y0, hb.x1, hb.y1] : [x, y, x + spr.width, y + spr.height];
        if (!lit && !boxes.some(b => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
        const [cv, cg] = AF.u.layer(spr.width, spr.height);
        cg.drawImage(spr, 0, 0);
        if (!lit) { cg.globalCompositeOperation = 'source-atop'; cg.fillStyle = `rgba(0,0,0,${dim})`; cg.fillRect(0, 0, cv.width, cv.height); }
        trees.push({ cv, x, y, p });
        if (lit) boxes.push(box);
      }
      litTrees = { env, trees, dim };
    }
    g.save();
    g.fillStyle = `rgba(0,0,0,${litTrees.dim})`;
    g.fillRect(0, 0, env.W, env.H);
    for (const { cv, x, y, p } of litTrees.trees) {
      if (p.pose) posed(g, p, cv);  // (a tree the scenery drew turned: `pose`, its foot and turn)
      else if (env.flipLight) { g.save(); g.translate(x + cv.width, y); g.scale(-1, 1); g.drawImage(cv, 0, 0); g.restore(); }
      else g.drawImage(cv, x, y);
    }
    g.restore();
  }
  // the tree marked: its day pointed at on the heatmap, else the tree pointed at here (one a scenery
  // draws elsewhere than it stands, turned say, keeps only the arrow over the box it left)
  function marked(env) {
    if (!env) return null;
    if (linkedAgo !== null) {
      const p = env.placed.find(p => !p.it.pond && p.it.ago === linkedAgo);
      if (p || deepLinked(env)) return p || null;
    }
    return hover && hover.p && (!hover.p.hitBox || hover.p.pose) && env.placed.includes(hover.p) ? hover.p : null;  // (a tree drawn elsewhere is outlined only where its `pose` says it is)
  }
  // the heatmap points at a day merged into the distant canopy
  function deepLinked(env) {
    const deep = env.deep, merged = data.merged;
    return linkedAgo !== null && merged && plantedDays.has(linkedAgo) && linkedAgo >= merged.to_ago && linkedAgo <= merged.from_ago
      && deep && deep.boxes.length && !(root.afVisits && root.afVisits.on);
  }
  /* Before the crows, robins and flames (core.js): the marked tree drawn again over what stands
   * before it, with a light outline round it and the birds on it, which then perch on it as ever.
   * With days selected on the heatmap it all goes on top at the end instead (drawMarker), over the
   * dimmed forest. */
  let liftedTop = null, pickedTop = null;
  // zoomed in, the tree selected (web/visit.js) keeps its outline, the pointer elsewhere or not
  const pickCache = { lifted: null };
  function pickedOf(env) {
    const zoom = root.afVisits, i = zoom && zoom.on ? zoom.picked : null;
    return i == null || !env ? null : env.placed.find(q => !q.it.pond && q.it.index === i) || null;
  }
  function drawLifted(g, t) {
    const env = current(), p = !litDays && marked(env), q = !litDays && pickedOf(env);
    pickedTop = q && q !== p ? lift(g, env, q, t, pickCache) : null;
    liftedTop = p ? lift(g, env, p, t) : null;
    if (q && q === p) pickedTop = liftedTop;  // (pointed at as well: one outline, its arrow over it)
  }
  /* the outline's top over the tree selected, for its arrow (null: not outlined now) */
  const pickedRing = () => pickedTop;
  function drawMarker(g) {
    const env = current();
    drawLit(g, env);
    const p = marked(env);
    // (zoomed in, the tree selected has its own arrow already, a size up: web/visit.js drawVisitMarker)
    if (p && !litDays && p === pickedOf(env)) return;
    if (p) { marker(g, p.pose && p.hitBox ? (p.hitBox.x0 + p.hitBox.x1) / 2 : p.x, litDays ? lift(g, env, p, env.t) : liftedTop !== null ? liftedTop : p.y); return; }
    if (env && deepLinked(env)) {
      const deep = env.deep;
      g.save(); g.fillStyle = '#fff8e0'; g.globalAlpha = 0.6;
      for (const [x, y] of deep.rims || []) g.fillRect(x, y - 1, 1, 1);
      g.restore();
      const box = deep.boxes.reduce((a, b) => Math.abs((a.x0 + a.x1) / 2 - env.W / 2) < Math.abs((b.x0 + b.x1) / 2 - env.W / 2) ? a : b);
      const x = Math.round((box.x0 + box.x1) / 2);
      marker(g, x, deep.rims && deep.rims.has(x) ? deep.rims.get(x) : box.y0);
      return;
    }
    if (!hover) return;
    marker(g, hover.x, hover.top);
  }
  // the birds a tree's outline goes round, as events draw them on it
  const BIRDS = ['crows', 'robins'], BIRD_ROOM = 8;  // (the room they take above and beside the crown)
  /* the tree and its outline drawn; returns the outline's top, for the arrow */
  function lift(g, env, p, t, cache) {
    let lifted = cache ? cache.lifted : liftedMine;
    // sprite() borrows a scratch canvas: keep a copy of the tree until the scene or the tree changes
    if (!lifted || lifted.env !== env || lifted.p !== p) {
      const { h, hzq } = AF.pixel.sizeOf(p, env), spr = AF.pixel.sprite(p.it, h, hzq, env);
      const [tree, tg] = AF.u.layer(spr.width, spr.height);
      if (env.flipLight && !p.pose) { tg.translate(spr.width, 0); tg.scale(-1, 1); }
      tg.drawImage(spr, 0, 0);
      lifted = { env, p, tree, x: Math.round(p.x - spr.width / 2), y: Math.round(p.y - spr.height + 1), ring: null };
      if (cache) cache.lifted = lifted; else liftedMine = lifted;
    }
    const L = lifted, birds = p.it.leeches || p.it.cured, R = BIRD_ROOM + 1;
    // the outline: round the tree and (drawn on a copy of the scene holding this tree alone) its
    // birds, which flap and hop: theirs is made again each frame
    if (!L.ring || birds) {
      const W = L.tree.width + 2 * R, H = L.tree.height + R + 1, ox = L.x - R, oy = L.y - R;
      const [m, mg] = AF.u.layer(W, H);
      mg.drawImage(L.tree, R, R);
      if (birds) {
        mg.save(); mg.translate(-ox, -oy);
        AF.events.runOnly(BIRDS, 'front', mg, Object.create(env, { placed: { value: [p] } }), t || 0);
        mg.restore();
      }
      const [ring, rg] = AF.u.layer(W, H);
      for (const [x, y] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) rg.drawImage(m, x, y);
      rg.globalCompositeOperation = 'source-in'; rg.fillStyle = '#fff8e0'; rg.fillRect(0, 0, W, H);
      rg.globalCompositeOperation = 'destination-out'; rg.drawImage(m, 0, 0);
      let top = H;
      const d = rg.getImageData(0, 0, W, H).data;
      for (let i = 3; i < d.length; i += 4) if (d[i]) { top = Math.floor(i / 4 / W); break; }
      L.ring = { cv: ring, ox, oy, top: oy + top };
    }
    g.save();
    if (p.pose) {  // a tree the scenery drew turned: its foot at pose.x, pose.y, turned by pose.ang, mirrored with pose.flip
      const q = p.pose;
      g.translate(q.x, q.y); g.rotate(q.ang); if (q.flip) g.scale(-1, 1);
      g.translate(-Math.floor(L.tree.width / 2) - L.x, -L.tree.height + 1 - L.y);
    }
    g.drawImage(L.tree, L.x, L.y);
    g.drawImage(L.ring.cv, L.ring.ox, L.ring.oy);
    g.restore();
    return p.pose && p.hitBox ? p.hitBox.y0 - 1 : L.ring.top;
  }
  // a copy of a tree's sprite (cv, drawn upright at x, y) where the scenery drew it turned:
  // its foot at pose.x, pose.y, turned by pose.ang, mirrored with pose.flip
  function posed(g, p, cv) {
    const q = p.pose;
    g.save(); g.imageSmoothingEnabled = false; g.translate(q.x, q.y); g.rotate(q.ang); if (q.flip) g.scale(-1, 1);
    g.drawImage(cv, -Math.floor(cv.width / 2), -cv.height + 1); g.restore();
  }
  function marker(g, cx, top) {
    const x = Math.round(cx), y = Math.round(top - 3);
    g.fillStyle = 'rgba(20,20,20,.7)'; g.fillRect(x - 3, y - 1, 7, 1);
    g.fillStyle = '#fff8e0';
    for (let r = 0; r < 3; r++) g.fillRect(x - (2 - r), y + r, 5 - 2 * r, 1);
  }

  function boxOf(env, p) {
    if (p.hitBox) return p.hitBox;  // a scenery that draws a tree elsewhere than its place (turned, say) leaves the box it drew it in
    const h = AF.STAGE_H[p.it.stage] * env.u * p.s, w = Math.max(h * 0.8, 4 * env.u);
    return { x0: p.x - w / 2, x1: p.x + w / 2, y0: p.y - h, y1: p.y + env.u };
  }
  function pick(env, mx, my) {
    const inBox = b => b && mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1;
    for (const b of env.visitorBoxes || []) if (inBox(b)) return { visitor: b.v };
    const event = AF.events.first('pick', env, data, mx, my, animate);  // the asteroid, a crater
    if (event) return { event };
    for (let i = env.placed.length - 1; i >= 0; i--) {
      const p = env.placed[i];
      if (p.it.pond) {
        if (!p.it.first) continue;
        const b = AF.pondBox(env, p);
        if (((mx - b.cx) / (b.w / 2)) ** 2 + ((my - b.cy) / (b.h / 2)) ** 2 <= 1) return { p, pond: true };
        continue;
      }
      const b = boxOf(env, p);
      if (p.hitBox || !AF.pixel.sprite) { if (b.hit ? b.hit(mx, my) : inBox(b)) return { p, b }; continue; }  // (a turned tree's own pixels: its `hit`)
      if (drawnAt(env, p, mx, my, 0)) return { p, b };
    }
    // nothing drawn right there: a tree drawn within a pixel or two (a sapling is thin)
    for (let i = env.placed.length - 1; i >= 0; i--) {
      const p = env.placed[i];
      if (!p.it.pond && !p.hitBox && AF.pixel.sprite && drawnAt(env, p, mx, my, NEAR)) return { p, b: boxOf(env, p) };
    }
    return deepPick(env, mx, my);
  }
  /* Is tree p drawn at (mx, my), or within `near` pixels of it? What its sprite covers, not a box
   * round it: a box had the pointer on one tree pick another in front of it, one point in seven
   * across a full forest, and bare ground pick a tree half the time. */
  const NEAR = 2, masks = new WeakMap();  // placed tree -> its sprite's drawn pixels
  function drawnAt(env, p, mx, my, near) {
    const { h, hzq } = AF.pixel.sizeOf(p, env);
    // (far from it, its sprite isn't read: no scenery's tree is as wide as one and a half times its
    // height, and a seedling's is 9 pixels whatever its height)
    const r = Math.max(h, 9);
    if (Math.abs(mx - p.x) > 1.5 * r + 6 + near || my > p.y + 2 + near || my < p.y - r - 4 - near) return false;
    let m = masks.get(p);
    if (!m || m.env !== env || m.th !== h) {
      const spr = AF.pixel.sprite(p.it, h, hzq, env), w = spr.width, sh = spr.height;
      const d = spr.getContext('2d').getImageData(0, 0, w, sh).data, a = new Uint8Array(w * sh);
      for (let i = 0; i < a.length; i++) a[i] = d[i * 4 + 3] > 0 ? 1 : 0;
      masks.set(p, m = { env, th: h, w, h: sh, x0: Math.round(p.x - w / 2), y0: Math.round(p.y - sh + 1), a });
    }
    const X = Math.floor(mx) - m.x0, Y = Math.floor(my) - m.y0;
    for (let dy = -near; dy <= near; dy++) for (let dx = -near; dx <= near; dx++) {
      if (dx * dx + dy * dy > near * near) continue;
      let cx = X + dx;
      const cy = Y + dy;
      if (cx < 0 || cy < 0 || cx >= m.w || cy >= m.h) continue;
      if (env.flipLight) cx = m.w - 1 - cx;  // drawn mirrored
      if (m.a[cy * m.w + cx]) return true;
    }
    return false;
  }
  function deepPick(env, mx, my) {  // the distant canopy, wherever the engine actually drew it
    for (const b of (env.deep && env.deep.boxes) || []) {
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { deep: env.deep.merged, b };
    }
    return null;
  }
  // what is at the pointer, on the canvas in its own layout: a forest turned on the page (the
  // phone card's sideways view) is pointed at the same as an upright one
  function hitAt(env, e) {
    const scale = env.W / (canvas.clientWidth || env.W), [x, y] = AF.u.pointIn(e, canvas);
    return pick(env, x * scale, y * scale);
  }
  // where the mouse last was over the forest, to point again from there once the scene is drawn afresh
  // under it (zooming in: the wheel moves no mouse, and the tree under it lost its outline and tooltip)
  let lastAt = null, again = 0;
  if (data.tooltips) {
    canvas.addEventListener('pointerdown', e => { touched = e.pointerType !== 'mouse'; });
    canvas.addEventListener('mousemove', e => {
      lastAt = e.isTrusted || !e.afAgain ? { clientX: e.clientX, clientY: e.clientY } : lastAt;
      const env = current();
      if (!env) return;
      const hit = hitAt(env, e);
      deepHover = null; eventHover = null;
      if (!hit || !hit.event || hit.event.html !== armed) armed = null;  // a tap on something else starts over
      if (!hit) { const changed = !!hover; hover = null; shown = null; tip.hidden = true; canvas.style.cursor = ''; if (changed) redraw(); return; }
      let html;
      if (hit.visitor) { hover = null; html = AF.tips.visitor(hit.visitor); canvas.style.cursor = ''; }
      else if (hit.event) {
        hover = null; eventHover = hit.event;
        html = hit.event.html + (hit.event.replay ? AF.watchHint(touched) : '');
        canvas.style.cursor = hit.event.replay ? 'pointer' : '';
      }
      else if (hit.deep) {
        hover = null;
        html = AF.tips.deep(hit.deep);
        canvas.style.cursor = data.inAnki && !data.testForest ? 'pointer' : '';
        deepHover = hit.deep;
      }
      else {
        hover = { x: hit.b ? (hit.b.x0 + hit.b.x1) / 2 : hit.p.x, top: hit.b ? hit.b.y0 : hit.p.y - 4 * env.u, tree: hit.pond ? null : hit.p.it, p: hit.pond ? null : hit.p };
        // zoomed in, a click picks a tree first (web/visit.js)
        const zoom = root.afVisits, picks = !hit.pond && zoom && zoom.on && zoom.picked !== hit.p.it.index;
        // (selecting is the bar's to say, under the forest: false, no hint; the tree selected says its click opens its cards)
        html = hit.pond ? AF.tips.pond(hit.p.it) : AF.tips.tree(hit.p.it, picks ? false : '', env.data);
        canvas.style.cursor = !hit.pond && (picks || (data.inAnki && !data.testForest)) ? 'pointer' : '';
      }
      // the same thing pointed at as before: the tip only follows the pointer (rewriting it, and
      // redrawing a still forest, on every move of the mouse was most of the cost of pointing)
      const changed = html !== shown || tip.hidden;
      if (changed) { tip.innerHTML = shown = html; }
      tip.hidden = false;
      // the pointer within the scene, which holds the canvas and the tip
      const at = AF.u.pointIn(e, canvas), x = canvas.offsetLeft + at[0], y = canvas.offsetTop + at[1];
      // (inside what shows of the scene: Layout's Background cuts it at the window's sides and top)
      const box = sceneEl.getBoundingClientRect(), minX = Math.max(0, -box.left) + TIP_MARGIN, minY = Math.max(0, -box.top) + TIP_MARGIN;
      const maxX = Math.min(sceneEl.clientWidth, window.innerWidth - box.left) - TIP_MARGIN;
      let left = x + TIP_OFFSET, top = y + TIP_OFFSET;
      if (left + tip.offsetWidth > maxX) left = x - tip.offsetWidth - TIP_OFFSET;
      if (top + tip.offsetHeight > sceneEl.clientHeight - TIP_MARGIN) top = y - tip.offsetHeight - TIP_OFFSET;
      tip.style.left = Math.max(minX, left) + 'px'; tip.style.top = Math.max(minY, top) + 'px';
      if (changed) redraw();  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { lastAt = null; hover = null; deepHover = null; shown = null; tip.hidden = true; canvas.style.cursor = ''; redraw(); });
    canvas.addEventListener('click', e => {
      if (eventHover && eventHover.replay) {
        if (touched && armed !== eventHover.html) { armed = eventHover.html; return; }  // the first tap: its tooltip
        armed = null; tip.hidden = true; root.afReplay();
        return;
      }
      // what the click is on: zoomed in, the scene may have been drawn afresh since the pointer
      // last moved, and what it pointed at then is gone
      const zoom = root.afVisits, env = current();
      let tree = hover && hover.tree, deep = deepHover;
      if (zoom && zoom.on && env) { const hit = hitAt(env, e); tree = hit && hit.p && !hit.pond ? hit.p.it : null; deep = hit && hit.deep; }
      if (zoom && zoom.on && tree && zoom.picked !== tree.index) { tip.hidden = true; zoom.pick(tree.index); return; }
      // (zoomed in, a double-click's second click is not a click on the tree it just selected: it
      // walks in, web/visit.js, rather than open Anki's browser)
      if (zoom && zoom.on && e.detail > 1) return;
      // (and a click on the ground, with a tree selected, lets it go, as Esc does)
      if (zoom && zoom.on && !tree && !deep && zoom.picked != null) { zoom.pick(null); return; }
      if (data.testForest) return;
      if (deep) send(`${data.channel}:browse:${deep.from_ago}:${AF.deckFor(data)}:${deep.to_ago}`);
      else if (tree) send(`${data.channel}:browse:` + tree.ago + ':' + (data.deckId && !tree.dim ? data.deckId : ''));
    });
  }
  /* the scene was rebuilt under the pointer (zooming in): what it pointed at is gone */
  function clear() {
    linkedAgo = null; liftedMine = null; pickCache.lifted = null; litTrees = null; hover = null; deepHover = null; eventHover = null; shown = null; armed = null; tip.hidden = true; canvas.style.cursor = '';
    if (!lastAt || touched || canvas.closest('.af-dragging')) return;
    clearTimeout(again);
    again = setTimeout(() => {
      if (!lastAt || !canvas.isConnected) return;
      const e = new MouseEvent('mousemove', Object.assign({ bubbles: true }, lastAt));
      e.afAgain = true;
      canvas.dispatchEvent(e);
    }, 0);
  }
  return { drawLifted, drawMarker, clear, pickedRing };
};
})();

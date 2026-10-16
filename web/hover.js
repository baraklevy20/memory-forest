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
AF.watchHint = touched => `<br><span class="af-hint">${touched ? 'Tap again' : 'Click'} to watch it again</span>`;

/* Wire up one mounted forest. `env()` is the scene as currently built (it is rebuilt on a
 * resize), and `redraw()` draws a still forest's moment again. Returns what the runner
 * draws of it each frame. */
AF.hover = function ({ root, canvas, tip, sceneEl, data, animate, env: current, redraw }) {
  const words = AF.WORDS;
  let hover = null, deepHover = null, eventHover = null, touched = false, armed = null, shown = null;  // armed: what one more tap replays; shown: the tip as written
  let linkedAgo = null, lifted = null;
  const plantedDays = new Set((data.calendar && data.calendar.planted || []).map(t => t[0]));
  root.afPointTreeDay = ago => {
    if (linkedAgo === ago) return;
    linkedAgo = ago; lifted = null; redraw();
  };
  function drawMarker(g) {
    const env = current();
    const p = env && linkedAgo !== null && env.placed.find(p => !p.it.pond && p.it.ago === linkedAgo);
    if (p) {
      // sprite() borrows a scratch canvas: keep one outlined copy until the scene changes.
      if (!lifted || lifted.env !== env) {
        const { h, hzq } = AF.pixel.sizeOf(p, env), spr = AF.pixel.sprite(p.it, h, hzq, env);
        const [cv, cg] = AF.u.layer(spr.width + 2, spr.height + 2);
        for (const [x, y] of [[0, 1], [2, 1], [1, 0], [1, 2]]) cg.drawImage(spr, x, y);
        cg.globalCompositeOperation = 'source-in'; cg.fillStyle = '#fff8e0'; cg.fillRect(0, 0, cv.width, cv.height);
        cg.globalCompositeOperation = 'source-over'; cg.drawImage(spr, 1, 1);
        lifted = { env, cv };
      }
      const cv = lifted.cv, x = Math.round(p.x - (cv.width - 2) / 2) - 1, y = Math.round(p.y - (cv.height - 2) + 1) - 1;
      g.save();
      if (env.flipLight) { g.translate(x + cv.width, y); g.scale(-1, 1); g.drawImage(cv, 0, 0); }
      else g.drawImage(cv, x, y);
      g.restore();
      marker(g, p.x, y);
      return;
    }
    const deep = env && env.deep, merged = data.merged;
    if (linkedAgo !== null && merged && plantedDays.has(linkedAgo) && linkedAgo >= merged.to_ago && linkedAgo <= merged.from_ago
        && deep && deep.boxes.length && !(root.afVisits && root.afVisits.on)) {
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
  function marker(g, cx, top) {
    const x = Math.round(cx), y = Math.round(top - 3);
    g.fillStyle = 'rgba(20,20,20,.7)'; g.fillRect(x - 3, y - 1, 7, 1);
    g.fillStyle = '#fff8e0';
    for (let r = 0; r < 3; r++) g.fillRect(x - (2 - r), y + r, 5 - 2 * r, 1);
  }

  function boxOf(env, p) {
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
      if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { p, b };
    }
    return deepPick(env, mx, my);
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
  if (data.tooltips) {
    canvas.addEventListener('pointerdown', e => { touched = e.pointerType !== 'mouse'; });
    canvas.addEventListener('mousemove', e => {
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
        html = AF.tips.deep(hit.deep, words);
        canvas.style.cursor = data.inAnki && !data.testForest ? 'pointer' : '';
        deepHover = hit.deep;
      }
      else {
        hover = { x: hit.p.x, top: hit.b ? hit.b.y0 : hit.p.y - 4 * env.u, tree: hit.pond ? null : hit.p.it };
        // zoomed in, a click picks a tree first (web/visit.js)
        const zoom = root.afVisits, picks = !hit.pond && zoom && zoom.on && zoom.picked !== hit.p.it.index;
        html = hit.pond ? AF.tips.pond(hit.p.it) : AF.tips.tree(hit.p.it, words, picks ? `${touched ? 'Tap' : 'Click'} to select it` : '');
        canvas.style.cursor = !hit.pond && (picks || (data.inAnki && !data.testForest)) ? 'pointer' : '';
      }
      // the same thing pointed at as before: the tip only follows the pointer (rewriting it, and
      // redrawing a still forest, on every move of the mouse was most of the cost of pointing)
      const changed = html !== shown || tip.hidden;
      if (changed) { tip.innerHTML = shown = html; }
      tip.hidden = false;
      // the pointer within the scene, which holds the canvas and the tip
      const at = AF.u.pointIn(e, canvas), x = canvas.offsetLeft + at[0], y = canvas.offsetTop + at[1];
      let left = x + TIP_OFFSET, top = y + TIP_OFFSET;
      if (left + tip.offsetWidth > sceneEl.clientWidth - TIP_MARGIN) left = x - tip.offsetWidth - TIP_OFFSET;
      if (top + tip.offsetHeight > sceneEl.clientHeight - TIP_MARGIN) top = y - tip.offsetHeight - TIP_OFFSET;
      tip.style.left = Math.max(TIP_MARGIN, left) + 'px'; tip.style.top = Math.max(TIP_MARGIN, top) + 'px';
      if (changed) redraw();  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { hover = null; deepHover = null; shown = null; tip.hidden = true; canvas.style.cursor = ''; redraw(); });
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
      if (data.testForest) return;
      if (deep) send(`${data.channel}:browse:${deep.from_ago}:${AF.deckFor(data)}:${deep.to_ago}`);
      else if (tree) send(`${data.channel}:browse:` + tree.ago + ':' + (data.deckId && !tree.dim ? data.deckId : ''));
    });
  }
  /* the scene was rebuilt under the pointer (zooming in): what it pointed at is gone */
  function clear() { linkedAgo = null; lifted = null; hover = null; deepHover = null; eventHover = null; shown = null; armed = null; tip.hidden = true; canvas.style.cursor = ''; }
  return { drawMarker, clear };
};
})();

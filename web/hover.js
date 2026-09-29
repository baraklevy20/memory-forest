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
  let hover = null, deepHover = null, eventHover = null, touched = false, armed = null;  // armed: what one more tap replays
  function drawMarker(g) {
    if (!hover) return;
    const x = Math.round(hover.x), y = Math.round(hover.top - 3);
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
  if (data.tooltips) {
    canvas.addEventListener('pointerdown', e => { touched = e.pointerType !== 'mouse'; });
    canvas.addEventListener('mousemove', e => {
      const env = current();
      if (!env) return;
      // where on the canvas, in its own layout: a forest turned on the page (the phone
      // card's sideways view) is pointed at the same as an upright one
      const scale = env.W / (canvas.clientWidth || env.W), mx = e.offsetX * scale, my = e.offsetY * scale;
      const hit = pick(env, mx, my);
      deepHover = null; eventHover = null;
      if (!hit || !hit.event || hit.event.html !== armed) armed = null;  // a tap on something else starts over
      if (!hit) { hover = null; tip.hidden = true; canvas.style.cursor = ''; return; }
      if (hit.visitor) { hover = null; tip.innerHTML = AF.tips.visitor(hit.visitor); canvas.style.cursor = ''; }
      else if (hit.event) {
        hover = null; eventHover = hit.event;
        tip.innerHTML = hit.event.html + (hit.event.replay ? AF.watchHint(touched) : '');
        canvas.style.cursor = hit.event.replay ? 'pointer' : '';
      }
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
      // the pointer within the scene, which holds the canvas and the tip
      const x = canvas.offsetLeft + e.offsetX, y = canvas.offsetTop + e.offsetY;
      let left = x + TIP_OFFSET, top = y + TIP_OFFSET;
      if (left + tip.offsetWidth > sceneEl.clientWidth - TIP_MARGIN) left = x - tip.offsetWidth - TIP_OFFSET;
      if (top + tip.offsetHeight > sceneEl.clientHeight - TIP_MARGIN) top = y - tip.offsetHeight - TIP_OFFSET;
      tip.style.left = Math.max(TIP_MARGIN, left) + 'px'; tip.style.top = Math.max(TIP_MARGIN, top) + 'px';
      redraw();  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { hover = null; deepHover = null; tip.hidden = true; canvas.style.cursor = ''; redraw(); });
    canvas.addEventListener('click', () => {
      if (eventHover && eventHover.replay) {
        if (touched && armed !== eventHover.html) { armed = eventHover.html; return; }  // the first tap: its tooltip
        armed = null; tip.hidden = true; root.afReplay();
        return;
      }
      if (data.testForest) return;
      if (deepHover) send(`${data.channel}:browse:${deepHover.from_ago}:${AF.deckFor(data)}:${deepHover.to_ago}`);
      else if (hover && hover.tree) send(`${data.channel}:browse:` + hover.tree.ago + ':' + (data.deckId && !hover.tree.dim ? data.deckId : ''));
    });
  }
  return { drawMarker };
};
})();

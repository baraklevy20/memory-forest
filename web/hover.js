/* Memory Forest — pointing at the forest: what is under the pointer (an animal, a tree, a
 * pond, the deep forest), its tooltip, the marker over the tree pointed at, and a click
 * that opens that tree's cards in Anki's browser. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { send } = AF.u;
// the tooltip sits this far from the pointer, and this far inside the scene's edges
const TIP_OFFSET = 14, TIP_MARGIN = 6;

/* Wire up one mounted forest. `env()` is the scene as currently built (it is rebuilt on a
 * resize), and `redraw()` draws a still forest's moment again. Returns what the runner
 * draws of it each frame. */
AF.hover = function ({ canvas, tip, sceneEl, data, env: current, redraw }) {
  const words = AF.WORDS;
  let hover = null, deepHover = null;
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
    for (const b of env.visitorBoxes || []) if (mx >= b.x0 && mx <= b.x1 && my >= b.y0 && my <= b.y1) return { visitor: b.v };
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
    canvas.addEventListener('mousemove', e => {
      const env = current();
      if (!env) return;
      const r = canvas.getBoundingClientRect();
      const scale = env.W / (r.width || env.W), mx = (e.clientX - r.left) * scale, my = (e.clientY - r.top) * scale;
      const hit = pick(env, mx, my);
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
      redraw();  // a still forest redraws the same moment, only the marker moves
    });
    canvas.addEventListener('mouseleave', () => { hover = null; deepHover = null; tip.hidden = true; canvas.style.cursor = ''; redraw(); });
    canvas.addEventListener('click', () => {
      if (data.testForest) return;
      if (deepHover) send(`${data.channel}:browse:${deepHover.from_ago}:${AF.deckFor(data)}:${deepHover.to_ago}`);
      else if (hover && hover.tree) send(`${data.channel}:browse:` + hover.tree.ago + ':' + (data.deckId && !hover.tree.dim ? data.deckId : ''));
    });
  }
  return { drawMarker };
};
})();

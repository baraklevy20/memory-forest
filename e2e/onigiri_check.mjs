// node e2e/onigiri_check.mjs <page.html> <chrome> [split]: the Onigiri tile of e2e/onigiri_check.py, in
// headless Chrome. Prints JSON: { tile: rect, forest: box, heatmap: box, errors: [...] }, each box
// { rect, inTile, colours } (how many colours its canvas holds) or null where there is none. With
// `split`, the forest in #tile and the heatmap in a tile of its own, #tile2 ({ tile2: rect }), and
// { strays: n }: the forests and heatmaps in the other's tile. { overflow: [px] }: each tile's content past its bottom.
import puppeteer from 'puppeteer-core';

const [html, chrome, mode] = process.argv.slice(2);
const split = mode === 'split', calTile = split ? '#tile2' : '#tile';
const LOAD_MS = 15000;
const SETTLE_MS = 800;  // (the heatmap is drawn a moment after the forest)
const wait = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu', '--allow-file-access-from-files'] });
const out = { errors: [] };
try {
  const p = await browser.newPage();
  await p.setViewport({ width: 1200, height: 900 });
  p.on('pageerror', e => out.errors.push(e.message));
  p.on('console', m => { if (m.type() === 'error') out.errors.push('console: ' + m.text()); });
  p.on('requestfailed', r => out.errors.push(`not loaded: ${r.url()}`));
  await p.goto('file://' + html);
  try {
    await p.waitForFunction(t => document.querySelector('#tile .af-canvas') && document.querySelector(t + ' .af-cal-canvas'), { timeout: LOAD_MS }, calTile);
  } catch {
    out.errors.push(split ? 'the forest and the heatmap never both showed in their tiles' : 'the forest and the heatmap never both showed in the tile');
  }
  await wait(SETTLE_MS);
  Object.assign(out, await p.evaluate(calTile => {
    const rect = el => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); };
    const box = (where, sel) => {
      const tile = rect(document.querySelector(where));
      const cv = document.querySelector(where + ' ' + sel);
      if (!cv || !cv.width || !cv.height) return null;
      const r = rect(cv), seen = new Set(), px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
      for (let i = 0; i < px.length && seen.size < 64; i += 4) if (px[i + 3]) seen.add((px[i] << 16) | (px[i + 1] << 8) | px[i + 2]);
      // in the tile: on screen, and no wider than it, its top inside (Onigiri cuts what overflows below)
      const inTile = r[2] > r[0] && r[0] >= tile[0] && r[2] <= tile[2] && r[1] >= tile[1] && r[1] < tile[3];
      return { rect: r, inTile, colours: seen.size };
    };
    const two = calTile !== '#tile';
    return { tile: rect(document.getElementById('tile')), tile2: two ? rect(document.querySelector(calTile)) : null,
             forest: box('#tile', '.af-canvas'), heatmap: box(calTile, '.af-cal-canvas'),
             strays: two ? document.querySelectorAll('#tile .af-cal-canvas, #tile2 .af-canvas').length : 0,
             // (each tile's content past its bottom: cut off, or a scroll bar in Onigiri)
             // (the lowest thing drawn in it against its bottom: a flex child shrinks, so the tile's
             // scrollHeight never shows what it cuts off)
             overflow: [...document.querySelectorAll('.external-widget-container')].map(t => {
               const bottom = t.getBoundingClientRect().bottom;
               let low = bottom;
               t.querySelectorAll('canvas, .af-caption, .af-journal, .af-meta').forEach(e => {
                 const r = e.getBoundingClientRect();
                 if (r.width && r.height) low = Math.max(low, r.bottom);
               });
               return Math.round(low - bottom);
             }) };
  }, calTile));
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

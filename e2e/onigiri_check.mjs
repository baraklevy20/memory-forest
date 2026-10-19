// node e2e/onigiri_check.mjs <page.html> <chrome>: the Onigiri tile of e2e/onigiri_check.py, in
// headless Chrome. Prints JSON: { tile: rect, forest: box, heatmap: box, errors: [...] }, each box
// { rect, inTile, colours } (how many colours its canvas holds) or null where there is none.
import puppeteer from 'puppeteer-core';

const [html, chrome] = process.argv.slice(2);
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
    await p.waitForFunction(() => document.querySelector('#tile .af-canvas') && document.querySelector('#tile .af-cal-canvas'), { timeout: LOAD_MS });
  } catch {
    out.errors.push('the forest and the heatmap never both showed in the tile');
  }
  await wait(SETTLE_MS);
  Object.assign(out, await p.evaluate(() => {
    const rect = el => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); };
    const tile = rect(document.getElementById('tile'));
    const box = sel => {
      const cv = document.querySelector('#tile ' + sel);
      if (!cv || !cv.width || !cv.height) return null;
      const r = rect(cv), seen = new Set(), px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
      for (let i = 0; i < px.length && seen.size < 64; i += 4) if (px[i + 3]) seen.add((px[i] << 16) | (px[i + 1] << 8) | px[i + 2]);
      // in the tile: on screen, and no wider than it, its top inside (Onigiri cuts what overflows below)
      const inTile = r[2] > r[0] && r[0] >= tile[0] && r[2] <= tile[2] && r[1] >= tile[1] && r[1] < tile[3];
      return { rect: r, inTile, colours: seen.size };
    };
    return { tile, forest: box('.af-canvas'), heatmap: box('.af-cal-canvas') };
  }));
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

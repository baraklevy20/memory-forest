// node e2e/onigiri_swap.mjs <page.html> <swaps.json> <fresh.html> <chrome>: e2e/onigiri_check.py's
// scenery change in Onigiri's two tiles, in headless Chrome. The page's tiles are swapped in place
// with swaps.json ([{ root, data, srcs }], the forest's first, as panel._swap_tiles does), and the
// colours of both tiles then are set beside a page drawn afresh with the new scenery. Prints JSON:
// { swapped, fresh, before: { heatmap: [r, g, b], forest: [r, g, b] }, errors: [...] }, each the mean colour
// of a tile's canvas's saturated pixels (the heatmap's studied days; the forest's sky and trees).
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const [html, swapsFile, freshHtml, chrome] = process.argv.slice(2);
const swaps = JSON.parse(fs.readFileSync(swapsFile, 'utf8'));
const cal = swaps[swaps.length - 1].root, forest = swaps[0].root;
const LOAD_MS = 15000, SETTLE_MS = 1500;
const wait = ms => new Promise(r => setTimeout(r, ms));
// (in the page) the mean colour of the heatmap's saturated pixels: its studied days, not the page or the soil
const colour = ([id, sel]) => {
  const cv = (document.getElementById(id) || { querySelector: () => null }).querySelector(sel);
  if (!cv || !cv.width) return null;
  const px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data, sum = [0, 0, 0];
  let n = 0;
  for (let i = 0; i < px.length; i += 4) {
    if (!px[i + 3] || Math.max(px[i], px[i + 1], px[i + 2]) - Math.min(px[i], px[i + 1], px[i + 2]) < 40) continue;
    sum[0] += px[i]; sum[1] += px[i + 1]; sum[2] += px[i + 2]; n++;
  }
  // (and the canvas as a whole, to set beside a fresh page's: with no animations the two are drawn alike)
  return n ? { mean: sum.map(v => Math.round(v / n)), whole: cv.toDataURL() } : null;
};

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu', '--allow-file-access-from-files'] });
const out = { errors: [] };
try {
  const open = async path => {
    const p = await browser.newPage();
    await p.setViewport({ width: 1200, height: 900 });
    p.on('pageerror', e => out.errors.push(e.message));
    p.on('console', m => { if (m.type() === 'error') out.errors.push('console: ' + m.text()); });
    await p.goto('file://' + path);
    await p.waitForFunction(id => (document.getElementById(id) || { querySelector: () => null }).querySelector('.af-cal-canvas'), { timeout: LOAD_MS }, cal);
    await wait(SETTLE_MS);
    return p;
  };
  const p = await open(html);
  const both = async q => ({ heatmap: await q.evaluate(colour, [cal, '.af-cal-canvas']), forest: await q.evaluate(colour, [forest, '.af-canvas']) });
  out.before = await both(p);
  // (both at once: Anki sends them one right after the other, and the two copies' loads of the new
  // scenery overlapping is what the forest's tile lost its scenery to; one call makes that overlap sure)
  const ok = await p.evaluate(all => all.map(s => { const r = document.getElementById(s.root); return !!(r && r.afSwap && r.afSwap(s.data, s.srcs)); }), swaps);
  ok.forEach((done, i) => { if (!done) out.errors.push(`no swap on ${swaps[i].root}`); });
  await wait(SETTLE_MS * 2);
  out.swapped = await both(p);
  out.fresh = await both(await open(freshHtml));
} catch (e) {
  out.errors.push(String(e && e.message || e));
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

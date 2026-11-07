// node e2e/onigiri_swap.mjs <page.html> <swaps.json> <fresh.html> <chrome>: e2e/onigiri_check.py's
// scenery change in Onigiri's two tiles, in headless Chrome. The page's tiles are swapped in place
// with swaps.json ([{ root, data, srcs }], the forest's first, as panel._swap_tiles does), and the
// heatmap tile's colour then is set beside a page drawn afresh with the new scenery. Prints JSON:
// { swapped: [r, g, b], fresh: [r, g, b], before: [r, g, b], errors: [...] }, each the mean colour of
// the heatmap's studied days (its saturated pixels).
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const [html, swapsFile, freshHtml, chrome] = process.argv.slice(2);
const swaps = JSON.parse(fs.readFileSync(swapsFile, 'utf8'));
const cal = swaps[swaps.length - 1].root;
const LOAD_MS = 15000, SETTLE_MS = 1500;
const wait = ms => new Promise(r => setTimeout(r, ms));
// (in the page) the mean colour of the heatmap's saturated pixels: its studied days, not the page or the soil
const colour = id => {
  const cv = (document.getElementById(id) || { querySelector: () => null }).querySelector('.af-cal-canvas');
  if (!cv || !cv.width) return null;
  const px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data, sum = [0, 0, 0];
  let n = 0;
  for (let i = 0; i < px.length; i += 4) {
    if (!px[i + 3] || Math.max(px[i], px[i + 1], px[i + 2]) - Math.min(px[i], px[i + 1], px[i + 2]) < 40) continue;
    sum[0] += px[i]; sum[1] += px[i + 1]; sum[2] += px[i + 2]; n++;
  }
  return n ? sum.map(v => Math.round(v / n)) : null;
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
  out.before = await p.evaluate(colour, cal);
  // (each swap in its own call, as Anki's evalWithCallback sends them)
  for (const s of swaps) {
    const ok = await p.evaluate((id, d, srcs) => { const r = document.getElementById(id); return !!(r && r.afSwap && r.afSwap(d, srcs)); }, s.root, s.data, s.srcs);
    if (!ok) out.errors.push(`no swap on ${s.root}`);
  }
  await wait(SETTLE_MS * 2);
  out.swapped = await p.evaluate(colour, cal);
  out.fresh = await (await open(freshHtml)).evaluate(colour, cal);
} catch (e) {
  out.errors.push(String(e && e.message || e));
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

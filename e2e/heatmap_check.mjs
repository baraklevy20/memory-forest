// node e2e/heatmap_check.mjs <heatmap.html> <chrome>: e2e/heatmap_check.py's look at the heatmap's
// hover layers, in headless Chrome. Prints JSON: { states: { state: [{ name, off }] }, errors },
// `off` "" where a year's layer lies on its weeks, else how far it is.
import puppeteer from 'puppeteer-core';

const [html, chrome] = process.argv.slice(2);
const wait = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu'] });
const out = { states: {}, errors: [] };
try {
  const p = await browser.newPage();
  await p.setViewport({ width: 900, height: 700, deviceScaleFactor: 2 });
  p.on('pageerror', e => out.errors.push(e.message));
  await p.goto('file://' + html);
  await p.waitForSelector('.af-cal-canvas', { timeout: 10000 });
  await wait(400);
  // each year's weeks and its layer: the year in view's (in the grid), and each earlier one's
  const look = () => p.evaluate(() => {
    const pairs = [...document.querySelectorAll('.af-cal-canvas')].map(cv => {
      const above = cv.parentElement.querySelector(':scope > .af-cal-above:not(.af-cal-spot)');
      const name = cv.classList.contains('af-cal-past-weeks') ? cv.parentElement.querySelector('b').textContent : 'the year in view';
      if (!above) return { name, off: 'missing' };
      const a = cv.getBoundingClientRect(), b = above.getBoundingClientRect();
      const d = [b.left - a.left, b.top - a.top, b.width - a.width, b.height - a.height].map(v => Math.round(v));
      return { name, off: d.some(v => Math.abs(v) > 1) ? `${d[0]}, ${d[1]} px (size ${d[2]}, ${d[3]})` : '' };
    });
    return pairs;
  });
  out.states['earlier years hidden'] = await look();
  const more = await p.$('.af-cal-more');
  if (!more) out.errors.push('no switch to show the earlier years');
  else {
    await more.click(); await wait(500);
    out.states['earlier years shown'] = await look();
    await (await p.$('.af-cal-more')).click(); await wait(500);
    out.states['hidden again'] = await look();
  }
} catch (e) {
  out.errors.push(String(e));
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify(out));

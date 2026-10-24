// node e2e/layout_check.mjs <jobs.json> <chrome>: the deck-list pages of e2e/layout_check.py, in
// headless Chrome, one after another. Prints JSON, a result for each job: the window's width, each
// box's [left, top, right, bottom] (the deck table, the forest's and the heatmap's canvases, the
// forest's scene and the heatmap's box, for their widths, the band over the heatmap's months (its padding), Anki's studied-today line), how many colours each canvas holds, whether the page was arranged
// (body.af-lay), and its errors, a ResizeObserver's loop among them, as the window is then resized
// across the breakpoint and back; or { missing } where the forest and the heatmap never showed. A job
// with `forest` or `heatmap` false (that one switched off on the deck list) waits for the other alone,
// and gives null for the boxes and colours of the one switched off.
import puppeteer from 'puppeteer-core';
import fs from 'fs';

const [jobsPath, chrome] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
const LOAD_MS = 15000;
const SETTLE_MS = 900;  // (the heatmap is drawn a moment after the forest, and a resize is debounced)
const wait = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu', '--allow-file-access-from-files'] });
const out = [];
try {
  for (const job of jobs) {
    const p = await browser.newPage();
    const errors = [];
    await p.setViewport({ width: job.width, height: 1000 });
    // (the page's own error events too: a ResizeObserver's loop is one, and reaches no console)
    await p.evaluateOnNewDocument(() => window.addEventListener('error', e => (window.afErrors = window.afErrors || []).push(e.message)));
    p.on('pageerror', e => errors.push(e.message));
    p.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
    p.on('requestfailed', r => errors.push(`not loaded: ${r.url()}`));
    await p.goto('file://' + job.html);
    try {
      await p.waitForFunction((f, h) => (!f || document.querySelector('.af-canvas')) && (!h || document.querySelector('.af-cal-canvas')),
        { timeout: LOAD_MS }, job.forest !== false, job.heatmap !== false);
    } catch {
      out.push({ missing: 'the forest and the heatmap never both showed', errors });
      await p.close();
      continue;
    }
    await wait(SETTLE_MS);
    const got = await p.evaluate(() => {
      const rect = el => { if (!el) return null; const r = el.getBoundingClientRect(); return [r.left, r.top + window.scrollY, r.right, r.bottom + window.scrollY].map(Math.round); };
      const colours = cv => {
        if (!cv) return null;
        const seen = new Set(), px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
        for (let i = 0; i < px.length && seen.size < 64; i += 4) if (px[i + 3]) seen.add((px[i] << 16) | (px[i + 1] << 8) | px[i + 2]);
        return seen.size;
      };
      const forest = document.querySelector('.af-canvas'), heat = document.querySelector('.af-cal-canvas');
      return {
        window: document.documentElement.clientWidth, table: rect(document.querySelector('center > table')),
        forest: rect(forest), heatmap: rect(heat), scene: rect(document.querySelector('.af-scene')), cal: rect(document.querySelector('.af-cal')),
        calPad: document.querySelector('.af-cal') ? parseFloat(getComputedStyle(document.querySelector('.af-cal')).paddingTop) : null, studied: rect(document.getElementById('studiedToday')),
        forestColours: colours(forest), heatmapColours: colours(heat), arranged: document.body.classList.contains('af-lay')
      };
    });
    if (job.shot) await p.screenshot({ path: job.shot, fullPage: true });
    // the window resized across the breakpoint and back: nothing may complain
    // (and then fits each width: a canvas drawn for the wider one held the heatmap past a narrow
    // window's edge in Anki 2.1.45)
    for (const w of [job.other, job.width]) {
      await p.setViewport({ width: w, height: 1000 }); await wait(SETTLE_MS);
      const past = await p.evaluate(() => [...document.querySelectorAll('.af-canvas, .af-cal-canvas, .af-cal')]
        .map(e => Math.round(e.getBoundingClientRect().right)).filter(r => r > document.documentElement.clientWidth + 1));
      if (past.length) errors.push(`at ${w} px after a resize, reaching past the window: ${past.join(', ')}`);
    }
    errors.push(...await p.evaluate(() => window.afErrors || []));
    out.push(Object.assign(got, { errors }));
    await p.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

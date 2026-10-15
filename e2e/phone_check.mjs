// node e2e/phone_check.mjs <card.html> <chrome>: the taps of e2e/phone_check.py, in headless Chrome
// as a phone. Prints JSON: { forest: { setup: { tree: tooltip } }, calendar: { setup: { pixel:
// tooltip } }, errors: [...] }, each tooltip "" where a tap showed none.
import puppeteer from 'puppeteer-core';

const [html, chrome] = process.argv.slice(2);
const ZOOM = 1.25;  // AnkiDroid's card zoom, about
const SETUPS = [['upright', 1, false], ['upright, zoomed', ZOOM, false], ['sideways', 1, true], ['sideways, zoomed', ZOOM, true]];
const LOAD_MS = 10000, TURN_MS = 1500, TAP_MS = 60;
const SETTLE_MS = 800;  // once drawn: past the phone card's relayout (web/phone.js RELAYOUT_MS) and its new drawing
const wait = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu'] });
const out = { forest: {}, calendar: {}, errors: [] };
try {
  // (one page at a time: a page in a tab behind gets its timers slowed, and is tapped before
  // it has settled)
  for (const target of ['forest', 'calendar']) {
    for (const [setup, zoom, sideways] of SETUPS) {
      const p = await browser.newPage();
      await p.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
      p.on('pageerror', e => out.errors.push(`${target}, ${setup}: ${e.message}`));
      if (zoom !== 1) await p.evaluateOnNewDocument(z => document.addEventListener('DOMContentLoaded', () => { document.body.style.zoom = z; }), String(zoom));
      await p.goto('file://' + html);
      // drawn: the forest built, and the calendar under it (a moment later)
      await p.waitForFunction(() => document.getElementById('memory-forest-phone').afEnv && document.querySelector('.af-cal-canvas'), { timeout: LOAD_MS });
      await wait(SETTLE_MS);
      if (sideways) {  // the full screen, which turns a phone held upright's view on its side
        await p.evaluate(t => document.querySelector(t === 'forest' ? '.af-expand:not(.af-expand-cal)' : '.af-expand-cal').click(), target);
        await wait(TURN_MS);
      }
      // where to tap, in the canvas's own css pixels, each named so every set-up taps the same:
      // the forest's front trees (by their place in it), the calendar's days (by their pixel)
      const spots = await p.evaluate(t => {
        if (t === 'forest') {
          const env = document.getElementById('memory-forest-phone').afEnv, cv = document.querySelector('.af-canvas'), s = cv.clientWidth / env.W;
          // (the middle of each one's tap box, as web/hover.js boxOf has it: its stage's height, scaled)
          const STAGE_H = [4, 8, 13, 19, 27, 38];
          return env.placed.filter(q => !q.it.pond).sort((a, b) => b.y - a.y).slice(0, 10)
            .map(q => ({ key: `tree ${q.it.index}`, x: q.x * s, y: (q.y - STAGE_H[q.it.stage] * env.u * q.s / 2) * s }));
        }
        const cv = document.querySelector('.af-cal-canvas'), s = cv.clientWidth / cv.width, out = [];
        for (let j = 0; j < 6; j++) for (const row of [1, 3, 5]) {
          const x = cv.width - 11 * (2 * j + 4) + 5, y = 14 + 11 * row + 5;  // (a cell is 11 pixels, the weeks 14 down)
          out.push({ key: `pixel ${x},${y}`, x: x * s, y: y * s });
        }
        return out;
      }, target);
      const taps = {};
      for (const spot of spots) {
        // the spot on the screen, from the canvas's box alone (turned a quarter clockwise when
        // sideways), and in view: the calendar scrolled to it
        const at = await p.evaluate((t, spot) => {
          const cv = document.querySelector(t === 'forest' ? '.af-canvas' : '.af-cal-canvas');
          if (t === 'calendar') { const g = cv.parentElement; g.scrollLeft = spot.x - g.clientWidth / 2; }
          const r = cv.getBoundingClientRect(), w = cv.clientWidth, h = cv.clientHeight;
          const [x, y] = cv.closest('.af-sideways') ? [r.right - spot.y * r.width / h, r.top + spot.x * r.height / w]
            : [r.left + spot.x * r.width / w, r.top + spot.y * r.height / h];
          return x > 2 && y > 2 && x < innerWidth - 2 && y < innerHeight - 2 ? [x, y] : null;
        }, target, spot);
        if (!at) continue;
        await wait(TAP_MS);
        await p.touchscreen.tap(at[0], at[1]);
        await wait(TAP_MS);
        taps[spot.key] = await p.evaluate(t => {
          const tip = document.querySelector(t === 'forest' ? '.af-scene .af-tip' : '.af-cal-tip');
          return tip && !tip.hidden ? tip.innerText.trim() : '';
        }, target);
      }
      out[target][setup] = taps;
      await p.close();
    }
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(out));

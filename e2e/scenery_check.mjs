// node e2e/scenery_check.mjs <page.html> <swap.html> <scenes.json> <chrome> <out.json>: the scenes of
// e2e/scenery_check.py, each mounted in turn on one page of one headless Chrome (no Chrome per
// scene: a mount takes a tenth of a second, a Chrome two). Writes JSON: { first: { name: shot },
// again: { name: shot }, swapped: { name: shot } }, a shot being { errors, hash, opaque, colours, w,
// h, placed, frames, zoom }.
//
// `again` draws the scenes marked `again` a second time on a fresh page, in the opposite order and
// with Math.random giving other numbers: a scene that draws differently there reads randomness, or
// something left behind by the scenes drawn before it.
import fs from 'fs';
import puppeteer from 'puppeteer-core';

const [html, swapHtml, scenesPath, chrome, outPath] = process.argv.slice(2);
const scenes = JSON.parse(fs.readFileSync(scenesPath, 'utf-8'));
const LOAD_MS = 20000;
// an animated scene: how long the forest gets to draw a frame once its clock has moved on
// (core.js draws one each 66-100ms, from a timer)
const TICK_MS = 260;
// zoomed in: a move is drawn MOVE_MS after it (web/visit.js), a fade takes FADE_MS
const MOVE_WAIT_MS = 10, ZOOM_WAIT_MS = 120;
const RESIZE_WAIT_MS = 600;
const wait = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu'] });

async function open(url = html) {
  const p = await browser.newPage();
  await p.setViewport({ width: 900, height: 700 });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e.stack || e.message || e)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console.error: ' + m.text()); });
  await p.goto('file://' + url);
  await p.waitForFunction(() => window.__ready === true, { timeout: LOAD_MS });
  if (errs.length) throw new Error('the page did not load cleanly: ' + errs.join('\n'));
  return { p, errs };
}

async function shoot(page, scene, seed) {
  const { p, errs } = page;
  errs.length = 0;
  const shot = await p.evaluate((data, seed) => window.__mount(data, seed), scene.data, seed);
  if (scene.data._resize) {  // (core.js rebuilds once the width has settled for 200ms)
    await p.evaluate(w => { document.getElementById('p').style.width = w + 'px'; }, scene.data._resize);
    await wait(RESIZE_WAIT_MS);
    shot.resized = await p.evaluate(() => window.__snap().hash);
  }
  if (scene.zoom) shot.zoom = await zoom(p);
  if (scene.frames) {
    shot.frames = [];
    for (const t of scene.frames) {
      await p.evaluate(t => { window.__now = window.__T0 + t * 1000; }, t);
      await wait(TICK_MS);
      shot.frames.push(await p.evaluate(() => window.__snap().hash));
    }
  }
  await wait(0);
  shot.errors = shot.errors.concat(errs);
  return shot;
}

// zoomed in (web/visit.js): its button, the arrow keys in and along, a click on the tree in the
// middle and its day before; then back out. { in, out: hashes, picked: a tree was }, or null
// with no zoom button
async function zoom(p) {
  const button = await p.$('#p .af-zoom');
  if (!button) return null;
  await button.click();
  for (const key of ['ArrowUp', 'ArrowUp', 'ArrowUp', 'ArrowUp', 'ArrowUp', 'ArrowUp', 'ArrowLeft', 'ArrowLeft', 'ArrowRight']) {
    await p.keyboard.press(key);
    await wait(MOVE_WAIT_MS);
  }
  await wait(ZOOM_WAIT_MS);
  // the front tree nearest the middle, at the middle of its tap box (as web/hover.js has it)
  const at = await p.evaluate(() => {
    const root = document.getElementById('p'), env = root.afEnv, cv = root.querySelector('canvas'), r = cv.getBoundingClientRect();
    const k = r.width / env.W, trees = env.placed.filter(q => !q.it.pond && q.x > 0 && q.x < env.W && q.y < env.H);
    const q = trees.sort((a, b) => Math.abs(a.x - env.W / 2) - Math.abs(b.x - env.W / 2) + (b.y - a.y) * 0.5)[0];
    return q && [r.left + q.x * k, r.top + (q.y - AnkiForest.STAGE_H[q.it.stage] * env.u * q.s / 2) * k];
  });
  if (at) { await p.mouse.click(at[0], at[1]); await wait(ZOOM_WAIT_MS); }
  const picked = await p.evaluate(() => { const v = document.getElementById('p').afVisits; return v && v.picked != null; });
  const prev = await p.$('#p .af-visit-btn[data-day="prev"]:not([disabled])');
  if (prev) { await prev.click(); await wait(ZOOM_WAIT_MS); }
  const inside = await p.evaluate(() => window.__snap().hash);
  await (await p.$('#p .af-zoom')).click();
  await wait(ZOOM_WAIT_MS);
  return { in: inside, out: await p.evaluate(() => window.__snap().hash), picked };
}

const out = { first: {}, again: {}, swapped: {} };
try {
  let page = await open();
  for (const scene of scenes) {
    try { out.first[scene.name] = await shoot(page, scene, 1); }
    catch (e) { out.first[scene.name] = { errors: ['harness: ' + (e.stack || e)] }; await page.p.close(); page = await open(); }
  }
  await page.p.close();
  // (one page at a time: a page in a tab behind gets its timers slowed)
  page = await open();
  for (const scene of scenes.filter(s => s.again).reverse()) {
    try { out.again[scene.name] = await shoot(page, scene, 987654321); }
    catch (e) { out.again[scene.name] = { errors: ['harness: ' + (e.stack || e)] }; await page.p.close(); page = await open(); }
  }
  await page.p.close();
  // `swapped`: the scenes marked `swap`, each swapped in for the one before on a page that
  // loads their scenery files only as they are asked for
  page = await open(swapHtml);
  for (const scene of scenes.filter(s => s.swap)) {
    page.errs.length = 0;
    try {
      const shot = await page.p.evaluate((data, srcs) => window.__swap(data, srcs, 1), scene.data, scene.srcs);
      await wait(0);
      shot.errors = shot.errors.concat(page.errs);
      out.swapped[scene.name] = shot;
    } catch (e) { out.swapped[scene.name] = { errors: ['harness: ' + (e.stack || e)] }; await page.p.close(); page = await open(swapHtml); }
  }
  await page.p.close();
} finally {
  await browser.close();
}
fs.writeFileSync(outPath, JSON.stringify(out));

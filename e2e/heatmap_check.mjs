// node e2e/heatmap_check.mjs <heatmap.html> <chrome>: e2e/heatmap_check.py's look at the heatmap's
// hover layers, in headless Chrome. Prints JSON: { states: { state: [{ name, off }] }, errors },
// `off` "" where a year's layer lies on its weeks, else how far it is.
import puppeteer from 'puppeteer-core';

const [html, chrome, forest, deep] = process.argv.slice(2);
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
  const layoutChecks = await p.evaluate(() => {
    const root = document.getElementById('p'), box = root.querySelector('.af-cal'), failures = [];
    const css = getComputedStyle(root), contentWidth = root.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
    if (Math.abs(box.getBoundingClientRect().width / contentWidth - 0.85) > 0.01) failures.push('heatmap did not use the configured 85% width');
    if (!box.querySelector('.af-cal-current')?.textContent.includes('days')) failures.push('current streak has no day-count label');
    box.querySelector('[data-view="timeline"]').click();
    if (box.querySelectorAll('.af-cal-months span[data-m]').length !== 10) failures.push('Timeline did not show ten months');
    box.querySelector('[data-view="by_year"]').click();
    return failures;
  });
  out.errors.push(...layoutChecks);
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
  if (forest) {
    await p.goto('file://' + forest);
    await p.waitForSelector('.af-cal-canvas');
    const checks = await p.evaluate(() => {
      const root = document.getElementById('p'), cv = root.querySelector('.af-canvas');
      const snapshot = () => cv.toDataURL();
      const before = snapshot(), env = root.afEnv;
      const tree = env.placed.find(p => p.it.date === '2026-09-10') || env.placed.find(p => !p.it.pond && p.it.ago < 150);
      if (!tree) return ['missing test tree'];
      root.afPointTreeDay(tree.it.ago);
      const lit = snapshot();
      root.afPointTreeDay(null);
      const failures = [];
      if (lit === before) failures.push('day did not lift its tree in a still forest');
      if (snapshot() !== before) failures.push('clearing the day did not restore the forest');
      root.afPointTreeDay(-10);
      if (snapshot() !== before) failures.push('future day highlighted a tree');
      root.afPointTreeDay(null);
      const ring = root.querySelector('.af-cal-hover');
      ring.style.transition = 'none';
      const originalView = root.querySelector('.af-cal-canvas').getAttribute('aria-label');
      // Forest hover keeps the calendar still and leaves its tiles unselected.
      const front = [...env.placed].reverse().find(p => !p.it.pond && p.it.ago < 150);
      const r = cv.getBoundingClientRect(), scale = r.width / env.W;
      cv.dispatchEvent(new MouseEvent('mousemove', { clientX: r.left + front.x * scale, clientY: r.top + (front.y - 2) * scale }));
      if (!ring.hidden) failures.push('forest hover selected a calendar day');
      if (root.querySelector('.af-cal-canvas').getAttribute('aria-label') !== originalView) failures.push('forest hover navigated the calendar');
      cv.dispatchEvent(new MouseEvent('mouseleave'));
      if (!ring.hidden) failures.push('leaving the forest did not clear its day');
      const weeks = root.querySelector('.af-cal-canvas');
      weeks.focus();
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
      for (let i = 0; i < tree.it.ago; i++) weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
      if (snapshot() === before) failures.push('keyboard day did not highlight its tree');
      if (!root.querySelector('.af-cal-tip').textContent.includes('new cards')) failures.push('day tooltip omitted its planted cards');
      // Return to this exact day through the mouse handler, not the public link callback.
      const dayRing = ring.getBoundingClientRect(), dayX = dayRing.left + dayRing.width / 2, dayY = dayRing.top + dayRing.height / 2;
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      if (snapshot() !== before) failures.push('Escape did not clear the linked tree');
      weeks.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: dayX, clientY: dayY }));
      if (snapshot() === before) failures.push('mouse day did not highlight its tree');
      if (!root.querySelector('.af-cal-tip').textContent.includes('Sep 10, 2026') && tree.it.date === '2026-09-10') failures.push('September 10 pointer selected the wrong date');
      return failures;
    });
    out.errors.push(...checks);
    if (!checks.length) out.states['linked hover in a still forest'] = [{ name: 'tree and day', off: '' }];
  }
  if (deep) {
    await p.goto('file://' + deep);
    await p.waitForSelector('.af-cal-canvas');
    const checks = await p.evaluate(() => {
      const root = document.getElementById('p'), cv = root.querySelector('.af-canvas'), old = window.TEST_BEHIND[0];
      const failures = [], before = cv.toDataURL();
      root.afPointTreeDay(old.ago);
      if (cv.toDataURL() === before) failures.push('old day did not highlight the deep canopy');
      root.afPointTreeDay(null);
      if (cv.toDataURL() !== before) failures.push('clearing old day did not restore the canopy');
      const planted = new Set(window.TEST_BEHIND.map(t => t.ago));
      let gap = old.ago - 1;
      while (planted.has(gap)) gap--;
      root.afPointTreeDay(gap);
      if (cv.toDataURL() !== before) failures.push('unplanted old day highlighted the canopy');
      root.afPointTreeDay(null);
      root.querySelector('.af-zoom').click();
      return failures;
    });
    out.errors.push(...checks);
    await wait(250);
    const zoomChecks = await p.evaluate(() => {
      const root = document.getElementById('p'), AF = window.AnkiForest, cv = root.querySelector('.af-canvas');
      const base = AF.layout(root.afEnv.data.trees), behind = AF.layoutBehind(window.TEST_BEHIND, base), t = behind[0];
      root.afVisits.resume({ cam: { x: t.x * (base.perRow + 0.5), z: t.row + t.jy + 1, b: 1 }, picked: null });
      const failures = [];
      if (!root.afEnv.placed.some(p => p.it.index === t.index)) failures.push('oldest tree was not materialized in zoom');
      const before = cv.toDataURL();
      root.afPointTreeDay(t.ago);
      if (cv.toDataURL() === before) failures.push('oldest zoomed tree did not highlight');
      root.afPointTreeDay(null);
      if (cv.toDataURL() !== before) failures.push('oldest zoomed tree did not clear');
      const beforeHover = root.querySelector('.af-cal-canvas:not(.af-cal-past-weeks)').getAttribute('aria-label');
      const front = [...root.afEnv.placed].reverse().find(p => !p.it.pond), rect = cv.getBoundingClientRect(), scale = rect.width / root.afEnv.W;
      cv.dispatchEvent(new MouseEvent('mousemove', { clientX: rect.left + front.x * scale, clientY: rect.top + (front.y - 2) * scale }));
      if (root.querySelector('.af-cal-canvas:not(.af-cal-past-weeks)').getAttribute('aria-label') !== beforeHover) failures.push('hovering an old zoomed tree navigated the heatmap');
      if (!root.querySelector('.af-cal-hover').hidden) failures.push('hovering an old zoomed tree selected a heatmap day');
      cv.dispatchEvent(new MouseEvent('mouseleave'));
      root.afVisits.resume({ cam: root.afVisits.state.cam, picked: t.index });
      if (root.querySelector('.af-cal-canvas:not(.af-cal-past-weeks)').getAttribute('aria-label') !== beforeHover) failures.push('zoom selection navigated the heatmap');
      if (!root.querySelector('.af-cal-hover').hidden) failures.push('zoom selection selected a heatmap day');
      return failures;
    });
    out.errors.push(...zoomChecks);
    if (!checks.length && !zoomChecks.length) out.states['5000 trees: deep canopy and oldest zoomed tree'] = [{ name: 'deep forest', off: '' }];
  }
} catch (e) {
  out.errors.push(String(e));
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify(out));

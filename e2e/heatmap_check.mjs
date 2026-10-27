// node e2e/heatmap_check.mjs <heatmap.html> <chrome>: e2e/heatmap_check.py's look at the heatmap's
// hover layers, in headless Chrome. Prints JSON: { states: { state: [{ name, off }] }, errors },
// `off` "" where a year's layer lies on its weeks, else how far it is.
// (text is read without the U+2066-2069 isolates a right-to-left page puts round its values: web/i18n.js)
import puppeteer from 'puppeteer-core';

const [html, chrome, forest, deep, forestRtl] = process.argv.slice(2);
const wait = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu'] });
const out = { states: {}, errors: [] };
try {
  const p = await browser.newPage();
  await p.setViewport({ width: 900, height: 700, deviceScaleFactor: 2 });
  p.on('pageerror', e => out.errors.push(e.message));
  p.on('console', m => { if (m.type() === 'error') out.errors.push(`console: ${m.text()}`); });
  await p.goto('file://' + html);
  await p.waitForSelector('.af-cal-canvas', { timeout: 10000 });
  await wait(400);
  const layoutChecks = await p.evaluate(() => {
    const root = document.getElementById('p'), box = root.querySelector('.af-cal'), failures = [];
    const css = getComputedStyle(root), contentWidth = root.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
    if (Math.abs(box.getBoundingClientRect().width / contentWidth - 0.85) > 0.01) failures.push('heatmap is not 85% of the forest over it (Follow the forest)');
    if (!box.querySelector('.af-cal-current')?.textContent.replace(/[\u2066-\u2069]/g, '').includes('days')) failures.push('current streak has no day-count label');
    box.querySelector('[data-view="timeline"]').click();
    // (as many months as its width holds at its days' size, calendar.js DAY_K: labels for all but a month cut short at an end)
    const months = Math.max(3, Math.min(24, Math.round(10 * box.getBoundingClientRect().width / (541 * 1.25)))), shown = box.querySelectorAll('.af-cal-months span[data-m]').length;
    if (Math.abs(shown - months) > 1) failures.push(`Timeline showed ${shown} months, not the ${months} its width holds`);
    box.querySelector('[data-view="by_year"]').click();
    const modes = [...box.querySelectorAll('.af-cal-shade [data-by]')].map(b => b.dataset.by);
    if (modes.join(',') !== 'reviews,time,median') failures.push(`unexpected heatmap modes: ${modes}`);
    for (const mode of ['median']) {
      const button = box.querySelector(`[data-by="${mode}"]`);
      if (!button || button.hidden) { failures.push(`${mode} answer time unavailable`); continue; }
      button.click();
      if (!button.classList.contains('af-on')) failures.push(`${mode} answer time did not activate`);
      if (!box.querySelector('.af-cal-key').textContent.replace(/[\u2066-\u2069]/g, '').includes('Slow')) failures.push(`${mode} answer time has no speed legend`);
    }
    box.querySelector('[data-by="reviews"]').click();
    return failures;
  });
  out.errors.push(...layoutChecks);
  // each row's weeks and its layer: the one in view's (in the grid), and each of Streak view's earlier ones
  const look = () => p.evaluate(() => {
    const pairs = [...document.querySelectorAll('.af-cal-canvas')].map(cv => {
      const above = cv.parentElement.querySelector(':scope > .af-cal-above:not(.af-cal-spot)');
      const name = cv.classList.contains('af-cal-past-weeks') ? `the row from ${cv.getAttribute('aria-label').match(/, (\w{3} \d{4}) to/)[1]}` : 'the weeks in view';
      if (!above) return { name, off: 'missing' };
      const a = cv.getBoundingClientRect(), b = above.getBoundingClientRect();
      const d = [b.left - a.left, b.top - a.top, b.width - a.width, b.height - a.height].map(v => Math.round(v));
      return { name, off: d.some(v => Math.abs(v) > 1) ? `${d[0]}, ${d[1]} px (size ${d[2]}, ${d[3]})` : '' };
    });
    return pairs;
  });
  out.states['by year'] = await look();
  await (await p.$('[data-view="streak"]')).click(); await wait(500);
  out.states['streak view'] = await look();
  if (out.states['streak view'].length < 2) out.errors.push(`Streak view showed ${out.states['streak view'].length} row(s), not the streak's rows`);
  await (await p.$('[data-view="by_year"]')).click(); await wait(500);
  out.states['by year again'] = await look();
  // the same forest and heatmap, and again right to left (heatmap_check.py: English words, the
  // panel's direction rtl): the days drawn mirrored, and the pointer and the keyboard on the day drawn
  for (const [page, rtl] of [[forest, false], [forestRtl, true]]) {
    if (!page) continue;
    const said = rtl ? ' (right to left)' : '';
    await p.goto('file://' + page);
    await p.waitForSelector('.af-cal-canvas');
    if (rtl) out.errors.push(...(await p.evaluate(() => {
      const root = document.getElementById('p'), failures = [], fail = m => failures.push(m);
      if (!root.classList.contains('af-rtl') || getComputedStyle(root).direction !== 'rtl') fail('the panel does not read right to left');
      const weeks = root.querySelector('.af-cal-canvas'), ring = root.querySelector('.af-cal-hover'), tipEl = root.querySelector('.af-cal-tip');
      ring.style.transition = 'none';
      const key = k => weeks.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
      const at = () => { const b = ring.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; };
      weeks.focus(); key('Home');
      const today = at(), todayTip = tipEl.textContent.replace(/[\u2066-\u2069]/g, '');
      for (let i = 0; i < 20; i++) key('ArrowUp');
      const before = at();
      if (!(today[0] < before[0])) fail(`today is not left of the days before it: ${today[0]} vs ${before[0]}`);
      // (← moves the way the screen shows: towards today, a week later)
      key('ArrowLeft');
      const left = at();
      if (!(left[0] < before[0])) fail('← did not step a week to the left');
      key('ArrowRight'); key('ArrowRight');
      if (!(at()[0] > before[0])) fail('→ did not step a week to the right, into the earlier days');
      key('Escape'); weeks.blur();
      // the pointer on the day drawn there: its tooltip is the keyboard's
      const move = ([x, y]) => weeks.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
      weeks.parentElement.dispatchEvent(new MouseEvent('mouseleave'));
      move(today);
      if (tipEl.textContent.replace(/[\u2066-\u2069]/g, '') !== todayTip) fail(`the pointer on today's tile told another day: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      // (and today's frame is drawn there: the canvas's pixel under the ring's edge is the frame's)
      const r = weeks.getBoundingClientRect(), g = weeks.getContext('2d'), k = weeks.width / r.width;
      const hb = ring.getBoundingClientRect();
      const px = g.getImageData(Math.floor((hb.left + 1 - r.left) * k), Math.floor((hb.top + hb.height / 2 - r.top) * k), 1, 1).data;
      if (!px[3]) fail('nothing drawn under the ring of today');
      // the months: the weeks' first month at the right end, today's month to the left of it
      const labels = [...root.querySelectorAll('.af-cal-months span:not([hidden])')];
      if (labels.length > 1 && !(labels[0].getBoundingClientRect().left > labels[labels.length - 1].getBoundingClientRect().left)) fail('the months run left to right');
      // the weekdays on the right, the arrows at the left end
      const days = root.querySelector('.af-cal-days span'), box = root.querySelector('.af-cal').getBoundingClientRect();
      if (days && !(days.getBoundingClientRect().left >= box.right - 2)) fail('the weekdays are not right of the weeks');
      const acts = root.querySelector('.af-cal-grid > .af-cal-acts').getBoundingClientRect();
      if (!(acts.left - box.left < 4)) fail('the arrows are not at the left end of the months row');
      const earlier = root.querySelector('[data-go="-1"]').getBoundingClientRect(), later = root.querySelector('[data-go="1"]').getBoundingClientRect();
      if (!(earlier.left > later.left)) fail('Earlier is not right of Later');
      weeks.parentElement.dispatchEvent(new MouseEvent('mouseleave'));  // (the forest's checks start from rest)
      return failures;
    })).map(m => m + said));
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
      if (!root.querySelector('.af-cal-tip').textContent.replace(/[\u2066-\u2069]/g, '').includes('new cards')) failures.push('day tooltip omitted its planted cards');
      // Return to this exact day through the mouse handler, not the public link callback.
      const dayRing = ring.getBoundingClientRect(), dayX = dayRing.left + dayRing.width / 2, dayY = dayRing.top + dayRing.height / 2;
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      if (snapshot() !== before) failures.push('Escape did not clear the linked tree');
      weeks.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: dayX, clientY: dayY }));
      if (snapshot() === before) failures.push('mouse day did not highlight its tree');
      if (!root.querySelector('.af-cal-tip').textContent.replace(/[\u2066-\u2069]/g, '').includes('Sep 10, 2026') && tree.it.date === '2026-09-10') failures.push('September 10 pointer selected the wrong date');
      // a stretch picked with Shift and two clicks: its summary, the rest of the heatmap dimmed, its
      // trees lit in the forest, a click inside it opening it, Esc letting it go; then days apart
      const dayAt = n => {
        weeks.focus();
        weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
        for (let i = 0; i < n; i++) weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }));
        const b = ring.getBoundingClientRect();
        return [b.left + b.width / 2, b.top + b.height / 2];
      };
      const first = dayAt(20), second = dayAt(5);
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      weeks.blur();
      const unpicked = snapshot(), tipEl = root.querySelector('.af-cal-tip');
      const click = ([x, y], shiftKey) => weeks.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: x, clientY: y, shiftKey, detail: 1 }));
      click(first, true); click(second, true);
      if (tipEl.hidden || !/ to /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || !/Studied/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) failures.push(`a stretch picked had no summary: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      if (!root.querySelector('.af-cal-spot')) failures.push('a stretch picked did not dim the other days');
      if (snapshot() === unpicked) failures.push("a stretch picked did not light its trees");
      weeks.parentElement.dispatchEvent(new MouseEvent('mouseleave'));  // (the heatmap's own: it does not bubble up from the weeks)
      if (!tipEl.hidden || !root.querySelector('.af-cal-spot')) failures.push('a stretch picked went, or kept its summary, when the pointer left');
      const sent = [], was = window.pycmd;
      window.pycmd = m => { sent.push(m); return false; };
      click(second, false);
      window.pycmd = was;
      if (!sent.some(m => /:days:-20_-5:/.test(m))) failures.push(`a click inside the stretch did not open it: ${sent}`);
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      if (root.querySelector('.af-cal-spot') || !tipEl.hidden) failures.push('Esc did not let the stretch go');
      if (snapshot() !== unpicked) failures.push('letting the stretch go did not restore the forest');
      // Cmd (Ctrl off a Mac) and a click drops a day from a stretch, and picks one apart from it
      const cmd = /Mac/.test(globalThis.navigator.platform) ? { metaKey: true } : { ctrlKey: true };
      const third = dayAt(12), apart = dayAt(2);
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      weeks.blur();
      click(first, true); click(second, true);
      const cmdClick = ([x, y]) => weeks.dispatchEvent(new MouseEvent('click', Object.assign({ bubbles: true, clientX: x, clientY: y, detail: 1 }, cmd)));
      cmdClick(third); cmdClick(apart);
      if (!/^16 days, /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) failures.push(`Cmd-clicks did not pick days apart: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      sent.length = 0;
      window.pycmd = m => { sent.push(m); return false; };
      click(second, false);
      window.pycmd = was;
      if (!sent.some(m => /:days:-20_-13,-11_-5,-2_-2:/.test(m))) failures.push(`days picked apart did not open as their runs: ${sent}`);
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      if (root.querySelector('.af-cal-spot')) failures.push('Esc did not let the days picked go');
      return failures;
    });
    out.errors.push(...checks.map(m => m + said));
    // picking, the rest of it: a plain click setting where Shift picks from, Shift+arrows, one day
    // read as that day, "to today", the count said once, the summary only while pointing, the dim
    // kept while picking (paged away, on every year shown) and on its weeks after paging and
    // redraws, a pick across two years, and what lets a pick go
    const picking = await p.evaluate(async () => {
      const root = document.getElementById('p'), failures = [], fail = m => failures.push(m);
      const weeks = () => root.querySelector('.af-cal-canvas:not(.af-cal-past-weeks)');
      const ring = root.querySelector('.af-cal-hover'), tipEl = root.querySelector('.af-cal-tip'), grid = weeks().parentElement;
      ring.style.transition = 'none';
      const key = (k, extra = {}) => weeks().dispatchEvent(new KeyboardEvent('keydown', Object.assign({ key: k, bubbles: true }, extra)));
      const esc = () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      const dayAt = n => {
        weeks().focus(); key('Home');
        for (let i = 0; i < n; i++) key('ArrowUp');
        const b = ring.getBoundingClientRect();
        return [b.left + b.width / 2, b.top + b.height / 2];
      };
      const done = () => { key('Escape'); weeks().blur(); grid.dispatchEvent(new MouseEvent('mouseleave')); };
      const cmd = /Mac/.test(globalThis.navigator.platform) ? { metaKey: true } : { ctrlKey: true };
      const click = ([x, y], mods = {}, on = weeks()) => on.dispatchEvent(new MouseEvent('click', Object.assign({ bubbles: true, clientX: x, clientY: y, detail: 1 }, mods)));
      const move = ([x, y], on = weeks()) => on.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
      const sentBy = f => { const sent = [], was = window.pycmd; window.pycmd = m => { sent.push(m); return false; }; f(); window.pycmd = was; return sent; };
      const spots = () => [...root.querySelectorAll('.af-cal-spot')].filter(s => s.style.visibility !== 'hidden');
      // (each dim layer lies on its year's weeks: same place, same size)
      const layersOn = what => {
        const cvs = [...root.querySelectorAll('.af-cal-canvas')].map(c => c.getBoundingClientRect());
        for (const s of spots()) {
          const r = s.getBoundingClientRect();
          if (!cvs.some(c => Math.abs(c.left - r.left) < 1.5 && Math.abs(c.top - r.top) < 1.5 && Math.abs(c.width - r.width) < 1.5 && Math.abs(c.height - r.height) < 1.5)) fail(`a dim layer left its weeks ${what}`);
        }
      };
      // (how dimmed the point is: the alpha of the layer over it, 0 for a day lit)
      const dimAt = ([x, y]) => {
        const s = spots().find(l => { const r = l.getBoundingClientRect(); return x >= r.left && x < r.right && y >= r.top && y < r.bottom; });
        if (!s) return -1;
        const r = s.getBoundingClientRect();
        return s.getContext('2d').getImageData(Math.floor((x - r.left) / r.width * s.width), Math.floor((y - r.top) / r.height * s.height), 1, 1).data[3];
      };
      const [d0, d3, d5, d9, d20] = [0, 3, 5, 9, 20].map(dayAt);
      done();
      // a plain click marks where Shift then picks from: one Shift-click picks the stretch
      const opened = sentBy(() => click(d20));
      if (!opened.some(m => /:day:-20:/.test(m))) fail(`a plain click did not open its day: ${opened}`);
      click(d5, { shiftKey: true });
      if (!/ to /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || dimAt(d9) !== 0 || dimAt(d3) <= 0) fail(`a Shift-click after a plain click did not pick the stretch: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      // the summary only while pointing; the dim stays at rest
      grid.dispatchEvent(new MouseEvent('mouseleave'));
      if (!tipEl.hidden || !spots().length) fail('at rest the summary stayed, or the dim went');
      move(d9);
      if (tipEl.hidden || !/^[A-Z][a-z]{2} \d+ to /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`pointing at a picked day did not give the summary: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      if (ring.hidden) fail('the day pointed at in a pick lost its ring');
      if (!/Studied all of these \d+ days/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`the stretch's summary: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      // paged away: still dimmed, no summary left behind; back: on its weeks
      grid.dispatchEvent(new MouseEvent('mouseleave'));
      root.querySelector('[data-go="-1"]').click();
      if (!spots().length) fail('paged away from the days picked, the heatmap was not dimmed');
      if (!tipEl.hidden) fail('paged away, the summary stayed behind');
      layersOn('after paging back');
      root.querySelector('[data-go="1"]').click();
      layersOn('after paging on');
      if (dimAt(d9) !== 0) fail('paged back, the days picked were not lit');
      // a redraw with the days focused (the keyboard paging) keeps the layer on its weeks
      weeks().focus(); key('PageUp'); key('PageDown');
      layersOn('after PageUp and PageDown');
      done(); esc();
      if (spots().length) fail('Esc did not let the stretch go');
      // Shift and the arrows pick from the keyboard
      weeks().focus(); key('Home'); key('ArrowUp'); key('ArrowUp');
      for (let i = 0; i < 4; i++) key('ArrowUp', { shiftKey: true });
      if (!/ to /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || dimAt(d5) !== 0) fail(`Shift+arrows did not pick: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      done(); esc();
      // one day selected reads as that day; a stretch up to today says so
      // (a day in the middle of its week, the median of seven days running: a day in the top or
      // bottom row has no days above or below it, the layer's clear past the weeks' edge, and the
      // walk below would run off into it. d9 alone failed on the Tuesdays and Wednesdays it was
      // a Sunday or a Monday, 2026-10-27)
      const mid = [9, 10, 11, 12, 13, 14, 15].map(dayAt).sort((a, b) => a[1] - b[1])[3];
      done();
      click(mid, cmd);
      // (its lit square sits evenly round its face: as much on the left as on the right, above as below)
      {
        const cv = weeks(), layerCv = spots()[0], r = cv.getBoundingClientRect();
        const px = Math.floor((mid[0] - r.left) / r.width * cv.width), py = Math.floor((mid[1] - r.top) / r.height * cv.height);
        const face = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height), lit = layerCv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
        const drawn = (x, y) => face.data[(y * cv.width + x) * 4 + 3] > 0, clear = (x, y) => lit.data[(y * cv.width + x) * 4 + 3] === 0;
        const reach = (test, x, y, dx, dy) => { while (test(x + dx, y + dy)) { x += dx; y += dy; } return dx ? x : y; };
        const f = [reach(drawn, px, py, -1, 0), reach(drawn, px, py, 1, 0), reach(drawn, px, py, 0, -1), reach(drawn, px, py, 0, 1)];
        const l = [reach(clear, px, py, -1, 0), reach(clear, px, py, 1, 0), reach(clear, px, py, 0, -1), reach(clear, px, py, 0, 1)];
        if (f[0] - l[0] !== l[1] - f[1] || f[2] - l[2] !== l[3] - f[3]) fail(`a selected day's lit square is lopsided round its face: face ${f}, lit ${l}`);
      }
      if (!/^[A-Z][a-z]+day, /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || /Studied every day/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`one day picked did not read as that day: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      esc();
      click(d3, { shiftKey: true }); click(d0, { shiftKey: true });
      if (!/to today/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`a stretch up to today did not say "to today": "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      esc();
      // days apart: their count said once
      click(d20, cmd); click(d9, cmd); click(d5, cmd);
      if (!/^3 days, /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || /of 3 days/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, '')) || !/of them/.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`days apart: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      // a click off the heatmap, a click on the forest, a right-click to mark: each lets them go
      document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      if (spots().length) fail('a click off the heatmap did not let the pick go');
      click(d20, cmd);
      root.querySelector('.af-canvas').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      if (spots().length) fail('a click on the forest did not let the pick go');
      click(d20, cmd); click(d9, cmd);
      const [mx, my] = d5;
      weeks().dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: mx, clientY: my }));
      if (spots().length) fail('a right-click to mark a day did not let the pick go');
      const name = root.querySelector('.af-cal-pin-name');
      if (name) name.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      // across two years: an earlier year's day and one in the year in view, both lit, a year with
      // none picked dimmed all over, the summary counting both, a click sending both
      root.querySelector('[data-view="streak"]').click();
      await new Promise(r => setTimeout(r, 300));
      if (!root.querySelector('.af-cal-past-weeks')) { fail('no earlier year to pick across'); return failures; }
      const [n0, n9] = [0, 9].map(dayAt);
      done();
      // (measured once the days' focus has scrolled the page: Streak view's years are taller than the window)
      const pastCv = [...root.querySelectorAll('.af-cal-past-weeks')].pop();  // (the year before the year in view: all of it after the first review)
      const pr = pastCv.getBoundingClientRect(), earlier = [pr.left + pr.width * 0.5, pr.top + pr.height * 0.55];
      click(n9, cmd);
      if (dimAt(earlier) <= 0) fail('an earlier year with none of the days picked was not dimmed');
      click(earlier, cmd, pastCv);
      if (dimAt(earlier) !== 0 || dimAt(n9) !== 0) fail('a pick across two years did not light both days');
      if (dimAt(n0) <= 0) fail('a day not picked was not dimmed');
      move(earlier, pastCv);
      if (!/^2 days, .*\d{4} to /.test(tipEl.textContent.replace(/[\u2066-\u2069]/g, ''))) fail(`the summary across two years did not count both: "${tipEl.textContent.replace(/[\u2066-\u2069]/g, '')}"`);
      layersOn('with the earlier years shown');
      const both = sentBy(() => click(earlier, {}, pastCv));
      const runs = both.map(m => (m.match(/:days:([^:]*):/) || [])[1]).find(Boolean) || '';
      if (runs.split(',').length !== 2 || !(+runs.split('_')[0] < -365)) fail(`a click on a picked day of an earlier year did not open both: ${both}`);
      // a Shift-click stretches across the years from the anchor
      click(n0, { shiftKey: true }, weeks());
      if (dimAt(n9) !== 0) fail('a Shift-click from an earlier year did not stretch into the year in view');
      esc();
      if (spots().length) fail('Esc did not let a pick across years go');
      root.querySelector('[data-view="by_year"]').click();
      return failures;
    });
    out.errors.push(...picking.map(m => m + said));
    if (!checks.length) out.states['linked hover in a still forest' + said] = [{ name: 'tree and day', off: '' }];
    if (rtl) out.states['by year, right to left'] = await look();
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

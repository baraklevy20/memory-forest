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
  p.on('console', m => { if (m.type() === 'error') out.errors.push(`console: ${m.text()}`); });
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
    const modes = [...box.querySelectorAll('.af-cal-shade [data-by]')].map(b => b.dataset.by);
    if (modes.join(',') !== 'reviews,time,median') failures.push(`unexpected heatmap modes: ${modes}`);
    for (const mode of ['median']) {
      const button = box.querySelector(`[data-by="${mode}"]`);
      if (!button || button.hidden) { failures.push(`${mode} answer time unavailable`); continue; }
      button.click();
      if (!button.classList.contains('af-on')) failures.push(`${mode} answer time did not activate`);
      if (!box.querySelector('.af-cal-key').textContent.includes('Slow')) failures.push(`${mode} answer time has no speed legend`);
    }
    box.querySelector('[data-by="reviews"]').click();
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
      if (tipEl.hidden || !/ to /.test(tipEl.textContent) || !/Studied/.test(tipEl.textContent)) failures.push(`a stretch picked had no summary: "${tipEl.textContent}"`);
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
      const cmd = /Mac/.test(navigator.platform) ? { metaKey: true } : { ctrlKey: true };
      const third = dayAt(12), apart = dayAt(2);
      weeks.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      weeks.blur();
      click(first, true); click(second, true);
      const cmdClick = ([x, y]) => weeks.dispatchEvent(new MouseEvent('click', Object.assign({ bubbles: true, clientX: x, clientY: y, detail: 1 }, cmd)));
      cmdClick(third); cmdClick(apart);
      if (!/^16 days, /.test(tipEl.textContent)) failures.push(`Cmd-clicks did not pick days apart: "${tipEl.textContent}"`);
      sent.length = 0;
      window.pycmd = m => { sent.push(m); return false; };
      click(second, false);
      window.pycmd = was;
      if (!sent.some(m => /:days:-20_-13,-11_-5,-2_-2:/.test(m))) failures.push(`days picked apart did not open as their runs: ${sent}`);
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      if (root.querySelector('.af-cal-spot')) failures.push('Esc did not let the days picked go');
      return failures;
    });
    out.errors.push(...checks);
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
      const cmd = /Mac/.test(navigator.platform) ? { metaKey: true } : { ctrlKey: true };
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
      if (!/ to /.test(tipEl.textContent) || dimAt(d9) !== 0 || dimAt(d3) <= 0) fail(`a Shift-click after a plain click did not pick the stretch: "${tipEl.textContent}"`);
      // the summary only while pointing; the dim stays at rest
      grid.dispatchEvent(new MouseEvent('mouseleave'));
      if (!tipEl.hidden || !spots().length) fail('at rest the summary stayed, or the dim went');
      move(d9);
      if (tipEl.hidden || !/^[A-Z][a-z]{2} \d+ to /.test(tipEl.textContent)) fail(`pointing at a picked day did not give the summary: "${tipEl.textContent}"`);
      if (ring.hidden) fail('the day pointed at in a pick lost its ring');
      if (!/Studied every day/.test(tipEl.textContent)) fail(`the stretch's summary: "${tipEl.textContent}"`);
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
      if (!/ to /.test(tipEl.textContent) || dimAt(d5) !== 0) fail(`Shift+arrows did not pick: "${tipEl.textContent}"`);
      done(); esc();
      // one day selected reads as that day; a stretch up to today says so
      click(d9, cmd);
      // (its lit square sits evenly round its face: as much on the left as on the right, above as below)
      {
        const cv = weeks(), layerCv = spots()[0], r = cv.getBoundingClientRect();
        const px = Math.floor((d9[0] - r.left) / r.width * cv.width), py = Math.floor((d9[1] - r.top) / r.height * cv.height);
        const face = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height), lit = layerCv.getContext('2d').getImageData(0, 0, cv.width, cv.height);
        const drawn = (x, y) => face.data[(y * cv.width + x) * 4 + 3] > 0, clear = (x, y) => lit.data[(y * cv.width + x) * 4 + 3] === 0;
        const reach = (test, x, y, dx, dy) => { while (test(x + dx, y + dy)) { x += dx; y += dy; } return dx ? x : y; };
        const f = [reach(drawn, px, py, -1, 0), reach(drawn, px, py, 1, 0), reach(drawn, px, py, 0, -1), reach(drawn, px, py, 0, 1)];
        const l = [reach(clear, px, py, -1, 0), reach(clear, px, py, 1, 0), reach(clear, px, py, 0, -1), reach(clear, px, py, 0, 1)];
        if (f[0] - l[0] !== l[1] - f[1] || f[2] - l[2] !== l[3] - f[3]) fail(`a selected day's lit square is lopsided round its face: face ${f}, lit ${l}`);
      }
      if (!/^[A-Z][a-z]+day, /.test(tipEl.textContent) || /Studied every day/.test(tipEl.textContent)) fail(`one day picked did not read as that day: "${tipEl.textContent}"`);
      esc();
      click(d3, { shiftKey: true }); click(d0, { shiftKey: true });
      if (!/to today/.test(tipEl.textContent)) fail(`a stretch up to today did not say "to today": "${tipEl.textContent}"`);
      esc();
      // days apart: their count said once
      click(d20, cmd); click(d9, cmd); click(d5, cmd);
      if (!/^3 days, /.test(tipEl.textContent) || /of 3 days/.test(tipEl.textContent) || !/of them/.test(tipEl.textContent)) fail(`days apart: "${tipEl.textContent}"`);
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
      const more = root.querySelector('.af-cal-more');
      if (!more) { fail('no earlier year to pick across'); return failures; }
      more.click();
      await new Promise(r => setTimeout(r, 300));
      const pastCv = [...root.querySelectorAll('.af-cal-past-weeks')].pop();  // (the year before the year in view: all of it after the first review)
      const pr = pastCv.getBoundingClientRect(), earlier = [pr.left + pr.width * 0.5, pr.top + pr.height * 0.55];
      const [n0, n9] = [0, 9].map(dayAt);
      done();
      click(n9, cmd);
      if (dimAt(earlier) <= 0) fail('an earlier year with none of the days picked was not dimmed');
      click(earlier, cmd, pastCv);
      if (dimAt(earlier) !== 0 || dimAt(n9) !== 0) fail('a pick across two years did not light both days');
      if (dimAt(n0) <= 0) fail('a day not picked was not dimmed');
      move(earlier, pastCv);
      if (!/^2 days, .*\d{4} to /.test(tipEl.textContent)) fail(`the summary across two years did not count both: "${tipEl.textContent}"`);
      layersOn('with the earlier years shown');
      const both = sentBy(() => click(earlier, {}, pastCv));
      const runs = both.map(m => (m.match(/:days:([^:]*):/) || [])[1]).find(Boolean) || '';
      if (runs.split(',').length !== 2 || !(+runs.split('_')[0] < -365)) fail(`a click on a picked day of an earlier year did not open both: ${both}`);
      // a Shift-click stretches across the years from the anchor
      click(n0, { shiftKey: true }, weeks());
      if (dimAt(n9) !== 0) fail('a Shift-click from an earlier year did not stretch into the year in view');
      esc();
      if (spots().length) fail('Esc did not let a pick across years go');
      more.click();
      return failures;
    });
    out.errors.push(...picking);
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

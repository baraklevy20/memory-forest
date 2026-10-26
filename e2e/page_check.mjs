// node e2e/page_check.mjs <pages.json> <chrome>: e2e/page_check.py's checks, in one headless Chrome,
// one page at a time. Prints JSON: { checks: [{ name, failures, bug }], errors, seconds }. A check
// fails on what it looks for and on any console error or uncaught exception on its page, but those
// it says it causes (`allow`); one with a `bug` is a known bug, expected to fail until fixed.
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const [manifest, chrome] = process.argv.slice(2);
const { pages, sim, only } = JSON.parse(fs.readFileSync(manifest, 'utf8'));
const wait = ms => new Promise(r => setTimeout(r, ms));
const started = Date.now();
const DESK = { width: 900, height: 900, deviceScaleFactor: 1 };
const PHONE = { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true };

const checks = [];
const check = (name, fn, opts = {}) => checks.push(Object.assign({ name, fn }, opts));

/* ---------- what the checks share ---------- */
// (in the page) the heatmap's parts, the tooltip's lines, and where a day's tile is on the screen
const HELPERS = () => {
  const box = () => document.querySelector('.af-cal');
  const weeks = () => document.querySelector('.af-cal-canvas:not(.af-cal-past-weeks)');
  // (the ring round a day eases to it: here it is there at once, so where it is can be read off)
  const ring = document.querySelector('.af-cal-hover');
  if (ring) ring.style.transition = 'none';
  window.T = {
    box, weeks,
    label: () => weeks().getAttribute('aria-label'),
    tip: () => {
      const t = document.querySelector('.af-cal-tip');
      if (!t || t.hidden) return '';
      const d = document.createElement('div');
      d.innerHTML = t.innerHTML.replace(/<br\s*\/?>/g, '\n');
      return d.textContent.trim();
    },
    sent: () => { const s = window.__sent.slice(); window.__sent.length = 0; return s; },
    btn: go => box().querySelector(`[data-go="${go}"]`),
    // the middle of the day `o` days from today in By year's weeks or Timeline's, by the page's own
    // offsets: the cell (1 + col * 10, 3 + row * 10 + 1) of the canvas's low-res pixels
    ring: () => { const r = document.querySelector('.af-cal-hover'); if (r.hidden) return null; const b = r.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; },
    at: (cv, px, py) => { const r = cv.getBoundingClientRect(), k = r.width / cv.width; return [r.left + px * k, r.top + py * k]; },
  };
};
async function open(browser, name, { viewport = DESK, before } = {}) {
  const p = await browser.newPage();
  await p.setViewport(viewport);
  const errors = [];
  p.on('pageerror', e => errors.push(`uncaught: ${e.message}`));
  p.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  if (before) await p.evaluateOnNewDocument(before);
  await p.goto('file://' + pages[name]);
  p.errors = errors;
  return p;
}
const ready = p => p.waitForSelector('.af-cal-canvas', { timeout: 10000 }).then(() => p.evaluate(HELPERS));
// the keyboard on the days: the heatmap focused, on today (Home), then `n` days back (ArrowUp) or on
async function keyTo(p, n) {
  await p.evaluate(() => T.weeks().focus());
  await p.keyboard.press('Home');
  const key = n < 0 ? 'ArrowUp' : 'ArrowDown';
  for (let i = 0; i < Math.abs(n); i++) await p.keyboard.press(key);
  return p.evaluate(() => T.tip());
}
// (each of `want` in the text: a string in it, a pattern or a { test } it passes)
const has = (fails, text, want, what) => { if (!want.every(w => (typeof w.test === 'function' ? w.test(text) : text.includes(w)))) fails.push(`${what}: got ${JSON.stringify(text)}`); };
const eq = (fails, got, want, what) => { if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${what}: wanted ${JSON.stringify(want)}, got ${JSON.stringify(got)}`); };

/* ---------- the heatmap (the calendar alone, in Anki) ---------- */
check('heatmap: Timeline opens on ten months, this one most of the way along', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  has(f, await p.evaluate(() => T.label()), [/^Study heatmap, Mar 2026 to Dec 2026: \d+ days studied, a 43-day streak$/], 'its description');
  eq(f, await p.evaluate(() => [...T.box().querySelectorAll('.af-cal-months span')].filter(s => !s.hidden).map(s => s.textContent)),
    ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 'the months');
  eq(f, await p.evaluate(() => [T.btn(-1).disabled, T.btn(1).disabled, T.btn(0).disabled, T.btn(0).textContent]), [false, false, true, '»'], '‹ › » on today\'s page');
  has(f, await p.evaluate(() => T.box().querySelector('.af-cal-current').textContent), ['43 days'], 'the current streak\'s note');
  eq(f, await p.evaluate(() => [...T.box().querySelectorAll('.af-cal-days span')].map(s => s.textContent)), ['Tue', 'Thu', 'Sat'], 'the weekdays (weeks from Monday)');
  return [p, f];
});

check('heatmap: ‹ › » page Timeline ten months at a time, as far as the history and the days ahead go', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await p.evaluate(() => T.btn(-1).click());
  has(f, await p.evaluate(() => T.label()), ['May 2025 to Feb 2026'], 'one page back');
  has(f, await p.evaluate(() => T.label()), [{ test: s => !s.includes('streak') }], 'a page without today names no streak');
  eq(f, await p.evaluate(() => [T.btn(0).disabled, T.btn(0).textContent]), [false, '»'], '» back to today');
  await p.evaluate(() => T.btn(0).click());
  has(f, await p.evaluate(() => T.label()), ['Mar 2026 to Dec 2026'], '» back');
  await p.evaluate(() => T.btn(1).click());
  has(f, await p.evaluate(() => T.label()), ['Jan 2027 to Oct 2027'], 'one page on');
  eq(f, await p.evaluate(() => [T.btn(1).disabled, T.btn(0).textContent]), [true, '«'], 'the end of the days ahead, and « pointing back');
  await p.evaluate(() => T.btn(0).click());
  let n = 0;
  while (n < 10 && !(await p.evaluate(() => T.btn(-1).disabled))) { await p.evaluate(() => T.btn(-1).click()); n++; }
  eq(f, n, 4, 'pages back to the first review (Mar 2023)');
  has(f, await p.evaluate(() => T.label()), ['Nov 2022 to Aug 2023'], 'the first page');
  // a trackpad's sideways swipe turns one page
  await p.evaluate(() => T.btn(0).click());
  await p.evaluate(() => T.weeks().dispatchEvent(new WheelEvent('wheel', { deltaX: 60, bubbles: true, cancelable: true })));
  has(f, await p.evaluate(() => T.label()), ['Jan 2027 to Oct 2027'], 'a swipe on');
  return [p, f];
});

check('heatmap: a narrow panel shows fewer months, today still in view', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await p.evaluate(() => { document.getElementById('p').style.width = '300px'; });
  await wait(400);
  const n = await p.evaluate(() => [...T.box().querySelectorAll('.af-cal-months span')].length);
  if (!(n >= 3 && n < 10)) f.push(`${n} months on a narrow panel`);
  has(f, await p.evaluate(() => T.label()), [/to Oct 2026: \d+ days studied, a 43-day streak$/], 'its description');
  await p.evaluate(() => { document.getElementById('p').style.width = ''; });
  await wait(400);
  has(f, await p.evaluate(() => T.label()), ['Mar 2026 to Dec 2026'], 'wide again');
  return [p, f];
});

check('heatmap: By year pages by year, and its switch tells Anki', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await p.evaluate(() => T.box().querySelector('[data-view="by_year"]').click());
  eq(f, await p.evaluate(() => T.sent()), ['forest:view:by_year'], 'the view sent');
  has(f, await p.evaluate(() => T.label()), ['Jan 2026 to Dec 2026'], 'this year');
  eq(f, await p.evaluate(() => T.box().querySelector('[data-view="by_year"]').getAttribute('aria-checked')), 'true', 'By year checked');
  await p.evaluate(() => T.btn(-1).click());
  has(f, await p.evaluate(() => T.label()), ['Jan 2025 to Dec 2025'], 'last year');
  await p.evaluate(() => { T.btn(0).click(); T.btn(1).click(); });
  has(f, await p.evaluate(() => T.label()), ['Jan 2027 to Dec 2027'], 'next year');
  eq(f, await p.evaluate(() => [T.btn(1).disabled, T.btn(0).textContent]), [true, '«'], 'no further than the days ahead');
  // ← → on the view's radio buttons switch it, as radio buttons do
  await p.focus('.af-cal-view [data-view="by_year"]');
  await p.keyboard.press('ArrowLeft');
  eq(f, await p.evaluate(() => [T.sent(), document.activeElement.dataset.view]), [['forest:view:timeline'], 'timeline'], 'the arrow key\'s view');
  has(f, await p.evaluate(() => T.label()), ['Mar 2026 to Dec 2026'], 'back on Timeline, on today');
  return [p, f];
});

check('heatmap: a button gone out of use under the keyboard hands its focus on', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await p.focus('[data-go="1"]');
  await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => [T.btn(1).disabled, document.activeElement && document.activeElement.dataset.go]), [true, '-1'], '› at the end: the focus on ‹');
  return [p, f];
});

check('heatmap: a day\'s tooltip: its date, its reviews, its place in the streak', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  let tip = await keyTo(p, 0);
  has(f, tip, [/^Today, Sunday, Oct 18\n\d+ reviews so far in .+, 12 still due\nDay 43 of your streak$/], 'today');
  tip = await keyTo(p, -1);
  has(f, tip, [/^Yesterday, Saturday, Oct 17\n\d+ reviews in .+\nDay 42 of your 43-day streak$/], 'yesterday');
  has(f, await keyTo(p, 1), [/^Tomorrow, Monday, Oct 19\n198 cards due$/], 'tomorrow');
  has(f, await keyTo(p, -10), ['Thursday, Oct 8, 2026', 'Nothing was due', 'Doesn\'t break your 43-day streak'], 'a day with nothing due inside the streak');
  has(f, await keyTo(p, -20), ['Monday, Sep 28, 2026', 'Not studied: a day off', 'Doesn\'t break your 43-day streak'], 'a day off');
  has(f, await keyTo(p, -45), [/Not studied$/], 'a missed day');
  has(f, await keyTo(p, -76), ['Aug 3, 2026', 'Not studied: a pond in your forest'], 'a pond\'s day');
  has(f, await keyTo(p, -30), ['A deer came: you kept a 30-day streak'], 'an animal\'s day');
  has(f, await keyTo(p, -5), ['All 4 of its cards have since been deleted'], 'a day whose cards are gone');
  has(f, await keyTo(p, -3), ['2 of its 5 cards have since been deleted'], 'a day with some cards gone');
  has(f, await keyTo(p, 7), ['Sunday, Oct 25, 2026', 'Final exam in 7 days'], 'a marked day ahead');
  has(f, await keyTo(p, -6), ['Star'], 'a mark with no name: its icon\'s');
  has(f, await keyTo(p, 18), ['Beat your longest streak (60 days) on this day'], 'the goal\'s day');
  // Esc puts it away
  await p.keyboard.press('Escape');
  eq(f, await p.evaluate(() => T.tip()), '', 'after Esc');
  return [p, f];
});

check('heatmap: Enter and a click open a day\'s cards in the browser, but not a missed day or one whose cards are gone', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await keyTo(p, -1); await p.keyboard.press('Enter');
  await keyTo(p, 3); await p.keyboard.press('Enter');
  await keyTo(p, -45); await p.keyboard.press('Enter');
  await keyTo(p, -5); await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => T.sent()), ['forest:day:-1::reviews', 'forest:day:3::reviews'], 'Enter on yesterday, on a day ahead, on a missed day, on a day with its cards gone');
  await keyTo(p, -2);
  const at = await p.evaluate(() => T.ring());
  await p.keyboard.press('Escape');
  await p.mouse.move(at[0], at[1]);
  eq(f, await p.evaluate(() => T.box().querySelector('.af-cal-grid').classList.contains('af-click')), true, 'the pointer over a day that opens');
  await p.mouse.click(at[0], at[1]);
  eq(f, await p.evaluate(() => T.sent()), ['forest:day:-2::reviews'], 'a click on the day before yesterday');
  // shaded by time, the day opens sorted by it
  await p.evaluate(() => T.box().querySelector('[data-by="time"]').click());
  await p.evaluate(() => T.sent());
  await keyTo(p, -1); await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => T.sent()), ['forest:day:-1::time'], 'Enter, shaded by time');
  return [p, f];
});

check('heatmap: today before you study is soil, and its click opens the cards due', async b => {
  const p = await open(b, 'fresh'); await ready(p); const f = [];
  has(f, await keyTo(p, 0), [/^Today, Sunday, Oct 18\nNot studied yet, 40 cards due$/], 'today\'s tooltip');
  await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => T.sent()), ['forest:day:0::due'], 'Enter on today');
  has(f, await keyTo(p, -1), ['Day 42 of your streak'], 'the streak lives on through today');
  return [p, f];
});

check('heatmap: the first tooltip waits a moment for the pointer; the next comes at once', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const [x, y] = await p.evaluate(() => T.at(T.weeks(), 1 + 30 * 10 + 4.5, 3 + 3 * 10 + 5.5));
  await p.mouse.move(x, y);
  eq(f, await p.evaluate(() => getComputedStyle(document.querySelector('.af-cal-tip')).visibility), 'hidden', 'straight away');
  await wait(300);
  eq(f, await p.evaluate(() => getComputedStyle(document.querySelector('.af-cal-tip')).visibility), 'visible', 'a moment later');
  await p.mouse.move(x + 13, y);
  eq(f, await p.evaluate(() => getComputedStyle(document.querySelector('.af-cal-tip')).visibility), 'visible', 'the next day');
  await p.mouse.move(5, 5);
  eq(f, await p.evaluate(() => [T.tip(), document.querySelector('.af-cal-hover').hidden]), ['', true], 'the pointer gone');
  return [p, f];
});

check('heatmap: Reviews, Time and Pace: each tells Anki, changes the key, the tooltips and the shades', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const look = () => p.evaluate(() => [T.weeks().toDataURL(), T.box().querySelector('.af-cal-key').textContent]);
  const [reviews, rKey] = await look();
  eq(f, rKey, 'LessMore', 'Reviews\' key');
  await p.evaluate(() => T.box().querySelector('[data-by="time"]').click());
  const [time, tKey] = await look();
  eq(f, await p.evaluate(() => T.sent()), ['forest:shade:time'], 'Time sent');
  eq(f, tKey, 'LessMore', 'Time\'s key');
  if (time === reviews) f.push('Time painted the days as Reviews did');
  has(f, await keyTo(p, -1), [/^Yesterday, Saturday, Oct 17\n(\d+ min|\d+ hr( \d+ min)?|A minute), \d+ reviews\n/], 'a day\'s tooltip by time');
  await p.evaluate(() => T.box().querySelector('[data-by="median"]').click());
  const [pace, pKey] = await look();
  eq(f, await p.evaluate(() => T.sent()), ['forest:shade:median'], 'Pace sent');
  eq(f, pKey, 'SlowFast', 'Pace\'s key');
  if (pace === time || pace === reviews) f.push('Pace painted the days as another did');
  has(f, await keyTo(p, -1), [/^Yesterday, Saturday, Oct 17\nMedian \d\.\d s per answer, \d+ reviews\n/], 'a day\'s tooltip by pace');
  // ← → on the radio buttons, wrapping round
  await p.focus('.af-cal-shade [data-by="median"]');
  await p.keyboard.press('ArrowRight');
  eq(f, await p.evaluate(() => [T.sent(), document.activeElement.dataset.by]), [['forest:shade:reviews'], 'reviews'], 'the arrow key from Pace');
  eq(f, (await look())[0], reviews, 'back on Reviews, the days as they were');
  return [p, f];
});

check('heatmap: a shade in the key, pointed at, gives its numbers and lights its days', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const swatch = async i => {
    const r = await p.evaluate(i => { const s = T.box().querySelectorAll('.af-cal-key .af-cal-swatch')[i].getBoundingClientRect(); return [s.left + s.width / 2, s.top + s.height / 2]; }, i);
    await p.mouse.move(r[0], r[1]);
    return p.evaluate(() => [document.querySelector('.af-cal-tip').textContent, !!document.querySelector('.af-cal-spot')]);
  };
  const [low, lit] = await swatch(0);
  has(f, low, [/^Under \d+ reviews$/], 'the faintest');
  if (!lit) f.push('the faintest shade\'s days are not lit');
  has(f, (await swatch(3))[0], [/^\d+\+ reviews$/], 'the busiest');
  has(f, (await swatch(1))[0], [/^\d+–\d+ reviews$|^\d+ reviews$/], 'the second');
  await p.mouse.move(5, 5);
  eq(f, await p.evaluate(() => !!document.querySelector('.af-cal-spot')), false, 'the days lit after the pointer left');
  await p.evaluate(() => T.box().querySelector('[data-by="time"]').click());
  has(f, (await swatch(3))[0], [/^\d+\+ min$|^.+\+$/], 'the busiest, by time');
  await p.mouse.move(5, 5);
  await p.evaluate(() => T.box().querySelector('[data-by="median"]').click());
  has(f, (await swatch(3))[0], [/^Under \d\.\d s per answer$/], 'Pace\'s strongest: the fastest');
  has(f, (await swatch(0))[0], [/^\d\.\d\+ s per answer$/], 'Pace\'s faintest: the slowest');
  return [p, f];
});

check('heatmap: a month\'s label tells its days studied, or the cards due ahead', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const month = async m => { await p.hover(`.af-cal-months span[data-m="${m}"]`); return p.evaluate(() => T.tip()); };
  has(f, await month(8), [/^September 2026\nStudied \d+ of 30 days \(\d+%\)\n\d[\d,]* reviews in .+\nAbout \d+ reviews and .+ per day studied$/], 'September');
  has(f, await month(9), ['October 2026', /so far/, /cards due later this month/, 'Oct 25: Final exam', 'Oct 12: Star'], 'this month');
  has(f, await month(11), [/^December 2026\n[\d,]+ cards due$/], 'a month ahead');
  return [p, f];
});

check('heatmap: a streak\'s bracket, pointed at, gives its days; a trophy its place', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const at = await p.evaluate(() => { const n = T.box().querySelector('.af-cal-current').getBoundingClientRect(), cv = T.weeks(), r = cv.getBoundingClientRect(); return [n.left + n.width / 2, r.top + 76.5 * r.width / cv.width]; });
  await p.mouse.move(at[0], at[1]);
  has(f, await p.evaluate(() => T.tip()), [/^Sep 4, 2026 to today\nYour 43-day streak$/], 'the current streak\'s bracket');
  // the 60-day streak of 2025, its last day Sep 13: By year 2025, its trophy under that day
  await p.evaluate(() => { T.box().querySelector('[data-view="by_year"]').click(); T.btn(-1).click(); });
  const trophy = await p.evaluate(() => {
    const jan1 = Date.UTC(2025, 0, 1), day = Date.UTC(2025, 8, 13), lead = (new Date(jan1).getUTCDay() + 6) % 7;
    const col = Math.floor(((day - jan1) / 86400000 + lead) / 7);
    return T.at(T.weeks(), 1 + col * 10 + 4.5, 3 + 70 + 3 + 3 + 4);
  });
  await p.mouse.move(trophy[0], trophy[1]);
  has(f, await p.evaluate(() => T.tip()), [/^Saturday, Sep 13, 2025\nYour longest streak: 60 days$/], 'the trophy');
  has(f, await p.evaluate(() => T.label()), [/^Study heatmap, Jan 2025 to Dec 2025: \d+ days studied$/], 'last year\'s description, no streak');
  return [p, f];
});

check('heatmap: a right-click marks a day; Enter keeps it, Esc puts it back, × removes it', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await keyTo(p, -8);
  const at = await p.evaluate(() => T.ring());
  await p.keyboard.press('Escape');
  await p.mouse.click(at[0], at[1], { button: 'right' });
  eq(f, await p.evaluate(() => [document.querySelector('.af-cal-pin').hidden, document.activeElement.className, T.sent()]),
    [false, 'af-cal-pin-name', ['forest:typing:1']], 'the editor open on its name');
  eq(f, await p.evaluate(() => [...document.querySelectorAll('.af-cal-pin-icon')].map(i => i.getAttribute('aria-checked'))),
    ['true', 'false', 'false', 'false', 'false', 'false', 'false', 'false'], 'a pin, to start with');
  await p.keyboard.type('  Mock   quiz ');
  await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => [document.querySelector('.af-cal-pin').hidden, T.sent()]), [true, ['forest:typing:0', 'forest:mark:2026-10-10:pin:Mock quiz']], 'kept, its name tidied');
  has(f, await keyTo(p, -8), ['Saturday, Oct 10, 2026', 'Mock quiz'], 'the day\'s tooltip');
  // again: another icon, then Esc
  await p.keyboard.press('Escape');
  await p.mouse.click(at[0], at[1], { button: 'right' });
  await p.evaluate(() => document.querySelector('.af-cal-pin-icon[data-icon="trip"]').click());
  await p.keyboard.press('Escape');
  eq(f, await p.evaluate(() => T.sent()), ['forest:typing:1', 'forest:typing:0'], 'Esc sends no mark');
  has(f, await keyTo(p, -8), ['Mock quiz'], 'Esc kept the mark as it was');
  // the icons by the keyboard, and × to take it away
  await p.keyboard.press('Escape');
  await p.mouse.click(at[0], at[1], { button: 'right' });
  await p.focus('.af-cal-pin-icon[data-icon="pin"]');
  await p.keyboard.press('ArrowRight');
  eq(f, await p.evaluate(() => document.querySelector('.af-cal-pin-icon[aria-checked="true"]').dataset.icon), 'exam', '→ on the icons');
  await p.evaluate(() => document.querySelector('.af-cal-pin-del').click());
  eq(f, await p.evaluate(() => T.sent()), ['forest:typing:1', 'forest:typing:0', 'forest:unmark:2026-10-10'], '× removes it');
  const tip = await keyTo(p, -8);
  if (/Mock quiz/.test(tip)) f.push(`the mark stayed after ×: ${tip}`);
  return [p, f];
});

check('heatmap: Streak view opens on the streak, and pages back and on through time as many rows at a time', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  await p.evaluate(() => T.box().querySelector('[data-view="streak"]').click());
  eq(f, await p.evaluate(() => T.sent()), ['forest:view:streak'], 'the view sent');
  // (the stretch shown: its rows' first and last months, read off each row's weeks, oldest first)
  const frame = () => p.evaluate(() => [...document.querySelectorAll('.af-cal-past-weeks'), T.weeks()].map(c => c.getAttribute('aria-label').match(/, (\w{3} \d{4}) to (\w{3} \d{4})/).slice(1)));
  const now = await frame();
  eq(f, now.length, 1, 'the 43-day streak, in one row');
  eq(f, await p.evaluate(() => [T.btn(1).disabled, T.btn(0).disabled, T.btn(-1).disabled]), [false, true, false], 'on into the days ahead, back in time');
  // › into the days ahead, « (or ‹) back to the streak
  await p.evaluate(() => T.btn(1).click());
  const later = await frame();
  if (!(Date.parse(`1 ${later[0][0]}`) > Date.parse(`1 ${now[0][0]}`))) f.push(`› did not page on: ${JSON.stringify(later)}`);
  eq(f, await p.evaluate(() => [T.btn(0).textContent, T.btn(0).disabled]), ['«', false], '« back from the days ahead');
  await p.evaluate(() => T.btn(-1).click());
  eq(f, await frame(), now, '‹ back to the streak');
  const at = m => Date.parse(`1 ${m}`);
  const seen = [now[0][0]];
  for (let i = 0; i < 10 && !(await p.evaluate(() => T.btn(-1).disabled)); i++) {
    await p.evaluate(() => T.btn(-1).click());
    seen.push((await frame())[0][0]);
  }
  // (a row a page: each a year and a bit before the last)
  if (seen.length < 3 || seen.some((m, i) => i && !(at(seen[i - 1]) - at(m) > 300 * 86400000 && at(seen[i - 1]) - at(m) < 400 * 86400000))) f.push(`pages not a row each: ${JSON.stringify(seen)}`);
  has(f, seen[seen.length - 1] || '', [/^\w{3} 202[23]$/], 'back to the first review');
  await p.evaluate(() => T.btn(1).click());
  eq(f, (await frame())[0][0], seen[seen.length - 2], '› a page on');
  await p.evaluate(() => T.btn(0).click());
  eq(f, await frame(), now, '» back to the streak');
  await p.evaluate(() => T.box().querySelector('[data-view="by_year"]').click());
  eq(f, await p.evaluate(() => document.querySelectorAll('.af-cal-past-year').length), 0, 'By year: the year alone');
  return [p, f];
});

check('heatmap: Streak view\'s rows: as wide as each other, their months over them, their paint kept until what they show changes', async b => {
  const p = await open(b, 'long'); await ready(p); const f = [];
  const rows = () => p.evaluate(() => [...document.querySelectorAll('.af-cal-past-weeks'), T.weeks()].map(c => c.width));
  const w = await rows();
  if (w.length !== 3 || new Set(w).size !== 1) f.push(`rows: ${JSON.stringify(w)}`);
  has(f, await p.evaluate(() => [...document.querySelectorAll('.af-cal-past-head span:not([hidden])')].map(s => s.textContent).join(' ')), [/^\w{3} 20\d\d /], 'the top row\'s first month says its year');
  await p.evaluate(() => { window.__first = [...document.querySelectorAll('.af-cal-past-weeks')]; });
  const same = () => p.evaluate(() => { const now = [...document.querySelectorAll('.af-cal-past-weeks')]; return now.length === window.__first.length && now.every((c, i) => c === window.__first[i]); });
  const away = () => p.evaluate(() => { T.box().querySelector('[data-view="by_year"]').click(); T.box().querySelector('[data-view="streak"]').click(); });
  await away();
  eq(f, await same(), true, 'back on Streak: the same paint');
  await p.evaluate(() => { document.body.style.background = 'rgb(245, 245, 245)'; });
  await wait(700);
  await away();
  if (await same()) f.push('a new page colour kept the old paint');
  // an earlier row's day has its tooltip too, and is not marked from there
  const pt = await p.evaluate(() => { const cv = document.querySelector('.af-cal-past-weeks'); return T.at(cv, 1 + 45 * 10 + 4.5, 3 + 2 * 10 + 5.5); });  // (late in the row: its start is before the first review)
  await p.mouse.move(pt[0], pt[1]);
  await wait(250);
  has(f, await p.evaluate(() => T.tip()), [/\d{4}/, /reviews/], 'a day on the top row');
  await p.mouse.click(pt[0], pt[1], { button: 'right' });
  eq(f, await p.evaluate(() => document.querySelector('.af-cal-pin').hidden), true, 'no editor on an earlier row');
  return [p, f];
});

check('heatmap: Anki\'s theme switch paints the days again for the new page', async b => {
  const p = await open(b, 'calendar'); await ready(p); const f = [];
  const look = () => p.evaluate(() => [T.weeks().toDataURL(), T.box().classList.contains('af-cal-on-light')]);
  const [dark, onLight] = await look();
  eq(f, onLight, false, 'on Anki\'s dark page');
  await p.evaluate(() => { document.body.style.background = 'rgb(245, 245, 245)'; });
  await wait(700);
  const [light, nowLight] = await look();
  eq(f, nowLight, true, 'on a light page');
  if (light === dark) f.push('the days were not painted again for the light page');
  // (as the light page draws them from the start)
  const q = await open(b, 'light'); await ready(q);
  const fresh = await q.evaluate(() => T.weeks().toDataURL());
  if (fresh !== light) f.push('switched to light, the days differ from a page that opened light');
  f.push(...q.errors);
  await q.close();
  await p.evaluate(() => { document.body.style.background = ''; });
  await wait(700);
  eq(f, (await look())[0], dark, 'back on the dark page');
  return [p, f];
});

check('heatmap: weeks from Sunday where the setting says', async b => {
  const p = await open(b, 'sunday'); await ready(p); const f = [];
  eq(f, await p.evaluate(() => [...T.box().querySelectorAll('.af-cal-days span')].map(s => s.textContent)), ['Mon', 'Wed', 'Fri'], 'the weekdays');
  // today, a Sunday, on the weeks' top row
  await keyTo(p, 0);
  const ring = await p.evaluate(() => { const r = document.querySelector('.af-cal-hover').getBoundingClientRect(), cv = T.weeks().getBoundingClientRect(), k = cv.width / T.weeks().width; return Math.round((r.top - cv.top) / k); });
  eq(f, ring, 3, 'today\'s ring on the top row (3 pixels down)');
  return [p, f];
});

check('heatmap: By year\'s years all as wide as the widest (2012, a leap year from a Sunday: 54 weeks)', async b => {
  const p = await open(b, 'old'); await ready(p); const f = [];
  // (By year's years, paged back to the first review)
  const shown = () => p.evaluate(() => [T.label().match(/(\d{4}) to/)[1], T.weeks().width]);
  const widths = [await shown()];
  for (let i = 0; i < 20 && !(await p.evaluate(() => T.btn(-1).disabled)); i++) {
    await p.evaluate(() => T.btn(-1).click());
    widths.push(await shown());
  }
  if (!widths.some(w => w[0] === '2012')) f.push(`2012 not shown: ${widths.map(w => w[0])}`);
  const odd = widths.filter(w => w[1] !== 1 + 54 * 10);
  if (odd.length) f.push(`years not 54 weeks wide: ${JSON.stringify(odd)}`);
  return [p, f];
});

/* ---------- the forest and the heatmap under it ---------- */
const forestReady = p => p.waitForFunction(() => document.getElementById('p').afEnv && document.querySelector('.af-cal-canvas'), { timeout: 15000 }).then(() => p.evaluate(HELPERS));

check('forest: a tree\'s tooltip and its click open its cards; the pointer gone, so is the tooltip', async b => {
  const p = await open(b, 'forest'); await forestReady(p); const f = [];
  const at = await p.evaluate(() => {
    const env = document.getElementById('p').afEnv, cv = document.querySelector('.af-canvas'), r = cv.getBoundingClientRect(), s = r.width / env.W;
    const q = env.placed.filter(q => !q.it.pond).sort((a, b) => b.y - a.y)[0];
    return { x: r.left + q.x * s, y: r.top + (q.y - AnkiForest.STAGE_H[q.it.stage] * env.u * q.s / 2) * s, ago: q.it.ago };
  });
  await p.mouse.move(at.x, at.y);
  const tip = await p.evaluate(() => { const t = document.querySelector('.af-scene .af-tip'); return t.hidden ? '' : t.textContent; });
  has(f, tip, [/planted/, /cards?/, 'Click to see these cards'], 'the tree\'s tooltip');
  await p.mouse.click(at.x, at.y);
  eq(f, await p.evaluate(() => T.sent()), [`forest:browse:${at.ago}:`], 'its click');
  await p.mouse.move(2, 2);
  eq(f, await p.evaluate(() => document.querySelector('.af-scene .af-tip').hidden), true, 'the tooltip after the pointer left');
  return [p, f];
});

check('forest: the cog opens the settings; its dot and the note say what\'s new, and the note\'s buttons answer it', async b => {
  const p = await open(b, 'forest'); await forestReady(p); const f = [];
  eq(f, await p.evaluate(() => { const c = document.querySelector('.af-cog'); return [c.classList.contains('af-cog-new'), c.title]; }),
    [true, 'Change scenery and settings (new scenery)'], 'the cog\'s dot');
  eq(f, await p.evaluate(() => [...document.querySelectorAll('.af-news button')].map(x => x.textContent)), ['Show me', 'Got it'], 'the note');
  await p.focus('.af-cog');
  await p.keyboard.press('Enter');
  eq(f, await p.evaluate(() => [T.sent(), document.querySelector('.af-cog').classList.contains('af-cog-new')]), [['forest:settings'], false], 'the cog by the keyboard');
  await p.evaluate(() => document.querySelector('.af-news [data-news="seen"]').click());
  eq(f, await p.evaluate(() => [T.sent(), !!document.querySelector('.af-news')]), [['forest:news:seen:heatmap2'], false], 'Got it');
  return [p, f];
});

check('forest: the caption\'s tooltips; its streak, clicked, shows the heatmap\'s Streak view', async b => {
  const p = await open(b, 'forest'); await forestReady(p); const f = [];
  const items = await p.evaluate(() => [...document.querySelectorAll('.af-caption .af-info')].map(e => e.textContent));
  if (!items.includes('150 trees') || !items.some(t => /-day streak$/.test(t))) f.push(`the caption: ${JSON.stringify(items)}`);
  await p.hover('.af-caption .af-info');
  has(f, await p.evaluate(() => { const t = document.querySelector('.af-cap-tip'); return t.hidden ? '' : t.textContent; }), ['One tree for each day you learned new cards'], 'the trees\' tooltip');
  const streak = await p.evaluateHandle(() => [...document.querySelectorAll('.af-caption .af-info')].find(e => /-day streak$/.test(e.textContent)));
  await streak.hover();
  has(f, await p.evaluate(() => document.querySelector('.af-cap-tip').textContent), ['Days you studied, in a row', 'Click to see all of it'], 'the streak\'s tooltip');
  await streak.click();
  // (this streak began this year: no earlier years to show with it)
  eq(f, await p.evaluate(() => [T.sent(), T.box().querySelector('[data-view="streak"]').classList.contains('af-on'), T.box().classList.contains('af-cal-years-open')]),
    [['forest:view:streak'], true, false], 'Streak view');
  await p.mouse.move(2, 2);
  await streak.hover();
  has(f, await p.evaluate(() => document.querySelector('.af-cap-tip').textContent), [{ test: s => !s.includes('see all of it') }], 'no click hint once on it');
  // stepped back to an earlier streak, a click brings today's back
  await p.evaluate(() => T.btn(-1).click());
  await streak.click();
  eq(f, await p.evaluate(() => T.btn(0).disabled), true, 'back on today\'s streak');
  return [p, f];
});

check('forest: the journal comes down to the heatmap\'s footer', async b => {
  const p = await open(b, 'forest'); await forestReady(p); const f = [];
  eq(f, await p.evaluate(() => [!!document.querySelector('.af-cal-foot .af-journal'), !!document.querySelector('.af-caption .af-journal')]), [true, false], 'the journal\'s place');
  return [p, f];
});

// the frames drawn, counted where each frame draws its flyers (core.js frame)
const COUNT = () => {
  const AF = window.AnkiForest, draw = AF.drawFlyers;
  window.__frames = 0;
  AF.drawFlyers = function () { window.__frames++; if (window.__throwOnce) { window.__throwOnce = false; throw new Error('test: a frame that throws'); } return draw.apply(this, arguments); };
};
const framesIn = async (p, ms) => { const a = await p.evaluate(() => window.__frames); await wait(ms); return (await p.evaluate(() => window.__frames)) - a; };

check('loop: about 10 frames a second; none on a hidden page, back once it is seen', async b => {
  const p = await open(b, 'live'); await forestReady(p); const f = [];
  await p.evaluate(COUNT);
  const n = await framesIn(p, 1000);
  if (n < 4 || n > 17) f.push(`${n} frames in a second, a calm scene`);
  await p.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); });
  await wait(200);
  const hidden = await framesIn(p, 600);
  if (hidden > 0) f.push(`${hidden} frames drawn on a hidden page`);
  await p.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); });
  const back = await framesIn(p, 600);
  if (back < 2) f.push(`only ${back} frames once the page was seen again`);
  return [p, f];
});

check('loop: a frame that throws does not stop the forest', async b => {
  const p = await open(b, 'live'); await forestReady(p); const f = [];
  await p.evaluate(COUNT);
  await p.evaluate(() => { window.__throwOnce = true; });
  await wait(300);
  const n = await framesIn(p, 600);
  if (n < 2) f.push(`${n} frames after one threw`);
  return [p, f];
}, { allow: /a frame that throws/ });

// (core.js: after a build that threw part way, each tick's AF.busy(env) reads the half-built scene and
// throws in the tick's `finally`, before the next tick is set: the loop is gone for good, and the
// next good build draws one still frame)
check('loop: a rebuild that fails part way leaves the loop alive for the next one', async b => {
  const p = await open(b, 'live'); await forestReady(p); const f = [];
  await p.evaluate(COUNT);
  await p.evaluate(() => {
    const eng = window.AnkiForest.engines.pixel, prep = eng.prepare;
    eng.prepare = function () { if (window.__failBuild) { window.__failBuild = false; throw new Error('test: a build that fails'); } return prep.apply(this, arguments); };
    window.__failBuild = true;
    document.getElementById('p').style.width = '600px';  // (a new width: rebuilt, ResizeObserver)
  });
  await wait(700);
  await p.evaluate(() => { document.getElementById('p').style.width = ''; });
  await wait(700);
  const n = await framesIn(p, 600);
  if (n < 2) f.push(`${n} frames after a failed rebuild and a good one`);
  eq(f, await p.evaluate(() => document.getElementById('p').afEnv && !!document.getElementById('p').afEnv.g), true, 'the forest built again');
  return [p, f];
}, { allow: /a build that fails/ });

check('mount: a remount lets go of the forest before: one listener, one loop, one heatmap', async b => {
  const p = await open(b, 'live'); await forestReady(p); const f = [];
  await p.evaluate(COUNT);
  const one = await framesIn(p, 1000);
  await p.evaluate(() => { for (let i = 0; i < 4; i++) AnkiForest.mount(document.getElementById('p'), JSON.parse(JSON.stringify(window.TEST_DATA)), { now: true }); });
  await wait(500);
  const five = await framesIn(p, 1000);
  if (five > one * 1.6 + 2) f.push(`after 4 remounts ${five} frames a second, ${one} before: old loops still running`);
  eq(f, await p.evaluate(() => [window.__vis, document.querySelectorAll('.af-scene').length, document.querySelectorAll('.af-cal').length, document.querySelectorAll('.af-cal-canvas:not(.af-cal-past-weeks)').length]),
    [1, 1, 1, 1], 'visibility listeners, scenes, heatmaps, weeks');
  // the heatmap alone on the same root: the forest stops, its cog stays, its listener goes
  await p.evaluate(() => AnkiForest.mount(document.getElementById('p'), Object.assign(JSON.parse(JSON.stringify(window.TEST_DATA)), { showForest: false })));
  await wait(300);
  eq(f, await p.evaluate(() => [window.__vis, !!document.querySelector('.af-canvas'), !!document.querySelector('.af-cog'), !!document.querySelector('.af-cal-canvas')]),
    [0, false, true, true], 'the heatmap alone: listeners, forest, cog, heatmap');
  const after = await framesIn(p, 600);
  if (after > 0) f.push(`${after} frames from a forest no longer shown`);
  // AF.swap: the forest back in place; a root not on the page: false
  eq(f, await p.evaluate(() => [AnkiForest.swap('p', JSON.parse(JSON.stringify(window.TEST_DATA)), []), AnkiForest.swap('nowhere', {}, [])]), [true, false], 'swap\'s answers');
  await p.waitForFunction(() => document.querySelector('.af-canvas') && document.getElementById('p').afEnv, { timeout: 5000 }).catch(() => f.push('swap drew no forest'));
  return [p, f];
});

/* ---------- the phone card ---------- */
const phoneReady = p => p.waitForFunction(() => document.getElementById('memory-forest-phone').afEnv && document.querySelector('.af-cal-canvas'), { timeout: 15000 }).then(() => wait(800));

check('phone: "Synced ... ago", the heatmap swiped along with Today, and no switches, editor or keyboard stops', async b => {
  const p = await open(b, 'phone', { viewport: PHONE }); await phoneReady(p); const f = [];
  has(f, await p.evaluate(() => document.querySelector('.af-phone-note').textContent), [/^Synced (just now|\d+ minutes? ago)\.$/], 'the line under it');
  eq(f, await p.evaluate(() => {
    const box = document.querySelector('.af-cal');
    return [box.classList.contains('af-cal-swiped'), box.querySelector('.af-cal-view').hidden, box.querySelector('.af-cal-shade').hidden, !!box.querySelector('[data-go="-1"]'), box.querySelector('.af-cal-canvas').tabIndex];
  }), [true, true, true, false, -1], 'swiped, no view or shade switch, no ‹ ›, not a tab stop');
  const today = () => p.evaluate(() => document.querySelector('.af-cal-today').hidden);
  eq(f, await today(), true, 'Today, with today in view');
  await p.evaluate(() => { const g = document.querySelector('.af-cal-grid'); g.scrollLeft = 0; g.dispatchEvent(new Event('scroll')); });
  eq(f, await today(), false, 'Today, scrolled back');
  await p.evaluate(() => document.querySelector('.af-cal-today').click());
  await wait(1200);
  eq(f, await today(), true, 'Today, once tapped');
  // no marks on the phone: there is no add-on to keep them
  const at = await p.evaluate(() => { const cv = document.querySelector('.af-cal-canvas'), r = cv.getBoundingClientRect(); return [r.right - 60, r.top + r.height / 3]; });
  await p.mouse.click(at[0], at[1], { button: 'right' });
  eq(f, await p.evaluate(() => document.querySelector('.af-cal-pin').hidden), true, 'no mark editor');
  return [p, f];
});

const fs1 = (p, sel) => p.evaluate(s => document.querySelector(s).click(), sel).then(() => wait(1500));
const phoneState = (p, simCls) => p.evaluate(cls => {
  const shell = document.querySelector('.af-phone-shell'), stage = document.querySelector('.af-phone-stage');
  return { full: shell.classList.contains(cls), sideways: stage.classList.contains('af-sideways'), turned: /rotate\(90deg\)/.test(stage.style.transform),
    forest: !!document.querySelector('#memory-forest-phone .af-canvas'), cal: !!document.querySelector('#memory-forest-phone .af-cal'),
    calSheet: shell.classList.contains('af-full-cal'), labels: [...document.querySelectorAll('.af-expand')].map(e => e.getAttribute('aria-label')) };
}, simCls);

check('phone: the forest\'s full screen turns it sideways, alone; leaving it puts it all back', async b => {
  const p = await open(b, 'phone', { viewport: PHONE }); await phoneReady(p); const f = [];
  await fs1(p, '.af-expand:not(.af-expand-cal)');
  eq(f, await phoneState(p, sim), { full: true, sideways: true, turned: true, forest: true, cal: false, calSheet: false, labels: ['Leave full screen'] }, 'in full screen');
  await fs1(p, '.af-expand:not(.af-expand-cal)');
  eq(f, await phoneState(p, sim), { full: false, sideways: false, turned: false, forest: true, cal: true, calSheet: false, labels: ['Forest full screen', 'Heatmap full screen'] }, 'after leaving it');
  return [p, f];
});

check('phone: the heatmap\'s full screen shows it alone, on its own sheet', async b => {
  const p = await open(b, 'phone', { viewport: PHONE }); await phoneReady(p); const f = [];
  await fs1(p, '.af-expand-cal');
  eq(f, await phoneState(p, sim), { full: true, sideways: true, turned: true, forest: false, cal: true, calSheet: true, labels: ['Leave full screen'] }, 'in full screen');
  await fs1(p, '.af-expand-cal');
  eq(f, await phoneState(p, sim), { full: false, sideways: false, turned: false, forest: true, cal: true, calSheet: false, labels: ['Forest full screen', 'Heatmap full screen'] }, 'after leaving it');
  return [p, f];
});

check('phone: held sideways already, the full screen needs no turn', async b => {
  const p = await open(b, 'phone', { viewport: Object.assign({}, PHONE, { width: 844, height: 390 }) }); await phoneReady(p); const f = [];
  await fs1(p, '.af-expand:not(.af-expand-cal)');
  const s = await phoneState(p, sim);
  eq(f, [s.full, s.sideways, s.cal], [true, false, false], 'full, upright, the forest alone');
  return [p, f];
});

check('phone: a full screen the app refuses says so, and stays upright', async b => {
  const p = await open(b, 'phone-denied', { viewport: PHONE }); await phoneReady(p); const f = [];
  await fs1(p, '.af-expand:not(.af-expand-cal)');
  has(f, await p.evaluate(() => document.querySelector('.af-phone-note').textContent), [/^Full screen isn't allowed here\. Synced/], 'the line under it');
  const s = await phoneState(p, sim);
  eq(f, [s.full, s.sideways, s.cal], [false, false, true], 'upright, as before');
  return [p, f];
});

check('phone: a forest synced days ago asks for a sync', async b => {
  const p = await open(b, 'phone-stale', { viewport: PHONE }); await phoneReady(p); const f = [];
  has(f, await p.evaluate(() => document.querySelector('.af-phone-note').textContent), [/^Synced 3 days ago\. Sync Anki on your computer to bring it up to date\.$/], 'the line under it');
  return [p, f];
});

check('phone: a note with no days yet waits for the sync', async b => {
  const p = await open(b, 'phone-empty', { viewport: PHONE }); await wait(500); const f = [];
  eq(f, await p.evaluate(() => document.getElementById('memory-forest-phone').textContent), 'Your forest arrives with the next sync from Anki on your computer.', 'the card');
  return [p, f];
});

/* ---------- run them ---------- */
const out = { checks: [], errors: [] };
const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--disable-gpu'] });
try {
  for (const c of checks) {
    if (only && !c.name.includes(only)) continue;
    const res = { name: c.name, failures: [], bug: c.bug || null };
    try {
      const [, fails] = await c.fn(browser);
      res.failures.push(...fails);
      await wait(50);
    } catch (e) {
      res.failures.push(`threw: ${e && e.message ? e.message : e}`);
    }
    for (const page of await browser.pages()) {
      if (!page.errors) continue;  // (the browser's own first tab)
      res.failures.push(...page.errors.filter(e => !(c.allow && c.allow.test(e))));
      await page.close().catch(() => {});
    }
    out.checks.push(res);
  }
} catch (e) {
  out.errors.push(String(e));
} finally {
  await browser.close();
}
out.seconds = (Date.now() - started) / 1000;
process.stdout.write(JSON.stringify(out));

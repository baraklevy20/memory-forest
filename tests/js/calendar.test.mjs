// The study heatmap's model (web/calendar.js): streaks and the days that pass over them, ponds, the
// trophies and the goal, the four shades by Reviews, Time and Pace, the days each view shows, the
// weeks they fall in, and the words its tooltips and key use. Made-up calendars only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { load, SCRIPTS, calendar } from './load.mjs';

const EXPOSE = ['history', 'windowOf', 'columns', 'weeksWidth', 'pastYears', 'yearsFor', 'reachOf', 'lasted', 'markLine',
  'countFor', 'widthOf', 'shades', 'exactSteps', 'oklab', 'restShade', 'blankOn', 'cellOf', 'utc', 'MARK_ICONS', 'MARK_ORDER',
  'setWeekStart: w => { weekStart = w; }', 'setCell: c => { CELL = c; }'];
const AF = load(SCRIPTS, { expose: { 'calendar.js': EXPOSE } }).AnkiForest;
const T = AF.__test;
const TODAY = '2026-10-18';  // (a Sunday)
const DAY = 86400000, today = T.utc(TODAY);
const H = (days, more) => T.history(calendar(TODAY, days, more));
const off = iso => (T.utc(iso) - today) / DAY;  // a date's offset from today
const plain = v => JSON.parse(JSON.stringify(v));  // (out of the page's context, for deepEqual)
const runs = h => plain(h.runs.map(r => [r.from, r.to, r.days]));

test('a streak is a run of days studied, the current one running through today', () => {
  const h = H([5, 0, 3, 4, 6]);
  assert.deepEqual(runs(h), [[-4, -4, 1], [-2, 0, 3]]);
  assert.equal(h.current, h.runs[1]);
  assert.equal(h.first, -4);
  assert.equal(h.n(-3), 0);
  assert.equal(h.n(0), 6);
});

test('today not studied yet keeps the streak alive; a missed yesterday ends it', () => {
  assert.equal(H([3, 4, 0]).current.days, 2);
  assert.equal(H([3, 0, 0]).current, null);
  assert.equal(H([0, 0, 0]).current, null);
});

test('a day with nothing due passes inside a streak, neither breaking nor growing it', () => {
  // (free: [older, newer] days ago)
  const h = H([3, 0, 4], { free: [[1, 1]] });
  assert.deepEqual(runs(h), [[-2, 0, 2]]);
  assert.ok(h.free.has(-1));
  assert.equal(h.runOf(-1), h.current);
  // and without it the streak breaks there
  assert.deepEqual(runs(H([3, 0, 4])), [[-2, -2, 1], [0, 0, 1]]);
});

test('the current streak lives on over the free days since its last day studied', () => {
  const h = H([3, 3, 0, 0], { free: [[1, 1]] });
  assert.equal(h.current && h.current.days, 2);
  assert.equal(h.runOf(-1), h.current);
  assert.equal(h.runOf(0), h.current);
  assert.equal(H([3, 3, 0, 0]).current, null);  // (a missed day instead)
});

test('a day off (a 6- or 5-day week) passes over a streak as a free day does', () => {
  const h = H([2, 0, 2], { daysOff: [1] });
  assert.ok(h.daysOff.has(-1) && h.free.has(-1));
  assert.equal(h.current.days, 2);
});

test('counted from the start date, a streak restarts there; otherwise it runs over it', () => {
  const days = Array(10).fill(5), forestStart = '2026-10-14';
  assert.deepEqual(runs(H(days, { forestStart })), [[-9, 0, 10]]);
  const h = H(days, { forestStart, streakFromStart: true });
  assert.deepEqual(runs(h), [[-9, -5, 5], [-4, 0, 5]]);
  assert.equal(h.fs, -4);
  // (a streak that ended before the start date is none of yours now)
  assert.equal(H([5, 5, 5, 0, 0], { forestStart: '2026-10-18', streakFromStart: true, free: [[1, 0]] }).current, null);
});

test('the forest\'s ponds take the days in them not studied', () => {
  const h = H([1, 0, 0, 1, 0, 1], { ponds: [['2026-10-14', '2026-10-17']] });
  assert.deepEqual(plain([...h.pond].sort((a, b) => a - b)), [-4, -3, -1]);
});

const streakOf = (len, gap = 1) => Array(len).fill(10).concat(Array(gap).fill(0));
test('your three longest streaks of 30 days or more take the trophies, the first to a length first', () => {
  const days = [...streakOf(40), ...streakOf(31), ...streakOf(50), ...streakOf(40), ...streakOf(5, 0)];
  const h = H(days);
  const podium = plain([...h.podium].map(([r, i]) => [r.days, i]).sort((a, b) => a[1] - b[1]));
  assert.deepEqual(podium, [[50, 0], [40, 1], [40, 2]]);
  const [first40] = [...h.podium].filter(([r]) => r.days === 40).sort((a, b) => a[1] - b[1]);
  assert.equal(first40[0], h.runs[0]);  // (the earlier 40 ranks above the later)
});

test('the goal: a 30-day streak first, then each record to pass in turn, none once it is the longest', () => {
  // (no streak of 30 yet: reach one; today studied, so from tomorrow)
  let h = H(streakOf(5, 0));
  assert.deepEqual(plain(h.goal), { o: 25, rank: 0, beats: 0 });
  // today not studied yet: today counts towards it
  h = H([...streakOf(5, 0), 0]);
  assert.deepEqual(plain(h.goal), { o: 24, rank: 0, beats: 0 });
  // a 40-day record: second place (30 days) first, then beating 40
  h = H([...streakOf(40), ...streakOf(10, 0)]);
  assert.deepEqual(plain(h.goal), { o: 20, rank: 1, beats: 0 });
  h = H([...streakOf(40), ...streakOf(35, 0)]);
  assert.deepEqual(plain(h.goal), { o: 6, rank: 0, beats: 40 });
  // the longest already: no goal
  assert.equal(H([...streakOf(40), ...streakOf(50, 0)]).goal, null);
  // no current streak: no goal
  assert.equal(H([...streakOf(40, 3)]).goal, null);
});

test('Reviews: the four shades split the last year\'s days at 40%, 70% and 90%', () => {
  const days = Array.from({ length: 100 }, (_, i) => i + 1);
  const h = H(days);
  assert.equal(h.by, 'reviews');
  assert.deepEqual(plain(h.splits()), [1, 41, 71, 91]);
  const shadeOfCount = n => h.shade(days.indexOf(n) - 99);
  assert.deepEqual([1, 40, 41, 70, 71, 90, 91, 100].map(shadeOfCount), [0, 0, 1, 1, 2, 2, 3, 3]);
});

test('Reviews: the splits stay at least one apart, and only the last 365 days count', () => {
  assert.deepEqual(plain(H(Array(50).fill(5)).splits()), [1, 6, 7, 8]);
  // a huge day 400 days ago counts for nothing
  const days = [100000, ...Array(399).fill(0), ...Array.from({ length: 100 }, (_, i) => i + 1)];
  assert.deepEqual(plain(H(days).splits()), [1, 41, 71, 91]);
});

test('Time: its splits snap to just under a whole minute, rising', () => {
  const days = Array(60).fill(10), time = Array.from({ length: 60 }, (_, i) => 60 * (i + 1));
  const h = H(days, { time, shadeBy: 'time' });
  assert.equal(h.by, 'time');
  assert.ok(h.timed);
  const s = plain(h.splits());
  for (let i = 1; i < s.length; i++) {
    assert.equal((s[i] + 30) % 60, 0, `split ${s[i]} is not a minute less 30 s`);
    if (i > 1) assert.ok(s[i] >= s[i - 1] + 60);
  }
  assert.equal(h.shade(0), 3);  // (the longest day)
  assert.equal(h.shade(-59), 0);
});

test('a choice with nothing to go by falls back to Reviews', () => {
  assert.equal(H([4, 5], { shadeBy: 'time' }).by, 'reviews');
  assert.equal(H([4, 5], { shadeBy: 'median' }).by, 'reviews');
  assert.equal(H([4, 5], { shadeBy: 'median', answerTime: [null, null] }).paced, false);
});

test('Pace: the fastest answers take the strongest shade; a day with no answer time a typical one', () => {
  const n = 50, days = Array(n).fill(10), answerTime = Array.from({ length: n }, (_, i) => 2 + i * 0.1);
  answerTime[n - 1] = null;
  const h = H(days, { answerTime, shadeBy: 'median' });
  assert.equal(h.by, 'median');
  assert.equal(h.shade(-(n - 1)), 3);  // (2.0 s: the fastest)
  assert.equal(h.shade(-1), 0);  // (the slowest timed)
  assert.ok(h.timeless(0));
  assert.ok([1, 2].includes(h.shade(0)), 'a day with no answer time takes the median day\'s shade');
  assert.equal(h.answerTime(-(n - 1)), 2);
  const s = plain(h.splits());
  assert.equal(s[0], 0);
  for (let i = 1; i < s.length; i++) assert.ok(s[i] > s[i - 1]);
});

test('the days ahead shade by their cards due, on a log scale up to the busiest', () => {
  const h = H([3], { due: [7, 1, 10, 100, 1000] });
  assert.equal(h.dueToday, 7);
  assert.equal(h.ahead, 4);
  assert.equal(h.n(4), 1000);
  assert.equal(h.dueShade(1000), 3);
  assert.equal(h.dueShade(1), 0);
  assert.ok(h.dueShade(10) <= h.dueShade(100));
});

test('animals stand on the day they came, none before the forest began', () => {
  const animals = [{ ago: 1, key: 'deer' }, { ago: 1, key: 'fox' }, { ago: 8, key: 'owl' }];
  const h = H(Array(10).fill(3), { animals, forestStart: '2026-10-15' });
  assert.equal(h.animals.get(-1).length, 2);
  assert.equal(h.animals.has(-8), false);
});

test('marks: an old bare date and a named one; deleted cards by day', () => {
  const h = H([1, 1, 1], { marks: ['2026-10-17', { day: '2026-10-25', icon: 'exam', name: 'Exam' }, { icon: 'pin' }], gone: [[1, 3, 5], [2, 2]] });
  assert.deepEqual(plain(h.marked.get(-1)), { icon: 'pin', name: '' });
  assert.deepEqual(plain(h.marked.get(7)), { icon: 'exam', name: 'Exam' });
  assert.equal(h.marked.size, 2);
  assert.deepEqual(plain(h.gone.get(-1)), [3, 5]);
  assert.deepEqual(plain(h.gone.get(-2)), [2, 2]);
});

test('Timeline: ten months, this month most of the way along, paged a whole stretch at a time', () => {
  const h = H([1]);
  let w = T.windowOf(h, 'timeline', 0, null, 10);
  assert.equal(w.from, off('2026-03-01'));
  assert.equal(w.to, off('2026-12-31'));
  assert.ok(w.apart);
  w = T.windowOf(h, 'timeline', -10, null, 10);
  assert.equal(w.from, off('2025-05-01'));
  assert.equal(w.to, off('2026-02-28'));
  // fewer months when narrow: this month still near the end
  w = T.windowOf(h, 'timeline', 0, null, 4);
  assert.equal(w.from, off('2026-07-01'));
  assert.equal(w.to, off('2026-10-31'));
});

test('By year: January to December; the phone: the first month counted to five months on', () => {
  const h = H(Array(400).fill(1));
  assert.deepEqual(plain(T.windowOf(h, 'by_year', 0, null)), { from: off('2026-01-01'), to: off('2026-12-31'), year: 2026 });
  assert.equal(T.windowOf(h, 'by_year', 0, 2025).from, off('2025-01-01'));
  const sw = T.windowOf(h, 'swiped', 0, null);
  assert.equal(sw.from, off('2025-09-01'));
  assert.equal(sw.to, off('2027-03-31'));
});

test('weeks: By year runs its months on; Timeline starts each month in a column of its own', () => {
  T.setWeekStart(1);
  const h = H([1]);
  const year = T.columns(h, T.windowOf(h, 'by_year', 0, null));
  assert.equal(year.length, 365);
  assert.deepEqual(plain(year[0]).slice(2), [0, 3]);  // (Jan 1 2026, a Thursday: row 3 with Monday on top)
  const cols = plain(year.map(c => c[2]));
  assert.equal(Math.max(...cols), 52);  // (53 weeks)
  // every Monday starts a new column, and nothing else does
  for (let i = 1; i < year.length; i++) assert.equal(year[i][2] - year[i - 1][2], year[i][3] === 0 ? 1 : 0);
  const tl = T.columns(h, T.windowOf(h, 'timeline', 0, null, 10));
  for (let i = 1; i < tl.length; i++) {
    const starts = new Date(tl[i][1]).getUTCDate() === 1, step = tl[i][2] - tl[i - 1][2];
    // (a month starting on the week's first day: an empty column before it)
    if (starts) assert.equal(step, tl[i][3] === 0 ? 2 : 1, `month at ${new Date(tl[i][1]).toISOString()}`);
    else assert.equal(step, tl[i][3] === 0 ? 1 : 0);
  }
});

test('the week starts on the day it is set to', () => {
  for (const [ws, row] of [[1, 6], [0, 0], [6, 1]]) {
    T.setWeekStart(ws);
    const h = H([1]), c = T.columns(h, T.windowOf(h, 'by_year', 0, null));
    assert.equal(c.find(x => x[0] === 0)[3], row, `today (a Sunday) with the week from day ${ws}`);
  }
  T.setWeekStart(1);
});

test('By year: every year as wide as the widest, a leap year from its weeks\' last day taking 54 weeks', () => {
  T.setWeekStart(1); T.setCell(10);
  // 2012: a leap year starting on a Sunday, the last day of a week from Monday
  const old = T.history(calendar('2012-12-31', Array(366).fill(1)));
  const w = T.windowOf(old, 'by_year', 0, null), cols = T.columns(old, w);
  assert.equal(cols[cols.length - 1][2], 53);
  assert.equal(T.weeksWidth(old, w, cols[cols.length - 1][2]), 1 + 54 * 10);
  // a history of only 2026: 53 weeks
  const now = H(Array(200).fill(1)), w2 = T.windowOf(now, 'by_year', 0, null), c2 = T.columns(now, w2);
  assert.equal(T.weeksWidth(now, w2, c2[c2.length - 1][2]), 1 + 53 * 10);
  // a history reaching back into 2012: 2026's weeks as wide as 2012's
  const long = T.history(calendar(TODAY, Array(off('2026-10-18') - off('2012-01-01') + 1).fill(1)));
  const w3 = T.windowOf(long, 'by_year', 0, null), c3 = T.columns(long, w3);
  assert.equal(T.weeksWidth(long, w3, c3[c3.length - 1][2]), 1 + 54 * 10);
  // Timeline: as wide as its own weeks
  const w4 = T.windowOf(now, 'timeline', 0, null, 10), c4 = T.columns(now, w4);
  assert.equal(T.weeksWidth(now, w4, c4[c4.length - 1][2]), 1 + (c4[c4.length - 1][2] + 1) * 10);
});

test('a tile style\'s own gap sets the cell', () => {
  assert.equal(T.cellOf({}), 10);
  assert.equal(T.cellOf({ look: { gap: 2 } }), 11);
  assert.equal(T.cellOf({ look: { gap: 0 } }), 9);
  assert.equal(T.cellOf({ look: { gap: 1.5 } }), 10);
});

test('earlier years: back to the current streak\'s start, or a long one just broken; else every year', () => {
  // a streak since mid 2024
  const since = off('2024-06-01'), days = Array(-since + 1).fill(4);
  let h = T.history(calendar(TODAY, [...Array(800).fill(2), 0, ...days]));
  assert.deepEqual(plain(T.pastYears(h, 2026, false)), [2025, 2024]);
  assert.deepEqual(plain(T.pastYears(h, 2026, true)).slice(-1), [new Date(today + h.first * DAY).getUTCFullYear()]);
  assert.deepEqual(plain(T.yearsFor(h, 2026, false)), []);
  assert.deepEqual(plain(T.yearsFor(h, 2026, true)), [2025, 2024]);
  // a long streak broken lately, then a short one: back to the long one
  h = T.history(calendar(TODAY, [...Array(500).fill(2), 0, ...Array(400).fill(3), 0, 0, ...Array(10).fill(3)]));
  assert.equal(T.reachOf(h), h.runs[h.runs.length - 2].from);
  // a streak of this year alone, the long one broken months ago: nothing short of every year to offer
  h = T.history(calendar(TODAY, [...Array(800).fill(2), ...Array(60).fill(0), ...Array(20).fill(3)]));
  assert.deepEqual(plain(T.pastYears(h, 2026, false)), []);
  assert.deepEqual(plain(T.yearsFor(h, 2026, true)), plain(T.pastYears(h, 2026, true)));
  assert.ok(T.pastYears(h, 2026, true).length >= 2);
});

test('Timeline shows as many months as its width holds at its days\' own size', () => {
  const ten = T.widthOf('timeline') * 1.25;  // (ten months at DAY_K: about 680 px)
  assert.equal(T.countFor('timeline', ten), 10);
  assert.equal(T.countFor('timeline', 0), 10);
  assert.equal(T.countFor('by_year', 50), 10);
  assert.equal(T.countFor('timeline', ten / 2), 5);
  assert.equal(T.countFor('timeline', ten * 1.6), 16);
  assert.equal(T.countFor('timeline', 20), 3);
  assert.equal(T.countFor('timeline', ten * 5), 24);
});

test('a stretch of time in words', () => {
  assert.deepEqual([20, 60, 48 * 60, 72 * 60, 120 * 60, 125 * 60, 600 * 60, 640 * 60].map(T.lasted),
    ['under a minute', 'a minute', '48 min', '1 hr 12 min', '2 hr', '2 hr 5 min', '10 hr', '11 hr']);
});

test('a mark\'s line: its name, or its icon\'s, and how far off it is', () => {
  assert.equal(T.markLine({ icon: 'exam', name: '' }, 3), 'Exam in 3 days');
  assert.equal(T.markLine({ icon: 'trip', name: 'Lisbon' }, 1), 'Lisbon tomorrow');
  assert.equal(T.markLine({ icon: 'heart', name: '' }, 0), 'Heart today');
  assert.equal(T.markLine({ icon: 'nonsense', name: '' }, -4), 'Pin');
  // the icons, in marks.ICONS' order, each six by six
  assert.deepEqual(plain(T.MARK_ORDER), ['pin', 'exam', 'trip', 'birthday', 'star', 'heart', 'done', 'sick']);
  for (const m of Object.values(T.MARK_ICONS)) assert.ok(m.rows.length === 6 && m.rows.every(r => r.length === 6));
});

const L = c => T.oklab(c)[0];
test('the shades stand out more from the page the busier the day: lighter on a dark page, darker on a light', () => {
  const sp = { mood: { special: 'natural' } }, look = { colours: '#3c8d40' };
  const dark = T.shades(sp, { bg: [44, 44, 44], dark: true }, look).grass.map(p => L(p[0]));
  const light = T.shades(sp, { bg: [245, 245, 245], dark: false }, look).grass.map(p => L(p[0]));
  for (let i = 1; i < 4; i++) { assert.ok(dark[i] > dark[i - 1], 'dark page'); assert.ok(light[i] < light[i - 1], 'light page'); }
  // "Busier days: Darker": a dark page's the other way round
  const darker = T.shades(sp, { bg: [44, 44, 44], dark: true }, { colours: '#3c8d40', darker: true }).grass.map(p => L(p[0]));
  for (let i = 1; i < 4; i++) assert.ok(darker[i] < darker[i - 1]);
});

test('your own colours: the busiest exactly the last, the faintest still apart from a missed day', () => {
  for (const paper of [{ bg: [44, 44, 44], dark: true }, { bg: [245, 245, 245], dark: false }]) {
    const steps = T.exactSteps(['#0e4429', '#39d353'], paper);
    assert.deepEqual(plain(steps[3].map(Math.round)), [0x39, 0xd3, 0x53]);
    const blank = T.oklab(T.blankOn(paper)), faint = T.oklab(steps[0]);
    assert.ok(Math.hypot(faint[0] - blank[0], faint[1] - blank[1], faint[2] - blank[2]) >= 0.06, 'the faintest shade reads as a missed day');
    const one = T.exactSteps('#39d353', paper);
    assert.deepEqual(plain(one[3].map(Math.round)), [0x39, 0xd3, 0x53]);
  }
});

test('a rest day\'s ring is the faintest shade far enough from the empty grey to see', () => {
  const sp = { mood: { special: 'natural' } };
  for (const paper of [{ bg: [44, 44, 44], dark: true }, { bg: [245, 245, 245], dark: false }]) {
    const pal = T.shades(sp, paper, { colours: '#3c8d40' }), ring = T.restShade(pal, paper);
    const blank = T.oklab(T.blankOn(paper)), r = T.oklab(ring);
    assert.ok(Math.hypot(r[0] - blank[0], r[1] - blank[1], r[2] - blank[2]) >= 0.1 || ring === pal.grass[3][0]);
    assert.ok(pal.grass.some(p => p[0] === ring));
  }
});

test('the calendar\'s width and the phone\'s scale', () => {
  // (Width: 680 px, 85% of the Forest width, or 85% of the room, never more than the room; By year
  // fits its year to it)
  const size = (width, fill, rule) => ({ view: 'timeline', size: { width, fill, rule } });
  assert.equal(AF.calendarWidthIn(size('forest', 'more'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('forest', 'more'), 800, 500), 500);
  assert.equal(AF.calendarWidthIn(size('full', 'more'), 800, 1300), 1105);
  assert.equal(AF.calendarWidthIn(size('fixed', 'bigger'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('fixed', 'bigger'), 800, 600), 600);
  assert.equal(AF.calendarWidthIn(size('full', 'more'), 800, 1300, 'by_year'), 1105);
  assert.equal(AF.calendarWidthIn(size('fixed', 'more'), 800, 1300, 'by_year'), 680);
  assert.equal(AF.calendarWidthIn(size('full', 'more', 'natural'), 800, 1300, 'by_year'), Math.round(531 * 1.25));  // (the debug natural rule)
  assert.equal(AF.calendarWidthIn(size('full', 'bigger'), 800, 1300, 'by_year'), 1105);
  assert.equal(AF.calendarMost(size('forest', 'more'), 800), 680);  // (beside the list alone)
  assert.equal(AF.calendarMost(size('full', 'more'), 800), Infinity);
  assert.equal(AF.calendarColumnShare(size('full', 'more'), 800), 0.85);  // (85% of the room beside the list)
  assert.equal(AF.calendarColumnShare(size('forest', 'more'), 800), 1);
  // (the Debug tab's rules stand in for the setting)
  assert.equal(AF.calendarWidthIn(size('full', 'more', 'flat'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('full', 'more', 'forest85'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('full', 'more', 'share'), 800, 1000), 850);
  assert.equal(AF.calendarWidthIn(size('full', 'more', 'fit_forest'), 800, 1300), 800);
  assert.equal(AF.calendarWidthIn(size('forest', 'more', 'fit'), 800, 1300), 1300);
  assert.equal(AF.calendarMost(size('forest', 'more', 'natural'), 800), Math.round(541 * 1.25 * 1.2));
  assert.equal(AF.calendarWant(size('forest', 'more', 'setting'), 800), 'forest');
  assert.equal(AF.calendarScaleFor(10), 1.4);  // (never under 1.4 css px a pixel)
  assert.equal(AF.calendarScaleFor(3 + 7 * 10 + 15), 1.4);
  assert.equal(AF.calendarScaleFor((3 + 7 * 10 + 15) * 3), 3);
});

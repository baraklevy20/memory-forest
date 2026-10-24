// The study heatmap's model (web/calendar.js): streaks and the days that pass over them, ponds, the
// trophies and the goal, the four shades by Reviews, Time and Pace, the days each view shows, the
// weeks they fall in, and the words its tooltips and key use. Made-up calendars only.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { load, SCRIPTS, calendar, WEB } from './load.mjs';

const EXPOSE = ['history', 'windowOf', 'columns', 'weeksWidth', 'streakRows', 'pageBefore', 'reachOf', 'lasted', 'markLine',
  'countFor', 'widthOf', 'shades', 'hourOf', 'exactSteps', 'oklab', 'restShade', 'blankOn', 'cellOf', 'utc', 'MARK_ICONS', 'MARK_ORDER',
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

test('Streak view: rows of whole weeks back to the streak worth seeing, paged back as many at a time', () => {
  const W = 53, rows = (h, page = null) => plain(T.streakRows(h, W, page));
  // a streak since mid 2024 (TODAY a Sunday: this week ends today), cards due for years ahead
  const since = off('2024-06-01'), days = Array(-since + 1).fill(4);
  let h = T.history(calendar(TODAY, [...Array(400).fill(2), 0, ...Array(100).fill(0), ...days], { due: Array(3000).fill(1) }));
  const open = rows(h);
  assert.equal(open.length, 3);
  assert.equal(open[2].to, 8 * 7);  // (eight weeks ahead)
  assert.ok(open.every((x, i) => x.to - x.from + 1 === W * 7 && x.cols === W && (!i || x.from === open[i - 1].to + 1)), 'one strip, no gaps');
  assert.ok(open[0].from <= since && open[0].from > since - W * 7, 'the top row holds the streak\'s first day');
  // ‹: the stretch just before, as many rows, until the first review
  const end = T.pageBefore(h, W, 3, open[0].from), back = rows(h, end);
  assert.equal(back[back.length - 1].to, open[0].from - 1);
  assert.ok(back.length <= 3 && back[0].from <= h.first + W * 7);
  // › from the streak: as many rows on, into the days ahead
  const on = plain(T.streakRows(h, W, null, 1));
  assert.equal(on.length, 3);
  assert.equal(on[0].from, open[2].to + 1);
  // (but no further than the row with the last day due: cards due for 200 days, one row on)
  h = T.history(calendar(TODAY, [...Array(400).fill(2), 0, ...Array(100).fill(0), ...days], { due: Array(201).fill(1) }));
  const capped = plain(T.streakRows(h, W, null, 1));
  assert.equal(capped.length, 3);
  assert.equal(capped[2].to, open[2].to + W * 7);
  assert.ok(capped[2].from <= h.ahead && capped[2].to >= h.ahead, 'its last row holds the last day due');
  // a long streak broken lately, then a short one: back to the long one
  h = T.history(calendar(TODAY, [...Array(500).fill(2), 0, ...Array(400).fill(3), 0, 0, ...Array(10).fill(3)]));
  assert.equal(T.reachOf(h), h.runs[h.runs.length - 2]);
  assert.ok(rows(h)[0].from <= h.runs[h.runs.length - 2].from);
  // no study at all: one row, today's
  h = T.history(calendar(TODAY, [0]));
  assert.equal(rows(h).length, 1);
});

test('Streak view: a page that would cut a streak with a bracket at its top starts on that streak\'s first week', () => {
  const W = 53, top = off('2026-01-05');  // (a Monday: a page's first day)
  const page = end => [end - W * 7 + 1, end];
  // studied from Sep 1, 2024 for 102 days (to Dec 11), then nothing until a week ago
  const at = iso => -off(iso), n = at('2024-01-01') + 1;
  const studied = d => (d <= at('2024-09-01') && d > at('2024-09-01') - 102) || d < 7;
  let h = T.history(calendar(TODAY, Array.from({ length: n }, (_, i) => (studied(n - 1 - i) ? 5 : 0))));
  const r = h.runs.find(x => x.days === 102);
  // a year back from Jan 2026 starts Dec 30, 2024: clear of the streak, nothing to move
  assert.deepEqual(plain(T.pageBefore(h, W, 1, top)), { end: top - 1, from: page(top - 1)[0] });
  // a year back from Nov 2025 would start in Nov 2024, inside it: the page reaches up to its first
  // week instead, still ending the day before (no day between left off every page)
  const t2 = off('2025-11-03'), p2 = T.pageBefore(h, W, 1, t2);
  assert.equal(p2.end, t2 - 1);
  assert.ok(p2.from <= r.from && p2.from > r.from - 7, `reaches the streak's week: ${p2.from}, ${r.from}`);
  const drawn = plain(T.streakRows(h, W, p2));
  assert.equal(drawn[drawn.length - 1].to, t2 - 1);
  assert.ok(drawn[0].from <= r.from, 'the whole streak in view');
  // a streak of under 30 days is left cut
  h = T.history(calendar(TODAY, Array.from({ length: n }, (_, i) => { const d = n - 1 - i; return (d <= at('2024-11-20') && d > at('2024-11-20') - 20) || d < 7 ? 5 : 0; })));
  assert.deepEqual(plain(T.pageBefore(h, W, 1, t2)), { end: t2 - 1, from: page(t2 - 1)[0] });
});

test('Streak view: paging back from your streak to your first review leaves no day off every page', () => {
  // six years of 100-day streaks, five days missed between them, each page's top cutting one
  const W = 53, n = 6 * 365, days = Array.from({ length: n }, (_, i) => ((n - 1 - i) % 105 < 100 ? 3 : 0));
  const h = T.history(calendar(TODAY, days));
  const seen = new Set(), add = rs => { for (const r of rs) for (let o = r.from; o <= r.to; o++) seen.add(o); };
  let rs = plain(T.streakRows(h, W, null)), turned = 0;
  const per = rs.length;
  add(rs);
  while (rs[0].from > h.first && turned++ < 50) {
    rs = plain(T.streakRows(h, W, T.pageBefore(h, W, per, rs[0].from)));
    add(rs);
  }
  const missing = [];
  for (let o = h.first; o <= 0; o++) if (!seen.has(o)) missing.push(o);
  assert.deepEqual(missing, [], 'every day on some page, the studied days between pages too');
  assert.ok(turned > 1 && turned < 50);
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
const PAGES = [{ bg: [44, 44, 44], dark: true }, { bg: [245, 245, 245], dark: false }];
const hue = k => Math.atan2(k[2], k[1]), chromaOf = k => Math.hypot(k[1], k[2]);
// a scenery at an hour as the panel draws it: the mood, with its own hour (`home`), and what the hour does (hourOf)
const atHour = (A, special, home, time, more = {}) => {
  const mood = Object.assign({ special, time, home, weather: 'clear' }, more);
  return { theme: {}, u: 1, mood, hour: A.__test.hourOf(mood) };
};
const labs = (A, sp, paper, look) => A.__test.shades(sp, paper, look).grass.map(p => A.__test.oklab(p[0]));
test('after dark a day scenery\'s shades cool with the forest, each keeping its lightness', () => {
  for (const paper of PAGES) {
    const day = labs(AF, atHour(AF, 'natural', 'golden_hour', 'day'), paper), night = labs(AF, atHour(AF, 'natural', 'golden_hour', 'night'), paper);
    const dusk = labs(AF, atHour(AF, 'natural', 'golden_hour', 'dusk'), paper);
    for (let i = 0; i < 4; i++) {
      // (its colourfulness as by day, or a little less where the screen can't show a colour that bright)
      assert.ok(Math.abs(night[i][0] - day[i][0]) < 0.002 && chromaOf(night[i]) <= chromaOf(day[i]) + 0.001 && chromaOf(night[i]) > 0.7 * chromaOf(day[i]), 'same lightness, about as colourful');
      assert.ok(hue(night[i]) > hue(dusk[i]) && hue(dusk[i]) > hue(day[i]), 'green turning towards the night blue');
    }
    // (dawn and golden hour: the trees as by day)
    assert.deepEqual(plain(labs(AF, atHour(AF, 'natural', 'golden_hour', 'golden_hour'), paper)), plain(day));
    assert.deepEqual(plain(labs(AF, atHour(AF, 'natural', 'golden_hour', 'dawn'), paper)), plain(day));
  }
});

// the night sceneries, with their files (each names its day colours, `calendarDay`)
// (Chalkboard is Plus only: the public repo has no file of it, so its check runs only where it is)
const CHALK = fs.existsSync(path.join(WEB, 'envs', 'chalkboard.js'));
const NIGHT = load([...SCRIPTS, 'envs/aurora.js', 'envs/pumpkin_patch.js', ...(CHALK ? ['envs/chalkboard.js'] : [])], { expose: { 'calendar.js': ['shades', 'hourOf', 'oklab'] } }).AnkiForest;
test('a night scenery keeps its colours after dark and wears its day colours by day, halfway at dawn and golden hour', () => {
  const N = NIGHT, own = (paper, key = 'aurora') => labs(N, { theme: {}, u: 1, mood: { special: key, time: 'night', home: 'night', weather: 'clear' } }, paper);
  for (const paper of PAGES) {
    for (const time of ['night', 'dusk']) assert.deepEqual(plain(labs(N, atHour(N, 'aurora', 'night', time), paper)), plain(own(paper)), time);
    // by day: its day colours, a green into the polar blue, where by night it is all the snow ghosts' slate blue
    const day = labs(N, atHour(N, 'aurora', 'night', 'day'), paper), night = own(paper), dawn = labs(N, atHour(N, 'aurora', 'night', 'dawn'), paper);
    const deg = k => (hue(k) * 180 / Math.PI + 360) % 360;
    assert.ok(deg(day[0]) < 200 && deg(night[0]) > 230, 'the fewest a green by day, a blue by night');
    for (let i = 0; i < 4; i++) {
      assert.ok(Math.abs(day[i][0] - night[i][0]) < 0.002, 'each shade at its lightness at every hour');
      assert.ok(Math.abs(dawn[i][0] - night[i][0]) < 0.002);
    }
    // (dawn halfway between, by hue: never through grey)
    assert.ok(deg(dawn[0]) > deg(day[0]) && deg(dawn[0]) < deg(night[0]) && chromaOf(dawn[0]) > 0.6 * Math.min(chromaOf(day[0]), chromaOf(night[0])));
    assert.deepEqual(plain(labs(N, atHour(N, 'aurora', 'night', 'golden_hour'), paper)), plain(dawn));
  }
  // a scenery at home at dusk (Pumpkin patch) too: its dusk and night colours by night, the vines' green to orange by day
  const pk = t => labs(N, atHour(N, 'pumpkin_patch', 'dusk', t), PAGES[0]);
  assert.deepEqual(plain(pk('night')), plain(own(PAGES[0], 'pumpkin_patch')));
  const pkDay = pk('day').map(k => (hue(k) * 180 / Math.PI + 360) % 360);
  assert.ok(pkDay[0] > 100 && pkDay[0] < 150, 'the fewest the vines\' green');
  assert.ok(Math.abs(pkDay[3] - 60) < 25, 'the most pumpkin orange');
  // a day scenery whose trees take no tint at night (Chalkboard) keeps its yellow chalk at every hour
  if (CHALK) {
    const ch = t => labs(N, atHour(N, 'chalkboard', 'day', t), PAGES[0]);
    assert.deepEqual(plain(ch('dusk')), plain(ch('day')));
    assert.deepEqual(plain(ch('night')), plain(ch('day')));
  }
  // a mood sent before `home` was: a scenery with day colours is a night one
  assert.deepEqual(plain(N.__test.hourOf({ special: 'aurora', time: 'night', weather: 'clear' })), null);
  assert.equal(N.__test.hourOf({ special: 'aurora', time: 'day', weather: 'clear' }).share, 1);
});

test('the heatmap follows the forest\'s hour, the clock\'s or a fixed one alike; colours chosen on the Heatmap tab stay as chosen', () => {
  const N = NIGHT;
  // (the hour is the mood's: a fixed Day on a night scenery is its day, as the forest is)
  assert.deepEqual(plain(N.__test.hourOf({ special: 'aurora', time: 'day', home: 'night', clock: false, weather: 'clear' })),
    plain(N.__test.hourOf({ special: 'aurora', time: 'day', home: 'night', clock: true, weather: 'clear' })));
  assert.equal(N.__test.hourOf({ special: 'aurora', time: 'night', home: 'night', clock: false, weather: 'clear' }), null);
  for (const [N2, key, home] of [[AF, 'natural', 'golden_hour'], [N, 'aurora', 'night']]) {
    const mine = t => plain(N2.__test.shades(atHour(N2, key, home, t), PAGES[0], { colours: '#3c8d40' }).grass);
    assert.deepEqual(mine('night'), mine('day'));
  }
});

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
  // (Width: 680 px, 85% of the Forest width, or 85% of the room, never more than the room, whatever the view)
  const size = (width, fill) => ({ view: 'timeline', size: { width, fill } });
  assert.equal(AF.calendarWidthIn(size('forest', 'more'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('forest', 'more'), 800, 500), 500);
  assert.equal(AF.calendarWidthIn(size('full', 'more'), 800, 1300), 1105);
  assert.equal(AF.calendarWidthIn(size('fixed', 'bigger'), 800, 1300), 680);
  assert.equal(AF.calendarWidthIn(size('fixed', 'bigger'), 800, 600), 600);
  assert.equal(AF.calendarWidthIn(size('full', 'bigger'), 800, 1300), 1105);
  assert.equal(AF.calendarMost(size('forest', 'more'), 800), 680);  // (beside the list alone)
  assert.equal(AF.calendarMost(size('full', 'more'), 800), Infinity);
  assert.equal(AF.calendarColumnShare(size('full', 'more')), 0.85);  // (85% of the room beside the list)
  assert.equal(AF.calendarColumnShare(size('forest', 'more')), 1);
  assert.equal(AF.calendarWant(size('forest', 'more')), 'forest');
  assert.equal(AF.calendarFull(size('full', 'more')), true);
  assert.equal(AF.calendarScaleFor(10), 1.4);  // (never under 1.4 css px a pixel)
  assert.equal(AF.calendarScaleFor(3 + 7 * 10 + 15), 1.4);
  assert.equal(AF.calendarScaleFor((3 + 7 * 10 + 15) * 3), 3);
});

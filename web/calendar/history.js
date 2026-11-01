/* Memory Forest — the study heatmap's model: every day of your history with its streaks, shades and
 * marks (history), and which days each view shows: Streak view's rows, Timeline's months, By year's
 * year (windowOf), in weeks (columns). No drawing here. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { STATE, SHOWN_STREAK, TROPHIES, DAY_MS, TODAY_AT, DAY_K, SWIPED_AHEAD, utc, dow, yearOf } = Cal;

// the four shades split your days studied in the last year at these shares (fewest to most):
// the most only your top tenth, so it marks your exceptional days rather than a whole busy season
const SHADE_SPLITS = [0.4, 0.7, 0.9], SHADE_SPAN = 365;
// (Pace's the other way round, its strongest shade the fastest: only your fastest tenth)
const PACE_SPLITS = [0.1, 0.3, 0.6];

/* every day by its offset from today (0 today, -1 yesterday, 1 tomorrow): its reviews or cards
 * due, the streaks (runs of days studied), the breaks long enough to make a pond, and the
 * review counts that split your days into the four shades */
function history(cal) {
  const today = utc(cal.start) + (cal.days.length - 1) * DAY_MS;
  const first = 1 - cal.days.length;  // the first day counted
  // (a start date leaves your record whole: `fs`, the day the forest began, only dims the days
  // before it, brings the animals from it on, and the ponds, the forest's, are only after it)
  const n = o => o > 0 ? cal.due[o] || 0 : o >= first ? cal.days[o - first] || 0 : 0;
  const fs = cal.forestStart ? (utc(cal.forestStart) - today) / DAY_MS : null;
  // (with the trees from before it kept, `cf`: the start date a streak counted from it begins on;
  // nothing is dimmed, as the forest has trees from before it)
  const cf = cal.countsFrom ? (utc(cal.countsFrom) - today) / DAY_MS : fs;
  // the days with no review and nothing due (study_log.load_free_days): a streak passes over
  // them, neither broken nor growing
  const free = new Set();
  for (const [older, newer] of cal.free || []) for (let a = newer; a <= older; a++) free.add(-a);
  // the days off a streak of 6 or 5 days a week passes over (payload._days_off): drawn as a day with
  // nothing due; only their tooltip tells them apart
  const daysOff = new Set((cal.daysOff || []).map(a => -a));
  daysOff.forEach(o => free.add(o));
  const runs = [], pond = new Set();
  let run = null;
  for (let o = first; o <= 0; o++) {
    if (n(o)) {
      // (a streak runs on over the forest's start date, your real one, as the caption counts it;
      // unless the Decks tab says to count it from the start date too)
      // (its length is in days studied: `days`)
      // (from the first day studied on or after it, even when the start date itself was free or a day off)
      if (run && !(cal.streakFromStart && cf !== null && run.from < cf && o >= cf)) { run.to = o; run.days++; } else runs.push(run = { from: o, to: o, days: 1 });
    } else {
      if (!free.has(o)) run = null;
    }
  }
  // the forest's own ponds (payload: its trees' gaps), the days in them not studied: a deck's
  // forest has the main forest's breaks, not the days away from that deck alone
  for (const [a, b] of cal.ponds || []) for (let o = (utc(a) - today) / DAY_MS; o <= (utc(b) - today) / DAY_MS; o++) if (!n(o)) pond.add(o);
  // a streak lives on through today until today ends, and over the days with nothing due since
  // its last day studied (forest_data._streaks)
  const end = runs[runs.length - 1];
  let current = end || null;
  for (let o = end ? end.to + 1 : 0; current && o < 0; o++) if (!free.has(o)) current = null;
  // (counted from the start date, a streak that ended before it is none of yours now, as the caption has it)
  if (current && cal.streakFromStart && cf !== null && current.to < cf) current = null;
  // the streak a day belongs to (a day with nothing due since the current one's last day, its)
  const runOf = o => runs.find(r => o >= r.from && o <= r.to) || (current && o > current.to && o <= 0 ? current : null);
  // your three longest streaks (of SHOWN_STREAK days or more; the first to reach a length ranks
  // above a later one as long), each with a trophy at its last day: gold, silver, bronze
  const podium = new Map(runs.filter(r => r.days >= SHOWN_STREAK)
    .sort((a, b) => b.days - a.days || a.from - b.from).slice(0, TROPHIES.length).map((r, i) => [r, i]));
  // the goal: the day the current streak, kept up, earns its next trophy: the third-longest's, then
  // the second's, then the longest's; none once it is the longest already
  let goal = null;
  if (current) {
    const others = runs.filter(r => r !== current && r.days >= SHOWN_STREAK).map(r => r.days).sort((a, b) => b - a);
    const len = current.days, need = i => Math.max(SHOWN_STREAK, (others[i] || 0) + 1);
    // (the next place up: the trophy it would hold once long enough, the third at most, or, once it
    // holds it, the one above; none once it is the longest)
    const place = Math.min(others.filter(d => d >= len).length, TROPHIES.length - 1);
    const rank = len < need(place) ? place : place - 1;
    // (the days still to study, from today, or from tomorrow once today is studied)
    if (rank >= 0) goal = { o: (current.to === 0 ? 1 : 0) + need(rank) - len - 1, rank, beats: others[rank] || 0 };
  }
  // the shades: where your days studied in the last year split into four (at least 1 apart), by
  // their reviews, or by the seconds those took (`by`: the toggle beside the arrows)
  const splitsOf = vals => {
    vals.sort((a, b) => a - b);
    const splits = [1];
    for (const share of SHADE_SPLITS) splits.push(Math.max(splits[splits.length - 1] + 1, vals.length ? vals[Math.floor(share * (vals.length - 1))] + 1 : splits.length * 50));
    const lv = v => splits.reduce((at, s, i) => v >= s ? i : at, 0);  // 0 the fewest .. 3 the most
    lv.splits = splits;
    return lv;
  };
  const time = o => (cal.time || [])[o - first] || 0;  // (seconds a day's reviews took, as the days are kept)
  const recent = [], recentTime = [];
  let busiest = 1;
  for (let o = Math.max(first, 1 - SHADE_SPAN); o <= 0; o++) if (n(o)) { recent.push(n(o)); if (time(o)) recentTime.push(time(o)); }
  for (let o = 1; o <= Math.min(SHADE_SPAN, cal.due.length - 1); o++) busiest = Math.max(busiest, n(o));
  const byReviews = splitsOf(recent), byTime = splitsOf(recentTime);
  // (by time, each split just under a whole minute, 5 minutes from half an hour: the key's "Under
  // 45 min" then holds for every day whose tooltip says less, and reads as a round number)
  const snap = s => { const m = Math.max(1, Math.round(s / 60)); return (m >= 30 ? Math.round(m / 5) * 5 : m) * 60 - 30; };
  // (the first just under a minute at the least, 30 s: never 61 s, past days its tooltips call "a minute")
  for (let i = 1, t = byTime.splits; i < t.length; i++) t[i] = Math.max(i === 1 ? 30 : t[i - 1] + 60, snap(t[i]));
  const dueShade = v => Math.min(3, Math.floor(4 * Math.log(v) / Math.log(busiest + 1)));
  // a day's median seconds per answer (payload: to a tenth, as its tooltip writes it), or null
  // (kept to the tenth here too, so a shade never contradicts the tooltip: "Under 3.3 s")
  const answerTime = o => { const v = (cal.answerTime || [])[o - first]; return v == null ? null : Math.round(v * 10) / 10; };
  // (Pace, the one shading by answer time: its splits from your answers' medians, as the others',
  // in tenths of a second; the fastest its strongest shade)
  const paces = [];
  for (let o = Math.max(first, 1 - SHADE_SPAN); o <= 0; o++) if (n(o) && answerTime(o) !== null) paces.push(answerTime(o));
  paces.sort((a, b) => a - b);
  const paceSplits = [0];
  for (const share of PACE_SPLITS) paceSplits.push(Math.max(paceSplits[paceSplits.length - 1] + 0.1,
    paces.length ? Math.ceil(paces[Math.floor(share * (paces.length - 1))] * 10) / 10 : paceSplits.length * 5));
  const paceLevel = v => paceSplits.reduce((at, sp, i) => v >= sp ? i : at, 0);  // 0 the fastest .. 3 the slowest
  paceLevel.splits = paceSplits;
  const paced = paces.length > 0;
  const by = cal.shadeBy === 'median' && paced ? 'median' : cal.shadeBy === 'time' && recentTime.length ? 'time' : 'reviews';
  const H = { by, answerTime, paced, timed: recentTime.length > 0 };
  // (a day studied with no answer time yet, read before it: a typical day's shade, the one the
  // median of your days takes, never Slow's; no swatch in the key lights it)
  const typical = paced ? 3 - paceLevel(paces[Math.floor(paces.length / 2)]) : 0;
  H.timeless = o => H.by === 'median' && answerTime(o) === null;
  H.shade = o => H.by === 'median' ? (answerTime(o) === null ? typical : 3 - paceLevel(answerTime(o)))
    : H.by === 'time' ? byTime(time(o)) : byReviews(n(o));
  H.splits = () => (H.by === 'median' ? paceLevel : H.by === 'time' ? byTime : byReviews).splits;
  // the animals, each on the day it came (none before the forest began)
  const animals = new Map();
  for (const a of cal.animals || []) if (-a.ago >= (fs !== null ? fs : first)) animals.set(-a.ago, (animals.get(-a.ago) || []).concat([a]));
  return Object.assign(H, {
    today, first, n, fs, cf, free, daysOff, runs, pond, current, runOf, podium, goal, animals,
    // (with the reviews before the forest's start date left out, Heatmap tab: the day it began)
    hid: cal.hiddenBefore ? (utc(cal.hiddenBefore) - today) / DAY_MS : null,
    // the days you marked, each with its icon and name (an older version's: a bare date)
    marked: new Map((cal.marks || []).map(m => typeof m === 'string' ? { day: m } : m).filter(m => m && m.day)
      .map(m => [(utc(m.day) - today) / DAY_MS, { icon: m.icon || 'pin', name: m.name || '' }])),
    // each day's cards since deleted: still counted in its reviews, but its click can't list them
    gone: new Map((cal.gone || []).map(([ago, count, of]) => [-ago, [count, of || count]])),
    dueShade, dueToday: cal.due[0] || 0,
    look: cal.look || null,  // the Heatmap tab's colours and tiles (paletteOf)
    ahead: cal.due.length - 1,  // the last day ahead counted
    // (and the last with cards due: Streak view pages on that far, no further into rows of nothing)
    lastDue: Math.max(0, ...cal.due.map((v, o) => (v > 0 ? o : 0))),
    time
  });
}

/* Streak view: one continuous strip of weeks, as By year draws them (no space between months),
 * wrapped into rows of `W` weeks each (weeksPerRow), oldest at the top. It opens on your streak: rows
 * ending ROWS_AHEAD weeks after this one, back to the one that holds the first day of the streak
 * worth seeing - the current one, and the last one before it of SHOWN_STREAK days or more while it
 * is longer than the current one and broke at most BROKE_LATELY days before it began (a long streak
 * just broken, then three days: the broken one is what people look for; one passed since, or broken
 * months ago, not); with neither, your latest streak. ‹ › page back and on as Timeline's do, as
 * many rows at a time as it opened with (`page`: the stretch paged to, { end, from }, or null for
 * your streak's; `ahead`: pages on from your streak, into the days ahead, no further than the row
 * with the last day due), but a page that would cut a streak with a bracket of its own at its top
 * reaches up to that streak's first week instead, the whole streak in view, and every day still on
 * some page (pageBefore) */
const BROKE_LATELY = 30, ROWS_AHEAD = 8;
function reachOf(H) {
  const now = H.current ? H.current.days : 0, began = H.current ? H.current.from : 1;
  const long = H.runs.filter(r => r !== H.current && r.days >= SHOWN_STREAK && r.days > now && began - r.to <= BROKE_LATELY)
    .sort((a, b) => b.to - a.to)[0];
  return long || H.current || H.runs[H.runs.length - 1] || null;  // (none: no study yet)
}
// rows of whole weeks ending `end` (a week's last day), oldest first, back to the one holding `start`
// (never before your first review's), each `cols` weeks wide
function rowsOf(H, end, start, W) {
  const out = [];
  for (let to = end; ; to -= W * 7) {
    const from = to - W * 7 + 1;
    out.unshift({ from, to, cols: W });
    if (from <= start || from <= H.first) return out;
  }
}
// the rows Streak view opens on: back to the streak worth seeing, on to ROWS_AHEAD weeks after this one
function openRows(H, W) {
  const lead = reachOf(H);
  return rowsOf(H, 6 - dow(H.today) + ROWS_AHEAD * 7, lead ? lead.from : 0, W);
}
function streakRows(H, W, page, ahead = 0) {
  const open = openRows(H, W), n = open.length;
  if (ahead) {  // (› from your streak: pages on into the days ahead, up to the row with the last day due)
    const last = open[n - 1].to, due = Math.max(1, Math.ceil((H.lastDue - last) / (W * 7)));
    return rowsOf(H, last + Math.min(ahead * n, due) * W * 7, -Infinity, W).slice(-n);
  }
  return page == null ? open : rowsOf(H, page.end, page.from, W);
}
// the page before the one starting `top` (a week's first day), `n` rows of W weeks: { end, from },
// ending the day before it; reaching further up when a streak of SHOWN_STREAK days or more its top
// would cut starts less than a page above it (to that streak's first week; one longer stays cut)
function pageBefore(H, W, n, top) {
  const end = top - 1, from = end - n * W * 7 + 1;
  const cut = H.runs.find(r => r.days >= SHOWN_STREAK && r.from < from && r.to >= from);
  if (!cut) return { end, from };
  const week = cut.from - dow(H.today + cut.from * DAY_MS);
  return { end, from: from - week < n * W * 7 ? week : from };
}
// the weeks a row holds at this width (css px): a year's at least; with More months as many as fit at
// the days' own size (DAY_K), with Bigger days a year's, stretched
const weeksPerRow = width => (STATE.BIGGER || !width ? 53 : Math.max(53, Math.floor((width / DAY_K - 1) / STATE.CELL)));
// css px between two of Streak view's rows (forest.css .af-cal-past-year's margin); an earlier row's
// month labels stand over its weeks as the last row's do (monthsRoom): each row's weeks the same
// distance under its labels' baseline, and the rows evenly apart, the last one too
const ROW_GAP = 4;
const NOTE_H = 11;  // css px: a streak's note line (forest.css .af-cal-note), centred on the brackets' lane
const ACTS_ROOM = 20;  // (and forest.css's `.af-cal-grid > .af-cal-acts { top: -20px }`, before the row is laid out)

// the views (state.CALENDAR_VIEWS): Timeline, By year, and Streak, whose year in view is drawn as By
// year's is, with the earlier years of its frame above it
const VIEWS = ['timeline', 'by_year', 'streak'];
const viewOf = v => (VIEWS.includes(v) ? v : 'timeline');
const yearly = v => v === 'by_year' || v === 'streak';
/* the days a view shows, [from, to] as offsets: Timeline's `count` months (ten, fewer when
 * narrow), `page` months back (negative) or on; the phone's whole
 * history, swiped along; or a year's January to December (By year's, Streak view's) */
function windowOf(H, view, page, year, count) {
  if (view === 'swiped') {  // the phone's: from the first month counted to a few months ahead, swiped along
    const f = new Date(H.today + H.first * DAY_MS), t = new Date(H.today);
    return { from: (Date.UTC(f.getUTCFullYear(), f.getUTCMonth(), 1) - H.today) / DAY_MS,
      to: (Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + SWIPED_AHEAD + 1, 1) - H.today) / DAY_MS - 1, apart: true };
  }
  if (yearly(view)) {
    const y = year || yearOf(H.today);
    return { from: (Date.UTC(y, 0, 1) - H.today) / DAY_MS, to: (Date.UTC(y, 11, 31) - H.today) / DAY_MS, year: y };
  }
  // Timeline: this month TODAY_AT along (ten months: seven before it and two after), the
  // past being the story; `page` months back (negative) or on
  const t = new Date(H.today), y = t.getUTCFullYear(), m = t.getUTCMonth() - Math.round(count * TODAY_AT) + page;
  return { from: (Date.UTC(y, m, 1) - H.today) / DAY_MS, to: (Date.UTC(y, m + count, 1) - H.today) / DAY_MS - 1, apart: true };
}

/* the days of a view in weeks, [offset, ms, column, row], its first day on top; Timeline starts each
 * month in a column of its own (By year runs its months on in the same weeks). (Timeline: a month
 * that starts its week, the one before having filled its last, has no ragged edge to set it apart,
 * so an empty column comes between them) */
function columns(H, win) {
  const out = [];
  let col = 0;
  for (let o = win.from; o <= win.to; o++) {
    const ms = H.today + o * DAY_MS, row = dow(ms), first = o === win.from, starts = win.apart && new Date(ms).getUTCDate() === 1;
    if (!first && starts) col += row === 0 ? 2 : 1;
    else if (!first && row === 0) col++;
    out.push([o, ms, col, row]);
  }
  return out;
}

/* how many low-res pixels across a view's weeks are: its last week's right edge; By year's every
 * year as wide as the widest it pages to, so the earlier years shown above it line up with it (a
 * leap year starting on its weeks' last day needs 54 weeks, the rest 53 at most) */
function weeksWidth(H, win, lastCol) {
  if (win.cols) return 1 + Math.max(win.cols, lastCol + 1) * STATE.CELL;  // (Streak view's rows: all as wide)
  if (win.year == null) return 1 + (lastCol + 1) * STATE.CELL;
  if (!H.yearCols) {
    H.yearCols = 0;
    for (let y = yearOf(H.today + H.first * DAY_MS); y <= yearOf(H.today + H.ahead * DAY_MS); y++) {
      const jan1 = Date.UTC(y, 0, 1), days = (Date.UTC(y + 1, 0, 1) - jan1) / DAY_MS;
      H.yearCols = Math.max(H.yearCols, Math.floor((dow(jan1) + days - 1) / 7) + 1);
    }
  }
  return 1 + Math.max(H.yearCols, lastCol + 1) * STATE.CELL;
}

Object.assign(Cal, { history, openRows, streakRows, pageBefore, weeksPerRow, ROW_GAP, NOTE_H, ACTS_ROOM, VIEWS, viewOf, yearly, windowOf, columns, weeksWidth });
})();

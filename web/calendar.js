/* Memory Forest — the study calendar, under the forest or on its own: one tile a day in weeks
 * (starting on the day your system, or the setting, says), as the Review Heatmap add-on draws
 * them. A day studied is in the scenery's colour, standing out more from the page the more you
 * reviewed (measured against your own days, so every pace uses all four shades); a missed day is
 * a faint tile (the tooltip says when a break made a pond); the days ahead are tilled soil,
 * stronger the more cards fall due. The milestones are the forest's own: each of its animals
 * (AF.VISITOR_SPRITES) stands on the day it came, in the scenery's own look for them (today's tile
 * keeps only its frame). The current streak has a
 * bracket under it, with the trophies and the goal ahead in a lane below. A click on a day opens
 * its cards in Anki's browser (actions.browse_calendar_day); a right-click pins it (marks.py).
 *
 * Two views, each fitted to the room there is: Timeline (`timeline`: ten months with this
 * month most of the way along, paged back and on with ‹ ›; on the phone, the whole history swiped
 * along) and By year (`by_year`: January to December). payload.py sends data.calendar = { view,
 * start, days, due, time, shadeBy, look, animals, ponds, browse, marks, forestStart, streakFromStart, weekStart }:
 * the date of the first day counted, the reviews of each day from it to today, the cards due on
 * each day from today on, the day each animal came, the forest's own ponds, whether a
 * click opens a day, the days you pinned, the forest's start date (if any), whether the streak
 * restarts there, and the weekday the weeks start on. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { hashStr, hex, rgb, layer, esc, mix, cap, send, animates } = AF.u;
const { SEEDLING } = AF.STAGE;

// low-res pixels: a day's square, the tile drawn in it, a little room above the weeks under the
// months' labels (every mark sits on its own day's tile), and the streak lane below the weeks: the
// brackets, with the trophies and the goal pennant under them
const TILE = 9, TOP = 3, ROWS = 7, BRACKET = 15, GAP = 1;
// a day's cell, its tile and the space after it: set by each heatmap measured or drawn, the space
// GAP but a style's own where it has one (look.gap: Round's 2), as weekStart is
let CELL = TILE + GAP;
const cellOf = cal => TILE + (cal && cal.look && Number.isInteger(cal.look.gap) ? cal.look.gap : GAP);  // (TOP: room between the months' labels and the weeks)
// css pixels: the footer's row (the journal and the key), the month labels' band and the streaks'
// notes (forest.css), for the room kept for the calendar before it is drawn
const FOOT_H = 18, FOOT_GAP = 7, ROW_UNDER = 20;  // (ROW_UNDER: the first row's top under the months' row, its baseline 8px above it)
const LABEL_END = 30;  // css px: a month's label starting this close to the row's end is left out
// the smallest scale the pixels stay crisp at, in device pixels; below it they are smoothed, and
// Timeline shows fewer months
const SHARP = 1.5;
const SHOWN_STREAK = 30;  // an earlier streak this long or longer gets a bracket of its own
// the trophies of your longest streaks, first to third: a cup on a stand, in pixels (G the
// metal, L its shine, D its shade), and each one's metal
const TROPHY = ['GGGGGGG', 'G.GLG.G', 'G.GLG.G', '.GGGGG.', '..GGG..', '...D...', '..DDD..', '.DDDDD.'];
const TROPHIES = [
  { G: '#e3b04b', L: '#fff3c4', D: '#a8782a', place: 'longest' },
  { G: '#c9ccd1', L: '#f6f7f9', D: '#8b9098', place: 'second-longest' },
  { G: '#c4834a', L: '#ecc196', D: '#8a5528', place: 'third-longest' }
].map(t => ({ frames: [TROPHY], pal: { G: t.G, L: t.L, D: t.D }, place: t.place }));
// a day you marked as important (marks.py), with the icon you picked for it, all in the pin's red
// (red is the mark that is yours): R red, L its shine, D a dark detail; `label` names a mark you
// didn't name. Their order is marks.ICONS', the order a click on the icon steps through them.
const MARK_PAL = { R: '#e0524a', L: '#ffb3a8', W: '#fff1ec', D: '#8a7a6a', K: '#1c1a1a' };
const MARK_ICONS = {
  // (six by six each, so one sits centred, a pixel clear all round, on the eight a tile shows before
  // its edge or gap: TILE_FACE)
  pin: { label: 'Pin', rows: ['.RRRR.', 'RRWWRR', 'RRWWRR', 'RRRRRR', '.RRRR.', '..RR..'] },
  exam: { label: 'Exam', rows: ['RRRRRR', 'KRWWWR', 'RRRRRR', 'KRWWWR', 'RRRRRR', 'KRRRRR'] },
  trip: { label: 'Trip', rows: ['..RR..', '..RR..', '.RRRR.', 'RRRRRR', '..RR..', '.RRRR.'] },  // (a plane from above, nose up: on its side it read as a red cross)
  birthday: { label: 'Birthday', rows: ['..LL..', '..DD..', '.RRRR.', '.WRWW.', 'RRRRRR', 'RRRRRR'] },
  star: { label: 'Star', rows: ['..RR..', '..RR..', 'RRWRRR', '.RRRR.', '.RRRR.', 'RR..RR'] },
  heart: { label: 'Heart', rows: ['RR..RR', 'RRRRRR', 'RWRRRR', 'RRRRRR', '.RRRR.', '..RR..'] },
  done: { label: 'Done', rows: ['......', '.....R', '....RR', 'R..RR.', 'RRRR..', '.RR...'] },
  sick: { label: 'Sick', rows: ['......', 'R.....', 'RLL...', 'RLLWWR', 'RRRRRR', 'R....R'] },  // (a head on the pillow, a sheet over them: a bare bed read as a flag)
};
const MARK_ORDER = Object.keys(MARK_ICONS);
for (const m of Object.values(MARK_ICONS)) m.spr = { frames: [m.rows], pal: MARK_PAL };
const markOf = m => MARK_ICONS[m && m.icon] || MARK_ICONS.pin;
// a mark's line in its day's tooltip: its name (or its icon's), and how far off it is
const markLine = (m, o) => {
  const name = m.name || markOf(m).label;
  return o > 1 ? `${name} in ${o} days` : o === 1 ? `${name} tomorrow` : o === 0 ? `${name} today` : name;
};
// the goal ahead: a pennant on the day the current streak would pass the next record, gold when
// it would be your longest, silver your second-longest (P its pole, G the metal, L its shine)
const GOAL = ['PGGGG', 'PGGLG', 'PGGG.', 'PG...', 'P....', 'P....', 'P....', 'P....'];
const GOALS = TROPHIES.map(t => ({ frames: [GOAL], pal: { P: '#8a7a6a', G: t.pal.G, L: t.pal.L }, place: t.place }));
const GOAL_LINE = 0.75;  // the dotted line from today to the goal: gold, this strong (on a dark page)
// the trophies' and the pennant's metals on a light page, by their own metal: gold, silver, bronze
const METALS_ON_LIGHT = { '#e3b04b': { G: '#b07d1e', L: '#e3b04b', D: '#8f6a1c' }, '#c9ccd1': { G: '#8b9098', L: '#c9ccd1', D: '#6f747c' },
  '#c4834a': { G: '#a8692f', L: '#c4834a', D: '#7a4a22' } };
const PINE_PERCENT = 28;
// the four shades split your days studied in the last year at these shares (fewest to most):
// the most only your top tenth, so it marks your exceptional days rather than a whole busy season
const SHADE_SPLITS = [0.4, 0.7, 0.9], SHADE_SPAN = 365;
// (Pace's the other way round, its strongest shade the fastest: only your fastest tenth)
const PACE_SPLITS = [0.1, 0.3, 0.6];
// the days ahead by their cards due, on a log scale up to the busiest day in the next year (due
// counts fall away steadily, so a quarter of the days each would light only the next weeks).
// The days that sit back, faded this far into the page's colour, light or dark: the days ahead
// (their soil) and the days before the forest's start date (your record, not the forest's time)
const FADE = 0.5;
const TILE_VARIANTS = 4;
const TILE_FACE = TILE - 1;  // a tile's face: all but its last row and column (a plain tile's edge, a scenery's own tile's gap)
const DAY_MS = 86400000;
const MONTHS_SHOWN = 10, MONTHS_MIN = 3, TODAY_AT = 0.7;  // Timeline: ten months, fewer when narrow; this month this far along
// the phone: the calendar is one long timeline swiped along (no buttons to page with), its pixels
// this many css pixels each, running this many months past this one
const SWIPED_K = 1.4, SWIPED_AHEAD = 5, SWIPED_TODAY_AT = 0.75;  // (and opened with today this far across)
const LABEL_GAP = 6, TIP_GAP = 8;  // css px between two month labels, and between a day and its tooltip
const SPOT_DIM = 0.72;  // the days a hover is not about: this far into the page (a key's shade, a month, a streak)
const TIP_WAIT = 150;  // ms the first tooltip waits, the pointer just come onto the heatmap
const SWIPE_PX = 40, SWIPE_QUIET = 250, SWIPE_AGAIN = 1.5;  // a trackpad's sideways swipe: css px to turn a page; ms still that ends it; how much faster than the last step a new swipe starts
const DAYS_ROOM = 28, NOTE_ROOM = 44, SINCE_ROOM = 150;  // css px: room the weekdays need left of the forest; a streak's length under its bracket, and its "Since" date beside it
const THEME_SETTLE_MS = 400;  // a page whose colour eases to the new theme has got there by then
// low-res px round an animal, a pin or a trophy that a finger's tap still counts for; css px a tap may move
const TOUCH_PAD = 6, TAP_SLOP = 10;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const deep = v => Array.isArray(v) ? v.map(deep) : hex(v);
const P = {};
Object.entries({
  // a day ahead's tilled soil, from a light day to a heavy one: on a dark page, earthy browns
  // (faded into it, they stay soil)
  tillDark: [['#a48d6e', '#9a8465'], ['#836f56', '#7a674f'], ['#63523f', '#5b4b39'], ['#45372a', '#3e3125']],
  tillDarkEdge: ['#8a7559', '#6c5b45', '#4f4132', '#33281e'],
  // and on a light page warmer ones, from tan to loam (the earthy ones faded towards white go grey)
  till: [['#d2a86e', '#c99e64'], ['#b07a42', '#a6713a'], ['#87552a', '#7d4d25'], ['#5c3517', '#532f13']],
  tillEdge: ['#b8905a', '#925f30', '#6b411d', '#44260f'],
  gold: '#e3b04b', goldOnLight: '#a8782a', past: '#9a8a74',
  // today's frame: light on a dark page, dark on a light one
  today: '#f4e3a0', todayOnLight: '#5e4a22'
}).forEach(([k, v]) => { P[k] = deep(v); });

const utc = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const iso = ms => new Date(ms).toISOString().slice(0, 10);
// a day as the forest's tooltips write it (AF.u.fmtDate), with its weekday, in English as the rest
const fmt = ms => AF.u.fmtDate(iso(ms));
const weekday = ms => new Date(iso(ms) + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' });
// a day's row: 0 on the day the weeks start (payload.WEEK_START_DAYS: Monday unless the system
// or the setting says otherwise), as the page counts days (Sunday 0)
let weekStart = 1;
const dow = ms => (new Date(ms).getUTCDay() - weekStart + 7) % 7;
const num = n => n.toLocaleString('en');
const yearOf = ms => new Date(ms).getUTCFullYear();
// a stretch of time in seconds, in minutes: "under a minute", "a minute", "48 min", "1 hr 12 min"
const lasted = secs => {
  const m = Math.round(secs / 60);
  return m < 1 ? 'under a minute' : m === 1 ? 'a minute' : m < 60 ? `${m} min` : m >= 600 ? `${Math.round(m / 60)} hr` : `${Math.floor(m / 60)} hr${m % 60 ? ` ${m % 60} min` : ''}`;
};

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
      if (run && !(cal.streakFromStart && fs !== null && run.from < fs && o >= fs)) { run.to = o; run.days++; } else runs.push(run = { from: o, to: o, days: 1 });
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
  if (current && cal.streakFromStart && fs !== null && current.to < fs) current = null;
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
    today, first, n, fs, free, daysOff, runs, pond, current, runOf, podium, goal, animals,
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
    time
  });
}

/* By year's earlier years, shown all at once under the year in view by its "earlier years" switch:
 * back to the one the streaks worth seeing began in - the current one, and the last one before it of
 * SHOWN_STREAK days or more while it is longer than the current one and broke at most BROKE_LATELY
 * days before it began (a long streak just broken, then three days: the broken one is what people
 * look for; one passed since, or broken months ago, not) - and with neither before the year in
 * view, every year; `all`: every year, back to your first review ("Show all years", under them).
 * Never before your first review; newest first */
const BROKE_LATELY = 30;
function reachOf(H) {
  const now = H.current ? H.current.days : 0, began = H.current ? H.current.from : 1;
  const long = H.runs.filter(r => r !== H.current && r.days >= SHOWN_STREAK && r.days > now && began - r.to <= BROKE_LATELY)
    .sort((a, b) => b.to - a.to)[0];
  const starts = [H.current, long].filter(Boolean).map(r => r.from);
  return starts.length ? Math.min(...starts) : 0;  // (none: nothing short of every year to offer)
}
function pastYears(H, shown, all) {
  const lo = Math.max(yearOf(H.today + H.first * DAY_MS), yearOf(H.today + (all ? H.first : reachOf(H)) * DAY_MS)), out = [];
  for (let y = shown - 1; y >= lo; y--) out.push(y);
  return out;
}
// the earlier years shown for a state (false, true or 'all'): true reaches the streak worth seeing,
// or, where that began in the year in view, every year (nothing short of them to offer)
function yearsFor(H, shown, state) {
  if (!state) return [];
  const streak = pastYears(H, shown, false);
  return state === 'all' || !streak.length ? pastYears(H, shown, true) : streak;
}
// css px: with the earlier years shown, the room over the year in view's months for the controls
// shown on hover (and the switch by them), which closed sit in the band over the months
const NOTE_H = 11;  // css px: a streak's note line (forest.css .af-cal-note), centred on the brackets' lane
const ACTS_ROOM = 20;  // (and forest.css's `.af-cal-grid > .af-cal-acts { top: -20px }`, before the row is laid out)

/* the days a view shows, [from, to] as offsets: Timeline's `count` months (ten, fewer when
 * narrow), `page` months back (negative) or on; the phone's whole
 * history, swiped along; or By year's January to December */
function windowOf(H, view, page, year, count) {
  if (view === 'swiped') {  // the phone's: from the first month counted to a few months ahead, swiped along
    const f = new Date(H.today + H.first * DAY_MS), t = new Date(H.today);
    return { from: (Date.UTC(f.getUTCFullYear(), f.getUTCMonth(), 1) - H.today) / DAY_MS,
      to: (Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + SWIPED_AHEAD + 1, 1) - H.today) / DAY_MS - 1, apart: true };
  }
  if (view === 'by_year') {
    const y = year || yearOf(H.today);
    return { from: (Date.UTC(y, 0, 1) - H.today) / DAY_MS, to: (Date.UTC(y, 11, 31) - H.today) / DAY_MS, year: y };
  }
  // Timeline: this month TODAY_AT along (ten months: seven before it and two after), the
  // past being the story; `page` months back (negative) or on
  const t = new Date(H.today), y = t.getUTCFullYear(), m = t.getUTCMonth() - Math.round(count * TODAY_AT) + page;
  return { from: (Date.UTC(y, m, 1) - H.today) / DAY_MS, to: (Date.UTC(y, m + count, 1) - H.today) / DAY_MS - 1, apart: true };
}

/* the four shades a day studied takes, fewest reviews to most, with their tiles' edges: built
 * round the scenery's colour (its own `calendar` colour, or its most colourful crown colour,
 * AF.foliage), from pale to deep, so the calendar belongs to the scene */
const DARK = [16, 16, 16];
// an empty day's grey on a dark page (EMPTY), the least the faintest shade stands apart from it
// (OKLab), and how much lighter it is made when closer (heatmap_look.py has the same sums)
const EMPTY_GREY = [128, 128, 128], EMPTY_ALPHA = 0.11, EMPTY_APART = 0.06;
const EMPTY_ALPHA_LIGHT = 0.2;
const blankOn = paper => mix(paper.bg, EMPTY_GREY, paper.dark ? EMPTY_ALPHA : EMPTY_ALPHA_LIGHT);  // (an empty day's grey over the page)
/* the four shades of colours you picked (yours, the ready ones), the same on a light page and a
 * dark one: the busiest exactly the last colour, the others stepping to it from the first through
 * OKLab; with one colour, from dim to full, dimmed into the page (its hue kept). Only the faintest
 * fades into the page a little (FAINT_FADE), so the quiet days sit back, less where it would come
 * too near an empty day */
const FAINT_FADE = 0.25, FADE_STEP = 0.05, DIM = [0.55, 0.36, 0.18, 0];
function exactSteps(colours, paper) {
  const two = Array.isArray(colours), a = hex(two ? colours[0] : colours), b = two ? hex(colours[1]) : a;
  const at = (i, f) => two ? (i ? blend(a, b, i / 3) : mix(a, paper.bg, f)) : mix(a, paper.bg, i ? DIM[i] : f);
  const blank = blankOn(paper);
  let f = two ? FAINT_FADE : DIM[0];
  while (f > 0 && apart(at(0, f), blank) < EMPTY_APART) f = Math.max(0, f - FADE_STEP);
  return [0, 1, 2, 3].map(i => (i === 3 ? b : at(i, f)));
}
const apart = (a, b) => { const p = oklab(a), q = oklab(b); return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]); };
// a light page's four shades: their lightness (OKLab L), fewest reviews to most, and the least
// colourfulness they keep (a near-grey key would otherwise give grey tiles)
const LIGHT_STEPS = [0.82, 0.69, 0.56, 0.43], LIGHT_CHROMA = 0.08;  // (0.86 sat too near a missed day's grey)
// and a dark page's, from a clear dim colour to a pale bright one: the middle two at 0.10-0.11 apart
// (OKLab x100) read as one in a small tile; these, from a search over every scenery, put
// every neighbour at least 12.6 apart and the fewest a step off a missed day's grey, in the room
// Anki's lighter dark page leaves; each shade's share of its key's colourfulness rises to the third,
// and the top keeps only half: a vivid colour that light glowed (2026-10-14)
const DARK_STEPS = [0.45, 0.58, 0.72, 0.85], DARK_CHROMA = [0.6, 1.0, 1.0, 0.5];
/* `t` of the way from colour `a` to `b`, through OKLab, where equal steps look equal (a plain mix
 * of a blue and a green dips muddy in the middle) */
const lin = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
const unlin = v => 255 * Math.min(1, Math.max(0, v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055));
function oklab(c) {
  const [r, g, b] = c.map(lin);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b), m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b),
    s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
}
function blend(a, b, t) {
  const p = oklab(a), q = oklab(b);
  return fromOklab(...p.map((v, i) => v + (q[i] - v) * t));
}
function fromOklab(L, A, B) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3, m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3, s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3;
  return [unlin(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s), unlin(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    unlin(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)];
}
// whether an OKLab colour is one the screen can show (each channel, before it is clipped, in 0..1)
function fits(L, A, B) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3, m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3, s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s].every(v => v >= -0.0005 && v <= 1.0005);
}
// a scenery's colour kept within a lightness and saturation a tile can show: a silhouette
// scenery's near-black trees (Witch across the moon) would make every tile black
const KEY_L = [0.36, 0.56], KEY_S = 0.28;
function readable(c) {
  const [r, g, b] = c.map(v => v / 255), max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, sat = 0, l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6;
  }
  l = Math.min(KEY_L[1], Math.max(KEY_L[0], l)); sat = Math.max(KEY_S, sat);
  const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat, p = 2 * l - q;
  const ch = t => { t = (t + 1) % 1; return 255 * (t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p); };
  return [ch(h + 1 / 3), ch(h), ch(h - 1 / 3)];
}
/* The page the calendar sits on: its colour (the first background behind `el` with any, AF.u.pageBg;
 * on a phone's transparent card, the app's own, AF.u.appBg) and whether it is dark (Anki's dark mode). */
function pageOf(el) {
  const behind = [];
  for (let e = el; e && e.nodeType === 1; e = e.parentElement) behind.push(e);
  const bg = AF.u.pageBg(behind) || AF.u.appBg();
  return { bg, dark: bg[0] * 0.3 + bg[1] * 0.59 + bg[2] * 0.11 < 128 };
}
/* the shades run towards the page's opposite, so a day stands out the more you studied: darker
 * for more on a light page, brighter for more on a dark one (a dark page's pale tiles would
 * otherwise draw the eye to your quietest days) */
function shades(env, paper, look) {
  // (your colours and the ready ones are `exact`: as picked, on either page: exactSteps)
  // a scenery whose trees are not its colour names its own (`calendar`: Frozen market's ice blue),
  // or two, the fewest reviews' and the most's, for a ramp between them (Aurora's night blue to
  // its green): each shade then takes its own colour along it. The Heatmap tab's colours
  // (heatmap_look.py) come in the same way, as one colour or two (`look.colours`)
  const dark = paper.dark, chosen = look && look.colours, exact = !!(look && look.exact && chosen);
  const chroma = c => Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]), own = chosen || AF.envOf(env).calendar;
  const keys = Array.isArray(own) ? [0, 1, 2, 3].map(i => readable(blend(hex(own[0]), hex(own[1]), i / 3)))
    : Array(4).fill(readable(own ? hex(own) : AF.foliage(env).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a)));
  // (about evenly far apart; on a dark page the top one only a little towards white, so a busy
  // day never outshines the forest)
  // (on a light page each shade at its own lightness, in even steps from a clear light colour to a
  // deep one, keeping only the key's hue and colourfulness: mixed towards white and black they
  // went grey, and a ramp's dark start and bright end met in the same muddy middle; and the
  // texture stronger: the white between the tiles otherwise outshines them)
  const steps = (dark ? DARK_STEPS : LIGHT_STEPS).map((L, i) => {
    const k = oklab(keys[i]), h = Math.atan2(k[2], k[1]);
    // (where the colour is beyond the screen's, its colourfulness gives way, not its lightness: a
    // clipped neon pink came out darker than the shade under it)
    let C = Math.max(LIGHT_CHROMA, Math.hypot(k[1], k[2])) * (dark ? DARK_CHROMA[i] : 1);
    while (C > 0.01 && !fits(L, C * Math.cos(h), C * Math.sin(h))) C *= 0.95;
    return fromOklab(L, C * Math.cos(h), C * Math.sin(h));
  });
  // (your colours and the ready ones: as picked, exactSteps; a ready ramp the other way round on a
  // light page, its deep colour the busiest, as Review Heatmap's light mode: `flipLight`)
  const flip = exact && !dark && look.flipLight && Array.isArray(look.colours);
  if (exact) steps.splice(0, 4, ...exactSteps(flip ? look.colours.slice().reverse() : look.colours, paper));
  // (the Heatmap tab's "Busier days: Darker": a dark page's shades the other way round, a pale tint
  // for a quiet day down to a clear dim colour for a busy one, still well clear of a missed day's grey)
  if (dark && look && look.darker) steps.reverse();
  const tone = dark ? 0.07 : 0.16, rim = dark ? 0.22 : 0.3;
  return { grass: steps.map(c => [c, mix(c, DARK, tone)]), edge: steps.map(c => mix(c, DARK, rim)) };
}

/* the scene the calendar is drawn for: the forest's own (`env`, its theme and the look its
 * environment gave the animals), or with no forest showing, one made from the data alone */
function sceneOf(data, env) {
  if (!env) {
    env = { mood: data.mood, data, W: 200, H: 100, u: 1, theme: AF.theme(data.mood, data.stats, data.events) };
    const spec = AF.envOf(env);
    try { if (spec.prepare) spec.prepare(env); } catch { /* only its look for the animals is wanted */ }
  }
  // the scenery's trees in plain light (no hour's tint, haze or rim): the same at any hour
  return { theme: Object.assign({}, env.theme, { tint: null, tintAmt: 0, hzStep: 0, rim: null }), mood: env.mood, u: 1,
    layout: null, data: env.data, visitorTint: env.visitorTint };
}
function spriteOf(t, h, env) {
  try { return AF.pixel.sprite(t, h, 0, env); }
  catch { return AF.pixel.sprite(t, h, 0, Object.assign({}, env, { mood: Object.assign({}, env.mood, { special: 'natural' }) })); }
}
/* a missed day, a day ahead with nothing due, or one before your history, drawn empty: a faint
 * grey square (no edge of its own) that sits back on Anki's light and dark pages alike */
const EMPTY = `rgba(128, 128, 128, ${EMPTY_ALPHA})`, EMPTY_LIGHT = `rgba(128, 128, 128, ${EMPTY_ALPHA_LIGHT})`;  // (clearer on a light page, so the weeks hold together)
const FREE_MARK = 'rgba(128, 128, 128, 0.5)';  // a day with nothing due, outside any streak: a single pixel, darker grey
// a day a streak passed over (nothing due, or a day off) wears a ring in the heatmap's own colour: the
// first shade, from the faintest, this far (OKLab) from the empty grey it rings (the faintest on a dark
// page; on a light one, where it is nearly the grey, the second)
const REST_APART = 0.10;
const restShade = (pal, paper) => { const blank = blankOn(paper); let lv = 0; while (lv < 3 && apart(pal.grass[lv][0], blank) < REST_APART) lv++; return pal.grass[lv][0]; };
/* a 1px ring just inside a tile's face, its four corners left off, as the pixel tiles round theirs */
function restRing(g, x, y, F) { for (let i = 1; i < F - 1; i++) { g.fillRect(x + i, y, 1, 1); g.fillRect(x + i, y + F - 1, 1, 1); g.fillRect(x, y + i, 1, 1); g.fillRect(x + F - 1, y + i, 1, 1); } }
function empty(g, x, y, fill = EMPTY, T = TILE) { g.fillStyle = fill; g.fillRect(x, y, T, T); }
/* a tile's texture: two tones in 2x2 clusters and an edge, its four corners left off so it reads
 * soft and round at its size (2026-10-16: bevel, dither, a soft brush and an inset were tried; at
 * 1x only the corners showed). A scenery with a look of its own (Starry night's brushstrokes) draws
 * its tiles in it instead (`calendarTile(g, pal, edge, v, size)`: `pal` the shade and its darker
 * tone, `v` which of the TILE_VARIANTS) */
function plainTile(g, pal, edge, v, T) {
  // today's two-tone texture, its four corners left off, so a tile reads round at its size
  for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
    if ((x === 0 || x === T - 1) && (y === 0 || y === T - 1)) continue;
    const e = y === T - 1 || x === T - 1;
    g.fillStyle = rgb(e ? edge : pal[(hashStr(v + ',' + (x >> 1) + ',' + (y >> 1)) & 3) === 0 ? 1 : 0]);
    g.fillRect(x, y, 1, 1);
  }
}
/* a shade's tiles, each of its TILE_VARIANTS textures drawn once, kept for every calendar after */
const tiles = new Map();
function tilesOf(pal, edge, look, gapless = false) {
  const key = (look ? look.name : '') + (gapless ? '|whole' + CELL : '') + '|' + pal.concat([edge]).map(c => c.join(',')).join('|');
  if (!tiles.has(key)) {
    const out = [];
    for (let v = 0; v < TILE_VARIANTS; v++) {
      // (with no spaces between the days, a tile fills its whole cell: drawn a pixel bigger, so the
      // gap every tile style keeps in its last row and column falls outside it)
      const [cv, g] = layer(gapless ? CELL : TILE, gapless ? CELL : TILE);
      (look ? look.draw : plainTile)(g, pal, edge, v, gapless ? CELL + 1 : TILE);
      cv.fill = pal[0];  // (its colour, for Smooth: the rounded face filled, then its texture over it)
      out.push(cv);
    }
    tiles.set(key, out);
  }
  return tiles.get(key);
}
// a light colour the scenery gives its animals (Synthwave's neon) glows around them, and
const GLOW_FROM = 0.55, GLOW_ALPHA = 0.32;
// any other animal is outlined in the page's own colour, cut out of the tiles as the gaps
// between them are, so it reads at a tile's size on any shade
function drawAnimal(g, spr, x0, y0, tint, outline) {
  const rows = spr.frames[0], w = rows[0].length, at = (x, y) => y >= 0 && y < rows.length && x >= 0 && x < w && spr.pal[rows[y][x]];
  const c = tint && hex(tint), light = c && (c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11) / 255 >= GLOW_FROM;
  g.fillStyle = light ? rgb(c, GLOW_ALPHA) : rgb(outline);
  for (let y = -1; y <= rows.length; y++) for (let x = -1; x <= w; x++) {
    if (!at(x, y) && (at(x - 1, y) || at(x + 1, y) || at(x, y - 1) || at(x, y + 1))) g.fillRect(x0 + x, y0 + y, 1, 1);
  }
  rows.forEach((line, y) => { for (let x = 0; x < w; x++) {
    const col = spr.pal[line[x]];
    if (col) { g.fillStyle = tint || col; g.fillRect(x0 + x, y0 + y, 1, 1); }
  } });
}

/* the shades a view draws with: the scenery's for days studied, soil for days ahead: a day's
 * tile among them (or null for an empty one), the key's, and the hover's */
function paletteOf(H, sp, paper) {
  // the Heatmap tab's look (heatmap_look.page_look): another scenery's tiles (`tile`: "plain", a
  // style of its own, or a scenery that draws its own, its file loaded with today's); missing, the
  // scenery's own
  const L = H.look || {};
  const drawn = AF.heatmapTiles[L.tile], by = L.tile === 'plain' || drawn ? null : L.tile && AF.ENVS[L.tile] && AF.ENVS[L.tile].calendarTile ? L.tile : sp.mood.special;
  const dark = paper.dark, S = shades(sp, paper, L), draw = by && (AF.ENVS[by] || {}).calendarTile;
  // (a shape with spaces and smooth corners whose style gives a `smoothRadius` (its .json, in the look), Round: each day a
  // tile of its own, as round as its shape cut in pixels but its edge drawn at the screen's
  // resolution, antialiased, in Flat's one colour: under sharpen with that radius)
  const gapless = L.gaps === false, roundTile = !!(drawn && L.smoothRadius && L.smooth && !gapless);
  const flat = { name: 'flat', draw: AF.heatmapTiles.flat.draw }, look = roundTile ? flat
    : drawn && drawn.draw ? { name: L.tile, draw: drawn.draw } : draw && { name: by, draw };  // (a scenery's own tiles, when it draws them)
  const shapes = isShape(L.tile) && !roundTile ? L.tile : null;
  // the soil faded into the page, so the days ahead sit behind the days you studied
  const fade = FADE, till = dark ? P.tillDark : P.till, edges = dark ? P.tillDarkEdge : P.tillEdge;
  // (on a light page in lightness only, keeping most of its colour: mixed with white, brown went grey-mauve)
  const bgL = oklab(paper.bg)[0], toPage = c => {
    if (dark) return mix(c, paper.bg, fade);
    const k = oklab(c);
    return fromOklab(k[0] + (bgL - k[0]) * fade, k[1] * (1 - 0.6 * fade), k[2] * (1 - 0.6 * fade));
  };
  const soil = lv => till[lv].map(toPage), soilEdge = lv => toPage(edges[lv]);
  // (more due stands out more, as more studied does: lighter on a dark page, darker on a light one)
  const dueLv = n => dark ? 3 - H.dueShade(n) : H.dueShade(n);
  // a day's shade: its two tones and edge, whether it is soil (a day ahead), and its texture (v)
  const shadeOf = c => {
    const v = hashStr(iso(c.ms)) % TILE_VARIANTS, soilOf = lv => ({ pal: soil(lv), edge: soilEdge(lv), soil: true, v, lv });
    // today before you study: soil, by the cards it has due, until your first review
    if (c.o === 0 && !c.n && H.dueToday) return soilOf(dueLv(H.dueToday));
    if (!c.n || c.o > H.ahead) return null;
    if (c.o > 0) return soilOf(dueLv(c.n));
    const lv = H.shade(c.o);
    return { pal: S.grass[lv], edge: S.edge[lv], soil: false, v, lv };
  };
  const tile = c => { const t = shadeOf(c); return t && tilesOf(t.pal, t.edge, look, gapless)[t.v]; };
  // (the key: the four shades of a day studied, in Flat's one colour for a shape, as Contours'
  // bands and Round's days are; the soil and the empty days say what they are; the hover's ring in
  // today's frame colours, which show on every shade, its inside clear, so the day and its mark
  // keep their colours)
  return { tile, shadeOf, gapless, roundTile, shapes, grass: S.grass, edge: S.edge,
    // (for the shapes: the soil's four shades, the empty days' grey as one colour, and the page)
    tills: [0, 1, 2, 3].map(lv => soil(lv)[0]), blank: blankOn(paper), page: paper.bg,
    key: [0, 1, 2, 3].map(lv => tilesOf(S.grass[lv], S.edge[lv], shapes ? flat : look)[0]), ring: rgb(dark ? P.today : P.todayOnLight) };
}
// a seedling of its own day's kind (pine or broadleaf, and its look)
function seedlingOf(sp, ms) {
  const seed = hashStr('calendar|' + iso(ms));
  return spriteOf({ stage: SEEDLING, kind: seed % 100 < PINE_PERCENT ? 1 : 0, size: 0, health: 0, variant: seed % 7, seed, index: -1 }, 7, sp);
}
// a light frame round today's tile (dark on a light page), in the gaps all round it: on the page's
// colour, so it shows whatever the day's shade (on the tile's own edge, a busy day's dark tile hid it)
function frame(g, x, y, T, dark, bg) {
  g.fillStyle = rgb(dark ? P.today : P.todayOnLight);
  const tx = x - 1, ty = y - 1;
  g.fillRect(tx, ty, T + 2, 1); g.fillRect(tx, ty + T + 1, T + 2, 1); g.fillRect(tx, ty, 1, T + 2); g.fillRect(tx + T + 1, ty, 1, T + 2);
  // (and a line of the page's colour just inside it, so it never runs into a tile as dark as it is)
  g.fillStyle = rgb(bg);
  g.fillRect(x, y, T, 1); g.fillRect(x, y + T - 1, T, 1); g.fillRect(x, y, 1, T); g.fillRect(x + T - 1, y, 1, T);
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
/* The heatmap's tile styles (the Heatmap tab's Tiles), each in a file of its own: web/heatmap/<key>.js
 * (and .json, what the tab says of it), or for one still in the works, web/drafts/ (this copy only).
 * A style registers itself in AF.heatmapTiles[key] as one of:
 *  - { draw(g, pal, edge, v, T) }: each day a tile of its own, drawn as plainTile is (Flat);
 *  - { fields, prepare(ctx), paint(ctx, c, x, y, edge, i, state) }: a joined shape (Round, Contours):
 *    the days of each field (`fields`: the days studied 'grass', the days ahead 'soil', the empty
 *    days 'blank') side by side are one shape, the gutters between them filled while there are no
 *    spaces between days, each shape's outer corners cut and inner corners filled in whole-pixel
 *    steps; `paint` gives each pixel's colour (`edge`: on the shape's rim; `prepare` any work
 *    first, its answer `state`). Shapes join where the days touch: across months in By year,
 *    while Timeline's months, each in columns of their own, stay apart (2026-10-14);
 *  - { pass(ctx) }: draws the days itself, and gives back each pixel's day (an Int32Array, -1
 *    none) for the pointer, or null.
 * A scenery's own tiles (Brush, Scanlines, the seasonal ones) are its `calendarTile` instead. */
AF.heatmapTiles = AF.heatmapTiles || {};
const isShape = k => { const t = AF.heatmapTiles[k]; return !!t && !t.draw; };
const DIAG = [[-1, -1], [1, -1], [-1, 1], [1, 1]], N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const FIELD_SIGMA = 6, FIELD_REACH = 2;
/* the shade at a pixel of a day's field, 0 to 3, unrounded: the days round it of its own kind (studied,
 * or ahead) weighted by how near their tiles' centres are (a Gaussian about a day across) */
function fieldLv(c, x, y, get) {
  const t = c.shade;
  let sum = 0, w = 0;
  for (let dc = -FIELD_REACH; dc <= FIELD_REACH; dc++) for (let dr = -FIELD_REACH; dr <= FIELD_REACH; dr++) {
    const n = get(c.col + dc, c.row + dr);
    if (!n || !n.shade || n.shade.blank || !n.shade.soil !== !t.soil) continue;
    const dx = n.x + (TILE >> 1) - x, dy = n.y + (TILE >> 1) - y, k = Math.exp(-(dx * dx + dy * dy) / (2 * FIELD_SIGMA * FIELD_SIGMA));
    sum += n.shade.lv * k; w += k;
  }
  return Math.min(3, Math.max(0, w ? sum / w : t.lv));
}
// a shape's outline: the days ahead their own shade's edge, the days studied a pixel darker than the busiest's
const outlineOf = (t, pal, dark) => (t.soil ? mix(t.edge, DARK, dark ? 0.15 : 0.2) : mix(pal.edge[3], DARK, dark ? 0.45 : 0.35));
function shapesPass(g, cells, at, W, Hh, H, pal, dark) {
  const style = AF.heatmapTiles[pal.shapes], rows = ROWS;
  const get = (col, row) => (row >= 0 && row < rows ? at.get(col * ROWS + row) : undefined);
  const ctx = { g, cells, get, W, Hh, H, pal, rows, dark, TOP, CELL, TILE, FADE, DARK, layer, mix, hashStr, iso, fieldLv, outlineOf };
  if (style.pass) return { owner: style.pass(ctx), lvAt: null };
  const [cv, rg] = layer(W, Hh), img = rg.createImageData(W, Hh), d = img.data;
  // (each pixel's day and shade, for a hover's highlight: a month, a streak, or a shade of the key
  // lit by the shape's own pixels, not by squares across it; `level` a style's own, Contours' bands)
  const owner = new Int32Array(W * Hh).fill(-1), lvAt = new Int8Array(W * Hh).fill(-1);
  const kind = c => (!c || !c.shade ? '' : c.shade.blank ? 'blank' : c.shade.soil ? 'soil' : 'grass');
  for (const field of style.fields) {
    const isIn = c => kind(c) === field;
    // each pixel's day (-1 none): a day's tile, the gutter to a neighbour right or below that is
    // in too, and the corner between four
    const own = new Int32Array(W * Hh).fill(-1);
    const put = (x0, y0, w, h, i) => { for (let y = y0; y < y0 + h; y++) for (let x = x0; x < x0 + w; x++) own[y * W + x] = i; };
    cells.forEach((c, i) => {
      if (!isIn(c)) return;
      put(c.x, c.y, TILE, TILE, i);
      // (with "Spaces between days" on, no day joins another: each its own little shape)
      if (!pal.gapless) return;
      const R = isIn(get(c.col + 1, c.row)), D = isIn(get(c.col, c.row + 1));
      if (R) put(c.x + TILE, c.y, CELL - TILE, TILE, i);
      if (D) put(c.x, c.y + TILE, TILE, CELL - TILE, i);
      if (R && D && isIn(get(c.col + 1, c.row + 1))) put(c.x + TILE, c.y + TILE, CELL - TILE, CELL - TILE, i);
    });
    // the corners, two pixels round: outer ones cut, inner ones filled
    const f = (x, y) => x >= 0 && y >= 0 && x < W && y < Hh && own[y * W + x] >= 0, out = own.slice();
    for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (f(x, y)) {
        for (const [dx, dy] of DIAG) if (!f(x + dx, y) && !f(x, y + dy)) {
          out[i] = -1;
          if (f(x - dx, y) && !f(x - dx, y + dy)) out[i - dx] = -1;
          if (f(x, y - dy) && !f(x + dx, y - dy)) out[i - dy * W] = -1;
        }
      } else {
        for (const [dx, dy] of DIAG) if (f(x + dx, y) && f(x, y + dy) && f(x + dx, y + dy)) {
          out[i] = own[i + dx];
          if (!f(x - dx, y) && f(x - dx, y + dy)) out[i - dx] = own[i - dx + dy * W];
          if (!f(x, y - dy) && f(x + dx, y - dy)) out[i - dy * W] = own[i + dx - dy * W];
        }
      }
    }
    // each pixel in its day's colour, as the style paints it (a day before the start date faded,
    // as its tile would be)
    const edgeAt = (x, y) => N4.some(([dx, dy]) => { const X = x + dx, Y = y + dy; return X < 0 || Y < 0 || X >= W || Y >= Hh || out[Y * W + X] < 0; });
    const state = style.prepare ? style.prepare(Object.assign({ out }, ctx)) : null;
    for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
      const o = out[y * W + x];
      if (o < 0) continue;
      const c = cells[o], k = (y * W + x) * 4;
      const col = style.paint(ctx, c, x, y, edgeAt(x, y), y * W + x, state);
      owner[y * W + x] = o;
      if (c.shade && !c.shade.blank && !c.shade.soil) lvAt[y * W + x] = style.level ? style.level(state, y * W + x) : c.shade.lv;
      d[k] = col[0]; d[k + 1] = col[1]; d[k + 2] = col[2];
      d[k + 3] = H.fs !== null && c.o < H.fs ? Math.round(255 * (1 - FADE)) : 255;
    }
  }
  rg.putImageData(img, 0, 0);
  g.drawImage(cv, 0, 0);
  return { owner, lvAt };
}
/* one view drawn: the canvas, and where everything on it is */
/* a mark's colour, the scenery's own: of every bright hue at a few lightnesses, the one that stands
 * out most from the scenery's shades on both pages and from a missed day, for normal vision and
 * the three colour blindnesses at their strongest (Machado et al. 2009), and at least MARK_HUE_APART
 * round the colour wheel from every shade's hue (an equally distant violet still read as one of
 * Pumpkin patch's purples). One red for every scenery
 * sat on Lanterns' and Cherry blossom's reds, and for a red-green colour-blind eye on Natural's
 * greens (2026-10-14) */
const CVD = [null,
  [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],  // (deutan)
  [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],  // (protan)
  [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]];  // (tritan)
const MARK_LS = [0.6, 0.66, 0.72, 0.78], MARK_C = 0.17, MARK_HUE_APART = Math.PI / 3, MARK_PAGES = [[44, 44, 44], [245, 245, 245]];  // (Anki's dark and light pages)
const markPals = new Map();
function markPalOf(sp, look) {
  // (the heatmap's own shades, so the mark stands out from the colours the Heatmap tab chose
  // too, not only the scenery's: a red that stood out from green sat on Flame's reds)
  const L0 = look && look.colours ? { colours: look.colours, exact: !!look.exact } : null;
  const key = sp.mood.special + '|' + JSON.stringify(L0);
  if (!markPals.has(key)) {
    const sim = (c, m) => { if (!m) return c; const l = c.map(lin); return m.map(r => unlin(r[0] * l[0] + r[1] * l[1] + r[2] * l[2])); };
    const dist = (a, b) => { const p = oklab(a), q = oklab(b); return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]); };
    const backs = [...shades(sp, { bg: MARK_PAGES[0], dark: true }, L0).grass, ...shades(sp, { bg: MARK_PAGES[1], dark: false }, L0).grass].map(p => p[0])
      .concat([mix(MARK_PAGES[0], [128, 128, 128], 0.11), mix(MARK_PAGES[1], [128, 128, 128], 0.2)]);
    const at = (L, h) => { let C = MARK_C; while (C > 0.01 && !fits(L, C * Math.cos(h), C * Math.sin(h))) C *= 0.95; return [L, C, h]; };
    const hues = backs.map(oklab).filter(k => Math.hypot(k[1], k[2]) > 0.04).map(k => Math.atan2(k[2], k[1]));
    const apart = h => hues.every(g => Math.abs(Math.atan2(Math.sin(h - g), Math.cos(h - g))) >= MARK_HUE_APART);
    let best = null, most = -1;
    for (const L of MARK_LS) for (let deg = 0; deg < 360; deg += 10) {
      if (!apart(deg * Math.PI / 180)) continue;
      const lch = at(L, deg * Math.PI / 180), col = fromOklab(lch[0], lch[1] * Math.cos(lch[2]), lch[1] * Math.sin(lch[2]));
      const worst = Math.min(...CVD.flatMap(m => backs.map(b => dist(sim(col, m), sim(b, m)))));
      if (worst > most) { most = worst; best = lch; }
    }
    const [L, C, h] = best, pale = at(Math.min(0.9, L + 0.14), h);
    markPals.set(key, Object.assign({}, MARK_PAL, { R: rgb(fromOklab(L, C * Math.cos(h), C * Math.sin(h))),
      L: rgb(fromOklab(pale[0], pale[1] * 0.55 * Math.cos(h), pale[1] * 0.55 * Math.sin(h))) }));
  }
  return markPals.get(key);
}
/* Smooth (the Heatmap tab's switch, `look.smooth`): each day's tile, in whichever style is chosen,
 * drawn inside a rounded square at the screen's own resolution, as GitHub's are (drawn in the
 * heatmap's own pixels and scaled up, corners step). The tiles, the empty days and today's frame are
 * drawn by sharpen once the scale is known; the marks, the free days' dots, the brackets and the
 * lane stay on the heatmap's pixels, over them. Not with the joined shapes (Contours, a drafted shape,
 * Round without spaces), which are no tiles. (The path by hand: Chromium 77, Anki 2.1.45's, has no
 * roundRect) */
const SMOOTH_R = 1.8;  // (the corners' radius, in the heatmap's pixels: GitHub's 2px on a 10px tile)
function rounded(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}
/* a view's tiles, empty days and today's frame drawn smooth on `hi`, `s` device pixels to the
 * heatmap's pixel, under `lo` (the rest of it, in its pixels) */
function sharpen(hi, lo, cells, H, dark, paper, s, F, R, G = 0) {
  const W = lo.width, Hh = lo.height;
  hi.width = Math.round(W * s); hi.height = Math.round(Hh * s);
  const g = hi.getContext('2d');
  g.setTransform(hi.width / W, 0, 0, hi.height / Hh, 0, 0);
  g.imageSmoothingEnabled = false;  // (a tile's own texture stays crisp inside its smooth outline)
  // (the rounded square is the tile's face, F: its last row and column are the gap between days,
  // which a style draws in its edge tone and which inside a smooth outline read as a stepped rim;
  // a style may grow it by G all round, its colour filling the rim, so the spaces between days are
  // narrower)
  const tile = (c, inset) => {
    const i = (inset || 0) - G;
    rounded(g, c.x + i, c.y + i, F - 2 * i, F - 2 * i, Math.max(0.6, R - i));
    if (c.t) {
      g.fillStyle = rgb(c.t.fill); g.fill();
      g.save(); g.clip(); g.drawImage(c.t, 0, 0, F, F, c.x, c.y, F, F); g.restore();
    } else { g.fillStyle = dark ? EMPTY : EMPTY_LIGHT; g.fill(); }
  };
  for (const c of cells) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    tile(c);
  }
  // (a rest day's ring, paint: the tile's own rounded outline in the heatmap's faint shade, the empty grey inside)
  for (const c of cells) if (c.rest) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    rounded(g, c.x - G, c.y - G, F + 2 * G, F + 2 * G, Math.max(0.6, R + G)); g.fillStyle = rgb(c.rest); g.fill();
    rounded(g, c.x + 1 - G, c.y + 1 - G, F + 2 * G - 2, F + 2 * G - 2, Math.max(0.6, R + G - 1)); g.fillStyle = rgb(blankOn(paper)); g.fill();
  }
  g.globalAlpha = 1;
  const today = cells.find(c => c.o === 0);
  if (today) {
    // (as frame: a light ring in the gaps all round, a line of the page's colour just inside it)
    rounded(g, today.x - 1 - G, today.y - 1 - G, F + 2 + 2 * G, F + 2 + 2 * G, R + 1 + G); g.fillStyle = rgb(dark ? P.today : P.todayOnLight); g.fill();
    rounded(g, today.x - G, today.y - G, F + 2 * G, F + 2 * G, R + G); g.fillStyle = rgb(paper.bg); g.fill();
    tile(today, 1);
  }
  g.drawImage(lo, 0, 0);
}
/* how many low-res pixels across a view's weeks are: its last week's right edge; By year's every
 * year as wide as the widest it pages to, so the earlier years shown above it line up with it (a
 * leap year starting on its weeks' last day needs 54 weeks, the rest 53 at most) */
function weeksWidth(H, win, lastCol) {
  if (win.year == null) return 1 + (lastCol + 1) * CELL;
  if (!H.yearCols) {
    H.yearCols = 0;
    for (let y = yearOf(H.today + H.first * DAY_MS); y <= yearOf(H.today + H.ahead * DAY_MS); y++) {
      const jan1 = Date.UTC(y, 0, 1), days = (Date.UTC(y + 1, 0, 1) - jan1) / DAY_MS;
      H.yearCols = Math.max(H.yearCols, Math.floor((dow(jan1) + days - 1) / 7) + 1);
    }
  }
  return 1 + Math.max(H.yearCols, lastCol + 1) * CELL;
}
function paint(H, win, sp, paper) {
  const dark = paper.dark, band = TOP;
  // the days in weeks, their first day on top; Timeline starts each month in a column of its own (By
  // year runs its months on in the same weeks)
  const cells = columns(H, win).map(([o, ms, col, row]) => ({ o, ms, n: H.n(o), col, row }));
  const xOf = c => 1 + c.col * CELL, yOf = c => band + c.row * CELL + 1;
  const at = new Map();  // (each day by its column and row, for the pointer)
  for (const c of cells) { c.x = xOf(c); c.y = yOf(c); at.set(c.col * ROWS + c.row, c); }
  const W = weeksWidth(H, win, cells[cells.length - 1].col), Hh = band + ROWS * CELL + BRACKET;
  const [cv, g] = layer(W, Hh);
  // the animals (and the forest's first seedling) on a layer of their own over it, shown while the
  // pointer is on the heatmap (forest.css): the forest's milestones, which the forest shows already
  const [above, ag] = layer(W, Hh);
  const pal = paletteOf(H, sp, paper), smooth = !!(H.look && H.look.smooth) && !pal.shapes;
  // the tiles first, each with a texture of its own day's (the same whichever page it is on); a
  // missed day, or one before your history, faint, so the view is never half bare
  for (const c of cells) {
    // (Round, Contours, a drafted shape: the days studied, and the days ahead, are drawn after,
    // as shapes: shapesPass; all but Rounded the empty days too)
    // (a style that draws the empty days too, as Contours does, gets them as shades of their own)
    const style = pal.shapes && AF.heatmapTiles[pal.shapes];
    if (style) c.shade = pal.shadeOf(c) || (!style.fields || style.fields.indexOf('blank') >= 0 ? { blank: true } : null);
    const t = pal.shapes ? null : pal.tile(c);
    // (a day before the forest's start date, studied or not, dimmed)
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    if (smooth) c.t = t;  // (drawn by sharpen)
    else if (t) g.drawImage(t, c.x, c.y);
    else if (!c.shade) empty(g, c.x, c.y, dark ? EMPTY : EMPTY_LIGHT, pal.gapless ? CELL : TILE);
    g.globalAlpha = 1;
  }
  // (a joined shape: each pixel's day and shade, for the highlight; a drafted one's days also for the pointer)
  const joined = pal.shapes ? shapesPass(g, cells, at, W, Hh, H, pal, dark) : null;
  const pane = joined && !joined.lvAt ? joined.owner : null;
  // (a day with nothing due, or a day off: inside a streak, a hollow tile, a ring in the heatmap's
  // faint shade round the empty grey (restShade), so the day reads as a slot the streak passed
  // through, unfilled, never as studied, and the week does not read as a gap; a single pixel was
  // too faint to see and a gold block read as a highlight, 2026-10-17. Not on today, whose frame
  // says it; outside any streak that pixel; over the shapes. Smooth tiles draw theirs in sharpen)
  const rest = restShade(pal, paper), face = pal.gapless ? CELL : TILE_FACE;
  for (const c of cells) if (H.free.has(c.o) && !c.n) {
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    const run = c.o < 0 ? H.runOf(c.o) : null, mid = TILE >> 1;
    if (run && smooth) c.rest = rest;
    else if (run) { g.fillStyle = rgb(rest); restRing(g, c.x, c.y, face); }
    else if (c.o !== 0) { g.fillStyle = FREE_MARK; g.fillRect(c.x + mid, c.y + mid, 1, 1); }
    g.globalAlpha = 1;
  }
  const animals = H.animals;
  const marks = [];  // (where the marks over the weeks stand, for the pointer)
  // the days you marked: each its icon, painted on its tile, centred on what shows of it, the day's shade round it
  // (important enough to sit on the data; its tooltip gives the day's count)
  for (const c of cells) {
    if (!H.marked.has(c.o)) continue;
    const spr = markOf(H.marked.get(c.o)).spr, rows = spr.frames[0];
    const x0 = c.x + Math.floor((TILE_FACE - rows[0].length) / 2), y0 = c.y + Math.floor((TILE_FACE - rows.length) / 2);
    // (cut out of the tile by a line of the page's colour, as the animals are: red on Lanterns' or
    // Cherry blossom's tiles was lost)
    drawAnimal(g, Object.assign({}, spr, { pal: markPalOf(sp, H.look) }), x0, y0, null, paper.bg);
  }
  const today = cells.find(c => c.o === 0);
  if (today && !smooth) frame(g, today.x, today.y, TILE, dark, paper.bg);
  // the streaks: a bracket under the weeks each ran through, gold for the current one, cut at
  // the view's edges (with no end mark there)
  const by = band + ROWS * CELL + 3, brackets = [];
  for (const r of H.runs) {
    const len = r.days, live = r === H.current;
    if (len < SHOWN_STREAK && !live) continue;
    const fo = Math.max(r.from, win.from), to = Math.min(r.to, win.to);
    if (fo > to) continue;
    const a = cells[fo - win.from], b = cells[to - win.from];
    const x0 = a.x + (fo === r.from ? 1 : 0), x1 = b.x + TILE - 2;
    g.fillStyle = rgb(live ? (dark ? P.gold : P.goldOnLight) : P.past);
    g.fillRect(x0, by, x1 - x0 + 1, 1);
    if (fo === r.from) g.fillRect(x0, by - 2, 1, 2);
    if (to === r.to) g.fillRect(x1, by - 2, 1, 2);
    // dotted under a week the streak passed over with nothing due (an old deck's quiet weeks)
    const weeks = new Map();
    for (let o = fo; o <= to; o++) { const c = cells[o - win.from]; weeks.set(c.col, (weeks.get(c.col) !== false) && !c.n); }
    for (const [col, off] of weeks) {
      if (!off) continue;
      const wx0 = Math.max(x0, col * CELL), wx1 = Math.min(x1, col * CELL + CELL - 1);
      g.clearRect(wx0, by, wx1 - wx0 + 1, 1);
      for (let x = wx0; x <= wx1; x += 2) g.fillRect(x, by, 1, 1);
    }
    brackets.push({ x0, x1, len, live, run: r, cut: fo > r.from });
  }
  // the streak lane: a trophy under the last day of each of your longest streaks and the goal
  // pennant under its day, below the brackets, and a dotted gold line from today on to the goal
  // (all the streak's marks together, none cutting through the weeks). On the layer shown while
  // you hover the heatmap, as the animals are (2026-10-16): the streak's own line stays in view,
  // the trophies and the goal, the gamey part, come with the pointer
  if (H.goal && H.current && H.current.to >= win.from && H.current.to <= win.to) {
    const a = cells[H.current.to - win.from], gc = H.goal.o <= win.to ? cells[H.goal.o - win.from] : cells[cells.length - 1];
    ag.fillStyle = dark ? rgb(P.gold, GOAL_LINE) : rgb(P.goldOnLight);
    for (let x = a.x + TILE; x <= gc.x + 4; x += 2) ag.fillRect(x, by, 1, 1);
    if (H.goal.o <= win.to) ag.fillRect(gc.x + 4, by - 2, 1, 2);
  }
  const lane = [];
  for (const [run, i] of H.podium) lane.push([run.to, TROPHIES[i]]);
  if (H.goal) lane.push([H.goal.o, GOALS[H.goal.rank]]);
  for (const [o, spr] of lane) {
    if (o < win.from || o > win.to) continue;
    // (the goal's pole on the day's middle, under the dotted line's end; a trophy centred)
    const c = cells[o - win.from], w = spr.frames[0][0].length, x0 = c.x + (GOALS.includes(spr) ? 4 : Math.floor((TILE - w) / 2)), y0 = by + 3;
    // (on a light page in their deeper shades: pale gold and silver would fade into it)
    const metal = !dark && METALS_ON_LIGHT[spr.pal.G];
    drawAnimal(ag, metal ? Object.assign({}, spr, { pal: Object.assign({}, spr.pal, metal) }) : spr, x0, y0, null, paper.bg);
    marks.push({ x0, x1: x0 + w, y0, y1: y0 + spr.frames[0].length, c, trophy: TROPHIES.indexOf(spr) });
  }
  // on the layer shown while you hover the heatmap, each on its own day's tile: the animals, each
  // where it came (the first, where two came on one day; the tooltip names them all), and the
  // seedling of the day the forest began with a start date (the one mark the start date leaves
  // here, besides the animals coming only after it). A day you marked keeps its mark in view.
  for (const c of cells) {
    if (H.marked.has(c.o)) continue;
    const a = (animals.get(c.o) || [])[0], spr = a && (a.spr || (AF.VISITOR_SPRITES && AF.VISITOR_SPRITES[a.key]));
    if (spr) {
      const rows = spr.frames[0];
      drawAnimal(ag, spr, c.x + Math.floor((TILE - rows[0].length) / 2), c.y + Math.floor((TILE - rows.length) / 2), sp.visitorTint, paper.bg);
    } else if (c.o === H.fs) {
      const s = seedlingOf(sp, c.ms);
      ag.drawImage(s, c.x + Math.floor((TILE - s.width) / 2), c.y + Math.floor((TILE - s.height) / 2));
    }
  }
  const radius = pal.roundTile ? H.look.smoothRadius : SMOOTH_R;  // (smooth: each tile's corners)
  const out = { cv, above, W, Hh, cells, at, pane, joined, brackets, band, marks, ring: pal.ring, key: pal.key, smooth, radius };
  if (smooth) {
    // (shown on a canvas of its own at the screen's resolution, drawn again when the scale changes)
    const [hi] = layer(W, Hh);
    hi.dataset.pixels = W;  // (the heatmap's width in its own pixels, for e2e/phone_check)
    let drawnAt = 0;
    const F = pal.gapless ? CELL : TILE_FACE;  // (each tile's face: no gap of its own when the days have none)
    const grow = pal.roundTile && !pal.gapless ? H.look.smoothGrow || 0 : 0;
    out.cv = hi; out.sharpen = s => { if (s !== drawnAt) { drawnAt = s; sharpen(hi, cv, cells, H, dark, paper, s, F, radius, grow); } };
    out.sharpen(dpr());
  }
  return out;
}

// a year's weeks, about as wide as they come: By year's, or Timeline's months apart (its
// months' own weeks, and the odd empty column)
const widthOf = view => (view === 'by_year' ? 53 : 54) * CELL + 1;
const dpr = () => window.devicePixelRatio || 1;
const sharpK = () => Math.min(1, SHARP / dpr());
// Timeline's months: ten, fewer (down to MONTHS_MIN) only where ten would be too small to stay crisp
function countFor(view, width) {
  if (view !== 'timeline' || !width) return MONTHS_SHOWN;
  if (width / widthOf(view) >= sharpK()) return MONTHS_SHOWN;
  return Math.max(MONTHS_MIN, Math.floor(MONTHS_SHOWN * width / (widthOf(view) * sharpK())));
}
// the phone's timeline scale for weeks this tall (css px): whole pixels, from SWIPED_K up
AF.calendarScaleFor = height => Math.max(SWIPED_K, Math.floor(height * dpr() / (TOP + ROWS * CELL + BRACKET)) / dpr());
/* the room over the canvas for the months' labels: the first row ROW_UNDER under the row's top,
 * at any zoom (the canvas's own TOP grows with it) */
const monthsRoom = k => Math.round(ROW_UNDER - (TOP + 1) * k);
/* the calendar's width, a share of the panel's (payload.py: 85%, a debug setting's otherwise), set on
 * its box before its room is measured (core.js) and again when it is drawn */
AF.calendarWidth = cal => (cal.width == null ? 85 : Math.max(50, Math.min(100, cal.width))) + '%';
/* how tall the footer will be: its row (FOOT_H), unless the forest's journal, which comes down into
 * it beside the shade's choice and the key, is long enough to wrap there. Measured on a stand-in
 * footer in the calendar's box (the real one is built only once the forest is drawn), so the room
 * kept for the calendar holds it and the page keeps still */
function footHeight(root, H) {
  // (the journal: in the caption until the footer is built, then in it; measured again from the footer by e2e/render_heatmap.py)
  const box = root && root.querySelector('.af-cal'), journal = root && root.querySelector('.af-journal');
  if (!box || !journal || !journal.textContent) return FOOT_H;
  const el = (cls, tag) => { const e = document.createElement(tag || 'span'); e.className = cls; return e; };
  const foot = el('af-cal-foot', 'div');
  foot.style.visibility = 'hidden';
  const j = el('af-cal-journal'); j.appendChild(journal.cloneNode(true)); foot.appendChild(j);
  // (the choice shows with two or more ways to shade: Reviews, Time with study time kept, Pace)
  const ways = ['Reviews'].concat(H.timed ? ['Time'] : [], H.paced ? ['Pace'] : []);
  if (ways.length >= 2) {
    const by = el('af-cal-by af-cal-shade');
    ways.forEach(w => { const b = document.createElement('button'); b.type = 'button'; b.textContent = w; by.appendChild(b); });
    foot.appendChild(by);
  }
  const key = el('af-cal-key'), ends = H.by === 'median' ? ['Slow', 'Fast'] : ['Less', 'More'];
  const word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
  [word(ends[0])].concat([0, 1, 2, 3].map(() => el('af-cal-swatch', 'canvas')), [word(ends[1])]).forEach(e => key.appendChild(e));
  foot.appendChild(key);
  box.appendChild(foot);
  const h = foot.offsetHeight;
  foot.remove();
  return Math.max(FOOT_H, h);
}
/* how tall the calendar will be at this width, for the room kept for it until it is drawn (root:
 * the panel, for the journal that will wrap in its footer) */
AF.calendarHeight = function (cal, width, root) {
  CELL = cellOf(cal);
  const view = cal.view === 'by_year' ? 'by_year' : 'timeline';
  // (the scale is the width's: the view's exact weeks, as it will lay them out)
  let W = widthOf(view) * countFor(view, width) / MONTHS_SHOWN, foot = FOOT_H;
  if (width > 0) {
    weekStart = cal.weekStart == null ? 1 : cal.weekStart;
    const H = cal.afHistory = history(cal);  // (the whole model: kept for the draw that follows, AF.calendar, which takes it once)
    const win = windowOf(H, view, 0, null, countFor(view, width)), cols = columns(H, win);
    W = weeksWidth(H, win, cols[cols.length - 1][2]);
    foot = footHeight(root, H);
  }
  const k = width > 0 ? width / W : 1;  // (all the width: By year its year, Timeline its months, countFor)
  // (By year's earlier years take no room at first: never shown when drawn, and their switch sits in
  // the band over the months, as the controls on hover do, so both views start at the same height)
  return Math.round(monthsRoom(k) + (TOP + ROWS * CELL + BRACKET) * k + FOOT_GAP + foot);  // (rounded as the page rounds the drawn height)
};

AF.calendar = function (root, data, env) {
  const cal = data.calendar;
  if (!cal || !cal.days || !cal.days.length) return;
  // (a calendar drawn here before stops watching the page: this one takes its place)
  if (root.afCalStop) root.afCalStop();
  let box = root.querySelector('.af-cal');
  if (!box) { box = document.createElement('div'); box.className = 'af-cal'; root.append(box); }
  box.style.width = AF.calendarWidth(cal);
  weekStart = cal.weekStart == null ? 1 : cal.weekStart; CELL = cellOf(cal);
  const H = cal.afHistory || history(cal), sp = sceneOf(data, env);  // (built already while measuring the room, AF.calendarHeight)
  delete cal.afHistory;
  const treesByDay = new Map((data.trees || []).map(t => [-t.ago, t]));
  for (const [ago, n] of cal.planted || []) if (!treesByDay.has(-ago)) treesByDay.set(-ago, { ago, n });
  let view = cal.view === 'by_year' ? 'by_year' : 'timeline';  // (the switch on the heatmap changes it)
  const deck = data.deckId && !data.testForest ? data.deckId : '';
  const swiped = !data.inAnki;  // on the phone: swiped along rather than paged
  let page = 0, year = null;  // Timeline's stretch, in months from today's (0), By year's year
  // what a screen reader says for the picture: the year in a sentence, its streak
  // (the stretch in view, paged to or not: "Study heatmap, Feb 2025 to Jan 2026: 203 days studied")
  const described = win => {
    let studied = 0;
    for (let o = Math.max(H.first, win.from); o <= Math.min(0, win.to); o++) if (H.n(o)) studied++;
    const month = o => { const d = new Date(H.today + o * DAY_MS); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
    return `Study heatmap, ${month(win.from)} to ${month(win.to)}: ${num(studied)} day${studied === 1 ? '' : 's'} studied`
      + (H.current && win.to >= 0 && win.from <= 0 ? `, a ${num(H.current.days)}-day streak` : '');
  };

  // the weeks, and a footer: the forest's journal (the panel's last line), the way about (‹ › and
  // », back to today, after them; on the phone a Today pill alone, once scrolled away) and the key,
  // the last two shown on hover (forest.css)
  box.innerHTML = '<div class="af-cal-grid"><div class="af-cal-months"></div><div class="af-cal-days"></div><div class="af-cal-hover" hidden></div><div class="af-cal-notes"></div><div class="af-cal-past"></div></div>'
    + '<div class="af-cal-foot"><span class="af-cal-journal"></span><span class="af-cal-acts">'
    + (swiped ? '<button type="button" class="af-cal-chev af-cal-today" data-go="0">Today</button>'
      : '<button type="button" class="af-cal-chev" data-go="-1" aria-label="Earlier" title="Earlier">‹</button>'
      + '<button type="button" class="af-cal-chev" data-go="1" aria-label="Later" title="Later">›</button>'
      + '<button type="button" class="af-cal-chev af-cal-now" data-go="0" aria-label="Back to today" title="Back to today">»</button>')
    + '</span><span class="af-cal-by af-cal-view" role="radiogroup" aria-label="View">'
    + '<button type="button" role="radio" data-view="timeline" title="Ten months, with this month most of the way along">Timeline</button>'
    + '<button type="button" role="radio" data-view="by_year" title="January to December, and your streak\'s earlier years above it">By year</button>'
    + '</span><span class="af-cal-by af-cal-shade" role="radiogroup" aria-label="Shade the days by">'
    + '<button type="button" role="radio" data-by="reviews" title="Shade each day by how many reviews you did">Reviews</button>'
    + '<button type="button" role="radio" data-by="time" title="Shade each day by how long you studied">Time</button>'
    + '<button type="button" role="radio" data-by="median" title="Shade each day by its median seconds per answer">Pace</button>'
    + '</span><span class="af-cal-key"></span></div>'
    + '<div class="af-tip af-cal-tip" hidden></div>'
    + '<div class="af-cal-pin" hidden><span class="af-cal-pin-icons"></span>'
    + '<input class="af-cal-pin-name" maxlength="40" spellcheck="false" aria-label="Mark name">'
    + '<button type="button" class="af-cal-pin-del" aria-label="Remove the mark" title="Remove the mark">\u00d7</button></div>';
  if (swiped) box.classList.add('af-cal-swiped');
  // the forest's journal comes down to the foot of the panel: a forest's caption with the
  // calendar under it would read as the calendar's
  const journal = root.querySelector('.af-caption .af-journal');
  if (journal) box.querySelector('.af-cal-journal').appendChild(journal);
  box.style.minHeight = '';  // (the room kept for it while the forest was building)
  const grid = box.querySelector('.af-cal-grid'), btn = go => box.querySelector(`[data-go="${go}"]`);
  if (swiped) grid.classList.add('af-cal-scroll');
  box.querySelectorAll('[data-go]').forEach(b => {
    b.addEventListener('click', () => (swiped ? toToday(true) : go(b.dataset.go)));
    // (a click must leave no focus behind, which would keep them in view after the pointer leaves)
    b.addEventListener('mousedown', e => e.preventDefault());
  });
  // ‹ Today › on the months' row, at its right end, beside the period they change (as calendars
  // have them; on the phone, Today alone stays in the footer)
  const acts = box.querySelector('.af-cal-acts');
  if (!swiped) grid.appendChild(acts);
  // what the shades go by, in the footer just left of the key it changes (Reviews | Time  Less ..
  // More): the day's reviews, or the time they took (kept by the add-on; on the phone, and with no
  // time kept, as the add-on has it, no choice). Not on the months' row: with the view and the
  // arrows there, that corner read as one crowded line of words (2026-10-15)
  const byBox = box.querySelector('.af-cal-shade');
  // (no choice with only one way to shade)
  byBox.querySelector('[data-by="time"]').hidden = !H.timed;
  byBox.querySelector('[data-by="median"]').hidden = !H.paced;
  byBox.hidden = swiped || [...byBox.querySelectorAll('button')].filter(b => !b.hidden).length < 2;
  // Timeline | By year, just left of it: the view as the Heatmap tab sets it, changed here for good
  // (as the shade is; not on the phone, which swipes along its own)
  const viewBox = box.querySelector('.af-cal-view');
  viewBox.hidden = swiped;
  if (!swiped) acts.insertBefore(viewBox, acts.firstChild);
  viewBox.querySelectorAll('button').forEach(b => {
    b.addEventListener('mousedown', e => e.preventDefault());
    b.addEventListener('keydown', e => {
      const step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
      if (!step) return;
      e.preventDefault();
      const to = viewBox.querySelector(`[data-view="${b.dataset.view === 'timeline' ? 'by_year' : 'timeline'}"]`);
      to.focus(); to.click();
    });
    b.addEventListener('click', () => {
      if (view === b.dataset.view) return;
      view = b.dataset.view; page = 0; year = null;
      yearsShown = false;  // (By year comes back as it opens: the year in view alone)
      send(`${data.channel}:view:${view}`);
      unpoint();
      draw();
    });
  });
  // the caption's streak, clicked: By year, as the switch would (`ask`: whether it would do anything)
  root.afCalByYear = ask => {
    if (swiped || view === 'by_year') return false;
    if (ask) return true;
    // (and its earlier years shown, so the whole streak is there; the year in view kept where the
    // Timeline's weeks were on screen, the years above it)
    const was = drawn.cv.getBoundingClientRect().top;
    viewBox.querySelector('[data-view="by_year"]').click();
    if (pastYears(H, yearOf(H.today)).length) {
      yearsShown = true;
      past();
      lay();
      const moved = drawn.cv.getBoundingClientRect().top - was;
      if (moved) window.scrollBy(0, moved);
    }
    return true;
  };
  byBox.querySelectorAll('button').forEach(b => {
    b.addEventListener('mousedown', e => e.preventDefault());  // (no focus left behind: as the arrows)
    b.addEventListener('keydown', e => {  // (←/→ move the choice, as radio buttons do)
      const step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
      if (!step) return;
      e.preventDefault();
      const shown = [...byBox.querySelectorAll('button')].filter(x => !x.hidden);
      const to = shown[(shown.indexOf(b) + step + shown.length) % shown.length];
      to.focus(); to.click();
    });
    b.addEventListener('click', () => {
      if (H.by === b.dataset.by) return;
      H.by = b.dataset.by;
      send(`${data.channel}:shade:${H.by}`);
      unpoint();
      draw();
    });
  });
  const months = box.querySelector('.af-cal-months'), days = box.querySelector('.af-cal-days');
  const notes = box.querySelector('.af-cal-notes'), tip = box.querySelector('.af-cal-tip'), hover = box.querySelector('.af-cal-hover');
  // (last: the day the pointer was last on; pointed: the year it is on, the one in view or an earlier one shown)
  let drawn = null, k = 2, last, pointed = null;
  let paper = pageOf(box);
  box.classList.toggle('af-cal-on-light', !paper.dark);  // (a choice's chosen half: a white pill on a light page)
  // the days a hover is about stand out (a shade in the key, a month, a streak): the others
  // dimmed into the page, on a layer over the weeks
  let spotCv = null;
  const spot = (keep, lv) => {
    if (spotCv) { spotCv.remove(); spotCv = null; }
    if (!keep || !drawn) return;
    const d = pointed || drawn;  // (a streak's bracket on an earlier year lights that year's days)
    const [cv, g] = layer(d.W, d.Hh);
    g.fillStyle = rgb(paper.bg, SPOT_DIM);
    if (d.joined) {
      // (a joined shape dimmed by its own pixels: a month or a streak lights its days' part of the
      // shape, a shade of the key the bands in that shade, `lv`, where the style has bands)
      const img = g.createImageData(d.W, d.Hh), px = img.data, [r0, g0, b0] = paper.bg, a0 = Math.round(255 * SPOT_DIM);
      const { owner, lvAt } = d.joined, W = d.W, Hh = d.Hh;
      let lit = new Uint8Array(owner.length);
      for (let i = 0; i < owner.length; i++) { const o = owner[i]; lit[i] = o >= 0 && (lv !== undefined && lvAt ? lvAt[i] === lv : keep(d.cells[o])) ? 1 : 0; }
      {  // (its corners two pixels round, outer cut and inner filled, as shapesPass draws the shapes:
        // a month starts and ends partway through a week, and its square steps read as cut out;
        // an outline and whole weeks were tried, 2026-10-16)
        const f = (x, y) => x >= 0 && y >= 0 && x < W && y < Hh && lit[y * W + x], out = lit.slice();
        for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) {
          const i = y * W + x;
          if (f(x, y)) {
            for (const [dx, dy] of DIAG) if (!f(x + dx, y) && !f(x, y + dy)) {
              out[i] = 0;
              if (f(x - dx, y) && !f(x - dx, y + dy)) out[i - dx] = 0;
              if (f(x, y - dy) && !f(x + dx, y - dy)) out[i - dy * W] = 0;
            }
          } else if (owner[i] >= 0) {
            for (const [dx, dy] of DIAG) if (f(x + dx, y) && f(x, y + dy) && f(x + dx, y + dy)) out[i] = 1;
          }
        }
        lit = out;
      }
      for (let i = 0; i < owner.length; i++) {
        if (lit[i]) continue;
        px[i * 4] = r0; px[i * 4 + 1] = g0; px[i * 4 + 2] = b0; px[i * 4 + 3] = a0;
      }
      g.putImageData(img, 0, 0);
    } else for (const c of d.cells) if (!keep(c)) g.fillRect(c.x - 1, c.y - 1, CELL, CELL);
    cv.className = 'af-cal-above af-cal-spot';
    Object.assign(cv.style, { left: d.cv.offsetLeft + 'px', top: d.cv.offsetTop + 'px', width: d.cv.style.width,
      height: d.cv.style.height, imageRendering: d.cv.style.imageRendering });
    grid.insertBefore(cv, notes);
    spotCv = cv;
  };
  // the day under the pointer: ringed in today's frame colour, which shows on every shade
  const ring = c => {
    spot(null);
    if (!c && editing && drawn) c = drawn.cells.find(x => x.o === editing.o) || null;  // (a day being marked keeps it)
    hover.hidden = !c;
    if (!c) return;
    const cv = (pointed || drawn).cv;
    hover.style.left = (cv.offsetLeft + (c.x - 1) * k) + 'px';
    hover.style.top = (cv.offsetTop + (c.y - 1) * k) + 'px';
    hover.style.width = hover.style.height = (TILE + 2) * k + 'px';  // (round the whole tile, as today's frame)
    hover.style.borderRadius = drawn.smooth ? (drawn.radius + 1) * k + 'px' : '';
    hover.style.borderColor = drawn.ring;
  };
  // the first tooltip after the pointer comes onto the heatmap waits a moment, so crossing it on the
  // way elsewhere flashes none; from one day to the next after that, at once (a tap and the
  // keyboard at once too)
  let warm = false, waking = 0;
  const reveal = () => {
    tip.hidden = false;
    if (warm || touched || document.activeElement === (drawn && drawn.cv)) { tip.style.visibility = ''; warm = true; return; }
    tip.style.visibility = 'hidden';
    clearTimeout(waking);
    waking = setTimeout(() => { tip.style.visibility = ''; warm = true; }, TIP_WAIT);
  };
  const pointTree = c => { if (root.afPointTreeDay) root.afPointTreeDay(c ? -c.o : null); };
  // (the tip shown again straight away, by the key or a streak, must not stay invisible from a day brushed too briefly to wake it)
  const unpoint = () => { pointTree(null); tip.hidden = true; tip.style.visibility = ''; ring(null); last = undefined; warm = false; clearTimeout(waking); pointed = null; };
  // how far you can page: back to the first day counted, on to the last day ahead counted
  const can = win => ({ back: win.from > H.first, on: win.to < H.ahead });

  function draw() {
    const hadCv = !!drawn && document.activeElement === drawn.cv;  // (the keyboard on the days: kept there)
    const old = drawn && drawn.cv;
    const count = swiped ? MONTHS_SHOWN : countFor(view, grid.clientWidth);
    // (paged away, a narrower or wider heatmap keeps the month you were looking at last in view)
    if (drawn && page && drawn.count !== count) page += drawn.count - count - Math.round(drawn.count * TODAY_AT) + Math.round(count * TODAY_AT);
    const win = windowOf(H, swiped ? 'swiped' : view, page, year, count), d = paint(H, win, sp, paper);
    drawn = Object.assign(d, { win, count });
    last = undefined;
    // (a page's slide is for paging alone: go starts it again after this; any other drawing, a day
    // marked say, must not replay it, the new canvas taking the class still on the grid)
    grid.classList.remove('af-cal-from-left', 'af-cal-from-right');
    grid.querySelectorAll('canvas').forEach(c => { if (c !== old) c.remove(); });
    // (the last weeks stay in the page, unseen, until the next drawing: a Mac's trackpad sends the
    // rest of a swipe, and the next one, to the element it began on until the pointer moves, and a
    // removed one passes them to nothing)
    if (old) {
      old.className = 'af-cal-gone';
      old.removeAttribute('style'); old.removeAttribute('role'); old.removeAttribute('aria-label');
      old.setAttribute('aria-hidden', 'true'); old.tabIndex = -1;
    }
    drawn.above.className = 'af-cal-above';
    grid.insertBefore(drawn.above, notes);
    drawn.cv.className = 'af-cal-canvas';
    drawn.cv.setAttribute('role', 'img');
    drawn.cv.setAttribute('aria-label', described(win));
    grid.insertBefore(drawn.cv, notes);
    const focused = box.contains(document.activeElement) ? document.activeElement : null;
    if (!swiped) drawn.cv.tabIndex = 0;  // (the days a tab stop: the keyboard's way along them, below)
    if (hadCv) drawn.cv.focus();
    // what the tiles mean, read off the tiles themselves
    // (Smooth: the face alone, filled, as the days are drawn: no gap row and column for a rim)
    const swatch = cv => {
      const c = document.createElement('canvas'), F = drawn.smooth ? TILE_FACE : TILE, g = c.getContext('2d');
      c.width = c.height = F;
      if (drawn.smooth) { g.fillStyle = rgb(cv.fill); g.fillRect(0, 0, F, F); }
      g.drawImage(cv, 0, 0, F, F, 0, 0, F, F);
      c.className = 'af-cal-swatch';
      return c;
    };
    const keyBox = box.querySelector('.af-cal-key'), word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
    keyBox.textContent = '';  // (and each appended alone: Chromium 77, Anki 2.1.45's, has no replaceChildren)
    // (Less .. More, by reviews or by time alike: a shade pointed at gives its numbers)
    const ends = H.by === 'median' ? ['Slow', 'Fast'] : ['Less', 'More'];
    [word(ends[0])].concat(drawn.key.map(swatch), [word(ends[1])]).forEach(el => keyBox.appendChild(el));
    viewBox.querySelectorAll('button').forEach(b => {
      const on = b.dataset.view === view;
      b.classList.toggle('af-on', on); b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1;
    });
    past();
    byBox.querySelectorAll('button').forEach(b => {
      const on = b.dataset.by === H.by;
      b.classList.toggle('af-on', on); b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1;
    });
    if (!swiped) {
      const may = can(win);
      btn(-1).disabled = !may.back; btn(1).disabled = !may.on;
      // (on today's page already, the jump stays where it is, dimmed; it points the way today
      // lies, » from the past, « from the days ahead)
      const now = btn(0), ahead = view === 'by_year' ? (year || yearOf(H.today)) > yearOf(H.today) : page > 0;
      now.disabled = view === 'by_year' ? win.year === yearOf(H.today) : page === 0;
      now.textContent = ahead ? '«' : '»';
      // (a button gone out of use under the keyboard - ‹ at the start of your history, › at the end,
      // » once back - hands its focus to the arrow still in use, so Tab starts from where you were)
      if (focused && focused.disabled) { const to = [btn(1), btn(-1)].find(b => b !== focused && !b.disabled); if (to) to.focus(); }
    }
    lay();
  }
  const cards = (n, what) => `${num(n)} ${what}${n === 1 ? '' : 's'}`;
  // the time a day's reviews took: "in 48 min", "in 1 hr 12 min" ("" where there is none to tell)
  const took = o => (H.time(o) ? ` in ${lasted(H.time(o))}` : '');
  // the days studied from one day to another, and their share: "Studied 26 of 31 days (84%)", the
  // reviews and about how many a day; only the days since your first review, up to today
  const studiedLines = (from, to) => {
    // (today counts once studied: until then it isn't over, nor missed)
    const end = H.n(0) ? 0 : -1, a = Math.max(from, H.first), b = Math.min(to, end);
    if (b < a) return [a === 0 ? 'Not studied yet' : H.hid !== null && b < H.hid ? 'Before your forest began' : 'Before your first review'];
    let studied = 0, reviews = 0, secs = 0;
    for (let o = a; o <= b; o++) if (H.n(o)) { studied++; reviews += H.n(o); secs += H.time(o) || 0; }
    // (a stretch your history starts inside counts from your first review: "since Mar 1")
    const since = a > from ? ` since ${new Date(H.today + a * DAY_MS).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' })}` : '';
    const span = b - a + 1, now = since || (b === end && to > end ? ' so far' : '');
    if (!studied) return [`Not studied${now}`];
    // (short enough not to wrap: the totals on one line, the day's average on the next, "studied"
    // only where some days were missed; the time where the review log kept it)
    const on = studied < span ? ' studied' : '', avg = cards(Math.round(reviews / studied), 'review');
    return [studied === span ? `Studied every day${now}` : `Studied ${num(studied)} of ${num(span)} day${span === 1 ? '' : 's'}${now} (${Math.min(99, Math.max(1, Math.round(100 * studied / span)))}%)`,  // (never 100% with a day missed, nor 0% with one studied)
      cards(reviews, 'review') + (secs ? ` in ${lasted(secs)}` : ''),
      `About ${avg}${secs ? ` and ${lasted(secs / studied)}` : ''} a day${on}`];
  };
  // By year's earlier years, all shown or all hidden by one switch over the heatmap ("Show 2 earlier
  // years"), each a whole year with its line of words over it, as the year in view is drawn: above
  // it, oldest at the top, so the picture reads down to now as a calendar does; showing or hiding
  // them keeps the year in view where it was on screen (the page scrolled by what came or went above
  // it). Not kept: By year always opens on the year in view alone (kept, it reopened on 2015)
  const pastBox = box.querySelector('.af-cal-past');
  grid.insertBefore(pastBox, grid.firstChild);  // (before the year in view's weeks: they follow it)
  // (false, true: back to the streak worth seeing, or 'all': back to the first review)
  let yearsShown = false, pasts = [], near = null;
  // each earlier year's weeks as last painted, painted again only when what they show changes: the
  // shade's choice, the page's colour, a mark in that year (the look and the days come with a new
  // calendar; a new scale only sharpens them again, layPast)
  const painted = new Map();
  const paintPast = (y, win) => {
    const key = [H.by, paper.dark, paper.bg.join(), [...H.marked].filter(([o]) => o >= win.from && o <= win.to)
      .map(([o, m]) => `${o}:${m.icon}:${m.name}`).join()].join('|');
    const was = painted.get(y);
    if (was && was.key === key) return was.d;
    const d = Object.assign(paint(H, win, sp, paper), { win });
    painted.set(y, { key, d });
    return d;
  };
  function past() {
    pastBox.textContent = '';
    pasts = [];
    if (near) { near.remove(); near = null; }
    box.classList.remove('af-cal-years-open');
    const y0 = drawn.win.year, every = swiped || view !== 'by_year' ? [] : pastYears(H, y0, true);
    if (!every.length) return;
    // (the switch reaches the streak worth seeing; with none before the year in view, every year)
    const streak = pastYears(H, y0, false), years = yearsFor(H, y0, yearsShown), reach = streak.length ? streak : every;
    const n = reach.length, toAll = !streak.length;
    const name = yearsShown ? (years.length === 1 ? `Hide ${years[0]}` : 'Hide the earlier years')
      : n === 1 ? `Show ${reach[0]}` : toAll ? `Show all years, back to ${reach[n - 1]}` : `Show ${n} earlier years`;
    const bar = document.createElement('div'), more = document.createElement('button');
    bar.className = 'af-cal-pastbar';
    more.type = 'button'; more.className = 'af-cal-more';
    more.setAttribute('aria-expanded', !!yearsShown);
    more.title = yearsShown ? (years.length === 1 ? `Hide ${years[0]}` : `Hide ${years[years.length - 1]} to ${years[0]}`)
      : n === 1 ? `Show ${reach[0]}` : `Show the earlier years, back to ${reach[n - 1]}`;
    more.innerHTML = `<span class="af-cal-more-chev" aria-hidden="true">${yearsShown ? '\u25be' : '\u25b4'}</span>${esc(name)}`;
    const set = state => {
      const was = drawn.cv.getBoundingClientRect().top;
      yearsShown = state;
      unpoint();
      past();
      lay();
      // (what came or went is above the year in view: the page follows, so it stays put on screen)
      const moved = drawn.cv.getBoundingClientRect().top - was;
      if (moved) window.scrollBy(0, moved);
      if (state && animates(data)) pastBox.classList.add('af-cal-past-in');
    };
    more.addEventListener('mousedown', e => e.preventDefault());
    more.addEventListener('click', () => set(yearsShown ? false : toAll ? 'all' : true));
    pastBox.classList.remove('af-cal-past-in');
    // (closed: the switch alone, in the band over the months on the left, taking no room; shown: in
    // a row over the earliest year, and Hide again where Show was: placed in lay)
    if (!yearsShown) {
      near = more;
      near.classList.add('af-cal-more-near');
      grid.appendChild(near);
      return;
    }
    bar.appendChild(more);
    pastBox.appendChild(bar);
    // (back to the first review, one more click: the years before the streak worth seeing)
    const rest = yearsShown ? every.slice(years.length) : [];
    if (rest.length) {
      const all = document.createElement('button');
      all.type = 'button'; all.className = 'af-cal-more af-cal-more-all';
      all.title = rest.length === 1 ? `Show ${rest[0]} too` : `Show ${rest[rest.length - 1]} to ${rest[0]} too, back to your first review`;
      all.innerHTML = `<span class="af-cal-more-chev" aria-hidden="true">\u25b4</span>${rest.length === 1 ? `Show ${rest[0]}` : `Show all years, back to ${rest[rest.length - 1]}`}`;
      all.addEventListener('mousedown', e => e.preventDefault());
      all.addEventListener('click', () => set('all'));
      bar.appendChild(all);
    }
    // (shown: one picture down to the year in view, the "Since" under it gone, the years above
    // saying it; and Hide also where Show was, so it is found where it was pressed)
    box.classList.add('af-cal-years-open');
    near = more.cloneNode(true);
    near.classList.add('af-cal-more-near');
    near.addEventListener('mousedown', e => e.preventDefault());
    near.addEventListener('click', () => set(false));
    grid.appendChild(near);
    for (const y of years.slice().reverse()) {
      const win = windowOf(H, 'by_year', 0, y), d = paintPast(y, win), el = document.createElement('div');
      const [first, second] = studiedLines(win.from, win.to);
      el.className = 'af-cal-past-year';
      el.innerHTML = `<div class="af-cal-past-head"><b>${y}</b><span>${esc(first)}${second ? ` \u00b7 ${esc(second)}` : ''}</span></div>`;
      d.cv.className = 'af-cal-canvas af-cal-past-weeks';
      d.cv.setAttribute('role', 'img');
      d.cv.setAttribute('aria-label', described(win));
      d.above.className = 'af-cal-above';
      el.appendChild(d.cv);
      el.appendChild(d.above);
      pastBox.appendChild(el);
      pasts.push(d);
    }
  }
  function layPast() {
    for (const d of pasts) {
      d.cv.style.width = d.above.style.width = d.W * k + 'px'; d.cv.style.height = d.above.style.height = d.Hh * k + 'px';
      d.above.style.left = d.cv.offsetLeft + 'px'; d.above.style.top = d.cv.offsetTop + 'px';
      d.cv.style.imageRendering = d.above.style.imageRendering = k < sharpK() ? 'auto' : '';
      if (d.sharpen) d.sharpen(k * dpr());
    }
  }
  function go(where) {
    const was = drawn.win.from;
    if (where === '0') { page = 0; year = null; }
    else {
      const may = can(drawn.win);
      if (where === '-1' ? !may.back : !may.on) return;  // (a click on a button just disabled)
      if (view === 'by_year') year = (year || yearOf(H.today)) + +where;
      else page += +where * drawn.count;
    }
    unpoint();
    draw();
    // the new stretch slides in from the side you went towards (unless the forest is kept still)
    if (drawn.win.from !== was && animates(data)) {
      grid.classList.remove('af-cal-from-left', 'af-cal-from-right');
      void grid.offsetWidth;  // (so the animation starts again on a quick second click)
      grid.classList.add(drawn.win.from < was ? 'af-cal-from-left' : 'af-cal-from-right');
    }
  }
  // fitted to the room there is, all its width (By year its year, Timeline its months, countFor),
  // smaller than its pixels if need be: no scrolling, smoothed where that leaves no whole device
  // pixel (sharpK)
  function lay() {
    const d = drawn;
    k = swiped ? Math.round((data.swipedK || SWIPED_K) * dpr()) / dpr() : (grid.clientWidth || d.W * 2) / d.W;
    // (the room over the year in view's weeks for its months, under the earlier years if any; and,
    // with them shown, for the controls over the months too)
    grid.style.paddingTop = '0px';
    pastBox.style.paddingBottom = monthsRoom(k) + (box.classList.contains('af-cal-years-open') ? ACTS_ROOM : 0) + 'px';
    d.cv.style.width = d.above.style.width = d.W * k + 'px'; d.cv.style.height = d.above.style.height = d.Hh * k + 'px';
    layPast();
    // (the layer placed once the earlier years above are laid out: their size moves the year in
    // view down, and a layer placed before sat that much too high, its trophies over another year)
    d.above.style.left = d.cv.offsetLeft + 'px'; d.above.style.top = d.cv.offsetTop + 'px';
    // (the key's tiles as big as the calendar's, and as far apart)
    box.querySelectorAll('.af-cal-swatch').forEach((sw, i, all) => {
      const F = d.smooth ? TILE_FACE : TILE;
      sw.style.width = sw.style.height = F * k + 'px'; if (i < all.length - 1) sw.style.marginRight = (CELL - F) * k + 'px';
      sw.style.borderRadius = d.smooth ? d.radius * k + 'px' : '';
    });
    d.cv.style.imageRendering = d.above.style.imageRendering = k < sharpK() ? 'auto' : '';  // (too small to stay crisp, pixels smooth better than they drop)
    if (d.sharpen) d.sharpen(k * dpr());
    let html = '', lastM = -1;
    for (const c of d.cells) {
      const day = new Date(c.ms);
      if (day.getUTCDate() > 7 || day.getUTCMonth() === lastM || c.x * k > d.W * k - LABEL_END) continue;
      lastM = day.getUTCMonth();
      // January is its year alone, every other month its name
      const text = lastM === 0 ? String(day.getUTCFullYear()) : MONTHS[lastM];
      html += `<span${text !== MONTHS[lastM] ? ' class="af-cal-year"' : ''} data-y="${day.getUTCFullYear()}" data-m="${lastM}" style="left:${c.x * k}px">${text}</span>`;
    }
    months.innerHTML = html;
    months.style.top = d.cv.offsetTop - monthsRoom(k) + 'px';
    // the weekdays of the second, fourth and sixth rows, beside the weeks (shown with the key, on hover)
    // (not where they would hang off the page: they stand just outside the forest's edge)
    if (!swiped) {
      const top = d.cv.offsetTop;
      days.innerHTML = [1, 3, 5].map(r => `<span style="top:${top + (d.band + r * CELL + TILE / 2) * k}px">${WEEKDAYS[(weekStart + r) % 7]}</span>`).join('');
      days.hidden = box.getBoundingClientRect().left < DAYS_ROOM;
    }
    // where two would touch (a narrow calendar), the one with a year stays and the other goes
    let prev = null;
    for (const s of months.children) {
      if (prev && s.offsetLeft < prev.offsetLeft + prev.offsetWidth + LABEL_GAP) {
        const drop = prev.classList.contains('af-cal-year') && !s.classList.contains('af-cal-year') ? s : prev;
        drop.hidden = true;
        if (drop === s) continue;
      }
      prev = s;
    }
    // ‹ Today › stand over the months' row, in the gap above it, unless the forest's caption's last
    // line reaches them there: then they go down onto the row, and a label under them makes way
    // while they show (forest.css)
    if (!swiped) {
      acts.classList.remove('af-acts-low');
      acts.style.top = months.offsetTop - ACTS_ROOM + 'px';
      if (near) near.style.top = months.offsetTop - ACTS_ROOM + 'px';
      const a = acts.getBoundingClientRect(), cap = root.querySelector('.af-caption');
      const words = cap ? [...cap.children].map(el => el.getBoundingClientRect()).filter(r => r.width && r.bottom > a.top - 30) : [];
      const low = words.some(r => r.right > a.left - LABEL_GAP && r.bottom > a.top - 4);
      acts.classList.toggle('af-acts-low', low);
      if (low) acts.style.top = months.offsetTop + 'px';
      const edge = acts.offsetLeft - LABEL_GAP;
      for (const s of months.children) s.classList.toggle('af-under', low && s.offsetLeft + s.offsetWidth > edge);
    }
    // each streak's length, the current one's too, centred under its bracket
    notes.style.top = d.cv.offsetTop + (d.band + ROWS * CELL + 3 + 7) * k - NOTE_H / 2 + 'px';
    notes.innerHTML = d.brackets.filter(b => (b.x1 - b.x0) * k >= NOTE_ROOM + 2 * (7 * k + 4)).map(b => {
      const since = b.live && b.cut && !box.classList.contains('af-cal-years-open') && (b.x1 - b.x0) * k >= SINCE_ROOM + NOTE_ROOM
        ? ` · Since ${esc(fmt(H.today + b.run.from * DAY_MS))}` : '';
      return `<span class="af-cal-note${b.live ? ' af-cal-current' : ''}" style="left:${(b.x0 + b.x1) / 2 * k}px">${num(b.len)} days${since}</span>`;
    }).join('');
    if (swiped) { away(); clip(); }
  }
  // the phone's timeline: opened on today, most of the way across, the days behind it in view
  function toToday(smooth) {
    const today = drawn.cells.find(c => c.o === 0), left = today ? Math.max(0, today.x * k - grid.clientWidth * SWIPED_TODAY_AT) : 0;
    if (smooth && grid.scrollTo) grid.scrollTo({ left, behavior: 'smooth' }); else grid.scrollLeft = left;
  }
  // (the timeline: Today only while today is scrolled out of view; a month's label cut by an
  // edge hidden until whole)
  function away() {
    const t = drawn.cells.find(c => c.o === 0);
    if (!t) return;
    const x = t.x * k - grid.scrollLeft;
    btn(0).hidden = x > 0 && x < grid.clientWidth - TILE * k;
  }
  function clip() {
    for (const s of months.children) s.style.visibility = s.offsetLeft < grid.scrollLeft + 4 || s.offsetLeft + s.offsetWidth > grid.scrollLeft + grid.clientWidth - 4 ? 'hidden' : '';
  }
  draw();
  if (swiped) {
    toToday(false);
    // (a tooltip goes with a swipe: it would point at a day no longer under it)
    grid.addEventListener('scroll', () => { away(); clip(); if (!tip.hidden) unpoint(); }, { passive: true }); away(); clip();
    // turned on its side (the phone's full screen, web/phone.js), a swipe along the calendar runs
    // down the screen, which the page's own scrolling won't follow: it is followed here
    let from = null;
    grid.addEventListener('touchstart', e => { from = grid.closest('.af-sideways') && e.touches.length === 1 ? [e.touches[0].clientY, grid.scrollLeft] : null; }, { passive: true });
    grid.addEventListener('touchmove', e => {
      if (!from) return;
      e.preventDefault();
      grid.scrollLeft = from[1] - (e.touches[0].clientY - from[0]);
    }, { passive: false });
    grid.addEventListener('touchend', () => { from = null; });
  }
  // a new width: Timeline's months counted again (draw), or the same ones laid out again
  let lastW = grid.clientWidth;
  const ro = window.ResizeObserver ? new ResizeObserver(() => {
    if (!box.isConnected) { stop(); return; }
    if (grid.clientWidth === lastW) return;
    lastW = grid.clientWidth;
    if (!swiped && countFor(view, lastW) !== drawn.count) draw(); else lay();
    if (editing) placePin();  // (a mark's editor, open, stays by its day)
  }) : null;
  if (ro) ro.observe(grid);
  // Anki switched between light and dark: the page's colour is read again and the days painted
  // for it (their shades, the animals' outlines, today's frame). Anki marks the switch on the
  // page's classes, and the system's own switch shows in the colour scheme; a moment later too,
  // for a page whose colour eases across
  const repaper = () => {
    if (!box.isConnected) return;
    const p = pageOf(box);
    if (p.bg.join() === paper.bg.join()) return;
    paper = p; unpoint();
    box.classList.toggle('af-cal-on-light', !paper.dark);
    draw();
  };
  const rethink = () => { if (!box.isConnected) { stop(); return; } requestAnimationFrame(repaper); setTimeout(repaper, THEME_SETTLE_MS); };
  const mo = window.MutationObserver ? new window.MutationObserver(rethink) : null;
  for (const el of [document.documentElement, document.body]) if (mo && el) mo.observe(el, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] });
  const scheme = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  if (scheme && scheme.addListener) scheme.addListener(rethink);
  function stop() {
    if (mo) mo.disconnect();
    if (ro) ro.disconnect();
    if (scheme && scheme.removeListener) scheme.removeListener(rethink);
    if (root.afCalStop === stop) root.afCalStop = null;
  }
  root.afCalStop = stop;

  // the day under the pointer (or an animal's, a pin's or a trophy's above or below the weeks):
  // its square's column and row, the gaps between tiles counted with the tile before them
  // (a finger's tap counts a little way round one, the nearest, as it hides what it touches;
  // never on the weeks themselves, where the tap is a day's)
  let touched = false;  // (the last press a finger's: pointerdown below)
  // (where on the canvas, AF.u.pointIn: right on a page the app zooms and in the phone's sideways
  // view; on anything but the canvas, nothing)
  let hit = null;  // (the mark over or under the weeks the pointer is on, if any: cellAt)
  const cellAt = e => {
    hit = null;
    // (the year in view, or an earlier one shown under it)
    pointed = e.target === drawn.cv ? drawn : pasts.find(d => d.cv === e.target) || null;
    if (!pointed) return null;
    const [x, y] = AF.u.pointIn(e, pointed.cv), px = x / k, py = y / k;
    const pad = touched && (py < pointed.band || py >= pointed.band + ROWS * CELL) ? TOUCH_PAD : 0;
    const off = m => Math.max(m.x0 - px, 0, px - m.x1 + 1) + Math.max(m.y0 - py, 0, py - m.y1 + 1);
    const mark = pointed.marks.filter(m => px >= m.x0 - pad && px < m.x1 + pad && py >= m.y0 - pad && py < m.y1 + pad)
      .sort((a, b) => off(a) - off(b))[0];
    hit = mark || null;
    if (mark) return mark.c;
    // (or a streak's bracket, or the lane under it: the streak itself)
    const by = pointed.band + ROWS * CELL + 3, br = py >= by - 3 && py < by + 12 ? pointed.brackets.find(b => px >= b.x0 - 1 && px <= b.x1 + 1) : null;
    if (br) { hit = br; return null; }
    // (a drafted shape: the pixel's own day, as it drew it, not the square of the grid)
    const pane = pointed.pane && px >= 0 && py >= 0 && px < pointed.W && py < pointed.Hh ? pointed.pane[Math.floor(py) * pointed.W + Math.floor(px)] : -1;
    if (pane >= 0) return pointed.cells[pane];
    const col = Math.floor(px / CELL), row = Math.floor((py - pointed.band) / CELL);
    return px >= 0 && row >= 0 && row < ROWS ? pointed.at.get(col * ROWS + row) || null : null;
  };
  // which days a click opens: a day with reviews (today too, once studied), a day ahead with cards
  // due, and today before you study, its cards due
  const dueNow = c => c.o === 0 && !c.n && H.dueToday > 0;
  // (not a day whose cards have all since been deleted: the browser would open on none)
  const allGone = o => { const g = H.gone.get(o); return !!g && g[0] >= g[1]; };
  const opens = c => cal.browse && (c.n > 0 || dueNow(c)) && c.o <= H.ahead && c.o >= H.first && !allGone(c.o);
  // a month in a few words, on its label: its days studied; and for the days ahead in it, the cards
  // due. January's label shows its year, so it tells the year's days studied first
  const monthSummary = (y, m) => {
    const at = (yy, mm) => (Date.UTC(yy, mm, 1) - H.today) / DAY_MS;
    const from = at(y, m), to = at(y, m + 1) - 1;
    const year = m === 0 && from <= 0 ? [`<b>${y}</b>`, ...studiedLines(from, at(y + 1, 0) - 1), ''] : [];
    const lines = [...year, `<b>${MONTH_NAMES[m]} ${y}</b>`, ...(from > 0 ? [] : studiedLines(from, to))];
    // (its marked days, by date and name, as their tooltips name them)
    const marked = [...H.marked].filter(([o]) => o >= from && o <= to).sort((p, q) => p[0] - q[0]);
    for (const [o, mk] of marked.slice(0, 4)) lines.push(`<i>${new Date(H.today + o * DAY_MS).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' })}:</i> ${esc(mk.name || markOf(mk).label)}`);
    if (marked.length > 4) lines.push(`<i>and ${marked.length - 4} more marked</i>`);
    let due = 0;
    for (let o = Math.max(from, 1); o <= Math.min(to, H.ahead); o++) due += H.n(o);
    if (due) lines.push(`${cards(due, 'card')} due${from > 0 ? '' : ' later this month'}`);
    else if (from > H.ahead) lines.push('Too far ahead to count');
    else if (from > 0) lines.push('Nothing due yet');
    return lines.join('<br>');
  };
  const pointMonth = lab => {
    pointTree(null);
    ring(null);
    // (its days stand out while it tells them)
    spot(c => { const d = new Date(c.ms); return d.getUTCFullYear() === +lab.dataset.y && d.getUTCMonth() === +lab.dataset.m; });
    grid.classList.remove('af-click');
    tip.innerHTML = monthSummary(+lab.dataset.y, +lab.dataset.m);
    reveal();
    const r = lab.getBoundingClientRect(), b0 = box.getBoundingClientRect();
    const cx = r.left - b0.left + r.width / 2, over = r.top - b0.top - tip.offsetHeight - TIP_GAP;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    // (above its label, off the month's own weeks; under it when the window has no room above)
    tip.style.top = (r.top - tip.offsetHeight - TIP_GAP < 0 ? r.bottom - b0.top + TIP_GAP : over) + 'px';
  };
  // a shade in the key, pointed at, tells what it stands for, in a few words: "65–109 reviews",
  // "8–12 min", "Under 3 min", "154+ reviews"
  const shadeLine = lv => {
    const s = H.splits(), by = H.by === 'time';
    if (H.by === 'median') {
      lv = 3 - lv;
      // ("Under 3.2 s per answer", "3.2–4.1 s per answer", "4.1+ s per answer": as the other keys' lines)
      const t = v => v.toFixed(1);
      return (lv === 0 ? `Under ${t(s[1])}` : lv === 3 ? `${t(s[3])}+` : `${t(s[lv])}\u2013${t(s[lv + 1])}`) + ' s per answer';
    }
    const at = i => by ? lasted(s[i]) : num(s[i]), upto = i => by ? lasted(s[i] - 60) : num(s[i] - 1);
    const unit = by ? '' : ' reviews';
    if (lv === 0) return `Under ${at(1)}${unit}`;
    if (lv === 3) return by && /^[0-9]+ min$/.test(at(3)) ? `${at(3).slice(0, -4)}+ min` : `${at(3)}+${unit}`;  // ("20+ min", as "154+ reviews")
    const lo = at(lv), hi = upto(lv + 1);
    if (lo === hi) return by ? lo : cards(s[lv], 'review');
    // ("8–12 min": the first minutes' unit left to the second)
    const from = !by ? lo : lo === 'a minute' ? '1' : / min$/.test(hi) && !/hr/.test(lo + hi) ? lo.slice(0, -4) : lo;
    return `${from}\u2013${hi}${unit}`;
  };
  const keyEl = box.querySelector('.af-cal-key');
  keyEl.addEventListener('mouseover', e => {
    const sw = e.target.classList && e.target.classList.contains('af-cal-swatch') ? e.target : null;
    const lv = sw ? [...keyEl.querySelectorAll('.af-cal-swatch')].indexOf(sw) : -1;
    if (lv < 0 || sw === last) return;
    last = sw;
    pointTree(null);
    ring(null);
    tip.textContent = shadeLine(lv);
    tip.hidden = false;
    const r = sw.getBoundingClientRect(), b0 = box.getBoundingClientRect();
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, r.left - b0.left + r.width / 2 - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (r.top - b0.top - tip.offsetHeight - TIP_GAP) + 'px';  // (above the key, at the heatmap's foot)
    spot(c => c.o <= 0 && c.n > 0 && !H.timeless(c.o) && H.shade(c.o) === lv, lv);  // (and its days stand out)
  });
  keyEl.addEventListener('mouseleave', unpoint);
  // a streak's bracket, pointed at: its first and last days, and its days lit
  const streak = b => {
    const r = b.run, day = o => esc(fmt(H.today + o * DAY_MS)), year = o => yearOf(H.today + o * DAY_MS);
    // ("Jun 1 to Dec 19, 2025": a year said once)
    const first = !b.live && year(r.from) === year(r.to) ? day(r.from).replace(/, [0-9]{4}$/, '') : day(r.from);
    tip.innerHTML = `<b>${first} to ${b.live ? 'today' : day(r.to)}</b><br>${b.live ? `Your ${num(r.days)}-day streak` : `${num(r.days)} days in a row`}`;
    tip.hidden = false;
    const on = pointed || drawn, left = grid.offsetLeft + on.cv.offsetLeft - grid.scrollLeft, cx = left + (b.x0 + b.x1) / 2 * k;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = grid.offsetTop + on.cv.offsetTop + (on.band + ROWS * CELL + BRACKET) * k + TIP_GAP + 'px';  // (under the lane)
    spot(c => c.o >= r.from && c.o <= r.to);
  };
  // its date, its reviews or cards due, and where it sits in its streak
  const point = e => {
    if (editing) return;  // (no tooltips while a mark is named: its day keeps the ring)
    // (the footer: its key and switches answer for themselves)
    if (e.target && e.target.closest && e.target.closest('.af-cal-foot')) return;
    const lab = e.target && e.target.closest ? e.target.closest('.af-cal-months span') : null;
    if (lab) pointed = null;
    if (lab) { if (lab !== last) { last = lab; pointMonth(lab); } return; }
    const c = cellAt(e), on = hit || c;
    if (on === last) return;  // (still on the same day, or mark: nothing changes)
    last = on;
    tell(c);
  };
  // a day's tooltip and ring, for the pointer's day or the keyboard's
  const tell = c => {
    pointTree(c);
    ring(c);
    grid.classList.toggle('af-click', !!c && opens(c));
    if (!c) { tip.hidden = true; if (hit && hit.run) streak(hit); return; }
    const off = c.o <= 0 && !c.n && H.free.has(c.o);  // (a day with nothing due)
    const run = c.o <= 0 && (c.n || off) ? H.runOf(c.o) : null;
    const what = c.o < H.first ? (H.hid !== null && c.o < H.hid ? 'Before your forest began' : 'Before your first review')
      : c.o > H.ahead ? 'Too far ahead to count'
      : c.o > 0 ? (c.n ? `${cards(c.n, 'card')} due` : 'Nothing due yet')
      : c.o === 0 && !c.n && H.dueToday ? `Not studied yet, ${cards(H.dueToday, 'card')} due`
      : c.n && H.by === 'median' && H.answerTime(c.o) !== null ? `Median ${H.answerTime(c.o).toFixed(1)} s per answer, ${cards(c.n, 'review')}${c.o === 0 && H.dueToday ? `, ${num(H.dueToday)} still due` : ''}`
      : c.o === 0 && H.dueToday ? (H.by === 'time' && H.time(c.o) ? `${cap(lasted(H.time(c.o)))} so far, ${cards(c.n, 'review')}` : `${cards(c.n, 'review')} so far${took(c.o)}`) + `, ${num(H.dueToday)} still due`
      // (shaded by time, the time first: "2 hr 9 min, 420 reviews")
      : c.n ? (H.by !== 'time' ? cards(c.n, 'review') + took(c.o) : H.time(c.o) ? `${cap(lasted(H.time(c.o)))}, ${cards(c.n, 'review')}` : `${cards(c.n, 'review')}, no time kept`) : H.daysOff.has(c.o) ? 'Not studied: a day off' : off ? (c.o === 0 ? 'Nothing due today' : 'Nothing was due')
      : H.pond.has(c.o) ? 'Not studied: a pond in your forest' : c.o === 0 ? 'Not studied yet' : 'Not studied';
    // (where in its streak, in days studied)
    let day = 0;
    for (let o = run ? run.from : 1; o <= c.o; o++) if (H.n(o)) day++;
    const total = run ? run.days : 0;
    // (a lone day between missed ones is no run: nothing to say)
    const where = run && off ? (run === H.current ? `Doesn't break your ${num(total)}-day streak` : `Didn't break a ${num(total)}-day streak`) : !run || (total === 1 && run !== H.current) ? ''
      : (run === H.current ? (day === total ? `Day ${num(day)} of your streak` : `Day ${num(day)} of your ${num(total)}-day streak`) : day === total && total >= SHOWN_STREAK ? `Last day of a ${num(total)}-day streak` : total >= SHOWN_STREAK ? `Day ${num(day)} of a ${num(total)}-day streak` : `Day ${num(day)} of ${num(total)} in a row`)
        // (which of your longest it is: on its trophy, not on each of its days)
        + (hit && hit.trophy >= 0 && H.podium.has(run) ? `<br>Your ${TROPHIES[hit.trophy].place} streak` : '');
    const goal = H.goal && H.goal.o === c.o
      // (with no earlier streak of that rank to pass, the goal is a trophy's first length)
      ? (H.goal.beats ? `<br>${H.goal.rank ? 'Pass' : 'Beat'} your ${GOALS[H.goal.rank].place} streak (${num(H.goal.beats)} days) on this day`
        : `<br>Reach a ${num(SHOWN_STREAK)}-day streak on this day`)
        // (the soonest it can be, with days off a week allowed: if you take none of them)
        + ((data.stats && data.stats.streak_week || 7) < 7 ? ', studying every day until then' : '') : '';
    const began = H.fs === c.o ? '<br>Your forest began' : H.fs !== null && c.o < H.fs && c.o >= H.first ? '<br><i>Before your forest began</i>' : '';
    const came = goal + began + (H.animals.get(c.o) || []).map(a => `<br>${esc(cap(a.label))} came: ${esc(a.why)}`).join('');
    const marked = H.marked.has(c.o) ? `<br>${esc(markLine(H.marked.get(c.o), c.o))}` : '';
    // (in cards, not reviews: a card reviewed twice that day counts once)
    const [lost, of] = c.o <= 0 && c.n ? H.gone.get(c.o) || [0, 0] : [0, 0];
    const gone = !lost ? '' : lost >= of ? `<br><i>${of === 1 ? 'Its card has' : of === 2 ? 'Both of its cards have' : `All ${num(of)} of its cards have`} since been deleted</i>`
      : `<br><i>${num(lost)} of its ${num(of)} cards ${lost === 1 ? 'has' : 'have'} since been deleted</i>`;
    // (today, yesterday and tomorrow by name, the year left out)
    const near = { '-1': 'Yesterday', 0: 'Today', 1: 'Tomorrow' }[c.o];
    const head = `<b>${near ? `${near}, ${esc(weekday(c.ms))}, ${esc(fmt(c.ms).replace(/, \d{4}$/, ''))}` : `${esc(weekday(c.ms))}, ${esc(fmt(c.ms))}`}</b>`;
    // (a trophy pointed at: its day and its streak, no more; the day's own numbers are on its tile)
    const trophy = hit && hit.trophy >= 0 && run && H.podium.has(run);
    const tree = data.showForest === false || c.o < H.first ? null : treesByDay.get(c.o), planted = tree ? `<br>${esc(cap(AF.WORDS.planted))} ${esc(AF.WORDS.one || 'tree')}: ${num(tree.n)} new cards` : '';
    const zoom = root.afVisits, scene = root.afEnv;
    const inView = tree && scene && scene.placed.some(p => !p.it.pond && p.it.ago === tree.ago);
    const location = !tree || data.showForest === false || inView ? '' : zoom && zoom.on
      ? '<br><i>This tree is outside your current zoom view</i>'
      : data.merged && tree.ago >= data.merged.to_ago && tree.ago <= data.merged.from_ago
        ? '<br><i>This day’s tree is part of your deep forest</i>' : '';
    tip.innerHTML = trophy ? `${head}<br>Your ${TROPHIES[hit.trophy].place} streak: ${num(total)} days`
      : `${head}<br>${what}${planted}${location}${gone}${where ? `<br><i>${where}</i>` : ''}${came}${marked}`;
    reveal();
    // below the day, centred on it, so it never covers ‹ Today › and the months over the weeks
    // (above it when there is no room below in the window), kept inside the calendar's sides;
    // placed by the page's own offsets, which a zoomed page leaves right
    const on = (pointed || drawn).cv, left = grid.offsetLeft + on.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + on.offsetTop;
    const cx = left + (c.x + TILE / 2) * k, top = canvasTop + (c.y - 1) * k, bottom = canvasTop + (c.y + TILE + 1) * k;
    const above = on.getBoundingClientRect().top + (c.y + TILE + 1) * k + TIP_GAP + tip.offsetHeight > window.innerHeight;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (above ? top - tip.offsetHeight - TIP_GAP : bottom + TIP_GAP) + 'px';
  };
  grid.addEventListener('mousemove', point);
  // the days by the keyboard: ← → a week, ↑ ↓ a day, the page turning at its ends; PageUp and
  // PageDown a page, Home back to today; each day's tooltip as the pointer gives it; Enter opens
  // the day, Esc puts the tooltip away
  let cur = null;
  const curCell = () => drawn.cells.find(c => c.o === cur) || null;
  const toCur = () => { cur = Math.max(drawn.win.from, Math.min(drawn.win.to, cur)); hit = null; last = curCell(); tell(last); };
  if (!swiped) {
    tip.setAttribute('aria-live', 'polite');
    grid.addEventListener('focusin', e => {
      if (e.target !== drawn.cv) return;
      if (cur === null || !curCell()) cur = drawn.cells.some(c => c.o === 0) ? 0 : drawn.win.to;
      toCur();
    });
    grid.addEventListener('focusout', e => { if (e.target === drawn.cv) unpoint(); });
    grid.addEventListener('keydown', e => {
      if (e.target !== drawn.cv || e.altKey || e.ctrlKey || e.metaKey) return;
      const step = { ArrowLeft: -7, ArrowRight: 7, ArrowUp: -1, ArrowDown: 1 }[e.key], pg = { PageUp: '-1', PageDown: '1' }[e.key];
      if (e.key === 'Escape') { if (!tip.hidden) { e.preventDefault(); e.stopPropagation(); unpoint(); } return; }
      if (e.key === 'Enter') { e.preventDefault(); const c = curCell(); if (c && opens(c)) send(`${data.channel}:day:${c.o}:${deck}${dueNow(c) ? ':due' : ':' + H.by}`); return; }
      if (e.key === 'Home') { e.preventDefault(); cur = 0; if (!curCell()) go('0'); toCur(); return; }
      if (!step && !pg) return;
      e.preventDefault();
      if (pg) { const along = cur - drawn.win.from; go(pg); cur = drawn.win.from + along; }
      else {
        cur += step;
        const may = can(drawn.win);
        if (cur < drawn.win.from && may.back) go('-1'); else if (cur > drawn.win.to && may.on) go('1');
      }
      toCur();
    });
  }
  // a finger's tap, taken as it lifts (a phone's web view need not make up a mouse's move for
  // it), unless it was a swipe along the timeline
  let down = null;
  grid.addEventListener('pointerdown', e => {
    touched = e.pointerType !== 'mouse';
    down = touched ? [e.clientX, e.clientY] : null;
  });
  grid.addEventListener('pointerup', e => {
    if (down && Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) < TAP_SLOP) {
      // (a second tap on what shows its tooltip puts it away)
      const again = !tip.hidden && last;
      last = undefined; point(e);
      if (again && last === again) { unpoint(); last = again; }  // (the mouse a phone makes up after must not bring it back)
    }
    down = null;
  });
  grid.addEventListener('pointercancel', () => { down = null; });
  grid.addEventListener('mouseleave', () => { unpoint(); grid.classList.remove('af-click'); });
  // a sideways swipe on a trackpad (or Shift and the wheel) turns the page, once a swipe: the
  // swipe's own momentum turns no more
  let swept = 0, sweeping = 0, lastDx = 0;
  if (!swiped) grid.addEventListener('wheel', e => {
    const dx = e.deltaX || (e.shiftKey ? e.deltaY : 0);
    if (!dx || Math.abs(dx) <= (e.shiftKey ? 0 : Math.abs(e.deltaY))) return;
    e.preventDefault();
    clearTimeout(sweeping);
    sweeping = setTimeout(() => { swept = 0; lastDx = 0; }, SWIPE_QUIET);
    // (a swipe's momentum only slows; picking up speed again, or turning back, is a new swipe,
    // even before the momentum has died away)
    const fresh = swept === null && (Math.sign(dx) !== Math.sign(lastDx) || Math.abs(dx) > SWIPE_AGAIN * Math.abs(lastDx));
    lastDx = dx;
    if (fresh) swept = 0;
    if (swept === null) return;
    swept += dx;
    if (Math.abs(swept) >= SWIPE_PX) { const to = swept > 0 ? '1' : '-1'; swept = null; go(to); }
  }, { passive: false });
  grid.addEventListener('click', e => {
    if (e.detail > 1) return;  // (a double-click opens the day once)
    const c = cellAt(e);
    if (c && opens(c)) send(`${data.channel}:day:${c.o}:${deck}${dueNow(c) ? ':due' : ':' + H.by}`);
  });
  // a right-click on a day marks it as important (an exam, say: marks.py) and opens a small editor
  // over it: the icons side by side, its own lit, its name, and × to take the mark away.
  // Enter, or a click anywhere else, keeps it; Esc puts back what was there. Kept by the add-on,
  // and drawn here at once (the forest itself is not drawn again).
  const pin = box.querySelector('.af-cal-pin'), pinName = pin.querySelector('.af-cal-pin-name');
  const pinIcons = pin.querySelector('.af-cal-pin-icons');
  pinIcons.setAttribute('role', 'radiogroup'); pinIcons.setAttribute('aria-label', 'Mark icon');
  // each icon a small button of its own, drawn from its sprite at a scale of 2
  MARK_ORDER.forEach(key => {
    const b = document.createElement('button'), cv = document.createElement('canvas'), rows = MARK_ICONS[key].rows, s = 2;
    b.type = 'button'; b.className = 'af-cal-pin-icon'; b.dataset.icon = key; b.setAttribute('role', 'radio');
    b.title = MARK_ICONS[key].label; b.setAttribute('aria-label', MARK_ICONS[key].label);
    cv.width = rows[0].length * s; cv.height = rows.length * s;
    const g = cv.getContext('2d');
    const markPal = markPalOf(sp, H.look);  // (in the colour the heatmap draws them in)
    rows.forEach((line, y) => { for (let x = 0; x < line.length; x++) if (markPal[line[x]]) { g.fillStyle = markPal[line[x]]; g.fillRect(x * s, y * s, s, s); } });
    b.appendChild(cv);
    b.addEventListener('mousedown', e => e.preventDefault());  // (the name keeps the focus)
    b.addEventListener('click', () => {
      const m = editing && H.marked.get(editing.o);
      if (!m) return;
      m.icon = key;
      showIcon(m);
      draw();
    });
    pinIcons.appendChild(b);
  });
  let editing = null;  // { o, ms, before }: the day being edited, and its mark before (null: none)
  const keepMarks = () => {  // (for a forest redrawn from this data)
    cal.marks = [...H.marked].map(([o, m]) => ({ day: iso(H.today + o * DAY_MS), icon: m.icon, name: m.name }));
  };
  const showIcon = m => {  // (its icon lit among them, and its name's placeholder the icon's)
    for (const b of pinIcons.children) {
      const on = b.dataset.icon === (MARK_ICONS[m.icon] ? m.icon : 'pin');
      b.classList.toggle('af-on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    }
    pinName.placeholder = markOf(m).label;
  };
  // the editor above its day, as its tooltip stands, inside the heatmap's sides (under the day when
  // the window has no room above it); placed again when the heatmap is laid out anew
  const placeOver = (el, c) => {
    const left = grid.offsetLeft + drawn.cv.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + drawn.cv.offsetTop;
    const cx = left + (c.x + TILE / 2) * k, room = drawn.cv.getBoundingClientRect().top + (c.y - 1) * k - el.offsetHeight - TIP_GAP;
    el.style.left = Math.min(box.clientWidth - el.offsetWidth, Math.max(0, cx - el.offsetWidth / 2)) + 'px';
    el.style.top = (room < 0 ? canvasTop + (c.y + TILE + 1) * k + TIP_GAP : canvasTop + (c.y - 1) * k - el.offsetHeight - TIP_GAP) + 'px';
  };
  const placePin = () => {
    const c = editing && drawn.cells.find(x => x.o === editing.o);
    if (c) placeOver(pin, c);
  };
  const closePin = keep => {
    if (!editing) return;
    const { o, ms, before } = editing, m = H.marked.get(o);
    editing = null;
    pin.hidden = true;
    ring(null);
    send(`${data.channel}:typing:0`);
    if (!keep) {  // (back as it was)
      if (before) H.marked.set(o, before); else H.marked.delete(o);
    } else if (m) {
      m.name = pinName.value.trim().replace(/\s+/g, ' ');
      if (!before || before.icon !== m.icon || before.name !== m.name) send(`${data.channel}:mark:${iso(ms)}:${m.icon}:${m.name}`);
    } else if (before) send(`${data.channel}:unmark:${iso(ms)}`);
    keepMarks();
    draw();
  };
  grid.addEventListener('contextmenu', e => {
    const c = cellAt(e);
    // (on the phone there is no add-on to keep the mark; an earlier year's day is not marked from here)
    if (!c || !data.inAnki || pointed !== drawn) return;
    e.preventDefault();
    if (editing) closePin(true);
    const before = H.marked.get(c.o);
    editing = { o: c.o, ms: c.ms, before: before ? Object.assign({}, before) : null };
    if (!before) H.marked.set(c.o, { icon: MARK_ORDER[0], name: '' });
    unpoint();
    draw();
    ring(null);
    const m = H.marked.get(c.o);
    showIcon(m);
    pinName.value = m.name;
    pin.hidden = false;
    placePin();
    send(`${data.channel}:typing:1`);  // (Anki's one-key shortcuts wait while a name is typed)
    pinName.focus();
  });
  pin.querySelector('.af-cal-pin-del').addEventListener('mousedown', e => e.preventDefault());
  pin.querySelector('.af-cal-pin-del').addEventListener('click', () => { if (editing) { H.marked.delete(editing.o); closePin(true); } });
  // (by the keyboard: Enter keeps it from anywhere in it but ×, Esc puts it back; the icons a radio
  // group, one tab stop, ← → moving the choice)
  pin.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.target.classList.contains('af-cal-pin-del')) { e.preventDefault(); closePin(true); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePin(false); }
    else if (e.target.parentNode === pinIcons && /^Arrow/.test(e.key)) {
      e.preventDefault();
      const all = [...pinIcons.children], d = /Left|Up/.test(e.key) ? -1 : 1, to = all[(all.indexOf(e.target) + d + all.length) % all.length];
      to.focus(); to.click();
    }
  });
  // (closed as the focus leaves it, not as it moves from the name to an icon or ×)
  pin.addEventListener('focusout', e => { if (!pin.contains(e.relatedTarget)) closePin(true); });
};
})();

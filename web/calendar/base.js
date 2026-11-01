/* Memory Forest — the study heatmap: its sizes and fixed colours, what changes as heatmaps are drawn
 * (STATE), and days as dates. The heatmap is one IIFE a file, in the order catalog.SCRIPTS loads them,
 * this one first; each adds what the later ones need to AF.cal (its own business: the rest of the page
 * only knows the AF.calendar* names). A file reads AF.cal as it loads, so it can only take from the files before it.
 * One heatmap's own state, while it stands on the page, is the `ui` that AF.calendar hands each part. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal = {};
const { hex } = AF.u;

// low-res pixels: a day's square, the tile drawn in it, a little room above the weeks under the
// months' labels (every mark sits on its own day's tile), and the streak lane below the weeks: the
// brackets, with the trophies and the goal pennant under them
const TILE = 9, TOP = 3, ROWS = 7, BRACKET = 15, GAP = 1;
// what changes as heatmaps are measured and drawn, one for the page: read it here each time (a copy
// goes stale). CELL: a day's cell, its tile and the space after it: set by each heatmap measured or
// drawn, the space GAP but a style's own where it has one (look.gap: Round's 2). BIGGER: Bigger days,
// set with CELL. weekStart: the day the weeks start on (cal.weekStart, Sunday 0). liveClock: a moving
// style's clock, in seconds of motion, one for every heatmap on the page (each loop moves it on by the
// time since any last did, liveClockAt, so a redrawn heatmap carries on where it was)
const STATE = { CELL: TILE + GAP, BIGGER: false, weekStart: 1, liveClock: 0, liveClockAt: 0 };
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
  { G: '#e3b04b', L: '#fff3c4', D: '#a8782a' },
  { G: '#c9ccd1', L: '#f6f7f9', D: '#8b9098' },
  { G: '#c4834a', L: '#ecc196', D: '#8a5528' }
].map(t => ({ frames: [TROPHY], pal: { G: t.G, L: t.L, D: t.D } }));

// the goal ahead: a pennant on the day the current streak would pass the next record, gold when
// it would be your longest, silver your second-longest (P its pole, G the metal, L its shine)
const GOAL = ['PGGGG', 'PGGLG', 'PGGG.', 'PG...', 'P....', 'P....', 'P....', 'P....'];
const GOALS = TROPHIES.map(t => ({ frames: [GOAL], pal: { P: '#8a7a6a', G: t.pal.G, L: t.pal.L } }));
// (right to left: the same pennant flying the other way; its pole on the day's middle mirrored, a
// tile's face being TILE_FACE across)
const GOALS_RTL = GOALS.map(g => ({ frames: [GOAL.map(row => row.split('').reverse().join(''))], pal: g.pal }));
const GOAL_AT = 4, GOAL_AT_RTL = 3;
const GOAL_LINE = 0.75;  // the dotted line from today to the goal: gold, this strong (on a dark page)
// the trophies' and the pennant's metals on a light page, by their own metal: gold, silver, bronze
const METALS_ON_LIGHT = { '#e3b04b': { G: '#b07d1e', L: '#e3b04b', D: '#8f6a1c' }, '#c9ccd1': { G: '#8b9098', L: '#c9ccd1', D: '#6f747c' },
  '#c4834a': { G: '#a8692f', L: '#c4834a', D: '#7a4a22' } };
const PINE_PERCENT = 28;

// the days ahead by their cards due, on a log scale up to the busiest day in the next year (due
// counts fall away steadily, so a quarter of the days each would light only the next weeks).
// The days that sit back, faded this far into the page's colour, light or dark: the days ahead
// (their soil) and the days before the forest's start date (your record, not the forest's time)
const FADE = 0.5;
const TILE_VARIANTS = 4;
const TILE_FACE = TILE - 1;  // a tile's face: all but its last row and column (a plain tile's edge, a scenery's own tile's gap)
const DAY_MS = 86400000;
const MONTHS_SHOWN = 10, MONTHS_MIN = 3, MONTHS_MOST = 24, TODAY_AT = 0.7;  // Timeline: ten months at its own size, more or fewer as its room holds; this month this far along
// the heatmap's size (Heatmap tab: Width and Fill it with; cal.size {width, fill}), 2026-10-20.
// Width: fixed (FIXED_W), following the forest (85% of it, the default), or full (85% of the room
// its place has), never wider than that room, and in its middle; By year always fits its year to it. Fill it with, for
// Timeline: More months (the default): a day DAY_K times its pixels everywhere (about 12 css px, ten
// months 676 px across), as many months as its width holds; or Bigger days: ten months, or the year, stretched over the width (fewer months only where ten would
// be too small to stay crisp)
const DAY_K = 1.25, SHARE = 0.85, FIXED_W = 680;
const sizeOf = cal => (cal && cal.size) || {};
const biggerOf = cal => sizeOf(cal).fill === 'bigger';
// the phone: the calendar is one long timeline swiped along (no buttons to page with), its pixels
// this many css pixels each, running this many months past this one
const SWIPED_K = 1.4, SWIPED_AHEAD = 5, SWIPED_TODAY_AT = 0.75;  // (and opened with today this far across)
const LABEL_GAP = 6, TIP_GAP = 8;  // css px between two month labels, and between a day and its tooltip
const SPOT_DIM = 0.72;  // the days a hover is not about: this far into the page (a key's shade, a month, a streak)
const TIP_WAIT = 150;  // ms the first tooltip waits, the pointer just come onto the heatmap
const SWIPE_PX = 40, SWIPE_QUIET = 250, SWIPE_AGAIN = 1.5;  // a trackpad's sideways swipe: css px to turn a page; ms still that ends it; how much faster than the last step a new swipe starts
const DAYS_ROOM = 28, NOTE_ROOM = 44, SINCE_ROOM = 150;  // css px: room the weekdays need left of the forest; a streak's length under its bracket, and its "Since" date beside it
// low-res px round an animal, a pin or a trophy that a finger's tap still counts for; css px a tap may move
const TOUCH_PAD = 6, TAP_SLOP = 10;
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
// a day as the forest's tooltips write it (AF.u.fmtDate), and without its year ("Oct 17"), in the
// reader's language as the rest; with its weekday ("Saturday, Oct 17, 2026", "Saturday, Oct 17")
const fmt = ms => AF.u.fmtDate(iso(ms));
const dayOnly = ms => AF.i18n.dayIn(ms, { month: 'short', day: 'numeric' });
// (Japanese writes the weekday short, in brackets after the date: "2026年8月7日(金)"; its long form ran
// straight on, "2026年8月7日金曜日")
const weekdayForm = () => (AF.i18n.lang() === 'ja' ? 'short' : 'long');
const withWeekday = (ms, year) => AF.i18n.dayIn(ms, year ? { weekday: weekdayForm(), month: 'short', day: 'numeric', year: 'numeric' } : { weekday: weekdayForm(), month: 'short', day: 'numeric' });
// a day's row: 0 on the day the weeks start (payload.WEEK_START_DAYS: Monday unless the system
// or the setting says otherwise), as the page counts days (Sunday 0)
const dow = ms => (new Date(ms).getUTCDay() - STATE.weekStart + 7) % 7;
const num = n => AF.i18n.num(n);
const yearOf = ms => new Date(ms).getUTCFullYear();
// a stretch of time in seconds, in minutes: "under a minute", "a minute", "48 min", "1 hr 12 min"
// (a time put into a sentence as a number with its unit is; its minutes unformatted, as before)
const lasted = secs => {
  const m = Math.round(secs / 60);
  return m < 1 ? AF.t('heatmap.under_a_minute') : m === 1 ? AF.t('heatmap.a_minute') : m < 60 ? AF.t('heatmap.n_min', { n: m }) : m >= 600 ? AF.t('heatmap.n_hr', { n: Math.round(m / 60) })
    : m % 60 ? AF.t('heatmap.h_hr_m_min', { h: Math.floor(m / 60), m: m % 60 }) : AF.t('heatmap.n_hr', { n: m / 60 });
};

const dpr = () => window.devicePixelRatio || 1;
const sharpK = () => Math.min(1, SHARP / dpr());

Object.assign(Cal, { STATE, TILE, TOP, ROWS, BRACKET, cellOf, FOOT_H, FOOT_GAP, ROW_UNDER, LABEL_END, SHOWN_STREAK, TROPHIES, GOALS, GOALS_RTL, GOAL_AT, GOAL_AT_RTL, GOAL_LINE, METALS_ON_LIGHT, PINE_PERCENT, FADE, TILE_VARIANTS, TILE_FACE, DAY_MS, MONTHS_SHOWN, MONTHS_MIN, MONTHS_MOST, TODAY_AT, DAY_K, SHARE, FIXED_W, sizeOf, biggerOf, SWIPED_K, SWIPED_AHEAD, SWIPED_TODAY_AT, LABEL_GAP, TIP_GAP, SPOT_DIM, TIP_WAIT, SWIPE_PX, SWIPE_QUIET, SWIPE_AGAIN, DAYS_ROOM, NOTE_ROOM, SINCE_ROOM, TOUCH_PAD, TAP_SLOP, P, utc, iso, fmt, dayOnly, withWeekday, dow, num, yearOf, lasted, dpr, sharpK });
})();

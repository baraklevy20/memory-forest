/* Memory Forest — the study calendar, under the forest or on its own: one tile a day in weeks
 * (starting on the day your system, or the setting, says), as the Review Heatmap add-on draws
 * them. A day studied is in the scenery's colour, standing out more from the page the more you
 * reviewed (measured against your own days, so every pace uses all four shades); a missed day is
 * a faint tile (the tooltip says when a break made a pond); the days ahead are tilled soil,
 * stronger the more cards fall due. The milestones are the forest's own: each of its animals
 * (AF.VISITOR_SPRITES) stands on the day it came, in the scenery's own look for them, and today's
 * seedling (AF.pixel.sprite) stands on today once you have studied. The current streak has a
 * bracket under it, with the trophies and the goal ahead in a lane below. A click on a day opens
 * its cards in Anki's browser (actions.browse_calendar_day); a right-click pins it (marks.py).
 *
 * Two views, each fitted to the room there is: Timeline (`timeline`: a year or more with this
 * month most of the way along, paged back and on with ‹ ›; on the phone, the whole history swiped
 * along) and By year (`by_year`: January to December). payload.py sends data.calendar = { view,
 * start, days, due, time, animals, breakDays, browse, marks, forestStart, streakFromStart, weekStart }:
 * the date of the first day counted, the reviews of each day from it to today, the cards due on
 * each day from today on, the day each animal came, the forest's own rule for ponds, whether a
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
const CELL = 11, TILE = 9, TOP = 3, ROWS = 7, BRACKET = 15;  // (TOP: room between the months' labels and the weeks)
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
  trip: { label: 'Trip', rows: ['..R...', '..RR..', 'RRRRRR', 'RRRRRR', '..RR..', '..R...'] },
  birthday: { label: 'Birthday', rows: ['..LL..', '..DD..', '.RRRR.', '.WRWW.', 'RRRRRR', 'RRRRRR'] },
  star: { label: 'Star', rows: ['..RR..', '..RR..', 'RRWRRR', '.RRRR.', '.RRRR.', 'RR..RR'] },
  heart: { label: 'Heart', rows: ['RR..RR', 'RRRRRR', 'RWRRRR', 'RRRRRR', '.RRRR.', '..RR..'] },
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
const GOALS = TROPHIES.slice(0, 2).map(t => ({ frames: [GOAL], pal: { P: '#8a7a6a', G: t.pal.G, L: t.pal.L }, place: t.place }));
const GOAL_LINE = 0.75;  // the dotted line from today to the goal: gold, this strong (on a dark page)
// the trophies' and the pennant's metals on a light page, by their own metal: gold, silver, bronze
const METALS_ON_LIGHT = { '#e3b04b': { G: '#b07d1e', L: '#e3b04b', D: '#8f6a1c' }, '#c9ccd1': { G: '#8b9098', L: '#c9ccd1', D: '#6f747c' },
  '#c4834a': { G: '#a8692f', L: '#c4834a', D: '#7a4a22' } };
const PINE_PERCENT = 28;
// the four shades split your days studied in the last year at these shares (fewest to most):
// the most only your top tenth, so it marks your exceptional days rather than a whole busy season
const SHADE_SPLITS = [0.4, 0.7, 0.9], SHADE_SPAN = 365;
// the days ahead by their cards due, on a log scale up to the busiest day in the next year (due
// counts fall away steadily, so a quarter of the days each would light only the next weeks).
// The days that sit back, faded this far into the page's colour, light or dark: the days ahead
// (their soil) and the days before the forest's start date (your record, not the forest's time)
const FADE = 0.5;
const TILE_VARIANTS = 4;  // each shade's tile comes in this many textures, drawn once
const TILE_FACE = TILE - 1;  // a tile's face: all but its last row and column (a plain tile's edge, a scenery's own tile's gap)
const DAY_MS = 86400000;
const MONTHS_SHOWN = 12, MONTHS_MIN = 3, TODAY_AT = 0.7;  // Timeline: a year (more when wide, fewer when narrow), this month this far along
// the phone: the calendar is one long timeline swiped along (no buttons to page with), its pixels
// this many css pixels each, running this many months past this one
const SWIPED_K = 1.4, SWIPED_AHEAD = 5, SWIPED_TODAY_AT = 0.75;  // (and opened with today this far across)
const LABEL_GAP = 6, TIP_GAP = 8;
const DAYS_ROOM = 28, NOTE_ROOM = 44;  // css px: room the weekdays need left of the forest; a streak's length, about  // css px between two month labels, and between a day and its tooltip
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
  const breakDays = cal.breakDays || 7;
  // the days with no review and nothing due (study_log.load_free_days): a streak passes over
  // them, neither broken nor growing
  const free = new Set();
  for (const [older, newer] of cal.free || []) for (let a = newer; a <= older; a++) free.add(-a);
  const runs = [], pond = new Set();
  let run = null, gap = null;
  for (let o = first; o <= 0; o++) {
    if (n(o)) {
      // a break of breakDays or more is a pond, as forest_data._breaks has it (counted from the
      // forest's start)
      const from = fs !== null ? Math.max(gap, fs) : gap;
      if (gap !== null && o - from >= breakDays) for (let g = from; g < o; g++) pond.add(g);
      gap = null;
      // (a streak runs on over the forest's start date, your real one, as the caption counts it;
      // unless the Decks tab says to count it from the start date too)
      // (its length is in days studied: `days`)
      if (run && !(cal.streakFromStart && o === fs)) { run.to = o; run.days++; } else runs.push(run = { from: o, to: o, days: 1 });
    } else {
      if (!free.has(o)) run = null;
      if (gap === null && o > first) gap = o;
    }
  }
  // a streak lives on through today until today ends, and over the days with nothing due since
  // its last day studied (forest_data._streaks)
  const end = runs[runs.length - 1];
  let current = end || null;
  for (let o = end ? end.to + 1 : 0; current && o < 0; o++) if (!free.has(o)) current = null;
  // the streak a day belongs to (a day with nothing due since the current one's last day, its)
  const runOf = o => runs.find(r => o >= r.from && o <= r.to) || (current && o > current.to && o <= 0 ? current : null);
  // your three longest streaks (of SHOWN_STREAK days or more; the first to reach a length ranks
  // above a later one as long), each with a trophy at its last day: gold, silver, bronze
  const podium = new Map(runs.filter(r => r.days >= SHOWN_STREAK)
    .sort((a, b) => b.days - a.days || a.from - b.from).slice(0, TROPHIES.length).map((r, i) => [r, i]));
  // the goal: the day the current streak, kept up, passes the second-longest of the others (to be
  // second) or, once it has, the longest (to be first); none once it is the longest already
  let goal = null;
  if (current) {
    const others = runs.filter(r => r !== current && r.days >= SHOWN_STREAK).map(r => r.days).sort((a, b) => b - a);
    const len = current.days, need = i => Math.max(SHOWN_STREAK, (others[i] || 0) + 1);
    const rank = others.length && len < need(1) ? 1 : len < need(0) ? 0 : -1;
    // (the days still to study, from today, or from tomorrow once today is studied)
    if (rank >= 0) goal = { o: (current.to === 0 ? 1 : 0) + need(rank) - len - 1, rank, beats: others[rank] || 0 };
  }
  // the shades: where your days studied in the last year split into four (at least 1 apart)
  const splitsOf = vals => {
    vals.sort((a, b) => a - b);
    const splits = [1];
    for (const share of SHADE_SPLITS) splits.push(Math.max(splits[splits.length - 1] + 1, vals.length ? vals[Math.floor(share * (vals.length - 1))] + 1 : splits.length * 50));
    return v => splits.reduce((lv, s, i) => v >= s ? i : lv, 0);  // 0 the fewest .. 3 the most
  };
  const recent = [];
  let busiest = 1;
  for (let o = Math.max(first, 1 - SHADE_SPAN); o <= 0; o++) if (n(o)) recent.push(n(o));
  for (let o = 1; o <= Math.min(SHADE_SPAN, cal.due.length - 1); o++) busiest = Math.max(busiest, n(o));
  const shade = splitsOf(recent), dueShade = v => Math.min(3, Math.floor(4 * Math.log(v) / Math.log(busiest + 1)));
  // the animals, each on the day it came (none before the forest began)
  const animals = new Map();
  for (const a of cal.animals || []) if (-a.ago >= (fs !== null ? fs : first)) animals.set(-a.ago, (animals.get(-a.ago) || []).concat([a]));
  return {
    today, first, n, fs, free, runs, pond, current, runOf, podium, goal, animals,
    // the days you marked, each with its icon and name (an older version's: a bare date)
    marked: new Map((cal.marks || []).map(m => typeof m === 'string' ? { day: m } : m).filter(m => m && m.day)
      .map(m => [(utc(m.day) - today) / DAY_MS, { icon: m.icon || 'pin', name: m.name || '' }])),
    // each day's cards since deleted: still counted in its reviews, but its click can't list them
    gone: new Map((cal.gone || []).map(([ago, count, of]) => [-ago, [count, of || count]])),
    shade, dueShade, dueToday: cal.due[0] || 0,
    ahead: cal.due.length - 1,  // the last day ahead counted
    time: o => (cal.time || [])[o - first] || 0  // (seconds a day's reviews took, as the days are kept)
  };
}

/* the days a view shows, [from, to] as offsets: Timeline's `count` months (a year, more when
 * wide, fewer when narrow), `page` such stretches back (negative) or on; the phone's whole
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
  // Timeline: this month TODAY_AT along (a year: eight months before it and three after), the
  // past being the story
  const t = new Date(H.today), y = t.getUTCFullYear(), m = t.getUTCMonth() - Math.round(count * TODAY_AT) + page * count;
  return { from: (Date.UTC(y, m, 1) - H.today) / DAY_MS, to: (Date.UTC(y, m + count, 1) - H.today) / DAY_MS - 1, apart: true };
}

/* the four shades a day studied takes, fewest reviews to most, with their tiles' edges: built
 * round the scenery's colour (its own `calendar` colour, or its most colourful crown colour,
 * AF.foliage), from pale to deep, so the calendar belongs to the scene */
const PALE = [232, 228, 216], DARK = [16, 16, 16];
// a light page's four shades: their lightness (OKLab L), fewest reviews to most, and the least
// colourfulness they keep (a near-grey key would otherwise give grey tiles)
const LIGHT_STEPS = [0.86, 0.72, 0.58, 0.44], LIGHT_CHROMA = 0.08;
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
function shades(env, dark) {
  // a scenery whose trees are not its colour names its own (`calendar`: Frozen market's ice blue),
  // or two, the fewest reviews' and the most's, for a ramp between them (Aurora's night blue to
  // its green): each shade then takes its own colour along it
  const chroma = c => Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]), own = AF.envOf(env).calendar;
  const keys = Array.isArray(own) ? [0, 1, 2, 3].map(i => readable(blend(hex(own[0]), hex(own[1]), i / 3)))
    : Array(4).fill(readable(own ? hex(own) : AF.foliage(env).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a)));
  // (about evenly far apart; on a dark page the top one only a little towards white, so a busy
  // day never outshines the forest)
  // (on a light page each shade at its own lightness, in even steps from a clear light colour to a
  // deep one, keeping only the key's hue and colourfulness: mixed towards white and black they
  // went grey, and a ramp's dark start and bright end met in the same muddy middle; and the
  // texture stronger: the white between the tiles otherwise outshines them)
  const steps = dark ? [mix(keys[0], DARK, 0.6), mix(keys[1], DARK, 0.42), mix(keys[2], DARK, 0.2), mix(keys[3], PALE, 0.2)]
    : LIGHT_STEPS.map((L, i) => {
      const k = oklab(keys[i]), C = Math.max(LIGHT_CHROMA, Math.hypot(k[1], k[2])), h = Math.atan2(k[2], k[1]);
      return fromOklab(L, C * Math.cos(h), C * Math.sin(h));
    });
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
const EMPTY = 'rgba(128, 128, 128, 0.11)', EMPTY_LIGHT = 'rgba(128, 128, 128, 0.2)';  // (clearer on a light page, so the weeks hold together)
const FREE_MARK = 'rgba(128, 128, 128, 0.5)';  // a day with nothing due: a single pixel, darker grey
function empty(g, x, y, fill = EMPTY) { g.fillStyle = fill; g.fillRect(x, y, TILE, TILE); }
/* a tile's texture: two tones in 2x2 clusters and an edge. A scenery with a look of its own
 * (Starry night's brushstrokes) draws its tiles in it instead (`calendarTile(g, pal, edge, v, size)`:
 * `pal` the shade and its darker tone, `v` which of the TILE_VARIANTS) */
function plainTile(g, pal, edge, v, T) {
  for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
    const e = y === T - 1 || x === T - 1;
    g.fillStyle = rgb(e ? edge : pal[(hashStr(v + ',' + (x >> 1) + ',' + (y >> 1)) & 3) === 0 ? 1 : 0]);
    g.fillRect(x, y, 1, 1);
  }
}
/* a shade's tiles, each of its TILE_VARIANTS textures drawn once, kept for every calendar after */
const tiles = new Map();
function tilesOf(pal, edge, look) {
  const key = (look ? look.name : '') + '|' + pal.concat([edge]).map(c => c.join(',')).join('|');
  if (!tiles.has(key)) {
    const out = [];
    for (let v = 0; v < TILE_VARIANTS; v++) {
      const [cv, g] = layer(TILE, TILE);
      (look ? look.draw : plainTile)(g, pal, edge, v, TILE);
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
  const dark = paper.dark, S = shades(sp, dark), draw = AF.envOf(sp).calendarTile;
  const look = draw && { name: sp.mood.special, draw };  // (a scenery's own tiles, when it draws them)
  // the soil faded into the page, so the days ahead sit behind the days you studied
  const fade = FADE, till = dark ? P.tillDark : P.till, edges = dark ? P.tillDarkEdge : P.tillEdge;
  const soil = lv => till[lv].map(c => mix(c, paper.bg, fade)), soilEdge = lv => mix(edges[lv], paper.bg, fade);
  // (more due stands out more, as more studied does: lighter on a dark page, darker on a light one)
  const dueLv = n => dark ? 3 - H.dueShade(n) : H.dueShade(n);
  const tile = c => {
    const v = hashStr(iso(c.ms)) % TILE_VARIANTS, soilTile = lv => tilesOf(soil(lv), soilEdge(lv), look)[v];
    // today before you study: soil, by the cards it has due, until your first review
    if (c.o === 0 && !c.n && H.dueToday) return soilTile(dueLv(H.dueToday));
    if (!c.n || c.o > H.ahead) return null;
    if (c.o > 0) return soilTile(dueLv(c.n));
    const lv = H.shade(c.n);
    return tilesOf(S.grass[lv], S.edge[lv], look)[v];
  };
  // (the key: the four shades of a day studied; the soil and the empty days say what they are; the
  // hover's ring in today's frame colours, which show on every shade, its inside clear, so the day
  // and its mark keep their colours)
  return { tile, key: [0, 1, 2, 3].map(lv => tilesOf(S.grass[lv], S.edge[lv], look)[0]), ring: rgb(dark ? P.today : P.todayOnLight), glow: 'transparent' };
}
// a seedling of its own day's kind (pine or broadleaf, and its look)
function seedlingOf(sp, ms) {
  const seed = hashStr('calendar|' + iso(ms));
  return spriteOf({ stage: SEEDLING, kind: seed % 100 < PINE_PERCENT ? 1 : 0, size: 0, health: 0, variant: seed % 7, seed, index: -1 }, 7, sp);
}
function frame(g, x, y, T, dark) {  // a light frame round today's tile (dark on a light page)
  g.fillStyle = rgb(dark ? P.today : P.todayOnLight);
  const tx = x - 1, ty = y - 1;
  g.fillRect(tx, ty, T + 1, 1); g.fillRect(tx, ty + T, T + 1, 1); g.fillRect(tx, ty, 1, T + 1); g.fillRect(tx + T, ty, 1, T + 1);
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
/* one view drawn: the canvas, and where everything on it is */
function paint(H, win, sp, paper) {
  const dark = paper.dark, band = TOP;
  // the days in weeks, their first day on top; Timeline starts each month in a column of its own (By
  // year runs its months on in the same weeks)
  const cells = columns(H, win).map(([o, ms, col, row]) => ({ o, ms, n: H.n(o), col, row }));
  const xOf = c => 1 + c.col * CELL, yOf = c => band + c.row * CELL + 1;
  const at = new Map();  // (each day by its column and row, for the pointer)
  for (const c of cells) { c.x = xOf(c); c.y = yOf(c); at.set(c.col * ROWS + c.row, c); }
  const W = xOf(cells[cells.length - 1]) + CELL, Hh = band + ROWS * CELL + BRACKET;
  const [cv, g] = layer(W, Hh);
  // the animals (and the forest's first seedling) on a layer of their own over it, shown while the
  // pointer is on the heatmap (forest.css): the forest's milestones, which the forest shows already
  const [above, ag] = layer(W, Hh);
  const pal = paletteOf(H, sp, paper);
  // the tiles first, each with a texture of its own day's (the same whichever page it is on); a
  // missed day, or one before your history, faint, so the view is never half bare
  for (const c of cells) {
    const t = pal.tile(c);
    // (a day before the forest's start date, studied or not, dimmed)
    g.globalAlpha = H.fs !== null && c.o < H.fs ? 1 - FADE : 1;
    if (t) g.drawImage(t, c.x, c.y);
    else empty(g, c.x, c.y, dark ? EMPTY : EMPTY_LIGHT);
    // (a day with nothing due: one pixel in its middle, the streak's day off)
    if (H.free.has(c.o) && !c.n) { g.fillStyle = FREE_MARK; g.fillRect(c.x + (TILE >> 1), c.y + (TILE >> 1), 1, 1); }
    g.globalAlpha = 1;
  }
  const animals = H.animals;
  const marks = [];  // (where the marks over the weeks stand, for the pointer)
  // today's seedling, once today is studied (an animal that came today stands there instead)
  const sown = cells.find(c => c.o === 0 && c.n && !animals.has(0));
  if (sown) {
    const s = seedlingOf(sp, sown.ms);
    g.drawImage(s, sown.x + Math.floor((TILE - 1 - s.width) / 2) + 1, sown.y + TILE - s.height);
  }
  // the days you marked: each its icon, painted on its tile, centred on what shows of it, the day's shade round it
  // (important enough to sit on the data; its tooltip gives the day's count)
  for (const c of cells) {
    if (!H.marked.has(c.o)) continue;
    const spr = markOf(H.marked.get(c.o)).spr, rows = spr.frames[0];
    const x0 = c.x + Math.floor((TILE_FACE - rows[0].length) / 2), y0 = c.y + Math.floor((TILE_FACE - rows.length) / 2);
    rows.forEach((line, y) => { for (let x = 0; x < line.length; x++) if (spr.pal[line[x]]) { g.fillStyle = spr.pal[line[x]]; g.fillRect(x0 + x, y0 + y, 1, 1); } });
  }
  const today = cells.find(c => c.o === 0);
  if (today) frame(g, today.x, today.y, TILE, dark);
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
    brackets.push({ x0, x1, len, live });
  }
  // the streak lane: a trophy under the last day of each of your longest streaks and the goal
  // pennant under its day, below the brackets, and a dotted gold line from today on to the goal
  // (all the streak's marks together, none cutting through the weeks)
  if (H.goal && H.current && H.current.to >= win.from && H.current.to <= win.to) {
    const a = cells[H.current.to - win.from], gc = H.goal.o <= win.to ? cells[H.goal.o - win.from] : cells[cells.length - 1];
    g.fillStyle = dark ? rgb(P.gold, GOAL_LINE) : rgb(P.goldOnLight);
    for (let x = a.x + TILE; x <= gc.x + 4; x += 2) g.fillRect(x, by, 1, 1);
    if (H.goal.o <= win.to) g.fillRect(gc.x + 4, by - 2, 1, 2);
  }
  const lane = [];
  for (const [run, i] of H.podium) lane.push([run.to, TROPHIES[i]]);
  if (H.goal) lane.push([H.goal.o, GOALS[H.goal.rank]]);
  for (const [o, spr] of lane) {
    if (o < win.from || o > win.to) continue;
    const c = cells[o - win.from], w = spr.frames[0][0].length, x0 = c.x + Math.floor((TILE - w) / 2), y0 = by + 3;
    // (on a light page in their deeper shades: pale gold and silver would fade into it)
    const metal = !dark && METALS_ON_LIGHT[spr.pal.G];
    drawAnimal(g, metal ? Object.assign({}, spr, { pal: Object.assign({}, spr.pal, metal) }) : spr, x0, y0, null, paper.bg);
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
  return { cv, above, W, Hh, cells, at, brackets, band, marks, ring: pal.ring, glow: pal.glow, key: pal.key };
}

// a year's weeks, about as wide as they come: By year's, or Timeline's months apart (its
// months' own weeks, and the odd empty column)
const widthOf = view => (view === 'by_year' ? 53 : 65) * CELL + 1;
const dpr = () => window.devicePixelRatio || 1;
const sharpK = () => Math.min(1, SHARP / dpr());
/* the scale `W` low-res pixels fill `width` css pixels at: whole device pixels, every tile and gap
 * the same; or, too narrow to stay crisp that way, all the width, smoothed (lay). Both views
 * (`fill`) take all the width, the forest's: By year its year, Timeline a year of it exactly
 * (countFor), never a thirteenth month */
const scaleFor = (width, W, fill) => { const k = Math.floor(width / W * dpr()) / dpr(); return k >= sharpK() && !fill ? k : width / W; };
/* the months Timeline shows in a grid this wide: a year at least, filling the width at whole
 * device pixels; fewer, down to MONTHS_MIN, where a year would be too small to stay crisp */
function countFor(view, width) {
  if (view !== 'timeline' || !width) return MONTHS_SHOWN;
  // (a year exactly, never a thirteenth month: stretched to the width, lay; fewer months only where a
  // year would be too small to stay crisp)
  if (width / widthOf(view) >= sharpK()) return MONTHS_SHOWN;
  return Math.max(MONTHS_MIN, Math.floor(MONTHS_SHOWN * width / (widthOf(view) * sharpK())));
}
// the phone's timeline scale for weeks this tall (css px): whole pixels, from SWIPED_K up
AF.calendarScaleFor = height => Math.max(SWIPED_K, Math.floor(height * dpr() / (TOP + ROWS * CELL + BRACKET)) / dpr());
/* the room over the canvas for the months' labels: the first row ROW_UNDER under the row's top,
 * at any zoom (the canvas's own TOP grows with it) */
const monthsRoom = k => Math.round(ROW_UNDER - (TOP + 1) * k);
/* how tall the calendar will be at this width, for the room kept for it until it is drawn */
AF.calendarHeight = function (cal, width) {
  const view = cal.view === 'by_year' ? 'by_year' : 'timeline';
  // (the scale is the width's: the view's exact weeks, as it will lay them out)
  let W = widthOf(view) * countFor(view, width) / MONTHS_SHOWN;
  if (width > 0) {
    weekStart = cal.weekStart == null ? 1 : cal.weekStart;
    const cols = columns(history(cal), windowOf(history(cal), view, 0, null, countFor(view, width)));
    W = 1 + cols[cols.length - 1][2] * CELL + CELL;
  }
  const k = width > 0 ? scaleFor(width, W, true) : 1;
  return Math.round(monthsRoom(k) + (TOP + ROWS * CELL + BRACKET) * k + FOOT_GAP + FOOT_H);  // (rounded as the page rounds the drawn height)
};

AF.calendar = function (root, data, env) {
  const cal = data.calendar;
  if (!cal || !cal.days || !cal.days.length) return;
  // (a calendar drawn here before stops watching the page: this one takes its place)
  if (root.afCalStop) root.afCalStop();
  let box = root.querySelector('.af-cal');
  if (!box) { box = document.createElement('div'); box.className = 'af-cal'; root.append(box); }
  weekStart = cal.weekStart == null ? 1 : cal.weekStart;
  const H = history(cal), view = cal.view === 'by_year' ? 'by_year' : 'timeline', sp = sceneOf(data, env);
  const deck = data.deckId && !data.testForest ? data.deckId : '';
  const swiped = !data.inAnki;  // on the phone: swiped along rather than paged
  let page = 0, year = null;  // Timeline's stretch (0: today's), By year's year
  // what a screen reader says for the picture: the year in a sentence, its streak
  let studiedYear = 0;
  for (let o = Math.max(H.first, -364); o <= 0; o++) if (H.n(o)) studiedYear++;
  const described = `Study heatmap: ${num(studiedYear)} day${studiedYear === 1 ? '' : 's'} studied in the last year`
    + (H.current ? `, current streak ${num(H.current.days)} day${H.current.days === 1 ? '' : 's'}` : '');

  // the weeks, and a footer: the forest's journal (the panel's last line), the way about (‹ ›,
  // with Today before them only once paged away, so they stay where they are as it comes and
  // goes) and the key, the last two shown on hover (forest.css)
  box.innerHTML = '<div class="af-cal-grid"><div class="af-cal-months"></div><div class="af-cal-days"></div><div class="af-cal-hover" hidden></div><div class="af-cal-notes"></div></div>'
    + '<div class="af-cal-foot"><span class="af-cal-journal"></span><span class="af-cal-acts">'
    + '<button type="button" class="af-cal-chev af-cal-today" data-go="0">Today</button>'
    + '<button type="button" class="af-cal-chev" data-go="-1" aria-label="Earlier" title="Earlier">‹</button>'
    + '<button type="button" class="af-cal-chev" data-go="1" aria-label="Later" title="Later">›</button>'
    + '<button type="button" class="af-cal-chev af-cal-now" data-go="0" aria-label="Back to today" title="Back to today">»</button>'
    + '</span><span class="af-cal-key"></span></div>'
    + '<div class="af-tip af-cal-tip" hidden></div>'
    + '<div class="af-cal-pin" hidden><span class="af-cal-pin-icons"></span>'
    + '<input class="af-cal-pin-name" maxlength="40" spellcheck="false" aria-label="Its name">'
    + '<button type="button" class="af-cal-pin-del" aria-label="Remove the mark" title="Remove the mark">\u00d7</button></div>';
  if (swiped) box.classList.add('af-cal-swiped');
  // the forest's journal comes down to the foot of the panel: a forest's caption with the
  // calendar under it would read as the calendar's
  const journal = root.querySelector('.af-caption .af-journal');
  if (journal) box.querySelector('.af-cal-journal').appendChild(journal);
  box.style.minHeight = '';  // (the room kept for it while the forest was building)
  const grid = box.querySelector('.af-cal-grid'), btn = go => box.querySelector(`[data-go="${go}"]`);
  // (on the phone only Today, which brings today back into view)
  if (swiped) { btn(-1).hidden = btn(1).hidden = true; grid.classList.add('af-cal-scroll'); }
  box.querySelectorAll('[data-go]').forEach(b => {
    b.addEventListener('click', () => (swiped ? toToday(true) : go(b.dataset.go)));
    // (a click must leave no focus behind, which would keep them in view after the pointer leaves)
    b.addEventListener('mousedown', e => e.preventDefault());
  });
  // ‹ Today › on the months' row, at its right end, beside the period they change (as calendars
  // have them; on the phone, Today alone stays in the footer)
  const acts = box.querySelector('.af-cal-acts');
  if (!swiped) grid.appendChild(acts);
  const months = box.querySelector('.af-cal-months'), days = box.querySelector('.af-cal-days');
  const notes = box.querySelector('.af-cal-notes'), tip = box.querySelector('.af-cal-tip'), hover = box.querySelector('.af-cal-hover');
  let drawn = null, k = 2, last;  // (last: the day the pointer was last on)
  let paper = pageOf(box);
  // the day under the pointer: lit with the shade that stands out most and ringed in it, lifted a little
  const ring = c => {
    hover.hidden = !c;
    if (!c) return;
    const cv = drawn.cv;
    hover.style.left = (cv.offsetLeft + (c.x - 1) * k) + 'px';
    hover.style.top = (cv.offsetTop + (c.y - 1) * k) + 'px';
    hover.style.width = hover.style.height = (TILE + 1) * k + 'px';
    hover.style.borderColor = drawn.ring; hover.style.background = drawn.glow;
  };
  const unpoint = () => { tip.hidden = true; ring(null); last = undefined; };
  // how far you can page: back to the first day counted, on to the last day ahead counted
  const can = win => ({ back: win.from > H.first, on: win.to < H.ahead });

  function draw() {
    const count = swiped ? MONTHS_SHOWN : countFor(view, grid.clientWidth);
    const win = windowOf(H, swiped ? 'swiped' : view, page, year, count), d = paint(H, win, sp, paper);
    drawn = Object.assign(d, { win, count });
    last = undefined;
    // (a page's slide is for paging alone: go starts it again after this; any other drawing, a day
    // marked say, must not replay it, the new canvas taking the class still on the grid)
    grid.classList.remove('af-cal-from-left', 'af-cal-from-right');
    grid.querySelectorAll('canvas').forEach(c => c.remove());
    drawn.above.className = 'af-cal-above';
    grid.insertBefore(drawn.above, notes);
    drawn.cv.className = 'af-cal-canvas';
    drawn.cv.setAttribute('role', 'img');
    drawn.cv.setAttribute('aria-label', described);
    grid.insertBefore(drawn.cv, notes);
    const may = can(win);
    btn(-1).disabled = !may.back; btn(1).disabled = !may.on;
    // what the tiles mean, read off the tiles themselves
    const swatch = cv => { const c = document.createElement('canvas'); c.width = c.height = TILE; c.getContext('2d').drawImage(cv, 0, 0); c.className = 'af-cal-swatch'; return c; };
    const keyBox = box.querySelector('.af-cal-key'), word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
    keyBox.textContent = '';  // (and each appended alone: Chromium 77, Anki 2.1.45's, has no replaceChildren)
    [word('Less')].concat(drawn.key.map(swatch), [word('More')]).forEach(el => keyBox.appendChild(el));
    // (on today's page already: the pill goes, the jump stays where it is, dimmed; it points the
    // way today lies, » from the past, « from the days ahead)
    box.querySelectorAll('[data-go="0"]').forEach(b => { b.disabled = !swiped && (view === 'by_year' ? win.year === yearOf(H.today) : page === 0); });
    const ahead = view === 'by_year' ? (year || yearOf(H.today)) > yearOf(H.today) : page > 0;
    box.querySelector('.af-cal-now').textContent = ahead ? '«' : '»';
    lay();
  }
  function go(where) {
    const was = drawn.win.from;
    if (where === '0') { page = 0; year = null; }
    else {
      const may = can(drawn.win);
      if (where === '-1' ? !may.back : !may.on) return;  // (a click on a button just disabled)
      if (view === 'by_year') year = (year || yearOf(H.today)) + +where;
      else page += +where;
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
  // fitted to the room there is (scaleFor), smaller than its pixels if need be: no scrolling
  function lay() {
    const d = drawn;
    k = swiped ? Math.round((data.swipedK || SWIPED_K) * dpr()) / dpr() : scaleFor(grid.clientWidth || d.W * 2, d.W, true);
    grid.style.paddingTop = monthsRoom(k) + 'px';
    d.cv.style.width = d.above.style.width = d.W * k + 'px'; d.cv.style.height = d.above.style.height = d.Hh * k + 'px';
    d.above.style.left = d.cv.offsetLeft + 'px'; d.above.style.top = d.cv.offsetTop + 'px';
    box.querySelectorAll('.af-cal-swatch').forEach(sw => { sw.style.width = sw.style.height = TILE * k + 'px'; });  // (the key's tiles as big as the calendar's)
    d.cv.style.imageRendering = d.above.style.imageRendering = k < sharpK() ? 'auto' : '';  // (too small to stay crisp, pixels smooth better than they drop)
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
      const a = acts.getBoundingClientRect(), cap = root.querySelector('.af-caption');
      const words = cap ? [...cap.children].map(el => el.getBoundingClientRect()).filter(r => r.width && r.bottom > a.top - 30) : [];
      const low = words.some(r => r.right > a.left - LABEL_GAP && r.bottom > a.top - 4);
      acts.classList.toggle('af-acts-low', low);
      const edge = acts.offsetLeft - LABEL_GAP;
      for (const s of months.children) s.classList.toggle('af-under', low && s.offsetLeft + s.offsetWidth > edge);
    }
    // each earlier streak's length in the trophies' lane, centred under its bracket, where it clears
    // the trophy at the bracket's end (the current one's is in the caption)
    notes.style.top = d.cv.offsetTop + (d.band + ROWS * CELL + 3 + 7) * k - 5.5 + 'px';
    notes.innerHTML = d.brackets.filter(b => !b.live && (b.x1 - b.x0) * k >= NOTE_ROOM + 2 * (7 * k + 4)).map(b =>
      `<span class="af-cal-note" style="left:${(b.x0 + b.x1) / 2 * k}px">${num(b.len)} days</span>`).join('');
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
    grid.addEventListener('scroll', () => { away(); clip(); }, { passive: true }); away(); clip();
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
    if (e.target !== drawn.cv) return null;
    const [x, y] = AF.u.pointIn(e, drawn.cv), px = x / k, py = y / k;
    const pad = touched && (py < drawn.band || py >= drawn.band + ROWS * CELL) ? TOUCH_PAD : 0;
    const off = m => Math.max(m.x0 - px, 0, px - m.x1 + 1) + Math.max(m.y0 - py, 0, py - m.y1 + 1);
    const mark = drawn.marks.filter(m => px >= m.x0 - pad && px < m.x1 + pad && py >= m.y0 - pad && py < m.y1 + pad)
      .sort((a, b) => off(a) - off(b))[0];
    hit = mark || null;
    if (mark) return mark.c;
    const col = Math.floor(px / CELL), row = Math.floor((py - drawn.band) / CELL);
    return px >= 0 && row >= 0 && row < ROWS ? drawn.at.get(col * ROWS + row) || null : null;
  };
  // which days a click opens: a day with reviews (today too, once studied), a day ahead with cards
  // due, and today before you study, its cards due
  const dueNow = c => c.o === 0 && !c.n && H.dueToday > 0;
  const opens = c => cal.browse && (c.n > 0 || dueNow(c)) && c.o <= H.ahead && c.o >= H.first;
  const cards = (n, what) => `${num(n)} ${what}${n === 1 ? '' : 's'}`;
  // the time a day's reviews took: "in 48 min", "in 1 hr 12 min" ("" where there is none to tell)
  const took = o => {
    const s = H.time(o);
    if (!s) return '';
    const m = Math.round(s / 60);
    return m < 1 ? ' in under a minute' : m < 60 ? ` in ${m} min` : ` in ${Math.floor(m / 60)} hr${m % 60 ? ` ${m % 60} min` : ''}`;
  };
  // a month in a few words, on its label: the days studied, the reviews and about how many a day;
  // and for the days ahead in it, the cards due
  const monthSummary = (y, m) => {
    const from = (Date.UTC(y, m, 1) - H.today) / DAY_MS, to = (Date.UTC(y, m + 1, 1) - H.today) / DAY_MS - 1;
    const lines = [`<b>${MONTH_NAMES[m]} ${y}</b>`];
    const a = Math.max(from, H.first), b = Math.min(to, 0);
    if (from > 0) { /* all ahead */ } else if (b < a) lines.push('No reviews yet');
    else {
      let studied = 0, reviews = 0;
      for (let o = a; o <= b; o++) if (H.n(o)) { studied++; reviews += H.n(o); }
      const span = b - a + 1, now = b === 0 && to > 0 ? ' so far' : '';
      if (!studied) lines.push(`Not studied${now}`);
      else {
        lines.push(`Studied ${num(studied)} of ${num(span)} day${span === 1 ? '' : 's'}${now}`);
        lines.push(`${cards(reviews, 'review')}, about ${num(Math.round(reviews / studied))} a day studied`);
      }
    }
    let due = 0;
    for (let o = Math.max(from, 1); o <= Math.min(to, H.ahead); o++) due += H.n(o);
    if (due) lines.push(`${cards(due, 'card')} due${from > 0 ? '' : ' in the days ahead'}`);
    return lines.join('<br>');
  };
  const pointMonth = lab => {
    ring(null);
    grid.classList.remove('af-click');
    tip.innerHTML = monthSummary(+lab.dataset.y, +lab.dataset.m);
    tip.hidden = false;
    const r = lab.getBoundingClientRect(), b0 = box.getBoundingClientRect();
    const cx = r.left - b0.left + r.width / 2, over = r.top - b0.top - tip.offsetHeight - TIP_GAP;
    tip.style.left = Math.min(box.clientWidth - tip.offsetWidth, Math.max(0, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = over + 'px';  // (above its label, off the month's own weeks)
  };
  // its date, its reviews or cards due, and where it sits in its streak
  const point = e => {
    const lab = e.target && e.target.closest ? e.target.closest('.af-cal-months span') : null;
    if (lab) { if (lab !== last) { last = lab; pointMonth(lab); } return; }
    const c = cellAt(e), on = hit || c;
    if (on === last) return;  // (still on the same day, or mark: nothing changes)
    last = on;
    ring(c);
    grid.classList.toggle('af-click', !!c && opens(c));
    if (!c) { tip.hidden = true; return; }
    const off = c.o <= 0 && !c.n && H.free.has(c.o);  // (a day with nothing due)
    const run = c.o <= 0 && (c.n || off) ? H.runOf(c.o) : null;
    const what = c.o < H.first ? 'No reviews yet'
      : c.o > H.ahead ? 'Too far ahead to show'
      : c.o > 0 ? (c.n ? `${cards(c.n, 'card')} due` : 'Nothing due yet')
      : c.o === 0 && !c.n && H.dueToday ? `${cards(H.dueToday, 'card')} due, not studied yet`
      : c.o === 0 && H.dueToday ? `${cards(c.n, 'review')} so far${took(c.o)}, ${num(H.dueToday)} still due`
      : c.n ? cards(c.n, 'review') + took(c.o) : off ? (c.o === 0 ? 'Nothing due today' : 'Nothing was due')
      : H.pond.has(c.o) ? 'Not studied: a pond in your forest' : c.o === 0 ? 'Not studied yet' : 'Not studied';
    // (where in its streak, in days studied)
    let day = 0;
    for (let o = run ? run.from : 1; o <= c.o; o++) if (H.n(o)) day++;
    const total = run ? run.days : 0;
    const where = run && off ? `Doesn't break your ${num(total)}-day streak` : !run ? ''
      : (run === H.current ? `Day ${num(day)} of your ${num(total)}-day streak` : `Day ${num(day)} of ${num(total)} in a row`)
        // (which of your longest it is: on its trophy, not on each of its days)
        + (hit && hit.trophy >= 0 && H.podium.has(run) ? `<br>Your ${TROPHIES[hit.trophy].place} streak` : '');
    const goal = H.goal && H.goal.o === c.o
      // (with no earlier streak of that rank to pass, the goal is a trophy's first length)
      ? (H.goal.beats ? `<br>Reach this day to ${H.goal.rank ? 'pass' : 'beat'} your ${GOALS[H.goal.rank].place} streak, ${num(H.goal.beats)} days`
        : `<br>Reach this day for a ${num(SHOWN_STREAK)}-day streak`) : '';
    const began = H.fs === c.o ? '<br>Your forest began' : '';
    const came = goal + began + (H.animals.get(c.o) || []).map(a => `<br>${esc(cap(a.label))} came: ${esc(a.why)}`).join('');
    const marked = H.marked.has(c.o) ? `<br>${esc(markLine(H.marked.get(c.o), c.o))}` : '';
    // (in cards, not reviews: a card reviewed twice that day counts once)
    const [lost, of] = c.o <= 0 && c.n ? H.gone.get(c.o) || [0, 0] : [0, 0];
    const gone = !lost ? '' : lost >= of ? `<br>${of === 1 ? 'Its card has' : `All ${num(of)} of its cards have`} since been deleted`
      : `<br>${num(lost)} of its ${num(of)} cards ${lost === 1 ? 'has' : 'have'} since been deleted`;
    tip.innerHTML = `<b>${esc(weekday(c.ms))}, ${esc(fmt(c.ms))}</b><br>${what}${gone}${where ? `<br><i>${where}</i>` : ''}${came}${marked}`;
    tip.hidden = false;
    // below the day, centred on it, so it never covers ‹ Today › and the months over the weeks
    // (above it when there is no room below in the window), kept inside the calendar's sides;
    // placed by the page's own offsets, which a zoomed page leaves right
    const left = grid.offsetLeft + drawn.cv.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + drawn.cv.offsetTop;
    const cx = left + (c.x + TILE / 2) * k, top = canvasTop + (c.y - 1) * k, bottom = canvasTop + (c.y + TILE + 1) * k;
    const above = drawn.cv.getBoundingClientRect().top + (c.y + TILE + 1) * k + TIP_GAP + tip.offsetHeight > window.innerHeight;
    tip.style.left = Math.min(box.clientWidth - tip.offsetWidth, Math.max(0, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (above ? top - tip.offsetHeight - TIP_GAP : bottom + TIP_GAP) + 'px';
  };
  grid.addEventListener('mousemove', point);
  // a finger's tap, taken as it lifts (a phone's web view need not make up a mouse's move for
  // it), unless it was a swipe along the timeline
  let down = null;
  grid.addEventListener('pointerdown', e => {
    touched = e.pointerType !== 'mouse';
    down = touched ? [e.clientX, e.clientY] : null;
  });
  grid.addEventListener('pointerup', e => {
    if (down && Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) < TAP_SLOP) { last = undefined; point(e); }
    down = null;
  });
  grid.addEventListener('pointercancel', () => { down = null; });
  grid.addEventListener('mouseleave', () => { unpoint(); grid.classList.remove('af-click'); });
  grid.addEventListener('click', e => {
    const c = cellAt(e);
    if (c && opens(c)) send(`${data.channel}:day:${c.o}:${deck}${dueNow(c) ? ':due' : ''}`);
  });
  // a right-click on a day marks it as important (an exam, say: marks.py) and opens a small editor
  // over it: the icons side by side, its own lit, its name, and × to take the mark away.
  // Enter, or a click anywhere else, keeps it; Esc puts back what was there. Kept by the add-on,
  // and drawn here at once (the forest itself is not drawn again).
  const pin = box.querySelector('.af-cal-pin'), pinName = pin.querySelector('.af-cal-pin-name');
  const pinIcons = pin.querySelector('.af-cal-pin-icons');
  pinIcons.setAttribute('role', 'radiogroup'); pinIcons.setAttribute('aria-label', 'Its icon');
  // each icon a small button of its own, drawn from its sprite at a scale of 2
  MARK_ORDER.forEach(key => {
    const b = document.createElement('button'), cv = document.createElement('canvas'), rows = MARK_ICONS[key].rows, s = 2;
    b.type = 'button'; b.className = 'af-cal-pin-icon'; b.dataset.icon = key; b.setAttribute('role', 'radio');
    b.title = MARK_ICONS[key].label; b.setAttribute('aria-label', MARK_ICONS[key].label);
    cv.width = rows[0].length * s; cv.height = rows.length * s;
    const g = cv.getContext('2d');
    rows.forEach((line, y) => { for (let x = 0; x < line.length; x++) if (MARK_PAL[line[x]]) { g.fillStyle = MARK_PAL[line[x]]; g.fillRect(x * s, y * s, s, s); } });
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
    }
    pinName.placeholder = markOf(m).label;
  };
  const closePin = keep => {
    if (!editing) return;
    const { o, ms, before } = editing, m = H.marked.get(o);
    editing = null;
    pin.hidden = true;
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
    if (!c || !data.inAnki) return;  // (on the phone there is no add-on to keep the mark)
    e.preventDefault();
    if (editing) closePin(true);
    const before = H.marked.get(c.o);
    editing = { o: c.o, ms: c.ms, before: before ? Object.assign({}, before) : null };
    if (!before) H.marked.set(c.o, { icon: MARK_ORDER[0], name: '' });
    unpoint();
    draw();
    const m = H.marked.get(c.o);
    showIcon(m);
    pinName.value = m.name;
    pin.hidden = false;
    // above the day, as its tooltip stands, inside the heatmap's sides
    const left = grid.offsetLeft + drawn.cv.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + drawn.cv.offsetTop;
    const cx = left + (c.x + TILE / 2) * k;
    pin.style.left = Math.min(box.clientWidth - pin.offsetWidth, Math.max(0, cx - pin.offsetWidth / 2)) + 'px';
    pin.style.top = (canvasTop + (c.y - 1) * k - pin.offsetHeight - TIP_GAP) + 'px';
    send(`${data.channel}:typing:1`);  // (Anki's one-key shortcuts wait while a name is typed)
    pinName.focus();
  });
  pin.querySelector('.af-cal-pin-del').addEventListener('mousedown', e => e.preventDefault());
  pin.querySelector('.af-cal-pin-del').addEventListener('click', () => { if (editing) { H.marked.delete(editing.o); closePin(true); } });
  pinName.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); closePin(true); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePin(false); }
  });
  pinName.addEventListener('blur', () => closePin(true));
};
})();

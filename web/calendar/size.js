/* Memory Forest — how wide and tall the study heatmap is: Timeline's months for a width, the width it
 * asks of each place it can stand (AF.calendarWant and on), and the room kept for it before it is drawn
 * (AF.calendarHeight). */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { STATE, TOP, ROWS, BRACKET, cellOf, FOOT_H, FOOT_GAP, ROW_UNDER, MONTHS_SHOWN, MONTHS_MIN, MONTHS_MOST, DAY_K, SHARE, FIXED_W, sizeOf, biggerOf, SWIPED_K, history, streakRows, weeksPerRow, ROW_GAP, viewOf, yearly, windowOf, columns, weeksWidth, dpr, sharpK } = Cal;

// a year's weeks, about as wide as they come: By year's, or Timeline's months apart (its
// months' own weeks, and the odd empty column)
const widthOf = view => (yearly(view) ? 53 : 54) * STATE.CELL + 1;

// Timeline's months: as many as its width holds at its days' size (More months), or ten, fewer (down
// to MONTHS_MIN) only where ten would be too small to stay crisp (Bigger days)
function countFor(view, width) {
  if (view !== 'timeline' || !width) return MONTHS_SHOWN;
  if (STATE.BIGGER) {
    if (width / widthOf(view) >= sharpK()) return MONTHS_SHOWN;
    return Math.max(MONTHS_MIN, Math.floor(MONTHS_SHOWN * width / (widthOf(view) * sharpK())));
  }
  return Math.max(MONTHS_MIN, Math.min(MONTHS_MOST, Math.round(MONTHS_SHOWN * width / (widthOf(view) * DAY_K))));
}
// the phone's timeline scale for weeks this tall (css px): whole pixels, from SWIPED_K up
AF.calendarScaleFor = height => Math.max(SWIPED_K, Math.floor(height * dpr() / (TOP + ROWS * STATE.CELL + BRACKET)) / dpr());
/* the room over the canvas for the months' labels: the first row ROW_UNDER under the row's top,
 * at any zoom (the canvas's own TOP grows with it) */
const monthsRoom = k => Math.round(ROW_UNDER - (TOP + 1) * k);
/* the width it asks for: "85%" of the room where it stands, "forest" (85% of the forest: of its panel
 * stacked with it, of the Forest width standing apart), or css px */
AF.calendarWant = cal => {
  const w = sizeOf(cal).width;
  return w === 'full' ? '85%' : w === 'fixed' ? FIXED_W : 'forest';
};
// (Full width stacked under the list: the panel takes all the window's room for it, core.js AF.panelWidth)
AF.calendarFull = cal => sizeOf(cal).width === 'full';
/* its width in a place `area` css px across (a row or a column of its own: core.js AF.arrange) */
AF.calendarWidthIn = (cal, forestW, area) => {
  const want = AF.calendarWant(cal);
  return Math.floor(typeof want === 'number' ? Math.min(want, area) : want === '85%' ? SHARE * area : Math.min(area, SHARE * forestW));
};
/* a column of its own beside the list: the most it takes, and its share of the room there (85% for
 * Full width, of all the room beside the list; else all of it, up to its most) */
AF.calendarMost = (cal, forestW) => {
  const want = AF.calendarWant(cal);
  return Math.floor(typeof want === 'number' ? want : want === '85%' ? Infinity : SHARE * forestW);
};
AF.calendarColumnShare = cal => (AF.calendarWant(cal) === '85%' ? SHARE : 1);
/* stacked in the panel with the forest (or alone in it): its width on its box, set before its room is
 * measured (core.js) and again as it is drawn (`view`, the one in view), the panel as wide as it asks
 * (core.js AF.panelWidth), in its middle. Placed apart, its row or column sets its width
 * (core.js AF.arrange). The phone's swiped timeline takes all its width */
AF.calendarFit = (box, cal, view, forestW, inAnki) => {
  const apart = box.parentElement && box.parentElement.classList.contains('af-apart');
  if (apart || !inAnki) {
    box.style.width = box.style.maxWidth = '';
    return;
  }
  const want = AF.calendarWant(cal);
  box.style.width = typeof want === 'number' ? want + 'px' : '85%';
  box.style.maxWidth = '100%';
  // (with no forest above, the settings cog's row over it as wide as it is, in the middle too: the cog
  // on the heatmap's own corner, the controls left of it, not out at the panel's edge)
  const top = box.previousElementSibling;
  if (top && top.classList.contains('af-top')) {
    top.style.width = box.style.width; top.style.maxWidth = box.style.maxWidth;
    top.style.marginLeft = top.style.marginRight = 'auto';
  }
};
/* how tall the footer will be: its row (FOOT_H), unless the forest's journal, which comes down into
 * it beside the shade's choice and the key, is long enough to wrap there. Measured on a stand-in
 * footer in the calendar's box (the real one is built only once the forest is drawn), so the room
 * kept for the calendar holds it and the page keeps still */
function footHeight(root, H) {
  // (the journal: in the caption until the footer is built, then in it; measured again from the footer by e2e/render_heatmap.py)
  // (not with the heatmap first, nor placed apart from the forest: the journal stays in the forest's caption)
  const box = root && root.querySelector('.af-cal'), journal = root && !journalStays(root) && root.querySelector('.af-journal');
  if (!box || !journal || !journal.textContent) return FOOT_H;
  const el = (cls, tag) => { const e = document.createElement(tag || 'span'); e.className = cls; return e; };
  const foot = el('af-cal-foot', 'div');
  foot.style.visibility = 'hidden';
  const j = el('af-cal-journal'); j.appendChild(journal.cloneNode(true)); foot.appendChild(j);
  // (the choice shows with two or more ways to shade: Reviews, Time with study time kept, Pace)
  const ways = shadeWays().filter(w => w[0] === 'reviews' || (w[0] === 'time' ? H.timed : H.paced)).map(w => w[1]);
  if (ways.length >= 2) {
    const by = el('af-cal-by af-cal-shade');
    ways.forEach(w => { const b = document.createElement('button'); b.type = 'button'; b.textContent = w; by.appendChild(b); });
    foot.appendChild(by);
  }
  const key = el('af-cal-key'), ends = keyEnds(H);
  const word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
  [word(ends[0])].concat([0, 1, 2, 3].map(() => el('af-cal-swatch', 'canvas')), [word(ends[1])]).forEach(e => key.appendChild(e));
  foot.appendChild(key);
  box.appendChild(foot);
  const h = foot.offsetHeight;
  foot.remove();
  return Math.max(FOOT_H, h);
}
// the footer's words: what the days are shaded by (each way's key and words), and the ends of the
// key ("Less .. More", "Slow .. Fast" by Pace)
const shadeWays = () => [['reviews', AF.t('heatmap.reviews')], ['time', AF.t('heatmap.time')],
  ['median', AF.t('heatmap.pace')]];
const keyEnds = H => (H.by === 'median' ? [AF.t('heatmap.slow'), AF.t('heatmap.fast')]
  : [AF.t('heatmap.less'), AF.t('heatmap.more')]);
/* whether the forest's journal stays in its caption rather than coming down into the heatmap's
 * footer: with the heatmap first (the caption under the forest is the panel's last line), or the two
 * placed apart round the deck list (core.js AF.arrange) */
const journalStays = root => root.classList.contains('af-cal-first') || root.classList.contains('af-apart');
/* how tall the calendar will be at this width, for the room kept for it until it is drawn (root:
 * the panel, for the journal that will wrap in its footer) */
AF.calendarHeight = function (cal, width, root) {
  STATE.CELL = cellOf(cal); STATE.BIGGER = biggerOf(cal);
  // (the phone draws its swiped timeline whatever the view: web/phone.js's shell holds its panel)
  const phone = !!(root && root.closest && root.closest('.af-phone-shell'));
  const view = phone ? 'timeline' : viewOf(cal.view);
  // (the scale is the width's: the view's exact weeks, as it will lay them out)
  let W = widthOf(view) * countFor(view, width) / MONTHS_SHOWN, foot = FOOT_H, earlier = 0;
  if (width > 0) {
    STATE.weekStart = cal.weekStart == null ? 1 : cal.weekStart;
    const H = cal.afHistory = history(cal);  // (the whole model: kept for the draw that follows, AF.calendar, which takes it once)
    let win = windowOf(H, view, 0, null, countFor(view, width));
    // (Streak view opens on today's frame: its last row, and the rows above it)
    if (view === 'streak') { const rows = streakRows(H, weeksPerRow(width), null); win = rows.pop(); earlier = rows.length; }
    const cols = columns(H, win);
    W = weeksWidth(H, win, cols[cols.length - 1][2]);
    foot = footHeight(root, H);
  }
  const k = width > 0 ? width / W : 1;  // (all the width: By year its year, Timeline its months, countFor)
  const weeks = (TOP + ROWS * STATE.CELL + BRACKET) * k;
  return Math.round(monthsRoom(k) + weeks + earlier * (monthsRoom(k) + weeks + ROW_GAP) + FOOT_GAP + foot);  // (rounded as the page rounds the drawn height)
};

Object.assign(Cal, { countFor, monthsRoom, shadeWays, keyEnds, journalStays });
})();

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
 * Three views, each fitted to the room there is: Timeline (`timeline`: the months round this one,
 * this month most of the way along (ten, or as many as its width holds: countFor), paged back and on with ‹ ›; on the phone, the whole history swiped
 * along), By year (`by_year`: January to December) and Streak (`streak`: all of your streak, its
 * weeks in rows, paged back and on with ‹ ›, streakRows). payload.py sends data.calendar = { view,
 * start, days, due, time, shadeBy, look, animals, ponds, browse, marks, forestStart, streakFromStart, weekStart }:
 * the date of the first day counted, the reviews of each day from it to today, the cards due on
 * each day from today on, the day each animal came, the forest's own ponds, whether a
 * click opens a day, the days you pinned, the forest's start date (if any), whether the streak
 * restarts there, and the weekday the weeks start on. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { esc, send, animates } = AF.u;
const { STATE, cellOf, DAY_MS, biggerOf, num, history, VIEWS, viewOf, pageOf, sceneOf, shadeWays, journalStays } = Cal;

AF.calendar = function (root, data, env) {
  AF.i18n.use(data.i18n);
  const cal = data.calendar;
  if (!cal || !cal.days || !cal.days.length) return;
  // (a calendar drawn here before stops watching the page: this one takes its place)
  if (root.afCalStop) root.afCalStop();
  let box = root.querySelector('.af-cal');
  if (!box) { box = document.createElement('div'); box.className = 'af-cal'; root.append(box); }
  STATE.weekStart = cal.weekStart == null ? 1 : cal.weekStart; STATE.CELL = cellOf(cal); STATE.BIGGER = biggerOf(cal);
  AF.calendarFit(box, cal, null, data.maxWidth, data.inAnki);
  const H = cal.afHistory || history(cal), sp = sceneOf(data, env);
  // a moving tile style moves with the forest's animations (off, or the system asking for less
  // motion: still), and in Anki only (the phone's card is looked at for moments: still); still, it
  // shows its first moment
  const moving = animates(data) && !!data.inAnki;
  H.still = !moving;  // (built already while measuring the room, AF.calendarHeight)
  delete cal.afHistory;
  const treesByDay = new Map((data.trees || []).map(t => [-t.ago, t]));
  for (const [ago, n] of cal.planted || []) if (!treesByDay.has(-ago)) treesByDay.set(-ago, { ago, n });
  // what more than one of the heatmap's parts changes or reads (web/calendar/*.js, each handed `ui`),
  // all of it here; the rest of each part stays its own
  const ui = {
    view: viewOf(cal.view),  // (the switch on the heatmap changes it)
    page: 0, year: null,  // Timeline's stretch, in months from today's (0), By year's year
    pages: [],  // Streak view's pages back from your streak: each one's { end, from }, the latest last (› goes back the way it came)
    ahead: 0,  // (and pages on from it, into the days ahead, as far as cards fall due)
    rows: [],  // (its rows above the one drawn as the heatmap's own weeks, oldest first)
    // (last: the day the pointer was last on; pointed: the year it is on, the one in view or an earlier one shown)
    drawn: null, k: 2, last: undefined, pointed: null,
    wakeLive: null,  // (a moving style's loop, once set up: a redraw starts it again)
    paper: null,  // (the page it sits on: pageOf)
    // the days a hover is about stand out (a shade in the key, a month, a streak): the others
    // dimmed into the page, on a layer over the weeks
    spotCvs: [],  // (a layer on each row of weeks shown: Streak view's earlier rows too)
    // the days selected, as Finder selects files: Cmd-click (Ctrl-click off a Mac) selects or drops one day,
    // Shift-click every day from the last one clicked (`anchor`) to this one, added to those selected
    // before it (`base`). `sel`, a Set of offsets: its days stay lit while nothing else is pointed
    // at, and the forest's trees of those days with them; `selVer` counts its changes. Not kept (2026-10-18)
    sel: null, anchor: null, base: null, selVer: 0,
    selTip: false,  // (the tooltip holds their summary: placed again whenever the heatmap is laid out anew)
    selCvs: [],  // (the days not selected dimmed: a layer a year)
    pasts: [],  // (Streak view's earlier rows, as drawn)
    touched: false,  // (the last press a finger's: pointerdown)
    hit: null,  // (the mark over or under the weeks the pointer is on, if any: cellAt)
    editing: null  // { o, ms, before }: the day being edited, and its mark before (null: none)
  };
  root.afCalView = ui.view;  // (the one in view, for its row's width: core.js AF.arrange)
  const deck = data.deckId && !data.testForest ? data.deckId : '';
  const swiped = !data.inAnki;  // on the phone: swiped along rather than paged
  // what a screen reader says for the picture: the year in a sentence, its streak
  // (the stretch in view, paged to or not: "Study heatmap, Feb 2025 to Jan 2026: 203 days studied")
  const described = win => {
    let studied = 0;
    for (let o = Math.max(H.first, win.from); o <= Math.min(0, win.to); o++) if (H.n(o)) studied++;
    const month = o => AF.i18n.dayIn(H.today + o * DAY_MS, { month: 'short', year: 'numeric' });
    const v = { from: month(win.from), to: month(win.to) };
    return H.current && win.to >= 0 && win.from <= 0
      ? AF.tn('heatmap.study_heatmap_from_to_to_n',
        studied, Object.assign(v, { days: num(H.current.days) }))
      : AF.tn('heatmap.study_heatmap_from_to_to_n_2', studied, v);
  };

  // the weeks, and a footer: the forest's journal (the panel's last line), the way about (‹ › and
  // », back to today, after them; on the phone a Today pill alone, once scrolled away) and the key,
  // the last two shown on hover (forest.css)
  // (the words escaped, as any text put into the page)
  const [byReviews, byTime, byPace] = shadeWays().map(w => esc(w[1]));
  const titled = text => `aria-label="${esc(text)}" title="${esc(text)}"`;
  // right to left (paint), the earlier days are to the right: ‹ › point the way they go, kept left
  // to right so the line's direction doesn't mirror them back (AF.i18n.arrow)
  const rtl = AF.i18n.rtl(), [EARLIER, LATER] = rtl ? ['›', '‹'] : ['‹', '›'], chevDir = rtl ? ' dir="ltr"' : '';
  box.innerHTML = '<div class="af-cal-grid"><div class="af-cal-months"></div><div class="af-cal-days"></div><div class="af-cal-hover" hidden></div><div class="af-cal-notes"></div><div class="af-cal-past"></div></div>'
    + '<div class="af-cal-foot"><span class="af-cal-journal"></span><span class="af-cal-acts">'
    + (swiped ? `<button type="button" class="af-cal-chev af-cal-today" data-go="0">${esc(AF.t('heatmap.today'))}</button>`
      : `<button type="button" class="af-cal-chev" data-go="-1"${chevDir} ${titled(AF.t('heatmap.earlier'))}>${EARLIER}</button>`
      + `<button type="button" class="af-cal-chev" data-go="1"${chevDir} ${titled(AF.t('heatmap.later'))}>${LATER}</button>`
      + `<button type="button" class="af-cal-chev af-cal-now" data-go="0"${chevDir} ${titled(AF.t('heatmap.back_to_today'))}>${rtl ? '«' : '»'}</button>`)
    + `</span><span class="af-cal-by af-cal-view" role="radiogroup" aria-label="${esc(AF.t('heatmap.view'))}">`
    + `<button type="button" role="radio" data-view="timeline" title="${esc(AF.t('heatmap.the_months_round_this_one_most'))}">${esc(AF.t('heatmap.timeline'))}</button>`
    + `<button type="button" role="radio" data-view="by_year" title="${esc(AF.t('heatmap.january_to_december'))}">${esc(AF.t('heatmap.by_year'))}</button>`
    + `<button type="button" role="radio" data-view="streak" title="${esc(AF.t('heatmap.your_streak_every_year_of_it'))}">${esc(AF.t('heatmap.streak'))}</button>`
    + `</span><span class="af-cal-by af-cal-shade" role="radiogroup" aria-label="${esc(AF.t('heatmap.shade_the_days_by'))}">`
    + `<button type="button" role="radio" data-by="reviews" title="${esc(AF.t('heatmap.shade_each_day_by_how_many'))}">${byReviews}</button>`
    + `<button type="button" role="radio" data-by="time" title="${esc(AF.t('heatmap.shade_each_day_by_how_long'))}">${byTime}</button>`
    + `<button type="button" role="radio" data-by="median" title="${esc(AF.t('heatmap.shade_each_day_by_its_median'))}">${byPace}</button>`
    + '</span><span class="af-cal-key"></span></div>'
    + '<div class="af-tip af-cal-tip" hidden></div>'
    + '<div class="af-cal-pin" hidden><span class="af-cal-pin-icons"></span>'
    + `<input class="af-cal-pin-name" maxlength="40" spellcheck="false" aria-label="${esc(AF.t('heatmap.mark_name'))}">`
    + `<button type="button" class="af-cal-pin-del" ${titled(AF.t('heatmap.remove_the_mark'))}>\u00d7</button></div>`;
  if (swiped) box.classList.add('af-cal-swiped');
  // the forest's journal comes down to the foot of the panel: a forest's caption with the
  // calendar under it would read as the calendar's
  // (unless it stays in the caption: journalStays)
  const stays = journalStays(root);
  const journal = stays ? null : root.querySelector('.af-caption .af-journal');
  if (journal) box.querySelector('.af-cal-journal').appendChild(journal);
  box.style.minHeight = '';  // (the room kept for it while the forest was building)
  const grid = box.querySelector('.af-cal-grid'), btn = go => box.querySelector(`[data-go="${go}"]`);
  if (swiped) grid.classList.add('af-cal-scroll');
  box.querySelectorAll('[data-go]').forEach(b => {
    b.addEventListener('click', () => (swiped ? ui.toToday(true) : ui.go(b.dataset.go)));
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
  // Timeline | By year | Streak, just left of it: the view as the Heatmap tab sets it, changed here for good
  // (as the shade is; not on the phone, which swipes along its own)
  const viewBox = box.querySelector('.af-cal-view');
  // (← → move a choice the way it looks: right to left, its next one is to the left)
  const arrowStep = key => ({ ArrowLeft: rtl ? 1 : -1, ArrowUp: -1, ArrowRight: rtl ? -1 : 1, ArrowDown: 1 })[key];
  viewBox.hidden = swiped;
  if (!swiped) acts.insertBefore(viewBox, acts.firstChild);
  viewBox.querySelectorAll('button').forEach(b => {
    b.addEventListener('mousedown', e => e.preventDefault());
    b.addEventListener('keydown', e => {
      const step = arrowStep(e.key);
      if (!step) return;
      e.preventDefault();
      const to = viewBox.querySelector(`[data-view="${VIEWS[(VIEWS.indexOf(b.dataset.view) + step + VIEWS.length) % VIEWS.length]}"]`);
      to.focus(); to.click();
    });
    b.addEventListener('click', () => {
      if (ui.view === b.dataset.view) return;
      ui.view = b.dataset.view; ui.page = 0; ui.year = null; ui.pages = []; ui.ahead = 0;
      send(`${data.channel}:view:${ui.view}`);
      ui.unpoint();
      ui.draw();
    });
  });
  // the caption's streak, clicked: Streak view, as the switch would (`ask`: whether it would do
  // anything), on your streak; the last weeks kept where they were on screen, the rows above them
  root.afCalStreak = ask => {
    if (swiped || (ui.view === 'streak' && !ui.pages.length && !ui.ahead)) return false;
    if (ask) return true;
    const was = ui.drawn.cv.getBoundingClientRect().top;
    if (ui.view === 'streak') ui.go('0'); else viewBox.querySelector('[data-view="streak"]').click();
    const moved = ui.drawn.cv.getBoundingClientRect().top - was;
    if (moved) window.scrollBy(0, moved);
    return true;
  };
  byBox.querySelectorAll('button').forEach(b => {
    b.addEventListener('mousedown', e => e.preventDefault());  // (no focus left behind: as the arrows)
    b.addEventListener('keydown', e => {  // (←/→ move the choice, as radio buttons do)
      const step = arrowStep(e.key);
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
      ui.unpoint();
      ui.draw();
    });
  });
  const months = box.querySelector('.af-cal-months'), days = box.querySelector('.af-cal-days');
  const notes = box.querySelector('.af-cal-notes'), tip = box.querySelector('.af-cal-tip'), hover = box.querySelector('.af-cal-hover');
  ui.paper = pageOf(box);
  box.classList.toggle('af-cal-on-light', !ui.paper.dark);  // (a choice's chosen half: a white pill on a light page)

  // what never changes once made, for the parts to take as they start; then each part, in this order
  Object.assign(ui, { root, data, cal, box, H, sp, moving, treesByDay, deck, swiped, described, rtl, stays, grid, btn, acts, byBox, viewBox, arrowStep, months, days, notes, tip, hover });
  Cal.highlighting(ui);
  Cal.drawing(ui);
  Cal.tooltips(ui);
  Cal.input(ui);
  Cal.markEditor(ui);
};
})();

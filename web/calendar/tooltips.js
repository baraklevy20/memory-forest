/* Memory Forest — what the study heatmap says: a day's tooltip, a month's, a shade's, a streak's, and
 * the pointer finding what it is on (cellAt, point, tell). */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { esc, cap } = AF.u;
const { STATE, TILE, ROWS, BRACKET, SHOWN_STREAK, markName, markLine, DAY_MS, TIP_GAP, TOUCH_PAD, fmt, dayOnly, withWeekday, num, yearOf, lasted } = Cal;

// which of your longest streaks it is, by its rank (0 the longest), each its own sentence
const placeName = rank => [AF.t('heatmap.your_longest_streak'), AF.t('heatmap.your_second_longest_streak'), AF.t('heatmap.your_third_longest_streak')][rank];
// the goal's day: pass the next of them (beat the longest), or reach the first trophy's length; `daily`:
// with days off a week allowed, if you take none of them until then
const goalLine = (goal, daily) => {
  const n = goal.beats;
  if (!n) {
    return daily ? AF.tn('heatmap.reach_a_n_day_streak_on', SHOWN_STREAK)
      : AF.tn('heatmap.reach_a_n_day_streak_on_2', SHOWN_STREAK);
  }
  if (daily) {
    return [AF.tn('heatmap.beat_your_longest_streak_n_days', n),
      AF.tn('heatmap.pass_your_second_longest_streak_n', n),
      AF.tn('heatmap.pass_your_third_longest_streak_n', n)][goal.rank];
  }
  return [AF.tn('heatmap.beat_your_longest_streak_n_days_2', n),
    AF.tn('heatmap.pass_your_second_longest_streak_n_2', n),
    AF.tn('heatmap.pass_your_third_longest_streak_n_2', n)][goal.rank];
};
const placeLine = (rank, n) => [AF.tn('heatmap.your_longest_streak_n_days', n),
  AF.tn('heatmap.your_second_longest_streak_n_days', n),
  AF.tn('heatmap.your_third_longest_streak_n_days', n)][rank];

Cal.tooltips = ui => {
  const { root, data, cal, box, H, treesByDay, swiped, grid, tip } = ui;
  // a number of reviews, and the time they took where the review log kept it: "103 reviews in 19 min"
  // a stretch's reviews and time together, the time first where the days are shaded by it, as a day's
  // own tooltip has them: "8 hr 24 min, 3,432 reviews"
  const totals = (n, secs) => (H.by === 'time' && secs ? cap(AF.tn('heatmap.time_n_reviews', n, { time: lasted(secs) })) : reviewsIn(n, secs));
  const reviewsIn = (n, secs) => (secs ? AF.tn('heatmap.n_reviews_in_time', n, { time: lasted(secs) })
    : AF.tn('heatmap.n_reviews', n));
  const due = n => AF.tn('heatmap.n_cards_due', n);
  // about how many a day: "About 34 reviews and 6 min a day", "studied" at its end where some days were missed
  const perDay = (reviews, studied, secs, missed) => {
    const n = Math.round(reviews / studied), v = { time: secs ? lasted(secs / studied) : '' };
    if (missed) {
      return secs ? AF.tn('heatmap.about_n_reviews_and_time_a', n, v)
        : AF.tn('heatmap.about_n_reviews_a_day_studied', n);
    }
    return secs ? AF.tn('heatmap.about_n_reviews_and_time_a_2', n, v) : AF.tn('heatmap.about_n_reviews_a_day', n);
  };
  // the days studied of so many: "Studied 26 of 31 days (84%)", or since a day, or so far
  const studiedOf = (studied, span, since, sofar) => {
    const v = { studied: num(studied), pct: Math.min(99, Math.max(1, Math.round(100 * studied / span))), date: since };  // (never 100% with a day missed, nor 0% with one studied)
    return since ? AF.tn('heatmap.studied_studied_of_n_days_since', span, v)
      : sofar ? AF.tn('heatmap.studied_studied_of_n_days_so', span, v)
        : AF.tn('heatmap.studied_studied_of_n_days_pct', span, v);
  };
  // the days studied from one day to another, and their share: "Studied 26 of 31 days (84%)", the
  // reviews and about how many a day; only the days since your first review, up to today
  const studiedLines = (from, to) => {
    // (today counts once studied: until then it isn't over, nor missed)
    const end = H.n(0) ? 0 : -1, a = Math.max(from, H.first), b = Math.min(to, end);
    if (b < a) return [a === 0 ? AF.t('heatmap.not_studied_yet') : H.hid !== null && b < H.hid ? AF.t('heatmap.before_your_forest_began') : AF.t('heatmap.before_your_first_review')];
    let studied = 0, reviews = 0, secs = 0;
    for (let o = a; o <= b; o++) if (H.n(o)) { studied++; reviews += H.n(o); secs += H.time(o) || 0; }
    // (a stretch your history starts inside counts from your first review: "since Mar 1")
    const since = a > from ? dayOnly(H.today + a * DAY_MS) : '';
    const span = b - a + 1, sofar = !since && b === end && to > end;
    if (!studied) return [since ? AF.t('heatmap.not_studied_since_date', { date: since }) : sofar ? AF.t('heatmap.not_studied_so_far') : AF.t('heatmap.not_studied')];
    // (short enough not to wrap: the totals on one line, the day's average on the next, "studied"
    // only where some days were missed; the time where the review log kept it)
    return [studied === span ? (since ? AF.t('heatmap.studied_every_day_since_date', { date: since }) : sofar ? AF.t('heatmap.studied_every_day_so_far') : AF.t('heatmap.studied_every_day'))
      : studiedOf(studied, span, since, sofar),
    totals(reviews, secs), perDay(reviews, studied, secs, studied < span)];
  };

  // the day under the pointer (or an animal's, a pin's or a trophy's above or below the weeks):
  // its square's column and row, the gaps between tiles counted with the tile before them
  // (a finger's tap counts a little way round one, the nearest, as it hides what it touches;
  // never on the weeks themselves, where the tap is a day's)
  // (where on the canvas, AF.u.pointIn: right on a page the app zooms and in the phone's sideways
  // view; on anything but the canvas, nothing)
  const cellAt = e => {
    ui.hit = null;
    // (the year in view, or an earlier one shown under it)
    ui.pointed = e.target === ui.drawn.cv ? ui.drawn : ui.pasts.find(d => d.cv === e.target) || null;
    if (!ui.pointed) return null;
    const [x, y] = AF.u.pointIn(e, ui.pointed.cv), px = x / ui.k, py = y / ui.k;
    const pad = ui.touched && (py < ui.pointed.band || py >= ui.pointed.band + ROWS * STATE.CELL) ? TOUCH_PAD : 0;
    const off = m => Math.max(m.x0 - px, 0, px - m.x1 + 1) + Math.max(m.y0 - py, 0, py - m.y1 + 1);
    const mark = ui.pointed.marks.filter(m => px >= m.x0 - pad && px < m.x1 + pad && py >= m.y0 - pad && py < m.y1 + pad)
      .sort((a, b) => off(a) - off(b))[0];
    ui.hit = mark || null;
    if (mark) return mark.c;
    // (or a streak's bracket, or the lane under it: the streak itself)
    const by = ui.pointed.band + ROWS * STATE.CELL + 3, br = py >= by - 3 && py < by + 12 ? ui.pointed.brackets.find(b => px >= b.x0 - 1 && px <= b.x1 + 1) : null;
    if (br) { ui.hit = br; return null; }
    // (a drafted shape: the pixel's own day, as it drew it, not the square of the grid)
    const pane = ui.pointed.pane && px >= 0 && py >= 0 && px < ui.pointed.W && py < ui.pointed.Hh ? ui.pointed.pane[Math.floor(py) * ui.pointed.W + Math.floor(px)] : -1;
    if (pane >= 0) return ui.pointed.cells[pane];
    const col = Math.floor(px / STATE.CELL), row = Math.floor((py - ui.pointed.band) / STATE.CELL);
    return px >= 0 && row >= 0 && row < ROWS ? ui.pointed.at.get(col * ROWS + row) || null : null;
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
    const year = m === 0 && from <= 0 ? [`<b>${AF.i18n.dayIn(Date.UTC(y, 0, 15), { year: 'numeric' })}</b>`, ...studiedLines(from, at(y + 1, 0) - 1), ''] : [];
    const lines = [...year, `<b>${AF.i18n.dayIn(Date.UTC(y, m, 15), { month: 'long', year: 'numeric' })}</b>`, ...(from > 0 ? [] : studiedLines(from, to))];
    return lines.concat(notesOf(from, to, 'month')).join('<br>');
  };
  // a stretch's marked days, by date and name, as their tooltips name them, and the cards due in
  // its days ahead (`later`: how a stretch begun before today says so, 'month' "later this month",
  // else "after today")
  const notesOf = (from, to, later, has = () => true) => {
    const lines = [];
    const marked = [...H.marked].filter(([o]) => o >= from && o <= to && has(o)).sort((p, q) => p[0] - q[0]);
    for (const [o, mk] of marked.slice(0, 4)) lines.push(AF.t('heatmap.date_name', { date: dayOnly(H.today + o * DAY_MS), name: markName(mk) }));
    if (marked.length > 4) lines.push(`<i>${AF.tn('heatmap.and_n_more_marked', marked.length - 4)}</i>`);
    let n = 0;
    for (let o = Math.max(from, 1); o <= Math.min(to, H.ahead); o++) if (has(o)) n += H.n(o);
    if (n) {
      lines.push(from > 0 ? due(n) : later === 'month' ? AF.tn('heatmap.n_cards_due_later_this_month', n)
        : AF.tn('heatmap.n_cards_due_after_today', n));
    } else if (from > H.ahead) lines.push(AF.t('heatmap.too_far_ahead_to_count'));
    else if (from > 0) lines.push(AF.t('heatmap.nothing_due_yet'));
    return lines;
  };

  const pointMonth = lab => {
    ui.pointTree(null);
    ui.ring(null);
    // (its days stand out while it tells them)
    ui.spot(c => { const d = new Date(c.ms); return d.getUTCFullYear() === +lab.dataset.y && d.getUTCMonth() === +lab.dataset.m; });
    grid.classList.remove('af-click');
    tip.innerHTML = monthSummary(+lab.dataset.y, +lab.dataset.m);
    ui.reveal();
    const r = lab.getBoundingClientRect(), b0 = box.getBoundingClientRect();
    const cx = r.left - b0.left + r.width / 2, over = r.top - b0.top - tip.offsetHeight - TIP_GAP;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    // (above its label, off the month's own weeks; under it when the window has no room above)
    tip.style.top = (r.top - tip.offsetHeight - TIP_GAP < 0 ? r.bottom - b0.top + TIP_GAP : over) + 'px';
  };
  // a shade in the key, pointed at, tells what it stands for, in a few words: "65–109 reviews",
  // "8–12 min", "Under 3 min", "154+ reviews"
  const shadeLine = lv => {
    const s = H.splits();
    if (H.by === 'median') {
      lv = 3 - lv;
      // ("Under 3.2 s per answer", "3.2–4.1 s per answer", "4.1+ s per answer": as the other keys' lines)
      const t = v => AF.i18n.dec(v);
      return lv === 0 ? AF.t('heatmap.under_s_s_per_answer', { s: t(s[1]) }) : lv === 3 ? AF.t('heatmap.s_s_per_answer', { s: t(s[3]) })
        : AF.t('heatmap.from_to_s_per_answer', { from: t(s[lv]), to: t(s[lv + 1]) });
    }
    if (H.by === 'time') {
      // (in minutes as lasted() writes them: "Under 8 min", "20+ min", "8–12 min", "a minute")
      const mins = secs => Math.round(secs / 60), inMin = m => m >= 1 && m < 60;
      if (lv === 0) return AF.t('heatmap.under_time', { time: lasted(s[1]) });
      if (lv === 3) return inMin(mins(s[3])) && mins(s[3]) > 1 ? AF.t('heatmap.n_min_2', { n: mins(s[3]) }) : AF.t('heatmap.time_2', { time: lasted(s[3]) });
      const lo = lasted(s[lv]), hi = lasted(s[lv + 1] - 60);
      if (lo === hi) return lo;
      // ("8–12 min": the first minutes' unit left to the second)
      const a = mins(s[lv]), b = mins(s[lv + 1] - 60);
      if (inMin(a) && inMin(b) && b > 1) return AF.t('heatmap.from_to_min', { from: a, to: b });
      return AF.t('heatmap.from_to', { from: a === 1 ? '1' : lo, to: hi });
    }
    // ("65–109 reviews", "Under 65 reviews", "154+ reviews")
    if (lv === 0) return AF.tn('heatmap.under_n_reviews', s[1]);
    if (lv === 3) return AF.tn('heatmap.n_reviews_2', s[3]);
    if (s[lv] === s[lv + 1] - 1) return AF.tn('heatmap.n_reviews', s[lv]);
    return AF.tn('heatmap.from_n_reviews', s[lv + 1] - 1, { from: num(s[lv]) });
  };
  const keyEl = box.querySelector('.af-cal-key');
  keyEl.addEventListener('mouseover', e => {
    const sw = e.target.classList && e.target.classList.contains('af-cal-swatch') ? e.target : null;
    const lv = sw ? [...keyEl.querySelectorAll('.af-cal-swatch')].indexOf(sw) : -1;
    if (lv < 0 || sw === ui.last) return;
    ui.last = sw; ui.selTip = false;
    ui.pointTree(null);
    ui.ring(null);
    tip.textContent = shadeLine(lv);
    tip.hidden = false;
    const r = sw.getBoundingClientRect(), b0 = box.getBoundingClientRect();
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, r.left - b0.left + r.width / 2 - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (r.top - b0.top - tip.offsetHeight - TIP_GAP) + 'px';  // (above the key, at the heatmap's foot)
    ui.spot(c => c.o <= 0 && c.n > 0 && !H.timeless(c.o) && H.shade(c.o) === lv, lv);  // (and its days stand out)
  });
  keyEl.addEventListener('mouseleave', ui.unpoint);
  // a streak's bracket, pointed at: its first and last days, and its days lit
  const streak = b => {
    const r = b.run, day = o => esc(fmt(H.today + o * DAY_MS)), year = o => yearOf(H.today + o * DAY_MS);
    // ("Jun 1 to Dec 19, 2025": a year said once)
    const first = !b.live && year(r.from) === year(r.to) ? esc(dayOnly(H.today + r.from * DAY_MS)) : day(r.from);
    const span = b.live ? AF.t('heatmap.from_to_today', { from: first }) : AF.t('heatmap.from_to_to', { from: first, to: day(r.to) });
    tip.innerHTML = `<b>${span}</b><br>${b.live ? AF.tn('heatmap.your_n_day_streak', r.days) : AF.tn('heatmap.n_days_in_a_row', r.days)}`;
    ui.selTip = false;
    tip.hidden = false;
    const on = ui.pointed || ui.drawn, left = grid.offsetLeft + on.cv.offsetLeft - grid.scrollLeft, cx = left + (b.x0 + b.x1) / 2 * ui.k;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = grid.offsetTop + on.cv.offsetTop + (on.band + ROWS * STATE.CELL + BRACKET) * ui.k + TIP_GAP + 'px';  // (under the lane)
    ui.spot(c => c.o >= r.from && c.o <= r.to);
  };
  // its date, its reviews or cards due, and where it sits in its streak
  const point = e => {
    if (ui.editing) return;  // (no tooltips while a mark is named: its day keeps the ring)
    // (the footer: its key and switches answer for themselves)
    if (e.target && e.target.closest && e.target.closest('.af-cal-foot')) return;
    // (a month's label: the last row's, or in Streak view an earlier row's, which tells its month too,
    // its days standing out in its own row)
    const lab = e.target && e.target.closest ? e.target.closest('.af-cal-months span, .af-cal-past-head span') : null;
    if (lab) ui.pointed = ui.pasts.find(d => d.head === lab.parentElement) || null;
    if (lab) { if (lab !== ui.last) { ui.last = lab; pointMonth(lab); } return; }
    const c = cellAt(e), on = ui.hit || c;
    if (on === ui.last) return;  // (still on the same day, or mark: nothing changes)
    ui.last = on;
    tell(c);
    // (Shift held: the days a click would select stand out, from the day it would stretch from to
    // this one, with those selected before it, so the stretch is seen before it is chosen)
    if (c && e.shiftKey && ui.anchor !== null && !swiped) {
      const a = Math.min(ui.anchor, c.o), b = Math.max(ui.anchor, c.o);
      ui.spot(x => (!!ui.base && ui.base.has(x.o)) || (x.o >= a && x.o <= b));
    }
  };
  // a day's tooltip and ring, for the pointer's day or the keyboard's
  const tell = c => {
    // (a day selected answers for all of them: their summary, a click opening them all)
    // (the day itself keeps its ring: the keyboard's day must show where it is, Shift+Enter selecting from it)
    if (c && ui.sel && ui.inSel(c)) {
      ui.pointTree(null); ui.ring(c);
      grid.classList.toggle('af-click', ui.selOpens());
      ui.showSel(true, c);
      return;
    }
    ui.pointTree(c);
    ui.ring(c);
    grid.classList.toggle('af-click', !!c && (ui.sel ? ui.inSel(c) && ui.selOpens() : opens(c)));
    if (!c) { tip.hidden = true; if (ui.hit && ui.hit.run) streak(ui.hit); else if (ui.sel) ui.showSel(); return; }
    const off = c.o <= 0 && !c.n && H.free.has(c.o);  // (a day with nothing due)
    const run = c.o <= 0 && (c.n || off) ? H.runOf(c.o) : null;
    const t = H.time(c.o), still = { due: num(H.dueToday) };
    const what = c.o < H.first ? (H.hid !== null && c.o < H.hid ? AF.t('heatmap.before_your_forest_began') : AF.t('heatmap.before_your_first_review'))
      : c.o > H.ahead ? AF.t('heatmap.too_far_ahead_to_count')
      : c.o > 0 ? (c.n ? due(c.n) : AF.t('heatmap.nothing_due_yet'))
      : c.o === 0 && !c.n && H.dueToday ? AF.tn('heatmap.not_studied_yet_n_cards_due', H.dueToday)
      : c.n && H.by === 'median' && H.answerTime(c.o) !== null ? (c.o === 0 && H.dueToday
        ? AF.tn('heatmap.median_s_s_per_answer_n', c.n, Object.assign({ s: AF.i18n.dec(H.answerTime(c.o)) }, still))
        : AF.tn('heatmap.median_s_s_per_answer_n_2', c.n, { s: AF.i18n.dec(H.answerTime(c.o)) }))
      : c.o === 0 && H.dueToday ? (H.by === 'time' && t ? cap(AF.tn('heatmap.time_so_far_n_reviews_due', c.n, Object.assign({ time: lasted(t) }, still)))
        : t ? AF.tn('heatmap.n_reviews_so_far_in_time', c.n, Object.assign({ time: lasted(t) }, still))
          : AF.tn('heatmap.n_reviews_so_far_due_still', c.n, still))
      // (shaded by time, the time first: "2 hr 9 min, 420 reviews")
      : c.n ? (H.by !== 'time' ? reviewsIn(c.n, t) : t ? cap(AF.tn('heatmap.time_n_reviews', c.n, { time: lasted(t) }))
        : AF.tn('heatmap.n_reviews_no_time_kept', c.n))
      : H.daysOff.has(c.o) ? AF.t('heatmap.not_studied_a_day_off') : off ? (c.o === 0 ? AF.t('heatmap.nothing_due_today') : AF.t('heatmap.nothing_was_due'))
      : H.pond.has(c.o) ? AF.t('heatmap.not_studied_a_pond_in_your') : c.o === 0 ? AF.t('heatmap.not_studied_yet') : AF.t('heatmap.not_studied');
    // (where in its streak, in days studied)
    let day = 0;
    for (let o = run ? run.from : 1; o <= c.o; o++) if (H.n(o)) day++;
    const total = run ? run.days : 0, at = { day: num(day) };
    // (a lone day between missed ones is no run: nothing to say)
    const where = run && off ? (run === H.current ? AF.tn('heatmap.doesnt_break_your_n_day_streak', total) : AF.tn('heatmap.didnt_break_a_n_day_streak', total))
      : !run || (total === 1 && run !== H.current) ? ''
        : (run === H.current ? (day === total ? AF.t('heatmap.day_day_of_your_streak', at) : AF.tn('heatmap.day_day_of_your_n_day', total, at))
          : day === total && total >= SHOWN_STREAK ? AF.tn('heatmap.last_day_of_a_n_day', total)
            : total >= SHOWN_STREAK ? AF.tn('heatmap.day_day_of_a_n_day', total, at) : AF.tn('heatmap.day_day_of_n_in_a', total, at))
        // (which of your longest it is: on its trophy, not on each of its days)
        + (ui.hit && ui.hit.trophy >= 0 && H.podium.has(run) ? `<br>${placeName(ui.hit.trophy)}` : '');
    // (the soonest it can be, with days off a week allowed: if you take none of them)
    const goal = H.goal && H.goal.o === c.o ? '<br>' + goalLine(H.goal, (data.stats && data.stats.streak_week || 7) < 7) : '';
    const began = H.fs === c.o ? `<br>${AF.t('heatmap.your_forest_began')}` : H.fs !== null && c.o < H.fs && c.o >= H.first ? `<br><i>${AF.t('heatmap.before_your_forest_began')}</i>`
      : H.fs === null && H.cf === c.o ? `<br>${AF.t('heatmap.ponds_and_animals_count_from_here')}` : '';
    const came = goal + began + (H.animals.get(c.o) || []).map(a => `<br>${esc(a.came)}`).join('');
    const marked = H.marked.has(c.o) ? `<br>${markLine(H.marked.get(c.o), c.o)}` : '';
    // (in cards, not reviews: a card reviewed twice that day counts once)
    const [lost, of] = c.o <= 0 && c.n ? H.gone.get(c.o) || [0, 0] : [0, 0];
    const gone = !lost ? '' : `<br><i>${lost >= of ? (of === 1 ? AF.t('heatmap.its_card_has_since_been_deleted') : of === 2 ? AF.t('heatmap.both_of_its_cards_have_since')
      : AF.tn('heatmap.all_n_of_its_cards_have', of))
      : AF.tn('heatmap.n_of_its_of_cards_have', lost, { of: num(of) })}</i>`;
    // (today, yesterday and tomorrow by name, the year left out)
    const near = c.o >= -1 && c.o <= 1;
    const head = `<b>${esc(near ? AF.t('heatmap.near_date', { near: AF.i18n.nearDay(c.o), date: withWeekday(c.ms, false) }) : withWeekday(c.ms, true))}</b>`;
    // (a trophy pointed at: its day and its streak, no more; the day's own numbers are on its tile)
    const trophy = ui.hit && ui.hit.trophy >= 0 && run && H.podium.has(run);
    const tree = data.showForest === false || c.o < H.first ? null : treesByDay.get(c.o);
    // (its cards always "cards", as before)
    const planted = tree ? `<br>${AF.tn('heatmap.planted_tree_n_new_cards', tree.n)}` : '';
    const zoom = root.afVisits, scene = root.afEnv;
    const inView = tree && scene && scene.placed.some(p => !p.it.pond && p.it.ago === tree.ago);
    const location = !tree || data.showForest === false || inView ? '' : zoom && zoom.on
      ? `<br><i>${AF.t('heatmap.this_tree_is_outside_your_current')}</i>`
      : data.merged && tree.ago >= data.merged.to_ago && tree.ago <= data.merged.from_ago
        ? `<br><i>${AF.t('heatmap.this_day_s_tree_is_part')}</i>` : '';
    // (days selected, none of them on this page: what they are, quietly, so a page dimmed all over says why)
    const away = ui.sel && !ui.onScreen().some(d => d.cells.some(ui.inSel))
      ? `<br><span class="af-hint">${AF.t('heatmap.selected_what', { what: ui.selSummary().split('<br>')[0].replace(/<\/?b>/g, '') })}</span>` : '';
    tip.innerHTML = trophy ? `${head}<br>${placeLine(ui.hit.trophy, total)}`
      : `${head}<br>${what}${planted}${location}${gone}${where ? `<br><i>${where}</i>` : ''}${came}${marked}${away}`;
    ui.reveal();
    // below the day, centred on it, so it never covers ‹ Today › and the months over the weeks
    // (above it when there is no room below in the window), kept inside the calendar's sides;
    // placed by the page's own offsets, which a zoomed page leaves right
    const on = (ui.pointed || ui.drawn).cv, left = grid.offsetLeft + on.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + on.offsetTop;
    const cx = left + (c.x + TILE / 2) * ui.k, top = canvasTop + (c.y - 1) * ui.k, bottom = canvasTop + (c.y + TILE + 1) * ui.k;
    const above = on.getBoundingClientRect().top + (c.y + TILE + 1) * ui.k + TIP_GAP + tip.offsetHeight > window.innerHeight;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = (above ? top - tip.offsetHeight - TIP_GAP : bottom + TIP_GAP) + 'px';
  };
  grid.addEventListener('mousemove', point);
  Object.assign(ui, { totals, reviewsIn, due, perDay, studiedOf, studiedLines, cellAt, dueNow, allGone, opens, notesOf, point, tell });
};
})();

/* Memory Forest — what stands out on the study heatmap: the days a hover is about, the day under the
 * pointer, and the days selected, with what they tell and do. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { rgb, layer, esc } = AF.u;
const { STATE, TILE, ROWS, BRACKET, markLine, DAY_MS, TIP_GAP, SPOT_DIM, TIP_WAIT, fmt, dayOnly, withWeekday, yearOf, DIAG } = Cal;

Cal.highlighting = ui => {
  const { root, data, cal, box, H, swiped, grid, notes, tip, hover } = ui;
  let selAt = null, selOn = null;  // (the day selected their summary was last asked from, and its year: it sits under that day's stretch)
  const inSel = c => !!ui.sel && ui.sel.has(c.o);
  // a layer over a year's weeks (`d`, the year in view or an earlier one shown) dimming the days
  // `keep` leaves out (or, where the style has bands, those not in the key's shade `lv`)
  const dimLayer = (d, keep, lv) => {
    const [cv, g] = layer(d.W, d.Hh);
    g.fillStyle = rgb(ui.paper.bg, SPOT_DIM);
    if (d.joined) {
      // (a joined shape dimmed by its own pixels: a month or a streak lights its days' part of the
      // shape, a shade of the key the bands in that shade, `lv`, where the style has bands)
      const img = g.createImageData(d.W, d.Hh), px = img.data, [r0, g0, b0] = ui.paper.bg, a0 = Math.round(255 * SPOT_DIM);
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
    } else {
      // (every day's square dimmed, then a kept day's face lit again with as much round it on each
      // side: a pixel where the days have room between them, none where they touch. Dimming the
      // other days alone left a kept day its gap on the left and top and none on the right and
      // bottom, 2026-10-19)
      for (const c of d.cells) g.fillRect(c.x - 1, c.y - 1, STATE.CELL, STATE.CELL);
      for (const c of d.cells) {
        if (!keep(c)) continue;
        const [x0, y0, x1, y1] = c.face || [0, 0, TILE, TILE], m = STATE.CELL > x1 - x0 ? 1 : 0;
        g.clearRect(c.x + x0 - m, c.y + y0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m);
      }
    }
    cv.className = 'af-cal-above af-cal-spot';
    Object.assign(cv.style, { left: d.cv.offsetLeft + 'px', top: d.cv.offsetTop + 'px', width: d.cv.style.width,
      height: d.cv.style.height, imageRendering: d.cv.style.imageRendering });
    grid.insertBefore(cv, notes);
    cv.afOn = d;
    return cv;
  };
  // while days are selected, every year shown dims its days not selected (a year with none of them
  // dims all over, so a selection reads as one, whichever years it spans): a layer a year, kept until
  // the selection or the year changes, hidden under a hover's own spot on the same year
  // (a day not selected, pointed at, is lit too while the pointer is on it: its ring round a dimmed
  // tile hid its shade, the very thing a Cmd-click would add)
  let holeAt = null;
  const showPickDim = () => {
    const years = ui.sel && ui.drawn ? [ui.drawn, ...ui.pasts.filter(p => p.cv && p.cv.isConnected)] : [];
    ui.selCvs = ui.selCvs.filter(x => {
      const ok = years.includes(x.d) && x.ver === ui.selVer && x.hole === holeAt && x.cv.isConnected && x.d.cv.isConnected;
      if (!ok) x.cv.remove();
      return ok;
    });
    for (const d of years) if (!ui.selCvs.some(x => x.d === d)) ui.selCvs.push({ d, ver: ui.selVer, hole: holeAt, cv: dimLayer(d, x => inSel(x) || x.o === holeAt) });
    for (const x of ui.selCvs) x.cv.style.visibility = ui.spotCvs.some(cv => cv.afOn === x.d) ? 'hidden' : '';
  };
  // a hover's days standing out (a shade in the key, a month, a streak): the others dimmed, on the
  // year pointed at (a streak's bracket on an earlier year lights that year's days); null: none
  const spot = (keep, lv) => {
    ui.spotCvs.forEach(cv => cv.remove());
    // (on every row shown, so a shade of the key, a streak or a month split over two rows lights its
    // days in all of them, and the rest dim alike: on the row pointed at alone, Streak view's other
    // rows stayed lit as if they were all of that shade)
    ui.spotCvs = keep && ui.drawn ? [ui.drawn, ...ui.pasts.filter(p => p.cv && p.cv.isConnected)].map(d => dimLayer(d, keep, lv)) : [];
    showPickDim();
  };
  // the day under the pointer: ringed in today's frame colour, which shows on every shade
  const ring = c => {
    holeAt = ui.sel && c && !inSel(c) ? c.o : null;
    spot(null);
    if (!c && ui.editing && ui.drawn) c = ui.drawn.cells.find(x => x.o === ui.editing.o) || null;  // (a day being marked keeps it)
    hover.hidden = !c;
    if (!c) return;
    const cv = (ui.pointed || ui.drawn).cv;
    // (round the day's face, a pixel out on every side: Flat's whole tile, as today's frame; a
    // scenery's own tile its 8 pixels, not its gap)
    const [x0, y0, x1] = c.face || [0, 0, TILE];
    hover.style.left = (cv.offsetLeft + (c.x + x0 - 1) * ui.k) + 'px';
    hover.style.top = (cv.offsetTop + (c.y + y0 - 1) * ui.k) + 'px';
    hover.style.width = hover.style.height = (x1 - x0 + 2) * ui.k + 'px';
    hover.style.borderRadius = ui.drawn.smooth ? (ui.drawn.radius + 1) * ui.k + 'px' : '';
    hover.style.borderColor = ui.drawn.ring;
  };
  // the first tooltip after the pointer comes onto the heatmap waits a moment, so crossing it on the
  // way elsewhere flashes none; from one day to the next after that, at once (a tap and the
  // keyboard at once too)
  let warm = false, waking = 0;
  const reveal = () => {
    tip.hidden = false;
    ui.selTip = false;
    if (warm || ui.touched || document.activeElement === (ui.drawn && ui.drawn.cv)) { tip.style.visibility = ''; warm = true; return; }
    tip.style.visibility = 'hidden';
    clearTimeout(waking);
    waking = setTimeout(() => { tip.style.visibility = ''; warm = true; }, TIP_WAIT);
  };
  const pointTree = c => { if (root.afPointTreeDay) root.afPointTreeDay(c ? -c.o : null); };
  // (the tip shown again straight away, by the key or a streak, must not stay invisible from a day brushed too briefly to wake it)
  const unpoint = () => { pointTree(null); tip.hidden = true; tip.style.visibility = ''; ring(null); ui.last = undefined; warm = false; clearTimeout(waking); ui.pointed = null; showSel(); };
  // how far you can page: back to the first day counted, on to the last day ahead counted (Streak
  // view: back while its top row starts after your first review, on as far as the days ahead go)
  const can = win => (ui.view === 'streak' ? { back: ui.ahead > 0 || (ui.rows.length ? ui.rows[0] : win).from > H.first, on: ui.pages.length > 0 || win.to < H.lastDue }
    : { back: win.from > H.first, on: win.to < H.ahead });


  // the days selected, as runs of days in a row: [[from, to], ...], oldest first
  const runsOf = () => {
    const runs = [];
    for (const o of [...ui.sel].sort((a, b) => a - b)) {
      const r = runs[runs.length - 1];
      if (r && r[1] === o - 1) r[1] = o; else runs.push([o, o]);
    }
    return runs;
  };
  // the days selected, in a few words, as a month tells its own: "Mar 12 to Apr 30, 2026" (one stretch)
  // or "12 days, Mar 3 to Apr 30, 2026" (days apart), the days studied among them, their reviews
  // and about how many a day, their marks and the cards due on them
  const selSummary = () => {
    const runs = runsOf(), from = runs[0][0], to = runs[runs.length - 1][1];
    const day = o => esc(fmt(H.today + o * DAY_MS)), year = o => yearOf(H.today + o * DAY_MS);
    // (a year said once; up to today, "to today", as your streak's bracket says it)
    const first = to !== 0 && year(from) === year(to) ? esc(dayOnly(H.today + from * DAY_MS)) : day(from);
    const stretch = { from: first, to: to === 0 ? '' : day(to) };
    // (one day selected: that day's own words, as its tooltip has them, not a stretch's "Studied every day")
    if (ui.sel.size === 1) {
      const n = H.n(from), what = from < H.first ? AF.t('heatmap.before_your_first_review') : from > H.ahead ? AF.t('heatmap.too_far_ahead_to_count')
        : from > 0 ? (n ? ui.due(n) : AF.t('heatmap.nothing_due_yet')) : n ? ui.reviewsIn(n, H.time(from)) : from === 0 ? AF.t('heatmap.not_studied_yet') : AF.t('heatmap.not_studied');
      // (and how to go on from it, quietly: a Shift-click stretching from this day can't be guessed)
      return [`<b>${esc(withWeekday(H.today + from * DAY_MS, true))}</b>`, what, ...(H.marked.has(from) ? [markLine(H.marked.get(from), from)] : []),
        `<span class="af-hint">${AF.t('heatmap.shift_click_another_day_to')}</span>`].join('<br>');
    }
    if (runs.length === 1) {
      const span = from === to ? day(from) : to === 0 ? AF.t('heatmap.from_to_today', stretch) : AF.t('heatmap.from_to_to', stretch);
      // (a stretch counts its days where a month needn't: "Studied all of these 21 days", not "every day")
      const studied = from > 0 ? [] : ui.studiedLines(from, to);
      if (studied[0] === AF.t('heatmap.studied_every_day')) studied[0] = AF.tn('heatmap.studied_all_of_these_n_days', to - from + 1);
      return [`<b>${span}</b>`, ...studied, ...ui.notesOf(from, to, 'after')].join('<br>');
    }
    const head = to === 0 ? AF.tn('heatmap.n_days_from_to_today', ui.sel.size, stretch)
      : AF.tn('heatmap.n_days_from_to_to', ui.sel.size, stretch);
    return [`<b>${head}</b>`, ...(from > 0 ? [] : pickedLines()), ...ui.notesOf(from, to, 'after', o => ui.sel.has(o))].join('<br>');
  };
  // studiedLines' words for days selected apart: "Studied 9 of 12 days (75%)", their reviews and
  // about how many a day; only the days since your first review, up to today
  const pickedLines = () => {
    const end = H.n(0) ? 0 : -1, past = [...ui.sel].filter(o => o >= H.first && o <= end);
    if (!past.length) return [[...ui.sel].some(o => o === 0) ? AF.t('heatmap.not_studied_yet') : AF.t('heatmap.before_your_first_review')];
    let studied = 0, reviews = 0, secs = 0;
    for (const o of past) if (H.n(o)) { studied++; reviews += H.n(o); secs += H.time(o) || 0; }
    if (!studied) return [AF.t('heatmap.not_studied')];
    const span = past.length, pct = Math.min(99, Math.max(1, Math.round(100 * studied / span)));
    // (the heading counts them: "of them" where these are all of them, not the count again)
    const all = span === ui.sel.size;
    return [studied === span ? (all ? AF.t('heatmap.studied_all_of_them') : AF.tn('heatmap.studied_all_of_these_n_days', span))
      : all ? AF.tn('heatmap.studied_n_of_them_pct', studied, { pct }) : ui.studiedOf(studied, span, '', false),
    ui.totals(reviews, secs), ui.perDay(reviews, studied, secs, studied < span)];
  };
  // (the days selected open in the browser where one of them in the past was studied)
  // (or, ahead, has cards due: those open as a day ahead clicked opens them; today, before you
  // study, its cards due, as today clicked opens them)
  const dueToday = () => !!ui.sel && ui.sel.has(0) && !H.n(0) && H.dueToday > 0;
  // (not days whose cards have all since been deleted, as a day clicked: the browser opened on none,
  // or not at all, under a pointer that said it would)
  const selOpens = () => !!ui.sel && !!cal.browse && (dueToday() || [...ui.sel].some(o => o >= H.first && o <= H.ahead && H.n(o) > 0 && !ui.allGone(o)));
  // the days selected: lit, their trees in the forest; pointed at (`told`), their summary under their
  // days in view (as a streak's is under its bracket); at rest the lit days alone, so the footer
  // under them (the journal, the key) stays in view; none selected: all back as it was
  // (under the year pointed at, the year in view or an earlier one, and under the stretch of them
  // the pointer is on, `at`, not halfway between the first and the last, over days not selected;
  // `selAt` and `selOn` keep it for the summary placed again)
  function showSel(told = false, at = null) {
    if (root.afLightTreeDays) root.afLightTreeDays(ui.sel && data.showForest !== false ? [...ui.sel].map(o => -o) : null);
    spot(null);
    ui.selTip = false;
    if (!told) { if (ui.sel) tip.hidden = true; return; }
    if (!ui.sel || !ui.drawn || ui.editing) return;
    if (at) { selAt = ui.sel.has(at.o) ? at.o : null; selOn = ui.pointed || ui.drawn; }
    // (and, where a click opens them, says so, quietly, as the forest's own tooltips do: that a
    // click on one of them opens them all can't be guessed)
    tip.innerHTML = selSummary() + (selOpens() && ui.sel.size > 1 ? `<br><span class="af-hint">${AF.t('tooltip.click_to_see_these_cards')}</span>` : '');
    tip.hidden = false; tip.style.visibility = '';
    ui.selTip = true;
    placeSel();
  }
  // their summary under their days in view, centred under them, kept inside the heatmap's sides
  function placeSel() {
    const run = selAt !== null && ui.sel.has(selAt) ? runsOf().find(([a, b]) => selAt >= a && selAt <= b) : null;
    const on = selOn && selOn.cv.isConnected ? selOn : ui.drawn, near = run ? on.cells.filter(x => x.o >= run[0] && x.o <= run[1]) : [];
    const cells = near.length ? near : on.cells.filter(inSel);
    if (!cells.length) { tip.hidden = true; ui.selTip = false; return; }
    const x0 = Math.min(...cells.map(c => c.x)), x1 = Math.max(...cells.map(c => c.x)) + TILE;
    const left = grid.offsetLeft + on.cv.offsetLeft - grid.scrollLeft, cx = left + (x0 + x1) / 2 * ui.k;
    tip.style.left = Math.max(0, Math.min(box.clientWidth - tip.offsetWidth, cx - tip.offsetWidth / 2)) + 'px';
    tip.style.top = grid.offsetTop + on.cv.offsetTop + (on.band + ROWS * STATE.CELL + BRACKET) * ui.k + TIP_GAP + 'px';  // (under the lane)
  }
  // a day selected: `stretch` (Shift) every day from the anchor to it, else (Cmd) it alone, selected or dropped
  const pick = (o, stretch) => {
    if (stretch) {
      if (ui.anchor === null) { ui.anchor = o; ui.base = new Set(ui.sel || []); }
      ui.sel = new Set(ui.base);
      for (let d = Math.min(ui.anchor, o); d <= Math.max(ui.anchor, o); d++) ui.sel.add(d);
    } else {
      ui.sel = new Set(ui.sel || []);
      if (ui.sel.has(o)) ui.sel.delete(o); else ui.sel.add(o);
      ui.anchor = o; ui.base = new Set(ui.sel);
    }
    const c = (ui.pointed || ui.drawn).cells.find(x => x.o === o) || null;
    // (a day dropped, still pointed at, tells its own tooltip again, as any day not selected does;
    // it went blank until the pointer moved on)
    if (!ui.sel.size) { unpick(); ui.last = undefined; if (c) { ui.last = c; ui.tell(c); } return; }
    ui.selVer++;
    ui.last = undefined;
    if (c && !ui.sel.has(o)) { showSel(); ui.last = c; ui.tell(c); return; }
    pointTree(null); ring(c);
    grid.classList.toggle('af-click', selOpens());
    showSel(ui.sel.has(o), c);
  };
  const unpick = () => {
    if (!ui.sel) return false;
    ui.sel = null; ui.anchor = null; ui.base = null; selAt = null; selOn = null; ui.selVer++;
    showSel();
    if (!ui.editing) { tip.hidden = true; }
    return true;
  };
  // (Esc, or a click anywhere off the heatmap, lets them go; each listener goes with its heatmap)
  const offSel = e => {
    if (!box.isConnected) { document.removeEventListener('keydown', offSel, true); document.removeEventListener('mousedown', offSel, true); return; }
    if (!ui.sel || ui.editing) return;
    if (e.type === 'keydown' ? e.key === 'Escape' : !box.contains(e.target)) { if (unpick() && e.type === 'keydown') { e.preventDefault(); e.stopPropagation(); } }
  };
  if (!swiped) { document.addEventListener('keydown', offSel, true); document.addEventListener('mousedown', offSel, true); }
  Object.assign(ui, { inSel, showPickDim, spot, ring, reveal, pointTree, unpoint, can, runsOf, selSummary, dueToday, selOpens, showSel, placeSel, pick, unpick });
};
})();

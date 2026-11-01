/* Memory Forest — the study heatmap on the page: a view drawn and laid out (draw, lay), Streak view's
 * earlier rows, the months' labels, paging, and what keeps it up to date (a moving style's loop, the phone's
 * swipe, a new width, Anki's theme). */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { rgb, esc, animates, onTheme } = AF.u;
const { STATE, TILE, ROWS, LABEL_END, TILE_FACE, DAY_MS, MONTHS_SHOWN, TODAY_AT, SWIPED_K, SWIPED_TODAY_AT, LABEL_GAP, DAYS_ROOM, NOTE_ROOM, SINCE_ROOM, fmt, yearOf, openRows, streakRows, pageBefore, weeksPerRow, ROW_GAP, NOTE_H, ACTS_ROOM, windowOf, pageOf, paint, dpr, sharpK, countFor, monthsRoom, keyEnds } = Cal;

const LIVE_MS = 66;  // (~15 frames a second, as the forest's own loop: core.js FRAME_MS)

Cal.drawing = ui => {
  const { root, data, cal, box, H, sp, moving, swiped, rtl, stays, grid, acts, byBox, viewBox, months, days, notes, tip } = ui;
  function draw() {
    const hadCv = !!ui.drawn && document.activeElement === ui.drawn.cv;  // (the keyboard on the days: kept there)
    const old = ui.drawn && ui.drawn.cv;
    // (More days' By year is narrower than Timeline: the switch changes its width, or its row's)
    if (!swiped) { root.afCalView = ui.view; if (root.classList.contains('af-apart') && root.afFit) root.afFit(); else AF.calendarFit(box, cal, ui.view, data.maxWidth, data.inAnki); }
    const count = swiped ? MONTHS_SHOWN : countFor(ui.view, grid.clientWidth);
    // (paged away, a narrower or wider heatmap keeps the month you were looking at last in view)
    if (ui.drawn && ui.page && ui.drawn.count !== count) ui.page += ui.drawn.count - count - Math.round(ui.drawn.count * TODAY_AT) + Math.round(count * TODAY_AT);
    let win;
    if (!swiped && ui.view === 'streak') {
      const W = weeksPerRow(grid.clientWidth);
      ui.rows = streakRows(H, W, ui.pages.length ? ui.pages[ui.pages.length - 1] : null, ui.ahead);
      win = ui.rows.pop();
    } else {
      ui.rows = [];
      win = windowOf(H, swiped ? 'swiped' : ui.view, ui.page, ui.year, count);
    }
    const d = paint(H, win, sp, ui.paper);
    ui.drawn = Object.assign(d, { win, count });
    ui.last = undefined;
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
    ui.drawn.above.className = 'af-cal-above';
    grid.insertBefore(ui.drawn.above, notes);
    ui.drawn.cv.className = 'af-cal-canvas';
    ui.drawn.cv.setAttribute('role', 'img');
    ui.drawn.cv.setAttribute('aria-label', ui.described(win));
    grid.insertBefore(ui.drawn.cv, notes);
    const focused = box.contains(document.activeElement) ? document.activeElement : null;
    if (!swiped) ui.drawn.cv.tabIndex = 0;  // (the days a tab stop: the keyboard's way along them, input.js)
    if (hadCv) ui.drawn.cv.focus();
    // what the tiles mean, read off the tiles themselves
    // (Smooth: the face alone, filled, as the days are drawn: no gap row and column for a rim)
    const swatch = cv => {
      const c = document.createElement('canvas'), F = ui.drawn.smooth ? TILE_FACE : TILE, g = c.getContext('2d');
      c.width = c.height = F;
      if (ui.drawn.smooth) { g.fillStyle = rgb(cv.fill); g.fillRect(0, 0, F, F); }
      g.drawImage(cv, 0, 0, F, F, 0, 0, F, F);
      c.className = 'af-cal-swatch';
      return c;
    };
    const keyBox = box.querySelector('.af-cal-key'), word = t => { const w = document.createElement('span'); w.textContent = t; return w; };
    keyBox.textContent = '';  // (and each appended alone: Chromium 77, Anki 2.1.45's, has no replaceChildren)
    // (Less .. More, by reviews or by time alike: a shade pointed at gives its numbers)
    const ends = keyEnds(H);
    [word(ends[0])].concat(ui.drawn.key.map(swatch), [word(ends[1])]).forEach(el => keyBox.appendChild(el));
    viewBox.querySelectorAll('button').forEach(b => {
      const on = b.dataset.view === ui.view;
      b.classList.toggle('af-on', on); b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1;
    });
    past();
    byBox.querySelectorAll('button').forEach(b => {
      const on = b.dataset.by === H.by;
      b.classList.toggle('af-on', on); b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1;
    });
    if (!swiped) {
      const may = ui.can(win);
      ui.btn(-1).disabled = !may.back; ui.btn(1).disabled = !may.on;
      // (on today's page already, the jump stays where it is, dimmed; it points the way today
      // lies, » from the past, « from the days ahead)
      const now = ui.btn(0), later = ui.view === 'by_year' ? (ui.year || yearOf(H.today)) > yearOf(H.today) : ui.view === 'streak' ? ui.ahead > 0 : ui.page > 0;
      now.disabled = ui.view === 'by_year' ? win.year === yearOf(H.today) : ui.view === 'streak' ? !ui.pages.length && !ui.ahead : ui.page === 0;
      now.textContent = later === rtl ? '»' : '«';  // (right to left, today lies the other way)
      // (a button gone out of use under the keyboard - ‹ at the start of your history, › at the end,
      // » once back - hands its focus to the arrow still in use, so Tab starts from where you were)
      if (focused && focused.disabled) { const to = [ui.btn(1), ui.btn(-1)].find(b => b !== focused && !b.disabled); if (to) to.focus(); }
    }
    lay();
    if (ui.wakeLive) ui.wakeLive();
    // (their summary goes with their days: under them on the new page, or away when none is on it)
    if (ui.sel && (tip.hidden || ui.selTip)) ui.showSel(ui.selTip); else if (ui.sel) ui.spot(null);
  }

  // Streak view's earlier rows: those above the last one (drawn as the heatmap's own weeks), each
  // with its months over it, oldest at the top, so the picture reads down to now as a calendar does
  const pastBox = box.querySelector('.af-cal-past');
  grid.insertBefore(pastBox, grid.firstChild);  // (before the year in view's weeks: they follow it)
  // each earlier row's weeks as last painted, painted again only when what they show changes: the
  // shade's choice, the page's colour, a mark in that row (the look and the days come with a new
  // calendar; a new scale only sharpens them again, layPast)
  const painted = new Map();
  const paintPast = (id, win) => {
    const key = [H.by, ui.paper.dark, ui.paper.bg.join(), [...H.marked].filter(([o]) => o >= win.from && o <= win.to)
      .map(([o, m]) => `${o}:${m.icon}:${m.name}`).join()].join('|');
    const was = painted.get(id);
    if (was && was.key === key) return was.d;
    const d = Object.assign(paint(H, win, sp, ui.paper), { win });
    painted.set(id, { key, d });
    return d;
  };
  function past() {
    pastBox.textContent = '';
    ui.pasts = [];
    // (shown: one picture down to the last row, the "Since" under it gone, the rows above saying it)
    box.classList.toggle('af-cal-years-open', ui.rows.length > 0);
    for (const win of ui.rows) {
      const d = paintPast(`${win.from}:${win.cols}`, win), el = document.createElement('div');
      el.className = 'af-cal-past-year';
      // (its months' labels, and its streaks' lengths: laid out with the weeks, layPast)
      el.innerHTML = '<div class="af-cal-past-head"></div><div class="af-cal-notes"></div>';
      d.head = el.firstChild; d.notes = el.lastChild;
      d.cv.className = 'af-cal-canvas af-cal-past-weeks';
      d.cv.setAttribute('role', 'img');
      d.cv.setAttribute('aria-label', ui.described(win));
      d.above.className = 'af-cal-above';
      el.insertBefore(d.cv, d.notes);
      el.insertBefore(d.above, d.notes);
      pastBox.appendChild(el);
      ui.pasts.push(d);
    }
  }
  // a row's months' labels, each over its first week: January is its year alone, every other month
  // its name, and in Streak view a row's first label its year too ("Jun 2024"); where two would
  // touch (a narrow calendar), the one with a year stays and the other goes
  // (right to left, each label ends over its month's first week, at that week's right edge, and the
  // next one stands to its left)
  // a row's first label, its month and year, the month written as the other labels write it (German's
  // "Nov. 2023" and "März 2023" beside "Nov" and "Mär" read as two spellings); a form with more than
  // the two (Portuguese's "nov. de 2023") or none apart (Japanese's "2023年11月") is kept as it is
  const monthYear = (ms, m) => {
    const s = AF.i18n.dayIn(ms, { month: 'short', year: 'numeric' }), rest = s.replace(AF.i18n.dayIn(ms, { year: 'numeric' }), '').trim();
    return rest && !/\s/.test(rest) && s.trim().split(/\s+/).length === 2 ? s.replace(rest, AF.i18n.monthName(m, 'short')) : s;
  };
  function label(into, d) {
    let html = '', lastM = -1;
    for (const c of d.cells) {
      const day = new Date(c.ms);
      if (day.getUTCDate() > 7 || day.getUTCMonth() === lastM || (rtl ? (c.x + TILE) * ui.k < LABEL_END : c.x * ui.k > d.W * ui.k - LABEL_END)) continue;
      lastM = day.getUTCMonth();
      const name = AF.i18n.monthName(lastM, 'short');
      const first = ui.view === 'streak' && !html;
      const text = lastM === 0 ? AF.i18n.dayIn(c.ms, { year: 'numeric' }) : first ? monthYear(c.ms, lastM) : name;
      html += `<span${text !== name ? ' class="af-cal-year"' : ''}${first ? ' data-first="1"' : ''} data-y="${day.getUTCFullYear()}" data-m="${lastM}" style="left:${c.x * ui.k}px">${text}</span>`;
    }
    into.innerHTML = html;
    if (rtl) for (const s of into.children) s.style.left = parseFloat(s.style.left) + TILE * ui.k - s.offsetWidth + 'px';
    const touch = (a, b) => (rtl ? b.offsetLeft + b.offsetWidth + LABEL_GAP > a.offsetLeft : b.offsetLeft < a.offsetLeft + a.offsetWidth + LABEL_GAP);
    let prev = null;
    for (const s of into.children) {
      // (a row's first label meeting January's year, "Dec 2025" and "2026": its month's name alone, the
      // year beside it saying which; dropped, a row begun in November or December had its first weeks
      // unnamed)
      if (prev && prev.dataset.first && s.dataset.m === '0' && touch(prev, s)) {
        const right = prev.offsetLeft + prev.offsetWidth;
        prev.textContent = AF.i18n.monthName(+prev.dataset.m, 'short');
        prev.classList.remove('af-cal-year');
        if (rtl) prev.style.left = right - prev.offsetWidth + 'px';
      }
      if (prev && touch(prev, s)) {
        const drop = prev.classList.contains('af-cal-year') && !s.classList.contains('af-cal-year') ? s : prev;
        drop.hidden = true;
        if (drop === s) continue;
      }
      prev = s;
    }
  }
  function layPast() {
    for (const d of ui.pasts) {
      d.head.style.height = monthsRoom(ui.k) + 'px';  // (as the months' row over the last one)
      label(d.head, d);
      d.cv.style.width = d.above.style.width = d.W * ui.k + 'px'; d.cv.style.height = d.above.style.height = d.Hh * ui.k + 'px';
      d.above.style.left = d.cv.offsetLeft + 'px'; d.above.style.top = d.cv.offsetTop + 'px';
      d.cv.style.imageRendering = d.above.style.imageRendering = ui.k < sharpK() ? 'auto' : '';
      if (d.sharpen) d.sharpen(ui.k * dpr());
      // each streak ending in this row, its length under its bracket, as the last row's are (a
      // streak going on into the next row says it there, once)
      d.notes.style.top = d.cv.offsetTop + (d.band + ROWS * STATE.CELL + 3 + 7) * ui.k - NOTE_H / 2 + 'px';
      d.notes.innerHTML = d.brackets.filter(b => b.run.to <= d.win.to && (b.x1 - b.x0) * ui.k >= NOTE_ROOM + 2 * (7 * ui.k + 4))
        .map(b => `<span class="af-cal-note${b.live ? ' af-cal-current' : ''}" style="left:${(b.x0 + b.x1) / 2 * ui.k}px">${AF.tn('heatmap.n_days', b.len)}</span>`).join('');
    }
  }
  function go(where) {
    const was = ui.drawn.win.from;
    if (where === '0') { ui.page = 0; ui.year = null; ui.pages = []; ui.ahead = 0; }
    else {
      const may = ui.can(ui.drawn.win);
      if (where === '-1' ? !may.back : !may.on) return;  // (a click on a button just disabled)
      if (ui.view === 'streak') {
        if (where === '1') { if (ui.pages.length) ui.pages.pop(); else ui.ahead++; }
        else if (ui.ahead) ui.ahead--;
        else ui.pages.push(pageBefore(H, ui.drawn.win.cols, openRows(H, ui.drawn.win.cols).length, (ui.rows.length ? ui.rows[0] : ui.drawn.win).from));
      }
      else if (ui.view === 'by_year') ui.year = (ui.year || yearOf(H.today)) + +where;
      else ui.page += +where * ui.drawn.count;
    }
    ui.unpoint();
    draw();
    // the new stretch slides in from the side you went towards (unless the forest is kept still)
    if (ui.drawn.win.from !== was && animates(data)) {
      grid.classList.remove('af-cal-from-left', 'af-cal-from-right');
      void grid.offsetWidth;  // (so the animation starts again on a quick second click)
      // (right to left, the earlier days come in from the right)
      grid.classList.add((ui.drawn.win.from < was) !== rtl ? 'af-cal-from-left' : 'af-cal-from-right');
    }
  }
  // fitted to the room there is, all its width (By year its year, Timeline its months, countFor),
  // smaller than its pixels if need be: no scrolling, smoothed where that leaves no whole device
  // pixel (sharpK)
  function lay() {
    const d = ui.drawn;
    ui.k = swiped ? Math.round((data.swipedK || SWIPED_K) * dpr()) / dpr() : (grid.clientWidth || d.W * 2) / d.W;
    // (the room over the year in view's weeks for its months, under the earlier years if any)
    grid.style.paddingTop = '0px';
    pastBox.style.paddingBottom = monthsRoom(ui.k) + (ui.pasts.length ? ROW_GAP : 0) + 'px';
    d.cv.style.width = d.above.style.width = d.W * ui.k + 'px'; d.cv.style.height = d.above.style.height = d.Hh * ui.k + 'px';
    layPast();
    // (the layer placed once the earlier years above are laid out: their size moves the year in
    // view down, and a layer placed before sat that much too high, its trophies over another year)
    d.above.style.left = d.cv.offsetLeft + 'px'; d.above.style.top = d.cv.offsetTop + 'px';
    // (the key's tiles as big as the calendar's, and as far apart)
    box.querySelectorAll('.af-cal-swatch').forEach((sw, i, all) => {
      const F = d.smooth ? TILE_FACE : TILE;
      sw.style.width = sw.style.height = F * ui.k + 'px'; if (i < all.length - 1) sw.style[rtl ? 'marginLeft' : 'marginRight'] = (STATE.CELL - F) * ui.k + 'px';
      sw.style.borderRadius = d.smooth ? d.radius * ui.k + 'px' : '';
    });
    d.cv.style.imageRendering = d.above.style.imageRendering = ui.k < sharpK() ? 'auto' : '';  // (too small to stay crisp, pixels smooth better than they drop)
    if (d.sharpen) d.sharpen(ui.k * dpr());
    label(months, d);
    months.style.top = d.cv.offsetTop - monthsRoom(ui.k) + 'px';
    // the weekdays of the second, fourth and sixth rows, beside the weeks (shown with the key, on hover)
    // (not where they would hang off the page: they stand just outside the forest's edge)
    if (!swiped) {
      const top = d.cv.offsetTop;
      days.innerHTML = [1, 3, 5].map(r => `<span style="top:${top + (d.band + r * STATE.CELL + TILE / 2) * ui.k}px">${esc(AF.i18n.weekdayName((STATE.weekStart + r) % 7, 'short'))}</span>`).join('');
      // (right to left, beside the weeks' first column, at the right)
      days.hidden = (rtl ? document.documentElement.clientWidth - box.getBoundingClientRect().right : box.getBoundingClientRect().left) < DAYS_ROOM;
    }
    // ‹ Today › stand over the months' row, in the gap above it (with earlier years shown, over the
    // first of them), unless the forest's caption's last line reaches them there: then they go down
    // onto that row, and a label under them makes way while they show (forest.css)
    if (!swiped) {
      const row = ui.pasts.length ? pastBox.firstChild.offsetTop : months.offsetTop;
      acts.classList.remove('af-acts-low');
      acts.style.top = row - ACTS_ROOM + 'px';
      // (the caption reaches them only from just above: not under the heatmap, nor beside it)
      const a = acts.getBoundingClientRect(), cap = stays ? null : root.querySelector('.af-caption');
      const words = cap ? [...cap.children].map(el => el.getBoundingClientRect()).filter(r => r.width && r.bottom > a.top - 30) : [];
      const low = words.some(r => (rtl ? r.left < a.right + LABEL_GAP : r.right > a.left - LABEL_GAP) && r.bottom > a.top - 4);
      acts.classList.toggle('af-acts-low', low);
      if (low) acts.style.top = row + 'px';
      const edge = rtl ? acts.offsetLeft + acts.offsetWidth + LABEL_GAP : acts.offsetLeft - LABEL_GAP;
      for (const s of months.children) s.classList.toggle('af-under', low && !ui.pasts.length && (rtl ? s.offsetLeft < edge : s.offsetLeft + s.offsetWidth > edge));
    }
    // each streak's length, the current one's too, centred under its bracket
    notes.style.top = d.cv.offsetTop + (d.band + ROWS * STATE.CELL + 3 + 7) * ui.k - NOTE_H / 2 + 'px';
    notes.innerHTML = d.brackets.filter(b => (b.x1 - b.x0) * ui.k >= NOTE_ROOM + 2 * (7 * ui.k + 4)).map(b => {
      const since = b.live && b.cut && !box.classList.contains('af-cal-years-open') && (b.x1 - b.x0) * ui.k >= SINCE_ROOM + NOTE_ROOM
        ? esc(fmt(H.today + b.run.from * DAY_MS)) : '';
      const text = since ? AF.tn('heatmap.n_days_since_date', b.len, { date: since }) : AF.tn('heatmap.n_days', b.len);
      return `<span class="af-cal-note${b.live ? ' af-cal-current' : ''}" style="left:${(b.x0 + b.x1) / 2 * ui.k}px">${text}</span>`;
    }).join('');
    if (swiped) { away(); clip(); }
    if (ui.selTip && !tip.hidden) ui.placeSel();  // (the earlier years shown or hidden move the year in view)
    // (the dimmed days' layers laid on their weeks again: drawn before this, as the days took the
    // focus back, or the earlier years shown above moving the year in view down, they sat at the
    // canvas's own size, or where the weeks were)
    ui.showPickDim();
    for (const cv of [...ui.spotCvs, ...ui.selCvs.map(x => x.cv)]) {
      if (!cv || !cv.afOn) continue;
      const c = cv.afOn.cv;
      Object.assign(cv.style, { left: c.offsetLeft + 'px', top: c.offsetTop + 'px', width: c.style.width, height: c.style.height, imageRendering: c.style.imageRendering });
    }
  }
  // the phone's timeline: opened on today, most of the way across, the days behind it in view
  function toToday(smooth) {
    // (right to left, the days behind it are to its right: today as far from the right edge)
    const today = ui.drawn.cells.find(c => c.o === 0), left = today ? Math.max(0, today.x * ui.k - grid.clientWidth * (rtl ? 1 - SWIPED_TODAY_AT : SWIPED_TODAY_AT)) : 0;
    if (smooth && grid.scrollTo) grid.scrollTo({ left, behavior: 'smooth' }); else grid.scrollLeft = left;
  }
  // (the timeline: Today only while today is scrolled out of view; a month's label cut by an
  // edge hidden until whole)
  function away() {
    const t = ui.drawn.cells.find(c => c.o === 0);
    if (!t) return;
    const x = t.x * ui.k - grid.scrollLeft;
    ui.btn(0).hidden = x > 0 && x < grid.clientWidth - TILE * ui.k;
  }
  function clip() {
    for (const s of months.children) s.style.visibility = s.offsetLeft < grid.scrollLeft + 4 || s.offsetLeft + s.offsetWidth > grid.scrollLeft + grid.clientWidth - 4 ? 'hidden' : '';
  }
  Object.assign(ui, { draw, go, toToday });
  draw();
  // a moving style: drawn again every LIVE_MS while the heatmap is on screen and the page shown,
  // from a timer as the forest's loop is (core.js), its earlier rows (Streak view) with it
  // (AF.calendarSpeed: how fast its clock runs, 1 its own pace, 0 held; for studies)
  let seen = true, ticking = false, liveTimer = 0;
  const liveTick = () => {
    liveTimer = 0;
    if (!box.isConnected) { stop(); return; }
    if (!seen || document.hidden || !ui.drawn || !ui.drawn.tick) { ticking = false; return; }
    const now = performance.now(), speed = AF.calendarSpeed == null ? 1 : AF.calendarSpeed;
    // (a long wait, a busy page, counts as at most three frames: the motion never jumps)
    STATE.liveClock += Math.min(LIVE_MS * 3, Math.max(0, now - STATE.liveClockAt)) / 1000 * speed; STATE.liveClockAt = now;
    try { ui.drawn.tick(STATE.liveClock); for (const d of ui.pasts) if (d.tick) d.tick(STATE.liveClock); }
    finally { liveTimer = setTimeout(liveTick, Math.max(0, LIVE_MS - (performance.now() - now))); }
  };
  // (its watchers set up only once a moving style is drawn: a heatmap that never moves adds none)
  let liveIo = null, watching = false;
  const liveShown = () => { if (!document.hidden) liveWake(); };
  function liveWake() {
    if (!moving || !ui.drawn || !ui.drawn.tick) return;
    if (!watching) {
      watching = true;
      document.addEventListener('visibilitychange', liveShown);
      if (window.IntersectionObserver) { liveIo = new IntersectionObserver(es => { seen = es[es.length - 1].isIntersecting; if (seen) liveWake(); }); liveIo.observe(grid); }
    }
    if (ticking) return;
    ticking = true; liveTick();
  }
  ui.wakeLive = liveWake; liveWake();
  if (swiped) {
    toToday(false);
    // (a tooltip goes with a swipe: it would point at a day no longer under it)
    grid.addEventListener('scroll', () => { away(); clip(); if (!tip.hidden) ui.unpoint(); }, { passive: true }); away(); clip();
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
  // a new width: Timeline's months counted again, or Streak view's weeks a row (draw), or the same
  // ones laid out again
  // (laid out just after the observer's turn, never in it: drawn there, the heatmap's new height came
  // back to the observers as one more change, and Chromium reported "ResizeObserver loop limit
  // exceeded" (77) or "loop completed with undelivered notifications" as the window was resized.
  // A timer, not a frame: Anki's offscreen check has none)
  let lastW = grid.clientWidth, relay = 0;
  const relaid = () => {
    relay = 0;
    if (!box.isConnected) { stop(); return; }
    if (grid.clientWidth === lastW) return;
    lastW = grid.clientWidth;
    if (!swiped && (countFor(ui.view, lastW) !== ui.drawn.count || (ui.view === 'streak' && weeksPerRow(lastW) !== ui.drawn.win.cols))) draw(); else lay();
    if (ui.editing) ui.placePin();  // (a mark's editor, open, stays by its day)
  };
  const ro = window.ResizeObserver ? new ResizeObserver(() => { if (!relay) relay = setTimeout(relaid, 0); }) : null;
  if (ro) ro.observe(grid);
  // Anki switched between light and dark: the page's colour is read again and the days painted
  // for it (their shades, the animals' outlines, today's frame): util.js onTheme
  const repaper = () => {
    if (!box.isConnected) { stop(); return; }
    const p = pageOf(box);
    if (p.bg.join() === ui.paper.bg.join() && p.solid === ui.paper.solid) return;
    ui.paper = p; ui.unpoint();
    box.classList.toggle('af-cal-on-light', !ui.paper.dark);
    draw();
  };
  const unheard = onTheme(repaper);
  function stop() {
    if (liveIo) liveIo.disconnect();
    clearTimeout(liveTimer); ticking = false;
    if (watching) document.removeEventListener('visibilitychange', liveShown);
    unheard();
    if (ro) ro.disconnect();
    clearTimeout(relay);
    if (root.afCalStop === stop) root.afCalStop = null;
  }
  root.afCalStop = stop;

};
})();

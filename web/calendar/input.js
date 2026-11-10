/* Memory Forest — the study heatmap's keyboard, taps, swipes and clicks. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { send } = AF.u;
const { SWIPE_PX, SWIPE_QUIET, SWIPE_AGAIN, TAP_SLOP } = Cal;

Cal.input = ui => {
  const { data, H, deck, swiped, rtl, grid, tip } = ui;
  // the days by the keyboard: ← → a week, ↑ ↓ a day, the page turning at its ends; PageUp and
  // PageDown a page, Home back to today; each day's tooltip as the pointer gives it; Enter opens
  // the day, Esc puts the tooltip away
  // (Streak view: across all its rows on screen, the rows above the last too, the page turning only
  // past the first row or the last)
  let cur = null;
  const onScreen = () => [ui.drawn].concat(ui.pasts);
  const topDay = () => (ui.pasts.length ? ui.pasts[0].win : ui.drawn.win).from;
  const curCell = () => {
    for (const d of onScreen()) { const c = d.cells.find(x => x.o === cur); if (c) { ui.pointed = d; return c; } }
    return null;
  };
  const toCur = () => { cur = Math.max(topDay(), Math.min(ui.drawn.win.to, cur)); ui.hit = null; ui.last = curCell(); ui.tell(ui.last); };
  if (!swiped) {
    tip.setAttribute('aria-live', 'polite');
    grid.addEventListener('focusin', e => {
      if (e.target !== ui.drawn.cv) return;
      if (cur === null || !curCell()) cur = ui.drawn.cells.some(c => c.o === 0) ? 0 : ui.drawn.win.to;
      toCur();
    });
    grid.addEventListener('focusout', e => { if (e.target === ui.drawn.cv) ui.unpoint(); });
    grid.addEventListener('keydown', e => {
      if (e.target !== ui.drawn.cv || e.altKey) return;
      // (Cmd+A, Ctrl+A off a Mac: every day studied or missed in view selected, up to today, as
      // Finder selects a folder's files; it selected the deck list's words instead)
      if ((MAC ? e.metaKey : e.ctrlKey) && !e.shiftKey && (e.key === 'a' || e.key === 'A')) {
        e.preventDefault();
        const days = onScreen().flatMap(d => d.cells.map(x => x.o)).filter(o => o >= H.first && o <= 0);
        if (!days.length) return;
        ui.sel = new Set(days); ui.anchor = null; ui.base = null; ui.selVer++; ui.last = undefined;
        const c = curCell();
        ui.ring(c); grid.classList.toggle('af-click', ui.selOpens());
        ui.showSel(true, c && ui.sel.has(c.o) ? c : ui.drawn.cells.find(x => ui.sel.has(x.o)));
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key !== 'Enter') return;
      // (← → a week the way the weeks run on screen: right to left, ← is a week later)
      const step = { ArrowLeft: rtl ? 7 : -7, ArrowRight: rtl ? -7 : 7, ArrowUp: -1, ArrowDown: 1 }[e.key], pg = { PageUp: '-1', PageDown: '1' }[e.key];
      if (e.key === 'Escape') { if (!tip.hidden) { e.preventDefault(); e.stopPropagation(); ui.unpoint(); } return; }
      if (e.key === 'Enter') { e.preventDefault(); const c = curCell(); if (c) dayClick(c, e); return; }
      // (Space selects or drops the keyboard's day, as Cmd+Enter does and as Space picks an item in a
      // list; it scrolled the deck list under the heatmap instead)
      if (e.key === ' ' && !e.ctrlKey && !e.metaKey) { e.preventDefault(); const c = curCell(); if (c) ui.pick(c.o, e.shiftKey); return; }
      // (Shift and Home selects on up to today, Shift and PageUp or PageDown a page on: as Shift and an
      // arrow does, as text is selected by the keyboard)
      if (e.key === 'Home') {
        e.preventDefault();
        if (e.shiftKey && ui.anchor === null) { ui.anchor = cur; ui.base = new Set(ui.sel || []); }
        cur = 0; if (!curCell()) ui.go('0');
        if (e.shiftKey) ui.pick(0, true);
        toCur(); return;
      }
      if (!step && !pg) return;
      e.preventDefault();
      // (Shift and an arrow selects as it goes, from the day it set out from: as text and lists are
      // selected by the keyboard)
      const stretch = !!(step || pg) && e.shiftKey;
      if (stretch && ui.anchor === null) { ui.anchor = cur; ui.base = new Set(ui.sel || []); }
      if (pg) { const along = cur - topDay(); ui.go(pg); cur = topDay() + along; }
      else {
        cur += step;
        const may = ui.can(ui.drawn.win);
        if (cur < topDay() && may.back) ui.go('-1'); else if (cur > ui.drawn.win.to && may.on) ui.go('1');
      }
      if (stretch) { cur = Math.max(topDay(), Math.min(ui.drawn.win.to, cur)); ui.pick(cur, true); }
      toCur();
      // (a plain arrow lets the day a stretch started from go: the next Shift and an arrow starts
      // where it stopped, the next Shift-click where it clicks)
      if (step && !stretch) { ui.anchor = null; ui.base = null; }
    });
  }
  // a finger's tap, taken as it lifts (a phone's web view need not make up a mouse's move for
  // it), unless it was a swipe along the timeline
  let down = null;
  grid.addEventListener('pointerdown', e => {
    ui.touched = e.pointerType !== 'mouse';
    down = ui.touched ? [e.clientX, e.clientY] : null;
  });
  grid.addEventListener('pointerup', e => {
    if (down && Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) < TAP_SLOP) {
      // (a second tap on what shows its tooltip puts it away)
      const again = !tip.hidden && ui.last;
      ui.last = undefined; ui.point(e);
      if (again && ui.last === again) { ui.unpoint(); ui.last = again; }  // (the mouse a phone makes up after must not bring it back)
    }
    down = null;
  });
  grid.addEventListener('pointercancel', () => { down = null; });
  grid.addEventListener('mouseleave', () => { ui.unpoint(); grid.classList.remove('af-click'); });
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
    // (towards the right, the later days; right to left, the earlier)
    if (Math.abs(swept) >= SWIPE_PX) { const to = (swept > 0) !== rtl ? '1' : '-1'; swept = null; ui.go(to); }
  }, { passive: false });
  // a click opens its day in the browser; Shift or Cmd and a click selects days (select), and a click on
  // one of them then opens them all (on any other day, lets them go)
  const MAC = /Mac|iPhone|iPad/.test(window.navigator.platform || '');
  const toggles = e => (MAC ? e.metaKey : e.ctrlKey);  // (a Mac's Ctrl-click is a right-click: the mark)
  const dayClick = (c, e) => {
    cur = c.o;  // (the keyboard's day goes there too: Shift and an arrow then stretches from it)
    // (on the year in view or an earlier one shown: a selection can span years)
    if ((e.shiftKey || toggles(e)) && !swiped) return ui.pick(c.o, e.shiftKey);
    if (ui.sel) {
      if (ui.inSel(c) && ui.selOpens()) {
        const runs = ui.runsOf().map(([a, b]) => [Math.max(a, H.first), Math.min(b, H.ahead)]).filter(([a, b]) => a <= b);
        send(`${data.channel}:days:${runs.map(r => r.join('_')).join(',')}:${deck}:${H.by}${ui.dueToday() ? ':due' : ''}`);
      } else if (!ui.inSel(c)) { ui.unpick(); ui.last = undefined; ui.tell(c); anchorAt(c); }
      return;
    }
    anchorAt(c);
    // zoomed in, a day with a tree: the camera glides to it and selects it, as a day's step does
    // (web/visit.js goTo; the deep forest's once Anki has sent its trees); its cards open from there,
    // a click on the tree selected, or a second on its day (reach: nowhere then); the tooltip says so
    if (ui.goesTo(c) && ui.forestRoot().afVisits.goTo(-c.o, () => open(c))) { ui.tell(c); return; }
    open(c);
  };
  const open = c => {
    if (ui.opens(c)) send(`${data.channel}:day:${c.o}:${deck}${ui.dueNow(c) ? ':due' : ':' + H.by}`);
  };
  // (a day clicked, or opened by Enter, is where a Shift-click then selects from, as Finder does
  // from the file last clicked: one Shift-click selects a stretch)
  const anchorAt = c => { if (!swiped) { ui.anchor = c.o; ui.base = new Set(); } };
  // (Shift and a click would select the page's words on its way)
  // (which kept the keyboard off the days too: the days take it as a plain click gives it them, so
  // Shift and an arrow then goes on from the day Shift-clicked)
  grid.addEventListener('mousedown', e => {
    if (!(e.shiftKey || toggles(e))) return;
    e.preventDefault();
    const c = !swiped && ui.cellAt(e);
    if (c && ui.drawn && document.activeElement !== ui.drawn.cv) { cur = c.o; ui.drawn.cv.focus({ preventScroll: true }); }
  });
  grid.addEventListener('click', e => {
    if (e.detail > 1) return;  // (a double-click opens the day once)
    const c = ui.cellAt(e);
    if (c) dayClick(c, e);
    // (a click between the days, on no day nor mark, lets the days selected go, as a click on a
    // folder's empty space does in Finder; a modifier held keeps them, as a slip of the click)
    // (on the weeks' own pictures only: the arrows and the view switch sit in the grid too)
    else if (ui.sel && !ui.hit && e.target.tagName === 'CANVAS' && !e.shiftKey && !toggles(e)) { ui.unpick(); ui.unpoint(); }
  });
  Object.assign(ui, { onScreen });
};
})();

/* Memory Forest — the days you mark as important on the heatmap (marks.py): their icons, their words,
 * their colour, the scenery's own (markPalOf), and the small editor a right-click opens over a day. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { rgb, esc, mix, send, oklab, fromOklab, lin, unlin } = AF.u;
const { TILE, DAY_MS, TIP_GAP, iso, fits, shades } = Cal;

// a day you marked as important (marks.py), with the icon you picked for it, all in the pin's red
// (red is the mark that is yours): R red, L its shine, D a dark detail; `label` names a mark you
// didn't name. Their order is marks.ICONS', the order a click on the icon steps through them.
const MARK_PAL = { R: '#e0524a', L: '#ffb3a8', W: '#fff1ec', D: '#8a7a6a', K: '#1c1a1a' };
const MARK_ICONS = {
  // (six by six each, so one sits centred, a pixel clear all round, on the eight a tile shows before
  // its edge or gap: TILE_FACE)
  pin: { label: AF.N_('heatmap.pin'), rows: ['.RRRR.', 'RRWWRR', 'RRWWRR', 'RRRRRR', '.RRRR.', '..RR..'] },
  exam: { label: AF.N_('heatmap.exam'), rows: ['RRRRRR', 'KRWWWR', 'RRRRRR', 'KRWWWR', 'RRRRRR', 'KRRRRR'] },
  trip: { label: AF.N_('heatmap.trip'), rows: ['..RR..', '..RR..', '.RRRR.', 'RRRRRR', '..RR..', '.RRRR.'] },  // (a plane from above, nose up: on its side it read as a red cross)
  birthday: { label: AF.N_('heatmap.birthday'), rows: ['..LL..', '..DD..', '.RRRR.', '.WRWW.', 'RRRRRR', 'RRRRRR'] },
  star: { label: AF.N_('heatmap.star'), rows: ['..RR..', '..RR..', 'RRWRRR', '.RRRR.', '.RRRR.', 'RR..RR'] },
  heart: { label: AF.N_('heatmap.heart'), rows: ['RR..RR', 'RRRRRR', 'RWRRRR', 'RRRRRR', '.RRRR.', '..RR..'] },
  done: { label: AF.N_('heatmap.done'), rows: ['......', '.....R', '....RR', 'R..RR.', 'RRRR..', '.RR...'] },
  sick: { label: AF.N_('heatmap.sick'), rows: ['......', 'R.....', 'RLL...', 'RLLWWR', 'RRRRRR', 'R....R'] },  // (a head on the pillow, a sheet over them: a bare bed read as a flag)
};
const MARK_ORDER = Object.keys(MARK_ICONS);
for (const m of Object.values(MARK_ICONS)) m.spr = { frames: [m.rows], pal: MARK_PAL };
const markOf = m => MARK_ICONS[m && m.icon] || MARK_ICONS.pin;
// a mark's name as the tooltips put it, escaped: one you typed kept in its own direction (a Latin
// name in a right-to-left line, say: AF.i18n.bdi)
const markName = m => (m.name ? (AF.i18n.rtl() ? AF.i18n.bdi(esc(m.name)) : esc(m.name)) : esc(AF.tx(markOf(m).label)));
// a mark's line in its day's tooltip, as html: its name (or its icon's), and how far off it is
const markLine = (m, o) => {
  const name = markName(m);
  // (its days unformatted, as before: "Exam in 1234 days")
  return o > 1 ? AF.tn('heatmap.name_in_n_days', o, { name, n: o }) : o === 1 ? AF.t('heatmap.name_tomorrow', { name })
    : o === 0 ? AF.t('heatmap.name_today', { name }) : name;
};

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
  const key = sp.mood.special + '|' + JSON.stringify(L0) + '|' + JSON.stringify(sp.hour || null);
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

Cal.markEditor = ui => {
  const { data, cal, box, H, sp, grid } = ui;
  // a right-click on a day marks it as important (an exam, say: marks.py) and opens a small editor
  // over it: the icons side by side, its own lit, its name, and × to take the mark away.
  // Enter, or a click anywhere else, keeps it; Esc puts back what was there. Kept by the add-on,
  // and drawn here at once (the forest itself is not drawn again).
  const pin = box.querySelector('.af-cal-pin'), pinName = pin.querySelector('.af-cal-pin-name');
  const pinIcons = pin.querySelector('.af-cal-pin-icons');
  pinIcons.setAttribute('role', 'radiogroup'); pinIcons.setAttribute('aria-label', AF.t('heatmap.mark_icon'));
  // each icon a small button of its own, drawn from its sprite at a scale of 2
  MARK_ORDER.forEach(key => {
    const b = document.createElement('button'), cv = document.createElement('canvas'), rows = MARK_ICONS[key].rows, s = 2;
    b.type = 'button'; b.className = 'af-cal-pin-icon'; b.dataset.icon = key; b.setAttribute('role', 'radio');
    b.title = AF.tx(MARK_ICONS[key].label); b.setAttribute('aria-label', b.title);
    cv.width = rows[0].length * s; cv.height = rows.length * s;
    const g = cv.getContext('2d');
    const markPal = markPalOf(sp, H.look);  // (in the colour the heatmap draws them in)
    rows.forEach((line, y) => { for (let x = 0; x < line.length; x++) if (markPal[line[x]]) { g.fillStyle = markPal[line[x]]; g.fillRect(x * s, y * s, s, s); } });
    b.appendChild(cv);
    b.addEventListener('mousedown', e => e.preventDefault());  // (the name keeps the focus)
    b.addEventListener('click', () => {
      const m = ui.editing && H.marked.get(ui.editing.o);
      if (!m) return;
      m.icon = key;
      showIcon(m);
      ui.draw();
    });
    pinIcons.appendChild(b);
  });
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
    pinName.placeholder = AF.tx(markOf(m).label);
  };
  // the editor above its day, as its tooltip stands, inside the heatmap's sides (under the day when
  // the window has no room above it); placed again when the heatmap is laid out anew
  const placeOver = (el, c) => {
    const left = grid.offsetLeft + ui.drawn.cv.offsetLeft - grid.scrollLeft, canvasTop = grid.offsetTop + ui.drawn.cv.offsetTop;
    const cx = left + (c.x + TILE / 2) * ui.k, room = ui.drawn.cv.getBoundingClientRect().top + (c.y - 1) * ui.k - el.offsetHeight - TIP_GAP;
    el.style.left = Math.min(box.clientWidth - el.offsetWidth, Math.max(0, cx - el.offsetWidth / 2)) + 'px';
    el.style.top = (room < 0 ? canvasTop + (c.y + TILE + 1) * ui.k + TIP_GAP : canvasTop + (c.y - 1) * ui.k - el.offsetHeight - TIP_GAP) + 'px';
  };
  const placePin = () => {
    const c = ui.editing && ui.drawn.cells.find(x => x.o === ui.editing.o);
    if (c) placeOver(pin, c);
  };
  const closePin = keep => {
    if (!ui.editing) return;
    const { o, ms, before } = ui.editing, m = H.marked.get(o);
    ui.editing = null;
    pin.hidden = true;
    ui.ring(null);
    send(`${data.channel}:typing:0`);
    if (!keep) {  // (back as it was)
      if (before) H.marked.set(o, before); else H.marked.delete(o);
    } else if (m) {
      m.name = pinName.value.trim().replace(/\s+/g, ' ');
      if (!before || before.icon !== m.icon || before.name !== m.name) send(`${data.channel}:mark:${iso(ms)}:${m.icon}:${m.name}`);
    } else if (before) send(`${data.channel}:unmark:${iso(ms)}`);
    keepMarks();
    ui.draw();
  };
  grid.addEventListener('contextmenu', e => {
    const c = ui.cellAt(e);
    // (on the phone there is no add-on to keep the mark; an earlier year's day is not marked from here)
    if (!c || !data.inAnki || ui.pointed !== ui.drawn) return;
    e.preventDefault();
    if (ui.editing) closePin(true);
    ui.unpick();  // (a mark is one day's: the days selected go, as a click on another day lets them go, not left dimming the day being marked)
    const before = H.marked.get(c.o);
    ui.editing = { o: c.o, ms: c.ms, before: before ? Object.assign({}, before) : null };
    if (!before) H.marked.set(c.o, { icon: MARK_ORDER[0], name: '' });
    ui.unpoint();
    ui.draw();
    ui.ring(null);
    const m = H.marked.get(c.o);
    showIcon(m);
    pinName.value = m.name;
    pin.hidden = false;
    placePin();
    send(`${data.channel}:typing:1`);  // (Anki's one-key shortcuts wait while a name is typed)
    pinName.focus();
  });
  pin.querySelector('.af-cal-pin-del').addEventListener('mousedown', e => e.preventDefault());
  pin.querySelector('.af-cal-pin-del').addEventListener('click', () => { if (ui.editing) { H.marked.delete(ui.editing.o); closePin(true); } });
  // (by the keyboard: Enter keeps it from anywhere in it but ×, Esc puts it back; the icons a radio
  // group, one tab stop, ← → moving the choice)
  pin.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.target.classList.contains('af-cal-pin-del')) { e.preventDefault(); closePin(true); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closePin(false); }
    else if (e.target.parentNode === pinIcons && /^Arrow/.test(e.key)) {
      e.preventDefault();
      const all = [...pinIcons.children], d = ui.arrowStep(e.key) || 1, to = all[(all.indexOf(e.target) + d + all.length) % all.length];
      to.focus(); to.click();
    }
  });
  // (closed as the focus leaves it, not as it moves from the name to an icon or ×)
  pin.addEventListener('focusout', e => { if (!pin.contains(e.relatedTarget)) closePin(true); });
  Object.assign(ui, { placePin });
};

Object.assign(Cal, { markOf, markName, markLine, markPalOf });
})();

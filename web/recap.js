/* Memory Forest — your year in the forest (recap.py): from Dec 7 to Jan 15, a
 * card on the deck list's forest (or, once answered, a link in its caption) opens a look back at the year,
 * a few cards over the deck list, one at a time: the year and its forest; the days studied, the year's
 * heatmap filling in day by day; the year's bests; the animals it brought walking in; a word for its
 * rhythm; and the summary, a picture of the year to save (1080 x 1350: the forest, the numbers, the
 * heatmap, the bests). A year of fewer than recap.SHORT_UNDER days studied has the first and the last alone.
 *
 * Everything is the add-on's own drawing: one forest mounted for the cards that show it (the deck list's
 * forest, its trees and animals), and the year's heatmap mounted twice out of sight (with its days, and
 * with none), drawn again by its own sharpen() at each size (calendar/draw.js keeps the drawn view on its
 * box: afDrawn). Only in Anki, on the deck list (data.recap). Its words are the page's (AF.t). */
(function () {
'use strict';
const AF = window.AnkiForest;
const { esc, send, onTheme } = AF.u;

const W = 1080, H = 1350, M = 90, CW = 900;  // the summary picture, its margin and its content's width
const BOTTOM = 72;  // (the name's line, this far over the picture's foot)
const DLG_W = 820, DLG_H = 588;  // the dialog, at its full size (smaller windows shrink it: fit)
const FOREST_W = 600;  // (the forest's width in the dialog: 300 of its pixels, twice over; three times on the picture's 900)
const HEAT_W = 740;
const STEP_MS = 800, FIRST_MS = 600, ALL_IN_MS = 5600, CHIPS_MOST = 10;  // the animals: one after another (many: all in by ALL_IN_MS)
const stepFor = n => Math.min(STEP_MS, Math.max(250, (ALL_IN_MS - FIRST_MS) / Math.max(1, n)));
const WHOLE_NEAR = 0.9;  // (a drawn-once heatmap style kept at whole pixels when that's at least this share of the size asked for)
const AWAY_STEP = 1 / 3;  // (the fill: a day not studied, against a day studied)
const LAND_MS = 500;  // (the streak's bracket, coming in)
const DOUBLE_MS = 500;  // (a click this soon after it opened is the second of a double click)
const SAVE_AGAIN_MS = 1000;  // (a second click on Save image this soon is the same one)

const num = n => AF.i18n.num(Math.round(n));
const msOf = iso => Date.parse(iso + 'T00:00:00Z');
const shortDate = iso => AF.i18n.dayIn(iso, { month: 'short', day: 'numeric' });
const longDate = iso => AF.i18n.dayIn(iso, { weekday: 'short', month: 'short', day: 'numeric' });
const monthLong = m => AF.i18n.monthName(m, 'long');
const ease = q => 1 - Math.pow(1 - Math.max(0, Math.min(1, q)), 3);
const cssVar = name => window.getComputedStyle(document.body).getPropertyValue(name).trim();

/* a wording with its number set big: the number in a span of its own where the text has it (a
 * language that writes the number as a word, Hebrew's "יום אחד", gets the whole line big) */
function withBig(text, n, wide) {
  const at = text.indexOf(num(n)), e = esc(text);
  if (at < 0) return `<span class="af-recap-num">${e}</span>`;
  // (`wide`: the final number's width, which a count kept from the start, so the line it stands in
  // stays put as the digits grow: centred, "9" to "10" to "100" moved the whole line each time)
  const w = wide ? ` style="min-width: ${wide}px"` : '';
  return esc(text.slice(0, at)) + `<span class="af-recap-num"${w}>${esc(num(n))}</span>` + esc(text.slice(at + num(n).length));
}
/* the width the number of `html` (a withBig) takes in `el` */
function bigWidth(el, html) {
  el.innerHTML = html;
  const s = el.querySelector('.af-recap-num');
  return s ? Math.ceil(s.getBoundingClientRect().width / ((el.getBoundingClientRect().width / el.offsetWidth) || 1)) : 0;
}
const timeIn = s => (s >= 90 * 60 ? AF.tn('recap.n_hours', Math.round(s / 3600)) : AF.tn('recap.n_minutes', s > 0 ? Math.max(1, Math.round(s / 60)) : 0));

/* the forest's front animals walking in (web/visitors.js asks this for each of them, each frame): from
 * the scene's nearer edge to its own spot, legs keeping step with the ground covered, in WALK_S
 * seconds at most (a far spot is a brisker walk, never a 15 second one); out of sight until it sets
 * off. One far slower than the rest (the snail) is just there when its time comes, rather than
 * racing in. Only the recap's forest has `recapWalk`. */
const WALK_S = [1.2, 2.8];
AF.recapWalk = function (env, v, x, t) {
  const w = env.data.recapWalk && env.data.recapWalk[v.key];
  if (!w) return null;
  if (t < w.at) return { hide: true };
  if (((AF.VISITOR_SPRITES || {})[v.key] || {}).speed < 0.3) return null;
  const from = x > env.W / 2 ? env.W + 10 : -10, d = Math.abs(x - from);
  const dur = Math.min(WALK_S[1], Math.max(WALK_S[0], d / (21 * env.u))), q = (t - w.at) / dur;
  if (q >= 1) return null;
  return { x: from + (x - from) * q, gone: d * q, dir: x >= from ? 1 : -1 };
};

/* ---------- the way in: a card on the forest, then a link in its caption ---------- */
AF.recap = function (root, data) {
  // (the forest swapped in place under an open look back, panel.refresh: a new weather, a setting, gave
  // Anki its one-key shortcuts back; s would start a review behind it)
  // (the deck list's page alone has data.recap, even null: not the recap's own heatmaps, mounted as it opens)
  if (current && data.inAnki && data.recap !== undefined) send(`${data.channel}:typing:1`);
  const R = data.recap;
  if (!R || !data.inAnki || data.deckId) return;
  const scene = root.querySelector('.af-scene');
  const link = () => {
    // (a line of its own, right under the caption's: in the caption's own line it ran on after the weather's credit)
    const caption = scene && root.querySelector('.af-caption');
    let meta = caption ? root.querySelector('.af-recap-row') : null;
    if (caption && !meta) {
      meta = document.createElement('div'); meta.className = 'af-recap-row'; meta.dir = 'auto';
      caption.parentNode.insertBefore(meta, caption.nextSibling);
    }
    // (the forest switched off on the deck list, the heatmap alone: in its footer, where the journal
    // goes, under its first week; put first, before the heatmap was drawn, it stood over it at the
    // panel's edge. A line of its own under the panel only if there is no heatmap after all)
    if (!meta && !scene) meta = root.querySelector('.af-cal-foot .af-cal-journal');
    if (!meta && !scene) {
      meta = root.querySelector('.af-recap-foot');
      if (!meta) { meta = document.createElement('div'); meta.className = 'af-recap-foot'; meta.dir = 'auto'; root.appendChild(meta); }
    }
    if (!meta || meta.querySelector('.af-recap-link')) return;
    const a = document.createElement('button');
    a.type = 'button'; a.className = 'af-recap-link';
    a.textContent = AF.t('recap.card_title', { year: R.year });
    a.addEventListener('click', () => open(root, data));
    if (meta.childNodes.length) meta.append(' · ');
    meta.append(a);
  };
  // (the forest's corner is the recap's first while it is offered: a note of what's new waits till it's
  // answered, web/news.js; with no forest on the page, its link under the heatmap)
  if (R.entry === 'card' && scene) {
    const card = document.createElement('div');
    card.className = 'af-news af-recap-entry';  // (not af-recap-card: the dialog's cards, hidden till their turn)
    card.innerHTML = `<div class="af-news-body" dir="auto"><b>${esc(AF.t('recap.card_title', { year: R.year }))}</b>${esc(R.animals.length ? AF.t('recap.card_text') : AF.t('recap.card_text_no_animals'))}</div>`
      + `<div class="af-news-acts"><button type="button" data-recap="open">${esc(AF.t('recap.open'))}</button>`
      + `<button type="button" data-recap="later">${esc(AF.t('recap.not_now'))}</button></div>`;
    card.addEventListener('click', e => {
      const b = e.target.closest('[data-recap]');
      if (!b) return;
      card.remove();
      if (b.dataset.recap === 'open') open(root, data);
      else send(`${data.channel}:recap:dismissed:${R.year}${R.early ? ':early' : ''}`);
      link();
      // (a note of what's new that waited behind it has the corner now, web/news.js)
      if (AF.newsNote) AF.newsNote(root, data);
    });
    (root.afTipLayer || scene).append(card);
    if (AF.cornerClear) AF.cornerClear(root, card);  // (Background, a narrow window: not over the deck list, web/news.js)
  } else if (R.entry !== 'none') link();
};

/* ---------- the dialog ---------- */
let current = null;  // the open recap, if any

/* Anki saved the picture (recap_actions.save): its button says so, the file's name under it */
AF.recapSaved = function (name) {
  const b = current && current.box.querySelector('.af-recap-save');
  if (!b) return;
  // (null: it couldn't be saved, Anki's tooltip says so; an earlier "Picture saved" and its name taken back)
  if (name === null) { b.textContent = AF.t('recap.save_image'); const old = current.box.querySelector('.af-recap-file'); if (old) old.remove(); return; }
  b.textContent = AF.t('recap.saved');
  let f = current.box.querySelector('.af-recap-file');
  if (!f) { f = document.createElement('p'); f.className = 'af-recap-file'; f.dir = 'auto'; b.parentNode.parentNode.appendChild(f); }
  f.textContent = name;
};

function open(root, data) {
  if (current) return;
  const R = data.recap, rtl = AF.i18n.rtl();
  // (the Debug tab's open answers nothing: the year's card still shows on its days, as it will for everyone)
  send(`${data.channel}:recap:opened:${R.year}${R.early ? ':early' : ''}`);
  send(`${data.channel}:typing:1`);  // (Anki's one-key shortcuts wait while it is open: actions.hold_shortcuts)
  style();
  const order = R.short ? ['title', 'summary'] : ['title', 'days', 'best'].concat(R.animals.length ? ['animals'] : []).concat(['label', 'summary']);
  const box = document.createElement('div');
  box.className = 'af-recap' + (rtl ? ' af-rtl' : '');
  box.setAttribute('dir', rtl ? 'rtl' : 'ltr');
  box.innerHTML = '<div class="af-recap-scrim"></div>'
    + `<div class="af-recap-dlg" role="dialog" aria-modal="true" tabindex="-1" aria-label="${esc(AF.t('recap.your_year_in_the_forest'))}">`
    + `<div class="af-recap-top"><div class="af-recap-bars">${order.map(() => '<i><b></b></i>').join('')}</div>`
    + `<button type="button" class="af-recap-skip">${esc(AF.t('recap.skip'))}</button>`
    + `<button type="button" class="af-recap-x" aria-label="${esc(AF.t('recap.close'))}" title="${esc(AF.t('recap.close'))}">×</button></div>`
    + '<div class="af-recap-body"><div class="af-recap-forest"><div class="af-panel"></div></div>'
    + order.map(k => `<section class="af-recap-card af-recap-${k}" data-card="${k}"></section>`).join('')
    + '<div class="af-recap-back" aria-hidden="true"></div></div></div>'
    + '<div class="af-recap-out" aria-hidden="true"><div class="af-panel" data-cal="full"></div><div class="af-panel" data-cal="empty"></div></div>';
  document.body.append(box);
  const dlg = box.querySelector('.af-recap-dlg'), q = sel => box.querySelector(sel);
  // (it always moves, the forest too: opened by a click, once a year, it plays as made, whatever the
  // forest's own Motion setting; Skip to summary is there for anyone who'd rather not watch)
  const S = current = { root, data, R, box, dlg, order, at: -1, run: 0, rtl, timers: [], heat: {}, stop: [], since: performance.now(), back: document.activeElement };

  // the forest: the deck list's, with this year's animals held back until their card
  const yearKeys = {};
  R.animals.forEach(a => { yearKeys[a.key] = a; });
  const mine = data.visitors || [];
  S.before = mine.filter(v => !yearKeys[v.key]);
  S.arriving = mine.filter(v => yearKeys[v.key]);
  // (every animal out, none of the day's few chosen: the year's newcomers would take the front line
  // from the forest's own when they came. The front's newcomers are in it from the start, out of
  // sight until their walk, so no one moves over for them)
  S.walkers = S.arriving.filter(v => walksIn(data, v.key));
  S.forestRoot = q('.af-recap-forest .af-panel');
  S.fdata = Object.assign({}, data, {
    animations: true, showForest: true, calendar: null, news: null, recap: null, newDot: '', journal: '', inAnki: false, maxWidth: FOREST_W, zoom: false,
    tooltips: false, layout: undefined, strike: null, visitors: S.before.concat(S.walkers), recapWalk: held(S), deckId: null, allVisitors: true
  });
  AF.mount(S.forestRoot, S.fdata, { now: true });
  // the year's heatmap, twice, out of sight: with its days, and with none (the days not yet filled in)
  const calData = cal => ({ calendar: cal, showForest: false, inAnki: true, maxWidth: HEAT_W, mood: data.mood, trees: [], stats: data.stats,
    animations: false, channel: data.channel, i18n: data.i18n, journal: '', events: [] });
  // (no today's frame: the year's last day, which isn't today in January, ringed ahead of the fill;
  // and a day of nothing due for it: with no days ahead (due: []) the heatmap counts none ahead
  // of the day before it, and left the year's last day studied blank, under its streak's bracket)
  // (and the gold bracket the year's best streak's, as its bests say, not the one still going on its last day)
  const best = R.bestStreak && R.bestStreak[0] >= 2 ? R.bestStreak.slice(1) : null;
  const year = Object.assign({}, R.calendar, { noToday: true, due: [0], goldRun: best });
  const blank = Object.assign({}, year, { days: R.calendar.days.map(() => 0) });
  S.calFull = q('[data-cal="full"]'); S.calEmpty = q('[data-cal="empty"]');
  AF.mount(S.calFull, calData(year));
  AF.mount(S.calEmpty, calData(blank));

  fill(S);
  fit(S);
  scrim(S);
  const onResize = () => fit(S);
  window.addEventListener('resize', onResize);
  S.stop.push(() => window.removeEventListener('resize', onResize));
  // Anki's theme switched: the heatmap's copies drawn again from its own (which repaints itself)
  S.stop.push(onTheme(() => { S.heat = {}; scrim(S); if (S.at >= 0) redrawStill(S); }));
  const keys = e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'Tab') {  // (round its own buttons in view: never off to the deck list under the scrim)
      const all = [].filter.call(dlg.querySelectorAll('button'), b => b.offsetParent && window.getComputedStyle(b).visibility === 'visible');
      const n = all.length, i = all.indexOf(document.activeElement);
      if (n) all[i < 0 ? (e.shiftKey ? n - 1 : 0) : (i + (e.shiftKey ? -1 : 1) + n) % n].focus();
      e.preventDefault(); e.stopPropagation();
      return;
    }
    const next = S.rtl ? 'ArrowLeft' : 'ArrowRight', back = S.rtl ? 'ArrowRight' : 'ArrowLeft';
    if (e.key === next) go(S, S.at + 1);
    else if (e.key === back) go(S, S.at - 1);
    else if (e.key === 'Escape' || e.key === 'Esc') close(S);
    else return;
    e.preventDefault(); e.stopPropagation();
  };
  document.addEventListener('keydown', keys, true);
  S.stop.push(() => document.removeEventListener('keydown', keys, true));
  q('.af-recap-x').addEventListener('click', e => { e.stopPropagation(); close(S); });
  q('.af-recap-skip').addEventListener('click', e => { e.stopPropagation(); go(S, order.length - 1); });
  // (a double click on Open or the caption's link: its second click lands on what just opened, and
  // closed it again, or went on past the title)
  const settled = () => performance.now() - S.since > DOUBLE_MS;
  q('.af-recap-scrim').addEventListener('click', () => { if (settled()) close(S); });
  q('.af-recap-body').addEventListener('click', e => {
    if (e.target.closest('button') || !settled()) return;
    // (its left third back, by where the click is: the finished decks' line and the chips, which take
    // the pointer for their tooltips, lie over the back strip)
    const r = e.currentTarget.getBoundingClientRect(), x = (e.clientX - r.left) / (r.width || 1);
    go(S, S.at + (S.at > 0 && (S.rtl ? x > 0.7 : x < 0.3) ? -1 : 1));  // (the first card: on, anywhere)
  });
  dlg.focus();
  go(S, 0);
}

function close(S) {
  S.run++;
  S.timers.forEach(clearTimeout); window.clearInterval(S.preview);
  S.stop.forEach(f => f());
  // (the forest drawn here stops drawing: a mount on the same root retires the one before it, and
  // so does a token of its own; the heatmaps stop watching the page)
  S.forestRoot.afToken = {};
  [S.calFull, S.calEmpty].forEach(r => { if (r.afCalStop) r.afCalStop(); r.afToken = {}; });
  S.box.remove();
  // (the keys' place back where they were: the caption's link, the card's Open having gone with it)
  const to = S.root.querySelector('.af-recap-link') || S.back;
  if (to && to.isConnected && to.focus) to.focus();
  send(`${S.data.channel}:typing:0`);
  current = null;
}

/* the dialog at its own size where the window has room, smaller where it hasn't */
function fit(S) {
  // (12px of room round it, not 24: in a 700px Anki window the deck list is about 600px tall, and
  // a 0.98 scale blurred every word and the forest's pixels for 12px)
  let k = Math.min(1, (window.innerWidth - 12) / DLG_W, (window.innerHeight - 12) / DLG_H);
  // (a forest's pixel is two css px: on a screen of 2 or more device px to one, smaller in steps
  // that keep it whole device px, so its trees don't come out with uneven pixels, 0.84 in a
  // 860 x 620 window; on a 1x screen the step would halve it, so it shrinks as it must)
  const step = 1 / (2 * (window.devicePixelRatio || 1));
  if (k < 1 && (window.devicePixelRatio || 1) >= 2 && Math.floor(k / step) * step >= 0.5) k = Math.floor(k / step) * step;
  S.dlg.style.transform = k < 1 ? `translate(-50%, -50%) scale(${Math.max(0.4, k)})` : '';
}

/* the scrim over the deck list: half black on a dark page; on a light one a third, half of it
 * turned Anki's light page a dull mid grey round the dialog */
function scrim(S) {
  const m = /(\d+)\D+(\d+)\D+(\d+)/.exec(window.getComputedStyle(document.body).backgroundColor) || [0, 0, 0, 0];
  const light = 0.299 * m[1] + 0.587 * m[2] + 0.114 * m[3] > 140;
  S.box.querySelector('.af-recap-scrim').style.background = light ? 'rgba(0, 0, 0, 0.32)' : '';
  // (an old Anki has no --canvas: the dialog in the page's own colour, not a light grey round a dark picture)
  const page = cssVar('--canvas') ? null : AF.u.pageBg([document.body, document.documentElement]) || AF.u.appBg();
  S.dlg.style.background = page ? `rgb(${page.join(', ')})` : '';
  // (nor --fg: the words in the page's own colour, not the stylesheet's near black, on its dark grey)
  const fg = cssVar('--fg') ? '' : window.getComputedStyle(document.body).color;
  S.dlg.style.setProperty('--fg', fg);
  S.dlg.style.setProperty('--fg-subtle', fg && !cssVar('--fg-subtle') ? fg.replace(/rgba?\(([^,]+),([^,]+),([^,)]+).*/, 'rgba($1,$2,$3, 0.62)') : '');
}

/* each card's words, once */
function fill(S) {
  const R = S.R, q = k => S.box.querySelector(`.af-recap-${k}`);
  const card = (k, html) => { const c = q(k); if (c) c.innerHTML = html; };
  card('title', `<p class="af-recap-kick">${esc(AF.t('recap.your_year_in_the_forest'))}</p><p class="af-recap-year">${esc(String(R.year))}</p>`
    + `<p class="af-recap-under">${esc(AF.tn('caption.n_trees', R.trees))} · ${esc(AF.tn('recap.n_new_cards', R.newCards))}</p>`
    + `<p class="af-recap-hint">${esc(AF.t('recap.hint'))}</p>`);
  card('days', '<p class="af-recap-big" data-big="days"></p><canvas class="af-recap-heat"></canvas><p class="af-recap-sub" data-big="reviews"></p>');
  const stats = [];
  if (R.bestStreak && R.bestStreak[0] >= 2) {
    stats.push(['streak', AF.t('recap.best_streak'), AF.t('recap.from_to', { first: shortDate(R.bestStreak[1]), last: shortDate(R.bestStreak[2]) })]);
  }
  if (R.bestMonth) stats.push(['month', AF.t('recap.best_month'), '']);
  if (R.bestDay) stats.push(['day', AF.t('recap.best_day'), longDate(R.bestDay[0])]);
  card('best', `<p class="af-recap-kick">${esc(AF.t('recap.your_best_of_year', { year: R.year }))}</p><div class="af-recap-trio">`
    + stats.map(([k, what, when]) => `<div class="af-recap-stat" data-stat="${k}"><p class="af-recap-v"></p><p class="af-recap-what">${esc(what)}</p><p class="af-recap-when">${esc(when)}</p></div>`).join('')
    + '</div>' + finishedLine(R));
  // (two rows of them at most: past CHIPS_MOST, the last chip counts the rest)
  const many = R.animals.length > CHIPS_MOST, chipped = many ? R.animals.slice(0, CHIPS_MOST - 1) : R.animals;
  card('animals', '<p class="af-recap-big" data-big="animals"></p><div class="af-recap-chips">'
    + chipped.map(a => `<span class="af-recap-chip" data-key="${esc(a.key)}" title="${esc(a.came || '')}"><canvas></canvas>${esc(a.name)}<span class="af-recap-when">${esc(shortDate(a.date))}</span></span>`).join('')
    + (many ? `<span class="af-recap-chip af-recap-more">${esc(AF.tn('recap.n_more', R.animals.length - chipped.length))}</span>` : '')
    + '</div>');
  S.box.querySelectorAll('.af-recap-chip[data-key]').forEach(c => sprite(c.querySelector('canvas'), c.dataset.key));
  const L = R.label && LABELS[R.label.key] ? R.label : { key: 'quiet' }, [title, line, lineOne] = LABELS[L.key];
  const v = { month: L.month != null ? monthLong(L.month) : '', date: L.date ? AF.i18n.dayIn(L.date, { month: 'long', day: 'numeric' }) : '' };
  card('label', `<p class="af-recap-kick">${esc(AF.t('recap.your_rhythm'))}</p><p class="af-recap-title">${esc(AF.tx(title))}</p>`
    + `<p class="af-recap-line">${esc(L.key === 'season' && L.days ? AF.tn('recap.label_season_line_days', L.days, v) : AF.tx(lineOne && L.days === 1 ? lineOne : line, v))}</p>`);
  card('summary', '<canvas class="af-recap-share" width="1080" height="1350"></canvas><div class="af-recap-side">'
    // (in December, the year so far: "That was your 2026" with two weeks of it left was not so)
    + `<p class="af-recap-kick2">${esc((R.early ? AF.t('recap.your_year_so_far', { year: R.year }) : AF.t('recap.that_was_your_year', { year: R.year })))}</p><p class="af-recap-say">${esc(AF.t('recap.share_say'))}</p>`
    + `<div class="af-recap-acts"><button type="button" class="af-recap-save">${esc(AF.t('recap.save_image'))}</button>`
    + `<button type="button" class="af-recap-again">${esc(AF.t('recap.watch_again'))}</button></div></div>`);
  const save = S.box.querySelector('.af-recap-save');
  // (as wide as the wider of its two wordings: "Picture saved" pushed Watch again 15px along)
  if (save) S.fitSave = () => {
    if (!save.offsetWidth) return;
    const was = save.textContent; save.style.minWidth = '';
    const a = save.offsetWidth; save.textContent = AF.t('recap.saved');
    const b = save.offsetWidth; save.textContent = was;
    save.style.minWidth = Math.max(a, b) + 'px';
  };
  // (drawn again on the summary's own canvas, in the dialog: a canvas out of the page writes left to right,
  // and Hebrew's "1,032 חזרות" came out "חזרות 1,032" in the file while the preview had it right)
  // (a double click on it opened Anki's save dialog twice, one after the other)
  if (save) save.addEventListener('click', e => { e.stopPropagation(); if (performance.now() - (S.savedAt || -1e9) < SAVE_AGAIN_MS) return; S.savedAt = performance.now(); send(`${S.data.channel}:recap:save:${R.year}:${picture(S, S.box.querySelector('.af-recap-share')).toDataURL('image/png')}`); });
  const again = S.box.querySelector('.af-recap-again');
  if (again) again.addEventListener('click', e => { e.stopPropagation(); go(S, 0); });
}

/* the decks learned to their last card that year, under the bests (recap.finished): their own names,
 * three at most, the rest counted ("and 4 more": the chips' "+4 more" read as a fourth deck's name in
 * a sentence); nothing when there were none. Never on the picture: no deck names there */
function finishedLine(R) {
  // (a name two of them share, as Japanese::Vocab and German::Vocab do, with its parent's: "Vocab, Vocab")
  const F = (R.finished || []).map((f, i, all) => (all.some((g, j) => j !== i && g.name === f.name)
    ? Object.assign({}, f, { name: (f.full || f.name).split('::').slice(-2).join('::') }) : f));
  if (!F.length) return '';
  // (each name, and the count of the rest, isolated in its own direction, and the list in the page's: the
  // words set it apart as one piece (AF.t's isolates) whose direction its first name decides, so in Hebrew
  // a list opening on "German A1" ran left to right, its order turned round, "and one more" first)
  const own = s => '\u2068' + s + '\u2069';
  // (four: the fourth's own name, in the room "and 1 more" took)
  const shown = F.length === 4 ? 4 : 3;
  // (past that, the biggest by name, in the year's order, the rest counted: the year's first few were
  // often its smallest, a 2,000-card deck left among "and 5 more")
  const big = F.length > shown ? F.slice().sort((a, b) => (b.cards || 0) - (a.cards || 0)).slice(0, shown) : F;
  // (the rest's count after a space, not the list's comma: "A, B, C and 4 more", German's "C und 4 weitere")
  const rest = F.length > shown ? ' ' + own(AF.tn('recap.and_n_more', F.length - shown)) : '';
  const names = F.filter(f => big.indexOf(f) >= 0).map(f => own(f.name)).join(AF.t('recap.list_sep')) + rest;
  const text = F.length === 1 ? AF.t('recap.finished_one', { deck: F[0].name })
    : AF.tn('recap.finished_many', F.length, { decks: (AF.i18n.rtl() ? '\u2067' : '\u2066') + names + '\u2069' });
  return `<p class="af-recap-fin" dir="auto" title="${esc(F.map(f => f.full).join('\n'))}">${esc(text)}</p>`;
}

/* the year's rhythm in a word (recap.label): its title, its line, and the line for a single day */
const LABELS = {
  comeback: [AF.N_('recap.label_comeback'), AF.N_('recap.label_comeback_line')],
  new: [AF.N_('recap.label_new'), AF.N_('recap.label_new_line'), AF.N_('recap.label_new_line_one')],
  steady: [AF.N_('recap.label_steady'), AF.N_('recap.label_steady_line')],
  weekly: [AF.N_('recap.label_weekly'), AF.N_('recap.label_weekly_line')],
  season: [AF.N_('recap.label_season'), AF.N_('recap.label_season_line')],
  patient: [AF.N_('recap.label_patient'), AF.N_('recap.label_patient_line')],
  quiet: [AF.N_('recap.label_quiet'), AF.N_('recap.label_quiet_line')]
};

/* an animal's own sprite (web/visitors.js), its first frame, whole pixels: two css px each, as the
 * dialog's forest draws it (one for the tallest and the widest, which would outgrow the chip) */
function sprite(cv, key) {
  const s = (AF.VISITOR_SPRITES || {})[key];
  if (!s) { cv.remove(); return; }
  const rows = s.frames[0], h = rows.length, w = Math.max.apply(null, rows.map(r => r.length));
  const k = h * 2 <= 22 && w * 2 <= 72 ? 2 : 1;
  cv.width = w * k; cv.height = h * k; cv.style.width = w * k + 'px'; cv.style.height = h * k + 'px';
  const g = cv.getContext('2d');
  rows.forEach((r, y) => { for (let x = 0; x < r.length; x++) { const c = s.pal[r[x]]; if (c) { g.fillStyle = c; g.fillRect(x * k, y * k, k, k); } } });
}

/* ---------- moving between the cards ---------- */
const FOREST_ON = { title: 1, animals: 1, label: 1 };

function go(S, i) {
  if (i < 0 || i >= S.order.length || !S.box.isConnected) return;
  S.run++;
  S.timers.forEach(clearTimeout); S.timers = [];
  window.clearInterval(S.preview);
  const was = S.order[S.at], k = S.order[i];
  S.at = i;
  // the year's animals: held back before their card; all of them in from there on
  const before = S.order.indexOf('animals');
  if (before >= 0 && i < before && was && S.order.indexOf(was) >= before) arrive(S, false);
  if (before >= 0 && i > before && (!S.arrived || S.fdata.visitors.length < S.before.length + S.arriving.length)) arrive(S, 'all');
  S.box.querySelectorAll('.af-recap-card').forEach(c => c.classList.toggle('af-recap-on', c.dataset.card === k));
  S.box.querySelector('.af-recap-forest').classList.toggle('af-recap-on', !!FOREST_ON[k]);
  S.box.classList.toggle('af-recap-at-end', i === S.order.length - 1);  // (nothing past the summary: no hand over it)
  // (none on the summary, nor just before it, where the next card is the summary: a short year's title)
  S.box.querySelector('.af-recap-skip').hidden = i >= S.order.length - 2;
  bars(S, 0);
  PLAY[k](S);
}

function bars(S, q) {
  const bs = S.box.querySelectorAll('.af-recap-bars b');
  for (let i = 0; i < bs.length; i++) bs[i].style.width = (i < S.at ? 100 : i === S.at ? Math.round(100 * Math.max(0, Math.min(1, q))) : 0) + '%';
}

/* `step(q)` for q from 0 to 1 over `ms`, then `done`; at once with no motion */
function play(S, ms, step, done) {
  const run = S.run, t0 = performance.now();
  const tick = () => {
    if (run !== S.run) return;
    const q = Math.min(1, (performance.now() - t0) / ms);
    step(q); bars(S, q);
    if (q < 1) requestAnimationFrame(tick); else if (done) done();
  };
  requestAnimationFrame(tick);
}
const later = (S, ms, f) => { const run = S.run; S.timers.push(setTimeout(() => { if (run === S.run) f(); }, ms)); };

/* the year's animals: back out (`false`: the front's newcomers there, out of sight), all in at once
 * ('all': the walks under way go on), or in one by one (true): the front ones walking in from the
 * scene's edge, the others (in a tree, on the water, on the cabin), which have no walk to hold them
 * back, each put in with its chip (a rebuild each) */
function arrive(S, how) {
  const d = S.fdata, rebuild = () => { if (S.forestRoot.afRebuild) S.forestRoot.afRebuild(); };
  S.arrived = !!how;
  if (!how) { d.visitors = S.before.concat(S.walkers); d.recapWalk = held(S); }
  else if (how === 'all') {
    d.visitors = S.before.concat(S.arriving);
    Object.keys(d.recapWalk).forEach(k => { if (d.recapWalk[k].at === Infinity) delete d.recapWalk[k]; });
  } else {
    const now = performance.now() / 1000, keys = S.R.animals.map(a => a.key), step = stepFor(keys.length);
    const at = v => FIRST_MS + Math.max(0, keys.indexOf(v.key)) * step;
    d.visitors = S.before.concat(S.walkers);
    d.recapWalk = {};
    S.walkers.forEach(v => { d.recapWalk[v.key] = { at: now + at(v) / 1000 }; });
    S.arriving.filter(v => S.walkers.indexOf(v) < 0).forEach(v => later(S, at(v), () => { d.visitors = d.visitors.concat([v]); rebuild(); }));
  }
  rebuild();
}
/* whether an animal walks in: one of the front line's (web/visitors.js), not the stork nesting on the cabin
 * (without AF.visitorPlace, the first ten animals' own places: those living in the forest don't walk) */
const OWN_PLACE = { deer: 'grazing', stag: 'grazing', owl: 'trees', heron: 'water', squirrel: 'feet', eagle: 'sky', cabin: 'home' };
const placeOf = key => (AF.visitorPlace ? AF.visitorPlace(key) : OWN_PLACE[key] || 'front');
const walksIn = (data, key) => placeOf(key) === 'front'
  && !(key === 'stork' && (data.visitors || []).some(v => v.key === 'cabin'));
/* the front's newcomers, there but out of sight */
const held = S => { const w = {}; S.walkers.forEach(v => { w[v.key] = { at: Infinity }; }); return w; };

const PLAY = {
  title(S) { play(S, 1200, () => {}); },
  days(S) {
    const R = S.R, big = S.box.querySelector('[data-big="days"]'), sub = S.box.querySelector('[data-big="reviews"]');
    const wide = bigWidth(big, withBig(AF.tn('recap.n_days_studied', R.studied), R.studied));
    // (the reviews and the time count up together with the fill, the time in step with the reviews:
    // the year's whole time beside a count still climbing read "1,204 reviews in 191 hours")
    const say = reviews => AF.tn('recap.n_reviews_in_time', reviews, { time: timeIn(R.reviews ? R.seconds * reviews / R.reviews : R.seconds) });
    // (held at the finished line's width and started from its first letter, so it doesn't slide as it grows)
    sub.innerHTML = `<span class="af-recap-subline">${esc(say(R.reviews))}</span>`;
    const subW = Math.ceil(sub.firstChild.getBoundingClientRect().width / ((sub.getBoundingClientRect().width / sub.offsetWidth) || 1));
    // (unseen till the first day fills in: "0 reviews in 0 minutes" stood there through the card's first half second)
    const line = reviews => { sub.innerHTML = `<span class="af-recap-subline" style="min-width: ${subW}px">${esc(say(reviews))}</span>`; sub.style.opacity = reviews ? '' : '0'; };
    const show = (n, reviews) => { big.innerHTML = withBig(AF.tn('recap.n_days_studied', n), n, wide); line(reviews); };
    const h = heatFor(S, HEAT_W);
    if (!h) { show(R.studied, R.reviews); bars(S, 1); return; }
    const cv = S.box.querySelector('.af-recap-heat');
    const from = msOf(R.first || R.calendar.start);
    const cells = h.cells.filter(c => c.o <= 0 && c.ms >= from).sort((a, b) => a.o - b.o);
    let shown = 0, studied = 0, reviews = 0;
    heatTo(cv, h, S, cells.slice(0, 0));
    sub.style.transition = 'none';  // (hidden at once, not faded out as the card comes in)
    show(0, 0);
    void sub.offsetWidth; sub.style.transition = '';
    // (its pace: a day studied a step, a day away a third of one, so the count never stalls over
    // the weeks away, March's empty months took a second and a half of nothing)
    const acc = [];
    cells.reduce((a, c, i) => (acc[i] = a + (c.n ? 1 : AWAY_STEP)), 0);
    const total = acc.length ? acc[acc.length - 1] : 0;
    // (the heatmap asked for again each frame: Anki's theme switched halfway, it goes on in the new colours)
    const now = () => heatFor(S, HEAT_W) || h;
    later(S, 350, () => play(S, Math.max(1400, Math.min(4400, total * 13)), q => {
      let upto = shown;
      while (upto < cells.length && acc[upto] <= q * total + 1e-9) upto++;
      for (; shown < upto; shown++) { const c = cells[shown]; if (c.n) { studied++; reviews += c.n; } }
      heatTo(cv, now(), S, cells.slice(0, shown));
      show(studied, reviews);
    }, () => {
      show(R.studied, R.reviews);
      // (the streaks' brackets and their lengths come in over the filled year, not all at once; the
      // trophies are the heatmap's hover layer's, never on these copies)
      const run = S.run, t0 = performance.now();
      const land = () => {
        if (run !== S.run) return;
        const a = ease((performance.now() - t0) / LAND_MS);
        heatTo(cv, now(), S, cells, a);
        if (a < 1) requestAnimationFrame(land); else heatTo(cv, now(), S, null);
      };
      requestAnimationFrame(land);
    }));
  },
  best(S) {
    const R = S.R, stats = S.box.querySelectorAll('.af-recap-stat');
    stats.forEach(s => s.classList.remove('af-recap-on'));
    // (`plain`: a detail line, counted in its own small words)
    const put = (el, n, text, plain, wide) => { if (plain) el.textContent = text(n); else el.innerHTML = withBig(text(n), n, wide); };
    const count = (el, to, text, delay, plain) => {
      const wide = plain ? 0 : bigWidth(el, withBig(text(to), to));
      put(el, 0, text, plain, wide);
      later(S, delay, () => {
        const t0 = performance.now(), run = S.run;
        const tick = () => {
          if (run !== S.run) return;
          const n = Math.round(to * ease((performance.now() - t0) / 1100));
          put(el, n, text, plain, wide);
          if (n < to) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    };
    stats.forEach((s, i) => {
      const v = s.querySelector('.af-recap-v'), when = s.querySelector('.af-recap-when'), k = s.dataset.stat;
      later(S, 250 + i * 650, () => s.classList.add('af-recap-on'));
      if (k === 'streak') count(v, R.bestStreak[0], n => AF.tn('recap.n_days', n), 250 + i * 650);
      if (k === 'month') { v.innerHTML = withBig(monthLong(R.bestMonth[0]), -1); count(when, R.bestMonth[1], n => AF.tn('heatmap.n_reviews', n), 250 + i * 650, true); }
      if (k === 'day') count(v, R.bestDay[1], n => AF.tn('heatmap.n_reviews', n), 250 + i * 650);
    });
    const fin = S.box.querySelector('.af-recap-fin');
    if (fin) { fin.classList.remove('af-recap-on'); later(S, 250 + stats.length * 650 + 400, () => fin.classList.add('af-recap-on')); }
    play(S, 250 + stats.length * 650 + 1100, () => {});
  },
  animals(S) {
    const big = S.box.querySelector('[data-big="animals"]'), chips = S.box.querySelectorAll('.af-recap-chip');
    // (the count waits for the first of them: never "0 animals moved in")
    const show = n => { big.innerHTML = withBig(AF.tn('recap.n_animals_moved_in', n), n); big.classList.add('af-recap-on'); };
    chips.forEach(c => c.classList.remove('af-recap-on'));
    arrive(S, true);
    big.classList.remove('af-recap-on');
    big.innerHTML = withBig(AF.tn('recap.n_animals_moved_in', 1), 1);
    // (each animal its chip, the ones past the last chip counted on it)
    const n = S.R.animals.length, step = stepFor(n);
    S.R.animals.forEach((x, i) => later(S, FIRST_MS + i * step, () => { chips[Math.min(i, chips.length - 1)].classList.add('af-recap-on'); show(i + 1); }));
    play(S, FIRST_MS + n * step, () => {});
  },
  label(S) { play(S, 1200, () => {}); },
  summary(S) {
    const cv = S.box.querySelector('.af-recap-share'), g = cv.getContext('2d'), run = S.run;
    picture(S, cv);
    if (S.fitSave) S.fitSave();
    // (the forest on it keeps moving: its part of the picture drawn again each frame while in view, not
    // the whole picture a few times a second, which stepped)
    const tick = () => { if (run !== S.run) return; forestOnto(g, S); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    bars(S, 1);
  }
};

/* what a theme switch draws again: the card in view's pictures */
function redrawStill(S) {
  const k = S.order[S.at];
  if (k === 'days') { const h = heatFor(S, HEAT_W), cv = S.box.querySelector('.af-recap-heat'); if (h && cv) heatTo(cv, h, S, null); }
  if (k === 'summary') picture(S, S.box.querySelector('.af-recap-share'));
}

/* ---------- the year's heatmap, drawn again at a size ---------- */
const drawnOf = r => { const b = r && r.querySelector('.af-cal'); return b && b.afDrawn; };

/* the heatmap as its own code draws it, the whole year `width` css px across (at the screen's resolution,
 * or `px` pixels a css px). Its days (`cells`), where each is on it, and the same with no days */
function heatFor(S, width, px) {
  const key = width + ':' + (px || 0);
  if (S.heat[key]) return S.heat[key];
  const full = drawnOf(S.calFull), empty = drawnOf(S.calEmpty);
  if (!full || !empty) return null;
  // (the whole year, January to December, however late it began: the card says the year, and an empty
  // spring is the year's too)
  const C = AF.cal.STATE.CELL, x0 = 0, x1 = full.W;
  // (in December, the days still to come left off: drawn as empty days, they read as days missed)
  const ahead = full.cells.filter(c => c.o > 0);
  const dp = px || window.devicePixelRatio || 1;
  let k = width / (x1 - x0) * dp;
  const shot = d => {
    let cv;
    if (d.sharpen) {
      const was = d.cv.width / d.W;
      d.sharpen(k);
      cv = document.createElement('canvas'); cv.width = Math.round((x1 - x0) * k); cv.height = Math.round(d.Hh * k);
      cv.getContext('2d').drawImage(d.cv, Math.round(x0 * k), 0, cv.width, cv.height, 0, 0, cv.width, cv.height);
      d.sharpen(was);
    } else {
      // (a style drawn once, at its own pixels (a scenery's: Giraffe, Scanlines): whole pixels when a whole
      // scale comes near the size asked for; else the next whole scale up, made smaller smoothly. Its whole
      // scale down, alone, left the year at 0.6 of its width on the picture)
      const n = Math.floor(k);
      if (n >= 1 && n >= WHOLE_NEAR * k) k = n;
      // (between whole scales its own pixels, each 1 or 2 of the picture's: made smaller smoothly from
      // the next scale up, Giraffe's patches and Contours' bands came out soft on a sharp picture)
      cv = document.createElement('canvas'); cv.width = Math.round((x1 - x0) * k); cv.height = Math.round(d.Hh * k);
      const g = cv.getContext('2d'); g.imageSmoothingEnabled = false;
      g.drawImage(d.cv, x0, 0, x1 - x0, d.Hh, 0, 0, cv.width, cv.height);
    }
    const g = cv.getContext('2d'), at = v => Math.round(v * k);
    ahead.forEach(c => { const x = at(c.x - 0.5 - x0), y = at(c.y - 0.5); g.clearRect(x, y, at(c.x - 0.5 - x0 + C) - x, at(c.y - 0.5 + C) - y); });
    return cv;
  };
  const h = { full: shot(full), empty: shot(empty), brackets: full.brackets || [], by: full.band + AF.cal.ROWS * C + 3, cells: full.cells.filter(c => !(c.o > 0)), x0, k, C, dp, band: TOP_BAND * dp };
  S.heat[key] = h;
  return h;
}
const TOP_BAND = 22;  // (the months' names over the weeks, css px)

/* onto `cv`: the months over the weeks, and the days `upto` (a list) filled in over the empty year, or
 * all of it with its streak's bracket and trophies (null) */
function heatTo(cv, h, S, upto, alpha) {
  // (the year ends under the streaks' counts, whatever its tiles' size: the brackets' lane under them is
  // empty here (its trophies are the heatmap's hover layer's), and with big tiles, a year begun in the
  // autumn, it left twice the room over the reviews' line)
  const w = h.full.width, ht = Math.ceil(h.band + h.by * h.k + 17 * h.dp);
  if (cv.width !== w || cv.height !== ht) { cv.width = w; cv.height = ht; cv.style.width = w / h.dp + 'px'; cv.style.height = ht / h.dp + 'px'; }
  const g = cv.getContext('2d');
  g.clearRect(0, 0, w, ht);
  months(g, h, h.band - 6 * h.dp, 11 * h.dp, cssVar('--fg-subtle') || '#888', S.rtl, 0, window.getComputedStyle(S.box).fontFamily);
  if (upto === null) { g.drawImage(h.full, 0, h.band); notes(g, h, S, 1); return; }
  g.drawImage(h.empty, 0, h.band);
  for (const c of upto) {
    const x = Math.floor((c.x - 0.5 - h.x0) * h.k), y = Math.floor((c.y - 0.5) * h.k), s = Math.ceil(h.C * h.k) + 1, sy = Math.ceil((h.C - 0.5) * h.k);
    g.drawImage(h.full, x, y, s, sy, x, y + h.band, s, sy);
  }
  if (alpha) { g.globalAlpha = alpha; g.drawImage(h.full, 0, h.band); notes(g, h, S, alpha); g.globalAlpha = 1; }
}
/* each streak's length under its bracket, as the heatmap writes it (calendar/draw.js: there a line
 * of the page's, not on its canvas), where the bracket is long enough to hold it */
function notes(g, h, S, alpha) {
  const kc = h.k / h.dp, size = 11 * h.dp;
  g.save();
  g.globalAlpha = alpha; g.fillStyle = cssVar('--fg-subtle') || '#888';
  g.font = `${size}px ${window.getComputedStyle(S.box).fontFamily}`;  // (the dialog's type: Anki's page is Helvetica on a Mac)
  g.textAlign = 'center'; g.textBaseline = 'top';
  h.brackets.filter(b => (b.x1 - b.x0) * kc >= AF.cal.NOTE_ROOM + 2 * (7 * kc + 4))
    .forEach(b => g.fillText(AF.tn('heatmap.n_days', b.len), ((b.x0 + b.x1) / 2 - h.x0) * h.k, h.band + h.by * h.k + 4 * h.dp));
  g.restore();
}
/* each month's short name over its first week, as the heatmap writes them */
function months(g, h, y, size, colour, rtl, left, font) {
  g.fillStyle = colour; g.font = `${size}px ${font || window.getComputedStyle(document.body).fontFamily}`;
  g.textBaseline = 'alphabetic'; g.textAlign = rtl ? 'right' : 'left';
  const first = {};
  h.cells.forEach(c => { const m = new Date(c.ms).getUTCMonth(); if (!(m in first) || c.o < first[m].o) first[m] = c; });
  Object.keys(first).forEach(m => {
    const c = first[m], x = left + (rtl ? (c.x + h.C - h.x0) : (c.x - h.x0)) * h.k;
    g.fillText(AF.i18n.monthName(+m, 'short'), x, y);
  });
}

/* ---------- the summary: the year as one picture, 1080 x 1350, in Anki's own colours ---------- */
function picture(S, onto) {
  const R = S.R, cv = onto || document.createElement('canvas');
  cv.width = W; cv.height = H;
  const g = cv.getContext('2d'), rtl = S.rtl, font = window.getComputedStyle(document.body).fontFamily;
  g.direction = rtl ? 'rtl' : 'ltr';
  // (Anki's colours. An old Anki has none of these variables, and in day mode no page colour at all:
  // the picture came out see-through, its words black on whatever shows it, its labels as dark as its numbers)
  const page = AF.u.pageBg([document.body, document.documentElement]) || AF.u.appBg(), bg = S.pictureBg = `rgb(${page.join(', ')})`;
  const fg = cssVar('--fg') || window.getComputedStyle(document.body).color;
  const sub = cssVar('--fg-subtle') || fg.replace(/rgba?\(([^,]+),([^,]+),([^,)]+).*/, 'rgba($1,$2,$3, 0.55)');
  // (right to left, the picture mirrors: what stands at the left stands at the right)
  const X = (x, w) => (rtl ? W - x - (w || 0) : x);
  // (`room`: the width it may take, its size brought down until it fits: German's "1.032 Wiederholungen"
  // ran into the next column's "176 Tage")
  const text = (s, x, y, size, colour, weight, end, room) => {
    g.font = `${weight || 400} ${size}px ${font}`; g.fillStyle = colour;
    while (room && size > 12 && g.measureText(s).width > room) { size--; g.font = `${weight || 400} ${size}px ${font}`; }
    g.textAlign = (end ? !rtl : rtl) ? 'right' : 'left';
    g.fillText(s, X(x), y);
  };
  // a line's width in the picture's type; columns of such widths spread across it, the first at the
  // left margin, the last ending at the right one, the same room between each
  const wide = (s, size, weight) => { g.font = `${weight || 400} ${size}px ${font}`; return g.measureText(s).width; };
  const spread = ws => {
    const gap = ws.length > 1 ? (CW - ws.reduce((a, b) => a + b, 0)) / (ws.length - 1) : 0;
    let x = M;
    return ws.map(w => { const at = x; x += w + gap; return at; });
  };
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  g.textBaseline = 'alphabetic';
  text(String(R.year), M, 150, 76, fg, 600);
  // the forest, at a whole number of its pixels
  const fc = S.forestRoot.querySelector('canvas.af-canvas'), fy = 196;
  let fh = 0;
  if (fc && fc.width) {
    const s = Math.max(1, Math.floor(CW / fc.width)), fw = fc.width * s;
    fh = fc.height * s;
    S.forestAt = { x: M + (CW - fw) / 2, y: fy, w: fw, h: fh };
    forestOnto(g, S);
  }
  // the numbers, the heatmap and the bests spread down to the name in the corner: the room left
  // over shared out between their gaps, so none stands out (an empty band over the name did)
  const h = heatFor(S, CW, 1);
  const used = 96 + 130 + (h ? h.full.height : 0) + 64 + 80, extra = Math.max(-12, (H - BOTTOM - 64 - (fy + fh) - used) / 4);
  // the year's numbers
  const y = fy + fh + 96 + extra, hours = R.seconds >= 90 * 60;
  // (as the days card counts them, timeIn: none recorded is 0, not "1 minute")
  const mins = R.seconds > 0 ? Math.max(1, Math.round(R.seconds / 60)) : 0;
  const stats = [[R.studied, AF.tn('recap.unit_days_studied', R.studied)], [R.reviews, AF.tn('recap.unit_reviews', R.reviews)],
    [R.newCards, AF.tn('recap.unit_new_cards', R.newCards)],
    hours ? [Math.round(R.seconds / 3600), AF.tn('recap.unit_hours', Math.round(R.seconds / 3600))] : [mins, AF.tn('recap.unit_minutes', mins)]];
  const sx = spread(stats.map(st => Math.max(wide(num(st[0]), 54, 600), wide(st[1], 26))));
  stats.forEach((st, i) => {
    const x = sx[i];
    text(num(st[0]), x, y, 54, fg, 600);
    text(st[1], x, y + 40, 26, sub);
  });
  // the heatmap, drawn again by its own code at the picture's width
  let hy = y + 130 + extra;
  if (h) {
    const left = M + (CW - h.full.width) / 2;
    months(g, h, hy - 10, 22, sub, rtl, left);
    g.drawImage(h.full, left, hy);
    hy += h.full.height;
  }
  // the bests, one line each (a short year: its best day and its first tree, no streak or month)
  const ry = hy + 64 + extra, recs = [];
  if (R.bestDay) recs.push([AF.t('recap.best_day'), AF.tn('heatmap.n_reviews', R.bestDay[1]), shortDate(R.bestDay[0])]);
  if (!R.short && R.bestStreak && R.bestStreak[0] >= 2) recs.push([AF.t('recap.best_streak'), AF.tn('recap.n_days', R.bestStreak[0]), AF.t('recap.from_to', { first: shortDate(R.bestStreak[1]), last: shortDate(R.bestStreak[2]) })]);
  // (a year studied in one month alone: "Best month: November, 36 reviews" said the year's own total again)
  const oneMonth = R.bestMonth && R.bestMonth[1] === R.reviews;
  if (!R.short && R.bestMonth && !oneMonth) recs.push([AF.t('recap.best_month'), monthLong(R.bestMonth[0]), AF.tn('heatmap.n_reviews', R.bestMonth[1])]);
  if ((R.short || oneMonth) && R.first) recs.push([AF.t('recap.first_day'), shortDate(R.first), AF.tn('caption.n_trees', R.trees)]);
  // (three spread like the numbers over them, a size smaller where they'd crowd: German's "1.032 Wiederholungen";
  // a short year's two in the first two thirds)
  const rw = (r, k) => Math.max(wide(r[0], 24 * k), wide(r[1], 34 * k, 600), wide(r[2], 24 * k));
  const rk = recs.length === 3 ? Math.min(1, (CW - 2 * 40) / recs.reduce((a, r) => a + rw(r, 1), 0)) : 1;
  const rx = recs.length === 3 ? spread(recs.map(r => rw(r, rk))) : recs.map((r, i) => M + i * (CW / 3));
  recs.forEach((r, i) => {
    const x = rx[i];
    text(r[0], x, ry, 24 * rk, sub);
    text(r[1], x, ry + 44, 34 * rk, fg, 600);
    text(r[2], x, ry + 80, 24 * rk, sub);
  });
  // its maker's name, quietly, in a corner: about an empty day's grey (a name, never translated)
  g.globalAlpha = 0.6;
  text('Memory Forest', M + CW, H - BOTTOM, 22, sub, 400, true);
  g.globalAlpha = 1;
  return cv;
}
/* the forest onto the picture, at its whole pixels, round cornered */
function forestOnto(g, S) {
  const fc = S.forestRoot.querySelector('canvas.af-canvas'), a = S.forestAt;
  if (!fc || !a) return;
  // (the page's colour first: drawn again each frame over itself, the corners' soft edge went hard)
  g.fillStyle = S.pictureBg; g.fillRect(a.x, a.y, a.w, a.h);
  g.save(); round(g, a.x, a.y, a.w, a.h, 14); g.clip();
  g.imageSmoothingEnabled = false; g.drawImage(fc, a.x, a.y, a.w, a.h); g.restore();
}
function round(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

/* ---------- its stylesheet, put on the page the first time it opens ---------- */
let styled = false;
function style() {
  if (styled) return;
  styled = true;
  const s = document.createElement('style');
  s.textContent = CSS;
  document.head.append(s);
}
// (no flex gap, :is() or aspect-ratio: Chromium 77, the oldest Anki's)
const CSS = `
.af-recap { position: fixed; left: 0; top: 0; right: 0; bottom: 0; z-index: 2147483000; font: 14px/1.4 var(--af-font, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif); }
.af-recap-scrim { position: absolute; left: 0; top: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.5); animation: af-recap-in 0.2s ease-out; }
@keyframes af-recap-in { from { opacity: 0; } }
@keyframes af-recap-rise { from { top: calc(50% + 12px); } }
.af-recap-dlg { position: absolute; left: 50%; top: 50%; width: ${DLG_W}px; height: ${DLG_H}px; margin: -${DLG_H / 2}px 0 0 -${DLG_W / 2}px;
  background: var(--canvas, #f5f5f5); color: var(--fg, #020202); border-radius: 12px; overflow: hidden; outline: none;
  box-shadow: 0 0 0 1px var(--border, rgba(128, 128, 128, 0.3)), 0 20px 60px rgba(0, 0, 0, 0.45); transform-origin: 50% 50%; animation: af-recap-in 0.12s ease-out, af-recap-rise 0.25s ease-out; }
.af-recap-dlg[style*="translate"] { margin: 0; }
/* (a row: the bars end where Skip begins, however long its words: German's ran under them) */
.af-recap-top { position: relative; height: 44px; display: flex; align-items: flex-start; padding: 0 12px 0 20px; }
.af-rtl .af-recap-top { padding: 0 20px 0 12px; }
.af-recap-bars { flex: 1; display: flex; margin: 23px 26px 0 0; }  /* (on Skip's and the x's middle: 2px over it at 21px) */
.af-rtl .af-recap-bars { margin: 23px 0 0 26px; }
.af-recap-bars i { flex: 1; height: 3px; border-radius: 1.5px; background: rgba(128, 128, 128, 0.25); margin: 0 2px; overflow: hidden; position: relative; }
.af-recap-bars b { position: absolute; left: 0; top: 0; bottom: 0; width: 0; background: var(--fg, #020202); opacity: 0.6; }
.af-rtl .af-recap-bars b { left: auto; right: 0; }
.af-recap-skip, .af-recap-x { flex: none; font-family: inherit; font-size: 13px; line-height: 1; color: var(--fg-subtle, #707070); background: transparent !important; border: 0 !important; box-shadow: none !important; cursor: pointer; padding: 8px; border-radius: 6px; }
.af-recap-skip { white-space: nowrap; margin-top: 9px; } .af-recap-x { margin: 9px 0 0 7px; font-size: 20px; padding: 4px 8px; }
.af-rtl .af-recap-x { margin: 9px 7px 0 0; }
.af-recap-skip:hover, .af-recap-x:hover { color: var(--fg, #020202); }
.af-recap-skip:focus, .af-recap-x:focus, .af-recap-save:focus, .af-recap-again:focus, .af-recap-link:focus { outline: 2px solid currentColor; outline-offset: 2px; }
.af-recap-link:focus:not(:focus-visible) { outline: none; }  /* (back from a click: no ring; from the keys, the caption's own grey ring) */
.af-recap-skip[hidden] { display: block; visibility: hidden; }  /* (its room kept: the bars never move) */
.af-recap-save:focus-visible { outline-color: var(--fg, #020202); }  /* (its own colour on the button filled with the text's; Chromium 77 skips it, keeping the plain one) */
.af-recap-body { position: relative; height: ${DLG_H - 44}px; cursor: pointer; }
.af-recap-back { position: absolute; top: 0; bottom: 0; left: 0; width: 30%; z-index: 1; }
.af-recap-at-end .af-recap-body { cursor: default; } .af-recap-at-end .af-recap-back { cursor: pointer; }
.af-rtl .af-recap-back { left: auto; right: 0; }
.af-recap-card { position: absolute; left: 0; top: 0; right: 0; bottom: 0; opacity: 0; visibility: hidden; text-align: center; z-index: 2; pointer-events: none;
  transform: translateY(6px); transition: opacity 0.15s, transform 0s 0.15s, visibility 0.15s; }
.af-recap-card.af-recap-on { opacity: 1; visibility: visible; transform: none; transition: opacity 0.3s 0.12s, transform 0.3s 0.12s, visibility 0s; }
.af-recap-card button { pointer-events: auto; }
/* (the finished decks' full names and each animal's how-it-came, in their tooltips: under the card's
   pointer-events: none, they never came up) */
.af-recap-fin, .af-recap-chip[title] { pointer-events: auto; }
.af-recap-card p { margin: 0; }
.af-recap-kick { font-size: 15px; color: var(--fg-subtle, #707070); }
.af-recap-num { font-size: 44px; font-weight: 600; color: var(--fg, #020202); display: inline-block; text-align: end; }
.af-recap-big { font-size: 22px; line-height: 1.2; color: var(--fg-subtle, #707070); font-variant-numeric: tabular-nums; }
.af-recap-subline { display: inline-block; text-align: start; }
.af-recap-sub { font-size: 15px; color: var(--fg-subtle, #707070); font-variant-numeric: tabular-nums; margin-top: 16px !important; transition: opacity 0.4s; }
.af-recap-forest { position: absolute; left: ${(DLG_W - FOREST_W) / 2}px; top: 108px; width: ${FOREST_W}px; height: ${FOREST_W / 2}px; z-index: 1; opacity: 0; transition: opacity 0.15s; pointer-events: none; }
.af-recap-forest.af-recap-on { opacity: 1; transition: opacity 0.35s 0.12s; }
.af-recap-forest .af-panel { padding: 0 !important; margin: 0 !important; max-width: none !important; width: ${FOREST_W}px; }
.af-recap-forest .af-caption, .af-recap-forest .af-cog, .af-recap-forest .af-zoom, .af-recap-forest .af-visit { display: none !important; }
.af-recap-forest canvas.af-canvas { border-radius: 6px; }
.af-recap-out { position: absolute; left: -20000px; top: 0; width: ${HEAT_W}px; visibility: hidden; }
.af-recap-out .af-panel { width: ${HEAT_W}px !important; max-width: none !important; padding: 0 !important; margin: 0 !important; }
.af-recap-out .af-cal { width: 100% !important; max-width: none !important; margin-top: 0 !important; }
.af-recap-title .af-recap-kick { margin-top: 14px; }
.af-recap-year { font-size: 56px; line-height: 1.05; font-weight: 600; margin-top: 2px !important; }
.af-recap-under { position: absolute; left: 0; right: 0; top: 418px; font-size: 15px; color: var(--fg-subtle, #707070); font-variant-numeric: tabular-nums; }
.af-recap-hint { position: absolute; left: 0; right: 0; top: 500px; font-size: 12.5px; color: var(--fg-subtle, #707070); }
.af-recap-days { display: flex; flex-direction: column; justify-content: center; padding-bottom: 24px; }
.af-recap-days .af-recap-big { margin-top: 0; }
.af-recap-heat { display: block; margin: 34px auto 0; }
.af-recap-best { display: flex; flex-direction: column; justify-content: center; padding-bottom: 24px; }
.af-recap-best .af-recap-kick { margin-top: 0; }
.af-recap-trio { display: flex; justify-content: center; margin-top: 48px; }
.af-recap-fin { margin-top: 44px !important; font-size: 15px; color: var(--fg-subtle, #707070); opacity: 0; transition: opacity 0.5s; padding: 0 40px; }
.af-recap-fin.af-recap-on { opacity: 1; }
/* (the three as tall as the tallest, their words at the foot: a value on two lines, German's "1.032 /
   Wiederholungen", rises, and Best streak, Best month and Best day stay on one line) */
.af-recap-stat { width: 240px; display: flex; flex-direction: column; justify-content: flex-end; opacity: 0; transform: translateY(8px); transition: opacity 0.4s, transform 0.4s; }
.af-recap-stat.af-recap-on { opacity: 1; transform: none; }
.af-recap-v { font-size: 22px; color: var(--fg-subtle, #707070); line-height: 1.2; min-height: 54px; font-variant-numeric: tabular-nums; }
.af-recap-what { font-size: 15px; margin-top: 6px !important; }
.af-recap-when { font-size: 13px; color: var(--fg-subtle, #707070); margin-top: 4px !important; font-variant-numeric: tabular-nums; }
.af-recap-animals .af-recap-big { margin-top: 26px; }
.af-recap-animals .af-recap-num { font-size: 36px; }
.af-recap-animals .af-recap-big { opacity: 0; transition: opacity 0.35s; }
.af-recap-animals .af-recap-big.af-recap-on { opacity: 1; }
.af-recap-chips { position: absolute; left: ${(DLG_W - FOREST_W) / 2 - 30}px; right: ${(DLG_W - FOREST_W) / 2 - 30}px; top: 438px; display: flex; flex-wrap: wrap; justify-content: center; }
.af-recap-chip { display: inline-flex; align-items: center; height: 28px; padding: 0 9px 0 7px; margin: 0 3px 5px; border-radius: 999px; background: rgba(128, 128, 128, 0.12);
  font-size: 12px; opacity: 0; transform: translateY(6px); transition: opacity 0.35s, transform 0.35s; white-space: nowrap; }
.af-recap-chip.af-recap-on { opacity: 1; transform: none; }
.af-recap-more { padding: 0 11px; color: var(--fg-subtle, #707070); }
.af-recap-chip canvas { image-rendering: pixelated; margin: 0 6px 0 0; align-self: flex-end; margin-bottom: 4px !important; }
.af-rtl .af-recap-chip canvas { margin: 0 0 0 6px; }
.af-recap-chip .af-recap-when { margin: 0 0 0 5px !important; font-size: 12px; }
.af-rtl .af-recap-chip .af-recap-when { margin: 0 5px 0 0 !important; }
.af-recap-label .af-recap-kick { margin-top: 14px; }
.af-recap-title { font-size: 36px; line-height: 1.15; font-weight: 600; margin-top: 4px !important; }
.af-recap-line { position: absolute; left: 0; right: 0; top: 446px; font-size: 18px; }
.af-recap-share { position: absolute; left: 44px; top: 20px; width: 400px; height: 500px; border-radius: 10px; box-shadow: 0 0 0 1px rgba(128, 128, 128, 0.35), 0 10px 30px rgba(0, 0, 0, 0.22); }
.af-rtl .af-recap-share { left: auto; right: 44px; }
.af-recap-side { position: absolute; left: 488px; top: 194px; width: 290px; text-align: start; }  /* (its middle on the picture's) */
.af-rtl .af-recap-side { left: auto; right: 488px; }
.af-recap-kick2 { font-size: 22px; }
.af-recap-say { font-size: 14px; color: var(--fg-subtle, #707070); margin-top: 8px !important; }
/* (each on one line, Watch again under Save image where the two don't fit: German's "Bild gespeichert" and
   "Noch einmal ansehen" took two lines each; the space after Save image, so a Watch again below starts flush) */
.af-recap-acts { display: flex; flex-wrap: wrap; align-items: center; margin-top: 12px; }
.af-recap-acts button { margin: 10px 18px 0 0 !important; white-space: nowrap; }
.af-rtl .af-recap-acts button { margin: 10px 0 0 18px !important; }
.af-recap-acts .af-recap-again { margin: 10px 0 0 0 !important; }
.af-rtl .af-recap-acts .af-recap-again { margin: 10px 0 0 0 !important; }
.af-recap-save { font-family: inherit; font-size: 15px; line-height: 1; color: var(--canvas, #fff) !important; background: var(--fg, #020202) !important; border: 0 !important; border-radius: 999px; padding: 11px 20px; cursor: pointer; }
.af-recap-save:hover { opacity: 0.9; }
.af-recap-file { font-size: 12.5px; color: var(--fg-subtle, #707070); margin-top: 8px !important; word-break: break-all; }
.af-recap-again { font-family: inherit; font-size: 14px; line-height: 1; color: var(--fg-subtle, #707070); background: transparent !important; border: 0 !important; box-shadow: none !important; padding: 6px 0; cursor: pointer; }
.af-recap-again:hover { color: var(--fg, #020202); }
.af-recap-link { font: inherit; color: inherit; background: none !important; border: 0 !important; border-bottom: 1px dotted currentColor !important; border-radius: 0 !important; box-shadow: none !important; padding: 0 !important; margin: 0; cursor: pointer; }
`;
})();

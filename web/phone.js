/* Memory Forest — the boot script of the card that shows the forest on a phone (see
 * phone_data.py). It goes last in the one file the card loads, in place of forest.js: it
 * reads the note's data, picks today's scene from the days the computer sent, follows the
 * phone's own clock where the settings say so, and mounts the forest. */
(function () {
'use strict';
const id = document.currentScript && document.currentScript.dataset.root;
const root = id && document.getElementById(id), json = id && document.getElementById(id + '-data');
const AF = window.AnkiForest;
if (!root || !json || !AF) return;
window.AnkiForest = undefined;
const MINUTE = 60 * 1000;

/* YYYY-MM-DD for the phone's own date */
function isoDate(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

/* today's scene: the day the computer sent for today's date, or the nearest it has */
function pickDay(days, today) {
  return days.find(d => d.date === today) || (today < days[0].date ? days[0] : days[days.length - 1]);
}

/* the time of day by this clock, as scene.time_of_day works it out on the computer */
function timeOfDay(now, sun) {
  const at = hm => { const [h, m] = hm.split(':').map(Number); const t = new Date(now); t.setHours(h, m, 0, 0); return t.getTime(); };
  const rise = at(sun.rise), set = at(sun.set), tw = sun.twilight * MINUTE, n = now.getTime();
  if (rise - tw <= n && n < rise + tw) return 'dawn';
  if (set - tw <= n && n < set + tw) return 'dusk';
  if (set - 2 * tw <= n && n < set - tw) return 'golden_hour';
  if (rise + tw <= n && n < set - tw) return 'day';
  return 'night';
}

/* the page's data for right now, from what the note holds */
function forNow(note, now) {
  const today = isoDate(now), day = pickDay(note.days, today), sent = note.days[0].date === today;
  const mood = Object.assign({}, day.mood);
  if (mood.clock) mood.time = timeOfDay(now, note.sun);
  let credit = note.credit;
  if (day.fallback && now.getTime() > day.liveUntil) {  // the live weather sent has gone stale
    Object.assign(mood, day.fallback);
    delete mood.temp; delete mood.city;
    credit = false;
  }
  const data = Object.assign({}, note, { mood, credit, dayNumber: day.dayNumber, sceneName: day.sceneName, sceneTip: day.sceneTip });
  if (!sent) {  // what happened on the day the computer sent this is old news by now
    Object.assign(data, { journal: '', anniversaries: [], events: [] });
    // and its warnings were for that day only: the asteroid due that night, the smoke that
    // asked for a review that day, the tumbleweeds blowing away as the backlog was cleared
    data.doom = null;
    if (note.fire && note.fire.smoke) {
      data.fire = Object.assign({}, note.fire, { smoke: 0 });
      data.trees = (note.trees || []).map(t => (t.smoke ? Object.assign({}, t, { smoke: 0 }) : t));
    }
    if (note.backlog && note.backlog.cleared) data.backlog = Object.assign({}, note.backlog, { cleared: false });
  }
  return data;
}

/* how long ago the computer sent it: "just now", "3 hours ago", "yesterday", "4 days ago" */
function ago(iso) {
  const m = Math.round((Date.now() - new Date(iso)) / MINUTE);
  if (!(m >= 1)) return 'just now';  // (or a computer whose clock runs ahead of the phone's)
  if (m < 60) return m + (m === 1 ? ' minute ago' : ' minutes ago');
  const h = Math.round(m / 60);
  if (h < 24) return h + (h === 1 ? ' hour ago' : ' hours ago');
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : d + ' days ago';
}

let note;
try { note = JSON.parse(json.textContent); } catch { note = null; }
json.remove();  // read once (the template read it first): its text would stay on the page as long as the card
if (!note || !Array.isArray(note.days) || !note.days.length) {
  root.textContent = 'Your forest arrives with the next sync from Anki on your computer.';
  return;
}
/* Sideways: on a phone held upright the forest is a thin strip across the top, so in full
 * screen it is turned a quarter to fill the screen for a phone turned on its side (auto-rotate
 * or not). Outside full screen it stays upright, so the caption and the button read easily. */
// the scene is twice as wide as it is tall (ASPECT in core.js); the caption and the line
// under it need this much of the screen's width beside it, and the forest keeps this
// margin from the screen's ends
const SCENE_ASPECT = 2, CAPTION_ROOM = 120, SIDE_MARGIN = 24, RELAYOUT_MS = 200;
const CALENDAR_SHARE = 0.62;  // the calendar's full screen: its weeks this much of the screen across (in whole pixels, kept crisp turned or not)
// a forest sent this long ago asks for a sync on the computer
const STALE_MS = 2 * 24 * 60 * MINUTE;
// the screen's room, in the page's own pixels: a card zoomed (AnkiDroid's card zoom) draws each
// of them bigger than the screen's, and a forest sized in the screen's would run off its edge
const probe = document.createElement('div');
probe.style.cssText = 'position:absolute;visibility:hidden;width:100px;height:0';
function screenRoom() {
  shell.append(probe);
  const k = probe.getBoundingClientRect().width / 100 || 1;
  probe.remove();
  return [window.innerWidth / k, window.innerHeight / k].map(Math.floor);
}
const portrait = () => { const [w, h] = screenRoom(); return h > w; };
// going full screen: the forest is turned first, so it fills the screen as it opens; and which
// fills it, the forest or the study calendar under it (each has its button)
let entering = false, mode = 'forest';

// one quiet line under it all: when it was synced, and what to do only once that is long ago
// (answering the card does no harm: the next sync makes it new again, phone.py _keep_new)
const shell = document.createElement('div'), stage = document.createElement('div'), stamp = document.createElement('div');
shell.className = 'af-phone-shell';
stage.className = 'af-phone-stage';
stamp.className = 'af-phone-note';
const sentAt = new Date(note.updated || '');
const stale = Date.now() - sentAt.getTime() > STALE_MS;
stamp.textContent = (note.updated ? 'Synced ' + ago(note.updated) + '. ' : '')
  + (stale ? 'Sync Anki on your computer to bring it up to date. ' : '');
root.before(shell);
shell.append(stage);
stage.append(root, stamp);

function drawFailed(e) { console.error('Memory Forest could not draw the forest:', e); root.textContent = 'Memory Forest could not draw your forest here.'; }

function layout() {
  const side = portrait() && (entering || !!document.fullscreenElement), [vw, vh] = screenRoom();
  stage.classList.toggle('af-sideways', side);
  // turned a quarter clockwise about its top left corner, then moved back onto the screen
  Object.assign(stage.style, side
    ? { width: vh + 'px', height: vw + 'px', transform: `translateX(${vw}px) rotate(90deg)`, minHeight: '' }
    : { width: '', height: '', transform: '', minHeight: '' });
  // outside full screen, the forest and its lines sit in the middle of the screen, not at its top
  if (!side && !document.fullscreenElement) {
    const body = window.getComputedStyle(document.body);
    const above = stage.getBoundingClientRect().top + window.scrollY;
    const below = parseFloat(body.marginBottom) + parseFloat(body.paddingBottom) || 0;
    stage.style.minHeight = Math.max(0, vh - above - below) + 'px';
  }
  const data = forNow(note, new Date()), isFull = !!document.fullscreenElement || entering;
  // as wide as the screen along the forest, but never taller than the screen across it
  // leaves room for beside the caption (a phone held sideways is only so tall)
  const along = side ? vh - SIDE_MARGIN : vw, across = side ? vw : vh;
  // in full screen the forest is shown alone, with no caption to leave room for; or the
  // calendar alone, as wide as the screen is long
  const room = isFull ? 0 : CAPTION_ROOM;
  data.maxWidth = Math.floor(Math.min(data.maxWidth, along, (across - room) * SCENE_ASPECT));
  if (isFull && mode === 'calendar') Object.assign(data, { showForest: false, maxWidth: Math.floor(along), swipedK: AF.calendarScaleFor(across * CALENDAR_SHARE) });
  else if (isFull) data.calendar = null;
  // the same forest at the same size as already drawn (going full screen and turning both
  // ask more than once): nothing to build again. Of layouts that overlap (a tap while the
  // first is still loading its scenery), the latest is the one drawn
  // zooming in among the trees is the full screen's alone, and simply on there (web/visit.js):
  // outside it the forest is too small to walk into, and a finger scrolls the card
  const zoom = isFull && mode === 'forest' ? 'always' : false;
  const key = JSON.stringify([data.maxWidth, data.mood, data.dayNumber, data.journal, zoom, data.showForest, !!data.calendar, data.swipedK]), mine = ++layouts;
  if (key === drawn && root.afEnv) return Promise.resolve();
  return AF.loadScripts(scenery(data.mood, !!data.calendar)).then(() => {
    if (mine !== layouts) return;
    drawn = key;
    // a zoomed-in view stays as it is through the new drawing (a turn in full screen), where the
    // new one zooms too
    const zoomed = zoom === 'always' && root.afVisits ? root.afVisits.state : null;
    AF.mount(root, data, { now: true, zoom });
    placeTurns();
    if (zoomed && root.afVisits) root.afVisits.resume(zoomed);
  }, () => {
    if (mine === layouts) root.textContent = 'Your forest is on its way: sync once more to fetch its drawing.';
  }).catch(drawFailed);
}
let drawn = '', layouts = 0;

/* Today's scenery: each environment, landscape and landmark is a file of its own in the
 * collection's media (the note names them), loaded the first time a scene needs it - the
 * one file the card loads holds everything else. */
function scenery(mood, calendar) {
  // (and, with the calendar shown, the files the heatmap's look borrows from another scenery: its tiles)
  const look = (calendar && note.calendar && note.calendar.look && note.calendar.look.files) || [];
  return [['envs', mood.special], ['landscapes', mood.landscape], ['landmarks', mood.landmark]]
    .map(([kind, key]) => key && (note.parts || {})[`${kind}/${key}.js`])
    .concat(look.map(rel => (note.parts || {})[rel])).filter((f, i, all) => f && all.indexOf(f) === i);
}

/* Full screen: the forest alone, without the app's bars and buttons, held in landscape where
 * the phone lets a page do that (sideways otherwise); or the calendar alone. Each has an icon on
 * itself - the forest's corner, the end of the calendar's footer - that becomes a close icon in
 * full screen. Whether the app's web view allows it at all is up to the app: the icons only show
 * where the page says it might, and the line under it says when it did not. */
const FULLSCREEN_CHECK_MS = 600;
const full = document.createElement('button'), fullCal = document.createElement('button');
full.type = fullCal.type = 'button';
full.className = 'af-turn af-expand';
fullCal.className = 'af-turn af-expand af-expand-cal';
full.hidden = !document.fullscreenEnabled;
fullCal.hidden = !document.fullscreenEnabled || !note.calendar;
// (each mount draws the forest and the calendar afresh, the calendar a moment after: the icons
// are put back on them whenever they are missing; watched on the panel's own children and the
// calendar's, whose footer each drawing builds anew, not on the whole forest, whose tooltips and
// layers come and go all the time)
const turnsWatch = window.MutationObserver ? new window.MutationObserver(() => placeTurns()) : null;
function placeTurns() {
  const sc = root.querySelector('.af-scene'), cal = root.querySelector('.af-cal'), foot = root.querySelector('.af-cal-foot');
  if (sc && full.parentNode !== sc) sc.appendChild(full);
  if (foot && fullCal.parentNode !== foot) foot.insertBefore(fullCal, foot.firstChild);
  if (cal && turnsWatch) turnsWatch.observe(cal, { childList: true });
}
if (turnsWatch) turnsWatch.observe(root, { childList: true });

const EXPAND = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 3h4v4M7 15H3v-4M15 3l-5 5M3 15l5-5"/></svg>';
const CLOSE = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4.5 4.5l9 9M13.5 4.5l-9 9"/></svg>';
const label = () => {
  const on = !!document.fullscreenElement;
  full.innerHTML = fullCal.innerHTML = on ? CLOSE : EXPAND;
  full.setAttribute('aria-label', on ? 'Leave full screen' : 'Forest full screen');
  fullCal.setAttribute('aria-label', on ? 'Leave full screen' : 'Heatmap full screen');
};
label();
document.addEventListener('fullscreenchange', label);
// (out of full screen, the shell goes back to the card's own background)
const backFromFull = () => { entering = false; shell.style.background = ''; shell.classList.remove('af-full-cal'); };
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) backFromFull(); });

/* the card's own colour: the first background the page has (the card, the body, the page), else
 * the app's - AnkiDroid and AnkiMobile paint it behind a transparent page, which a full screen
 * would show as black */
const FOREST_BG = '#000000';
function cardColor() {
  const bg = AF.u.pageBg([document.querySelector('.card'), document.body, document.documentElement]) || AF.u.appBg();
  return `rgb(${bg.join(',')})`;
}
function enter(what) {
  mode = what;
  entering = true;
  layout();
  // the forest on black, as a picture is shown; the calendar on the card's own colour, on a
  // sheet of its own (phone.py's CSS)
  shell.style.background = what === 'forest' ? FOREST_BG : cardColor();
  shell.classList.toggle('af-full-cal', what === 'calendar');
  return shell.requestFullscreen().then(() => {
    const o = window.screen.orientation;
    if (o && o.lock) o.lock('landscape').catch(() => {});  // no landscape lock: the page turns the forest itself
  }, e => {  // not allowed: back upright
    backFromFull();
    layout();
    throw e;
  });
}
function leave() {
  try { window.screen.orientation.unlock(); } catch { /* never locked */ }
  document.exitFullscreen().catch(() => {});
}
const NOT_ALLOWED = "Full screen isn't allowed here. ";
const notAllowed = () => { if (!stamp.textContent.includes(NOT_ALLOWED)) stamp.textContent = NOT_ALLOWED + stamp.textContent; };
[[full, 'forest'], [fullCal, 'calendar']].forEach(([button, what]) => button.addEventListener('click', e => {
  e.stopPropagation();  // (not a tap on the forest or a day under it)
  if (document.fullscreenElement) { leave(); return; }
  enter(what).catch(notAllowed);
  setTimeout(() => { if (!document.fullscreenElement) notAllowed(); }, FULLSCREEN_CHECK_MS);
}));
let pending;
const relayout = () => { clearTimeout(pending); pending = setTimeout(layout, RELAYOUT_MS); };
window.addEventListener('resize', relayout);
document.addEventListener('fullscreenchange', relayout);  // the caption comes and goes with it

try { layout(); }
catch (e) { drawFailed(e); }
})();

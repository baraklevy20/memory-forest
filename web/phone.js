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
  }
  return data;
}

function when(iso) {
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
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
// a forest sent this long ago asks for a sync on the computer
const STALE_MS = 2 * 24 * 60 * MINUTE;
const portrait = () => window.innerHeight > window.innerWidth;
// going full screen: the forest is turned first, so it fills the screen as it opens
let entering = false;

const shell = document.createElement('div'), stage = document.createElement('div'), stamp = document.createElement('div');
const noAnswer = document.createElement('div');
shell.className = 'af-phone-shell';
stage.className = 'af-phone-stage';
stamp.className = noAnswer.className = 'af-phone-note';
const sentAt = new Date(note.updated || '');
const stale = Date.now() - sentAt.getTime() > STALE_MS;
stamp.textContent = `Sent from Anki on your computer${note.updated ? ', ' + when(note.updated) : ''}. `
  + (stale ? 'Open Anki on your computer and sync to bring it up to date. ' : '');
noAnswer.textContent = 'No need to answer this card: just go back.';
root.before(shell);
shell.append(stage);
stage.append(root, stamp, noAnswer);

function drawFailed(e) { console.error('Memory Forest could not draw the forest:', e); root.textContent = 'Memory Forest could not draw your forest here.'; }

function layout() {
  const side = portrait() && (entering || !!document.fullscreenElement), vw = window.innerWidth, vh = window.innerHeight;
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
  const data = forNow(note, new Date());
  // as wide as the screen along the forest, but never taller than the screen across it
  // leaves room for beside the caption (a phone held sideways is only so tall)
  const along = side ? vh - SIDE_MARGIN : vw, across = side ? vw : vh;
  // in full screen the forest is shown alone, with no caption to leave room for
  const room = document.fullscreenElement ? 0 : CAPTION_ROOM;
  data.maxWidth = Math.floor(Math.min(data.maxWidth, along, (across - room) * SCENE_ASPECT));
  // the same forest at the same size as already drawn (going full screen and turning both
  // ask more than once): nothing to build again. Of layouts that overlap (a tap while the
  // first is still loading its scenery), the latest is the one drawn
  const key = JSON.stringify([data.maxWidth, data.mood, data.dayNumber, data.journal]), mine = ++layouts;
  if (key === drawn && root.afEnv) return Promise.resolve();
  return AF.loadScripts(scenery(data.mood)).then(() => {
    if (mine !== layouts) return;
    drawn = key;
    AF.mount(root, data, { now: true });
  }, () => {
    if (mine === layouts) root.textContent = 'Your forest is on its way: sync once more to fetch its drawing.';
  }).catch(drawFailed);
}
let drawn = '', layouts = 0;

/* Today's scenery: each environment, landscape and landmark is a file of its own in the
 * collection's media (the note names them), loaded the first time a scene needs it - the
 * one file the card loads holds everything else. */
function scenery(mood) {
  return [['envs', mood.special], ['landscapes', mood.landscape], ['landmarks', mood.landmark]]
    .map(([kind, key]) => key && (note.parts || {})[`${kind}/${key}.js`]).filter(Boolean);
}

/* Full screen: the forest alone, without the app's bars and buttons, held in landscape where
 * the phone lets a page do that (sideways otherwise). A page may only go full screen
 * straight after a tap, so on a touch screen the first tap on the forest does it; the
 * button goes in and out after that. Whether the app's web view allows it at all is up to
 * the app: the button only shows where the page says it might, and says when it did not. */
const FULLSCREEN_CHECK_MS = 600;
const full = document.createElement('button'), hint = document.createElement('span');
full.type = 'button';
full.className = 'af-turn';
full.hidden = !document.fullscreenEnabled;
hint.textContent = 'Tap the forest to fill the screen. ';
hint.hidden = true;
stamp.prepend(hint);
stamp.append(full);
const label = () => { full.textContent = document.fullscreenElement ? 'Leave full screen' : 'Full screen'; };
label();
document.addEventListener('fullscreenchange', label);
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) entering = false; });

function enter() {
  entering = true;
  layout();
  // the full screen is the card's own colour, not the black a page gets by default
  shell.style.background = window.getComputedStyle(document.body).backgroundColor;
  return shell.requestFullscreen().then(() => {
    const o = window.screen.orientation;
    if (o && o.lock) o.lock('landscape').catch(() => {});  // no landscape lock: the page turns the forest itself
  }, e => {  // not allowed: back upright
    entering = false;
    layout();
    throw e;
  });
}
function leave() {
  try { window.screen.orientation.unlock(); } catch { /* never locked */ }
  document.exitFullscreen().catch(() => {});
}
full.addEventListener('click', () => {
  if (document.fullscreenElement) { leave(); return; }
  enter().catch(() => { full.textContent = "Full screen isn't allowed here"; });
  setTimeout(() => { if (!document.fullscreenElement) full.textContent = "Full screen isn't allowed here"; }, FULLSCREEN_CHECK_MS);
});

const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
if (touch && document.fullscreenEnabled) {
  hint.hidden = false;
  const once = e => {
    shell.removeEventListener('click', once, true);
    hint.hidden = true;
    if (!e.target.closest('button') && !document.fullscreenElement) enter().catch(() => {});  // a button does its own thing
  };
  shell.addEventListener('click', once, true);
}
let pending;
const relayout = () => { clearTimeout(pending); pending = setTimeout(layout, RELAYOUT_MS); };
window.addEventListener('resize', relayout);
document.addEventListener('fullscreenchange', relayout);  // the caption comes and goes with it

try { layout(); }
catch (e) { drawFailed(e); }
})();

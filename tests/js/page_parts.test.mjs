// The page's small parts, in node: the shared helpers (web/util.js), the tooltips' words
// (web/tooltips.js), the caption (web/caption.js), the phone card's clock and "Synced ... ago"
// (web/phone.js), what's new (web/news.js) and the scene runner's script loading (web/core.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import { load, SCRIPTS } from './load.mjs';

const plain = v => JSON.parse(JSON.stringify(v));
const page = (globals = {}) => load(SCRIPTS, { globals });

test('util: text for the page is escaped, capitalised and dated in English', () => {
  const { u } = page().AnkiForest;
  assert.equal(u.esc('<b a="1">&</b>'), '&lt;b a=&quot;1&quot;&gt;&amp;&lt;/b&gt;');
  assert.equal(u.esc(42), '42');
  assert.equal(u.cap('deer'), 'Deer');
  assert.equal(u.cap(''), '');
  assert.equal(u.fmtDate('2026-03-05'), 'Mar 5, 2026');
  assert.equal(u.fmtDate('2025-12-31'), 'Dec 31, 2025');
});

test('util: colours', () => {
  const { u } = page().AnkiForest;
  assert.deepEqual(plain(u.hex('#3c8d40')), [60, 141, 64]);
  assert.equal(u.toHex([60, 141, 64]), '#3c8d40');
  assert.equal(u.toHex([-5, 300, 12.6]), '#00ff0d');
  assert.equal(u.mixHex('#000000', '#ffffff', 0.5), '#808080');
  assert.equal(u.rgb([1.9, 2, 3], 0.5), 'rgba(1,2,3,0.5)');
  assert.equal(u.rgb('#abc'), '#abc');
});

test('util: random numbers repeat for a seed; a string hashes the same every time', () => {
  const { u } = page().AnkiForest;
  const a = u.rng(7), b = u.rng(7), xs = [a(), a(), a()];
  assert.deepEqual(xs, [b(), b(), b()]);
  assert.ok(xs.every(x => x >= 0 && x < 1));
  assert.equal(u.hashStr('calendar|2026-10-18'), u.hashStr('calendar|2026-10-18'));
  assert.notEqual(u.hashStr('a'), u.hashStr('b'));
});

test('util: messages go to Anki only where its bridge is', () => {
  let got = [];
  const anki = page({ pycmd: m => got.push(m) }).AnkiForest;
  anki.u.send('forest:settings');
  assert.deepEqual(got, ['forest:settings']);
  assert.ok(anki.u.canBrowse());
  const phone = page().AnkiForest;
  assert.equal(phone.u.canBrowse(), false);
  got = [];
  phone.u.send('forest:settings');  // (no bridge: nothing, and no error)
  assert.deepEqual(got, []);
});

test('util: "Animate the forest" on, off, or as the system asks', () => {
  const still = page({ matchMedia: () => ({ matches: true }) }).AnkiForest.u, moving = page({ matchMedia: () => ({ matches: false }) }).AnkiForest.u;
  assert.equal(still.animates({ animations: 'system' }), false);
  assert.equal(moving.animates({ animations: 'system' }), true);
  assert.equal(still.animates({ animations: true }), true);
  assert.equal(moving.animates({ animations: false }), false);
});

test('util: the colour behind the page, and behind a phone\'s transparent card', () => {
  const styles = new Map();
  const w = page({ getComputedStyle: el => ({ backgroundColor: styles.get(el) || 'rgba(0, 0, 0, 0)' }) });
  const { u } = w.AnkiForest, a = { nodeType: 1 }, b = { nodeType: 1 };
  styles.set(a, 'rgba(10, 20, 30, 0.2)'); styles.set(b, 'rgb(44, 44, 44)');
  assert.deepEqual(plain(u.pageBg([a, b])), [44, 44, 44]);  // (a faint background is seen through)
  assert.equal(u.pageBg([a]), null);
  assert.deepEqual(plain(u.appBg()), [255, 255, 255]);
  w.document.querySelector = sel => (sel.includes('nightMode') ? {} : null);
  assert.deepEqual(plain(u.appBg()), [47, 47, 49]);
});

test('util: a pointer\'s place is taken back out of a zoomed page', () => {
  const { u } = page().AnkiForest;
  const el = { clientWidth: 100, clientHeight: 50, getBoundingClientRect: () => ({ width: 125, height: 62.5 }) };
  assert.deepEqual(plain(u.pointIn({ offsetX: 50, offsetY: 25 }, el)), [40, 20]);
  const flat = { clientWidth: 100, clientHeight: 50, getBoundingClientRect: () => ({ width: 100, height: 50 }) };
  assert.deepEqual(plain(u.pointIn({ offsetX: 50, offsetY: 25 }, flat)), [50, 25]);
  // (a turned box: its sides swapped, its area the same)
  const turned = { clientWidth: 100, clientHeight: 50, getBoundingClientRect: () => ({ width: 50, height: 100 }) };
  assert.deepEqual(plain(u.pointIn({ offsetX: 10, offsetY: 5 }, turned)), [10, 5]);
});

test('util: loop mode rounds each motion to whole cycles, and leaves them alone outside it', () => {
  const AF = page().AnkiForest, { u } = AF;
  assert.equal(u.cyc(1.4), 1.4);
  assert.equal(u.per(3), 3);
  AF.LOOP = 10;
  const w = u.cyc(1.4);
  assert.ok(Math.abs(Math.sin(w * 10) - Math.sin(0)) < 1e-9);
  assert.ok(Math.abs(10 / u.per(3) - Math.round(10 / u.per(3))) < 1e-9);
});

test('tooltips: memory strength in days, months, years', () => {
  const AF = page().AnkiForest;
  assert.deepEqual([5, 59.4, 60, 364, 365, 800].map(AF.fmtStrength), ['5 days', '59 days', '2 months', '12 months', '1.0 years', '2.2 years']);
});

test('tooltips: a tree\'s lines say what is known, and no more', () => {
  const AF = page({ pycmd: () => {} }).AnkiForest, words = AF.WORDS;
  const tree = { date: '2026-10-10', ago: 8, n: 12, stage: 3, remembered: 0.913, strength: 90 };
  let html = AF.tips.tree(tree, words);
  assert.match(html, /<b>Oct 10, 2026<\/b> · planted 8 days ago/);
  assert.match(html, /12 cards · mature/);
  assert.match(html, /~91% remembered · lasts ~3 months/);
  assert.match(html, /Click to see these cards/);
  // (no forgetting curve behind it: only how it is going)
  html = AF.tips.tree(Object.assign({}, tree, { measured: false }), words);
  assert.match(html, /91% still going well/);
  assert.doesNotMatch(html, /remembered/);
  // every card suspended: nothing to measure
  html = AF.tips.tree(Object.assign({}, tree, { suspended: 12 }), words);
  assert.match(html, /All 12 cards suspended/);
  assert.doesNotMatch(html, /remembered/);
  assert.match(AF.tips.tree(Object.assign({}, tree, { n: 1, suspended: 1 }), words), /Its card is suspended/);
  // today, yesterday; a seedling says no numbers; a leech and a cured one
  assert.match(AF.tips.tree(Object.assign({}, tree, { ago: 0, stage: 0 }), words), /planted today/);
  assert.doesNotMatch(AF.tips.tree(Object.assign({}, tree, { ago: 1, stage: 0 }), words), /remembered/);
  assert.match(AF.tips.tree(Object.assign({}, tree, { ago: 1 }), words), /planted yesterday/);
  assert.match(AF.tips.tree(Object.assign({}, tree, { leeches: 2 }), words), /2 leeches here/);
  assert.match(AF.tips.tree(Object.assign({}, tree, { cured: 1 }), words), /A leech here mature again/);
  assert.match(AF.tips.tree(Object.assign({}, tree, { struggling: 3 }), words), /3 of 12 relearning/);
  // a click that picks it, zoomed in, says so in place of the cards
  html = AF.tips.tree(tree, words, 'Click to select it');
  assert.match(html, /Click to select it/);
  assert.doesNotMatch(html, /see these cards/);
  // on the phone (no bridge), no click hint
  assert.doesNotMatch(page().AnkiForest.tips.tree(tree, words), /Click/);
  // the date escaped as text
  assert.doesNotMatch(AF.tips.tree(Object.assign({}, tree, { date: '2026-10-10' }), Object.assign({}, words, { planted: '<i>' })), /<i>/);
});

test('tooltips: a pond says when the break ran', () => {
  const { tips } = page().AnkiForest;
  assert.equal(tips.pond({ days: 4, from: '2026-05-03', to: '2026-05-06' }), '<b>A quiet pond</b><br>4 days without reviews, in May 2026');
  assert.match(tips.pond({ days: 60, from: '2026-04-20', to: '2026-06-18' }), /from April to June 2026/);
  assert.match(tips.pond({ days: 60, from: '2025-12-20', to: '2026-01-18' }), /from December 2025 to January 2026/);
  assert.equal(tips.pond({ days: 3 }), '<b>A quiet pond</b><br>3 days without reviews');
});

test('tooltips: the deep forest and an animal', () => {
  const AF = page({ pycmd: () => {} }).AnkiForest;
  const html = AF.tips.deep({ count: 1200, cards: 15000, from_date: '2020-01-02', to_date: '2023-05-06', ancient: 30 }, AF.WORDS);
  assert.match(html, /The deep forest/);
  assert.match(html, /1,200 older trees · 15,000 cards/);
  assert.match(html, /30 of them ancient/);
  assert.equal(AF.tips.visitor({ label: 'a deer', why: 'you studied 30 days in a row' }), '<b>A deer</b><br>Moved in when you studied 30 days in a row.');
  assert.match(AF.tips.visitor({ label: 'a cabin', key: 'cabin', why: 'x' }), /Built when/);
});

/* a stand-in for the panel's root, enough for the caption and the news: its parts by selector */
function fakeRoot(parts = {}) {
  const el = () => ({ textContent: '', innerHTML: '', classList: new Set(), children: [], listeners: {},
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }, setAttribute(k, v) { this[k] = v; },
    append(c) { this.children.push(c); } });
  const made = {};
  const root = { querySelector: sel => (sel in parts ? parts[sel] : (made[sel] = made[sel] || el())), querySelectorAll: () => [] };
  root.made = made;
  for (const v of Object.values(parts)) if (v) Object.assign(v, Object.assign(el(), v));
  return root;
}
const stats = { trees: 120, ancient: 4, streak: 37 };
const mood = { special: 'natural', weather: 'rain', source: 'manual' };

test('caption: trees, the deep forest, ancient trees and the streak, each with its tooltip', () => {
  const AF = page({ pycmd: () => {} }).AnkiForest, root = fakeRoot();
  AF.caption(root, { stats, mood, channel: 'forest', journal: 'A quiet week.',
    merged: { count: 1500, cards: 9000, from_date: '2019-01-01', to_date: '2022-02-02', from_ago: 2800, to_ago: 1600 } });
  const html = root.made['.af-meta'].innerHTML;
  assert.equal(root.made['.af-journal'].textContent, 'A quiet week.');
  assert.match(html, />120 trees</);
  assert.match(html, />1,500 in the deep forest</);
  assert.match(html, /data-cmd="forest:browse:2800::1600"/);
  assert.match(html, />4 ancient</);
  // the streak's click is the page's own (By year in the heatmap), not a message
  assert.match(html, /<span class="af-info af-click" data-tip="[^"]*" data-act="\d+">37-day streak</);
  const act = root.afCaptionActs[+html.match(/data-act="(\d+)"/)[1]];
  let asked = null;
  assert.equal(act({ afCalByYear: q => { asked = q; return true; } }), true);
  assert.equal(asked, undefined);
  assert.match(act.hint({ afCalByYear: () => true }), /Click to see it year by year/);
  assert.equal(act.hint({ afCalByYear: () => false }), '');
  assert.equal(act.hint({}), '');
  // the weather only when live
  assert.doesNotMatch(html, /Weather/);
});

test('caption: a streak counted over 6 or 5 days a week says so', () => {
  const AF = page().AnkiForest;
  for (const [week, says] of [[7, /in a row\. A day with nothing due doesn&#39;t break it\.|A day with nothing due doesn't break it\./], [6, /a day off in a week/], [5, /two days off in a week/]]) {
    const root = fakeRoot();
    AF.caption(root, { stats: Object.assign({}, stats, { streak_week: week }), mood });
    assert.match(root.made['.af-meta'].innerHTML, says);
  }
});

test('caption: one tree, a test forest, a deck\'s highlight, live weather and its errors', () => {
  const AF = page({ pycmd: () => {} }).AnkiForest;
  let root = fakeRoot();
  AF.caption(root, { stats: { trees: 1 }, mood, testForest: true, merged: { count: 2, cards: 3, from_date: '2020-01-01', to_date: '2020-02-01', from_ago: 9, to_ago: 5 } });
  let html = root.made['.af-meta'].innerHTML;
  assert.match(html, />Test forest</);
  assert.match(html, />1 tree</);
  assert.doesNotMatch(html, /data-cmd/);  // (a made-up forest's deep forest opens nothing)
  root = fakeRoot();
  AF.caption(root, { stats, mood: Object.assign({}, mood, { source: 'real', city: 'Oslo', temp: 4.6 }), highlight: true, deckName: 'Lang::German', litCount: 30, deckId: 5, credit: true });
  html = root.made['.af-meta'].innerHTML;
  assert.match(html, />German: 30 of 120 trees</);
  assert.match(html, />Weather: rain in Oslo, 5°</);
  assert.match(html, /weather by MET Norway/);
  root = fakeRoot();
  AF.caption(root, { stats, mood, weatherError: 'city not found: Atlantis' });
  assert.match(root.made['.af-meta'].innerHTML, />City not found</);
  root = fakeRoot();
  AF.caption(root, { stats, mood, weatherError: 'timed out' });
  assert.match(root.made['.af-meta'].innerHTML, /could not be fetched \(timed out\)/);
});

test('caption: the deep forest is browsed across decks where a deck screen highlights it', () => {
  const AF = page().AnkiForest;
  assert.equal(AF.deckFor({ deckId: 7 }), 7);
  assert.equal(AF.deckFor({ deckId: 7, highlight: true }), '');
  assert.equal(AF.deckFor({}), '');
});

test('news: a dot on the cog, and a note on the forest whose buttons answer it', () => {
  const sent = [], made = [], w = load(SCRIPTS, { globals: { pycmd: m => sent.push(m) } });
  // (the note: a div the page makes)
  w.document.createElement = tag => { const e = { tag, listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, remove() { this.removed = true; } }; made.push(e); return e; };
  const cog = {}, scene = {}, root = fakeRoot({ '.af-cog': cog, '.af-scene': scene });
  w.AnkiForest.news(root, { inAnki: true, channel: 'forest', newDot: 'scenery', news: { id: 'heatmap2', title: 'A <new> heatmap', text: 'Try it.', action: 'Show me' } });
  assert.ok(cog.classList.has('af-cog-new'));
  assert.equal(cog.title, 'Change scenery and settings (new scenery)');
  assert.equal(cog['aria-label'], cog.title);
  const card = made.find(e => e.tag === 'div');
  assert.ok(scene.children.includes(card));
  assert.match(card.innerHTML, /<b>A &lt;new&gt; heatmap<\/b>Try it\./);
  assert.match(card.innerHTML, /data-news="open">Show me</);
  assert.match(card.innerHTML, /data-news="seen">Got it</);
  card.listeners.click({ target: { closest: () => null } });  // (a click beside the buttons)
  assert.ok(!card.removed);
  card.listeners.click({ target: { closest: () => ({ dataset: { news: 'seen' } }) } });
  assert.ok(card.removed);
  assert.deepEqual(sent, ['forest:news:seen:heatmap2']);
  // something new that is not a scenery
  const cog3 = {};
  w.AnkiForest.news(fakeRoot({ '.af-cog': cog3, '.af-scene': null }), { inAnki: true, newDot: 'settings' });
  assert.equal(cog3.title, 'Change scenery and settings (something new)');
  // not in Anki (the phone): nothing at all
  made.length = 0;
  const cog2 = {};
  w.AnkiForest.news(fakeRoot({ '.af-cog': cog2, '.af-scene': {} }), { inAnki: false, newDot: 'scenery', news: { id: 'x', title: 't', text: 'x' } });
  assert.equal(made.length, 0);
  assert.equal(cog2.title, undefined);
});

// web/phone.js runs only on its card; its clock and its words, handed to the tests at its first line
const PHONE_EDITS = { 'phone.js': [
  ['window.AnkiForest = undefined;\nconst MINUTE = 60 * 1000;', 'window.AnkiForest = undefined;'],
  ['if (!root || !json || !AF) return;', 'const MINUTE = 60 * 1000; if (!root || !json || !AF) { window.__phone = { isoDate, pickDay, timeOfDay, forNow, ago }; return; }'],
] };
const phone = () => load([...SCRIPTS, 'phone.js'], { edits: PHONE_EDITS }).__phone;

test('phone: "Synced ... ago"', () => {
  const { ago } = phone(), at = mins => new Date(Date.now() - mins * 60000).toISOString();
  assert.equal(ago(at(0)), 'just now');
  assert.equal(ago(at(-30)), 'just now');  // (a computer whose clock runs ahead)
  assert.equal(ago('not a date'), 'just now');
  assert.equal(ago(at(1)), '1 minute ago');
  assert.equal(ago(at(45)), '45 minutes ago');
  assert.equal(ago(at(60)), '1 hour ago');
  assert.equal(ago(at(5 * 60)), '5 hours ago');
  assert.equal(ago(at(24 * 60)), 'yesterday');
  assert.equal(ago(at(4 * 24 * 60)), '4 days ago');
});

test('phone: today\'s scene is the day sent for today, or the nearest', () => {
  const { pickDay, isoDate } = phone(), days = [{ date: '2026-10-17' }, { date: '2026-10-18' }, { date: '2026-10-19' }];
  assert.equal(pickDay(days, '2026-10-18'), days[1]);
  assert.equal(pickDay(days, '2026-10-01'), days[0]);
  assert.equal(pickDay(days, '2026-11-01'), days[2]);
  assert.equal(isoDate(new Date(2026, 0, 5, 23, 30)), '2026-01-05');
});

test('phone: the time of day by the phone\'s own clock', () => {
  const { timeOfDay } = phone(), sun = { rise: '06:30', set: '18:30', twilight: 30 };
  const at = (h, m) => new Date(2026, 9, 18, h, m);
  assert.equal(timeOfDay(at(3, 0), sun), 'night');
  assert.equal(timeOfDay(at(6, 10), sun), 'dawn');
  assert.equal(timeOfDay(at(12, 0), sun), 'day');
  assert.equal(timeOfDay(at(17, 40), sun), 'golden_hour');
  assert.equal(timeOfDay(at(18, 30), sun), 'dusk');
  assert.equal(timeOfDay(at(19, 0), sun), 'night');
});

test('phone: a note from an earlier day drops that day\'s news; stale live weather falls back', () => {
  const { forNow, isoDate } = phone(), now = new Date(2026, 9, 18, 12, 0), today = isoDate(now);
  const day = (date, more) => Object.assign({ date, mood: { time: 'day', weather: 'rain', clock: false, temp: 3, city: 'Oslo' }, dayNumber: 9, sceneName: 'Lake' }, more);
  const note = { days: [day('2026-10-17')], sun: { rise: '06:30', set: '18:30', twilight: 30 }, journal: 'Big day', anniversaries: [3], events: [{ k: 1 }],
    doom: { at: 1 }, fire: { smoke: 2 }, trees: [{ smoke: 1, n: 3 }, { n: 1 }], backlog: { cleared: true }, credit: true };
  let data = forNow(note, now);
  assert.equal(data.journal, '');
  assert.deepEqual(plain(data.anniversaries), []);
  assert.equal(data.doom, null);
  assert.equal(data.fire.smoke, 0);
  assert.equal(data.trees[0].smoke, 0);
  assert.equal(data.backlog.cleared, false);
  assert.equal(note.trees[0].smoke, 1, 'the note itself is left as it came');
  // sent today: kept
  data = forNow(Object.assign({}, note, { days: [day(today)] }), now);
  assert.equal(data.journal, 'Big day');
  assert.equal(data.dayNumber, 9);
  // the live weather gone stale: the scenery's own, with no city and no credit
  data = forNow(Object.assign({}, note, { days: [day(today, { fallback: { weather: 'clear' }, liveUntil: now.getTime() - 1 })] }), now);
  assert.equal(data.mood.weather, 'clear');
  assert.equal(data.mood.city, undefined);
  assert.equal(data.credit, false);
  // the clock followed where the settings say so
  data = forNow(Object.assign({}, note, { days: [day(today, { mood: { clock: true, time: 'day' } })] }), new Date(2026, 9, 18, 3, 0));
  assert.equal(data.mood.time, 'night');
});

test('core: scripts load once each, one at a time, under this copy\'s name', async () => {
  const w = page(), AF = w.AnkiForest, added = [];
  w.document.head.appendChild = el => { added.push([el.src, w.AnkiForest === AF]); setTimeout(() => (el.src.includes('bad') ? el.onerror() : el.onload()), 1); };
  w.AnkiForest = 'another copy';
  await AF.loadScripts(['envs/a.js', 'envs/b.js', 'envs/a.js']);
  await AF.loadScripts(['envs/a.js']);
  assert.deepEqual(added, [['envs/a.js', true], ['envs/b.js', true]]);
  assert.equal(w.AnkiForest, 'another copy', 'the name is given back once they are in');
  // a file that won't load: rejected, and tried again the next time
  await assert.rejects(AF.loadScripts(['envs/bad.js']), /could not load envs\/bad\.js/);
  await assert.rejects(AF.loadScripts(['envs/bad.js']));
  assert.equal(added.filter(a => a[0] === 'envs/bad.js').length, 2);
});

test('core: a scene is busy (15 frames a second) only while something fast is in it', () => {
  const AF = page().AnkiForest;
  const env = { mood: { special: 'natural', landscape: 'none', landmark: 'none' }, data: {}, placed: [] };
  assert.equal(AF.busy(env), false);
  AF.ENVS.natural = Object.assign({}, AF.ENVS.natural, { busy: true });
  assert.equal(AF.busy(env), true);
  AF.ENVS.natural.busy = e => e.data.fast === true;
  assert.equal(AF.busy(env), false);
  env.data.fast = true;
  assert.equal(AF.busy(env), true);
});

// (core.js's loop asks AF.busy after every frame, in the `finally` that sets the next one: a scene
// whose build threw part way has no trees placed yet, AF.busy throws, and the loop is gone for good:
// e2e/page_check.mjs's "a rebuild that fails part way" shows it in the page)
test('core: AF.busy answers for a scene whose build stopped part way', () => {
  const AF = page().AnkiForest;
  assert.equal(AF.busy({ mood: { special: 'natural', landscape: 'none', landmark: 'none' }, data: {} }), false);
});

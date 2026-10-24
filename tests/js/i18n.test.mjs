// The page's words in the reader's language (web/i18n.js): translations, plurals, and the dates and
// numbers Intl writes; and Python's plural table agreeing with the page's (i18n.py PLURALS).
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { load, SCRIPTS, WEB } from './load.mjs';

const page = i18n => { const AF = load(SCRIPTS).AnkiForest; AF.i18n.use(i18n); return AF; };

test('i18n: with no language sent, the page writes English, from web/strings_en.js', () => {
  const AF = page(undefined);
  assert.equal(AF.t('caption.click_to_see_their_cards'), 'Click to see their cards.');
  assert.equal(AF.tn('heatmap.n_reviews', 1), '1 review');
  assert.equal(AF.tn('heatmap.n_reviews', 3581), '3,581 reviews');
  assert.equal(AF.t('x.not_there'), 'x.not_there');
  assert.equal(AF.u.fmtDate('2026-10-17'), 'Oct 17, 2026');
  assert.equal(AF.i18n.dec(1.5), '1.5');
  assert.equal(AF.i18n.dec(2), '2.0');
  assert.equal(AF.i18n.monthName(2, 'short'), 'Mar');
  assert.equal(AF.i18n.weekdayName(1, 'short'), 'Mon');
  assert.equal(AF.i18n.nearDay(0), 'Today');
  assert.equal(AF.i18n.dir(), 'ltr');
});

test('i18n: a translation and its plural forms; one it was not sent shows the English', () => {
  const AF = page({ lang: 'he', format: 'he', dir: 'rtl', plural: 'one_two_other', strings: {
    'caption.click_to_see_their_cards': 'אפשר ללחוץ כדי לראות את הכרטיסים.',
    'heatmap.n_reviews': { one: 'חזרה אחת', two: 'שתי חזרות', other: '{n} חזרות' },
  } });
  assert.equal(AF.t('caption.click_to_see_their_cards'), 'אפשר ללחוץ כדי לראות את הכרטיסים.');
  assert.equal(AF.t('caption.test_forest'), 'Test forest');
  assert.equal(AF.tn('heatmap.n_reviews', 1), 'חזרה אחת');
  assert.equal(AF.tn('heatmap.n_reviews', 2), 'שתי חזרות');
  // (a number in a right-to-left sentence is isolated, so it keeps its place: U+2068 to U+2069)
  assert.equal(AF.tn('heatmap.n_reviews', 60), '\u206860\u2069 חזרות');
  assert.equal(AF.i18n.dir(), 'rtl');
});

test('i18n: German dates and numbers come from Intl', () => {
  const AF = page({ lang: 'de', format: 'de', plural: 'one_other', strings: { 'heatmap.n_reviews': { one: '{n} Wiederholung', other: '{n} Wiederholungen' } } });
  assert.equal(AF.tn('heatmap.n_reviews', 3581), '3.581 Wiederholungen');
  assert.equal(AF.i18n.num(3581), '3.581');
  assert.equal(AF.i18n.dec(1.5), '1,5');
  assert.equal(AF.i18n.monthName(2, 'long'), 'März');
  assert.equal(AF.i18n.nearDay(0), 'Heute');
});

test('i18n: en-GB writes British dates', () => {
  const AF = page({ lang: 'en-GB', format: 'en-GB' });
  assert.equal(AF.u.fmtDate('2026-10-17'), '17 Oct 2026');
});

test('i18n: the page and Python pick the same plural form', () => {
  const AF = page(undefined);
  const py = path.join(WEB, '..');
  const ns = [0, 1, 2, 3, 4, 5, 10, 11, 12, 14, 21, 22, 25, 100, 101, 102, 111, 1000];
  const out = JSON.parse(execFileSync('python3', ['-c',
    `import json, i18n; print(json.dumps({r: [f(n) for n in ${JSON.stringify(ns)}] for r, f in i18n.PLURALS.items()}))`], { cwd: py }).toString());
  for (const [rule, forms] of Object.entries(out)) {
    assert.deepEqual(ns.map(AF.i18n.PLURALS[rule]), forms, rule);
  }
  assert.deepEqual(Object.keys(AF.i18n.PLURALS).sort(), Object.keys(out).sort());
});

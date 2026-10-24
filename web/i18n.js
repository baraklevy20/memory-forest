/* Memory Forest — the page's words in the reader's language (i18n.py's other half): each wording by
 * its id, in English from web/strings_en.js (made from locales/en.json by dev/strings.py) unless the
 * page is sent it in its language (data.i18n: i18n.page_strings), its plural forms, and the dates and
 * numbers Intl writes in the same language.
 *   AF.t('caption.click_to_see_their_cards')   a wording, by its id
 *   AF.tn('heatmap.n_reviews', n)               a plural; {n} is the number as the language writes it
 *   AF.N_('caption.fog') ... AF.tx(name)        a constant, made before the language is known, shown
 * Placeholders are {name}, filled from an object of values as given (escape them first). */
(function () {
'use strict';
const AF = window.AnkiForest;
// the plural rules (i18n.py PLURALS has the same): Intl.PluralRules in a Chromium as old as Anki
// 2.1.45's has older data (Hebrew's "many"), so the page and Python pick a form alike
const PLURALS = {
  one_other: n => n === 1 ? 'one' : 'other',
  zero_one_other: n => n === 0 || n === 1 ? 'one' : 'other',
  other: () => 'other',
  one_two_other: n => n === 1 ? 'one' : n === 2 ? 'two' : 'other',
  slavic: n => n % 10 === 1 && n % 100 !== 11 ? 'one' : n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? 'few' : 'many',
  polish: n => n === 1 ? 'one' : n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? 'few' : 'many',
  czech: n => n === 1 ? 'one' : n >= 2 && n <= 4 ? 'few' : 'other',
  arabic: n => n === 0 ? 'zero' : n === 1 ? 'one' : n === 2 ? 'two' : n % 100 >= 3 && n % 100 <= 10 ? 'few' : n % 100 >= 11 ? 'many' : 'other',
  bcs: n => n % 10 === 1 && n % 100 !== 11 ? 'one' : n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? 'few' : 'other',
  romanian: n => n === 1 ? 'one' : n === 0 || (n % 100 >= 2 && n % 100 <= 19) ? 'few' : 'other',
  lithuanian: n => n % 10 === 1 && !(n % 100 >= 11 && n % 100 <= 19) ? 'one' : n % 10 >= 2 && !(n % 100 >= 11 && n % 100 <= 19) ? 'few' : 'other',
  latvian: n => n % 10 === 0 || (n % 100 >= 11 && n % 100 <= 19) ? 'zero' : n % 10 === 1 && n % 100 !== 11 ? 'one' : 'other',
  slovenian: n => n % 100 === 1 ? 'one' : n % 100 === 2 ? 'two' : n % 100 === 3 || n % 100 === 4 ? 'few' : 'other',
  irish: n => n === 1 ? 'one' : n === 2 ? 'two' : n >= 3 && n <= 6 ? 'few' : n >= 7 && n <= 10 ? 'many' : 'other',
  welsh: n => ({ 0: 'zero', 1: 'one', 2: 'two', 3: 'few', 6: 'many' })[n] || 'other',
};
const ENGLISH = { lang: 'en', format: 'en-US', dir: 'ltr', plural: 'one_other', strings: {} };

let L = ENGLISH;
const made = new Map();  // the Intl formatters made so far, for this language

/* The language a page speaks, from its data (none: English) */
function use(i18n) {
  const next = Object.assign({}, ENGLISH, i18n || {});
  try {
    if (!Intl.DateTimeFormat.supportedLocalesOf([next.format]).length) next.format = 'en-US';
  } catch { next.format = 'en-US'; }  // (a tag this Chromium's Intl refuses)
  if (next.format !== L.format) made.clear();
  L = next;
}
// a wording in the language, else its English, else the id itself (dev/strings.py check finds those)
const word = key => key in L.strings ? L.strings[key] : AF.EN && key in AF.EN ? AF.EN[key] : key;
// (in a right-to-left language, a value with digits or Latin letters in it - a date, a number, a
// name - is isolated, U+2068 to U+2069, so its parts keep their order inside the sentence: "מאז 15 בנוב׳ 2024")
const isolate = v => L.dir === 'rtl' && /[0-9A-Za-z]/.test(v) ? '\u2068' + v + '\u2069' : v;
const fill = (text, values) => values ? text.replace(/\{(\w+)\}/g, (m, k) => k in values ? isolate(String(values[k])) : m) : text;
const t = (key, values) => { const s = word(key); return fill(typeof s === 'string' ? s : s.other || key, values); };
function tn(key, n, values) {
  const s = word(key), v = Object.assign({ n: num(n) }, values || {});
  if (typeof s === 'string') return fill(s, v);
  // (a wording the page was not sent in its language is English, and takes English's forms)
  const rule = key in L.strings ? PLURALS[L.plural] || PLURALS.one_other : PLURALS.one_other;
  return fill(s[rule(Math.abs(Math.round(n)))] || s.other || key, v);
}
const N_ = key => key;

/* ---------- dates and numbers, as Intl writes them in the language ---------- */
function intl(kind, opts) {
  const key = kind + JSON.stringify(opts);
  if (!made.has(key)) made.set(key, new Intl[kind](L.format, opts));
  return made.get(key);
}
const num = n => intl('NumberFormat', {}).format(n);
// a number with this many decimals, as the language writes them: "1.5", "1,5"
const dec = (n, digits = 1) => intl('NumberFormat', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
// a day (a UTC midnight in ms, or 'YYYY-MM-DD') as Intl's `opts` write it
const dayIn = (d, opts) => intl('DateTimeFormat', Object.assign({ timeZone: 'UTC' }, opts)).format(new Date(typeof d === 'number' ? d : d + 'T00:00:00Z'));
const monthName = (m, form) => dayIn(Date.UTC(2001, m, 15), { month: form });  // m: January 0; form: 'short' | 'long'
const weekdayName = (wd, form) => dayIn(Date.UTC(2001, 0, 7 + wd), { weekday: form });  // wd: Sunday 0 (7 Jan 2001 was one)
// yesterday, today and tomorrow by name ("Today", "Heute", "היום"), capitalised where the language does
const nearDay = o => AF.u.cap(intl('RelativeTimeFormat', { numeric: 'auto' }).format(o, 'day'));
// a date the way the tooltips write one: "Oct 17, 2026", "17. Okt. 2026", "17 באוק׳ 2026"
const fmtDate = iso => dayIn(iso, { day: 'numeric', month: 'short', year: 'numeric' });
const rtl = () => L.dir === 'rtl';
// text whose direction is its own (a date, a number with its word, a name the user typed), kept from
// mixing with the words around it in a right-to-left line
const bdi = html => `<bdi>${html}</bdi>`;
// a panel set to read in the language's direction (forest.css .af-rtl; Anki's own <html dir> is not
// asked: the add-on may speak another language than Anki's); left as it was for left to right
function dirOn(el) {
  if (!el) return;
  el.classList.toggle('af-rtl', rtl());
  if (rtl()) el.setAttribute('dir', 'rtl'); else if (el.getAttribute('dir') === 'rtl') el.removeAttribute('dir');
}
// an arrow (‹ › « ») pointing the way it is drawn: in a right-to-left line a lone arrow is mirrored
// (Unicode's mirrored glyphs), so one that already points as it should is kept left to right
const arrow = ch => (rtl() ? `<span dir="ltr">${ch}</span>` : ch);

AF.t = t; AF.tn = tn; AF.N_ = N_; AF.tx = t;
AF.i18n = { use, num, dec, dayIn, monthName, weekdayName, nearDay, fmtDate, rtl, bdi, dirOn, arrow, lang: () => L.lang, dir: () => L.dir, PLURALS };
})();

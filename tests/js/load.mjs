// The browser scripts (web/), loaded into node for the JS unit tests (tests/js/*.test.mjs, `npm run
// test:js`): each file run as the page runs it, in a context of its own with a stand-in window and
// document (no canvas drawing: a 2d context that does nothing). A file's inner functions are none of
// the page's business, so `expose` hands the tests some of them: a line added to the file's text just
// before its last `})();`, `AF.__test = { ... }` (the file itself is never changed).
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

export const WEB = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'web');

// a 2d context that takes every call and draws nothing
const noop = () => {};
const context2d = () => new Proxy({}, {
  get(t, k) {
    if (k in t) return t[k];
    if (k === 'createImageData' || k === 'getImageData') return (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) });
    if (k === 'measureText') return () => ({ width: 0 });
    return noop;
  },
  set(t, k, v) { t[k] = v; return true; },
});
function element(tag) {
  const el = {
    tagName: String(tag).toUpperCase(), nodeType: 1, style: {}, dataset: {}, children: [], width: 0, height: 0,
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    getContext: () => context2d(), setAttribute: noop, removeAttribute: noop, addEventListener: noop, removeEventListener: noop,
    appendChild: c => c, append: noop, remove: noop, querySelector: () => null, querySelectorAll: () => [],
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0, right: 0, bottom: 0 }),
  };
  return el;
}

/* A fresh page with these scripts (paths under web/) run in order; `expose`: { 'calendar.js': [names] }
 * to hand the tests, as window.AnkiForest.__test[name]. `globals`: more for the page's window (pycmd).
 * Returns the page's window. */
export function load(files, { expose = {}, globals = {}, edits = {} } = {}) {
  const doc = {
    createElement: element, documentElement: element('html'), body: element('body'), head: element('head'),
    scripts: [], hidden: false, addEventListener: noop, removeEventListener: noop,
    querySelector: () => null, querySelectorAll: () => [], getElementById: () => null, currentScript: null,
  };
  const win = {
    document: doc, console, setTimeout, clearTimeout, performance, devicePixelRatio: 1,
    getComputedStyle: () => ({ backgroundColor: 'rgba(0, 0, 0, 0)' }), matchMedia: () => ({ matches: false, addListener: noop, removeListener: noop }),
    Path2D: class { rect() {} moveTo() {} lineTo() {} arc() {} closePath() {} }, Image: class {},
    requestAnimationFrame: cb => setTimeout(cb, 0), ...globals,
  };
  win.window = win;
  const ctx = vm.createContext(win);
  for (const file of files) {
    let src = fs.readFileSync(path.join(WEB, file), 'utf8');
    for (const [from, to] of edits[file] || []) {
      if (!src.includes(from)) throw new Error(`${file}: the test's edit no longer applies (${from.slice(0, 60)})`);
      src = src.replace(from, to);
    }
    const names = expose[file];
    if (names) {
      const end = src.lastIndexOf('})();');
      if (end < 0) throw new Error(`${file}: no closing })(); to expose its functions before`);
      src = src.slice(0, end) + `window.AnkiForest.__test = Object.assign(window.AnkiForest.__test || {}, { ${names.join(', ')} });\n` + src.slice(end);
    }
    vm.runInContext(src, ctx, { filename: path.join(WEB, file) });
  }
  return win;
}

// the scripts every forest loads, in order (catalog.SCRIPTS, read from catalog.py so the two never part)
export const SCRIPTS = (() => {
  const py = fs.readFileSync(path.join(WEB, '..', 'catalog.py'), 'utf8'), body = py.slice(py.indexOf('SCRIPTS = ('));
  return [...body.slice(0, body.indexOf('\n)')).matchAll(/"([^"]+\.js)"/g)].map(m => m[1]);
})();
export const BEFORE_CALENDAR = SCRIPTS.slice(0, SCRIPTS.indexOf('calendar.js'));

const DAY_MS = 86400000;
export const isoDay = ms => new Date(ms).toISOString().slice(0, 10);
/* a made-up calendar (payload.py's data.calendar) ending on `today` (an ISO date): `days` its reviews,
 * oldest first, today last */
export function calendar(today, days, more = {}) {
  const t = Date.UTC(+today.slice(0, 4), +today.slice(5, 7) - 1, +today.slice(8, 10));
  return { view: 'timeline', weekStart: 1, start: isoDay(t - (days.length - 1) * DAY_MS), days, due: [0], animals: [], marks: [], ...more };
}

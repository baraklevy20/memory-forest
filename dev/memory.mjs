/* What the forest holds in memory, and where.

    node dev/memory.mjs                          # aurora, 730 trees
    node dev/memory.mjs golden_lake 730 --still  # animations off
    node dev/memory.mjs aurora 730 --minutes 5   # and how it grows over five minutes
    node dev/memory.mjs aurora 730 --swaps 20    # after twenty redraws in place (a settings change)
    node dev/memory.mjs aurora 730 weather=snow  # the preset in other weather

In a headless Chrome (dev/profile_page.py builds the page), measured in steps: a blank page,
the page with the forest's scripts loaded, the forest built, then animating. Each step gives the
footprint of the page's renderer, the GPU process and the browser (what Activity Monitor
shows, from dev/rusage.py), and the JS heap. Then the canvases the forest made, with their
sizes, and the JS heap by what holds it (a heap snapshot). */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PYTHON = process.env.PYTHON || path.join(os.homedir(), '.pyenv/shims/python3');
const SETTLE_MS = 4000, ANIMATE_MS = 20000;

const args = process.argv.slice(2);
const flag = name => { const i = args.indexOf(name); return i < 0 ? null : args.splice(i, 2)[1]; };
const toggle = name => { const i = args.indexOf(name); if (i >= 0) args.splice(i, 1); return i >= 0; };
const still = toggle('--still');
const minutes = Number(flag('--minutes') || 0), swaps = Number(flag('--swaps') || 0);
const [preset = 'aurora', trees = '730', ...settings] = args;

const out = fs.mkdtempSync(path.join(os.tmpdir(), 'forest-memory-'));
const pageFile = path.join(out, 'page.html');
fs.writeFileSync(pageFile, execFileSync(PYTHON, [path.join(HERE, 'profile_page.py'), preset, trees, ...settings], { maxBuffer: 1 << 28 }).toString()
  .replace('"animations": true', `"animations": ${!still}`));

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: true, defaultViewport: { width: 900, height: 700 },
  args: ['--disable-extensions', '--disable-component-update', '--disable-background-networking', '--disable-sync',
    '--disable-default-apps', '--disable-features=Translate,OptimizationHints,MediaRouter', '--enable-precise-memory-info'],
});
const page = (await browser.pages())[0] || await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
// every canvas the page makes, and the line that made it
await page.evaluateOnNewDocument(() => {
  window.__canvases = [];
  const make = document.createElement;
  document.createElement = function (tag, ...a) {
    const el = make.call(this, tag, ...a);
    if (String(tag).toLowerCase() === 'canvas') {
      const line = (new Error().stack.split('\n')[2] || '').trim().replace(/^at /, '').replace(/\(?file:.*?(web\/)/, '$1').replace(/\)$/, '').replace(/:\d+$/, '');
      window.__canvases.push({ el: new WeakRef(el), line });
    }
    return el;
  };
});
const cdp = await page.createCDPSession(), bcdp = await browser.target().createCDPSession();
await cdp.send('Performance.enable');
const procs = async () => (await bcdp.send('SystemInfo.getProcessInfo')).processInfo;
const rusage = ids => JSON.parse(execFileSync(PYTHON, [path.join(HERE, 'rusage.py'), ...ids.map(String)]).toString());
const mb = b => (b / 1048576).toFixed(1).padStart(6) + 'MB';
const gc = async () => { await cdp.send('HeapProfiler.collectGarbage'); await new Promise(r => setTimeout(r, 300)); };

// the page's renderer: the one whose CPU moves while the page spins
const findRenderer = async () => {
  const a = await procs();
  await page.evaluate(() => { const end = performance.now() + 300; while (performance.now() < end); });
  const b = await procs();
  return b.filter(p => p.type === 'renderer').map(p => [p.id, p.cpuTime - ((a.find(q => q.id === p.id) || {}).cpuTime || 0)]).sort((x, y) => y[1] - x[1])[0][0];
};
let renderer = null;
const step = async label => {
  await gc();
  const ps = await procs(), gpu = (ps.find(p => p.type === 'GPU') || {}).id, br = (ps.find(p => p.type === 'browser') || {}).id;
  const r = rusage([renderer, gpu, br].filter(Boolean));
  const m = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(x => [x.name, x.value]));
  const row = { label, renderer: r[renderer].footprint, gpu: r[gpu].footprint, browser: r[br].footprint, heap: m.JSHeapUsedSize, nodes: m.Nodes };
  console.log(`${label.padEnd(26)} renderer ${mb(row.renderer)}  GPU ${mb(row.gpu)}  browser ${mb(row.browser)}  JS heap ${mb(row.heap)}  ${row.nodes} DOM nodes`);
  return row;
};

const dumpAllocators = async () => {
  const file = path.join(out, 'memory-trace.json');
  await page.tracing.start({ path: file, categories: ['disabled-by-default-memory-infra'] });
  await cdp.send('Tracing.requestMemoryDump').catch(() => bcdp.send('Tracing.requestMemoryDump'));
  await new Promise(r => setTimeout(r, 1500));
  await page.tracing.stop();
  const ev = JSON.parse(fs.readFileSync(file)).traceEvents;
  const pname = new Map(ev.filter(e => e.ph === 'M' && e.name === 'process_name').map(e => [e.pid, e.args.name]));
  const res = {};
  for (const e of ev.filter(e => e.ph === 'v' && e.args && e.args.dumps && e.args.dumps.allocators)) {
    const name = pname.get(e.pid) || e.pid, A = e.args.dumps.allocators, top = {};
    for (const [k, v] of Object.entries(A)) {
      const sz = v.attrs && v.attrs.size ? parseInt(v.attrs.size.value, 16) : 0;
      const parts = k.split('/');
      // the top level, and one level down for the big ones
      if (parts.length === 1) top[k] = (top[k] || 0) + sz;
      else if (parts.length === 2 && ['malloc', 'skia', 'gpu', 'v8', 'cc', 'partition_alloc', 'blink_gc', 'discardable', 'shared_memory', 'canvas'].includes(parts[0])) top[k] = (top[k] || 0) + sz;
    }
    res[name] = top;
  }
  return res;
};
// the page's renderer in a dump: the one named Renderer that is not Chrome's own UI
const pageAllocs = all => Object.entries(all).find(([k]) => k === 'Renderer') || [null, {}];
console.log(`${preset}, ${trees} trees${settings.length ? ' ' + settings.join(' ') : ''}, animations ${still ? 'off' : 'on'}  (footprints, after a garbage collection)\n`);
await page.goto('about:blank');
renderer = await findRenderer();
const blank = await step('blank page');
await page.goto('file://' + pageFile);
renderer = await findRenderer();  // a file page can get a renderer of its own
const loaded = await step('scripts loaded');
const aLoaded = pageAllocs(await dumpAllocators())[1];
await page.evaluate(() => AnkiForest.mount(document.getElementById('p'), window.D));
await new Promise(r => setTimeout(r, SETTLE_MS));
const built = await step('forest built');
const aBuilt = pageAllocs(await dumpAllocators())[1];
await new Promise(r => setTimeout(r, ANIMATE_MS));
const animated = await step(`after ${ANIMATE_MS / 1000}s ${still ? 'still' : 'animating'}`);
console.log(`\nwhat the forest adds over a blank page: renderer ${mb(animated.renderer - blank.renderer)}  GPU ${mb(animated.gpu - blank.gpu)}  browser ${mb(animated.browser - blank.browser)}`);
console.log(`  of which loading the scripts: renderer ${mb(loaded.renderer - blank.renderer)}; building the scene: renderer ${mb(built.renderer - loaded.renderer)}, GPU ${mb(built.gpu - loaded.gpu)}; animating: renderer ${mb(animated.renderer - built.renderer)}, GPU ${mb(animated.gpu - built.gpu)}`);

/* ---------- Chrome's own account, by allocator (memory-infra) ---------- */
const allocs = await dumpAllocators();
const aNow = pageAllocs(allocs)[1];
console.log('\nthe page\'s renderer, what grew by allocator (MB): building the scene | then animating');
[...new Set([...Object.keys(aBuilt), ...Object.keys(aNow)])].map(k => [k, (aBuilt[k] || 0) - (aLoaded[k] || 0), (aNow[k] || 0) - (aBuilt[k] || 0)])
  .filter(([, a, b]) => Math.abs(a) > 262144 || Math.abs(b) > 262144).sort((x, y) => y[1] - x[1])
  .forEach(([k, a, b]) => console.log(`  ${mb(a)} | ${mb(b)}  ${k}`));
for (const [proc, top] of Object.entries(allocs)) {
  if (!/Renderer|GPU/i.test(String(proc))) continue;
  console.log(`\n${proc}, by allocator (Chrome's memory-infra; sub-allocators indented):`);
  Object.entries(top).filter(([k, v]) => !k.includes('/') && v > 262144).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
    console.log(`  ${mb(v)}  ${k}`);
    Object.entries(top).filter(([kk, vv]) => kk.startsWith(k + '/') && vv > 262144).sort((a, b) => b[1] - a[1]).slice(0, 5)
      .forEach(([kk, vv]) => console.log(`      ${mb(vv)}  ${kk}`));
  });
}

/* ---------- the canvases ---------- */
const canvases = await page.evaluate(() => {
  const main = document.querySelector('.af-canvas');
  const all = window.__canvases.map(c => ({ c: c.el.deref(), line: c.line })).filter(x => x.c);
  if (main && !all.some(x => x.c === main)) all.push({ c: main, line: 'the page (core.js mount)' });
  return all.map(({ c, line }) => {
    let attrs = {};
    try { attrs = c.getContext('2d').getContextAttributes(); } catch { /* another kind */ }
    return { line, w: c.width, h: c.height, onPage: c.isConnected, cpu: Boolean(attrs.willReadFrequently) };
  });
});
const groups = new Map();
for (const c of canvases) {
  const k = `${c.line}${c.onPage ? ' (on the page)' : ''}${c.cpu ? ' [CPU]' : ''}`;
  const g = groups.get(k) || { n: 0, px: 0, sizes: new Set() };
  g.n++; g.px += c.w * c.h; g.sizes.add(`${c.w}x${c.h}`); groups.set(k, g);
}
const totalPx = canvases.reduce((a, c) => a + c.w * c.h, 0);
const made = await page.evaluate(() => window.__canvases.length);
console.log(`\n${made} canvases made, ${canvases.length} still alive, ${mb(totalPx * 4)} of pixels (4 bytes each), by the line that made them:`);
[...groups].sort((a, b) => b[1].px - a[1].px).forEach(([k, g]) =>
  console.log(`  ${mb(g.px * 4)}  ${String(g.n).padStart(3)} x  ${[...g.sizes].slice(0, 3).join(', ').padEnd(26)} ${k}`));

/* ---------- the JS heap, by what holds it ---------- */
const chunks = [];
cdp.on('HeapProfiler.addHeapSnapshotChunk', e => chunks.push(e.chunk));
await cdp.send('HeapProfiler.takeHeapSnapshot', { reportProgress: false });
const snap = JSON.parse(chunks.join(''));
const F = snap.snapshot.meta.node_fields, T = snap.snapshot.meta.node_types[0], N = F.length;
const iType = F.indexOf('type'), iName = F.indexOf('name'), iSize = F.indexOf('self_size');
const bySize = new Map();
let heapTotal = 0;
for (let i = 0; i < snap.nodes.length; i += N) {
  const type = T[snap.nodes[i + iType]], name = snap.strings[snap.nodes[i + iName]], size = snap.nodes[i + iSize];
  heapTotal += size;
  // objects by their constructor; strings, code, arrays and the rest by kind
  const k = type === 'object' || type === 'native' ? `${type}: ${name.slice(0, 50)}` : type;
  bySize.set(k, (bySize.get(k) || 0) + size);
}
fs.writeFileSync(path.join(out, `${preset}.heapsnapshot`), chunks.join(''));
console.log(`\nJS heap snapshot: ${mb(heapTotal)}, the biggest holders (self size):`);
[...bySize].sort((a, b) => b[1] - a[1]).slice(0, 18).forEach(([k, s]) => console.log(`  ${mb(s)}  ${k}`));

/* ---------- over time, and over redraws in place ---------- */
for (let i = 1; i <= minutes * 2; i++) {
  await new Promise(r => setTimeout(r, 30000));
  await step(`  +${i * 30}s`);
}
for (let i = 1; i <= swaps; i++) {
  await page.evaluate(() => { const root = document.getElementById('p'); root.afSwap(JSON.parse(JSON.stringify(window.D)), []); });
  await new Promise(r => setTimeout(r, 1500));
  if (i % 10 === 0 || i === swaps) await step(`after ${i} redraws`);
}
if (errors.length) console.log('\nERRORS: ' + errors.join(' | '));
console.log(`\nheap snapshot: ${path.join(out, preset + '.heapsnapshot')} (DevTools > Memory > Load)`);
await browser.close();

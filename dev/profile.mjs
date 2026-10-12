/* Where the forest's CPU and memory go once it is drawn and only animating.

    node dev/profile.mjs                       # aurora, 730 trees, 15s
    node dev/profile.mjs starry_night 300 --secs 30
    node dev/profile.mjs aurora 730 --still    # animations off, for the floor
    node dev/profile.mjs aurora 730 weather=snow time_of_day=day  # the preset in other weather
    node dev/profile.mjs aurora 730 --minutes 10  # memory over a long run, sampled each 10s
    node dev/profile.mjs aurora 730 --changes  # how much of each frame differs from the last
    node dev/profile.mjs aurora 730 --calls    # each line that draws on the forest, and how much
                                               # of what it draws is the same as the frame before
    node dev/profile.mjs aurora 730 --inject try.js  # with try.js run once it is mounted (a patch to try)
    node dev/profile.mjs aurora 730 --quick    # CPU and canvas calls only, for a sweep of the
                                               # presets base and Plus ship:
    for p in golden_lake misty_valley cherry_blossom starry_night aurora lanterns frozen_market \
      pumpkin_patch bamboo synthwave; do node dev/profile.mjs $p 730 --quick | grep SUMMARY; done

Mounts one forest (dev/profile_page.py) in a headless Chrome, which on a Mac still draws
with the GPU as Anki does (--headed shows the window), waits for it to settle, then measures:

  - CPU per Chrome process (browser, renderer, GPU), from the processes' own CPU time
  - the JS that runs, from a sampling profile: self time by function and file
  - each part of a frame (sky effects, the engine, visitors, events...), timed by wrapping
    those functions, and how many canvas calls a frame makes
  - memory: the JS heap and each process's resident size, at the start and the end

The .cpuprofile it writes opens in Chrome DevTools (Performance > Load profile). */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PYTHON = process.env.PYTHON || path.join(os.homedir(), '.pyenv/shims/python3');
const SETTLE_MS = 4000;  // the build, the first frames, and the resize rebuild
const SECTION_MS = 5000;  // the instrumented pass, after the clean one
const SAMPLE_US = 200;  // the profiler's sampling interval

const args = process.argv.slice(2);
const flag = name => { const i = args.indexOf(name); return i < 0 ? null : args.splice(i, 2)[1]; };
const toggle = name => { const i = args.indexOf(name); if (i >= 0) args.splice(i, 1); return i >= 0; };
const headed = toggle('--headed'), still = toggle('--still'), quick = toggle('--quick'), changes = toggle('--changes'), calls = toggle('--calls');
const minutes = Number(flag('--minutes') || 0);
const inject = flag('--inject');  // a script run once the forest is mounted, to try a change without making it
const secs = Number(flag('--secs') || (quick ? 8 : 15));
// anything after the preset and the tree count is a setting to draw it with: weather=rain time_of_day=night
const [preset = 'aurora', trees = '730', ...settings] = args;

const out = fs.mkdtempSync(path.join(os.tmpdir(), 'forest-profile-'));
const html = execFileSync(PYTHON, [path.join(HERE, 'profile_page.py'), preset, trees, ...settings], { maxBuffer: 1 << 28 }).toString()
  .replace('"animations": true', `"animations": ${!still}`);
const pageFile = path.join(out, 'page.html');
fs.writeFileSync(pageFile, html);

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: !headed, defaultViewport: headed ? null : { width: 900, height: 700 },
  // a covered or background window would stop the loop; Anki's panel is in front
  args: ['--window-size=900,700', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
    '--disable-background-timer-throttling', '--no-first-run', '--no-default-browser-check',
    '--enable-precise-memory-info',
    // Chrome's own background work, which would otherwise be counted in with the forest's
    '--disable-extensions', '--disable-component-update', '--disable-background-networking', '--disable-sync',
    '--disable-default-apps', '--disable-features=Translate,OptimizationHints,MediaRouter'],
});
const page = (await browser.pages())[0] || await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e.stack || e)));
await page.goto('file://' + pageFile);
await page.evaluate(() => AnkiForest.mount(document.getElementById('p'), window.D));
if (inject) await page.evaluate(fs.readFileSync(inject, 'utf8'));
await new Promise(r => setTimeout(r, SETTLE_MS));

const cdp = await page.createCDPSession();
const browserCdp = await browser.target().createCDPSession();
const procs = async () => (await browserCdp.send('SystemInfo.getProcessInfo')).processInfo;
await cdp.send('Performance.enable');
// inline scripts are named by their sourceURL only in the debugger's view: scriptId -> name
const scriptNames = new Map();
// (and an inline script's lines count from the top of the page)
cdp.on('Debugger.scriptParsed', e => { if (e.url) scriptNames.set(e.scriptId, { name: e.url.replace(/^.*?(web\/)/, '$1'), line: e.startLine }); });
await cdp.send('Debugger.enable');
// the page's own renderer: the one whose CPU time moves while the page spins for a moment
const pageRenderer = await (async () => {
  const a = await procs();
  await page.evaluate(() => { const end = performance.now() + 300; while (performance.now() < end); });
  const b = await procs();
  const moved = b.filter(p => p.type === 'renderer').map(p => [p.id, p.cpuTime - (a.find(q => q.id === p.id) || { cpuTime: 0 }).cpuTime]);
  return moved.sort((x, y) => y[1] - x[1])[0][0];
})();

const rss = pid => { try { return Number(execFileSync('ps', ['-o', 'rss=', '-p', String(pid)]).toString().trim()) * 1024; } catch { return 0; } };
const memory = async () => {
  const m = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(x => [x.name, x.value]));
  const ps = await procs();
  return { heap: m.JSHeapUsedSize, heapTotal: m.JSHeapTotalSize, nodes: m.Nodes, listeners: m.JSEventListeners,
    procs: ps.map(p => ({ type: p.type, id: p.id, rss: rss(p.id) })) };
};
const mb = b => (b / 1048576).toFixed(1) + 'MB';
const MEMORY_OF = ['browser', 'renderer', 'GPU'];  // the rest are Chrome's services, not the forest's
const showMemory = (label, m) => {
  const shown = m.procs.filter(p => MEMORY_OF.includes(p.type) && (p.type !== 'renderer' || p.id === pageRenderer));
  console.log(`${label}: JS heap ${mb(m.heap)} (of ${mb(m.heapTotal)}), ${m.nodes} DOM nodes, ${m.listeners} listeners; resident `
    + shown.map(p => `${p.type === 'renderer' ? 'forest renderer' : p.type} ${mb(p.rss)}`).join(', '));
};

const attrs = await page.evaluate(() => { const c = document.querySelector('.af-canvas'); return c ? c.getContext('2d').getContextAttributes() : {}; });
console.log(`${preset}, ${trees} trees, animations ${still ? 'off' : 'on'}, canvas ${JSON.stringify(attrs)}${errors.length ? ', ERRORS: ' + errors.join(' | ') : ''}\n`);
const mem0 = await memory();
showMemory('memory at start', mem0);
/* ---------- who draws on the forest, and how much of it is the same each frame ---------- */
if (calls) {
  const r = await page.evaluate(ms => new Promise(done => {
    const c = document.querySelector('.af-canvas'), main = c.getContext('2d'), P = CanvasRenderingContext2D.prototype;
    const by = {}, orig = {};
    let frames = 0, cur = new Map(), prev = new Map();
    // the frame's draws, by the line that made them: a list of what each drew
    const endFrame = () => {
      for (const [line, sigs] of cur) {
        const b = by[line] || (by[line] = { n: 0, same: 0, fns: new Set() });
        b.n += sigs.length;
        const was = new Map();
        (prev.get(line) || []).forEach(x => was.set(x, (was.get(x) || 0) + 1));
        sigs.forEach(x => { const k = was.get(x); if (k) { b.same++; was.set(x, k - 1); } });
      }
      prev = cur; cur = new Map(); frames++;
    };
    ['fillRect', 'drawImage', 'putImageData', 'fill', 'stroke', 'fillText', 'clearRect'].forEach(m => {
      const fn = orig[m] = P[m];
      P[m] = function (...a) {
        if (this === main) {
          if (m === 'clearRect') endFrame();
          else {
            const line = (new Error().stack.split('\n')[2] || '').trim().replace(/^at /, '').replace(/\(?file:.*?(web\/)/, '$1').replace(/\)$/, '').replace(/:\d+$/, '');
            // what it draws: the call, its numbers and the paint (an image by its size)
            const sig = m + a.map(x => typeof x === 'object' && x ? `${x.width}x${x.height}` : x).join(',') + '|' + this.fillStyle + '|' + this.globalAlpha + '|' + this.globalCompositeOperation;
            if (!cur.has(line)) cur.set(line, []);
            cur.get(line).push(sig);
          }
        }
        return fn.apply(this, a);
      };
    });
    setTimeout(() => {
      Object.assign(P, orig);
      done({ frames: frames - 1, by: Object.entries(by).map(([line, b]) => ({ line, n: b.n, same: b.same })) });
    }, ms);
  }), 4000);
  const f = Math.max(1, r.frames), total = r.by.reduce((a, b) => a + b.n, 0), same = r.by.reduce((a, b) => a + b.same, 0);
  console.log(`\n${r.frames} frames: ${Math.round(total / f)} draws a frame, ${Math.round(same / f)} (${(100 * same / Math.max(1, total)).toFixed(0)}%) the same as the frame before`);
  console.log('   per frame   same   line');
  r.by.sort((a, b) => b.n - a.n).slice(0, 30).forEach(b =>
    console.log(`  ${(b.n / f).toFixed(0).padStart(8)}  ${(100 * b.same / b.n).toFixed(0).padStart(4)}%   ${b.line}`));
  await browser.close(); process.exit(0);
}

/* ---------- how much each frame changes (reads every frame back: slow, so on its own) ---------- */
if (changes) {
  const r = await page.evaluate(ms => new Promise(done => {
    const c = document.querySelector('.af-canvas'), g = c.getContext('2d'), clear = g.clearRect;
    let prev = null;
    const frames = [];
    // a frame starts by clearing the canvas: what is on it then is the frame before, finished
    g.clearRect = function (...a) {
      const d = g.getImageData(0, 0, c.width, c.height).data;
      if (prev && prev.length === d.length) {
        let n = 0, x0 = c.width, y0 = c.height, x1 = -1, y1 = -1;
        for (let i = 0; i < d.length; i += 4) {
          if (d[i] !== prev[i] || d[i + 1] !== prev[i + 1] || d[i + 2] !== prev[i + 2] || d[i + 3] !== prev[i + 3]) {
            n++; const p = i / 4, x = p % c.width, y = (p / c.width) | 0;
            if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
          }
        }
        frames.push({ n, box: n ? (x1 - x0 + 1) * (y1 - y0 + 1) : 0 });
      }
      prev = d;
      return clear.apply(this, a);
    };
    // then the same again with one part of the frame moving and the clock stopped for the
    // rest, part by part, to see which of them change pixels
    const AF = window.AnkiForest, E = AF.engines.pixel, T0 = performance.now() / 1000;
    const parts = { 'fx.back': [AF.fx, 'back', 2], 'fx.front': [AF.fx, 'front', 2], drawFlyers: [AF, 'drawFlyers', 2],
      drawVisitors: [AF, 'drawVisitors', 2], 'engine.frame': [E, 'frame', 2], 'engine.frameBack': [E, 'frameBack', 2],
      'events.run': [AF.events, 'run', 3] };
    const orig = {}, by = {};
    Object.entries(parts).forEach(([k, [o, m]]) => { orig[k] = o[m]; });
    const only = live => Object.entries(parts).forEach(([k, [o, m, ti]]) => {
      if (typeof orig[k] !== 'function') return;
      o[m] = k === live ? orig[k] : function (...a) { a[ti] = T0; return orig[k].apply(this, a); };
    });
    const runs = [...Object.keys(parts), '(none: what is left)'];
    const next = i => {
      if (i === runs.length) { only(null); Object.entries(parts).forEach(([k, [o, m]]) => { if (orig[k]) o[m] = orig[k]; }); g.clearRect = clear; done({ frames, by, W: c.width, H: c.height }); return; }
      only(runs[i]);
      const start = frames.length;
      setTimeout(() => { by[runs[i]] = frames.slice(start + 1); next(i + 1); }, 3000);
    };
    setTimeout(() => { by.all = frames.slice(); next(0); }, ms);
  }), secs * 1000);
  const F = r.by.all, px = r.W * r.H, same = F.filter(f => !f.n).length;
  const med = a => { const s = [...a].sort((x, y) => x - y); return s[s.length >> 1] || 0; };
  console.log(`\n${F.length} frames of ${r.W}x${r.H} (${px} pixels):`);
  console.log(`  identical to the one before: ${same} (${(100 * same / F.length).toFixed(0)}%)`);
  console.log(`  pixels changed, median ${med(F.map(f => f.n))}, max ${Math.max(...F.map(f => f.n))}`);
  console.log('  changed pixels per frame: ' + F.slice(0, 45).map(f => f.n).join(' '));
  console.log(`SUMMARY ${preset.padEnd(18)} ${r.W}x${r.H}  identical ${(100 * same / F.length).toFixed(0).padStart(3)}%  changed px median ${String(med(F.map(f => f.n))).padStart(6)} (${(100 * med(F.map(f => f.n)) / px).toFixed(2)}%)  box median ${(100 * med(F.map(f => f.box)) / px).toFixed(0).padStart(3)}%`);
  console.log('  with only one part moving (the rest frozen):');
  Object.entries(r.by).filter(([k]) => k !== 'all').forEach(([k, fr]) => {
    const moved = fr.filter(f => f.n);
    console.log(`    ${k.padEnd(22)} changes ${String(moved.length).padStart(3)}/${fr.length} frames, median ${String(med(fr.map(f => f.n))).padStart(5)} px, mean ${String(Math.round(fr.reduce((a, f) => a + f.n, 0) / Math.max(1, fr.length))).padStart(5)} px`);
  });
  await browser.close(); process.exit(0);
}

/* ---------- the clean pass: CPU per process, with nothing else watching ---------- */
// and the hardware counters of the forest's renderer and the GPU (dev/rusage.py): instructions
// retired hardly move with the machine's load, where CPU % does
const counted = async () => {
  const ids = [pageRenderer, ((await procs()).find(p => p.type === 'GPU') || {}).id].filter(Boolean);
  return JSON.parse(execFileSync(PYTHON, [path.join(HERE, 'rusage.py'), ...ids.map(String)]).toString());
};
const framesNow = () => page.evaluate(() => { const env = document.getElementById('p').afEnv; return env ? env.frames || 0 : 0; });
await page.evaluate(() => {  // count the frames drawn: a frame begins by clearing the forest's canvas
  const g = document.querySelector('.af-canvas').getContext('2d'), clear = g.clearRect;
  g.clearRect = function (...a) { const env = document.getElementById('p').afEnv; if (env) env.frames = (env.frames || 0) + 1; return clear.apply(this, a); };
});
const before = await procs(), c0 = await counted(), n0 = await framesNow();
let t0 = performance.now();
await new Promise(r => setTimeout(r, secs * 1000));
const after = await procs(), c1 = await counted(), n1 = await framesNow();
let wall = (performance.now() - t0) / 1000;
const insOf = id => c1[id] && c0[id] ? c1[id].instructions - c0[id].instructions : 0;
const gpuId = (after.find(p => p.type === 'GPU') || {}).id;
const ins = insOf(pageRenderer) + insOf(gpuId), drawn = n1 - n0;

console.log(`\nCPU over ${wall.toFixed(1)}s (% of one core):`);
let total = 0;
after.forEach(p => {
  const b = before.find(q => q.id === p.id);
  const pct = 100 * (p.cpuTime - (b ? b.cpuTime : 0)) / wall;
  total += pct;
  if (pct >= 0.05) console.log(`  ${(p.id === pageRenderer ? 'forest renderer' : p.type).padEnd(16)} pid ${String(p.id).padEnd(7)} ${pct.toFixed(1).padStart(5)}%`);
});
console.log(`  ${'total'.padEnd(28)} ${total.toFixed(1).padStart(5)}%`);
// in Anki the page's renderer and the GPU are what the forest costs (QtWebEngine runs the GPU
// in Anki's own process); the browser and the rest are Chrome's
const cpuOf = id => { const a = after.find(p => p.id === id), b = before.find(p => p.id === id); return a && b ? 100 * (a.cpuTime - b.cpuTime) / wall : 0; };
const rendererPct = cpuOf(pageRenderer), gpuPct = cpuOf((after.find(p => p.type === 'GPU') || {}).id);
console.log(`  forest = renderer + GPU    ${(rendererPct + gpuPct).toFixed(1).padStart(5)}%`);
console.log(`instructions: ${(ins / wall / 1e6).toFixed(0)}M a second (renderer ${(insOf(pageRenderer) / wall / 1e6).toFixed(0)}M, GPU ${(insOf(gpuId) / wall / 1e6).toFixed(0)}M), ${drawn} frames (${(drawn / wall).toFixed(1)}/s), ${(ins / Math.max(1, drawn) / 1e6).toFixed(2)}M a frame`);

/* ---------- a sampling profile of the JS ---------- */
if (!quick) {
await cdp.send('Profiler.enable');
await cdp.send('Profiler.setSamplingInterval', { interval: SAMPLE_US });
t0 = performance.now();
await cdp.send('Profiler.start');
await new Promise(r => setTimeout(r, secs * 1000));
const { profile } = await cdp.send('Profiler.stop');
wall = (performance.now() - t0) / 1000;
fs.writeFileSync(path.join(out, `${preset}.cpuprofile`), JSON.stringify(profile));
// self time per node, summed by function and place
const dt = {}, byId = new Map(profile.nodes.map(n => [n.id, n]));
profile.samples.forEach((id, i) => { dt[id] = (dt[id] || 0) + (profile.timeDeltas[i] || 0); });
const self = new Map(), files = new Map();
let busy = 0;
for (const [id, us] of Object.entries(dt)) {
  const f = byId.get(Number(id)).callFrame;
  if (f.functionName === '(idle)') continue;
  busy += us;
  const script = scriptNames.get(f.scriptId), file = script ? script.name : '';
  const key = `${f.functionName || '(anonymous)'}  ${file}${file ? ':' + (f.lineNumber - script.line + 1) : ''}`;
  self.set(key, (self.get(key) || 0) + us);
  const fk = file || f.functionName;
  files.set(fk, (files.get(fk) || 0) + us);
}
const pctOf = us => (100 * us / (wall * 1e6)).toFixed(2).padStart(6) + '%';
console.log(`\nrenderer main thread busy ${pctOf(busy)} of the time; by file (self time):`);
[...files].sort((a, b) => b[1] - a[1]).slice(0, 12).forEach(([k, us]) => console.log(`  ${pctOf(us)}  ${k}`));
console.log('\nhottest functions (self time):');
[...self].sort((a, b) => b[1] - a[1]).slice(0, 25).forEach(([k, us]) => console.log(`  ${pctOf(us)}  ${k}`));
}

/* ---------- the instrumented pass: each part of a frame, and canvas calls ---------- */
const sections = await page.evaluate(ms => new Promise(done => {
  const AF = window.AnkiForest, times = {}, counts = {};
  let frames = 0;
  const wrap = (obj, name, label, perArg) => {
    const fn = obj && obj[name];
    if (typeof fn !== 'function') return;
    obj[name] = function (...a) {
      const s = performance.now();
      try { return fn.apply(this, a); } finally {
        const k = perArg ? `${label}(${a[0]})` : label;
        times[k] = (times[k] || 0) + performance.now() - s;
      }
    };
  };
  const E = AF.engines.pixel;
  wrap(E, 'frame', 'engine.frame'); wrap(E, 'frameBack', 'engine.frameBack');
  wrap(AF.fx, 'back', 'fx.back'); wrap(AF.fx, 'front', 'fx.front');
  wrap(AF, 'drawFlyers', 'drawFlyers'); wrap(AF, 'drawVisitors', 'drawVisitors');
  wrap(AF.events, 'run', 'events.run', true);
  const env = document.getElementById('p').afEnv;
  if (env && env.quantize) wrap(env, 'quantize', 'quantize');
  // a frame starts with clearRect on the main canvas: count it, and every canvas call
  const P = CanvasRenderingContext2D.prototype;
  const main = document.querySelector('.af-canvas').getContext('2d');
  ['fillRect', 'drawImage', 'clearRect', 'getImageData', 'putImageData', 'fill', 'stroke', 'arc', 'fillText', 'createImageData'].forEach(m => {
    const fn = P[m];
    P[m] = function (...a) {
      const k = (this === main ? 'main.' : 'offscreen.') + m;
      counts[k] = (counts[k] || 0) + 1;
      return fn.apply(this, a);
    };
  });
  const env0 = document.getElementById('p').afEnv, f0 = env0 ? env0.frames || 0 : 0;
  setTimeout(() => { const e = document.getElementById('p').afEnv; frames = (e ? e.frames || 0 : 0) - f0; done({ times, counts, frames, ms }); }, ms);
}), quick ? 2000 : SECTION_MS);

const f = Math.max(1, sections.frames);
console.log(`\n${sections.frames} frames in ${sections.ms / 1000}s (${(sections.frames / (sections.ms / 1000)).toFixed(1)}/s); per frame:`);
Object.entries(sections.times).sort((a, b) => b[1] - a[1])
  .forEach(([k, t]) => console.log(`  ${(t / f).toFixed(3).padStart(7)}ms  ${k}`));
console.log('canvas calls per frame:');
Object.entries(sections.counts).sort((a, b) => b[1] - a[1])
  .forEach(([k, n]) => console.log(`  ${(n / f).toFixed(0).padStart(7)}  ${k}`));
const perFrame = k => Math.round((sections.counts[k] || 0) / f);
console.log(`SUMMARY ${preset.padEnd(18)} ${String((ins / wall / 1e6).toFixed(0)).padStart(4)}M instr/s  ${(drawn / wall).toFixed(1).padStart(4)} fps  ${(ins / Math.max(1, drawn) / 1e6).toFixed(2)}M/frame  CPU ${(rendererPct + gpuPct).toFixed(1).padStart(5)}%  fillRect/frame ${String(perFrame('main.fillRect')).padStart(6)}  drawImage/frame ${perFrame('main.drawImage')}`);
if (quick) { await browser.close(); process.exit(0); }

/* ---------- a trace: where the time goes off the JS thread ---------- */
// every task each thread ran (toplevel), by thread, with the work inside the busiest ones
const traceFile = path.join(out, `${preset}.trace.json`);
await page.tracing.start({ path: traceFile, categories: ['toplevel', 'cc', 'gpu', 'viz', 'blink', 'v8',
  'disabled-by-default-devtools.timeline', 'disabled-by-default-skia', 'disabled-by-default-gpu.service'] });
await new Promise(r => setTimeout(r, SECTION_MS));
await page.tracing.stop();
const events = JSON.parse(fs.readFileSync(traceFile)).traceEvents;
const threadName = new Map(), procName = new Map();
events.filter(e => e.ph === 'M').forEach(e => {
  if (e.name === 'thread_name') threadName.set(`${e.pid}:${e.tid}`, e.args.name);
  if (e.name === 'process_name') procName.set(e.pid, e.args.name);
});
// self time: an event's own time, less the events nested inside it on the same thread
const threads = new Map(), byThread = new Map();
events.filter(e => e.ph === 'X' && e.dur).forEach(e => {
  const k = `${e.pid}:${e.tid}`;
  if (!byThread.has(k)) byThread.set(k, []);
  byThread.get(k).push(e);
});
for (const [k, list] of byThread) {
  const t = { task: 0, names: new Map() };
  threads.set(k, t);
  list.sort((a, b) => a.ts - b.ts || b.dur - a.dur);
  const stack = [];
  const close = e => { if (e.name !== 'ThreadControllerImpl::RunTask' && e.name !== 'ThreadPool_RunTask') t.names.set(e.name, (t.names.get(e.name) || 0) + e.self); };
  for (const e of list) {
    while (stack.length && stack[stack.length - 1].ts + stack[stack.length - 1].dur <= e.ts) close(stack.pop());
    e.self = e.dur;
    if (stack.length) stack[stack.length - 1].self -= e.dur; else t.task += e.dur;
    stack.push(e);
  }
  while (stack.length) close(stack.pop());
}
const traceUs = SECTION_MS * 1000;
console.log(`\nthreads by busy time, and the events that own it (self time; trace, ${SECTION_MS / 1000}s, % of one core):`);
[...threads].filter(([, t]) => t.task / traceUs > 0.002).sort((a, b) => b[1].task - a[1].task).slice(0, 10).forEach(([k, t]) => {
  const pid = Number(k.split(':')[0]);
  console.log(`  ${(100 * t.task / traceUs).toFixed(1).padStart(5)}%  ${procName.get(pid) || pid} / ${threadName.get(k) || k}`);
  [...t.names].sort((a, b) => b[1] - a[1]).slice(0, 8)
    .forEach(([n, us]) => console.log(`           ${(100 * us / traceUs).toFixed(2).padStart(5)}%  ${n}`));
});

/* ---------- memory: now, and over a long run if asked ---------- */
showMemory('\nmemory after', await memory());
for (let i = 1; i <= minutes * 6; i++) {
  await new Promise(r => setTimeout(r, 10000));
  showMemory(`  +${i * 10}s`, await memory());
}

console.log(`\nprofile: ${path.join(out, preset + '.cpuprofile')}, trace: ${traceFile} (DevTools > Performance > Load profile)`);
await browser.close();

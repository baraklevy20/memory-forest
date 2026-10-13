/* Catch a change that makes the forest cost more CPU or memory than it did.

    npm run perf:baseline                       # measure every scene, and keep the numbers
    npm run perf                                # measure again, and fail on any scene that got worse
    node dev/perf_check.mjs compare --only aurora,golden_lake-rain

Each scene is drawn in a headless Chrome (dev/profile_page.py builds the page) and measured
on what it costs once built and animating:

  instructions  CPU instructions a second, the forest's renderer and the GPU process together,
                from the processes' hardware counters (dev/rusage.py). Unlike CPU %, these
                hardly move with whatever else the machine is doing (a few percent run to run).
  fps           frames drawn a second: 10 for a calm scene, 15 for one with anything fast
                in it (AF.busy). A calm scene drawn at 15 costs half as much again.
  memory        the footprint the forest's renderer adds over a blank page, after a garbage
                collection (what Activity Monitor shows; a few MB run to run), and the JS heap.

A scene fails when it is worse than the baseline by more than the margins below. A failing
scene is measured once more and the better of the two counts, as one run can be unlucky.
The numbers belong to this machine and this Chrome: the baseline is not in git (like
render_baseline.json), and it says so when the Chrome it was made with has changed. Needs
macOS (the hardware counters) and Chrome. */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PYTHON = process.env.PYTHON || path.join(os.homedir(), '.pyenv/shims/python3');
const BASELINE = path.join(HERE, 'perf_baseline.json');
const TREES = 730;
// a scene fails above these: instructions by a share (and at least an absolute amount, so a
// cheap scene's small wobble is not a failure), memory by MB
const MAX_INSTR_UP = 0.15, MIN_INSTR_UP = 8e6, MAX_RENDERER_MB_UP = 8, MAX_HEAP_MB_UP = 2, MAX_FPS_OFF = 1;
// built, then settled (a resize rebuild, the first frames), then measured for
const SETTLE_MS = 4000, MEASURE_MS = 8000;

// every preset some edition ships, as it comes (a new one joins by itself, measured from its
// first run: record it with perf:baseline -- --only <it>), then the conditions that cost the
// most: rain and snow (15 frames a second and hundreds of drops), night, the biggest forest, and
// the forest without the study calendar under it (every other scene has one, as it is in Anki)
const shipped = JSON.parse(execFileSync(PYTHON, [path.join(HERE, 'profile_page.py'), '--shipped']).toString());
const SCENES = [
  ...shipped.map(p => ({ name: p, preset: p })),
  { name: 'golden_lake-rain', preset: 'golden_lake', settings: ['weather=rain'] },
  { name: 'golden_lake-snow', preset: 'golden_lake', settings: ['weather=snow'] },
  { name: 'golden_lake-night', preset: 'golden_lake', settings: ['time_of_day=night'] },
  { name: 'golden_lake-no-calendar', preset: 'golden_lake', settings: ['calendar=off'] },
  { name: 'aurora-5000-trees', preset: 'aurora', trees: 5000 },
];

const rusage = ids => JSON.parse(execFileSync(PYTHON, [path.join(HERE, 'rusage.py'), ...ids.map(String)]).toString());
const MB = 1048576;

async function measure(scene) {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'forest-perf-'));
  const pageFile = path.join(out, 'page.html');
  fs.writeFileSync(pageFile, execFileSync(PYTHON, [path.join(HERE, 'profile_page.py'), scene.preset, String(scene.trees || TREES), ...(scene.settings || [])],
    { maxBuffer: 1 << 28 }));
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: true, defaultViewport: { width: 900, height: 700 },
    args: ['--disable-extensions', '--disable-component-update', '--disable-background-networking', '--disable-sync',
      '--disable-default-apps', '--disable-features=Translate,OptimizationHints,MediaRouter'],
  });
  try {
    const page = (await browser.pages())[0] || await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    const cdp = await page.createCDPSession(), bcdp = await browser.target().createCDPSession();
    await cdp.send('Performance.enable');
    const procs = async () => (await bcdp.send('SystemInfo.getProcessInfo')).processInfo;
    const gpu = async () => ((await procs()).find(p => p.type === 'GPU') || {}).id;
    // the page's renderer: the one whose CPU moves while the page spins
    const renderer = async () => {
      const a = await procs();
      await page.evaluate(() => { const end = performance.now() + 300; while (performance.now() < end); });
      const b = await procs();
      return b.filter(p => p.type === 'renderer').map(p => [p.id, p.cpuTime - ((a.find(q => q.id === p.id) || {}).cpuTime || 0)]).sort((x, y) => y[1] - x[1])[0][0];
    };
    const footprint = async id => { await cdp.send('HeapProfiler.collectGarbage'); return rusage([id])[id].footprint; };

    await page.goto('about:blank');
    const blank = await footprint(await renderer());
    await page.goto('file://' + pageFile);
    await page.evaluate(() => {
      // count the frames drawn: each begins by clearing the forest's canvas
      window.__frames = 0;
      const get = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (...a) {
        const g = get.apply(this, a);
        if (g && this.classList.contains('af-canvas') && !g.__counted) {
          const clear = g.clearRect; g.clearRect = function (...b) { window.__frames++; return clear.apply(this, b); }; g.__counted = true;
        }
        return g;
      };
      AnkiForest.mount(document.getElementById('p'), window.D);
    });
    await new Promise(r => setTimeout(r, SETTLE_MS));
    const rid = await renderer(), gid = await gpu();
    const c0 = rusage([rid, gid]), f0 = await page.evaluate(() => window.__frames), t0 = Date.now();
    await new Promise(r => setTimeout(r, MEASURE_MS));
    const c1 = rusage([rid, gid]), f1 = await page.evaluate(() => window.__frames), secs = (Date.now() - t0) / 1000;
    const instr = [rid, gid].reduce((a, id) => a + (c1[id].instructions - c0[id].instructions), 0) / secs;
    const rendererMb = (await footprint(rid) - blank) / MB;
    const heapMb = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value])).JSHeapUsedSize / MB;
    return { instr, fps: (f1 - f0) / secs, rendererMb, heapMb, errors };
  } finally {
    await browser.close();
  }
}

/* worse than the baseline by more than the margins: a list of what is, empty when nothing */
function worse(now, was) {
  const out = [];
  const up = now.instr - was.instr;
  if (up > Math.max(was.instr * MAX_INSTR_UP, MIN_INSTR_UP)) out.push(`instructions +${Math.round(100 * up / was.instr)}%`);
  if (Math.abs(now.fps - was.fps) > MAX_FPS_OFF) out.push(`${was.fps.toFixed(0)} -> ${now.fps.toFixed(0)} fps`);
  if (now.rendererMb - was.rendererMb > MAX_RENDERER_MB_UP) out.push(`renderer +${(now.rendererMb - was.rendererMb).toFixed(1)}MB`);
  if (now.heapMb - was.heapMb > MAX_HEAP_MB_UP) out.push(`JS heap +${(now.heapMb - was.heapMb).toFixed(1)}MB`);
  if (now.errors.length) out.push('errors: ' + now.errors[0].slice(0, 80));
  return out;
}
/* the better of two runs, measure by measure */
const better = (a, b) => ({ instr: Math.min(a.instr, b.instr), fps: Math.abs(a.fps - b.fps) < 0.01 ? a.fps : b.fps,
  rendererMb: Math.min(a.rendererMb, b.rendererMb), heapMb: Math.min(a.heapMb, b.heapMb), errors: a.errors.length ? b.errors : a.errors });

const row = (name, m, note = '') => `${name.padEnd(20)} ${(m.instr / 1e6).toFixed(0).padStart(5)}M instr/s  ${m.fps.toFixed(1).padStart(4)} fps  `
  + `renderer +${m.rendererMb.toFixed(1).padStart(4)}MB  JS heap ${m.heapMb.toFixed(1).padStart(4)}MB${note ? '  ' + note : ''}`;

async function main() {
  const args = process.argv.slice(2), what = args[0] || 'compare';
  const only = args.includes('--only') ? new Set(args[args.indexOf('--only') + 1].split(',')) : null;
  // (--only may also name a preset no edition ships yet, a draft, to measure it before it does)
  const scenes = SCENES.filter(s => !only || only.has(s.name))
    .concat([...only || []].filter(n => !SCENES.some(s => s.name === n)).map(n => ({ name: n, preset: n })));
  if (!scenes.length) { console.error(`no such scene: one of ${SCENES.map(s => s.name).join(', ')}`); process.exit(2); }
  const chrome = execFileSync(CHROME, ['--version']).toString().trim();

  if (what === 'baseline') {
    // two runs each, the better kept: the bar later runs are held to
    const kept = only && fs.existsSync(BASELINE) ? JSON.parse(fs.readFileSync(BASELINE)).scenes : {};
    for (const s of scenes) {
      const m = better(await measure(s), await measure(s));
      console.log(row(s.name, m, m.errors.length ? 'ERRORS: ' + m.errors[0].slice(0, 80) : ''));
      kept[s.name] = { instr: m.instr, fps: m.fps, rendererMb: m.rendererMb, heapMb: m.heapMb };
    }
    fs.writeFileSync(BASELINE, JSON.stringify({ chrome, made: new Date().toISOString().slice(0, 10), scenes: kept }, null, 1));
    console.log(`\nwrote ${path.relative(process.cwd(), BASELINE)} (${chrome})`);
    return;
  }

  if (!fs.existsSync(BASELINE)) { console.error('no baseline yet: npm run perf:baseline'); process.exit(2); }
  const base = JSON.parse(fs.readFileSync(BASELINE));
  if (base.chrome !== chrome) console.log(`the baseline was made with ${base.chrome}, this is ${chrome}: numbers may have moved for that alone\n`);
  const failed = [];
  for (const s of scenes) {
    const was = base.scenes[s.name];
    let m = await measure(s);
    if (!was) { console.log(row(s.name, m, `(not in the baseline: record it with npm run perf:baseline -- --only ${s.name})`)); continue; }
    if (worse(m, was).length) m = better(m, await measure(s));  // one unlucky run is not a regression
    const bad = worse(m, was);
    const change = `${m.instr >= was.instr ? '+' : ''}${Math.round(100 * (m.instr - was.instr) / was.instr)}% instr`;
    console.log(row(s.name, m, bad.length ? 'WORSE: ' + bad.join(', ') : `ok (${change})`));
    if (bad.length) failed.push(s.name);
  }
  if (failed.length) {
    console.log(`\n${failed.length} scene(s) cost more than the baseline: ${failed.join(', ')}`);
    console.log('if that is meant (a new effect worth its cost), record it with: npm run perf:baseline -- --only ' + failed.join(','));
    process.exit(1);
  }
  console.log(`\n${scenes.length} scenes within the baseline (instructions +${MAX_INSTR_UP * 100}%, renderer +${MAX_RENDERER_MB_UP}MB, JS heap +${MAX_HEAP_MB_UP}MB, fps ±${MAX_FPS_OFF})`);
}

await main();

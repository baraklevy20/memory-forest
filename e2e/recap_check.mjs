// node e2e/recap_check.mjs <pages.json> <chrome>: e2e/recap_check.py's checks, one headless Chrome.
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const [manifest, chrome] = process.argv.slice(2);
const { pages, shots } = JSON.parse(fs.readFileSync(manifest, 'utf8'));
const wait = ms => new Promise(r => setTimeout(r, ms));
const failures = [];
const expect = (ok, what) => { if (!ok) failures.push(what); };
const onCard = p => p.evaluate(() => { const c = document.querySelector('.af-recap-card.af-recap-on'); return c ? c.dataset.card : null; });
const sent = p => p.evaluate(() => window.__sent.filter(m => m.indexOf('forest:recap') === 0 || m.indexOf('forest:typing') === 0));

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--mute-audio'] });
try {
  for (const name of Object.keys(pages)) {
    const p = await browser.newPage();
    await p.setViewport({ width: 900, height: 640, deviceScaleFactor: shots ? 2 : 1 });
    const errors = [];
    p.on('pageerror', e => errors.push(`${name}: uncaught: ${e.message}`));
    p.on('console', m => { if (m.type() === 'error') errors.push(`${name}: console: ${m.text()}`); });
    await p.goto('file://' + pages[name]);
    if (name === 'heatmap_only') {
      // the forest off: a link in the heatmap's footer, under it, and the recap opens with its own forest drawn
      await p.waitForSelector('.af-cal-foot .af-recap-link', { timeout: 15000 });
      expect(!(await p.$('.af-recap-entry')), `${name}: no card where there's no forest`);
      await p.click('.af-cal-foot .af-recap-link');
      await p.waitForSelector('.af-recap-dlg');
      await wait(1500);
      expect(await p.evaluate(() => { const c = document.querySelector('.af-recap-forest canvas.af-canvas'); return !!c && c.width > 0; }), `${name}: the recap's forest is drawn`);
      if (shots) await p.screenshot({ path: path.join(shots, `${name}_title.png`) });
      await p.keyboard.press('Escape');
      expect(!(await p.$('.af-recap-dlg')), `${name}: Esc closes it`);
      failures.push(...errors);
      await p.close();
      continue;
    }
    await p.waitForSelector('.af-recap-entry [data-recap="open"]', { timeout: 15000 });
    if (name === 'with_news') {
      // the recap's card has the corner; the note of what's new waits
      expect(await p.evaluate(() => document.querySelectorAll('.af-news:not(.af-recap-entry)').length) === 0, `${name}: what's new waits`);
      failures.push(...errors);
      await p.close();
      continue;
    }
    const shot = async label => { if (shots) await p.screenshot({ path: path.join(shots, `${name}_${label}.png`) }); };
    await shot('card');
    await p.click('.af-recap-entry [data-recap="open"]');
    await p.waitForSelector('.af-recap-dlg');
    expect((await sent(p)).join(',') === 'forest:recap:opened:2026,forest:typing:1', `${name}: opening says so and holds Anki's shortcuts: ${await sent(p)}`);
    const light = name === 'light';
    const order = light ? ['title', 'summary'] : ['title', 'days', 'best', 'animals', 'label', 'summary'];
    expect(await onCard(p) === 'title', `${name}: opens on its title`);
    await wait(1500); await shot('title');
    // Space doesn't go on (other add-ons may use it); clicks and → do
    await p.keyboard.press('Space');
    expect(await onCard(p) === 'title', `${name}: Space stays on the title, not ${await onCard(p)}`);
    for (let i = 1; i < order.length; i++) {
      if (i % 2) await p.keyboard.press('ArrowRight');
      else { const b = await (await p.$('.af-recap-body')).boundingBox(); await p.mouse.click(b.x + b.width * 0.8, b.y + 20); }
      expect(await onCard(p) === order[i], `${name}: ${i % 2 ? '→' : 'a click'} brings ${order[i]}, not ${await onCard(p)}`);
      await wait(order[i] === 'animals' ? 4200 : order[i] === 'days' ? 5200 : 2600);
      await shot(order[i]);
    }
    await p.keyboard.press('ArrowRight');
    expect(await onCard(p) === 'summary', `${name}: on past the last card it stays`);
    await p.keyboard.press('ArrowLeft');
    expect(await onCard(p) === order[order.length - 2], `${name}: ← goes back`);
    if (!light) {
      // a click on the dialog goes on, on its left third back
      const box = await (await p.$('.af-recap-body')).boundingBox();
      await p.mouse.click(box.x + box.width * 0.8, box.y + 20);
      expect(await onCard(p) === 'summary', `${name}: a click goes on`);
      await p.mouse.click(box.x + box.width * 0.1, box.y + 20);
      expect(await onCard(p) === 'label', `${name}: a click on the left goes back`);
      expect(await p.evaluate(() => document.querySelector('.af-recap-skip').hidden), `${name}: no Skip when the summary is next`);
      await p.mouse.click(box.x + box.width * 0.1, box.y + 20);
      expect(await onCard(p) === 'animals', `${name}: back again to the animals`);
      await p.click('.af-recap-skip');
      expect(await onCard(p) === 'summary', `${name}: Skip to summary`);
      expect(await p.evaluate(() => document.querySelector('.af-recap-skip').hidden), `${name}: no Skip on the summary`);
    } else await p.keyboard.press('ArrowRight');
    await wait(600);
    await p.evaluate(() => { window.__sent.length = 0; });
    await p.click('.af-recap-save');
    const saved = (await sent(p)).filter(m => m.indexOf('forest:recap:save:2026:data:image/png;base64,') === 0);
    expect(saved.length === 1, `${name}: Save image sends the picture`);
    if (saved.length) {
      const png = Buffer.from(saved[0].split('base64,')[1], 'base64');
      expect(png.readUInt32BE(16) === 1080 && png.readUInt32BE(20) === 1350, `${name}: the picture is 1080 x 1350`);
      if (shots) fs.writeFileSync(path.join(shots, `${name}_share.png`), png);
    }
    await p.keyboard.press('Escape');
    expect(!(await p.$('.af-recap')), `${name}: Esc closes it`);
    expect((await sent(p)).indexOf('forest:typing:0') >= 0, `${name}: closing gives Anki its shortcuts back`);
    expect(!!(await p.$('.af-recap-row .af-recap-link')), `${name}: a line under the caption keeps a way back in`);
    expect(!(await p.$('.af-recap-entry [data-recap]')), `${name}: the card is gone`);
    await p.click('.af-recap-row .af-recap-link');
    expect(await onCard(p) === 'title', `${name}: its link opens it again`);
    await p.keyboard.press('Escape');
    failures.push(...errors);
    await p.close();
  }
} finally { await browser.close(); }
console.log(failures.length ? 'FAIL\n' + failures.join('\n') : 'ok   recap: card, keys, clicks, skip, save, close, link');
process.exit(failures.length ? 1 : 0);

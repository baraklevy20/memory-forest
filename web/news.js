/* Memory Forest — what's new (news.py): a dot on the cog for a new scenery or new settings,
 * and a note on the forest for a new feature, shown until it is answered. Only in Anki: the
 * phone has no cog, and nowhere to follow a note to. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { esc, send } = AF.u;

AF.news = function (root, data) {
  if (!data.inAnki) return;
  // (the year's look back, web/recap.js: its card, or its caption's link; with the forest off, core.js
  // asks once the heatmap is drawn, for its link in the heatmap's footer)
  if (AF.recap && data.showForest !== false) AF.recap(root, data);
  const cog = root.querySelector('.af-cog');
  if (cog && data.newDot) {
    cog.classList.add('af-cog-new');
    cog.title = data.newDot === 'scenery' ? AF.t('news.change_scenery_and_settings_new_scenery') : AF.t('news.change_scenery_and_settings_something_new');
    cog.setAttribute('aria-label', cog.title);
    // opening the settings answers it (news.settings_opened); the forest redraws later
    cog.addEventListener('click', () => cog.classList.remove('af-cog-new'));
  }
  AF.newsNote(root, data);
};

/* the note on the forest, if there is one and the corner is free: called again once the year's recap
 * card that had it is answered (web/recap.js), so the note shows then, not at the next drawing */
AF.newsNote = function (root, data) {
  const n = data.news, scene = root.querySelector('.af-scene');
  if (!n || !scene) return;  // (the calendar alone: no forest to put a note on)
  // (the year's recap has the corner: the note waits till it's answered)
  const corner = root.afTipLayer || scene;
  if (corner.querySelector && corner.querySelector('.af-recap-entry, .af-news')) return;
  const card = document.createElement('div');
  card.className = 'af-news';
  // (its title and text in their own direction: a note is English, as the release notes are, and in
  // a right-to-left panel its full stop landed at the start of its last line, ".the heatmap's new Streak view")
  card.innerHTML = `<div class="af-news-body" dir="auto"><b>${esc(n.title)}</b>${esc(n.text)}</div><div class="af-news-acts">`
    + (n.action ? `<button type="button" data-news="open">${esc(n.action)}</button>` : '')
    + `<button type="button" data-news="seen">${AF.t('news.got_it')}</button></div>`;
  card.addEventListener('click', e => {
    const b = e.target.closest('[data-news]');
    if (!b) return;
    card.remove();
    send(`${data.channel}:news:${b.dataset.news}:${n.id}`);
  });
  // (Layout's Background: on the layer over the page, at the window's corner: in the scene it was cut
  // off by the window's side, gone over its top in a wide window, and under the cards in a narrow one)
  (root.afTipLayer || scene).append(card);
  AF.cornerClear(root, card);
};

/* Layout's Background: a card in the window's corner (a note, the year's recap card) steps down under the
 * deck list where the window is too narrow for it beside the list: at the corner it covered the decks'
 * names, for the month the year's card is out. Again as the window is resized. */
AF.cornerClear = function (root, card) {
  if (root.afCornerFit) { window.removeEventListener('resize', root.afCornerFit); root.afCornerFit = null; }
  const table = root.afTipLayer && card.parentNode === root.afTipLayer && document.querySelector('center > table');
  if (!table) return;
  const fit = () => {
    if (!card.isConnected) { window.removeEventListener('resize', fit); return; }
    card.style.top = '';
    const a = card.getBoundingClientRect(), b = table.getBoundingClientRect();
    if (a.right > b.left && a.left < b.right && a.top < b.bottom && a.bottom > b.top) card.style.top = Math.round(b.bottom + 10) + 'px';
  };
  root.afCornerFit = fit;
  window.addEventListener('resize', fit);
  fit();
};
})();

/* Memory Forest — what's new (news.py): a dot on the cog for a new scenery or new settings,
 * and a note on the forest for a new feature, shown until it is answered. Only in Anki: the
 * phone has no cog, and nowhere to follow a note to. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { esc, send } = AF.u;

AF.news = function (root, data) {
  if (!data.inAnki) return;
  const cog = root.querySelector('.af-cog');
  if (cog && data.newDot) {
    cog.classList.add('af-cog-new');
    cog.title = data.newDot === 'scenery' ? AF.t('news.change_scenery_and_settings_new_scenery') : AF.t('news.change_scenery_and_settings_something_new');
    cog.setAttribute('aria-label', cog.title);
    // opening the settings answers it (news.settings_opened); the forest redraws later
    cog.addEventListener('click', () => cog.classList.remove('af-cog-new'));
  }
  const n = data.news, scene = root.querySelector('.af-scene');
  if (!n || !scene) return;  // (the calendar alone: no forest to put a note on)
  const card = document.createElement('div');
  card.className = 'af-news';
  card.innerHTML = `<b>${esc(n.title)}</b>${esc(n.text)}<div class="af-news-acts">`
    + (n.action ? `<button type="button" data-news="open">${esc(n.action)}</button>` : '')
    + `<button type="button" data-news="seen">${AF.t('news.got_it')}</button></div>`;
  card.addEventListener('click', e => {
    const b = e.target.closest('[data-news]');
    if (!b) return;
    card.remove();
    send(`${data.channel}:news:${b.dataset.news}:${n.id}`);
  });
  scene.append(card);
};
})();

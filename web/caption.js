/* Memory Forest — the line under the forest: its numbers, the scene's name and the weather,
 * each with a tooltip of its own. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { fmtDate, esc, canBrowse, send, animates } = AF.u;
// the caption's tooltip sits this far above what it explains
const TIP_MARGIN = 6;

// (each goes into the caption's "Weather: rain in Oslo, 5°")
const WEATHER_NAMES = { clear: AF.N_('caption.clear_sky'), cloudy: AF.N_('caption.cloudy'), fog: AF.N_('caption.fog'), rain: AF.N_('caption.rain'),
  storm: AF.N_('caption.thunderstorm'), snow: AF.N_('caption.snow'), deep_winter: AF.N_('caption.deep_winter'), after_rain: AF.N_('caption.after_the_rain') };
// the live weather's line: its name, and the city and temperature where they are known
function weatherLine(m) {
  const v = { weather: WEATHER_NAMES[m.weather] ? AF.tx(WEATHER_NAMES[m.weather]) : m.weather, city: m.city, temp: m.temp != null ? Math.round(m.temp) : null };
  if (m.city && v.temp != null) return AF.t('caption.weather_weather_in_city_temp', v);
  if (m.city) return AF.t('caption.weather_weather_in_city', v);
  if (v.temp != null) return AF.t('caption.weather_weather_temp', v);
  return AF.t('caption.weather_weather', v);
}

/* the merged band spans every deck, so on a deck screen showing the whole forest it is
 * browsed without a deck filter; a deck's own forest keeps it */
const deckFor = data => (data.deckId && !data.highlight ? data.deckId : '');
AF.deckFor = deckFor;

AF.caption = function (root, data) {
  const s = data.stats, m = data.mood;
  root.querySelector('.af-journal').textContent = data.journal || '';
  const items = [];
  if (data.testForest) items.push([AF.t('caption.test_forest'), AF.t('caption.made_up_trees_from_the_test')]);
  if (data.highlight) items.push([AF.tn('caption.deck_lit_of_n_trees', s.trees, { deck: (data.deckName || '').split('::').pop(), lit: data.litCount, n: s.trees }),
    AF.t('caption.trees_holding_cards_from_this_deck')]);
  if (s.trees) items.push([AF.tn('caption.n_trees', s.trees), AF.t('caption.one_tree_for_each_day_you')]);
  if (data.merged) {
    const mg = data.merged, v = { from: fmtDate(mg.from_date), to: fmtDate(mg.to_date) };
    items.push([AF.tn('caption.n_in_the_deep_forest', mg.count),
      AF.tn('caption.your_trees_from_from_to_to', mg.cards, v)
      + (canBrowse() && !data.testForest ? ' ' + AF.t('caption.click_to_see_their_cards') : ''),
      data.testForest ? '' : `${data.channel}:browse:${mg.from_ago}:${deckFor(data)}:${mg.to_ago}`]);
  }
  if (s.ancient) items.push([AF.tn('caption.n_ancient', s.ancient, { n: s.ancient }), AF.t('caption.trees_whose_cards_you_will_likely')]);
  // (a click shows all of it in the heatmap under the forest: its Streak view, on today's streak)
  const byYear = r => r.afCalStreak && r.afCalStreak();
  byYear.hint = r => (r.afCalStreak && r.afCalStreak(true) ? `<br><span class="af-hint">${AF.t('caption.click_to_see_all_of_it')}</span>` : '');
  // (a streak of 6 or 5 days a week: a week's first missed days pass too, payload._days_off)
  const week = s.streak_week || 7;
  if (s.streak) items.push([AF.tn('caption.n_day_streak', s.streak, { n: s.streak }), week === 7
    ? AF.t('caption.days_you_studied_in_a_row')
    : week === 6 ? AF.t('caption.days_you_studied_in_a_row_2', { week })
      : AF.t('caption.days_you_studied_in_a_row_3', { week }), byYear]);
  items.push(...AF.events.collect('caption', data, animates(data)));  // the asteroid, on its way or struck
  // the scene's name, unless it is the plain default
  if (data.sceneName) items.push([data.sceneName, data.sceneTip || AF.t('caption.the_scenery_chosen_in_the_forest')]);
  if (data.weatherError) {
    const lost = data.weatherError.startsWith('city not found');
    items.push([lost ? AF.t('caption.city_not_found') : AF.t('caption.live_weather_unavailable'), lost
      ? AF.t('caption.openstreetmap_does_not_know_that_city')
      : AF.t('caption.the_live_weather_could_not_be')]);  // (not why: the service's own words, in English)
  }
  // the weather only when it is live; otherwise it is simply part of the preset
  if (m.source === 'real') {
    items.push([weatherLine(m), AF.t('caption.live_weather_from_met_norway_cc')]);
  }
  // an item's click is a message for Anki, or something done right here on the page
  root.afCaptionActs = items.map(([, , cmd]) => typeof cmd === 'function' ? cmd : null);
  root.querySelector('.af-meta').innerHTML = items.map(([t, tip, cmd], i) => typeof cmd === 'function'
    ? `<span class="af-info af-click" data-tip="${esc(tip)}" data-act="${i}">${esc(t)}</span>`
    : `<span class="af-info${cmd && canBrowse() ? ' af-click' : ''}" data-tip="${esc(tip)}"${cmd ? ` data-cmd="${esc(cmd)}"` : ''}>${esc(t)}</span>`).join(' · ')
    + (data.credit ? ` <span class="af-credit">· ${AF.t('caption.weather_by_met_norway')}</span>` : '');
};
/* caption hints use the forest's own tooltip (Anki's webview doesn't show title tooltips) */
AF.captionTips = function (root) {
  // (in the forest's own box: placed apart from the heatmap, the panel has no box of its own)
  const host = root.querySelector('.af-forest') || root;
  const capTip = document.createElement('div'); capTip.className = 'af-tip af-cap-tip'; capTip.hidden = true; host.append(capTip);
  // on a touch screen a tap opens an item's tooltip, and a second tap on it acts (see AF.watchHint)
  let touched = false, armed = null;
  const place = el => {
    const pr = host.getBoundingClientRect(), r = el.getBoundingClientRect();
    const left = Math.min(Math.max(0, r.left - pr.left + r.width / 2 - capTip.offsetWidth / 2), pr.width - capTip.offsetWidth);
    capTip.style.left = left + 'px'; capTip.style.top = (r.top - pr.top - capTip.offsetHeight - TIP_MARGIN) + 'px';
  };
  root.querySelectorAll('.af-info').forEach(el => {
    el.addEventListener('pointerdown', e => { touched = e.pointerType !== 'mouse'; });
    el.addEventListener('mouseenter', () => {
      capTip.textContent = el.dataset.tip;
      const act = el.dataset.act && root.afCaptionActs[el.dataset.act];
      // (an item's own hint, or the event's replay; none where its click does nothing now)
      const hint = act ? (act.hint ? act.hint(root) : AF.watchHint(touched)) : '';
      if (act) { capTip.insertAdjacentHTML('beforeend', hint); el.classList.toggle('af-click', !!hint); }
      capTip.hidden = false;
      place(el);
    });
    el.addEventListener('mouseleave', () => { capTip.hidden = true; armed = null; });
    if (el.dataset.act) el.addEventListener('click', () => {
      if (touched && armed !== el) { armed = el; return; }  // the first tap: its tooltip
      armed = null; capTip.hidden = true;
      root.afCaptionActs[el.dataset.act](root);
    });
    else if (el.dataset.cmd && canBrowse()) el.addEventListener('click', () => send(el.dataset.cmd));
  });
}
})();

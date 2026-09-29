/* Memory Forest — the line under the forest: its numbers, the scene's name and the weather,
 * each with a tooltip of its own. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { fmtDate, esc, cap, canBrowse, send, animates } = AF.u;
// the caption's tooltip sits this far above what it explains
const TIP_MARGIN = 6;

const WEATHER_NAMES = { clear: 'clear sky', cloudy: 'cloudy', fog: 'fog', rain: 'rain', storm: 'thunderstorm', snow: 'snow', deep_winter: 'deep winter', after_rain: 'after the rain' };

/* the merged band spans every deck, so on a deck screen showing the whole forest it is
 * browsed without a deck filter; a deck's own forest keeps it */
const deckFor = data => (data.deckId && !data.highlight ? data.deckId : '');
AF.deckFor = deckFor;

AF.caption = function (root, data) {
  const s = data.stats, m = data.mood, words = AF.WORDS;
  root.querySelector('.af-journal').textContent = data.journal || '';
  const items = [];
  if (data.testForest) items.push(['Test forest', `Made-up ${words.many} from the Test forest setting. Turn it off in the forest settings to see your real one.`]);
  if (data.highlight) items.push([`${(data.deckName || '').split('::').pop()}: ${data.litCount} of ${s.trees} ${words.many}`, `${cap(words.many)} holding cards from this deck stay in colour; the rest fade back. Change this with Deck screens in the forest settings.`]);
  if (s.trees) items.push([`${s.trees.toLocaleString()} ${s.trees === 1 ? words.one : words.many}`, `One ${words.one} for each day you learned new cards. Hover over one to see its day, click it to see its cards.`]);
  if (data.merged) items.push([`${data.merged.count.toLocaleString()} in ${words.deep}`,
    `Your ${words.many} from ${fmtDate(data.merged.from_date)} to ${fmtDate(data.merged.to_date)} stand together in the distance, holding ${data.merged.cards.toLocaleString()} cards. Drawing every one of them individually would slow the deck list down.`
    + (canBrowse() && !data.testForest ? ' Click to see their cards.' : ''),
    data.testForest ? '' : `${data.channel}:browse:${data.merged.from_ago}:${deckFor(data)}:${data.merged.to_ago}`]);
  if (s.ancient) items.push([`${s.ancient} ancient`, `${cap(words.many)} whose cards you will likely remember for more than a year: their median memory strength is at least 365 days. That is FSRS stability where you have it, and the scheduling interval where you do not.`]);
  if (s.streak) items.push([`${s.streak}-day streak`, 'Days in a row with at least one review.']);
  items.push(...AF.events.collect('caption', data, words, animates(data)));  // the asteroid, on its way or struck
  // the scene's name, unless it is the plain default
  if (data.sceneName) items.push([data.sceneName, data.sceneTip || 'The scenery, chosen in the forest settings.']);
  if (data.weatherError) {
    const lost = data.weatherError.startsWith('city not found');
    items.push([lost ? 'City not found' : 'Live weather unavailable', lost
      ? "Open-Meteo does not know that city, so the scenery keeps its own weather. Check the spelling, or try its English name, in the forest settings."
      : `The live weather could not be fetched (${data.weatherError}), so the scenery keeps its own weather for now.`]);
  }
  // the weather only when it is live; otherwise it is simply part of the preset
  if (m.source === 'real') {
    items.push([`Weather: ${WEATHER_NAMES[m.weather] || m.weather}${m.city ? ` in ${m.city}` : ''}${m.temp != null ? `, ${Math.round(m.temp)}°` : ''}`,
      'Live weather from Open-Meteo.']);
  }
  // an item's click is a message for Anki, or something done right here on the page
  root.afCaptionActs = items.map(([, , cmd]) => typeof cmd === 'function' ? cmd : null);
  root.querySelector('.af-meta').innerHTML = items.map(([t, tip, cmd], i) => typeof cmd === 'function'
    ? `<span class="af-info af-click" data-tip="${esc(tip)}" data-act="${i}">${esc(t)}</span>`
    : `<span class="af-info${cmd && canBrowse() ? ' af-click' : ''}" data-tip="${esc(tip)}"${cmd ? ` data-cmd="${esc(cmd)}"` : ''}>${esc(t)}</span>`).join(' · ')
    + (data.credit ? ' <span class="af-credit">· weather by Open-Meteo</span>' : '');
};
/* caption hints use the forest's own tooltip (Anki's webview doesn't show title tooltips) */
AF.captionTips = function (root) {
  const capTip = document.createElement('div'); capTip.className = 'af-tip af-cap-tip'; capTip.hidden = true; root.append(capTip);
  // on a touch screen a tap opens an item's tooltip, and a second tap on it acts (see AF.watchHint)
  let touched = false, armed = null;
  const place = el => {
    const pr = root.getBoundingClientRect(), r = el.getBoundingClientRect();
    const left = Math.min(Math.max(0, r.left - pr.left + r.width / 2 - capTip.offsetWidth / 2), pr.width - capTip.offsetWidth);
    capTip.style.left = left + 'px'; capTip.style.top = (r.top - pr.top - capTip.offsetHeight - TIP_MARGIN) + 'px';
  };
  root.querySelectorAll('.af-info').forEach(el => {
    el.addEventListener('pointerdown', e => { touched = e.pointerType !== 'mouse'; });
    el.addEventListener('mouseenter', () => {
      capTip.textContent = el.dataset.tip;
      if (el.dataset.act) capTip.insertAdjacentHTML('beforeend', AF.watchHint(touched));
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

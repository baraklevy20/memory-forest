/* Memory Forest — what hovering a tree, a pond, the deep forest or an animal says. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { fmtDate, esc, cap, canBrowse } = AF.u;
const { YOUNG, MATURE } = AF.STAGE;

// memory strength reads in days, then in months from MONTHS_FROM days, then in years
const DAYS_PER_YEAR = 365, DAYS_PER_MONTH = 30, MONTHS_FROM = 60;
AF.fmtStrength = d => d >= DAYS_PER_YEAR ? `${(d / DAYS_PER_YEAR).toFixed(1)} years` : d >= MONTHS_FROM ? `${Math.round(d / DAYS_PER_MONTH)} months` : `${Math.round(d)} days`;
function tipHtml(t, words) {
  const when = t.ago === 0 ? 'today' : t.ago === 1 ? 'yesterday' : `${t.ago} days ago`;
  const lines = [`<b>${esc(fmtDate(t.date))}</b> · ${esc(words.planted)} ${when}`, `${t.n} card${t.n === 1 ? '' : 's'} · ${esc(words.stages[t.stage])}`];
  if (t.suspended && t.suspended >= t.n) {
    // every card retired: the tree stands as it was, with nothing left to measure
    lines.push(t.n === 1 ? 'Its card is suspended' : `All ${t.n} cards suspended`);
  } else if (t.stage >= YOUNG) {
    // "measured" is false when there is no forgetting curve behind the number, only a
    // count of what has gone wrong lately - so the tooltip must not claim more than that
    const parts = t.measured === false
      ? [`${Math.round(t.remembered * 100)}% still going well`]
      : [`~${Math.round(t.remembered * 100)}% remembered`];
    if (t.strength) parts.push(`lasts ~${AF.fmtStrength(t.strength)}`);
    lines.push(parts.join(' · '));
    if (t.struggling && t.stage >= MATURE) lines.push(`${t.struggling} of ${t.n} relearning or lapsed this week`);
    if (t.suspended) lines.push(`${t.suspended} of ${t.n} suspended`);
  }
  if (canBrowse()) lines.push(CLICK_HINT);
  return lines.join('<br>');
}
const CLICK_HINT = '<span class="af-hint">Click to see these cards</span>';
function pondHtml(p) { return `<b>A quiet pond</b><br>${p.days} days without reviews`; }
function deepHtml(m, words) {
  const lines = [`<b>${esc(cap(words.deep))}</b>`,
    `${m.count.toLocaleString()} older ${esc(words.many)} · ${m.cards.toLocaleString()} cards`,
    `${esc(fmtDate(m.from_date))} – ${esc(fmtDate(m.to_date))}`];
  if (m.ancient) lines.push(`${m.ancient.toLocaleString()} of them ancient`);
  if (canBrowse()) lines.push(CLICK_HINT);
  return lines.join('<br>');
}
function visitorHtml(v) { const who = v.label.charAt(0).toUpperCase() + v.label.slice(1); return `<b>${esc(who)}</b><br>${v.key === 'cabin' ? 'Built' : 'Moved in'} when ${esc(v.why)}.`; }
/* What one day is called, in the tooltips and the caption */
AF.WORDS = { one: 'tree', many: 'trees', planted: 'planted', deep: 'the deep forest', stages: AF.STAGE_NAMES };
AF.tips = { tree: tipHtml, pond: pondHtml, deep: deepHtml, visitor: visitorHtml };
})();

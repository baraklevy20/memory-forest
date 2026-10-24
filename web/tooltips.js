/* Memory Forest — what hovering a tree, a pond, the deep forest or an animal says. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { fmtDate, esc, canBrowse } = AF.u;
const { YOUNG, MATURE } = AF.STAGE;
// a tree's stage, by AF.STAGE's number (shown in the reader's language: AF.tips.stage)
const STAGES = [AF.N_('tooltip.seedling'), AF.N_('tooltip.sapling'), AF.N_('tooltip.young'),
  AF.N_('tooltip.mature'), AF.N_('tooltip.old'), AF.N_('tooltip.ancient')];
const stage = s => AF.tx(STAGES[s]);

// memory strength reads in days, then in months from MONTHS_FROM days, then in years
const DAYS_PER_YEAR = 365, DAYS_PER_MONTH = 30, MONTHS_FROM = 60;
AF.fmtStrength = d => d >= DAYS_PER_YEAR ? AF.t('tooltip.n_years', { n: AF.i18n.dec(d / DAYS_PER_YEAR) })
  : d >= MONTHS_FROM ? AF.tn('tooltip.n_months', Math.round(d / DAYS_PER_MONTH))
    : AF.tn('heatmap.n_days', Math.round(d));
// how much of a tree's cards is remembered: from a forgetting curve, or (`measured` false) only a
// count of what has gone wrong lately - so it must not claim more than that
AF.rememberedText = t => t.measured === false
  ? AF.t('tooltip.pct_still_going_well', { pct: Math.round(t.remembered * 100) })
  : AF.t('tooltip.pct_remembered', { pct: Math.round(t.remembered * 100) });
/* `click`: what a click on it does, when that is not opening its cards (zooming in: picking it) */
function tipHtml(t, click) {
  const when = t.ago === 0 ? AF.t('tooltip.planted_today') : t.ago === 1 ? AF.t('tooltip.planted_yesterday')
    : AF.tn('tooltip.planted_n_days_ago', t.ago, { n: t.ago });
  const lines = [`<b>${esc(fmtDate(t.date))}</b> · ${esc(when)}`, `${esc(AF.tn('tooltip.n_cards', t.n, { n: t.n }))} · ${esc(stage(t.stage))}`];
  if (t.suspended && t.suspended >= t.n) {
    // every card retired: the tree stands as it was, with nothing left to measure
    lines.push(t.n === 1 ? AF.t('tooltip.its_card_is_suspended') : AF.tn('tooltip.all_n_cards_suspended', t.n, { n: t.n }));
  } else if (t.stage >= YOUNG) {
    const parts = [AF.rememberedText(t)];
    if (t.strength) parts.push(AF.t('tooltip.lasts_time', { time: AF.fmtStrength(t.strength) }));
    lines.push(parts.join(' · '));
    if (t.struggling && t.stage >= MATURE) lines.push(AF.tn('tooltip.n_of_total_relearning_or_lapsed', t.struggling, { n: t.struggling, total: t.n }));
    if (t.suspended) lines.push(AF.tn('tooltip.n_of_total_suspended', t.suspended, { n: t.suspended, total: t.n }));
  }
  if (t.leeches && t.stage >= YOUNG) lines.push(AF.tn('tooltip.n_leeches_here_the_crows_stay', t.leeches, { n: t.leeches }));
  if (t.cured) lines.push(t.cured === 1 ? AF.t('tooltip.a_leech_here_mature_again_the')
    : AF.tn('tooltip.n_leeches_here_mature_again_the', t.cured, { n: t.cured }));
  if (t.big) lines.push(AF.tn('tooltip.a_big_learning_day_n_new', t.n, { n: t.n, usual: t.big }));
  if ((t.burn || t.smoke) && AF.fireLine) lines.push(AF.fireLine(t));  // Wild's fire (web/events/fire.js)
  if (click) lines.push(`<span class="af-hint">${esc(click)}</span>`);
  else if (canBrowse()) lines.push(clickHint());
  return lines.join('<br>');
}
const clickHint = () => `<span class="af-hint">${AF.t('tooltip.click_to_see_these_cards')}</span>`;
/* a break's line, with when it ran by the month: "in May 2026", or "from April to June 2026" */
function pondLine(p) {
  const n = { n: p.days };
  if (!p.to) return AF.tn('tooltip.n_days_without_reviews', p.days, n);
  const a = p.from || p.to, b = p.to;
  const month = (iso, year) => AF.i18n.dayIn(iso, year ? { month: 'long', year: 'numeric' } : { month: 'long' });
  if (a.slice(0, 7) === b.slice(0, 7)) return AF.tn('tooltip.n_days_without_reviews_in_month', p.days, Object.assign(n, { month: month(b, true) }));
  return AF.tn('tooltip.n_days_without_reviews_from_from', p.days,
    Object.assign(n, { from: month(a, a.slice(0, 4) !== b.slice(0, 4)), to: month(b, true) }));
}
function pondHtml(p) { return `<b>${AF.t('tooltip.a_quiet_pond')}</b><br>${esc(pondLine(p))}`; }
function deepHtml(m) {
  const lines = [`<b>${AF.t('tooltip.the_deep_forest')}</b>`,
    `${esc(AF.tn('tooltip.n_older_trees', m.count))} · ${esc(AF.tn('tooltip.n_cards', m.cards))}`,
    esc(AF.t('tooltip.from_to', { from: fmtDate(m.from_date), to: fmtDate(m.to_date) }))];
  if (m.ancient) lines.push(esc(AF.tn('tooltip.n_of_them_ancient', m.ancient)));
  if (canBrowse()) lines.push(clickHint());
  return lines.join('<br>');
}
/* an animal or the cabin: its name ("A deer") and why it is there ("Moved in when you kept a 30-day
 * streak."), both whole and translated in milestones.py */
function visitorHtml(v) {
  return `<b>${esc(v.name)}</b><br>${esc(v.stayed)}`;
}
AF.tips = { tree: tipHtml, pond: pondHtml, deep: deepHtml, visitor: visitorHtml, stage };
})();

/* Memory Forest — the study heatmap's colours: the four shades of a scenery or of colours you picked,
 * at the forest's hour, on the page it sits on. HEATMAP_COLOURS.md says why they are as they are;
 * dev/heatmap_shades.py runs shades() from this file, and reads its constants as text. */
(function () {
'use strict';
const AF = window.AnkiForest, Cal = AF.cal;
const { hex, mix, oklab, fromOklab } = AF.u;

/* the four shades a day studied takes, fewest reviews to most, with their tiles' edges: built
 * round the scenery's colour (its own `calendar` colour, or its most colourful crown colour,
 * AF.foliage), from pale to deep, so the calendar belongs to the scene */
const DARK = [16, 16, 16];
// an empty day's grey on a dark page (EMPTY), the least the faintest shade stands apart from it
// (OKLab), and how much lighter it is made when closer (heatmap_look.py has the same sums)
const EMPTY_GREY = [128, 128, 128], EMPTY_ALPHA = 0.11, EMPTY_APART = 0.06;
const EMPTY_ALPHA_LIGHT = 0.2;
const blankOn = paper => mix(paper.bg, EMPTY_GREY, paper.dark ? EMPTY_ALPHA : EMPTY_ALPHA_LIGHT);  // (an empty day's grey over the page)
/* the four shades of colours you picked (yours, the ready ones), the same on a light page and a
 * dark one: the busiest exactly the last colour, the others stepping to it from the first through
 * OKLab; with one colour, from dim to full, dimmed into the page (its hue kept). Only the faintest
 * fades into the page a little (FAINT_FADE), so the quiet days sit back, less where it would come
 * too near an empty day */
const FAINT_FADE = 0.25, FADE_STEP = 0.05, DIM = [0.55, 0.36, 0.18, 0];
function exactSteps(colours, paper) {
  const two = Array.isArray(colours), a = hex(two ? colours[0] : colours), b = two ? hex(colours[1]) : a;
  const at = (i, f) => two ? (i ? blend(a, b, i / 3) : mix(a, paper.bg, f)) : mix(a, paper.bg, i ? DIM[i] : f);
  const blank = blankOn(paper);
  let f = two ? FAINT_FADE : DIM[0];
  while (f > 0 && apart(at(0, f), blank) < EMPTY_APART) f = Math.max(0, f - FADE_STEP);
  return [0, 1, 2, 3].map(i => (i === 3 ? b : at(i, f)));
}
const apart = (a, b) => { const p = oklab(a), q = oklab(b); return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]); };
// a light page's four shades: their lightness (OKLab L), fewest reviews to most, and the least
// colourfulness they keep (a near-grey key would otherwise give grey tiles)
const LIGHT_STEPS = [0.82, 0.69, 0.56, 0.43], LIGHT_CHROMA = 0.08;  // (0.86 sat too near a missed day's grey)
// and a dark page's, from a clear dim colour to a pale bright one: the middle two at 0.10-0.11 apart
// (OKLab x100) read as one in a small tile; these, from a search over every scenery, put
// every neighbour at least 12.6 apart and the fewest a step off a missed day's grey, in the room
// Anki's lighter dark page leaves; each shade's share of its key's colourfulness rises to the third,
// and the top keeps only half: a vivid colour that light glowed (2026-10-14)
const DARK_STEPS = [0.45, 0.58, 0.72, 0.85], DARK_CHROMA = [0.6, 1.0, 1.0, 0.5];
/* `t` of the way from colour `a` to `b`, through OKLab, where equal steps look equal (a plain mix
 * of a blue and a green dips muddy in the middle) */
function blend(a, b, t) {
  const p = oklab(a), q = oklab(b);
  return fromOklab(...p.map((v, i) => v + (q[i] - v) * t));
}
// whether an OKLab colour is one the screen can show (each channel, before it is clipped, in 0..1)
function fits(L, A, B) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3, m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3, s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3;
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s].every(v => v >= -0.0005 && v <= 1.0005);
}
// a scenery's colour kept within a lightness and saturation a tile can show: a silhouette
// scenery's near-black trees (Witch across the moon) would make every tile black
const KEY_L = [0.36, 0.56], KEY_S = 0.28;
function readable(c) {
  const [r, g, b] = c.map(v => v / 255), max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, sat = 0, l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6;
  }
  l = Math.min(KEY_L[1], Math.max(KEY_L[0], l)); sat = Math.max(KEY_S, sat);
  const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat, p = 2 * l - q;
  const ch = t => { t = (t + 1) % 1; return 255 * (t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p); };
  return [ch(h + 1 / 3), ch(h), ch(h - 1 / 3)];
}
/* The heatmap's colours follow the forest's hour (mood.time: the clock, the city's sun or a fixed
 * hour, whichever the forest follows), as its trees do. A scenery's colours are made for its own hour
 * (`mood.home`, its preset's, from scene.py):
 * - a day scenery (its own hour dawn, day or golden hour) keeps them while the sun is up, as its
 *   trees do; after dark they cool with them: their hue turns towards its night tint (its night
 *   sky's blue), a little at dusk and more at night (HOUR_TURN, hourTurn). One whose trees take no
 *   tint at night (Chalkboard's chalk) keeps its colours at every hour, as they do
 * - a night scenery (its own hour dusk or night: Aurora, Lanterns, Synthwave...) keeps them after
 *   dark, when its lights are lit; by day it wears its day colours (`calendarDay`, from its daytime
 *   palette: chosen like `calendar`, a hue turned from night colours went muddy), and at dawn and
 *   golden hour the two meet halfway (DAY_SHARE, dayBlend). One with no day colours keeps its own.
 * - a scenery that names colours for each hour (`calendarHours`, Synthwave's grid neon) wears them at
 *   those hours, and its own `calendar` at the rest.
 * Each colour keeps the lightness the shades give it, so the steps stay as far apart at every hour
 * (HEATMAP_COLOURS.md; dev/heatmap_shades.py checks every hour). Colours chosen on the Heatmap tab
 * stay as chosen. */
const HOUR_TURN = { dusk: 0.1, night: 0.35 }, AFTER_DARK = ['dusk', 'night'];
const DAY_SHARE = { dawn: 0.5, day: 1, golden_hour: 0.5 };
function hourTurn(c, hour) {
  const k = oklab(c), t = oklab(hex(hour.tint)), C = Math.hypot(k[1], k[2]);
  const h = Math.atan2(k[2], k[1]), to = Math.atan2(t[2], t[1]);
  const turned = h + Math.atan2(Math.sin(to - h), Math.cos(to - h)) * hour.turn;  // (the short way round)
  let C2 = C;
  while (C2 > 0.01 && !fits(k[0], C2 * Math.cos(turned), C2 * Math.sin(turned))) C2 *= 0.95;
  return fromOklab(k[0], C2 * Math.cos(turned), C2 * Math.sin(turned));
}
/* `t` of the way from colour `a` to `b` by hue (the short way round) and colourfulness, not straight
 * through OKLab: a night blue to a day green went grey halfway (each shade's lightness is set after) */
function dayBlend(a, b, t) {
  if (t >= 1) return b;
  const p = oklab(a), q = oklab(b), hp = Math.atan2(p[2], p[1]), hq = Math.atan2(q[2], q[1]);
  const h = hp + Math.atan2(Math.sin(hq - hp), Math.cos(hq - hp)) * t;
  const L = p[0] + (q[0] - p[0]) * t;
  let C = Math.hypot(p[1], p[2]) + (Math.hypot(q[1], q[2]) - Math.hypot(p[1], p[2])) * t;
  while (C > 0.01 && !fits(L, C * Math.cos(h), C * Math.sin(h))) C *= 0.95;
  return fromOklab(L, C * Math.cos(h), C * Math.sin(h));
}
/* what the mood's hour does to a scenery's colours (above): { tint, turn } after dark for a day
 * scenery, { to, share } towards the colours it names for the other half of the day, or null where
 * its own colours stand. A mood with no `home` (sent before it was) takes a scenery with day
 * colours as a night one. */
function hourOf(mood) {
  const spec = AF.ENVS[mood.special] || {}, home = mood.home || (spec.calendarDay ? 'night' : 'day');
  if (spec.calendarHours) {
    const to = spec.calendarHours[mood.time];
    return to ? { to, share: 1 } : null;
  }
  if (AFTER_DARK.includes(home)) {
    const share = DAY_SHARE[mood.time];
    return share && spec.calendarDay ? { to: spec.calendarDay, share } : null;
  }
  const turn = HOUR_TURN[mood.time];
  if (!turn) return null;
  try {
    const th = AF.theme(Object.assign({}, mood, { time: 'night', weather: 'clear' }), {}, []);
    return th.tint ? { turn, tint: th.tint } : null;
  } catch { return null; }
}
/* The page the calendar sits on: its colour (the first background behind `el` with any, AF.u.pageBg;
 * on a phone's transparent card, the app's own, AF.u.appBg) and whether it is dark (Anki's dark mode). */
const cardOut = () => {
  const m = window.getComputedStyle(document.body).getPropertyValue('--af-card-out').match(/[\d.]+/g);
  return m && m.length >= 3 ? [+m[0], +m[1], +m[2]] : null;
};
function pageOf(el) {
  const behind = [];
  for (let e = el; e && e.nodeType === 1; e = e.parentElement) behind.push(e);
  // (its card under it in Onigiri's tile, the forest bare on the page: forest.css .af-card-heat, its
  // colour as it comes out, core.js AF.cardTones; the cream page round it gave a light page's shades)
  const card = el.closest && el.closest('.af-card-heat') ? cardOut() : null;
  const bg = card || AF.u.pageBg(behind) || AF.u.appBg();
  return { bg, dark: bg[0] * 0.3 + bg[1] * 0.59 + bg[2] * 0.11 < 128, solid: !!(el.closest && el.closest('.af-text-bands')) };
}
/* the shades run towards the page's opposite, so a day stands out the more you studied: darker
 * for more on a light page, brighter for more on a dark one (a dark page's pale tiles would
 * otherwise draw the eye to your quietest days) */
function shades(env, paper, look) {
  // (your colours and the ready ones are `exact`: as picked, on either page: exactSteps)
  // a scenery whose trees are not its colour names its own (`calendar`: Frozen market's ice blue),
  // or two, the fewest reviews' and the most's, for a ramp between them (Aurora's night blue to
  // its green): each shade then takes its own colour along it. The Heatmap tab's colours
  // (heatmap_look.py) come in the same way, as one colour or two (`look.colours`)
  const dark = paper.dark, chosen = look && look.colours, exact = !!(look && look.exact && chosen);
  const chroma = c => Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]), own = chosen || AF.envOf(env).calendar;
  const keysOf = own => Array.isArray(own) ? [0, 1, 2, 3].map(i => readable(blend(hex(own[0]), hex(own[1]), i / 3)))
    : Array(4).fill(readable(own ? hex(own) : AF.foliage(env).slice(1).reduce((a, c) => chroma(c) > chroma(a) ? c : a)));
  // (the scenery's colours follow the forest's hour, hourOf; colours chosen on the Heatmap tab stay as chosen)
  const plain = keysOf(own), hour = !chosen && env.hour;
  const keys = !hour ? plain : hour.to ? keysOf(hour.to).map((c, i) => dayBlend(plain[i], c, hour.share)) : plain.map(c => hourTurn(c, hour));
  // (about evenly far apart; on a dark page the top one only a little towards white, so a busy
  // day never outshines the forest)
  // (on a light page each shade at its own lightness, in even steps from a clear light colour to a
  // deep one, keeping only the key's hue and colourfulness: mixed towards white and black they
  // went grey, and a ramp's dark start and bright end met in the same muddy middle; and the
  // texture stronger: the white between the tiles otherwise outshines them)
  const steps = (dark ? DARK_STEPS : LIGHT_STEPS).map((L, i) => {
    const k = oklab(keys[i]), h = Math.atan2(k[2], k[1]);
    // (where the colour is beyond the screen's, its colourfulness gives way, not its lightness: a
    // clipped neon pink came out darker than the shade under it)
    let C = Math.max(LIGHT_CHROMA, Math.hypot(k[1], k[2])) * (dark ? DARK_CHROMA[i] : 1);
    while (C > 0.01 && !fits(L, C * Math.cos(h), C * Math.sin(h))) C *= 0.95;
    return fromOklab(L, C * Math.cos(h), C * Math.sin(h));
  });
  // (your colours and the ready ones: as picked, exactSteps; a ready ramp the other way round on a
  // light page, its deep colour the busiest, as Review Heatmap's light mode: `flipLight`)
  const flip = exact && !dark && look.flipLight && Array.isArray(look.colours);
  if (exact) steps.splice(0, 4, ...exactSteps(flip ? look.colours.slice().reverse() : look.colours, paper));
  // (the Heatmap tab's "Busier days: Darker": a dark page's shades the other way round, a pale tint
  // for a quiet day down to a clear dim colour for a busy one, still well clear of a missed day's grey)
  if (dark && look && look.darker) steps.reverse();
  return { grass: steps.map(c => toned(c, dark)[0]), edge: steps.map(c => toned(c, dark)[1]) };
}
// a shade's two tones and its edge: the colour, a little darker, and darker still
const toned = (c, dark) => [[c, mix(c, DARK, dark ? 0.07 : 0.16)], mix(c, DARK, dark ? 0.22 : 0.3)];

Object.assign(Cal, { DARK, EMPTY_ALPHA, EMPTY_ALPHA_LIGHT, blankOn, apart, fits, hourOf, pageOf, shades, toned });
})();

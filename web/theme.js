/* Memory Forest — times of day, and the theme a scene is drawn in: the hour, the weather, the
 * environment and your numbers as ambience. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { mixHex, clamp } = AF.u;

/* ---------- times of day ---------- */
AF.TIMES = {
  dawn: { sky: ['#b3bcd8', '#cbc3dc', '#e3c8d4', '#f1cfc2', '#f7dcc0', '#fae8cf'], orb: { kind: 'sun', x: 0.3, y: 0.3, r: 8, c: '#fff6dc', glow: '#fbe6c6', halo: 7 },
    far: '#b7b2cb', near: '#9ea8b8', g0: '#9ab28e', g1: '#628463', grass: '#86a47e', haze: '#eadfd3', hzStep: 0.13, water: '#c3c6dc',
    tint: '#c8a8b8', tintAmt: 0.12, rim: '#f6c9b8', shadow: 0.6, clouds: { n: 4, top: '#fff6ee', bot: '#e7d5da', a: 230 }, birdC: '#5e5a6e' },
  day: { sky: ['#6aa6d8', '#82b6df', '#9cc6e6', '#b5d4ea', '#cde0ea', '#e0ebe8'], orb: { kind: 'sun', x: 0.8, y: 0.13, r: 7, c: '#fffbe6', glow: '#fff3c4', halo: 5 },
    far: '#9ab0c4', near: '#7c9c96', g0: '#6f9a58', g1: '#446c3c', grass: '#86b068', haze: '#c6d8dc', hzStep: 0.12, water: '#8fbcd8',
    clouds: { n: 5, top: '#ffffff', bot: '#dfe8ef', a: 240 }, birdC: '#3d4a55' },
  golden_hour: { sky: ['#6f93c0', '#9aaec4', '#d4bca0', '#efc48c', '#f7d49a', '#fbe2b0'], orb: { kind: 'sun', x: 0.78, y: 0.15, r: 7, c: '#fff0c8', glow: '#ffd99a', halo: 5 },
    far: '#a898a6', near: '#8a8c84', g0: '#7f9c50', g1: '#4d6a36', grass: '#a0b460', haze: '#ead2ac', hzStep: 0.12, water: '#b0a890',
    tint: '#e0a060', tintAmt: 0.06, rim: '#ffac8a', shadow: 0.9, clouds: { n: 4, top: '#fff0d8', bot: '#e8c0a0', a: 235 }, birdC: '#4a3a30' },
  dusk: { sky: ['#1f2b47', '#34436a', '#5e5f86', '#9a7a93', '#d49a8a', '#eebf98'], orb: { kind: 'sun', x: 0.72, y: 0.35, r: 7, c: '#f8dca8', glow: '#f6d3a0', halo: 4 },
    far: '#6c6a8e', near: '#4b5670', g0: '#4a6448', g1: '#2a4230', grass: '#3f6446', haze: '#9a93ad', hzStep: 0.12, water: '#7d78a0',
    tint: '#5a3f5e', tintAmt: 0.22, rim: '#f2b57a', shadow: 1.0, clouds: { n: 5, top: '#f3cbb7', bot: '#c79fae', a: 235 }, birdC: '#3a3148' },
  night: { sky: ['#060a18', '#0b1430', '#131f45', '#1c2a58', '#263666', '#324476'], orb: { kind: 'moon', x: 0.22, y: 0.17, r: 7, c: '#eef1f8', glow: '#5b6d9c', halo: 5 },
    far: '#1d2848', near: '#162140', g0: '#1a2b2d', g1: '#101b1d', grass: '#22383a', haze: '#2a3560', hzStep: 0.1, tint: '#141d3c', tintAmt: 0.45, water: '#1d2a4a',
    clouds: { n: 3, top: '#2c3766', bot: '#222b54', a: 200 }, stars: 90, birdC: '#2a3148' },
  // the warm plum night that lantern nights use
  plum_night: { sky: ['#0a0922', '#181136', '#281744', '#3a1e4d', '#4f2853', '#673356'], orb: { kind: 'moon', x: 0.82, y: 0.14, r: 5, c: '#f3e6c8', glow: '#6e4a6a', halo: 3 },
    far: '#231836', near: '#1b132c', g0: '#1b2426', g1: '#10181a', grass: '#223030', haze: '#3a2a4a', hzStep: 0.1, tint: '#1d1530', tintAmt: 0.5, water: '#2a1f3e',
    clouds: { n: 3, top: '#3a2a55', bot: '#2a1f40', a: 200 }, stars: 60, birdC: '#2a1f3a', warmFlies: true }
};

/* ---------- mood → theme: weather, specials, events, and your numbers as ambience ---------- */
// your numbers as ambience: a firefly per streak day and a bird per REVIEWS_PER_BIRD of
// today's reviews, up to a limit; a lantern per ANCIENT_PER_LANTERN ancient trees
const MAX_FLIES = 60, REVIEWS_PER_BIRD = 40, MAX_BIRDS = 6, ANCIENT_PER_LANTERN = 12, MAX_LANTERNS = 3;
// how much weather there is to draw: drops, splashes, flakes and glints on the ground
const RAIN_DROPS = 260, STORM_DROPS = 320, SPLASHES = 46, SNOWFLAKES = 190, DEEP_SNOWFLAKES = 320;
const AFTER_RAIN_DROPS = 36, AFTER_RAIN_GLINTS = 40;
// a cloudy night keeps this share of its stars; an aurora night has at least AURORA_STARS
const CLOUDY_STARS = 0.3, AURORA_STARS = 110;
// the aurora hides a moon this close to new
const NEW_MOON_HIDDEN = 0.08;
AF.theme = function (mood, stats, events) {
  const sp = mood.special, night = mood.time === 'night';
  const spec = AF.ENVS[sp] || {};
  const look = (spec.look && spec.look(mood, night)) || AF.TIMES[mood.time] || AF.TIMES.day;
  const th = JSON.parse(JSON.stringify(look));
  if (spec.theme) spec.theme(th, mood, night);
  const w = mood.weather, ev = events || [];
  const mixAll = (keys, col, amt) => keys.forEach(k => { if (th[k]) th[k] = mixHex(th[k], col, amt); });
  const mixSky = (col, amt) => { th.sky = th.sky.map(c => mixHex(c, col, amt)); };
  const skyMid = () => th.sky[Math.floor(th.sky.length / 2)];
  const addTint = (col, amt) => { th.tint = th.tint ? mixHex(th.tint, col, 0.5) : col; th.tintAmt = Math.max(th.tintAmt || 0, amt); };
  if (th.orb) th.orb.phase = mood.moon;
  th.tint = th.tint || null; th.tintAmt = th.tintAmt || 0;
  th.flies = 0; th.birds = 0; th.stars = th.stars || 0;
  const calm = w === 'clear' || w === 'cloudy' || w === 'after_rain';
  const clearSky = w === 'clear' || w === 'after_rain';
  if (calm && (night || mood.time === 'dusk')) th.flies = clamp(stats.streak || 0, 0, MAX_FLIES);
  if (calm && !night) th.birds = clamp(Math.ceil((stats.today_reviews || 0) / REVIEWS_PER_BIRD), 0, MAX_BIRDS);
  if (!clearSky) th.stars = w === 'cloudy' ? Math.round(th.stars * CLOUDY_STARS) : 0;

  if (w === 'cloudy') {
    mixSky(night ? '#1a2030' : '#9aa3ad', 0.6);
    if (th.orb) { th.orb.halo = 0; th.orb.c = mixHex(th.orb.c, skyMid(), 0.6); }
    th.clouds = { n: 7, top: mixHex(th.clouds.top, '#c9ced4', 0.4), bot: mixHex(th.clouds.bot, '#8e98a2', 0.4), a: 245 };
    th.deck = { n: 3, top: night ? '#2a3040' : '#c3c9cf', bot: night ? '#1c2230' : '#9aa3ad', a: 250 };
    addTint('#8e9aa4', 0.12); th.flat = true; th.rim = null; th.shadow = 0;
  } else if (w === 'rain' || w === 'storm') {
    const grey = night ? '#10151c' : (w === 'storm' ? '#3c464e' : '#56626b');
    mixSky(grey, w === 'storm' ? 0.65 : 0.5);
    if (!night) th.sky = th.sky.map((c, i) => i >= th.sky.length - 2 ? mixHex(c, '#6e6a78', 0.5) : c);
    mixAll(['far', 'near'], grey, 0.4); mixAll(['g0', 'g1', 'grass'], '#33443a', 0.25);
    th.haze = mixHex(th.haze, grey, 0.5);
    addTint(w === 'storm' ? '#2a3440' : '#3a4a55', w === 'storm' ? 0.35 : 0.3);
    th.clouds = { n: 9, top: mixHex(grey, '#8a96a0', 0.35), bot: mixHex(grey, '#1a2026', 0.25), a: 250, y0: 0, dy: 0.18, speed: 1.4 };
    th.deck = { n: 3, top: mixHex(grey, '#6a7680', 0.3), bot: mixHex(grey, '#1a2026', 0.3), a: 250 };
    th.rain = w === 'storm' ? STORM_DROPS : RAIN_DROPS; th.splashes = SPLASHES; th.lightning = w === 'storm';
    if (w === 'storm') th.wind = true;
    th.orb = null; th.rim = null; th.shadow = 0;
  } else if (w === 'fog') {
    const fogC = night ? '#3a4458' : '#dcdcd8';
    mixSky(fogC, 0.55); mixAll(['far', 'near'], fogC, 0.5);
    th.haze = fogC; th.hzStep *= 1.25; th.fog = mixHex(fogC, '#ffffff', night ? 0.1 : 0.3);
    th.clouds = null; th.rim = null; th.shadow = 0;
    if (th.orb) { th.orb.halo = 0; th.orb.r *= 1.5; th.orb.c = mixHex(th.orb.c, th.fog, 0.5); th.orb.soft = true; }
  } else if (w === 'snow' || w === 'deep_winter') {
    const deep = w === 'deep_winter';
    mixSky(deep ? (night ? '#1e2432' : '#b7bcc4') : (night ? '#26314a' : '#c9d2df'), deep ? 0.65 : 0.45);
    th.g0 = night ? '#61789a' : '#e8eef6'; th.g1 = night ? '#34465e' : '#cbd6e4'; th.grass = night ? '#7890ac' : '#dfe7f1';
    mixAll(['far', 'near'], night ? '#3a4a66' : (deep ? '#d0d6de' : '#c4cedd'), deep ? 0.55 : 0.4);
    addTint(night ? '#141d3c' : '#9aa6b8', deep ? 0.2 : 0.12);
    th.snow = true; th.snowfall = deep ? DEEP_SNOWFLAKES : SNOWFLAKES;
    th.clouds = { n: deep ? 4 : 3, top: night ? '#3a4566' : '#eef2f7', bot: night ? '#2c3552' : '#d3dbe6', a: 230 };
    th.water = night ? '#40506c' : '#c9d6e6'; th.shadow = 0;
    if (th.orb && th.orb.kind === 'sun') { th.orb.halo = 0; th.orb.c = mixHex(th.orb.c, skyMid(), 0.6); }
    if (deep) { th.deepSnow = true; th.frozen = true; th.water = night ? '#5a6a86' : '#dfe8f0'; th.orb = null; th.stars = 0; th.rim = null;
      th.deck = { n: 3, top: night ? '#2a3040' : '#c8cdd4', bot: night ? '#1c2230' : '#a8aeb8', a: 250 }; }
  } else if (w === 'after_rain') {
    mixSky('#b8bcc8', 0.18);
    th.rainbow = !night; th.glints = AFTER_RAIN_GLINTS; th.rain = AFTER_RAIN_DROPS; th.rainLight = true; th.puddles = true;
    if (th.clouds) { th.clouds.y0 = 0; th.clouds.dy = 0.1; }
    mixAll(['g0', 'g1'], '#2f4a3a', 0.15);
  }
  if (mood.wind) th.wind = true;

  // the sky already holds a fixed field of them
  if (sp === 'lanterns') th.lanterns = clamp(Math.round((stats.ancient || 0) / ANCIENT_PER_LANTERN), 1, MAX_LANTERNS);
  if (sp === 'aurora' && w !== 'rain' && w !== 'storm') {
    th.aurora = true; if (clearSky) th.stars = Math.max(th.stars, AURORA_STARS);
    if (th.orb && th.orb.kind === 'moon') { if (mood.moon < NEW_MOON_HIDDEN || mood.moon > 1 - NEW_MOON_HIDDEN) th.orb = null; else th.orb.x = 0.86; }
  }
  if (night && clearSky) {
    th.shooting = true;
    if (ev.includes('meteor_shower')) th.meteors = true;
    if (ev.includes('new_ancient')) th.bigStar = true;
    if (ev.includes('harvest_moon') && th.orb) th.orb = { kind: 'moon', x: 0.7, y: 0.33, r: 11, c: '#f4c27a', glow: '#c98a4a', halo: 6, full: true };
  }
  // an environment's last word, once the weather and the sky are settled
  if (spec.after) spec.after(th, mood, night, stats);
  return th;
};
})();

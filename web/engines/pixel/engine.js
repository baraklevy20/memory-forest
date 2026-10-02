/* Memory Forest — pixel-art engine: puts the sky, the ground, the trees and the water
 * together for the scene runner. Environments, landscapes and landmarks hook in from their
 * own files. Everything is drawn on a low-resolution canvas and scaled up. */
(function () {
'use strict';
const AF = window.AnkiForest;
const { layer } = AF.u;
const { fogVeil, ridges, drawSky, drawGround, groundDetails, deepForest, sprite, HAZE_STEPS } = AF.pixel;

// the light comes from the other side once the sun or moon is past this far across
const FLIP_LIGHT_X = 0.55;
// in fog, the land already drawn is veiled again from depth FOG_VEIL_FROM, every
// FOG_VEIL_STEP, up to FOG_VEIL_TO, by FOG_VEIL_AMT unless the theme says otherwise
const FOG_VEIL_FROM = 0.08, FOG_VEIL_STEP = 0.12, FOG_VEIL_TO = 0.85, FOG_VEIL_AMT = 0.2;
// a lightning flash lifts the land this far towards white
const FLASH_LIFT = 0.35;

AF.engines.pixel = {
  prepare(env) {
    const th = env.theme;
    const spec = AF.envOf(env);
    if (spec.prepare) spec.prepare(env, th);
    env.quantize = spec.quantize || null;
    // the landscape has the last word on how much room it takes at the front
    const land = AF.landOf(env);
    if (land.prepare) land.prepare(env);

    env.flipLight = !!(th.orb && th.orb.x > FLIP_LIGHT_X && spec.flipLight !== false);
    env.ridges = ridges(env);
  },
  sky: drawSky,
  steps(env) {
    const th = env.theme, { W, H, u } = env, steps = [lg => drawGround(env, lg)], land = AF.landOf(env);
    // what the landscape lays on the ground before anything stands on it, e.g. a river's bed
    if (land.bed) steps.push(lg => land.bed(env, lg));
    // a landscape with an open horizon (`noDeep`) has nowhere for a distant treeline
    if (env.deep && !land.noDeep) steps.push(lg => deepForest(env, lg));
    let nextFog = th.fog ? FOG_VEIL_FROM : Infinity;
    for (const p of env.placed) {
      if (th.fog && p.it.depth >= nextFog && nextFog < FOG_VEIL_TO) { steps.push(lg => fogVeil(lg, W, H, p.y, th.fog, th.fogAmt || FOG_VEIL_AMT)); nextFog += FOG_VEIL_STEP; }
      if (p.it.pond) { steps.push(lg => AF.drawPond(lg, env, p)); continue; }
      steps.push(lg => {
        const h = Math.max(3, Math.round(AF.STAGE_H[p.it.stage] * u * p.s)), spr = sprite(p.it, h, Math.round(p.hz * HAZE_STEPS), env);
        groundDetails(env, lg, p, spr.width - 4);
        const x0 = Math.round(p.x - spr.width / 2), y0 = Math.round(p.y - spr.height + 1);
        if (env.flipLight) { lg.save(); lg.translate(x0 + spr.width, y0); lg.scale(-1, 1); lg.drawImage(spr, 0, 0); lg.restore(); } else lg.drawImage(spr, x0, y0);
        if (env.afterItem) env.afterItem(lg, p);
      });
    }
    return steps;
  },
  post(env) {
    const { W, H } = env;
    if (env.theme.lightning) {  // a brighter copy of the land, shown while lightning flashes
      const [lit, lg] = layer(W, H); lg.drawImage(env.land, 0, 0);
      const img = lg.getImageData(0, 0, W, H), d = img.data;
      for (let i = 0; i < d.length; i += 4) if (d[i + 3]) { d[i] += (235 - d[i]) * FLASH_LIFT; d[i + 1] += (240 - d[i + 1]) * FLASH_LIFT; d[i + 2] += (255 - d[i + 2]) * FLASH_LIFT; }
      lg.putImageData(img, 0, 0); env.landLit = lit;
    }
    const land = AF.landOf(env);
    if (land.post) land.post(env);  // a lake builds its reflection here, a river finds its open water
    env.lake = env.water;
  },
  frameBack(g, env, t) {
    const land = AF.landOf(env);
    if (land.frameBack) land.frameBack(g, env, t);  // e.g. a sea of cloud far below
  },
  frame(g, env, t) {
    const land = AF.landOf(env);
    if (land.frame) land.frame(g, env, t);          // water, glints on the sea
    const mk = AF.markOf(env);
    if (mk.frame) mk.frame(g, env, t);              // falling water, a sweeping beam
    if (land.frameFront) land.frameFront(g, env, t);  // and what falls in front of it all
    const spec = AF.envOf(env);
    if (spec.frame) spec.frame(g, env, t);
  }
};
})();

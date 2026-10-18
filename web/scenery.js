/* Memory Forest — the registries environments, landscapes and landmarks add themselves to,
 * each from a file of its own. */
(function () {
'use strict';
const AF = window.AnkiForest;

/* ---------- environments ----------
 * Each environment lives in web/envs/<key>.js and registers itself here: its look, its
 * tweaks to the theme, its tree colours and its scenery. Delete that file and the
 * environment is gone - nothing else in the add-on mentions it by name. */
// kept if already there: a second copy of the add-on on the same page (the public
// edition beside this one) adds to these rather than wiping what the first registered
AF.ENVS = AF.ENVS || {};
AF.env = function (key, spec) { AF.ENVS[key] = spec; };
AF.envOf = env => AF.ENVS[env.mood.special] || {};

/* ---------- landscapes and landmarks ----------
 * The same bargain as environments: web/landscapes/<key>.js holds everything that makes a
 * lake a lake, web/landmarks/<key>.js everything that makes a peak a peak, and deleting
 * either file removes it from the add-on. A scene has one landscape and one landmark. */
AF.LANDSCAPES = AF.LANDSCAPES || {};
AF.landscape = function (key, spec) { AF.LANDSCAPES[key] = spec; };
/* A scenery that frames the forest in a window (the rooms) sets env.fitX(x, env) in its
 * prepare: every landscape then plants its rows through it, the landscape's own squeeze
 * still applied first, so each tree stands where it can be seen and hovered. */
const fitted = new WeakMap(), NO_LAND = {};  // (one stand-in for no landscape, so its wrapper is kept too)
AF.landOf = env => {
  const land = AF.LANDSCAPES[env.mood.landscape] || NO_LAND, fit = env.fitX;
  if (!fit) return land;
  let byFit = fitted.get(land);
  if (!byFit) fitted.set(land, byFit = new Map());
  if (!byFit.has(fit)) {
    byFit.set(fit, Object.assign(Object.create(land), {
      placeX(it, e) { return fit(land.placeX ? land.placeX(it, e) : it.x, e); },
    }));
  }
  return byFit.get(fit);
};

AF.LANDMARKS = AF.LANDMARKS || {};
AF.landmark = function (key, spec) { AF.LANDMARKS[key] = spec; };
/* An environment may stand a landmark of its own in for the scene's (env.landmarkKey, set in
 * its prepare: the lanterns' larger moon bridge), leaving the scene's data as it came. */
AF.markOf = env => AF.LANDMARKS[env.landmarkKey || env.mood.landmark] || {};
})();

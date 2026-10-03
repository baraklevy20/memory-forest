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
AF.landOf = env => AF.LANDSCAPES[env.mood.landscape] || {};

AF.LANDMARKS = AF.LANDMARKS || {};
AF.landmark = function (key, spec) { AF.LANDMARKS[key] = spec; };
AF.markOf = env => AF.LANDMARKS[env.mood.landmark] || {};
})();

/* A river running across the front of the forest, with its far bank below.
 *
 * Shallower than the lake, and flowing: the water is a band rather than everything from
 * the shore down, and it carries drifting flow lines instead of the sun's reflection. */
(function () {
'use strict';
const AF = window.AnkiForest;

AF.landscape('river', {
  prepare(env) { env.bot = 0.77; env.visitorY = env.H * 0.815; },
  post(env) { AF.buildWater(env, { y0: 0.83, deep: 0.1, shore: 0.8, step: 2.2, tint: 0.4, river: true }); },
  frame(g, env, t) { AF.drawWater(g, env, t); },
});
})();

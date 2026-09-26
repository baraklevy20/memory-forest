/* A still lake across the front of the forest, holding its reflection.
 *
 * The engine owns the reflecting machinery, because an environment can borrow it too
 * (synthwave lays neon stripes on the same water). The lake only says where its water
 * sits and how deeply it stains what it reflects. */
(function () {
'use strict';
const AF = window.AnkiForest;

AF.landscape('lake', {
  prepare(env) { env.bot = 0.74; env.visitorY = env.H * 0.785; },
  post(env) { AF.buildWater(env, { y0: 0.8, deep: 1, shore: 0.765, step: 2.9, tint: 0.28 }); },
  frame(g, env, t) { AF.drawWater(g, env, t); },
});
})();

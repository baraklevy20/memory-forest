/* Memory Forest — bootstrap: mount the forest with the data the add-on embedded in the page. */
(function () {
'use strict';
// the page names this add-on's panel on the script tag, and holds its data beside it
const id = document.currentScript && document.currentScript.dataset.root;
const root = id && document.getElementById(id), json = id && document.getElementById(id + '-data');
if (!root || !json || !window.AnkiForest) return;
let data;
try { data = JSON.parse(json.textContent); } catch (e) { console.error('Memory Forest could not read its data:', e); root.remove(); return; }
try { window.AnkiForest.mount(root, data); }
catch (e) { console.error('Memory Forest could not draw the forest:', e); root.remove(); }
})();

/* Memory Forest — bootstrap: mount the forest with the data the add-on embedded in the page. */
(function () {
'use strict';
// the page names this add-on's panel on the script tag, and holds its data beside it
const id = document.currentScript && document.currentScript.dataset.root;
const root = id && document.getElementById(id), json = id && document.getElementById(id + '-data');
const AF = window.AnkiForest;
if (!root || !json || !AF) return;
// this copy's files are all loaded: let the name go, so no other copy can build on this one
window.AnkiForest = undefined;
let data;
try { data = JSON.parse(json.textContent); } catch (e) { console.error('Memory Forest could not read its data:', e); root.remove(); return; }
try { AF.mount(root, data); }
catch (e) { console.error('Memory Forest could not draw the forest:', e); root.remove(); }
})();

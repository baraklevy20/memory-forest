# Developing Memory Forest

## Layout

```
__init__.py      Anki hooks, caching, background weather refresh, click-to-browse
settings.py      the settings dialog (changes apply immediately)
presets.py       the ready-made scenes the dialog offers
forest_data.py   SQL rows → trees, stats, visitors (no aqt; unit-tested)
scene.py         environment/weather/time selection, moon phase, journal
weather.py       Open-Meteo geocoding + forecast, JSON cache in user_files/
store.py         the small JSON files under user_files/, written atomically
web/core.js      layout, themes, runner, tooltips, visitors, ponds
web/effects.js   clouds, rain, snow, fireflies, birds, wind…
web/engines/pixel.js   sky, ground, landscapes, tree sprites and palettes
catalog.py       what this copy can draw, read from the files under web/
web/envs/*.js        one file per environment: its look, trees, scenery and effects
web/envs/*.json      ... and beside it, its label and its preset
web/landscapes/      one .js and one .json per landscape
web/landmarks/       one .js and one .json per landmark
dev/             packaging, previews and the render checks
```

Environments, landscapes and landmarks are each **a .js and a .json** under `web/`: the
code that draws it, and its label (plus, for an environment, its preset). Delete the pair
and it is gone - nothing else in the add-on names it, and only the pieces a scene actually
uses are sent to the page.

## Development

Everything runs through npm from this folder, so there is one place to look:

```
npm install
npm run build          # the .ankiaddon to upload
npm test               # the unit tests, no Anki needed
npm run lint           # eslint over the JavaScript, ruff over the Python
npm run check          # lint, tests and the full render sweep: what to run before tagging

npm run render         # every preset, and every environment against every
                       # landscape, hour and weather, checked for errors and blank canvases
npm run render:quick   # a representative subset, for a fast loop
npm run baseline       # record what every scene looks like (kept locally, not committed)
npm run compare        # ... and check after a refactor that nothing moved (add :quick for a subset)
npm run audit          # what each setting actually changes; fails on one that does nothing

npm run payload -- "~/Library/Application Support/Anki2/User 1/collection.anki2"
npm run gallery        # writes dev/gallery.html
```

The render checks need Chrome. The export copies the collection (and its `-wal`) before
reading, so it is safe while Anki is open. `dev/payload.js` holds your study history and is
gitignored, and `dev/package.py` refuses to build an add-on file that would ship it.

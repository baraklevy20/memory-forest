# Developing Memory Forest

## Layout

```
__init__.py      connects the add-on to Anki: the hooks, and nothing else
panel.py         the forest panel's HTML and scripts, and redrawing it in place
payload.py       what a panel is drawn from: cached trees, the day's scene, the numbers
live_weather.py  the live weather for your city: its cache, and refreshing it in the background
actions.py       clicks (settings, browse a tree's cards) and the deck gear menu
planting.py      the "a new tree was planted" message
events_state.py  the events on Anki's side: the Stakes remembered per profile, and what the page is sent
debug_events.py  the Debug group's study events and timeline (debug only)
state.py         the config, and what is remembered per profile in user_files/
settings/        the settings dialog: dialog.py, and one file per tab (changes apply immediately)
presets.py       the ready-made scenes the dialog offers
study_log.py     what is read from the collection: cards, review log, Anki days (no aqt)
forest_data.py   rows → trees, stages, health, ponds and stats (no aqt; unit-tested)
memory.py        the FSRS forgetting curve (no aqt)
milestones.py    the animals that move in, and anniversaries (no aqt)
events.py        the events' rules: stakes and strikes, big days, tall grass (no aqt)
fake_forest.py   the made-up test forest, for debug (no aqt)
scene.py         environment/weather/time selection, moon phase, night-sky events
journal.py       the one line under the forest, on the days there is something to say
weather.py       Open-Meteo geocoding + forecast, JSON cache in user_files/
store.py         the small JSON files under user_files/, written atomically
catalog.py       what this copy can draw, read from the files under web/, and the
                 scripts every forest loads, in order
web/util.js      shared helpers; makes window.AnkiForest, so it loads first
web/layout.js    where the trees, ponds and deep forest stand
web/scenery.js   the registries environments, landscapes and landmarks add themselves to
web/theme.js     times of day, and the theme the weather and your numbers make of them
web/visitors.js  the milestone animals and the cabin
web/ponds.js     ponds and puddles
web/tooltips.js  what hovering says
web/caption.js   the line of numbers under the forest
web/hover.js     pointing at the forest: what is under the pointer, its tooltip, a click
web/core.js      the scene runner: mount, draw each frame, swap
web/effects.js   the moving effects' order; the effects are in web/effects/:
                 weather.js (clouds, rain, snow, lightning, wind, fog) and
                 ambience.js (stars, fireflies, birds, lanterns, petals, falling leaves)
web/events.js    the events' registry, and the points where the scene calls them; each event
                 is a file in web/events/: asteroid.js (the Stakes' asteroid, the strike and its
                 craters), crows.js (leeches), grass.js (tall grass), flowers.js (big days)
web/engines/pixel/   the pixel engine: trees.js (sprites, palettes), sky.js, ground.js
                     (ground, landmark, deep forest), water.js, engine.js (puts it together)
web/envs/*.js        one file per environment: its look, trees, scenery and effects
web/envs/*.json      ... and beside it, its label and its preset
web/landscapes/      one .js and one .json per landscape
web/landmarks/       one .js and one .json per landmark
tests/           one test file per module, sharing tests/helpers.py; the modules that talk
                 to Anki run against a stand-in Anki (tests/fake_anki.py)
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

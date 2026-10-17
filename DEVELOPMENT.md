# Developing Memory Forest

## Layout

```
__init__.py      connects the add-on to Anki: the hooks, and nothing else
panel.py         the forest panel's HTML and scripts, and redrawing it in place
payload.py       what a panel is drawn from: cached trees, the day's scene, the numbers
live_weather.py  the live weather for your city: its cache, and refreshing it in the background
actions.py       clicks (settings, browse a tree's cards or a heatmap day's) and the deck gear menu
answer_column.py the answer buttons' column, where the forest's study events are read from
planting.py      the "a new tree was planted" message
phone.py         the forest on your phone: the note, deck and script it syncs in, written at each sync
phone_note.py    telling that note, its deck and its cards apart from your own study
phone_data.py    what that note holds: the page's data and the next days' scenes, and the one-file script (no aqt)
events_state.py  the events on Anki's side: Nature read from the days you studied, and what the page is sent
debug_events.py  the Debug tab's study events and timeline (debug only)
state.py         the config, and what is remembered per profile in user_files/
marks.py         the days you mark as important on the heatmap (exams, trips), kept per profile
news.py          what an update announces: the cog's dot, NEW and IMPROVED on tiles, a note on the forest
release_notes.py release_notes.json read and rendered: the About tab, the AnkiWeb page, the GitHub release
heatmap_look.py  the heatmap's colours and tiles: each scenery's own, and the ready-made ramps (no aqt)
seasons.py       the day the forest is drawn for
edition.py       which edition this copy is (Memory Forest or Plus), and whether it has the debug tools
scope.py         what the forest counts: the decks left out, its days, and whether the study data changed
settings/        the settings dialog: dialog.py, and one file per tab (changes apply immediately):
                 scenery_tab.py, forest_tab.py, heatmap_tab.py (the heatmap's views, streak and look),
                 decks.py, about.py
presets.py       the ready-made scenes the dialog offers
study_log.py     what is read from the collection: cards, review log, Anki days (no aqt)
forest_data.py   rows → trees, stages, health, ponds and stats (no aqt; unit-tested)
memory.py        the FSRS forgetting curve (no aqt)
milestones.py    the animals that move in, and anniversaries (no aqt)
events.py        the events' rules: Nature's strikes and fire, big days, tall grass, review hell (no aqt)
fake_forest.py   the made-up test forest, for debug (no aqt)
scene.py         environment/weather/time selection, moon phase, night-sky events
journal.py       the one line under the forest, on the days there is something to say
weather.py       Photon geocoding + MET Norway forecast, sun times, JSON cache in user_files/
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
web/visit.js     the zoom button: the forest's older rows, brought up close and walked through
web/calendar.js  the study heatmap under the forest: its views, streak, trophies, marks and tooltips
web/heatmap/     the heatmap's tile styles, a .js and a .json each (flat, round, contours), and the
                 ready-made colour ramps' .json
web/core.js      the scene runner: mount, draw each frame, swap
web/phone.js     the phone card's boot script: today's scene by the phone's clock, then mount
web/effects.js   the moving effects' order; the effects are in web/effects/:
                 weather.js (clouds, rain, snow, lightning, wind, fog) and
                 ambience.js (stars, fireflies, birds, lanterns, petals, falling leaves)
web/events.js    the events' registry, and the points where the scene calls them; each event
                 is a file in web/events/: asteroid.js (Merciless's asteroid, the strike and its
                 craters), crows.js (leeches), robins.js (leeches cured), grass.js (tall
                 grass), tumbleweeds.js (review hell), flowers.js (big days), fire.js
                 (Wild's fire; the burnt trees' char is in engines/pixel/trees.js)
web/engines/pixel/   the pixel engine: trees.js (sprites, palettes), sky.js, ground.js
                     (ground, landmark, deep forest), water.js, engine.js (puts it together)
web/envs/*.js        one file per environment: its look, trees, scenery and effects
web/envs/*.json      ... and beside it, its label and its preset
web/landscapes/      one .js and one .json per landscape
web/landmarks/       one .js and one .json per landmark (moon_bridge, peak, pagoda)
tests/           one test file per module, sharing tests/helpers.py; the modules that talk
                 to Anki run against a stand-in Anki (tests/fake_anki.py)
e2e/             the checks that run the real files: the render checks (render_check.py), the
                 phone and heatmap checks in headless Chrome, and the add-on in old Ankis (old_anki.py)
dev/             packaging, previews, pictures for the docs and the perf tools
```

Environments, landscapes and landmarks are each **a .js and a .json** under `web/`: the
code that draws it, and its label (plus, for an environment, its preset). Delete the pair
and it is gone - nothing else in the add-on names it, and only the pieces a scene actually
uses are sent to the page.


## Development

Everything runs through npm from this folder, so there is one place to look:

```
npm install
npm run build          # package only, no tests; output in dist/ (gitignored)
npm run check:anki     # real Anki compatibility tests, headless by default
npm test               # the unit tests, no Anki needed; then the phone and heatmap checks,
                       # only if their files changed (uncommitted, or in the last commit)
npm run test:phone     # the phone card in headless Chrome, whatever changed
npm run test:heatmap   # the heatmap's hover layer in headless Chrome, whatever changed
npm run lint           # eslint over the JavaScript and the node tooling, ruff over the Python
npm run check          # lint, tests and the full render sweep: what to run before tagging

npm run render         # every preset, and every environment against every
                       # landscape, hour and weather, checked for errors and blank canvases
npm run render:quick   # a representative subset, for a fast loop
npm run baseline       # record what every scene looks like (kept locally, not committed)
npm run compare        # ... and check after a refactor that nothing moved (add :quick for a subset)
npm run perf:baseline  # record what each scene costs in CPU and memory (kept locally, not committed)
npm run perf           # ... and check a change made none of them cost much more (dev/perf_check.mjs)
npm run audit          # what each setting actually changes; fails on one that does nothing

npm run payload -- "~/Library/Application Support/Anki2/User 1/collection.anki2"
npm run gallery        # writes dev/gallery.html
```

The perf check measures CPU in instructions a second, from macOS's hardware counters: unlike
CPU %, they hardly move with whatever else the machine is doing. It needs macOS, and a baseline
is only good for the machine and Chrome it was made on. To look into a cost, `node dev/profile.mjs
<preset>` breaks it down (`--calls` for who draws what, `--changes` for what moves) and `node
dev/memory.mjs <preset>` does the same for memory.

Build targets never run tests automatically. CI runs the checks separately: the unit tests,
the render checks and, since a fresh checkout cannot tell what changed, the phone and heatmap
checks every time. For an
explicit compatibility check of a particular build, run
`python3 e2e/old_anki.py --check --all --package path/to/addon.ankiaddon`.
The Anki checks use Qt's offscreen platform and do not activate native windows;
`--show` opts into visible windows for interactive debugging.

The render checks need Chrome. The export copies the collection (and its `-wal`) before
reading, so it is safe while Anki is open. `dev/payload.js` holds your study history and is
gitignored, and `dev/package.py` refuses to build an add-on file that would ship it.

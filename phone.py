"""The forest on your phone: a note of its own that AnkiWeb carries to AnkiDroid and
AnkiMobile, whose card draws the forest (the "Show my forest on my phone" setting).

Each sync writes the forest into the note first, so the phone gets it as it is now, and
again once the sync is done, since the reviews it brought in from the phone may have
grown it; the next sync takes that along. The drawing itself travels as one script in the
collection's media (phone_data.bundle). The note's card sits new in a deck of its own:
study that deck to look at the forest, and leave without answering. A card that was
answered anyway is made new again, and the deck never counts towards the forest.

Nothing is created until the setting is on, and turning it off takes the deck and note
away again (remove); only the empty note type stays, since removing one forces a full sync.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import traceback

from aqt import mw

from . import events_state, live_weather, payload, phone_data
from .state import OFF_VALUES, PHONE_DECK, PHONE_NOTETYPE, config, follow_season, log, remember_phone_cards, today

DECK = PHONE_DECK
FIELDS = ("About", "Forest")  # never change these: a field added later forces a full sync
ABOUT = ("Memory Forest keeps your forest here, so your phone can show it. Study this deck to see it, "
         "and go back without answering. The add-on rewrites this note at every sync.")
# the deck's own options: the one card always shows when the deck is studied
NEW_PER_DAY, REVIEWS_PER_DAY = 100, 9999
# ... and keeps coming back: Again, Hard and Good move it along learning steps a second
# long (in minutes, as Anki keeps them), so only Easy, whose interval is at least a day, takes
# it out of the deck, and the next sync makes it new again (_keep_new)
STEPS = [1 / 60] * 50

FRONT = """<div id="memory-forest-phone" class="af-panel"></div>
<script type="application/json" id="memory-forest-phone-data">{{Forest}}</script>
<script>
(function () {
  var root = document.getElementById('memory-forest-phone'), data = null;
  try { data = JSON.parse(document.getElementById('memory-forest-phone-data').textContent); } catch (e) {}
  if (!data || !data.script) { root.textContent = 'Your forest arrives with the next sync from Anki on your computer.'; return; }
  var s = document.createElement('script');
  s.src = data.script;
  s.charset = 'utf-8';
  s.setAttribute('data-root', 'memory-forest-phone');
  s.onerror = function () { root.textContent = 'Your forest is on its way: sync once more to fetch its drawing.'; };
  document.body.appendChild(s);
})();
</script>"""
BACK = "{{FrontSide}}"
CSS = """.card { margin: 0; padding: 0; }
.af-panel { margin-top: 12px; }
.af-phone-note { margin: 6px 12px 12px; font: 11.5px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif; color: #8a8f8c; text-align: center; }
.af-turn { display: block; margin: 8px auto 0; min-height: 40px; padding: 8px 22px; border: 1px solid currentColor; border-radius: 20px;
           background: none; color: inherit; font: inherit; font-size: 15px; font-weight: 600; }
.af-turn[hidden] { display: none; }
.af-sideways { position: fixed; top: 0; left: 0; transform-origin: top left; box-sizing: border-box;
               display: flex; flex-direction: column; justify-content: center; }
.af-sideways .af-panel { margin: 0 auto; }
.af-sideways .af-phone-note { margin-bottom: 0; }
.af-sideways .af-cap-tip { display: none !important; }
.af-phone-stage { display: flex; flex-direction: column; justify-content: center; }
.af-phone-note + .af-phone-note { margin-top: -6px; }
.af-phone-shell:fullscreen { overflow: hidden; }
.af-phone-shell:fullscreen .af-caption, .af-phone-shell:fullscreen .af-phone-note { display: none; }
.af-phone-shell:fullscreen .af-phone-stage:not(.af-sideways) { display: flex; flex-direction: column; justify-content: center; height: 100%; }"""


def enabled(cfg: dict | None = None) -> bool:
    return (cfg if cfg is not None else config()).get("phone_forest", False) not in OFF_VALUES


def _notetype(col) -> dict:
    """The note type, made on first use, with its template brought up to date: changing a
    template's text needs no full sync, only adding or removing fields and templates does."""
    mm = col.models
    m = mm.by_name(PHONE_NOTETYPE)
    if m is None:
        m = mm.new(PHONE_NOTETYPE)
        for name in FIELDS:
            mm.add_field(m, mm.new_field(name))
        t = mm.new_template("Forest")
        t["qfmt"], t["afmt"] = FRONT, BACK
        mm.add_template(m, t)
        m["css"] = CSS
        mm.add(m)
        return mm.by_name(PHONE_NOTETYPE)
    t = m["tmpls"][0]
    if (t["qfmt"], t["afmt"], m["css"]) != (FRONT, BACK, CSS):
        t["qfmt"], t["afmt"], m["css"] = FRONT, BACK, CSS
        mm.update_dict(m)
    return m


def _options(col, did: int) -> None:
    """Give the forest's deck options that always let its one card show and keep it coming
    back, or bring them up to date - unless the user gave the deck options of their own.
    Only ever the add-on's own deck: never one the card was moved to, nor a filtered deck."""
    deck = col.decks.get(did, default=False)
    if not deck or deck.get("dyn"):  # a filtered deck has no options of its own
        return
    if deck.get("conf", 1) == 1:  # still on the default options, which may hold no new cards
        # the preset outlives the deck (removing one forces a full sync), so reuse it
        conf = next((c for c in col.decks.all_config() if c["name"] == DECK), None) or col.decks.add_config(DECK)
        deck["conf"] = conf["id"]
        col.decks.save(deck)
    conf = col.decks.config_dict_for_deck_id(did)
    if not conf or conf.get("name") != DECK:
        return
    steps = conf["new"]["delays"]
    same_steps = len(steps) == len(STEPS) and all(abs(a - b) < 1e-4 for a, b in zip(steps, STEPS))  # kept as float32
    if (conf["new"]["perDay"], conf["rev"]["perDay"]) != (NEW_PER_DAY, REVIEWS_PER_DAY) or not same_steps:
        conf["new"]["perDay"], conf["rev"]["perDay"], conf["new"]["delays"] = NEW_PER_DAY, REVIEWS_PER_DAY, STEPS
        col.decks.update_config(conf)


def _note(col):
    """The note that carries the forest, made (with its note type and deck) if it is missing.
    Its card may have been moved to another deck since, or borrowed by a filtered one: the
    options only ever go to the add-on's own deck, and that deck is not made again."""
    m = _notetype(col)
    nids = col.db.list("select id from notes where mid = ? order by id", m["id"])
    if nids:
        note = col.get_note(nids[0])
        mine = col.decks.id_for_name(DECK)
        if mine:
            _options(col, mine)
        return note
    note = col.new_note(m)
    note["About"], note["Forest"] = ABOUT, ""
    did = col.decks.id(DECK)
    _options(col, did)
    col.add_note(note, did)
    log("made the note that takes the forest to your phone")
    return note


# each file's name in media (made from what is in it), worked out once a session and again
# only if its source changed on disk: {key: (modified times, name)}. Only names are kept: a
# file's text is made again on the rare occasion it has to be written.
_names: dict = {}
# the files the note last needed, so the media folder is only looked through when they change
_written: tuple = (None, frozenset())


def _named(key: str, paths: list, name) -> str:
    stamp = tuple(os.path.getmtime(p) for p in paths)
    hit = _names.get(key)
    if not hit or hit[0] != stamp:
        hit = _names[key] = (stamp, name())
    return hit[1]


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _scripts(col, days: list) -> tuple:
    """(the script the card loads, {scenery file: its name} for the days' scenes): in the
    collection's media, under names made from what is in them. Every scenery this copy ships
    is written, not only the days': so changing the scenery uploads nothing new, and the media
    changes once an update, when the names do. Older copies go, so the next sync removes them
    from the phone too."""
    web = phone_data.catalog.WEB
    core = [os.path.join(web, rel) for rel in phone_data.catalog.core_scripts(web)] + [
        os.path.join(web, "forest.css"), os.path.join(web, phone_data.BOOT)]

    def bundle() -> bytes:
        return phone_data.bundle().encode("utf-8")
    name = _named("bundle", core, lambda: f"{phone_data.SCRIPT_PREFIX}{hashlib.sha1(bundle()).hexdigest()[:10]}.js")
    files, names = {name: bundle}, {}
    for rel in phone_data.all_scenery(web):
        path = os.path.join(web, rel)
        names[rel] = _named(rel, [path], lambda rel=rel, path=path: phone_data.part_name(rel, _read(path)))
        files[names[rel]] = lambda path=path: _read(path)
    global _written
    here = col.media.dir()
    # each time, as it costs no more than a look: whatever was taken away since (by another
    # copy of the add-on, or a sync from a computer on another version) is written again
    for fname, text in files.items():
        if not os.path.exists(os.path.join(here, fname)):
            col.media.write_data(fname, text())
    if _written != (here, frozenset(files)):
        old = [f for f in os.listdir(here) if f.startswith(phone_data.SCRIPT_PREFIX) and f.endswith(".js") and f not in files]
        if old:
            col.media.trash_files(old)
        _written = (here, frozenset(files))
    return name, {rel: names[rel] for rel in phone_data.scenery(days, web)}  # the note names only the days'


def _keep_new(col, note) -> None:
    """Answered, suspended or buried on the phone: new again, so the deck keeps showing it."""
    stale = [cid for cid in col.card_ids_of_note(note.id)
             if (card := col.get_card(cid)).type != 0 or card.queue < 0]
    if stale:
        col.sched.schedule_cards_as_new(stale, restore_position=True, reset_counts=True)


def remove() -> None:
    """Take the forest off the phone: its note, its deck and its script in media. The deck
    only goes if nothing else was put in it, and a deck the card was moved to stays. The note
    type and the deck's options preset stay: removing either forces a full sync, and they are
    empty and out of the way. Anki keeps the reviews of the cards removed, so they are
    remembered, and those reviews go on being left out of your study (state.phone_cards)."""
    global _written
    col = mw.col
    m = col.models.by_name(PHONE_NOTETYPE) if col is not None else None
    if m is None:
        return
    try:
        nids = col.db.list("select id from notes where mid = ?", m["id"])
        if nids:
            remember_phone_cards(col.db.list("select id from cards where nid in (select id from notes where mid = ?)", m["id"]))
            col.remove_notes(nids)
        mine = col.decks.id_for_name(DECK)
        if mine and len(col.decks.deck_and_child_ids(mine)) == 1 and not col.db.scalar(
                "select count() from cards where did = ? or odid = ?", mine, mine):  # nothing else lives here now
            col.decks.remove([mine])
        folder = col.media.dir()
        _written = (None, frozenset())  # written again when the setting comes back on
        scripts = [f for f in os.listdir(folder) if f.startswith(phone_data.SCRIPT_PREFIX) and f.endswith(".js")]
        if scripts:
            col.media.trash_files(scripts)
        log("took the forest off your phone")
    except Exception:
        log("could not take the forest off your phone:\n" + traceback.format_exc())


# whether the setting was on when last looked at: only turning it off removes the deck, so a
# computer that never had it on leaves alone the one another computer keeps
_was_on: bool | None = None


def follow_setting() -> bool:
    """After the settings change: turned on, the note is made (or brought up to date) now
    rather than at the next sync; turned off, the deck goes. True when the setting was just
    turned on or off, so the deck may have come or gone."""
    global _was_on
    on = enabled()
    if on:
        publish()
    elif _was_on:
        remove()
    flipped = on != bool(_was_on)  # (not looked at yet: it was off)
    _was_on = on
    return flipped


def remember_setting() -> None:
    """Note whether the setting is on, before anything can change it."""
    global _was_on
    _was_on = enabled()


def publish() -> None:
    """Write the forest as it is now into the note, if the setting is on and it changed."""
    col = mw.col
    cfg = follow_season(config())  # before the forest is drawn for it, as the desktop's is
    if col is None or not enabled(cfg):
        return
    try:
        note = _note(col)
        real, place, _error = live_weather.for_config(cfg)
        name = getattr(payload, "_scene_name", None)
        now = _dt.datetime.combine(today(cfg), _dt.datetime.now().time())  # or the debug date's
        page = payload.payload()
        strike = page.get("strike")
        if strike and strike.get("news") and "before" not in strike:
            # the phone can't ask for the forest a strike took, so it comes along while the
            # strike is news; after that its crater no longer plays it there
            page = dict(page, strike=dict(strike, **(events_state.strike_before(strike["seen"]) or {})))
        scene_name = (lambda date: name(cfg, date)) if name else (lambda _date: {})
        days = phone_data.schedule(cfg, now, real, place, scene_name)
        script, parts = _scripts(col, days)
        data = phone_data.phone_payload(page, cfg, now, script, real, place, scene_name, parts, days)
        if not phone_data.same_forest(note["Forest"], data):
            note["Forest"] = phone_data.encode(data)
            col.update_note(note, skip_undo_entry=True)
        _keep_new(col, note)
    except Exception:
        log("could not update the forest for your phone:\n" + traceback.format_exc())

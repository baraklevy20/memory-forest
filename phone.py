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

from . import live_weather, payload, phone_data
from .state import OFF_VALUES, PHONE_NOTETYPE, config, log

DECK = "Memory Forest"
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
.af-turn { margin-left: 4px; padding: 2px 8px; border: 1px solid currentColor; border-radius: 10px; background: none; color: inherit; font: inherit; }
.af-turn[hidden] { display: none; }
.af-sideways { position: fixed; top: 0; left: 0; transform-origin: top left; box-sizing: border-box;
               display: flex; flex-direction: column; justify-content: center; }
.af-sideways .af-panel { margin: 0 auto; }
.af-sideways .af-phone-note { margin-bottom: 0; }
.af-sideways .af-cap-tip { display: none !important; }
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
    back, or bring them up to date - unless the user gave the deck options of their own."""
    deck = col.decks.get(did)
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
    """The note that carries the forest, made (with its note type and deck) if it is missing."""
    m = _notetype(col)
    nids = col.db.list("select id from notes where mid = ? order by id", m["id"])
    if nids:
        note = col.get_note(nids[0])
        for did in set(col.db.list("select did from cards where nid = ?", note.id)):
            _options(col, did)
        return note
    note = col.new_note(m)
    note["About"], note["Forest"] = ABOUT, ""
    did = col.decks.id(DECK)
    _options(col, did)
    col.add_note(note, did)
    log("made the note that takes the forest to your phone")
    return note


def _script(col) -> str:
    """The drawing, in the collection's media under a name made from what is in it; older
    copies go, so the next sync removes them from the phone too."""
    text = phone_data.bundle().encode("utf-8")
    name = f"{phone_data.SCRIPT_PREFIX}{hashlib.sha1(text).hexdigest()[:10]}.js"
    folder = col.media.dir()
    if not os.path.exists(os.path.join(folder, name)):
        name = col.media.write_data(name, text)
    old = [f for f in os.listdir(folder) if f.startswith(phone_data.SCRIPT_PREFIX) and f.endswith(".js") and f != name]
    if old:
        col.media.trash_files(old)
    return name


def _keep_new(col, note) -> None:
    """Answered, suspended or buried on the phone: new again, so the deck keeps showing it."""
    stale = [cid for cid in col.card_ids_of_note(note.id)
             if (card := col.get_card(cid)).type != 0 or card.queue < 0]
    if stale:
        col.sched.schedule_cards_as_new(stale, restore_position=True, reset_counts=True)


def remove() -> None:
    """Take the forest off the phone: its note, its deck and its script in media. The deck
    only goes if nothing else was put in it. The note type and the deck's options preset stay:
    removing either forces a full sync, and they are empty and out of the way."""
    col = mw.col
    m = col.models.by_name(PHONE_NOTETYPE) if col is not None else None
    if m is None:
        return
    try:
        nids = col.db.list("select id from notes where mid = ?", m["id"])
        dids = set(col.db.list("select distinct did from cards where nid in (select id from notes where mid = ?)", m["id"]))
        if nids:
            col.remove_notes(nids)
        mine = col.decks.id_for_name(DECK)
        for did in dids | ({mine} if mine else set()):
            ids = col.decks.deck_and_child_ids(did)
            if len(ids) > 1 or col.db.scalar("select count() from cards where did = ? or odid = ?", did, did):
                continue  # something else lives here now
            col.decks.remove([did])
        folder = col.media.dir()
        scripts = [f for f in os.listdir(folder) if f.startswith(phone_data.SCRIPT_PREFIX) and f.endswith(".js")]
        if scripts:
            col.media.trash_files(scripts)
        log("took the forest off your phone")
    except Exception:
        log("could not take the forest off your phone:\n" + traceback.format_exc())


# whether the setting was on when last looked at: only turning it off removes the deck, so a
# computer that never had it on leaves alone the one another computer keeps
_was_on: bool | None = None


def follow_setting() -> None:
    """After the settings change: turned on, the note is made (or brought up to date) now
    rather than at the next sync; turned off, the deck goes."""
    global _was_on
    on = enabled()
    if on:
        publish()
    elif _was_on:
        remove()
    _was_on = on


def remember_setting() -> None:
    """Note whether the setting is on, before anything can change it."""
    global _was_on
    _was_on = enabled()


def publish() -> None:
    """Write the forest as it is now into the note, if the setting is on and it changed."""
    col = mw.col
    cfg = config()
    if col is None or not enabled(cfg):
        return
    try:
        note = _note(col)
        script = _script(col)
        real, place, _error = live_weather.for_config(cfg)
        name = getattr(payload, "_scene_name", None)
        data = phone_data.phone_payload(payload.payload(), cfg, _dt.datetime.now(), script, real, place,
                                        (lambda date: name(cfg, date)) if name else (lambda _date: {}))
        if not phone_data.same_forest(note["Forest"], data):
            note["Forest"] = phone_data.encode(data)
            col.update_note(note, skip_undo_entry=True)
        _keep_new(col, note)
    except Exception:
        log("could not update the forest for your phone:\n" + traceback.format_exc())

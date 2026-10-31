"""What the forest does when it is clicked, and the deck list's gear-menu entry: open the
settings, open the browser on a tree's cards, leave a deck out or bring it back."""

from __future__ import annotations

import traceback

from anki.collection import SearchNode
from aqt import dialogs, gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.utils import tooltip

from . import answer_column, bars, events_state, marks, news, payload, study_log
from .i18n import N_, t, tn, tx
from .panel import hold_shortcuts, refresh
from .phone import publish as publish_for_phone
from .phone import switch
from .phone_note import PHONE_NOTETYPE, phone_decks
from .scope import day_cutoff, excluded_decks
from .settings import open_settings as open_dialog
from .state import CALENDAR_SHADES, CALENDAR_VIEWS, MODULE, config, keeps_suspended, log, save_config


def settings_changed() -> None:
    """After any change to the config: the forest on your phone brought up to date, and the
    forest redrawn."""
    publish_for_phone()
    refresh()


def phone_switched(on: bool) -> None:
    """"Show my forest on my phone" ticked or unticked: its deck made or taken away now, and
    redrawn - the whole deck list when that deck has just come or gone, so it shows (or goes)
    at once."""
    if switch(on) and mw.col is not None and mw.state == "deckBrowser":
        mw.deckBrowser.refresh()
    else:
        refresh()


def open_settings(focus: str = "") -> None:
    open_dialog(MODULE, settings_changed, phone_switched, focus)


def browse_day(days_ago: int, did: int | None = None, until_days_ago: int | None = None) -> None:
    """Open the browser on the cards first studied on that day (same rule as the trees), or
    on everything from that day up to `until_days_ago` when the deep forest is clicked."""
    _open_browser(study_log.day_search(days_ago, until_days_ago, keeps_suspended()), did)


def browse_calendar_day(offset: int, did: int | None = None, due: bool = False, answer_mode: str = "") -> None:
    """Open the browser on a study calendar day's cards (web/calendar.js): those reviewed that
    day, `offset` days before today (0: today), or those due that day, `offset` days ahead (or
    today, `due`, before you have studied: the cards its tile counts)."""
    values, label = None, ""
    if answer_mode in ("reviews", "time", "median") and offset <= 0 and not due:
        cutoff = day_cutoff(mw.col)
        values = (study_log.day_answer_times(mw.col.db, cutoff, offset) if answer_mode == "median"
                  else study_log.day_card_totals(mw.col.db, cutoff, offset, answer_mode))
        label = _column_label(answer_mode, study_log.day_date(-offset, cutoff).isoformat())
    _open_browser(study_log.calendar_search(mw.col.db, offset, mw.col.sched.today, due), did, values, label, answer_mode)


def browse_calendar_days(runs: list, did: int | None = None, answer_mode: str = "", due_today: bool = False) -> None:
    """Open the browser on the cards reviewed on the days picked on the heatmap (web/calendar.js:
    Shift-click a stretch, Cmd/Ctrl-click a day), `runs` of them as (first, last) days from today
    (0: today), with their reviews, time or median answer time over those days beside them; days
    ahead open their cards due, as a day ahead clicked does, and so does today with `due_today`
    (picked before you have studied: the cards its tile counts, as today clicked opens them)."""
    picked = sorted((min(a, b), max(a, b)) for a, b in runs)
    ahead = [d for a, b in picked for d in range(max(a, 1), b + 1)]
    runs = []
    for a, b in ((a, min(b, 0)) for a, b in picked if a <= 0):
        if runs and a <= runs[-1][1] + 1:  # (overlapping or touching runs as one: no day counted twice)
            runs[-1] = (runs[-1][0], max(runs[-1][1], b))
        else:
            runs.append((a, b))
    due =[t for d in ahead for t in study_log.calendar_search(mw.col.db, d, mw.col.sched.today)]
    if due_today and any(a <= 0 <= b for a, b in picked):  # (its terms together: due, not suspended, not buried)
        due.insert(0, "(" + " ".join(study_log.calendar_search(mw.col.db, 0, mw.col.sched.today, True)) + ")")
    if not runs:
        if due:
            _open_browser([study_log._any_of(due)], did)
        return
    cutoff = day_cutoff(mw.col)
    mode = answer_mode if answer_mode in ("reviews", "time", "median") else "reviews"
    values = (study_log.days_answer_times(mw.col.db, cutoff, runs) if mode == "median"
              else study_log.days_card_totals(mw.col.db, cutoff, runs, mode))
    if not values:
        if due:
            _open_browser([study_log._any_of(due)], did)
        return
    date = lambda o: study_log.day_date(-o, cutoff).isoformat()  # noqa: E731
    days = sum(b - a + 1 for a, b in runs)
    label = _column_label(mode, date(runs[0][0]), date(runs[-1][1]) if days > 1 else "", days if len(runs) > 1 else 0)
    terms = study_log.calendar_days_search(runs)
    _open_browser([study_log._any_of(terms + due)] if due else terms, did, values, label, mode)


def _column_label(mode: str, first: str, last: str = "", days: int = 0) -> str:
    """The browser column's heading for the days clicked or picked on the heatmap: "Reviews
    (2026-10-12)", "Reviews (2026-10-01 to 2026-10-05)", or for days apart, "Reviews (3 days,
    2026-10-01 to 2026-10-05)"; "Total time" or "Answer time" for the other modes."""
    if mode == "time":
        if days:
            return tn("actions.total_time_days_days_first_to", days,
                      days=days, first=first, last=last)
        return t("actions.total_time_first_to_last", first=first, last=last) if last else t("actions.total_time_date", date=first)
    if mode == "median":
        if days:
            return tn("actions.answer_time_days_days_first_to", days,
                      days=days, first=first, last=last)
        return t("actions.answer_time_first_to_last", first=first, last=last) if last else t("actions.answer_time_date", date=first)
    if days:
        return tn("actions.reviews_days_days_first_to_last", days,
                  days=days, first=first, last=last)
    return t("actions.reviews_first_to_last", first=first, last=last) if last else t("actions.reviews_date", date=first)


def _days_picked(text: str) -> list:
    """The days picked on the heatmap, as the page sends them: "-20_-5,-3_-3"."""
    return [tuple(int(v) for v in part.split("_", 1)) for part in text.split(",") if "_" in part]


def _open_browser(terms: list, did: int | None = None, answer_times: dict | None = None, answer_label: str = "", metric: str = "median") -> None:
    """The browser on `terms`, kept to the cards the forest counts: the deck `did` if given, and
    never a deck left out of the forest or the note that carries it to your phone."""
    terms = list(terms)
    name = mw.col.decks.name_if_exists(did) if did else None
    if name:  # deck names can hold quotes and colons, so let Anki quote it
        terms.insert(0, mw.col.build_search_string(SearchNode(deck=name)))
    # the decks left out of the forest planted none of its trees (a deck: search takes
    # their subdecks with them)
    for out in config().get("excluded_decks") or []:
        try:
            out_name = mw.col.decks.name_if_exists(int(out))
        except (TypeError, ValueError):
            continue
        if out_name:
            terms.append(mw.col.build_search_string(SearchNode(negated=SearchNode(deck=out_name))))
    # nor did the note that carries the forest to your phone, wherever its card is: opened on
    # the phone, it would be one card more than the tooltip says (found by its note type, as
    # phone_note.phone_cards finds it)
    terms.append(mw.col.build_search_string(SearchNode(negated=SearchNode(note=PHONE_NOTETYPE))))
    browser = dialogs.open("Browser", mw)
    if answer_times is None:
        browser.search_for(" ".join(terms))
        return

    # Match cards before aggregating notes: a note can have siblings in other decks.
    matching = set(mw.col.find_cards(" ".join(terms)))
    answer_times = {cid: value for cid, value in answer_times.items() if cid in matching}
    if answer_label:
        answer_column.show(browser, answer_times, answer_label, " ".join(terms), metric)

    # Sort only this opening search; leave later searches alone.
    def sort_answers(context):
        if context.browser is not browser or context.ids is None:
            return
        times = answer_times
        if browser.table.is_notes_mode():
            times = answer_column.note_values(answer_times, metric)
        context.ids = sorted(context.ids, key=lambda item: (-times.get(item, -1), item))

    gui_hooks.browser_did_search.append(sort_answers)
    try:
        browser.search_for(" ".join(terms))
    finally:
        gui_hooks.browser_did_search.remove(sort_answers)


def on_js_message(handled, message, context):
    if not isinstance(context, (DeckBrowser, Overview)) or not isinstance(message, str) or not message.startswith(MODULE + ":"):
        return handled
    cmd = message.split(":")[1:]
    try:
        if cmd[0] == "settings":
            open_settings()
        elif cmd[0] == "news" and len(cmd) > 2:  # a note answered: hidden for good, or followed
            news.mark_seen([cmd[2]])
            if cmd[1] == "open":
                open_settings(news.opens(cmd[2]))
        elif cmd[0] == "struck" and len(cmd) > 1:
            events_state.mark_seen(":".join(cmd[1:]))
        elif cmd[0] == "strike" and len(cmd) > 1:  # a replay asks for the forest it took
            return (True, events_state.strike_before(":".join(cmd[1:])))
        elif cmd[0] == "deep":  # zoomed in among the trees: the deep forest's, one by one
            return (True, payload.deep_trees(cmd[1] if len(cmd) > 1 else ""))
        elif cmd[0] == "mark" and len(cmd) > 2:  # a heatmap day marked as important: mark:day:icon:name
            marks.set_mark(mw.col, cmd[1], cmd[2], ":".join(cmd[3:]))  # (the heatmap has drawn it already: no redraw)
        elif cmd[0] == "unmark" and len(cmd) > 1:
            marks.unmark(mw.col, cmd[1])
        elif cmd[0] == "shade" and len(cmd) > 1 and cmd[1] in CALENDAR_SHADES:  # the toggle beside the key: Reviews, Time, or Pace
            save_config(dict(config(), calendar_shade=cmd[1]))  # (the heatmap has drawn it already: no redraw)
        elif cmd[0] == "view" and len(cmd) > 1 and cmd[1] in CALENDAR_VIEWS:  # Timeline | By year | Streak, on the heatmap
            save_config(dict(config(), calendar=cmd[1]))  # (drawn already; the Heatmap tab's View follows it)
        elif cmd[0] == "bars":  # Layout's Background: Anki's bars tinted from the scene, or not (bars.py)
            bars.tint(cmd[1:])
        elif cmd[0] == "typing":  # a mark's name being typed on the page: Anki's one-key shortcuts wait
            hold_shortcuts(cmd[1:] == ["1"])
        elif cmd[0] == "day" and len(cmd) > 1:  # a study calendar day clicked
            browse_calendar_day(int(cmd[1]), int(cmd[2]) if len(cmd) > 2 and cmd[2] else None, len(cmd) > 3 and cmd[3] == "due",
                                cmd[3] if len(cmd) > 3 else "")
        elif cmd[0] == "days" and len(cmd) > 1:  # days picked on the heatmap, clicked
            browse_calendar_days(_days_picked(cmd[1]), int(cmd[2]) if len(cmd) > 2 and cmd[2] else None,
                                 cmd[3] if len(cmd) > 3 else "", len(cmd) > 4 and cmd[4] == "due")
        elif cmd[0] == "browse":
            browse_day(int(cmd[1]),
                       int(cmd[2]) if len(cmd) > 2 and cmd[2] else None,
                       int(cmd[3]) if len(cmd) > 3 and cmd[3] else None)
    except Exception:
        log(f"could not handle {message}:\n" + traceback.format_exc())
    return (True, None)


LEFT_OUT = N_("actions.left_out_of_your_forest_its")
BROUGHT_BACK = N_("actions.back_in_your_forest")


def on_deck_options_menu(menu, did: int) -> None:
    """Leave a deck out of the forest, or bring it back, from its gear menu in the deck list."""
    try:
        deck = mw.col.decks.get(did, default=False)
        if not deck or deck.get("dyn") or did in phone_decks():  # the phone's deck is the forest itself
            return
        cfg = config()
        mine = [int(d) for d in cfg.get("excluded_decks") or [] if str(d).lstrip("-").isdigit()]
        if did in mine:
            action = menu.addAction(t("actions.bring_back_into_memory_forest"))
            action.triggered.connect(lambda: _set_excluded([d for d in mine if d != did], BROUGHT_BACK))
        elif did in excluded_decks(cfg):
            action = menu.addAction(t("actions.left_out_of_memory_forest_with"))
            action.setEnabled(False)
        else:
            action = menu.addAction(t("actions.leave_out_of_memory_forest"))
            action.triggered.connect(lambda: _set_excluded(mine + [did], LEFT_OUT))
    except Exception:
        log("could not add to the deck menu:\n" + traceback.format_exc())


def _set_excluded(dids: list, message: str) -> None:
    cfg = config()
    cfg["excluded_decks"] = sorted(set(dids))
    save_config(cfg)
    refresh()
    tooltip(tx(message))

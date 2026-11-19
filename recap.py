"""Your year in the forest: a look back at a year of study, offered from Dec 7 (the year
so far) through Jan 15 (web/recap.js draws it, over the deck list).

The numbers are the heatmap's own: its days and their reviews (the forest's, read with it), its
streak rules (a day with nothing due, and a 5 or 6 days a week streak's days off, never break one),
and its day rollover. The animals of the year are those whose milestone the history shows was
earned that year (milestones.animal_days, from the review history alone: never the day the forest
saw one come, which for a forest updated to new milestones is the update's, not the study's). Only
animals: no building or plant (NOT_ANIMALS).

What was answered is kept per profile in user_files/state.json ("recap": {year: "opened" or
"dismissed"}). The Debug tab's date shows it on any day of its window."""

from __future__ import annotations

import datetime as _dt

from . import milestones
from .state import load_state, save_state

# the year's recap is offered from Dec 7 (as the other apps' look backs come out: the year so far)
# through Jan 15; answered in December, its card comes back once in January, for the whole year
WINDOW_FROM, WINDOW_TO = 7, 15
# fewer days studied than this: the short version, the title and the summary card alone, with no
# claims of a streak or a best month
SHORT_UNDER = 7
# what the milestones bring that isn't an animal (a building, a plant): never among the year's animals.
# (The stork is a bird, nesting on the cabin: it counts.)
NOT_ANIMALS = frozenset({"cabin", "birdhouse", "mushrooms"})
OPENED, DISMISSED = "opened", "dismissed"
# a deck smaller than this, its last new card learned, isn't one to look back on
FINISHED_LEAST_CARDS = 20


def finished(rows: list, names: dict, year: int, date_of_ms, excluded=frozenset()) -> list:
    """The decks whose every card was learned in `year`: those with no new card left whose last new
    card was first studied that year (study_log.load_deck_firsts' `rows`, `names` {deck id: name},
    `date_of_ms` a revlog id's date). A deck counts with its subdecks; one whose parent is finished
    too is said once, as the parent, and a parent only when all of its subdecks (and its own cards) were
    learned to the end that year. One with a subdeck left out of the forest (`excluded`, whose cards
    `rows` hasn't) is never said as a whole. Oldest first: [{"name", "full", "date", "cards"}]."""
    # (each deck's cards added up into it and every deck over it, in one pass: deck by deck against every
    # other name, a collection of 3,000 subdecks took 2 s)
    whole: dict = {}  # name -> [cards, new cards left, the newest first answer, a subdeck left out]
    for did, name in names.items():
        parts = name.split("::")
        for k in range(1, len(parts) + 1):
            w = whole.setdefault("::".join(parts[:k]), [0, 0, None, False])
            if did in excluded:
                w[3] = True
    own = {did: (n, left, last) for did, n, left, last in rows}
    for did, (n, left, last) in own.items():
        name = names.get(did)
        if name is None:
            continue
        parts = name.split("::")
        for k in range(1, len(parts) + 1):
            w = whole["::".join(parts[:k])]
            w[0] += n
            w[1] += left or 0
            if last and (w[2] is None or last > w[2]):
                w[2] = last
    done = {n: date_of_ms(w[2]) for n, w in whole.items() if w[0] and not w[1] and w[2]}
    ids = {name: did for did, name in names.items()}

    kids: dict = {}  # name -> its subdecks one level down, those with cards
    for n, w in whole.items():
        if "::" in n and w[0]:
            kids.setdefault(n.rsplit("::", 1)[0], []).append(n)

    def said_whole(name):
        # (Languages, its German learned this year and its Spanish two years ago, is German's: a part
        # learned before the year has no first answer in it, read from the year on, study_log.load_deck_firsts)
        mine = own.get(ids[name])
        parts = kids.get(name, [])
        return (all(d in done and done[d].year == year for d in parts)
                and not (parts and mine and mine[0] and not (mine[2] and date_of_ms(mine[2]).year == year)))
    out = [(n, done[n], whole[n][0]) for n in names.values()
           if n in done and done[n].year == year and whole[n][0] >= FINISHED_LEAST_CARDS and not whole[n][3] and said_whole(n)]
    said = {n for n, _, _ in out}
    kept = [x for x in out if not any("::".join(x[0].split("::")[:k]) in said for k in range(1, x[0].count("::") + 1))]

    # (each by its own name, but where two would read the same, "A1, A1": by as much of its path as tells them apart)
    tails = {}  # (each end of a name said, one part, two, ...: how many said end so)
    for x in kept:
        parts = x[0].split("::")
        for k in range(1, len(parts) + 1):
            tails["::".join(parts[-k:])] = tails.get("::".join(parts[-k:]), 0) + 1

    def short(n):
        parts = n.split("::")
        return next(("::".join(parts[-k:]) for k in range(1, len(parts) + 1) if tails["::".join(parts[-k:])] == 1), n)
    # (with its cards: the line names the biggest, web/recap.js)
    return [{"name": short(n), "full": n, "date": d.isoformat(), "cards": c} for n, d, c in sorted(kept, key=lambda x: (x[1], x[0]))]


def year_for(day: _dt.date) -> int | None:
    """The year whose recap is offered on `day`: Y from Dec 7 of Y through Jan 15 of Y+1, else None.
    In December it is the year so far."""
    if day.month == 12 and day.day >= WINDOW_FROM:
        return day.year
    if day.month == 1 and day.day <= WINDOW_TO:
        return day.year - 1
    return None


def runs(studied: set, skip: set, first: _dt.date, last: _dt.date) -> list:
    """The streaks between `first` and `last` (dates), as the heatmap counts them: (days studied,
    first day, last day). A day in `skip` (nothing due, or a day off) neither breaks a streak nor
    adds to it; any other day not studied ends it."""
    out, cur = [], None
    d = first
    while d <= last:
        if d in studied:
            cur = [cur[0] + 1, cur[1], d] if cur else [1, d, d]
        elif d not in skip and cur:
            out.append(tuple(cur))
            cur = None
        d += _dt.timedelta(days=1)
    if cur:
        out.append(tuple(cur))
    return out


def _gaps(days: list) -> list:
    """(last day before, first day back, days away) between days studied, oldest first."""
    return [(a, b, (b - a).days - 1) for a, b in zip(days, days[1:]) if (b - a).days > 1]


def label(year: int, studied: list, last: _dt.date, first_ever: _dt.date | None, streak: tuple | None, skip: set = frozenset(),
          off: set = frozenset()) -> dict:
    """A warm word for the year's rhythm, never its size: the first rule that fits, every one of
    them true of a light year as of a heavy one.

    comeback  away two weeks or more this year, then nine days in ten studied from the day you
              came back, with a streak of 30 days or more still going on the year's last day
    new       your first review ever was this year, under 90 days before its end
    steady    four days in five studied, from the year's first day studied to its end (a month of
              study that then stopped is no steady year: its month is its season; `off`, a 5 or 6
              days a week streak's days off, not counted: a weekday streak kept all year is steady)
    weekly    three days of the week hold nearly all of them (85 in 100, twelve days at least): a
              weekend's study, or a Monday and Thursday's
    season    one month holds a third or more of the year's days studied (seven days at least)
    patient   three days studied or more
    quiet     the rest: a day or two"""
    if not studied:
        return {"key": "quiet"}
    away = [g for g in _gaps(studied) if g[2] - sum(1 for k in range(1, g[2] + 1) if g[0] + _dt.timedelta(days=k) in skip) >= 14]
    if away and streak and streak[0] >= 30 and streak[2] >= last - _dt.timedelta(days=1):
        back = away[-1][1]
        span = (last - back).days + 1
        if sum(1 for d in studied if d >= back) >= 0.9 * span:
            return {"key": "comeback", "month": back.month - 1}
    if first_ever and first_ever.year == year and (last - first_ever).days < 90:
        return {"key": "new", "date": first_ever.isoformat(), "days": len(studied)}
    seen = set(studied)
    span = (last - studied[0]).days + 1 - sum(1 for d in off if studied[0] <= d <= last and d not in seen)
    if len(studied) >= 7 and len(studied) >= 0.8 * span:
        return {"key": "steady"}
    by_weekday = [0] * 7
    for d in studied:
        by_weekday[d.weekday()] += 1
    if len(studied) >= 12 and sum(sorted(by_weekday)[-3:]) >= 0.85 * len(studied):
        return {"key": "weekly"}
    by_month = [0] * 12
    for d in studied:
        by_month[d.month - 1] += 1
    top = max(range(12), key=lambda m: by_month[m])
    if by_month[top] >= 7 and by_month[top] >= len(studied) / 3:
        return {"key": "season", "month": top, "days": by_month[top]}
    return {"key": "patient"} if len(studied) >= 3 else {"key": "quiet"}


def numbers(year: int, reviews: dict, seconds: dict, trees: list, skip: set, last: _dt.date, animals: list | None = None,
            off: set = frozenset()) -> dict:
    """The year in numbers, from its days (dates) up to `last`: `reviews` {date: reviews}, `seconds`
    {date: seconds they took}, the forest's `trees` (each its "date" and "n" cards), `skip` (dates a
    streak passes over) and `animals` [(key, date earned)]."""
    start, end = _dt.date(year, 1, 1), min(_dt.date(year, 12, 31), last)
    days = {d: n for d, n in reviews.items() if start <= d <= end and n}
    studied = sorted(days)
    grown = [t for t in trees if start.isoformat() <= str(t.get("date", "")) <= end.isoformat()]
    months, month_days = [0] * 12, [0] * 12
    for d, n in days.items():
        months[d.month - 1] += n
        month_days[d.month - 1] += 1
    best_day = min(studied, key=lambda d: (-days[d], d)) if studied else None
    best_month = min(range(12), key=lambda m: (-months[m], m)) if studied else None
    streaks = runs(set(studied), set(skip), start, end) if studied else []
    best = min(streaks, key=lambda r: (-r[0], r[1])) if streaks else None
    first_ever = min((d for d, n in reviews.items() if n), default=None)
    return {
        "year": year, "last": end.isoformat(), "first": studied[0].isoformat() if studied else None,
        "studied": len(studied), "reviews": sum(days.values()),
        "seconds": sum(s for d, s in seconds.items() if start <= d <= end),
        "newCards": sum(int(t.get("n") or 0) for t in grown), "trees": len(grown),
        "bestDay": [best_day.isoformat(), days[best_day]] if best_day else None,
        "bestMonth": [best_month, months[best_month], month_days[best_month]] if best_month is not None else None,
        "bestStreak": [best[0], best[1].isoformat(), best[2].isoformat()] if best else None,
        "months": months,
        "short": len(studied) < SHORT_UNDER,
        # (the comeback goes by the streak still going at the year's end, not the best: a long spring
        # streak, then a summer away and an autumn back every day, is a comeback)
        "label": label(year, studied, end, first_ever, streaks[-1] if streaks else None, set(skip), set(off)),
        "animals": [{"key": k, "date": d.isoformat()} for k, d in sorted(animals or [], key=lambda a: (a[1], a[0]))
                    if start <= d <= end and k not in NOT_ANIMALS],
    }


def earned(visitors: list, trees: list, day_reviews: dict, today_number: int, cutoff_date) -> list:
    """[(key, date)] for the animals the forest has whose milestone the history dates (the day a
    streak reached its length, the 50th tree, the 10,000th review, the first pond): what
    milestones.animal_days works out with no recorded day to fall back on. `cutoff_date(ago)`
    gives an Anki day's date."""
    bare = [{"key": v["key"]} for v in visitors]
    return [(a["key"], cutoff_date(a["ago"])) for a in milestones.animal_days(bare, trees, day_reviews, today_number)]


# ---------- what was answered (per profile, user_files/state.json) ----------

def answered(year: int) -> str:
    rec = load_state().get("recap")
    return rec.get(str(year), "") if isinstance(rec, dict) else ""


EARLY = ":early"  # (answered in December, on the year so far: its card comes back in January)


def answer(year: int, how: str, early: bool = False) -> None:
    """The year's card answered: opened (the recap seen) or dismissed ("Not now"), in December
    (`early`, the year so far) or once it was over."""
    s = load_state()
    rec = s.get("recap") if isinstance(s.get("recap"), dict) else {}
    was = rec.get(str(year))
    # (opened stays opened: once the year is over for good, in December till January)
    if was != OPENED and not (early and was == OPENED + EARLY):
        rec[str(year)] = how + (EARLY if early else "")
    s["recap"] = rec
    save_state(s)


def entry(year: int, offered: int | None, early: bool) -> str:
    """How the deck list offers the year's recap: "card" (in the forest's corner) until it is answered,
    then "link" (in the caption), or "none" outside its window. Answered in December, on the year so
    far, its card comes back once in January, for the whole year."""
    if offered != year:
        return "none"
    was = answered(year)
    return "card" if not was or (was.endswith(EARLY) and not early) else "link"


def forget(year: int | None = None) -> None:
    """The Debug tab's replay: the card shows again (for one year, or all)."""
    s = load_state()
    rec = s.get("recap") if isinstance(s.get("recap"), dict) else {}
    if year is None:
        rec = {}
    else:
        rec.pop(str(year), None)
    s["recap"] = rec
    save_state(s)


# ---------- for the page (payload.py) ----------

def for_page(forest: dict, day: _dt.date, today: _dt.date, today_number: int, date_of, free: set, off: set,
             week_start: int, look, planted: list | None = None, record: tuple | None = None, decks=None) -> dict | None:
    """What the deck list's page needs for the recap, or None when there is none to offer: outside
    its window, or for a year with no day studied.
    `forest` as payload.py has it (its days and their time as days ago, its trees and animals),
    `day` the date the scenery is chosen for (the Debug tab may move it), `today` Anki's, with its
    scheduler `today_number`, `date_of(ago)` an Anki day's date, `free` and `off` the days (ago) a
    streak passes over, and `look(cal)` the calendar with the Heatmap tab's look added. `planted`: the
    trees as the study grew them, before an asteroid took any (the year's trees and new cards count them).
    `record`: the heatmap's ({ago: reviews}, {ago: seconds}) where they are not the forest's (a start date,
    the reviews from before it shown): the year's days go by them; its animals by the forest's own."""
    year = offered = year_for(day)
    if year is None:
        return None
    day_reviews = forest.get("day_reviews") or {}
    shown, times = record if record is not None else (day_reviews, forest.get("day_time") or {})
    reviews = {date_of(a): n for a, n in shown.items() if n}
    if not any(d.year == year for d in reviews):
        return None  # (a fresh install with nothing studied that year: nothing to look back on)
    seconds = {date_of(a): s for a, s in times.items()}
    skip = {date_of(a) for a in set(free) | set(off)}
    animals = earned(forest.get("visitors") or [], forest["trees"], day_reviews, today_number, date_of)
    out = numbers(year, reviews, seconds, planted if planted is not None else forest["trees"], skip, today, animals,
                  {date_of(a) for a in off})
    names = {a["key"]: a for a in milestones.for_page([{"key": a["key"]} for a in out["animals"]])}
    out["animals"] = [dict(a, name=names[a["key"]].get("name", a["key"]), came=names[a["key"]].get("came", "")) for a in out["animals"]]
    # the heatmap of the year, By year, as the deck list's draws it: its days to the year's end (or today)
    last = _dt.date.fromisoformat(out["last"])
    start = _dt.date(year, 1, 1)
    shift, span = (today - last).days, (last - start).days  # (its today is the year's last day: offsets from there)
    out["calendar"] = look({
        "view": "by_year", "shadeBy": "reviews", "weekStart": week_start, "start": start.isoformat(),
        "days": [reviews.get(start + _dt.timedelta(days=i), 0) for i in range(span + 1)],
        "due": [], "planted": [], "animals": [], "ponds": [], "marks": [], "gone": [], "browse": False,
        # (the days a streak passes over, as the heatmap's: [older, newer] days before its today)
        "free": [[a - shift, a - shift] for a in sorted(free) if 0 <= a - shift <= span],
        "daysOff": sorted(a - shift for a in off if 0 <= a - shift <= span)})
    # the decks learned to their last card that year (`decks(year)`, payload.py: only asked for here)
    out["finished"] = decks(year) if decks else []
    out["early"] = year == day.year  # (in December, the year so far)
    out["entry"] = entry(year, offered, out["early"])
    return out

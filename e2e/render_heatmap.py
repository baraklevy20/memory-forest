"""The study heatmap's scenes for e2e/render_check.py: a made-up study history, each view and
state of it, and the probes run once it has drawn (the room it takes against the room kept for
it, and a day, a shade in the key and a trophy answering the pointer)."""

from __future__ import annotations

import datetime as dt

SCENE_TREES = 200  # (as render_check's: the forest drawn above the heatmap)

HEATMAP_TODAY = dt.date(2026, 9, 19)


def heatmap_calendar(view: str, years) -> dict:
    """A study history from 2018: patchy years, a long streak from Jun 2024 to today, a mark,
    the cards due ahead. Fixed, so a scene draws the same every run."""
    start = dt.date(2018, 3, 1)
    n = (HEATMAP_TODAY - start).days + 1
    days, time_ = [], []
    for i in range(n):
        d = start + dt.timedelta(days=i)
        on = d >= dt.date(2024, 6, 1) or (i * 7) % 10 < 6
        reviews = 20 + (i * 37) % 180 if on else 0
        days.append(reviews)
        time_.append(reviews * (5 + i % 6) if reviews else 0)
    return {"view": view, "shadeBy": "reviews", "_open": years, "weekStart": 1, "start": start.isoformat(),
            "days": days, "time": time_, "due": [40] + [30 + i % 25 for i in range(1, 200)], "animals": [],
            "breakDays": 7, "forestStart": None, "hiddenBefore": None, "streakFromStart": False,
            "marks": [{"day": "2026-03-04", "icon": "sick", "name": ""}], "gone": [], "browse": False}


def heatmap_scenes() -> list:
    """Timeline and By year (its earlier years hidden, shown, all), dark; the two views light."""
    out = []
    for view, years in (("timeline", False), ("by_year", False), ("by_year", True), ("by_year", "all")):
        tag = view if view == "timeline" else f"by_year-{ {False: 'closed', True: 'open', 'all': 'all'}[years] }"
        out.append((f"heatmap-{tag}", {"heatmap": heatmap_calendar(view, years), "page": "dark"}, SCENE_TREES))
    for view in ("timeline", "by_year"):
        out.append((f"heatmap-{view}-light", {"heatmap": heatmap_calendar(view, False), "page": "light"}, SCENE_TREES))
    # a journal long enough to wrap in the footer: the room kept for the calendar must hold both lines
    long = dict(heatmap_calendar("timeline", False), _journal="One of your trees became ancient today. Watch for a shooting star tonight, over the lake.")
    out.append(("heatmap-timeline-long-journal", {"heatmap": long, "page": "dark"}, SCENE_TREES))
    return out


# once the heatmap has drawn: the room kept for it against the room it takes, and the pointer on a
# day, a shade in the key and the trophies' lane, each of which must show its tooltip; errors if not
HEATMAP_PROBES = """
async function probes(r) {
  const sleep = ms => new Promise(f => setTimeout(f, ms));
  const box = document.querySelector('.af-cal'), tip = document.querySelector('.af-cal-tip');
  const say = () => (tip && !tip.hidden ? tip.textContent : '');
  // (to whatever is on top at that point, as a real pointer: a layer over the weeks must not swallow
  // it; each part scrolled into the window first, as nothing is "at" a point outside it)
  let lost = 0;
  const move = (_el, x, y, type) => {
    const at = document.elementFromPoint(x, y);
    if (!at) { lost++; return; }
    at.dispatchEvent(new MouseEvent(type || 'mousemove', { bubbles: true, clientX: x, clientY: y }));
  };
  const into = el => { el.scrollIntoView({ block: 'center' }); return el.getBoundingClientRect(); };
  const kept = AnkiForest.calendarHeight(window.D.calendar, box.clientWidth, box.parentNode);
  const took = box.getBoundingClientRect().height;
  if (Math.abs(kept - took) > 1) r.errors.push(`heatmap: ${Math.round(took)}px drawn in ${kept}px kept (the panel jumps)`);
  // By year's earlier years, shown by their switch (never at first); then Timeline and back, which
  // must come back to the year in view alone, and shown again for the probes below
  const open = window.D.calendar._open, click = sel => { const b = document.querySelector(sel); if (b) b.click(); return !!b; };
  if (open) {
    if (!click('.af-cal-more-near')) r.errors.push('heatmap: no switch for the earlier years');
    if (open === 'all' && !click('.af-cal-more-all')) r.errors.push('heatmap: no "Show all years"');
    if (!document.querySelector('.af-cal-past-year')) r.errors.push('heatmap: the earlier years did not show');
    click('[data-view="timeline"]'); click('[data-view="by_year"]');
    if (document.querySelector('.af-cal-past-year')) r.errors.push('heatmap: back from Timeline, By year kept its earlier years');
    click('.af-cal-more-near'); if (open === 'all') click('.af-cal-more-all');
  }
  const cv = document.querySelector('.af-cal-grid > canvas.af-cal-canvas'), c = into(cv);
  // a day: the first spot along the middle row whose tooltip names a day
  let day = '';
  for (let x = c.left + 4; x < c.right && !day; x += 6) { move(cv, x, c.top + c.height * 0.45); await sleep(220); if (/day, /.test(say())) day = say(); }
  if (!day) r.errors.push('heatmap: no day showed its tooltip');
  move(document.body, 1, 1, 'mouseleave');
  // a shade in the key, as the pointer comes onto it and moves on it
  const sw = document.querySelectorAll('.af-cal-key canvas')[2];
  if (sw) {
    const s = into(sw);
    move(sw, s.left + 2, s.top + 2, 'mouseover'); move(sw, s.left + 3, s.top + 3); await sleep(220);
    if (!/reviews|min/.test(say())) r.errors.push('heatmap: a shade in the key showed no tooltip');
  } else r.errors.push('heatmap: no key');
  // the trophies' lane under the weeks, along its middle where the pointer lands on a trophy: a
  // trophy or the goal flag answers (a layer laid over the lane once swallowed it)
  const n = document.querySelector('.af-cal-notes'), lc = into(cv), nr = n.getBoundingClientRect(), mid = (nr.top + nr.bottom) / 2;
  let lane = '';
  for (let x = lc.left; x < lc.right && !lane; x += 2) { move(cv, x, mid); await sleep(5); if (/longest|on this day/.test(say())) lane = say(); }
  if (!lane) r.errors.push('heatmap: neither a trophy nor the goal showed its tooltip');
  if (lost) r.errors.push(`heatmap: ${lost} pointer moves found nothing under them (the probe, not the heatmap)`);
  r.tips = { day, lane };
  // the picture: every heatmap canvas, and where its rows sit
  const foot = document.querySelector('.af-cal-foot');
  r.layout = { kept, took: Math.round(took), foot: foot ? Math.round(foot.getBoundingClientRect().top - box.getBoundingClientRect().top) : null };
  r.heatmap = [...document.querySelectorAll('.af-cal-canvas')].map(k => k.toDataURL()).join('|') + JSON.stringify(r.layout);
}
"""

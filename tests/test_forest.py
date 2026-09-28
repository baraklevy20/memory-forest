"""Tests for the pure-Python parts of Memory Forest (no Anki needed).

Run from the repo root:
    python -m unittest discover anki_forest/tests
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import forest_data as fd
import presets
import scene
import store
import weather

DAY = fd.DAY_SECS
CUTOFF = int(dt.datetime(2026, 9, 20, 4, 0).timestamp())  # next rollover; "today" is 19 Sep
TODAY = 2000


def ms(days_ago: int, hour: int = 12) -> int:
    """Revlog-style ms timestamp at `hour` o'clock on the Anki day `days_ago` days back."""
    return int((CUTOFF - (days_ago + 1) * DAY + (hour - 4) * 3600) * 1000)


def card(cid, ctype=2, ivl=30, s=None):
    data = json.dumps({"s": s}) if s is not None else "{}"
    return (cid, ctype, 2, ivl, data)


def rows(cards, first_last=None, lapses=(), review_days=(0,), total=100, today=10):
    return fd.Rows(list(cards), first_last or {}, set(lapses), set(review_days), total, today)


class CohortTests(unittest.TestCase):
    def test_cards_grouped_by_first_review_day_not_creation(self):
        # three cards created in one bulk import, but studied on different days
        created = ms(100)
        cards = [card(created + i, s=40) for i in range(3)]
        fl = {created: (ms(10), ms(1)), created + 1: (ms(10, 20), ms(1)), created + 2: (ms(5), ms(1))}
        f = fd.build_forest(rows(cards, fl), CUTOFF, TODAY)
        self.assertEqual([(t["ago"], t["n"]) for t in f["trees"]], [(10, 2), (5, 1)])

    def test_rollover_hour_keeps_late_night_study_on_the_same_day(self):
        cards = [card(1, s=30), card(2, s=30)]
        fl = {1: (ms(3, 23), ms(1)), 2: (ms(3, 27), ms(1))}  # 23:00 and 03:00 the next morning
        f = fd.build_forest(rows(cards, fl), CUTOFF, TODAY)
        self.assertEqual([t["ago"] for t in f["trees"]], [3])

    def test_card_without_revlog_falls_back_to_creation_day(self):
        f = fd.build_forest(rows([card(ms(7), s=30)]), CUTOFF, TODAY)
        self.assertEqual(f["trees"][0]["ago"], 7)

    def test_stages_from_fsrs_stability_and_ivl_fallback(self):
        cards = [card(1, s=400), card(2, s=200), card(3, s=30), card(4, s=5), card(5, ivl=45)]
        fl = {i: (ms(20 + i), ms(1)) for i in range(1, 6)}
        stages = {t["ago"]: t["stage"] for t in fd.build_forest(rows(cards, fl), CUTOFF, TODAY)["trees"]}
        self.assertEqual(stages, {21: 5, 22: 4, 23: 3, 24: 2, 25: 3})

    def test_today_is_a_seedling_and_learning_cohort_is_a_sapling(self):
        cards = [card(1, ctype=1, s=1), card(2, ctype=1), card(3, ctype=1), card(4, s=2)]
        fl = {1: (ms(0), ms(0)), 2: (ms(2), ms(0)), 3: (ms(2), ms(0)), 4: (ms(2), ms(0))}
        stages = {t["ago"]: t["stage"] for t in fd.build_forest(rows(cards, fl), CUTOFF, TODAY)["trees"]}
        self.assertEqual(stages, {0: 0, 2: 1})

    def test_health_only_for_matured_trees(self):
        mature = [card(i, s=60) for i in range(1, 11)]
        young = [card(i, s=5) for i in range(11, 21)]
        fl = {i: (ms(40 if i <= 10 else 12), ms(2)) for i in range(1, 21)}
        lapses = {1, 2, 3, 11, 12, 13}  # 30% of each cohort
        trees = {t["ago"]: t for t in fd.build_forest(rows(mature + young, fl, lapses), CUTOFF, TODAY)["trees"]}
        self.assertEqual(trees[40]["health"], 2)
        self.assertEqual(trees[12]["health"], 0)

    def test_fake_forest_sizes(self):
        for n in (0, 3, 150, 1000):
            f = fd.fake_forest(n)
            self.assertEqual(len(f["trees"]), n)
            self.assertEqual(f["stats"]["trees"], n)
        self.assertGreaterEqual(fd.fake_forest(200)["stats"]["ponds"], 1)

    def test_small_forests_are_never_merged(self):
        for n in (0, 150, fd.MAX_INDIVIDUAL_TREES):
            f = fd.merge_old(fd.fake_forest(n))
            self.assertNotIn("merged", f)
            self.assertEqual(len(f["trees"]), n)

    def test_merge_keeps_the_newest_trees_and_sums_the_rest(self):
        full = fd.fake_forest(1000)
        f = fd.merge_old(full)
        m = f["merged"]
        self.assertEqual(len(f["trees"]), fd.MAX_INDIVIDUAL_TREES)
        self.assertEqual(m["count"] + len(f["trees"]), 1000)
        self.assertEqual(m["count"] + sum(1 for _ in f["trees"]), full["stats"]["trees"])
        self.assertEqual(m["cards"] + sum(t["n"] for t in f["trees"]), full["stats"]["cards"])
        # the kept trees are the newest ones, and the summary covers everything older
        self.assertEqual(f["trees"][-1]["ago"], full["trees"][-1]["ago"])
        self.assertEqual(m["from_ago"], full["trees"][0]["ago"])
        self.assertGreater(m["from_ago"], m["to_ago"])
        self.assertGreater(m["to_ago"], f["trees"][0]["ago"])
        self.assertEqual(f["stats"], full["stats"])  # the numbers under the forest still count them all

    def test_positions_seeded_by_absolute_day(self):
        cards = [card(1, s=30)]
        a = fd.build_forest(rows(cards, {1: (ms(5), ms(1))}), CUTOFF, TODAY)["trees"][0]
        b = fd.build_forest(rows(cards, {1: (ms(5), ms(1))}), CUTOFF + DAY, TODAY + 1)["trees"][0]
        self.assertEqual((a["seed"], b["ago"]), (b["seed"], a["ago"] + 1))


class DeckFilterTests(unittest.TestCase):
    def test_deck_forest_only_counts_that_decks_cards_and_reviews(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text);
            create table revlog (id integer, cid integer, ease integer, type integer);
        """)
        # cid, current deck, home deck (odid != 0 means a filtered deck borrowed it), day
        for cid, did, odid, days in ((1, 10, 0, 5), (2, 10, 0, 5), (3, 20, 0, 3), (4, 99, 10, 5)):
            con.execute("insert into cards values (?, ?, ?, ?, 2, 2, 30, '{}')", (cid, cid, did, odid))
            con.execute("insert into revlog values (?, ?, 3, 0)", (ms(days), cid))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]

        whole = fd.build_forest(fd.load_rows(DB(), CUTOFF), CUTOFF, TODAY)
        deck = fd.build_forest(fd.load_rows(DB(), CUTOFF, [10]), CUTOFF, TODAY)
        self.assertEqual([t["n"] for t in whole["trees"]], [3, 1])
        # the card a filtered deck borrowed still belongs to its home deck's forest
        self.assertEqual([(t["ago"], t["n"]) for t in deck["trees"]], [(5, 3)])
        self.assertEqual(deck["stats"]["reviews"], 3)
        self.assertEqual(fd.load_deck_days(DB(), CUTOFF, [10]), {5})


class SuspendedTests(unittest.TestCase):
    """Suspended cards keep their trees, frozen as they were: size and stage, but no
    struggling and no recall."""

    @staticmethod
    def suspended(cid, ctype=2, s=60):
        return (cid, ctype, -1, 30, json.dumps({"s": s}))

    def test_a_tree_of_suspended_cards_stands_as_it_was(self):
        # suspended while relearning: it would otherwise yellow the tree for good
        cards = [self.suspended(1, ctype=3), self.suspended(2), self.suspended(3)]
        fl = {i: (ms(40), ms(30)) for i in (1, 2, 3)}
        tree = fd.build_forest(rows(cards, fl, lapses={2}), CUTOFF, TODAY)["trees"][0]
        self.assertEqual((tree["n"], tree["stage"], tree["health"], tree["struggling"]), (3, fd.MATURE, 0, 0))
        self.assertEqual(tree["suspended"], 3)
        self.assertFalse(tree["measured"])

    def test_health_and_recall_only_weigh_the_cards_still_studied(self):
        active = [card(i, s=60) for i in range(1, 5)]
        cards = active + [self.suspended(i) for i in range(5, 21)]
        fl = {i: (ms(40), ms(2)) for i in range(1, 21)}
        tree = fd.build_forest(rows(cards, fl, lapses={1, 2}), CUTOFF, TODAY)["trees"][0]
        # 2 of the 4 studied cards lapsed: half, not a tenth of all 20
        self.assertEqual((tree["n"], tree["suspended"], tree["health"]), (20, 16, 3))
        self.assertTrue(tree["measured"])

    def test_the_loader_only_brings_them_when_asked(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        for cid, queue in ((1, 2), (2, -1)):
            con.execute("insert into cards values (?, ?, 10, 0, 2, ?, 30, '{}', 0)", (cid, cid, queue))
            con.execute("insert into revlog values (?, ?, 3, 0)", (ms(5), cid))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        self.assertEqual([c[0] for c in fd.load_rows(DB(), CUTOFF).cards], [1])
        self.assertEqual(sorted(c[0] for c in fd.load_rows(DB(), CUTOFF, suspended=True).cards), [1, 2])
        con.execute("update cards set queue = -1")
        self.assertEqual(fd.load_deck_days(DB(), CUTOFF, [10]), set())
        self.assertEqual(fd.load_deck_days(DB(), CUTOFF, [10], suspended=True), {5})


class HistoryFilterTests(unittest.TestCase):
    """The History tab: decks left out of the forest, and a day it starts from."""

    def setUp(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript("""
            create table cards (id integer, nid integer, did integer, odid integer, type integer, queue integer, ivl integer, data text, due integer);
            create table revlog (id integer, cid integer, ease integer, type integer);
            create table notes (id integer, tags text);
        """)
        # cid, current deck, home deck, the days it was reviewed on (first one first)
        for cid, did, odid, days in ((1, 10, 0, (9, 2)), (2, 20, 0, (5,)), (3, 99, 20, (5,)), (4, 10, 0, (3, 1))):
            con.execute("insert into cards values (?, ?, ?, ?, 2, 2, 30, '{}', 0)", (cid, cid, did, odid))
            con.execute("insert into notes values (?, '')", (cid,))
            for d in days:
                con.execute("insert into revlog values (?, ?, 3, 0)", (ms(d), cid))
        # a deleted card's review: no card left to say which deck it was in
        con.execute("insert into revlog values (?, 7, 3, 0)", (ms(4),))

        class DB:
            def all(self, q, *a): return con.execute(q, a).fetchall()
            def scalar(self, q, *a): return con.execute(q, a).fetchone()[0]
        self.db = DB()

    def test_a_left_out_deck_plants_nothing_and_its_reviews_dont_count(self):
        rows = fd.load_rows(self.db, CUTOFF, excluded=[20])
        # card 3 sits in a filtered deck, but its home is deck 20, so it goes too
        self.assertEqual(sorted(c[0] for c in rows.cards), [1, 4])
        self.assertNotIn(5, rows.review_days)
        # the deleted card's review stays: 4 reviews of decks 10, and that one
        self.assertEqual(rows.total_reviews, 5)
        self.assertIn(4, rows.review_days)

    def test_nothing_before_the_start_date_counts(self):
        rows = fd.load_rows(self.db, CUTOFF, since=ms(4, hour=4) // 1000)
        # card 1 was first studied 9 days ago, so its tree would stand before the forest
        self.assertEqual(sorted(c[0] for c in rows.cards), [4])
        # ... but a review of it since then still counts as a day of study
        self.assertEqual(rows.review_days, {1, 2, 3, 4})
        self.assertEqual(rows.total_reviews, 4)
        # the cards that remain are dated by their whole history, not from the start date
        tree = fd.build_forest(rows, CUTOFF, TODAY)["trees"]
        self.assertEqual([t["ago"] for t in tree], [3])

    def test_the_start_date_begins_at_the_rollover_hour(self):
        today = fd.day_date(0, CUTOFF)
        self.assertEqual(fd.day_start(today, CUTOFF), CUTOFF - DAY)
        self.assertEqual(fd.day_start(today - dt.timedelta(days=3), CUTOFF), CUTOFF - 4 * DAY)


class StatsTests(unittest.TestCase):
    def test_streaks_survive_until_today_ends(self):
        self.assertEqual(fd._streaks({1, 2, 3, 10, 11}), (3, 3))
        self.assertEqual(fd._streaks({0, 1, 2}), (3, 3))
        self.assertEqual(fd._streaks({2, 3}), (0, 2))

    def test_long_break_becomes_a_pond_before_the_next_tree(self):
        cards = [card(1, s=30), card(2, s=30)]
        fl = {1: (ms(30), ms(1)), 2: (ms(15), ms(1))}
        review_days = set(range(0, 16)) | {30}
        trees = fd.build_forest(rows(cards, fl, review_days=review_days), CUTOFF, TODAY)["trees"]
        self.assertNotIn("gap", trees[0])
        self.assertEqual(trees[1]["gap"], 14)

    def test_a_week_off_is_a_pond_and_a_long_weekend_is_not(self):
        for away, pond in ((fd.BREAK_DAYS - 1, False), (fd.BREAK_DAYS, True)):
            cards = [card(1, s=30), card(2, s=30)]
            back = away + 2  # the first day, the days away, then the day you came back
            fl = {1: (ms(back), ms(1)), 2: (ms(1), ms(1))}
            trees = fd.build_forest(rows(cards, fl, review_days={back, 1, 0}), CUTOFF, TODAY)["trees"]
            self.assertEqual("gap" in trees[1], pond, f"{away} days away")

    def test_visitors_and_arrivals(self):
        s = {"trees": 50, "longest_streak": 30, "streak": 30, "reviews": 10_020, "today_reviews": 40,
             "ancient": 0, "forest_age": 100, "planted_today": True}
        v = {x["key"]: x["new"] for x in fd.visitors(s)}
        self.assertEqual(v, {"rabbit": True, "deer": True, "fox": True})
        s.update(ponds=1, forest_age=365)
        v = {x["key"]: x["new"] for x in fd.visitors(s)}
        self.assertTrue(v["heron"] is False and v["cabin"] is True)

    def test_anniversaries(self):
        trees = [{"date": "2025-09-19"}, {"date": "2026-09-19"}, {"date": "2025-09-18"}]
        self.assertEqual(fd.anniversaries(trees, dt.date(2026, 9, 19)), [0])


class WeatherTests(unittest.TestCase):
    def test_wmo_mapping(self):
        self.assertEqual([weather.map_wmo(c) for c in (0, 3, 45, 61, 81, 73, 96)],
                         ["clear", "cloudy", "fog", "rain", "rain", "snow", "storm"])

    def forecast(self, code=0, is_day=1, precip=(0, 0, 0), wind=5):
        return {
            "current": {"time": "2026-09-19T15:00", "weather_code": code, "is_day": is_day, "temperature_2m": 14.2, "wind_speed_10m": wind},
            "hourly": {"time": ["2026-09-19T13:00", "2026-09-19T14:00", "2026-09-19T15:00", "2026-09-19T16:00"], "precipitation": list(precip) + [5]},
            "daily": {"time": ["2026-09-18", "2026-09-19"], "sunrise": ["x", "2026-09-19T06:58"], "sunset": ["y", "2026-09-19T19:12"]},
        }

    def test_parse_forecast(self):
        w = weather.parse_forecast(self.forecast(wind=40))
        self.assertEqual((w["weather"], w["sunrise"], w["windy"]), ("clear", "2026-09-19T06:58", True))

    def test_recent_rain_then_sun_is_after_rain(self):
        self.assertEqual(weather.parse_forecast(self.forecast(precip=(0, 1.2, 0)))["weather"], "after_rain")
        self.assertEqual(weather.parse_forecast(self.forecast(precip=(0, 1.2, 0), is_day=0))["weather"], "clear")

    def test_cache_refresh_and_offline_fallback(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        cache = weather.WeatherCache(path)
        calls = []

        def fake(url):
            calls.append(url)
            if "geocoding" in url:
                return {"results": [{"name": "Berlin", "latitude": 52.5, "longitude": 13.4}]}
            return self.forecast(code=61)

        self.assertEqual(cache.refresh("Berlin", fake, now=1000)["weather"], "rain")
        self.assertFalse(cache.needs_refresh("berlin ", now=1000 + 60))
        self.assertTrue(cache.needs_refresh("Berlin", now=1000 + weather.MAX_AGE_SECS + 1))

        def offline(url):
            raise OSError("no network")

        self.assertIsNone(cache.refresh("Berlin", offline, now=5000))
        kept = weather.WeatherCache(path)
        self.assertEqual(kept.current("Berlin", now=5000)["weather"], "rain")  # last good kept
        self.assertFalse(cache.needs_refresh("Berlin", now=5000 + 60))  # backs off after failure
        # but it carries the sunrise, sunset and local time of the moment it was fetched,
        # so once it is hours old the real clock and a daily pick are more honest
        self.assertIsNone(kept.current("Berlin", now=1000 + weather.STALE_SECS + 1))
        self.assertIn("no network", kept.failing("Berlin"))


class SceneTests(unittest.TestCase):
    NOW = dt.datetime(2026, 9, 19, 15, 0)

    def test_fixed_weather_wins_over_real(self):
        real = {"weather": "rain", "local_time": "2026-09-19T15:00", "sunrise": None, "sunset": None, "windy": False}
        m = scene.choose_mood({"weather": "snow"}, self.NOW, real)
        self.assertEqual((m["weather"], m["source"]), ("snow", "manual"))

    def test_environment_weather_and_time_are_independent(self):
        m = scene.choose_mood({"environment": "aurora", "weather": "snow", "time_of_day": "auto"}, self.NOW)
        # the hour is the clock's, and says so: a night-only environment overrules it in the page
        self.assertEqual((m["special"], m["weather"], m["time"], m["clock"]), ("aurora", "snow", "day", True))
        m = scene.choose_mood({"environment": "synthwave", "weather": "rain", "time_of_day": "dawn"}, self.NOW)
        self.assertEqual((m["special"], m["weather"], m["time"], m["clock"]), ("synthwave", "rain", "dawn", False))

    def test_fixed_time_is_respected_even_for_night_environments(self):
        m = scene.choose_mood({"environment": "lanterns", "time_of_day": "dusk"}, self.NOW)
        self.assertEqual((m["special"], m["time"]), ("lanterns", "dusk"))

    def test_real_weather_used_when_auto(self):
        real = {"weather": "fog", "local_time": "2026-09-19T06:40", "sunrise": "2026-09-19T06:58", "sunset": "2026-09-19T19:12", "windy": False, "temp": 9}
        m = scene.choose_mood({"weather": "auto", "time_of_day": "auto"}, self.NOW, real, {"name": "Berlin", "lat": 52.5})
        self.assertEqual((m["weather"], m["time"], m["source"], m["city"]), ("fog", "dawn", "real", "Berlin"))

    def test_the_real_sky_keeps_time_after_the_weather_was_fetched(self):
        # fetched at 06:40 in a UTC+2 city; four hours later it must be day there, not dawn
        real = {"weather": "clear", "local_time": "2026-09-19T06:40", "utc_offset": 7200, "sunrise": "2026-09-19T06:58",
                "sunset": "2026-09-19T19:12", "windy": False}
        later = dt.datetime(2026, 9, 19, 8, 40, tzinfo=dt.timezone.utc)  # 10:40 in the city
        m = scene.choose_mood({"weather": "auto", "time_of_day": "auto"}, later, real)
        self.assertEqual(m["time"], "day")

    def test_no_city_keeps_the_presets_own_weather(self):
        # the real sky without a city follows only the clock; nothing is made up for the date
        wet = next(p for p in presets.FOREST_PRESETS if p.weather not in ("clear", presets.DAILY))
        cfg = dict(wet.values(), weather="auto", time_of_day="auto")
        for d in range(1, 20):
            self.assertEqual(scene.choose_mood(cfg, dt.datetime(2026, 5, d, 12))["weather"], wet.weather)

    def test_nothing_set_is_the_default_preset(self):
        m = scene.choose_mood({}, self.NOW)
        base = presets.FOREST_PRESETS[0]
        self.assertEqual((m["environment"], m["landscape"], m["landmark"], m["weather"], m["time"]),
                         (base.environment, base.landscape, base.landmark, base.weather, base.time))

    def test_surprise_me_daily_takes_the_presets_in_turn(self):
        daily = presets.by_key()["daily"].values()
        days = [dt.datetime(2026, 9, 19, 12) + dt.timedelta(days=d) for d in range(60)]
        picks = [scene.choose_mood(daily, d)["environment"] for d in days]
        turn = [p for p in presets.FOREST_PRESETS if p.key != "daily"]
        self.assertTrue(all(a != b for a, b in zip(picks, picks[1:])), "a new preset every day")
        self.assertEqual(set(picks[:len(turn)]), {p.environment for p in turn}, "every preset comes round")
        # and each day is that preset whole: its landscape, landmark, weather and hour too
        p = presets.of_the_day(days[0].date())
        m = scene.choose_mood(daily, days[0])
        self.assertEqual((m["landscape"], m["weather"], m["time"]), (p.landscape, p.weather, p.time))

    def test_surprise_me_daily_can_follow_the_real_sky(self):
        real = {"weather": "fog", "local_time": "2026-09-19T15:00", "sunrise": None, "sunset": None, "windy": False}
        cfg = dict(presets.by_key()["daily"].values(), weather="auto", time_of_day="auto")
        m = scene.choose_mood(cfg, self.NOW, real)
        self.assertEqual((m["weather"], m["source"]), ("fog", "real"))

    def test_time_of_day(self):
        self.assertEqual([scene.time_of_day(dt.datetime(2026, 9, 19, h)) for h in (3, 7, 12, 19, 23)],
                         ["night", "dawn", "day", "dusk", "night"])

    def test_golden_hour_before_dusk(self):
        self.assertEqual(scene.time_of_day(dt.datetime(2026, 9, 19, 17, 30)), "golden_hour")

    def test_landscape_and_landmark_defaults(self):
        m = scene.choose_mood({}, self.NOW)
        self.assertEqual((m["landscape"], m["landmark"]), ("lake", "none"))
        self.assertEqual(scene.choose_mood({"landscape": "auto"}, self.NOW)["landscape"], "lake")
        m = scene.choose_mood({"landscape": "river", "landmark": "peak"}, self.NOW)
        self.assertEqual((m["landscape"], m["landmark"]), ("river", "peak"))
        # a landmark that no longer exists falls back to the default preset's
        self.assertEqual(scene.choose_mood({"landmark": "gone"}, self.NOW)["landmark"], presets.FOREST_PRESETS[0].landmark)

    def test_sky_events(self):
        self.assertIn("meteor_shower", scene.events({"streak": 100}, dt.date(2026, 5, 1)))
        self.assertIn("meteor_shower", scene.events({"streak": 3}, dt.date(2026, 8, 12)))
        self.assertIn("harvest_moon", scene.events({"forest_age": 730}, dt.date(2026, 5, 1)))
        self.assertEqual(scene.events({"streak": 3, "forest_age": 10}, dt.date(2026, 5, 1), True), ["new_ancient"])

    def test_every_environment_is_its_own_special(self):
        for key in scene.ENVIRONMENTS:
            self.assertEqual(scene.choose_mood({"environment": key}, self.NOW)["special"], key)

    def test_moon_phase(self):
        self.assertAlmostEqual(scene.moon_phase(dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)), 0, places=3)
        self.assertAlmostEqual(scene.moon_phase(dt.datetime(2000, 1, 21, 9, 0, tzinfo=dt.timezone.utc)), 0.5, delta=0.02)

    def journal_for(self, **stats):
        base = {"trees": 40, "young": 3, "ancient": 0, "old": 2, "yellowing": 0, "streak": 12,
                "planted_today": True, "today_cards": 20, "oldest_date": "2025-09-19", "ponds": 0}
        base.update(stats)
        forest = {"trees": [{"date": "2025-09-19", "n": 30}], "stats": base, "visitors": []}
        mood = {"weather": "clear", "special": "none", "time": "day"}
        return scene.journal(forest, mood, dt.date(2026, 9, 19), [])

    def test_an_ordinary_day_says_nothing(self):
        # a line every day is wallpaper; most days the forest should be quiet
        self.assertEqual(self.journal_for(), "")
        self.assertEqual(self.journal_for(planted_today=False), "")
        for w in ("rain", "snow", "fog", "storm"):
            mood = {"weather": w, "special": "none", "time": "day"}
            forest = {"trees": [{"date": "2025-09-19", "n": 30}], "visitors": [],
                      "stats": {"trees": 40, "young": 3, "ancient": 1, "old": 2, "yellowing": 1, "streak": 12,
                                "planted_today": True, "today_cards": 20, "oldest_date": "2025-09-19", "ponds": 1}}
            self.assertEqual(scene.journal(forest, mood, dt.date(2026, 9, 19), []), "")

    def test_it_speaks_on_the_day_a_milestone_is_reached(self):
        self.assertIn("first tree", self.journal_for(trees=1))
        self.assertIn("100th tree", self.journal_for(trees=100))
        self.assertIn("30 days in a row", self.journal_for(streak=30))
        # ... and not the day after
        self.assertEqual(self.journal_for(trees=101), "")
        self.assertEqual(self.journal_for(streak=31), "")

    def test_a_milestone_only_counts_on_a_day_you_planted(self):
        self.assertEqual(self.journal_for(trees=100, planted_today=False), "")

    def test_journal_prefers_new_visitors_then_anniversaries(self):
        forest = {"trees": [{"date": "2025-09-19", "n": 30}], "stats": {"trees": 1, "young": 0, "ancient": 0, "old": 0, "yellowing": 0, "streak": 0, "planted_today": False, "today_cards": 0, "oldest_date": "2025-09-19"},
                  "visitors": [{"key": "fox", "label": "a fox", "why": "you passed 10,000 reviews", "new": True}]}
        mood = {"weather": "clear", "special": "none", "time": "day"}
        self.assertIn("fox", scene.journal(forest, mood, dt.date(2026, 9, 19), [0]))
        forest["visitors"] = []
        self.assertIn("turned a year old", scene.journal(forest, mood, dt.date(2026, 9, 19), [0]))


class SearchTests(unittest.TestCase):
    """What clicking a tree asks Anki for. When the forest skips suspended cards the
    search must too, or the tooltip's count and the browser's list disagree."""

    def test_one_day_is_the_difference_of_two_introduced_terms(self):
        self.assertEqual(fd.day_search(5), ["introduced:6", "-is:suspended", "-introduced:5"])

    def test_today_needs_no_lower_bound(self):
        self.assertEqual(fd.day_search(0), ["introduced:1", "-is:suspended"])

    def test_a_range_spans_from_the_oldest_day_to_the_newest(self):
        terms = fd.day_search(1200, 420)
        self.assertEqual(terms, ["introduced:1201", "-is:suspended", "-introduced:420"])

    def test_a_one_day_range_is_the_same_as_that_day(self):
        self.assertEqual(fd.day_search(30, 30), fd.day_search(30))

    def test_a_forest_that_keeps_suspended_cards_finds_them_too(self):
        self.assertEqual(fd.day_search(5, suspended=True), ["introduced:6", "-introduced:5"])


class RetrievabilityTests(unittest.TestCase):
    """The "% remembered" number, which the tooltip states as fact."""

    def test_a_card_just_reviewed_is_remembered(self):
        self.assertAlmostEqual(fd._retrievability(100, 0, "{}"), 1.0, places=6)

    def test_at_its_stability_a_card_sits_at_ninety_percent(self):
        # that is what FSRS stability means: 90% recall after `stability` days
        self.assertAlmostEqual(fd._retrievability(100, 100, "{}"), 0.9, places=6)
        self.assertAlmostEqual(fd._retrievability(7, 7, '{"decay":0.2}'), 0.9, places=6)

    def test_each_card_uses_its_own_decay(self):
        # FSRS-6 gives every card a decay; a flatter curve forgets more slowly
        late_default = fd._retrievability(10, 100, "{}")
        late_flat = fd._retrievability(10, 100, '{"decay":0.15}')
        self.assertGreater(late_flat, late_default)

    def test_nonsense_decay_falls_back_to_the_default(self):
        for blob in ('{"decay":0}', '{"decay":5}', '{"decay":"x"}', "{}", ""):
            self.assertAlmostEqual(fd._retrievability(50, 50, blob), 0.9, places=6)


class StoreTests(unittest.TestCase):
    """The small JSON files under user_files/."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "state.json")

    def test_a_missing_file_reads_as_empty(self):
        self.assertEqual(store.load_json(self.path), {})

    def test_it_makes_its_own_directory_and_round_trips(self):
        store.save_json(self.path, {"a": 1})
        self.assertEqual(store.load_json(self.path), {"a": 1})

    def test_anything_that_is_not_an_object_reads_as_empty(self):
        store.save_json(self.path, {})
        for junk in ("null", "[1, 2]", "not json at all", ""):
            open(self.path, "w").write(junk)
            self.assertEqual(store.load_json(self.path), {})

    def test_a_failed_write_leaves_the_old_file_alone(self):
        store.save_json(self.path, {"keep": True})
        try:
            store.save_json(self.path, {"bad": {1, 2}})  # a set is not JSON
        except TypeError:
            pass
        self.assertEqual(store.load_json(self.path), {"keep": True})


class RegistryFileTests(unittest.TestCase):
    """Environments, landscapes and landmarks are each one file plus one row.

    A key with no file is a setting the dialog offers and the panel cannot draw; a file
    nothing names is code that ships and never runs. Either way it is a dead setting, and
    that is the failure this catches before anyone sees it.
    """

    WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

    def files(self, kind: str) -> set:
        return {f[:-3] for f in os.listdir(os.path.join(self.WEB, kind)) if f.endswith(".js")}

    def check(self, kind: str, keys: set, register: str, exempt: set | None = None) -> None:
        files = self.files(kind)
        self.assertEqual(keys - files, exempt or set(), f"{kind}: a .json with no .js to draw it")
        self.assertEqual(files - keys, set(), f"{kind}: a .js with no .json to name it")
        for name in files:
            src = open(os.path.join(self.WEB, kind, name + ".js"), encoding="utf-8").read()
            self.assertIn(f"{register}('{name}'", src, f"{kind}/{name}.js should register {name!r}")

    def test_every_environment_names_its_own_file(self):
        # the plain forest needs no file, because it is what every other one departs from
        self.check("envs", set(scene.ENVIRONMENTS), "AF.env", exempt={"natural"})

    def test_every_landscape_names_its_own_file(self):
        self.check("landscapes", set(scene.LANDSCAPES), "AF.landscape")

    def test_every_landmark_names_its_own_file(self):
        self.check("landmarks", set(scene.LANDMARKS), "AF.landmark", exempt={"none"})


class PresetTests(unittest.TestCase):
    """A preset is a shortcut that fills the five look settings, so each of the five has
    to be something the dialog would have offered anyway."""

    def test_every_preset_names_settings_that_exist(self):
        D = presets.DAILY
        for p in presets.FOREST_PRESETS:
            self.assertIn(p.environment, set(scene.ENVIRONMENTS) | {D}, p.key)
            self.assertIn(p.landscape, set(scene.LANDSCAPES) | {D}, p.key)
            self.assertIn(p.landmark, set(scene.LANDMARKS) | {D}, p.key)
            self.assertIn(p.weather, set(scene.WEATHERS) | {D}, p.key)
            self.assertIn(p.time, set(scene.TIMES) | {D}, p.key)

    def test_following_the_real_sky_keeps_the_preset(self):
        # the checkbox swaps a preset's weather and hour for the real ones, not the preset
        for p in presets.FOREST_PRESETS:
            real = dict(p.values(), weather="auto", time_of_day="auto")
            self.assertEqual(presets.match(real), p.key)
            self.assertEqual(presets.apply(p.key, real), real)

    def test_every_environment_is_reachable_from_a_preset(self):
        # an environment no preset offers is one most people will never see
        used = {p.environment for p in presets.FOREST_PRESETS}
        self.assertEqual(set(scene.ENVIRONMENTS) - used, set())

    def test_keys_and_labels_are_unique(self):
        keys = [p.key for p in presets.FOREST_PRESETS]
        self.assertEqual(len(set(keys)), len(keys))
        labels = [p.label for p in presets.FOREST_PRESETS]
        self.assertEqual(len(set(labels)), len(labels))
        self.assertNotIn(presets.CUSTOM, keys)  # Custom is the dropdown's own last row

    def test_a_fresh_install_is_a_preset_and_not_custom(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = json.load(open(os.path.join(here, "config.json"), encoding="utf-8"))
        self.assertNotEqual(presets.match(cfg), presets.CUSTOM,
                            "the shipped config should be one of the presets, or the dialog opens on Custom")

    def test_settings_that_match_nothing_are_custom(self):
        odd = dict(presets.FOREST_PRESETS[1].values(), weather="storm", time_of_day="night")
        self.assertEqual(presets.match(odd), presets.CUSTOM)

    def test_a_preset_round_trips_through_match(self):
        for p in presets.FOREST_PRESETS:
            self.assertEqual(presets.match(p.values()), p.key)

    def test_no_two_presets_stand_for_the_same_five_settings(self):
        # two identical presets would be indistinguishable: picking the second would snap
        # the dropdown back to the first
        seen = {}
        for p in presets.FOREST_PRESETS:
            fingerprint = tuple(sorted(p.values().items()))
            self.assertNotIn(fingerprint, seen, f"{p.key} draws the same scene as {seen.get(fingerprint)}")
            seen[fingerprint] = p.key

    def test_picking_a_preset_fills_the_advanced_settings(self):
        """What the drawer shows after picking a preset: that preset's own five settings,
        not the ones that happened to be there before."""
        before = {"environment": "old_env", "landscape": "old_land", "landmark": "old_mark",
                  "weather": "storm", "time_of_day": "dawn"}
        for p in presets.FOREST_PRESETS:
            after = presets.apply(p.key, before)
            self.assertEqual(after, p.values(), p.key)
            self.assertEqual(presets.match(after), p.key)      # and the dropdown still says so

    def test_custom_leaves_the_settings_alone(self):
        before = {"environment": "old_env", "landscape": "old_land", "landmark": "old_mark",
                  "weather": "storm", "time_of_day": "dawn"}
        self.assertEqual(presets.apply(presets.CUSTOM, before), before)
        self.assertEqual(presets.apply("no_such_preset", before), before)

    def test_changing_one_setting_afterwards_makes_it_custom(self):
        after = presets.apply("synthwave", {})
        self.assertEqual(presets.match(after), "synthwave")
        self.assertEqual(presets.match(dict(after, weather="snow")), presets.CUSTOM)



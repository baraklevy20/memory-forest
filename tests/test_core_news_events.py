"""What's new over its whole life (news.py), the events' journal lines and what is remembered of
a strike (events_state.py), and the live weather's refresh (live_weather.py) - in a stand-in Anki."""

from __future__ import annotations

import datetime as dt
import json
import types
import unittest
from unittest import mock

from fake_anki import addon, mw, reset
from helpers import TODAY

news, events_state, live_weather, state = addon.news, addon.events_state, addon.live_weather, addon.state
DAY = dt.date(2026, 10, 8)
NEWER = {"text": "B.", "announce": {"id": "newer_note", "kind": "note", "title": "New: B", "text": "B."}}
OLDER = {"text": "A.", "announce": {"id": "older_note", "kind": "note", "title": "New: A", "text": "A."}}


def from_1_2_0():
    """As someone updating from 1.2.0: its state.json, and no news.json (1.2.0 had none)."""
    with open(state.STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"Test profile": {"ancient_days": [], "animals": {"all": {"rabbit": None}}}}, f)


def two_versions():
    return mock.patch.object(news, "_versions", return_value=[{"version": "9.1.0", "new": [NEWER]},
                                                              {"version": "9.0.0", "new": [OLDER]}])


class NoteLifeTests(unittest.TestCase):
    def setUp(self):
        reset()
        from_1_2_0()

    def test_only_the_newest_note_shows_and_the_one_behind_it_never_does(self):
        with two_versions():
            self.assertEqual(news.note({}, DAY)["id"], "newer_note")
            news.mark_seen(["newer_note"])
            self.assertIsNone(news.note({}, DAY))
            self.assertIn("older_note", [e["id"] for e in news.unseen({})])  # (the About tab lists it)

    def test_its_three_days_are_kept_across_restarts(self):
        with two_versions():
            news.note({}, DAY)
            news._fresh_at_start = None  # (Anki restarted: only news.json remembers)
            self.assertIsNotNone(news.note({}, DAY + dt.timedelta(days=news.NOTE_DAYS - 1)))
            self.assertIsNone(news.note({}, DAY + dt.timedelta(days=news.NOTE_DAYS)))
            self.assertIn("newer_note", news._load()["seen"])  # (gone for good)

    def test_a_date_put_back_starts_its_days_again(self):
        with two_versions():
            news.note({}, DAY)
            back = DAY - dt.timedelta(days=10)
            self.assertIsNotNone(news.note({}, back))
            self.assertIsNotNone(news.note({}, back + dt.timedelta(days=news.NOTE_DAYS - 1)))
            self.assertIsNone(news.note({}, back + dt.timedelta(days=news.NOTE_DAYS)))

    def test_a_news_file_hand_edited_into_nonsense_is_read_as_nothing_seen(self):
        with open(news.NEWS_PATH, "w", encoding="utf-8") as f:
            json.dump({"seen": "newer_note", "shown": ["x"], "tags": {"bamboo": "new"}}, f)
        with two_versions():
            self.assertEqual(news._load(), {"seen": [], "shown": {}, "tags": {}})
            self.assertEqual(news.note({}, DAY)["id"], "newer_note")
        with open(news.NEWS_PATH, "w", encoding="utf-8") as f:
            f.write("{not json")
        with two_versions():
            self.assertEqual(news.note({}, DAY)["id"], "newer_note")

    def test_a_shown_day_that_is_not_a_date_starts_its_days_from_today(self):
        with open(news.NEWS_PATH, "w", encoding="utf-8") as f:
            json.dump({"seen": [], "shown": {"newer_note": "soon"}}, f)
        with two_versions():
            self.assertIsNotNone(news.note({}, DAY))
            self.assertEqual(news._load()["shown"]["newer_note"], DAY.isoformat())

    def test_ids_no_version_announces_are_never_kept_as_seen(self):
        with two_versions():
            news.mark_seen(["nonsense", "newer_note"])
            self.assertEqual(news._load()["seen"], ["newer_note"])

    def test_picking_a_scenery_with_no_tag_changes_nothing(self):
        with two_versions():
            news.note({}, DAY)  # (news.json written)
            news.tried("bamboo")
            self.assertEqual(news._load()["tags"], {})

    def test_picking_a_scenery_before_news_json_exists_changes_nothing(self):
        with two_versions():
            news.tried("bamboo")
            self.assertEqual(news._load()["tags"], {})

    def test_opening_the_settings_with_user_files_read_only_tags_nothing(self):
        with two_versions(), mock.patch.object(news, "save_json", side_effect=OSError("read-only")), \
                mock.patch.object(news, "log", lambda _msg: None):
            self.assertEqual(news.tile_tags({}, DAY), {})
            self.assertEqual(news.setting_tags({}, DAY), [])

    def test_a_news_file_that_can_t_be_written_still_shows_the_note(self):
        with two_versions(), mock.patch.object(news, "save_json", side_effect=OSError("read-only")), \
                mock.patch.object(news, "log", lambda _msg: None):
            self.assertEqual(news.note({}, DAY)["id"], "newer_note")


class RealNotesTests(unittest.TestCase):
    """The release notes as they ship: someone updating from 1.2.0 hears of 1.3.0; a fresh install
    of nothing."""

    def test_updating_from_1_2_0_brings_the_newest_note(self):
        reset()
        from_1_2_0()
        notes = [e for e in news.offered({}) if e["kind"] == news.NOTE]
        self.assertTrue(notes)
        self.assertEqual(news.note({}, DAY)["id"], notes[0]["id"])

    def test_updating_from_1_2_0_tags_the_heatmap_s_settings_new(self):
        reset()
        from_1_2_0()
        ids = [e["id"] for e in news.offered({})]
        if "calendar-1.3" not in ids:
            self.skipTest("the 1.3.0 note is no longer offered")
        self.assertTrue({"calendar", "finished_decks"} <= set(news.setting_tags({}, DAY)))
        self.assertTrue({"calendar", "finished_decks"} <= set(news.setting_tags({}, DAY + dt.timedelta(days=news.TAG_DAYS - 1))))
        self.assertEqual(news.setting_tags({}, DAY + dt.timedelta(days=news.TAG_DAYS)), [])

    def test_a_fresh_install_hears_of_nothing_at_all(self):
        reset()
        self.assertIsNone(news.note({}, DAY))
        self.assertEqual(news.unseen({}), [])
        self.assertEqual(news.cog_dot({}), "")
        self.assertEqual(news.setting_tags({}, DAY), [])
        self.assertEqual(news.tile_tags({}, DAY), {})

    def test_the_about_tab_lists_the_newest_version_first(self):
        reset()
        versions = [v for v, _summary, _sections in news.about({})]
        self.assertTrue(versions)
        self.assertEqual(versions, sorted(versions, key=lambda v: tuple(int(n) for n in v.split(".")), reverse=True))


class JournalLineTests(unittest.TestCase):
    def test_the_fire_s_lines(self):
        line = events_state.fire_line
        self.assertEqual(line({}), "")
        self.assertIn("Smoke is rising", line({"fire": {"smoke": True}}))
        self.assertEqual(line({"fire": {"smoke": False, "out": True}}), "The last of the fire is out. Your forest is green again.")
        self.assertEqual(line({"fire": {"smoke": False, "out": False, "news": False, "trees": 4}}), "")
        self.assertIn("1 tree is burning", line({"fire": {"smoke": False, "out": False, "news": True, "trees": 1}}))
        self.assertIn("3 trees are burning", line({"fire": {"smoke": False, "out": False, "news": True, "trees": 3}}))

    def test_the_strike_s_line_until_it_is_told(self):
        line = events_state.strike_line
        self.assertEqual(line({"strike": {"news": True, "told": True, "lost": 1}}),
                         "An asteroid took your forest of 1 tree. A new one grows from here.")
        self.assertIn("of 12 trees", line({"strike": {"news": True, "told": True, "lost": 12}}))
        self.assertEqual(line({"strike": {"news": True, "told": False, "lost": 12}}), "")
        self.assertEqual(line({"strike": {"news": False, "told": True, "lost": 12}}), "")
        self.assertEqual(line({"strike": None}), "")

    def test_a_backlog_cleared_on_peaceful_has_no_tumbleweeds_to_blow_away(self):
        cleared = {"overdue": 0, "cleared": True}
        self.assertEqual(events_state.news_line({"nature": "peaceful", "backlog": cleared}), "You cleared your overdue reviews.")
        self.assertEqual(events_state.news_line({"nature": "wild", "backlog": cleared}),
                         "You cleared your overdue reviews. The tumbleweeds blew away.")
        self.assertEqual(events_state.news_line({"nature": "wild", "backlog": dict(cleared, cleared=False)}), "")

    def test_a_strike_comes_before_a_fire_and_a_backlog(self):
        extras = {"nature": "merciless", "strike": {"news": True, "told": True, "lost": 2},
                  "fire": {"smoke": True}, "backlog": {"cleared": True}}
        self.assertIn("asteroid", events_state.news_line(extras))


class SyncsTests(unittest.TestCase):
    def setUp(self):
        reset()
        events_state._synced.clear()
        self.addCleanup(events_state._synced.clear)
        self.addCleanup(setattr, events_state, "_syncing", False)

    def test_a_profile_logged_out_of_ankiweb_never_waits_for_a_sync(self):
        with mock.patch.object(mw.pm, "sync_auth", lambda: None, create=True):
            self.assertTrue(events_state.settled())

    def test_a_logged_in_profile_waits_for_its_first_sync(self):
        with mock.patch.object(mw.pm, "sync_auth", lambda: object(), create=True):
            self.assertFalse(events_state.settled())
            events_state.sync_started()
            self.assertFalse(events_state.settled())
            events_state.sync_finished()
            self.assertTrue(events_state.settled())
            events_state.sync_started()  # (a later sync, under way: the phone's forest waits for it)
            self.assertFalse(events_state.settled())

    def test_an_older_anki_s_sync_key_says_it_syncs(self):
        with mock.patch.object(mw.pm, "profile", {"syncKey": "abc"}, create=True):
            self.assertFalse(events_state.settled())
        with mock.patch.object(mw.pm, "profile", {}, create=True):
            self.assertTrue(events_state.settled())

    def test_a_profile_that_can_t_say_waits_to_be_safe(self):
        def broken():
            raise RuntimeError("no profile")
        with mock.patch.object(mw.pm, "sync_auth", broken, create=True):
            self.assertFalse(events_state.settled())

    def test_a_sync_counts_for_its_own_profile_only(self):
        with mock.patch.object(mw.pm, "sync_auth", lambda: object(), create=True):
            events_state.sync_finished()
            with mock.patch.object(mw.pm, "name", "Someone else"):
                self.assertFalse(events_state.settled())


class StrikeSeenTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_strike_played_marks_every_one_before_it_seen(self):
        events_state.mark_seen("2026-09-10")
        st = state.load_state()
        self.assertTrue(events_state._seen(st, "2026-09-01"))
        self.assertTrue(events_state._seen(st, "2026-09-10"))
        self.assertFalse(events_state._seen(st, "2026-09-12"))
        self.assertEqual(st["strike_seen_day"], TODAY)

    def test_an_older_strike_played_again_leaves_the_newest_seen(self):
        events_state.mark_seen("2026-09-10")
        events_state.mark_seen("2026-08-01")
        self.assertEqual(state.load_state()["strike_seen"], "2026-09-10")

    def test_the_debug_timeline_s_strikes_are_seen_one_by_one(self):
        events_state.mark_seen("t3")
        st = state.load_state()
        self.assertTrue(events_state._seen(st, "t3"))
        self.assertFalse(events_state._seen(st, "t2"))
        self.assertFalse(events_state._seen({}, "2026-09-10"))  # (nothing played yet)

    def test_a_strike_no_longer_the_latest_has_no_forest_to_replay(self):
        self.assertIsNone(events_state.strike_before("2001-01-01"))

    def test_only_the_last_few_strikes_are_kept_to_replay(self):
        events_state._strikes.clear()
        self.addCleanup(events_state._strikes.clear)
        out = {"latest": {"ago": 400, "lost": 1, "before": []}, "craters": []}
        for i in range(events_state.STRIKES_KEPT + 2):
            events_state.strike_payload(out, f"k{i}", lambda ago: "2026-01-01", playable=False)
        self.assertEqual(list(events_state._strikes), [f"k{i}" for i in range(2, events_state.STRIKES_KEPT + 2)])
        self.assertIsNone(events_state.strike_before("k0"))
        self.assertEqual(events_state.strike_before("k5"), {"before": [], "merged": None})


class BacklogMemoryTests(unittest.TestCase):
    def test_a_cleared_backlog_whose_depth_was_never_kept_is_half_deep(self):
        reset()
        state.save_state({"hell_day": TODAY - 1, "hell_level": "deep"})  # (a hand edit, or an older version's)
        out = events_state._backlog({})
        self.assertEqual((out["cleared"], out["was"]), (True, 0.5))
        self.assertEqual(state.load_state()["backlog_cleared"], TODAY)  # (cleared all day long)

    def test_a_day_kept_as_text_is_no_day(self):
        reset()
        state.save_state({"hell_day": str(TODAY - 1)})
        self.assertFalse(events_state._backlog({})["cleared"])


class LiveWeatherTests(unittest.TestCase):
    class Cache:
        def __init__(self, now=None, place=None, failing="", due=True):
            self.now, self.where, self.why, self.due = now, place, failing, due
            self.refreshed = []

        def current(self, _city):
            return self.now

        def place(self, _city):
            return self.where

        def failing(self, _city):
            return self.why

        def needs_refresh(self, _city):
            return self.due

        def refresh(self, city):
            self.refreshed.append(city)
            return {"ok": True}

    def setUp(self):
        reset()
        self.tasks = []
        self.redraws = []
        self.addCleanup(live_weather.redraw_with, live_weather._redraw)  # (the add-on's own, as it loaded)
        live_weather.redraw_with(lambda: self.redraws.append(1))
        self.addCleanup(setattr, live_weather, "_refreshing", False)
        live_weather._refreshing = False
        patch = mock.patch.object(mw, "taskman", types.SimpleNamespace(run_in_background=self.run_later))
        patch.start()
        self.addCleanup(patch.stop)

    def run_later(self, task, done, uses_collection=True):
        self.tasks.append((task, done, uses_collection))

    def finish(self, fail=False):
        task, done, _uses = self.tasks.pop(0)

        class Future:
            def result(self):
                if fail:
                    raise OSError("offline")
                return task()
        done(Future())

    def test_a_fixed_weather_reads_nothing_and_fetches_nothing(self):
        cache = self.Cache(now={"weather": "rain"})
        with mock.patch.object(live_weather, "_weather", cache):
            self.assertEqual(live_weather.for_config({"city": "Berlin", "weather": "fog"}), (None, None, ""))
        self.assertEqual(self.tasks, [])

    def test_the_real_sky_reads_the_cache_and_fetches_once_in_the_background(self):
        cache = self.Cache(now={"weather": "rain"}, place={"name": "Berlin"})
        with mock.patch.object(live_weather, "_weather", cache):
            self.assertEqual(live_weather.for_config({"city": " Berlin ", "weather": "auto"}), ({"weather": "rain"}, {"name": "Berlin"}, ""))
            live_weather.for_config({"city": "Berlin"})  # (no weather set: the real sky)
            self.assertEqual(len(self.tasks), 1)  # (one fetch at a time)
            self.assertFalse(self.tasks[0][2])  # (it needs no collection)
            self.finish()
        self.assertEqual(cache.refreshed, ["Berlin"])
        self.assertEqual(self.redraws, [1])  # the deck list redraws with it
        self.assertFalse(live_weather._refreshing)

    def test_no_weather_yet_says_why(self):
        cache = self.Cache(failing="No city called Atlantis.")
        with mock.patch.object(live_weather, "_weather", cache):
            self.assertEqual(live_weather.for_config({"city": "Atlantis", "weather": "auto"}), (None, None, "No city called Atlantis."))
            self.assertEqual(live_weather.city_problem("Atlantis"), "No city called Atlantis.")
            self.assertEqual(live_weather.city_problem("   "), "")

    def test_a_fetch_that_fails_or_lands_while_studying_redraws_nothing(self):
        cache = self.Cache()
        with mock.patch.object(live_weather, "_weather", cache):
            live_weather.for_config({"city": "Berlin", "weather": "auto"})
            self.finish(fail=True)
            self.assertFalse(live_weather._refreshing)  # (and the next look tries again)
            self.addCleanup(setattr, mw, "state", mw.state)
            mw.state = "review"
            live_weather.for_config({"city": "Berlin", "weather": "auto"})
            self.finish()
        self.assertEqual(self.redraws, [])

    def test_a_fresh_cache_fetches_nothing(self):
        with mock.patch.object(live_weather, "_weather", self.Cache(now={"weather": "clear"}, due=False)):
            live_weather.for_config({"city": "Berlin", "weather": "auto"})
        self.assertEqual(self.tasks, [])

    def test_an_older_anki_s_background_tasks_are_asked_without_uses_collection(self):
        asked = []
        with mock.patch.object(mw, "taskman", types.SimpleNamespace(run_in_background=lambda task, done: asked.append(task))), \
                mock.patch.object(live_weather, "_weather", self.Cache()):
            live_weather.for_config({"city": "Berlin", "weather": "auto"})
        self.assertEqual(len(asked), 1)


if __name__ == "__main__":
    unittest.main()

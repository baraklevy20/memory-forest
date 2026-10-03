"""The forest as the phone gets it (phone_data.py): the note's JSON and the one-file script."""

from __future__ import annotations

import datetime as dt
import json
import os
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import catalog
import phone_data

NOW = dt.datetime(2026, 9, 19, 15, 0)
REAL = {"weather": "rain", "windy": True, "temp": 12, "local_time": "2026-09-19T15:00",
        "sunrise": "2026-09-19T06:52", "sunset": "2026-09-19T19:14"}
PAGE = {"trees": [{"ago": 0, "n": 3}], "stats": {"trees": 1}, "mood": {"time": "day"}, "journal": "A new tree.",
        "channel": "memory_forest", "deckId": None, "deckName": None, "highlight": False, "litCount": None,
        "weatherError": "", "inAnki": True, "maxWidth": 800, "strike": {"fresh": True}, "craters": []}


class BundleTests(unittest.TestCase):
    def test_it_holds_every_script_the_forest_can_use_and_boots_last(self):
        text = phone_data.bundle()
        for rel in catalog.SCRIPTS + ("phone.js",):
            with open(os.path.join(catalog.WEB, rel), encoding="utf-8") as f:
                self.assertIn(f.read(), text, rel)
        with open(os.path.join(catalog.WEB, "phone.js"), encoding="utf-8") as f:
            self.assertTrue(text.rstrip().endswith(f.read().rstrip()))
        with open(os.path.join(catalog.WEB, "forest.js"), encoding="utf-8") as f:
            self.assertNotIn(f.read(), text)  # the deck list's boot script would mount a second forest

    def test_the_scenery_is_not_in_it_but_each_piece_a_file_of_its_own(self):
        text = phone_data.bundle()
        for kind in catalog.KINDS:
            for key in catalog.entries(kind):
                path = os.path.join(catalog.WEB, kind, f"{key}.js")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.assertNotIn(f.read(), text, f"{kind}/{key}")
        days = [{"mood": {"special": "aurora", "landscape": "lake", "landmark": "none"}},
                {"mood": {"special": "aurora", "landscape": "meadow", "landmark": None}}]
        self.assertEqual(phone_data.scenery(days), ["envs/aurora.js", "landscapes/lake.js", "landscapes/meadow.js"])
        self.assertTrue(phone_data.part_name("envs/aurora.js", b"x").startswith(phone_data.SCRIPT_PREFIX + "envs-aurora-"))
        self.assertNotEqual(phone_data.part_name("envs/aurora.js", b"x"), phone_data.part_name("envs/aurora.js", b"y"))

    def test_the_stylesheet_comes_along(self):
        self.assertIn(".af-panel", phone_data.bundle())


class ScheduleTests(unittest.TestCase):
    def test_one_scene_a_day_from_today(self):
        days = phone_data.schedule({}, NOW)
        self.assertEqual(len(days), phone_data.SCHEDULE_DAYS)
        self.assertEqual(days[0]["date"], "2026-09-19")
        self.assertEqual(days[-1]["date"], (NOW.date() + dt.timedelta(days=phone_data.SCHEDULE_DAYS - 1)).isoformat())
        self.assertEqual([d["dayNumber"] for d in days[:2]], [NOW.date().toordinal(), NOW.date().toordinal() + 1])

    def test_the_clock_is_the_phones_when_time_of_day_is_automatic(self):
        self.assertTrue(phone_data.schedule({"time_of_day": "auto"}, NOW)[0]["mood"]["clock"])
        fixed = phone_data.schedule({"time_of_day": "dusk"}, NOW)[0]["mood"]
        self.assertEqual((fixed["time"], fixed["clock"]), ("dusk", False))

    def test_surprise_me_daily_changes_the_scene_from_day_to_day(self):
        daily = dict.fromkeys(("environment", "weather", "time_of_day", "landscape", "landmark"), "daily")
        envs = {d["mood"]["environment"] for d in phone_data.schedule(daily, NOW)}
        self.assertGreater(len(envs), 1)

    def test_live_weather_is_todays_only_and_has_a_fallback(self):
        cfg = {"weather": "auto", "city": "Berlin"}
        days = phone_data.schedule(cfg, NOW, REAL, {"name": "Berlin"})
        self.assertEqual((days[0]["mood"]["weather"], days[0]["mood"]["source"]), ("rain", "real"))
        self.assertEqual(days[0]["liveUntil"], int((NOW + dt.timedelta(hours=phone_data.LIVE_WEATHER_HOURS)).timestamp() * 1000))
        self.assertNotEqual(days[0]["fallback"]["source"], "real")
        self.assertNotEqual(days[1]["mood"]["source"], "real")
        self.assertNotIn("fallback", days[1])

    def test_each_day_can_be_named(self):
        days = phone_data.schedule({}, NOW, scene_name=lambda date: {"sceneName": date.isoformat()})
        self.assertEqual(days[1]["sceneName"], "2026-09-20")


class PayloadTests(unittest.TestCase):
    def payload(self, **kw):
        return phone_data.phone_payload(PAGE, {}, NOW, "_memory_forest-abc.js", **kw)

    def test_what_only_the_deck_list_uses_stays_behind(self):
        data = self.payload()
        for key in phone_data.DESKTOP_ONLY:
            self.assertNotIn(key, data)
        self.assertEqual((data["trees"], data["journal"]), (PAGE["trees"], PAGE["journal"]))
        self.assertEqual((data["inAnki"], data["script"], data["v"]), (False, "_memory_forest-abc.js", phone_data.VERSION))

    def test_a_strike_only_plays_on_the_phone_when_asked(self):
        # the desktop plays it and says it has been seen; the phone can't, so it only replays
        self.assertEqual(self.payload()["strike"], {"fresh": False})
        self.assertIsNone(phone_data.phone_payload(dict(PAGE, strike=None), {}, NOW, "x.js")["strike"])

    def test_the_suns_hours_are_the_citys_or_the_defaults(self):
        self.assertEqual(self.payload()["sun"]["rise"], "06:30")
        self.assertEqual(self.payload(real=REAL)["sun"], {"rise": "06:52", "set": "19:14", "twilight": 60})

    def test_the_encoded_json_holds_nothing_html_could_take_for_markup(self):
        data = dict(self.payload(), journal="<b>Tom & Jerry</b> — ✓")
        text = phone_data.encode(data)
        for c in "<>&":
            self.assertNotIn(c, text)
        self.assertTrue(text.isascii())
        self.assertEqual(json.loads(text)["journal"], "<b>Tom & Jerry</b> — ✓")


class SameForestTests(unittest.TestCase):
    def test_a_later_write_of_the_same_forest_is_the_same(self):
        first = phone_data.phone_payload(PAGE, {"weather": "auto", "city": "Berlin"}, NOW, "s.js", REAL)
        later = phone_data.phone_payload(PAGE, {"weather": "auto", "city": "Berlin"}, NOW + dt.timedelta(minutes=5), "s.js", REAL)
        self.assertTrue(phone_data.same_forest(phone_data.encode(first), later))
        # a degree or two warmer is not worth an upload; a change of weather's worth is
        warmer = phone_data.phone_payload(PAGE, {"weather": "auto", "city": "Berlin"}, NOW, "s.js", dict(REAL, temp=14))
        self.assertTrue(phone_data.same_forest(phone_data.encode(first), warmer))
        hot = phone_data.phone_payload(PAGE, {"weather": "auto", "city": "Berlin"}, NOW, "s.js", dict(REAL, temp=20))
        self.assertFalse(phone_data.same_forest(phone_data.encode(first), hot))

    def test_a_changed_forest_a_new_day_or_a_new_script_is_not(self):
        old = phone_data.encode(phone_data.phone_payload(PAGE, {}, NOW, "s.js"))
        grown = dict(PAGE, trees=[{"ago": 0, "n": 4}])
        self.assertFalse(phone_data.same_forest(old, phone_data.phone_payload(grown, {}, NOW, "s.js")))
        self.assertFalse(phone_data.same_forest(old, phone_data.phone_payload(PAGE, {}, NOW + dt.timedelta(days=1), "s.js")))
        self.assertFalse(phone_data.same_forest(old, phone_data.phone_payload(PAGE, {}, NOW, "t.js")))

    def test_live_weather_running_out_is_sent_again(self):
        cfg = {"weather": "auto", "city": "Berlin"}
        first = phone_data.encode(phone_data.phone_payload(PAGE, cfg, NOW, "s.js", REAL))
        half = dt.timedelta(hours=phone_data.LIVE_WEATHER_HOURS / 2)
        # a sync soon after: the phone's live weather has hours left, nothing to write
        soon = phone_data.phone_payload(PAGE, cfg, NOW + half - dt.timedelta(minutes=10), "s.js", REAL)
        self.assertTrue(phone_data.same_forest(first, soon))
        # past half its hours: written again, so it does not run out while the computer syncs
        later = phone_data.phone_payload(PAGE, cfg, NOW + half + dt.timedelta(minutes=10), "s.js", REAL)
        self.assertFalse(phone_data.same_forest(first, later))
        # without live weather, time alone never asks for a write
        plain = phone_data.encode(phone_data.phone_payload(PAGE, {}, NOW, "s.js"))
        self.assertTrue(phone_data.same_forest(plain, phone_data.phone_payload(PAGE, {}, NOW + 2 * half, "s.js")))

    def test_an_empty_or_hand_edited_field_is_not(self):
        new = phone_data.phone_payload(PAGE, {}, NOW, "s.js")
        for old in ("", "not json", "[]"):
            self.assertFalse(phone_data.same_forest(old, new))


if __name__ == "__main__":
    unittest.main()

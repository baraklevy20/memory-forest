"""What's new (news.py): who hears of what, once, and only of what their edition has."""

from __future__ import annotations

import datetime as dt
import json
import os
import unittest
from unittest import mock

from fake_anki import addon, reset

news = addon.news
DAY = dt.date(2026, 10, 8)
DEBUG = {"debug": True}
DEBUG_BASE = {"debug": True, "debug_edition": "base"}
DEBUG_PLUS = {"debug": True, "debug_edition": "plus"}
NOTE = {"text": "A feature.", "announce": {"id": "a_feature", "kind": "note", "title": "New: a feature",
                                          "text": "It does things.", "action": "See it", "opens": "fine"}}
SCENERY = {"text": "Bamboo comes to every edition.", "needs": "scenery:bamboo", "announce": {"id": "new_bamboo", "kind": "dot"}}
SETTINGS = {"text": "Clearer settings.", "announce": {"id": "new_settings", "kind": "dot"}}
IMPROVED_SCENERIES = {"text": "Bamboo and Cherry blossom are repainted.", "announce": {"id": "repainted", "kind": "improved", "sceneries": ["bamboo", "cherry_blossom"]}}
PLUS_SCENERY = {"text": "Cherry blossom.", "needs": "scenery:cherry_blossom", "announce": {"id": "new_cherry", "kind": "dot"}}


def updated():
    """As someone with a forest from before: state.json holds something."""
    with open(addon.state.STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"User 1": {"ancient_days": []}}, f)


def notes(*items, fixed=()):
    """release_notes.json as one version holding these items."""
    return mock.patch.object(news, "_versions", return_value=[{"version": "9.0.0", "new": list(items), "fixed": list(fixed)}])


def editions_here(test):
    """Pretending to be base or Plus needs editions.json, which only the private copy has."""
    if not os.path.exists(addon.edition.EDITIONS_FILE):
        test.skipTest("no editions.json: the public repo is one edition")


def debug_tools():
    """As in this copy, which has the debug tools (a release has no debug_events.py)."""
    return mock.patch.object(addon.state.os.path, "exists", return_value=True)


class FreshOrUpdatedTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_a_fresh_install_hears_of_nothing(self):
        with notes(NOTE):
            self.assertIsNone(news.note({}, DAY))
        self.assertTrue(os.path.exists(news.NEWS_PATH))

    def test_a_fresh_install_hears_of_nothing_after_its_first_forest_too(self):
        news.started()  # nothing kept yet, as the add-on loads
        try:
            with notes(NOTE):
                addon.state.save_state({"animals": {"all": {}}})  # the first forest's, saved before it asks
                self.assertIsNone(news.note({}, DAY))
        finally:
            news._fresh_at_start = None

    def test_someone_who_updated_gets_the_note(self):
        updated()
        with notes(NOTE):
            self.assertEqual(news.note({}, DAY), {"id": "a_feature", "title": "New: a feature", "text": "It does things.", "action": "See it"})


class NoteTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()
        patch = notes(NOTE)
        patch.start()
        self.addCleanup(patch.stop)

    def test_answered_it_is_gone_for_good(self):
        news.mark_seen(["a_feature"])
        self.assertIsNone(news.note({}, DAY))

    def test_unanswered_it_goes_after_three_days(self):
        news.note({}, DAY)
        self.assertIsNotNone(news.note({}, DAY + dt.timedelta(days=news.NOTE_DAYS - 1)))
        self.assertIsNone(news.note({}, DAY + dt.timedelta(days=news.NOTE_DAYS)))

    def test_its_button_opens_a_tab(self):
        self.assertEqual(news.opens("a_feature"), "fine")

    def test_the_debug_replays(self):
        news.replay_fresh()
        self.assertIsNone(news.note({}, DAY))
        news.replay_update()
        self.assertIsNotNone(news.note({}, DAY))


class DebugSampleTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()

    def test_the_made_up_ones_only_while_debug_is_on(self):
        with notes():
            self.assertIsNone(news.note({}, DAY))
            self.assertEqual(news.dots({}), [])
            with debug_tools():
                self.assertEqual(news.note(DEBUG, DAY)["id"], "debug_note")
                self.assertEqual(news.dots(DEBUG), ["bamboo"])

    def test_a_real_note_comes_before_the_made_up_one(self):
        with notes(NOTE), debug_tools():
            self.assertEqual(news.note(DEBUG, DAY)["id"], "a_feature")


class ShowItAsNewTests(unittest.TestCase):
    """The Debug tab's Show it as new."""

    def setUp(self):
        reset()
        updated()

    def test_the_made_up_note_points_at_any_setting(self):
        with notes(NOTE), debug_tools():
            news.debug_show(opens="animations", name="Animate the forest")
            shown = news.note(DEBUG, DAY)
            self.assertEqual((shown["id"], shown["title"]), ("debug_note", "New: Animate the forest"))
            self.assertEqual(news.opens("debug_note"), "animations")

    def test_a_real_note_again_even_once_seen(self):
        with notes(NOTE), debug_tools():
            news.mark_seen(["a_feature"])
            news.debug_show(show="a_feature")
            self.assertEqual(news.note(DEBUG, DAY)["id"], "a_feature")
            self.assertEqual(news.opens("a_feature"), "fine")

    def test_answered_it_is_gone_again(self):
        with notes(), debug_tools():
            news.debug_show(opens="city", name="Your city")
            news.mark_seen(["debug_note"])
            self.assertIsNone(news.note(DEBUG, DAY))

    def test_with_debug_off_it_changes_nothing(self):
        with notes(NOTE):
            news.mark_seen(["a_feature"])
            news.debug_show(opens="city", name="Your city")
            self.assertIsNone(news.note({}, DAY))


class DotTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()

    def test_a_new_scenery_dots_the_cog_until_the_settings_open(self):
        with notes(SCENERY):
            self.assertEqual(news.dots({}), ["bamboo"])
            self.assertEqual(news.settings_opened({}), ["bamboo"])  # NEW on its tile, this visit
            self.assertEqual(news.dots({}), [])
            self.assertEqual(news.settings_opened({}), [])

    def test_new_settings_dot_the_cog_with_no_tile_to_tag(self):
        with notes(SETTINGS):
            self.assertEqual(news.cog_dot({}), "settings")
            self.assertEqual(news.dots({}), [])
            self.assertEqual(news.settings_opened({}), [])
            self.assertEqual(news.cog_dot({}), "")

    def test_a_new_scenery_names_the_dot_even_beside_new_settings(self):
        with notes(SETTINGS, SCENERY):
            self.assertEqual(news.cog_dot({}), "scenery")
            self.assertEqual(news.settings_opened({}), ["bamboo"])
            self.assertEqual(news.cog_dot({}), "")

    def test_a_scenery_the_edition_lacks_is_never_announced(self):
        editions_here(self)
        with notes(PLUS_SCENERY), debug_tools():
            self.assertNotIn("cherry_blossom", news.dots(DEBUG_BASE))  # (debug's made-up one is there)
            self.assertIn("cherry_blossom", news.dots(DEBUG_PLUS))


class ImprovedTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()

    def test_improved_sceneries_light_the_dot_and_are_tagged_on_the_first_visit(self):
        with notes(IMPROVED_SCENERIES):
            self.assertEqual(news.cog_dot({}), "scenery")
            self.assertIn("bamboo", news.improved_opened({}))
            self.assertEqual(news.cog_dot({}), "")  # seeing them answers the dot
            self.assertEqual(news.improved_opened({}), [])

    def test_a_fresh_install_sees_nothing_as_improved(self):
        reset()
        with notes(IMPROVED_SCENERIES):
            self.assertEqual(news.improved_opened({}), [])

    def test_only_the_sceneries_the_edition_has_are_tagged(self):
        editions_here(self)
        with notes(IMPROVED_SCENERIES), debug_tools():
            self.assertEqual(news.improved_opened(DEBUG_BASE), ["bamboo"])


class TileTagTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()

    def test_a_tag_stays_on_later_visits_until_the_scenery_is_picked(self):
        with notes(SCENERY, IMPROVED_SCENERIES):
            self.assertEqual(news.tile_tags({}, DAY)["bamboo"], "new")  # new wins over improved
            self.assertEqual(news.tile_tags({}, DAY + dt.timedelta(days=1))["bamboo"], "new")
            news.tried("bamboo")
            self.assertNotIn("bamboo", news.tile_tags({}, DAY + dt.timedelta(days=2)))

    def test_debugs_made_up_new_scenery_never_hides_a_real_improved_tag(self):
        with notes(IMPROVED_SCENERIES), debug_tools():
            self.assertEqual(news.tile_tags(DEBUG, DAY).get("bamboo"), "improved")

    def test_a_tag_goes_after_two_weeks_unpicked(self):
        with notes(IMPROVED_SCENERIES):
            self.assertEqual(news.tile_tags({}, DAY).get("bamboo"), "improved")
            self.assertIn("bamboo", news.tile_tags({}, DAY + dt.timedelta(days=news.TAG_DAYS - 1)))
            self.assertNotIn("bamboo", news.tile_tags({}, DAY + dt.timedelta(days=news.TAG_DAYS)))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        reset()
        updated()

    def test_replaying_the_update_shows_only_the_newest_versions_news(self):
        versions = [{"version": "9.1.0", "improved": [IMPROVED_SCENERIES]}, {"version": "9.0.0", "new": [NOTE, SCENERY]}]
        with mock.patch.object(news, "_versions", return_value=versions), debug_tools():
            news.replay_update()
            self.assertEqual(news.update_label(), "9.0.0 to 9.1.0")
            # 9.1.0's improved bamboo lights it; 9.0.0's new bamboo and debug's sample are old news
            self.assertEqual(news.cog_dot(DEBUG), "scenery")
            self.assertIsNone(news.note(DEBUG, DAY))
            self.assertEqual(news.tile_tags(DEBUG, DAY).get("bamboo"), "improved")


class AboutTests(unittest.TestCase):
    def setUp(self):
        reset()

    def test_new_improved_and_fixed_under_their_headings(self):
        with notes("Something new.", fixed=["A fix."]):
            self.assertEqual(news.about({}), [("9.0.0", "", [("New", ["Something new."]), ("Fixed", ["A fix."])])])

    def test_only_what_the_edition_has(self):
        editions_here(self)
        with notes("Something new.", PLUS_SCENERY), debug_tools():
            self.assertEqual(news.about(DEBUG_BASE), [("9.0.0", "", [("New", ["Something new."])])])
            self.assertEqual(news.about(DEBUG_PLUS), [("9.0.0", "", [("New", ["Something new.", "Cherry blossom."])])])

    def test_the_real_notes_read(self):
        versions = [v for v, _summary, _sections in news.about({})]
        self.assertTrue(versions)
        self.assertEqual(len(versions), len(set(versions)))


if __name__ == "__main__":
    unittest.main()

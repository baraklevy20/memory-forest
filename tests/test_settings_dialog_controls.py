"""Each control of the real settings dialog, clicked or typed into as a user would, and what it
saves: the scenery picker and Customize, the real sky and the city, the Forest tab, the Heatmap
tab's colours, styles, screens, week, streak and Busier days, the Decks tab, the Debug tab, and
the NEW tags a note puts on them. Skipped without PyQt6: see settings_qt.py."""

from __future__ import annotations

import datetime
import unittest

import settings_qt as Q
from settings_qt import QtCase, addon, needs_editions, saved

if Q.HAVE_QT:
    from PyQt6.QtCore import QDate, Qt
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QLabel, QMenu


def done_saves(test, d, expected: dict):
    test.done(d)
    test.assertEqual(saved(), expected)


def tile(d, key):
    return next(t for t in d.scenery.picker.tiles if t.preset.key == key)


def look_of(key) -> dict:
    """What picking preset `key` saves: its five settings, those at their default left out."""
    defaults = Q.fake_anki.mw.addonManager.defaults
    return {k: v for k, v in addon.presets.by_key()[key].values().items() if defaults.get(k) != v}


def pills(widget) -> list:
    return [w for w in widget.findChildren(QLabel) if w.text() == "NEW" or "NEW&nbsp;" in w.text()]


class SceneryTests(QtCase):
    def test_clicking_a_tile_picks_its_scenery(self):
        d = self.open_dialog()
        tile(d, "synthwave").click()
        Q.settle()
        self.assertEqual(d.scenery.preset.currentData(), "synthwave")
        self.assertTrue(tile(d, "synthwave").isChecked())
        self.assertFalse(tile(d, "golden_lake").isChecked())
        self.assertEqual(d.custom.look(), addon.presets.by_key()["synthwave"].values())
        done_saves(self, d, look_of("synthwave"))

    def test_clicking_the_chosen_tile_keeps_it_chosen(self):
        d = self.open_dialog()
        tile(d, "golden_lake").click()
        Q.settle()
        self.assertTrue(tile(d, "golden_lake").isChecked())
        done_saves(self, d, {})

    def test_the_dialog_opens_on_the_scenery_the_config_is(self):
        d = self.open_dialog(addon.presets.by_key()["bamboo"].values())
        self.assertEqual(d.scenery.preset.currentData(), "bamboo")
        self.assertTrue(tile(d, "bamboo").isChecked())

    def test_surprise_me_daily_saves_daily_for_all_five(self):
        d = self.open_dialog()
        tile(d, "daily").click()
        Q.settle()
        done_saves(self, d, dict.fromkeys(addon.presets.LOOK, "daily"))

    def test_a_search_shows_only_the_sceneries_it_names_and_enter_picks_the_first(self):
        d = self.open_dialog()
        picker = d.scenery.picker
        # (offered once there are more sceneries than SEARCH_FROM: not in the public repo's copy)
        self.assertEqual(picker.search.isVisible(), len(picker.tiles) > addon.s_scenery_picker.SEARCH_FROM)
        picker.search.setText("synthw")
        Q.settle()
        shown = [t.preset.key for t in picker.tiles if t.isVisible()]
        self.assertEqual(shown, ["synthwave"])
        self.press(picker.search, Qt.Key.Key_Return)
        self.assertTrue(d.isVisible())  # (Enter in the search is not Done)
        self.assertEqual(d.scenery.preset.currentData(), "synthwave")
        picker.search.setText("no such scenery")
        Q.settle()
        self.assertTrue(picker.none_found.isVisible())

    def test_enter_on_a_tile_picks_it(self):
        d = self.open_dialog()
        t = tile(d, "aurora")
        t.setFocus()
        self.press(t, Qt.Key.Key_Return)
        self.assertTrue(d.isVisible())
        self.assertEqual(d.scenery.preset.currentData(), "aurora")

    def test_a_plus_tile_in_the_base_edition_shows_the_way_to_plus_and_picks_nothing(self):
        d = self.open_dialog({"debug": True, "debug_edition": "base"})
        locked = next(t for t in d.scenery.picker.tiles if t.locked)
        locked.click()
        Q.settle()
        self.assertIn("is in Memory Forest Plus", d.scenery.picker.note.text())
        self.assertTrue(d.scenery.picker.note.isVisible())
        self.assertEqual(d.scenery.preset.currentData(), "golden_lake")
        tile(d, "aurora").click()  # (picking a scenery puts the line away)
        Q.settle()
        self.assertFalse(d.scenery.picker.note.isVisible())

    def test_the_real_sky_sets_weather_and_time_to_automatic_and_back(self):
        d = self.open_dialog()
        self.assertFalse(d.scenery.city.isEnabled())
        d.scenery.real_sky.click()
        Q.settle()
        self.assertEqual((d.custom.weather.currentData(), d.custom.time.currentData()), ("auto", "auto"))
        self.assertTrue(d.scenery.city.isEnabled())
        d.scenery.city.setText(" Berlin ")
        d.scenery.city.editingFinished.emit()
        Q.let_save()
        self.assertEqual(saved(), {"weather": "auto", "time_of_day": "auto", "city": "Berlin"})
        d.scenery.real_sky.click()  # (off: the scenery's own sky back)
        Q.settle()
        done_saves(self, d, {"city": "Berlin"})

    def test_customize_opens_in_the_tiles_place_and_goes_back(self):
        d = self.open_dialog()
        sc = d.scenery
        self.assertEqual(sc.customize.text(), "Customize Golden hour by the lake ›")
        sc.customize.on_click()
        Q.settle()
        self.assertTrue(sc.customizing())
        self.assertFalse(sc.picker.search.isVisible())
        self.assertTrue(sc.custom.isVisible())
        sc.custom.back.on_click()
        Q.settle()
        self.assertFalse(sc.customizing())
        self.assertEqual(sc.picker.search.isVisible(), sc.picker.search_wanted)

    def test_a_customized_setting_makes_your_own_mix_and_reset_puts_it_back(self):
        d = self.open_dialog()
        c = d.custom
        d.scenery.show_customize(True)
        Q.settle()
        c.landmark.setCurrentIndex(c.landmark.findData("pagoda"))
        Q.settle()
        self.assertEqual(d.scenery.preset.currentData(), addon.presets.CUSTOM)
        self.assertTrue(c.resets["landmark"].isVisible())
        self.assertFalse(c.resets["landscape"].isVisible())
        self.assertIn("your own mix", c.title.text())
        self.assertFalse(any(t.isChecked() for t in d.scenery.picker.tiles))
        Q.let_save()
        self.assertEqual(saved(), {"landmark": "pagoda"})
        c.resets["landmark"].click()
        Q.settle()
        self.assertEqual(d.scenery.preset.currentData(), "golden_lake")
        self.assertFalse(c.resets["landmark"].isVisible())
        done_saves(self, d, {})

    def test_the_heatmap_tab_follows_the_scenery_chosen(self):
        d = self.open_dialog()
        tile(d, "lanterns").click()
        Q.settle()
        self.assertEqual(d.heatmap.look.here, "lanterns")
        self.assertEqual(d.heatmap.look.tile_choice.currentData(), "scenery")


class ForestTabTests(QtCase):
    def test_nature_saves_the_level_clicked_and_says_what_it_means(self):
        d = self.open_dialog()
        note = d.forest.nature_note.text()
        d.forest.nature.buttons["merciless"].click()
        Q.settle()
        self.assertNotEqual(d.forest.nature_note.text(), note)
        done_saves(self, d, {"nature": "merciless"})

    def test_each_nature_level_has_its_picture_at_the_tiles_size(self):
        tab = addon.s_forest_tab
        for level in tab.NATURE_LABELS:
            movie = Q.QtGui.QMovie(tab.os.path.join(tab.NATURE_ICONS, f"{level}.gif"))
            self.assertTrue(movie.isValid(), level)
            self.assertGreater(movie.frameCount(), 1, level)
            movie.jumpToFrame(0)
            self.assertEqual((movie.currentPixmap().width(), movie.currentPixmap().height()), (tab.NATURE_GIF_W, tab.NATURE_GIF_H), level)
            self.assertIn(level, tab.NATURE_STILL_MS)

    def playing(self, d) -> list:
        return [k for k, t in d.forest.nature.buttons.items() if t.playing()]

    def test_the_chosen_nature_tile_plays_and_the_others_hold_still(self):
        d = self.open_dialog({"nature": "wild"})
        self.tab(d, "Forest")
        tiles = d.forest.nature.buttons
        self.assertEqual(self.playing(d), ["wild"])
        self.assertTrue(all(not t.still.isNull() for t in tiles.values()))
        tiles["merciless"].click()
        Q.settle()
        self.assertEqual(self.playing(d), ["merciless"])
        self.assertEqual([k for k, t in tiles.items() if t.isChecked()], ["merciless"])  # (never two chosen)
        tiles["merciless"].click()  # (the chosen one again: still chosen)
        Q.settle()
        self.assertEqual(d.forest.nature.currentData(), "merciless")
        d.forest.animations.buttons["off"].click()
        Q.settle()
        self.assertEqual(self.playing(d), [])
        self.tab(d, "Scenery")  # (on another tab it never plays)
        d.forest.animations.buttons["on"].click()
        Q.settle()
        self.assertEqual(self.playing(d), [])
        self.tab(d, "Forest")
        self.assertEqual(self.playing(d), ["merciless"])
        done_saves(self, d, {"nature": "merciless"})

    def test_nature_tiles_hold_still_with_ankis_reduce_motion_on_follow_system(self):
        Q.mw.pm.reduce_motion = lambda: True
        self.addCleanup(lambda: Q.mw.pm.__dict__.pop("reduce_motion", None))
        d = self.open_dialog({"animations": "system"})
        self.tab(d, "Forest")
        self.assertEqual(self.playing(d), [])

    def test_nature_tiles_are_one_tab_stop_with_the_arrow_keys_between_them(self):
        d = self.open_dialog({"nature": "peaceful"})
        self.tab(d, "Forest")
        tiles = d.forest.nature.buttons
        stops = [k for k, t in tiles.items() if t.focusPolicy() == Qt.FocusPolicy.StrongFocus]
        self.assertEqual(stops, ["peaceful"])
        self.press(tiles["peaceful"], Qt.Key.Key_Right)
        Q.settle()
        self.assertEqual(d.forest.nature.currentData(), "wild")
        self.assertEqual([k for k, t in tiles.items() if t.focusPolicy() == Qt.FocusPolicy.StrongFocus], ["wild"])
        self.press(tiles["wild"], Qt.Key.Key_Right)
        self.press(tiles["merciless"], Qt.Key.Key_Right)  # (the last: stays)
        Q.settle()
        self.assertEqual(d.forest.nature.currentData(), "merciless")
        self.press(tiles["merciless"], Qt.Key.Key_Left)
        Q.settle()
        self.assertEqual(d.forest.nature.currentData(), "wild")
        self.assertEqual(self.playing(d), ["wild"])
        done_saves(self, d, {"nature": "wild"})

    def test_enter_on_a_nature_tile_picks_it_and_not_done(self):
        d = self.open_dialog({"nature": "peaceful"})
        self.tab(d, "Forest")
        tile = d.forest.nature.buttons["merciless"]
        self.press(tile, Qt.Key.Key_Return)
        Q.settle()
        self.assertTrue(d.isVisible())
        self.assertEqual(d.forest.nature.currentData(), "merciless")

    def test_nature_news_points_at_the_tiles_group(self):
        d = self.open_dialog()
        widget, name = d.forest.news_targets()["nature"]
        self.assertEqual(name, "Nature")
        self.assertIs(widget, d.forest.nature_group.title)
        self.assertTrue(d.forest.nature_group.isAncestorOf(d.forest.nature))

    def test_where_the_forest_shows(self):
        d = self.open_dialog()
        f = d.forest
        f.main_forest.buttons[False].click()
        f.deck_mode.buttons["own"].click()
        f.finished.click()
        done_saves(self, d, {"main_forest": False, "deck_forest_mode": "own", "finished_decks": False})

    def test_the_layout_picture_and_side(self):
        d = self.open_dialog()
        lay = d.forest.layout_pick
        self.assertEqual(lay.choice.currentData(), "under")
        self.assertFalse(lay.side.isEnabled())  # (nothing beside the list)
        lay.choice.buttons["forest_side"].click()
        Q.settle()
        self.assertTrue(lay.side.isEnabled())
        lay.side.buttons["left"].click()
        done_saves(self, d, {"layout": "forest_side", "layout_side": "left"})

    def test_the_layout_pictures_are_one_even_row_and_follow_the_side(self):
        d = self.open_dialog()
        lay = d.forest.layout_pick
        widths = {b.width() for b in lay.choice.buttons.values()}
        self.assertEqual(len(widths), 1)
        right = lay.choice.pictures["forest_side"].pixmap().toImage()
        lay.choice.buttons["forest_side"].click()
        lay.side.buttons["left"].click()
        Q.settle()
        left = lay.choice.pictures["forest_side"].pixmap().toImage()
        self.assertEqual(left, right.mirrored(True, False))  # (the side column on the other side)

    def test_cancel_puts_the_layout_back(self):
        d = self.open_dialog()
        d.forest.layout_pick.choice.buttons["both_side"].click()
        Q.let_save()
        self.assertEqual(Q.current()["layout"], "both_side")  # (the deck list behind is the preview)
        self.cancel(d)
        self.assertEqual(Q.current()["layout"], "under")

    def test_the_forest_width(self):
        d = self.open_dialog()
        d.forest.max_width.setValue(1000)
        done_saves(self, d, {"max_width": 1000})

    def test_animation_off_stills_the_scenery_tiles(self):
        d = self.open_dialog()
        self.assertTrue(all(t.playing for t in d.scenery.picker.tiles))
        d.forest.animations.buttons["off"].click()
        Q.settle()
        self.assertFalse(any(t.playing for t in d.scenery.picker.tiles))
        done_saves(self, d, {"animations": False})


class MovingTilesTests(QtCase):
    movies = True

    def test_the_tiles_in_view_move_and_stop_once_animation_is_off(self):
        d = self.open_dialog()
        moving = [t for t in d.scenery.picker.tiles if t.movie is not None]
        self.assertTrue(moving, "no scenery has a moving picture")
        running = Q.QtGui.QMovie.MovieState.Running
        self.assertTrue(any(t.movie.state() == running for t in moving))
        self.assertFalse(any(t.movie.state() == running for t in moving if not t.isVisible()))
        d.forest.animations.buttons["off"].click()
        Q.settle()
        self.assertFalse(any(t.movie.state() == running for t in moving))
        self.tab(d, "Forest")  # (out of sight: none moves, even with animation back on)
        d.forest.animations.buttons["on"].click()
        Q.settle()
        self.assertFalse(any(t.movie.state() == running for t in moving))
        self.tab(d, "Scenery")
        self.assertTrue(any(t.movie.state() == running for t in moving))

    def test_animation_can_follow_the_system(self):
        d = self.open_dialog({"animations": False})
        d.forest.animations.buttons["system"].click()
        done_saves(self, d, {"animations": "system"})

    def test_the_planting_message(self):
        d = self.open_dialog()
        d.forest.planting.click()
        done_saves(self, d, {"planting_tooltip": False})

    def test_the_phone_box_makes_and_takes_away_the_phones_deck_as_it_is_clicked(self):
        d = self.open_dialog()
        d.forest.phone.click()
        d.forest.phone.click()
        self.assertEqual(self.phone_calls, [True, False])
        done_saves(self, d, {})  # (not the add-on's config: the note in the collection is the switch)


class HeatmapTabTests(QtCase):
    def test_where_the_heatmap_shows_and_its_week(self):
        d = self.open_dialog()
        h = d.heatmap
        h.week.buttons["sunday"].click()
        h.calendar_main.click()
        done_saves(self, d, {"calendar_week_start": "sunday", "calendar_main": False})

    def test_the_week_and_the_look_grey_out_with_the_heatmap_shown_nowhere(self):
        d = self.open_dialog()
        h = d.heatmap
        h.calendar_main.click()
        h.calendar_decks.click()
        Q.settle()
        self.assertFalse(h.week.isEnabled())
        self.assertFalse(h.colours_group.isEnabled())
        self.assertFalse(h.tiles_group.isEnabled())
        h.calendar_decks.click()
        Q.settle()
        self.assertTrue(h.week.isEnabled())
        self.assertTrue(h.colours_group.isEnabled())

    def test_the_week_starts_on_the_arrow_keys_too(self):
        d = self.open_dialog()
        week = d.heatmap.week
        self.tab(d, "Heatmap")
        week.buttons["system"].setFocus()
        self.press(week.buttons["system"], Qt.Key.Key_Right)
        self.assertEqual(week.currentData(), "monday")
        self.press(week.buttons["monday"], Qt.Key.Key_Left)
        self.press(week.buttons["system"], Qt.Key.Key_Left)  # (the first: nowhere further)
        self.assertEqual(week.currentData(), "system")
        done_saves(self, d, {})

    def test_leaving_out_the_earlier_reviews_counts_the_streak_from_the_start_date(self):
        d = self.open_dialog()
        h = d.heatmap
        h.record.click()
        Q.settle()
        self.assertFalse(h.streak_from.isEnabled())
        self.assertTrue(h.streak_from.currentData())  # (shown as it counts, your own pick kept)
        Q.let_save()
        self.assertEqual(saved(), {"calendar_record": False})
        h.record.click()
        Q.settle()
        self.assertTrue(h.streak_from.isEnabled())
        self.assertFalse(h.streak_from.currentData())
        h.streak_from.buttons[True].click()
        done_saves(self, d, {"streak_from_start": True})

    def test_days_off_count_from_the_day_they_are_chosen(self):
        d = self.open_dialog()
        d.heatmap.streak_week.buttons[5].click()
        done_saves(self, d, {"streak_week": 5, "streak_week_since": addon.scope.anki_today().isoformat()})

    def test_days_off_kept_as_they_were_keep_their_day(self):
        d = self.open_dialog({"streak_week": 6, "streak_week_since": "2026-09-01"})
        d.heatmap.streak_week.buttons[5].click()
        d.heatmap.streak_week.buttons[6].click()
        done_saves(self, d, {"streak_week": 6, "streak_week_since": "2026-09-01"})

    def test_every_day_again_forgets_the_day_off_started(self):
        d = self.open_dialog({"streak_week": 6, "streak_week_since": "2026-09-01"})
        d.heatmap.streak_week.buttons[7].click()
        done_saves(self, d, {})

    def test_a_ready_colour(self):
        d = self.open_dialog()
        d.heatmap.look.ready["flame"].click()
        Q.settle()
        self.assertEqual(d.heatmap.look.source.currentData(), "ready:flame")
        done_saves(self, d, {"calendar_colours": "ready:flame"})

    def test_your_own_colour_from_the_colour_picker(self):
        look = addon.s_heatmap_look
        asked = []

        class Picker:
            @staticmethod
            def getColor(initial, parent, title):
                asked.append((initial.name(), title))
                return QColor("#AA3311")
        was = look.QColorDialog
        look.QColorDialog = Picker
        self.addCleanup(setattr, look, "QColorDialog", was)
        d = self.open_dialog()
        lc = d.heatmap.look
        self.assertFalse(lc.second.isEnabled())  # (no blend: the second colour greyed out)
        lc.first.click()
        Q.settle()
        self.assertEqual(asked, [("#2a9d8f", "Your colour")])
        self.assertEqual(lc.source.currentData(), "mine")
        done_saves(self, d, {"calendar_colours": "mine", "calendar_mine": ["#aa3311", "#e9c46a"]})

    def test_a_cancelled_colour_picker_changes_nothing(self):
        look = addon.s_heatmap_look
        was = look.QColorDialog
        look.QColorDialog = type("Picker", (), {"getColor": staticmethod(lambda *a: QColor())})
        self.addCleanup(setattr, look, "QColorDialog", was)
        d = self.open_dialog()
        d.heatmap.look.first.click()
        done_saves(self, d, {})

    def test_blend_into_a_second_colour(self):
        d = self.open_dialog()
        lc = d.heatmap.look
        lc.blend.click()
        Q.settle()
        self.assertEqual(lc.source.currentData(), "mine")
        self.assertTrue(lc.second.isEnabled())
        done_saves(self, d, {"calendar_colours": "mine", "calendar_mine_two": True})

    def test_custom_colours(self):
        d = self.open_dialog()
        d.heatmap.look.yours.click()
        done_saves(self, d, {"calendar_colours": "mine"})

    def test_a_tile_style(self):
        d = self.open_dialog()
        lc = d.heatmap.look
        lc.tile_buttons["round"].click()
        Q.settle()
        self.assertEqual(lc.tile_choice.currentData(), "round")
        self.assertTrue(lc.tile_buttons["round"].isChecked())
        self.assertFalse(lc.tile_buttons["scenery"].isChecked())
        done_saves(self, d, {"calendar_tiles": "round"})

    def test_the_scenery_button_lists_every_scenerys_colours_and_a_pick_chooses_them(self):
        menus = self.fake_menu(pick="Aurora night")
        d = self.open_dialog()
        lc = d.heatmap.look
        lc.ready["olive"].click()
        lc.scenery.click()
        Q.settle()
        self.assertEqual(len(menus), 1)
        self.assertEqual(menus[0][0], "Current scenery")
        self.assertIn("Aurora night", menus[0])
        self.assertEqual(lc.source.currentData(), "ready:aurora")
        self.assertTrue(lc.scenery.isChecked())
        self.assertFalse(lc.ready["olive"].isChecked())
        self.assertEqual(lc.scenery.text(), "Aurora night \u25be")
        done_saves(self, d, {"calendar_colours": "ready:aurora"})

    def test_the_scenery_button_without_a_pick_chooses_nothing(self):
        menus = self.fake_menu(pick=None)
        d = self.open_dialog()
        lc = d.heatmap.look
        lc.ready["olive"].click()
        lc.scenery.click()
        Q.settle()
        self.assertEqual(len(menus), 1)
        self.assertEqual(lc.source.currentData(), "ready:olive")
        self.assertFalse(lc.scenery.isChecked())
        done_saves(self, d, {"calendar_colours": "ready:olive"})

    def test_the_arrow_keys_choose_the_scenery_button_without_opening_its_list(self):
        menus = self.fake_menu(pick="Aurora")
        d = self.open_dialog()
        self.tab(d, "Heatmap")
        lc = d.heatmap.look
        lc.ready["olive"].click()
        lc.ready["olive"].setFocus()
        self.press(lc.ready["olive"], Qt.Key.Key_Left)
        self.assertEqual(menus, [])
        self.assertEqual(lc.source.currentData(), "scenery")
        self.press(lc.scenery, Qt.Key.Key_Right)
        self.assertEqual(menus, [])
        self.assertEqual(lc.source.currentData(), "ready:olive")
        done_saves(self, d, {"calendar_colours": "ready:olive"})

    def test_the_arrow_keys_go_through_the_tile_styles(self):
        d = self.open_dialog()
        self.tab(d, "Heatmap")
        lc = d.heatmap.look
        lc.tile_buttons["scenery"].setFocus()
        self.press(lc.tile_buttons["scenery"], Qt.Key.Key_Right)
        self.assertEqual(lc.tile_choice.currentData(), "flat")
        done_saves(self, d, {"calendar_tiles": "flat"})

    def fake_menu(self, pick):
        """The scenery button's list, never shown (QMenu.exec would wait for a click): what it
        lists, each time it opens, and the entry named `pick` chosen from it."""
        opened = []

        class Menu(QMenu):
            def exec(self, *_a):
                actions = [a for a in self.actions() if not a.isSeparator()]
                opened.append([a.text() for a in actions])
                for a in actions:
                    if a.text() == pick:
                        a.trigger()
        look = addon.s_heatmap_look
        was = look.QMenu
        look.QMenu = Menu
        self.addCleanup(setattr, look, "QMenu", was)
        return opened

    def test_busier_days_shows_in_dark_mode_only_and_saves(self):
        d = self.open_dialog()
        self.tab(d, "Heatmap")
        self.assertFalse(d.heatmap.look.busier_box.isVisible())
        self.cancel(d)
        Q.theme.night_mode = True
        d = self.open_dialog()
        self.tab(d, "Heatmap")
        self.assertTrue(d.heatmap.look.busier_box.isVisible())
        d.heatmap.look.busier.buttons["darker"].click()
        done_saves(self, d, {"calendar_busier": "darker"})

    def test_a_seasonal_tile_style_out_of_its_week_shows_as_scenery(self):
        d = self.open_dialog({"calendar_tiles": "pumpkin"})
        lc = d.heatmap.look
        self.tab(d, "Heatmap")
        self.assertFalse(lc.tile_buttons["pumpkin"].isVisible())
        self.assertEqual(lc.tile_choice.currentData(), "scenery")
        self.assertTrue(lc.tile_buttons["scenery"].isChecked())
        done_saves(self, d, {})

    def test_a_seasonal_tile_style_in_its_week_is_offered_and_kept(self):
        cfg = {"debug": True, "debug_date": "2026-10-28", "calendar_tiles": "pumpkin"}
        d = self.open_dialog(cfg)
        lc = d.heatmap.look
        self.tab(d, "Heatmap")
        self.assertTrue(lc.tile_buttons["pumpkin"].isVisible())
        self.assertEqual(lc.tile_choice.currentData(), "pumpkin")
        done_saves(self, d, {"debug_date": "2026-10-28", "calendar_tiles": "pumpkin"})

    def test_a_seasonal_tile_style_falls_back_to_scenery_when_the_debug_date_leaves_its_week(self):
        d = self.open_dialog({"debug": True, "debug_date": "2026-10-28", "calendar_tiles": "pumpkin"})
        d.debug.date.setDate(QDate(2026, 11, 5))
        Q.settle()
        lc = d.heatmap.look
        self.assertEqual(lc.tile_choice.currentData(), "scenery")
        self.done(d)
        self.assertNotIn("calendar_tiles", saved())

    def test_a_seasonal_scenerys_colours_out_of_its_week_are_the_scenerys(self):
        d = self.open_dialog({"calendar_colours": "ready:pumpkin_patch"})
        self.assertEqual(d.heatmap.look.source.currentData(), "scenery")

    def test_the_debug_switches_save_only_where_they_differ_from_the_style(self):
        d = self.open_dialog({"debug": True})
        lc = d.heatmap.look
        lc.tile_buttons["flat"].click()
        Q.settle()
        smooth = lc.smooth.isChecked()
        lc.smooth.click()
        Q.let_save()
        self.assertEqual(Q.current()["debug_smooth"], not smooth)
        lc.tile_buttons["round"].click()  # (a style picked: its own corners back)
        done_saves(self, d, {"calendar_tiles": "round"})


class DecksTabTests(QtCase):
    def test_the_decks_are_listed_without_the_filtered_one(self):
        d = self.open_dialog()
        self.assertEqual(sorted(d.decks.items), [1, 10, 11, 20])
        self.assertTrue(all(i.checkState(0) == Qt.CheckState.Checked for i in d.decks.items.values()))

    def test_unticking_a_deck_leaves_it_out(self):
        d = self.open_dialog()
        self.toggle_deck(d, 20)
        done_saves(self, d, {"excluded_decks": [20]})

    def test_a_deck_left_out_greys_out_its_subdecks_which_keep_their_own_choice(self):
        d = self.open_dialog()
        items = d.decks.items
        self.toggle_deck(d, 10)
        self.assertEqual(items[11].checkState(0), Qt.CheckState.Unchecked)
        self.assertTrue(items[11].isDisabled())
        self.toggle_deck(d, 10)
        self.assertEqual(items[11].checkState(0), Qt.CheckState.Checked)
        self.assertFalse(items[11].isDisabled())
        done_saves(self, d, {})

    def test_ticking_a_deck_back_in(self):
        d = self.open_dialog({"excluded_decks": [1, 20]})
        self.assertEqual(d.decks.items[20].checkState(0), Qt.CheckState.Unchecked)
        self.toggle_deck(d, 20)
        done_saves(self, d, {"excluded_decks": [1]})

    def test_a_deck_since_deleted_is_dropped_from_those_left_out(self):
        d = self.open_dialog({"excluded_decks": [20, 999]})
        done_saves(self, d, {"excluded_decks": [20]})

    def test_the_trees_are_counted_for_the_decks_ticked(self):
        d = self.open_dialog()
        Q.settle()
        self.assertIn("4 trees", d.decks.summary.text())
        self.assertEqual(d.decks.items[20].text(1), "1 tree")
        self.toggle_deck(d, 10)
        self.assertIn("1 tree", d.decks.summary.text())
        self.assertEqual(d.decks.items[10].text(1), "no trees")

    def test_a_start_date_leaves_the_days_before_it_out(self):
        d = self.open_dialog()
        Q.settle()
        dk = d.decks
        self.assertFalse(dk.since.isEnabled())
        self.assertIn("starts on your first day of study", dk.since_hint.text())
        dk.since_on.click()
        Q.settle()
        self.assertTrue(dk.since.isEnabled())
        start = addon.scope.anki_today() - datetime.timedelta(days=10)
        dk.since.setDate(QDate(start.year, start.month, start.day))
        Q.settle()
        self.assertIn("2 trees", dk.summary.text())
        self.assertIn("2 earlier ones left out", dk.summary.text())
        done_saves(self, d, {"ignore_before": start.isoformat()})

    def test_the_start_date_goes_no_later_than_today(self):
        d = self.open_dialog()
        today = addon.scope.anki_today()
        self.assertEqual(d.decks.since.maximumDate().toPyDate(), today)

    def test_suspended_cards(self):
        d = self.open_dialog()
        d.decks.keep_suspended.click()
        done_saves(self, d, {"keep_suspended": False})


class DebugTabTests(QtCase):
    def test_the_debug_tabs_settings_round_trip(self):
        d = self.open_dialog({"debug": True})
        g = d.debug
        g.test.click()
        g.trees_box.setValue(300)
        g.big.click()
        g.heatmap_width.setValue(70)
        done_saves(self, d, {"test_forest": True, "test_trees": 300, "debug_big_days": True, "debug_heatmap_width": 70})

    def test_without_debug_its_settings_are_kept_for_next_time(self):
        cfg = {"test_forest": True, "test_trees": 300, "debug_date": "2026-12-20"}
        d = self.open_dialog(cfg)
        d.forest.planting.click()
        done_saves(self, d, dict(cfg, planting_tooltip=False))

    @needs_editions
    def test_pretending_to_be_the_base_edition_offers_only_its_sceneries(self):
        d = self.open_dialog({"debug": True})
        everything = set(d.scenery.scenery_choices())
        d.debug.edition.setCurrentIndex(d.debug.edition.findData("base"))
        Q.settle()
        offered = set(d.scenery.scenery_choices())
        self.assertLess(offered, everything)
        self.assertLessEqual(offered, addon.edition.edition_presets("base"))
        self.assertTrue(any(t.locked for t in d.scenery.picker.tiles))
        self.done(d)
        self.assertEqual(saved()["debug_edition"], "base")

    def test_a_debug_date_in_a_holidays_week_offers_its_scenery(self):
        d = self.open_dialog({"debug": True, "debug_date": "2026-09-19"})
        self.assertNotIn("pumpkin_patch", d.scenery.scenery_choices())
        d.debug.date.setDate(QDate(2026, 10, 28))
        Q.settle()
        self.assertIn("pumpkin_patch", d.scenery.scenery_choices())


class WhatsNewTests(QtCase):
    def tags(self, settings=(), tiles=None):
        news = addon.news
        for name, value in (("setting_tags", lambda _cfg, _day: list(settings)), ("tile_tags", lambda _cfg, _day: dict(tiles or {}))):
            was = getattr(news, name)
            setattr(news, name, value)
            self.addCleanup(setattr, news, name, was)

    def test_a_new_setting_wears_new(self):
        self.tags(settings=["animations", "planting_tooltip", "finished_decks"])
        d = self.open_dialog()
        tagged = pills(d.forest)
        self.assertEqual(len(tagged), 3)
        self.assertTrue(d.forest.planting.property("af_new"))
        self.assertTrue(d.forest.finished.property("af_new"))
        self.assertTrue(d.forest.animations.property("af_new"))
        self.assertEqual(pills(d.heatmap), [])

    def test_a_new_group_wears_new_on_its_title(self):
        self.tags(settings=["calendar_colours"])
        d = self.open_dialog()
        self.assertIn("NEW", d.heatmap.colours_group.title.text())

    def test_a_whole_new_tab_wears_new_on_its_name_only(self):
        self.tags(settings=["calendar"])
        d = self.open_dialog()
        i = d.tabs.indexOf(d.pages[d.heatmap])
        self.assertTrue(d.tabs.tabText(i).startswith("Heatmap "))
        self.assertTrue(d.tabs.tabBar().property("af_new_tab"))
        self.assertNotIn("NEW", d.heatmap.layout_group.title.text())
        for i in range(d.tabs.count()):  # (the pill stays put as the tabs change)
            d.tabs.setCurrentIndex(i)
            Q.settle()

    def test_a_setting_the_dialog_lacks_is_passed_over(self):
        self.tags(settings=["no_such_setting"])
        d = self.open_dialog()
        self.assertEqual(pills(d), [])

    def test_new_and_improved_sceneries_wear_their_tags_until_picked(self):
        self.tags(tiles={"aurora": "new", "bamboo": "improved"})
        d = self.open_dialog()
        self.assertEqual(d.scenery.picker.new_keys, {"aurora"})
        self.assertEqual(d.scenery.picker.improved_keys, {"bamboo"})
        self.assertTrue(tile(d, "aurora").new)
        self.assertTrue(tile(d, "bamboo").improved)
        tried = []
        was = addon.news.tried
        addon.news.tried = tried.append
        self.addCleanup(setattr, addon.news, "tried", was)
        tile(d, "aurora").click()
        Q.settle()
        self.assertEqual(tried, ["aurora"])

    def test_a_notes_button_opens_its_setting_tagged_new(self):
        d = self.open_dialog(focus="keep_suspended")
        self.assertEqual(d.tab_key(), "decks")
        self.assertTrue(d.decks.keep_suspended.property("af_new"))

    def test_a_notes_button_into_customize_opens_customize(self):
        d = self.open_dialog(focus="landmark")
        self.assertEqual(d.tab_key(), "scenery")
        self.assertTrue(d.scenery.customizing())

    def test_a_notes_button_for_a_whole_new_tab_tags_its_name_not_a_group(self):
        d = self.open_dialog(focus="calendar")
        self.assertEqual(d.tab_key(), "heatmap")
        self.assertNotIn("NEW", d.heatmap.layout_group.title.text())


if __name__ == "__main__":
    unittest.main()


DAILY = dict.fromkeys(("environment", "landscape", "landmark", "weather", "time_of_day"), "daily")


class SurpriseTests(QtCase):
    """Surprise me daily's sceneries: a page in the tiles' place, each scenery it takes turns
    with ticked, or unticked to leave it out."""

    def open_page(self, config=None):
        d = self.open_dialog(dict(DAILY, **(config or {})))
        d.scenery.surprise_link.on_click()
        Q.settle()
        return d, d.scenery.surprise

    @staticmethod
    def surprise_tile(page, key):
        return next(t for t in page.picker.tiles if t.preset.key == key)

    def test_the_link_shows_only_while_surprise_me_is_chosen(self):
        d = self.open_dialog()
        link = d.scenery.surprise_link
        self.assertFalse(link.isVisible())
        tile(d, "daily").click()
        Q.settle()
        self.assertTrue(link.isVisible())
        self.assertTrue(link.isEnabled())

    def test_unticking_a_scenery_leaves_it_out_and_the_link_counts_it(self):
        d, page = self.open_page()
        sc = d.scenery
        self.assertEqual(sc.stack.currentIndex(), 2)
        self.assertFalse(sc.picker.search.isVisible())
        every = len(page.offered)
        self.assertIn(f"(all {every})", sc.surprise_link.text())
        self.assertNotIn("daily", page.offered)
        self.assertFalse(any(addon.presets.by_key()[k].season for k in page.offered))
        self.surprise_tile(page, "synthwave").click()
        Q.let_save()
        self.assertEqual(saved(), dict(DAILY, surprise_left_out=["synthwave"]))
        self.assertIn(f"({every - 1} of {every})", sc.surprise_link.text())
        self.assertEqual(page.note.text(), addon.settings.surprise_page.NOTE)
        self.surprise_tile(page, "synthwave").click()  # (ticked again)
        Q.settle()
        done_saves(self, d, DAILY)

    def test_the_last_ticked_scenery_stays_ticked(self):
        _d, page = self.open_page()
        for t in page.picker.tiles:
            t.click()
        Q.settle()
        self.assertEqual(page.picker.ticked(), [page.picker.tiles[-1].preset.key])
        self.assertEqual(page.note.text(), addon.s_surprise_page.ONE_LEFT)
        page.picker.tiles[-1].click()
        Q.settle()
        self.assertEqual(len(page.picker.ticked()), 1)

    def test_the_tiles_are_one_tab_stop_with_arrows_between_them_and_space_ticks(self):
        from PyQt6.QtTest import QTest
        d, page = self.open_page()
        tiles = page.picker.tiles
        stops = [t for t in tiles if t.focusPolicy() == Qt.FocusPolicy.StrongFocus]
        self.assertEqual(stops, [tiles[0]])
        tiles[0].setFocus()  # (offscreen the window is never active: focusWidget() says where the focus is)
        self.press(tiles[0], Qt.Key.Key_Right)
        self.assertIs(d.focusWidget(), tiles[1])
        self.assertEqual([t for t in tiles if t.focusPolicy() == Qt.FocusPolicy.StrongFocus], [tiles[1]])
        self.press(tiles[1], Qt.Key.Key_Left)
        self.assertIs(d.focusWidget(), tiles[0])
        QTest.keyClick(tiles[0], Qt.Key.Key_Space)
        Q.settle()
        self.assertFalse(tiles[0].isChecked())
        self.assertIn(tiles[0].preset.key, page.left_out)

    def test_back_goes_to_the_tiles(self):
        d, page = self.open_page()
        page.back.on_click()
        Q.settle()
        self.assertEqual(d.scenery.stack.currentIndex(), 0)
        self.assertTrue(d.scenery.picker.isVisible())

    def test_cancel_puts_the_list_back(self):
        d, page = self.open_page({"surprise_left_out": ["aurora"]})
        self.assertFalse(self.surprise_tile(page, "aurora").isChecked())
        self.surprise_tile(page, "synthwave").click()
        self.surprise_tile(page, "aurora").click()
        Q.let_save()
        self.assertEqual(saved()["surprise_left_out"], ["synthwave"])
        self.cancel(d)
        self.assertEqual(saved(), dict(DAILY, surprise_left_out=["aurora"]))

    def test_one_left_out_that_this_copy_lacks_is_kept(self):
        d, page = self.open_page({"surprise_left_out": ["not_here"]})
        self.surprise_tile(page, "synthwave").click()
        done_saves(self, d, dict(DAILY, surprise_left_out=["not_here", "synthwave"]))

    def test_restore_defaults_resets_it(self):
        from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox
        d = self.open_dialog(dict(DAILY, surprise_left_out=["synthwave"]))

        def choose(box):
            self.assertIn("Surprise me daily's sceneries", box.informativeText())
            next(b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole).click()
        Q.answer_modal(choose)
        self.button(d, QDialogButtonBox.StandardButton.RestoreDefaults).click()
        Q.settle()
        self.assertEqual(saved(), {})
        self.assertEqual(self.dialog.scenery.surprise.left_out, set())

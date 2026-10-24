"""The settings dialog itself: its tabs, and saving. Every change is saved and redrawn
immediately, so the forest behind the dialog doubles as the preview; Cancel puts
everything back, Restore defaults included. The tabs each live in a file of their own."""

from __future__ import annotations

import math

from aqt import gui_hooks, mw
from aqt.qt import QDialog, QDialogButtonBox, QEvent, QGuiApplication, QMessageBox, QTabWidget, QTimer, QVBoxLayout

from .. import i18n, news, presets
from ..edition import debug_available, debug_edition, debug_language, is_plus
from ..events import NATURE_LABELS, nature_level
from ..i18n import N_, t, tx
from ..seasons import offer_day, today
from . import whats_new
from .about import AboutTab
from .decks import DecksTab
from .forest_tab import ForestTab
from .heatmap_tab import HeatmapTab
from .scenery_picker import ROW_H, ROWS_FEWEST, ROWS_SHOWN
from .scenery_tab import SceneryTab
from .widgets import Scrolled, follow_direction, mirror

DIALOG_MIN_WIDTH = 460
# the Debug tab's timeline buttons need more room than the dialog's usual width
DEBUG_MIN_WIDTH = 760
# the dialog saves this long after the last change, so dragging a slider is one redraw
APPLY_DEBOUNCE_MS = 250
# a new city is looked up in the background; check back for a problem after this long
CITY_RECHECK_MS = 4000
# room for the window's title bar, which the dialog's own size leaves out (Windows' is the taller)
TITLE_BAR = 32
SHRINK_TRIES = 5
SHOW_WHOLE_TRIES = 3  # turns of the event loop a scrolling tab may take to measure its help
# choices about your study data rather than the forest's look: Restore defaults keeps them (and the
# phone switch, which lives in the collection, it never touches)
DATA_KEYS = ("excluded_decks", "ignore_before", "keep_earlier_trees", "keep_suspended", "calendar_record", "streak_from_start",
             "streak_week", "streak_week_since")
# set on the heatmap itself (its Reviews | Time toggle, its Timeline | By year | Streak switch), maybe while
# the dialog is open: saved as it is now, never as the dialog found it, and Cancel leaves it be (the
# view had a row here too until 2026-10-16: the switch on the heatmap is where it is changed)
OUTSIDE_KEYS = ("calendar_shade", "calendar")


RESTORE_TITLE = N_("settings.dialog.restore_defaults")
RESTORE_BUTTON = N_("settings.dialog.restore_defaults_2")  # (it asks first)
RESTORE_QUESTION = N_("settings.dialog.put_the_settings_back_to_their")
RESTORE_NOTE = N_("settings.dialog.resets_the_scenery_customize_and_surprise")  # (one key: {nature} is a Nature level's name)
# the tab the dialog was left on, for the next time it opens while Anki is: kept in memory
# only, so Anki starts again on the Scenery tab (not the config either: it is no setting)
_last_tab = ""
# the tabs as an older note's button named them
OLD_TAB_KEYS = {"general": "scenery", "fine": "scenery", "history": "decks"}


def restore_note(defaults: dict) -> str:
    """What Restore defaults asks before it does anything: what it resets, and what it keeps
    (DATA_KEYS)."""
    return tx(RESTORE_NOTE, nature=tx(NATURE_LABELS[nature_level(defaults.get("nature"))]))


class NoDebugTab:
    """What stands in for the Debug tab while debug is off (or in a release, which ships
    without it - see dev/package.py): nothing to show and nothing changed, so the debug
    settings the config holds are kept as they are, waiting for next time."""

    def connect(self, _changed) -> None:
        pass

    def sync(self) -> None:
        pass

    def values(self) -> dict:
        return {}

    def offer_news(self, _targets) -> None:
        pass


def debug_tab(cfg: dict):
    """The Debug tab while debug is on and this copy has it (edition.debug_available); NoDebugTab otherwise."""
    if not debug_available(cfg):
        return NoDebugTab()
    from .debug import DebugTab
    return DebugTab(cfg)


class SettingsDialog(QDialog):
    def __init__(self, module: str, on_change, on_phone, reopen, parent=None, focus: str = "", carry: dict | None = None):
        """`carry`: what a dialog Restore defaults (or a theme switch) closed hands on to the one
        it opens - the settings and phone as the first dialog found them, for Cancel to put back,
        and after a theme switch its place on the screen."""
        super().__init__(parent or mw)
        self.module = module
        self.on_change, self.on_phone = on_change, on_phone
        self.reopen = reopen
        cfg = dict(mw.addonManager.getConfig(module) or {})
        i18n.set_override(debug_language(cfg))  # (the Debug tab's Language, read on opening)
        # the dialog reads the way its words do, not as Anki's own language does: a right-to-left one
        # (Hebrew, Arabic...) in an English Anki right to left, an English one in a right-to-left Anki
        # left to right (its children follow)
        follow_direction(self)
        carry = carry or {}
        # what this dialog's changes are saved on top of (the keys no tab holds, such as debug's
        # while its tab is hidden), and what Cancel puts back: the same, unless Restore defaults
        # reopened it, when Cancel goes back to before Restore
        self.opened = cfg
        self.original = dict(carry.get("original", cfg))
        self.setWindowTitle("Memory Forest Plus" if is_plus() else "Memory Forest")  # (the add-on's name)
        self.setMinimumWidth(DIALOG_MIN_WIDTH)

        # opening the settings answers the cog's dot: the new sceneries wear NEW, and the
        # improved ones IMPROVED, until each is picked or two weeks go by (news.tile_tags)
        tags = news.tile_tags(cfg, today(cfg))
        self.scenery = SceneryTab(cfg, [k for k, t in tags.items() if t == "new"], [k for k, t in tags.items() if t == "improved"])
        self.custom = self.scenery.custom
        self.heatmap = HeatmapTab(cfg)
        self.forest = ForestTab(cfg, on_phone, carry.get("phone_was"))
        self.decks = DecksTab(cfg, self.original)
        # the made-up test forest and the event switches are a developer's tool: their tab is
        # only there while debug is on (its values are still kept, so they wait for next time)
        self.debug = debug_tab(cfg)
        shown = [(self.scenery, t("settings.dialog.scenery")), (self.forest, t("settings.dialog.forest")),
                 (self.heatmap, t("settings.dialog.heatmap")), (self.decks, t("settings.dialog.decks"))]
        if not isinstance(self.debug, NoDebugTab):
            self.setMinimumWidth(DEBUG_MIN_WIDTH)
            shown.append((self.debug, "Debug"))  # (a developer's tool: stays English)
        self.debug.offer_news(self.news_targets())
        # (the dialog's own timer, as below: a closed dialog is never called back)
        self._whole = QTimer(self); self._whole.setSingleShot(True); self._whole.setInterval(0)
        self._whole.timeout.connect(self._show_whole_step)
        self._whole_tries = 0
        tabs = self.tabs = QTabWidget()
        tabs.currentChanged.connect(self._show_whole)
        self.about = AboutTab()
        # the Forest, Heatmap and Debug tabs scroll on a screen too short for them (widgets.Scrolled);
        # the others fit (Scenery by showing fewer rows of tiles: fit_screen)
        # (the Heatmap tab, the longest, asks for no more than Forest: shown, the dialog grows to
        # show it whole where the screen has room, _show_whole, rather than every tab being as tall)
        self.pages = {self.forest: Scrolled(self.forest)}
        self.pages[self.heatmap] = Scrolled(self.heatmap, cap=lambda: self.pages[self.forest].sizeHint().height())
        if not isinstance(self.debug, NoDebugTab):
            # (the Debug tab, the longest by far, asks for no more than Forest either, and never grows
            # the dialog when shown: the dialog is as tall with debug on as without, Debug scrolls)
            self.pages[self.debug] = Scrolled(self.debug, cap=lambda: self.pages[self.forest].sizeHint().height())
        for widget, name in shown + [(self.about, t("settings.dialog.about"))]:
            tabs.addTab(self._page(widget), name)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("settings.dialog.done"))
        # (Qt's own words are Anki's language, which the add-on's need not be: the Debug tab's, or one Anki lacks)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("settings.dialog.cancel"))
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(tx(RESTORE_BUTTON))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._debounce = QTimer(self); self._debounce.setSingleShot(True); self._debounce.setInterval(APPLY_DEBOUNCE_MS)
        self._theme_pending = False  # (a reopen for a theme switch, waiting for the hook to finish)
        self._debounce.timeout.connect(self.apply)
        self.scenery.preset.currentIndexChanged.connect(self._preset_chosen)
        self.scenery.real_sky.toggled.connect(self._real_sky_toggled)
        # the tiles move unless the forest is still (Qt can't tell what the system asks for)
        self.forest.animations.on_change(lambda: self.scenery.picker.animate(self.forest.animations.currentData() != "off"))
        for tab in (self.scenery, self.forest, self.heatmap, self.decks, self.debug):
            tab.connect(self._changed)
        # the dialog's own timer, so a closed (and deleted) dialog is never called back
        self._city_check = QTimer(self); self._city_check.setSingleShot(True); self._city_check.setInterval(CITY_RECHECK_MS)
        self._city_check.timeout.connect(self._sync)
        self.finished.connect(self._release)
        self.scenery.city.editingFinished.connect(self._city_check.start)
        self._reverting = True  # Cancel and shutdown put the old config back; Restore defaults must not
        self._sync()
        # lay the tabs out once before the dialog is first shown, so the tabs can measure the
        # room their longest help needs, and the dialog opens that big
        # the tab it was left on last time, unless a note's button points somewhere (first, so
        # the dialog is sized for the page it opens on: Customize is shorter than the tiles)
        self.show_tab(_last_tab)
        # a new feature's settings wear NEW for a while after the update (news.setting_tags)
        targets = self.news_targets()
        for key in news.setting_tags(cfg, today(cfg)):
            if key in targets:
                tab = targets[key][0]
                # (a whole new tab wears NEW on its name only, not on its first group too)
                if key in getattr(tab, "new_tab_keys", ()):
                    whats_new.tag_tab(self.tabs, self.tabs.indexOf(self._page(tab)))
                else:
                    whats_new.tag(tab, targets[key][1])
        self.show_news(focus)
        # right to left, the labels' lines start on the right whatever their words (mirror), and
        # again for what a tab makes as it is shown
        mirror(self)
        tabs.currentChanged.connect(lambda _i: mirror(self))
        self.layout().activate()
        self.fit_screen()
        self.adjustSize()
        if carry.get("geometry") is not None:  # (opened again for a theme switch: where it was)
            self.restoreGeometry(carry["geometry"])
        # (Anki 2.1.45-2.1.49 have no theme_did_change: their theme changes only on a restart)
        if hasattr(gui_hooks, "theme_did_change"):
            gui_hooks.theme_did_change.append(self._theme_changed)

    def fit_screen(self) -> None:
        """On a screen too short for the dialog, the scenery picker shows fewer rows of tiles
        (half a row at a time, down to ROWS_FEWEST), so Done and Cancel stay on it."""
        room = self._room()
        if room is None:
            return
        # the dialog as tall as its tallest tab asks (a scrolling one, widgets.Scrolled, at its full
        # height: Qt's own sizing stops at two thirds of the screen), up to the screen's height
        QTimer.singleShot(0, lambda: self.resize(self.width(), max(self.minimumHeight(), min(room, self.sizeHint().height()))))
        over = self.minimumSizeHint().height() - room
        if over <= 0:
            return
        halves = math.ceil(over / (ROW_H / 2))
        rows = max(ROWS_FEWEST, ROWS_SHOWN - halves / 2)
        need = self.minimumSizeHint().height() - round((ROWS_SHOWN - rows) * ROW_H)
        self.scenery.picker.set_rows(rows)
        self.scenery.surprise.picker.set_rows(rows)  # (Surprise me daily's sceneries, in the tiles' place)
        # Qt takes a turn or two of the event loop to lower the dialog's minimum; until then it
        # won't get shorter
        self._shrink_to(need, SHRINK_TRIES)

    def _room(self) -> int | None:
        """The dialog's height on this screen at most (its title bar left out), or None if Qt
        can't say which screen."""
        holder = self.parent()
        screen = holder.screen() if holder is not None and hasattr(holder, "screen") else QGuiApplication.primaryScreen()
        return None if screen is None else screen.availableGeometry().height() - TITLE_BAR

    def _show_whole(self, *_args) -> None:
        """A scrolling tab in view (widgets.Scrolled) scrolls only on a screen too short for it:
        the dialog grows by what it would scroll, up to the screen's height. Its wrapped help
        measures itself only once the tab has its width, so this looks again after a turn or
        two of the event loop."""
        self._whole_tries = SHOW_WHOLE_TRIES
        self._whole.start()

    def _show_whole_step(self) -> None:
        page = self.tabs.currentWidget()
        if not isinstance(page, Scrolled) or page.widget() is self.debug:
            return
        over, room = page.verticalScrollBar().maximum(), self._room()
        if over > 0 and room is not None and self.height() < room:
            self.resize(self.width(), min(room, self.height() + over))
        if self._whole_tries > 0:
            self._whole_tries -= 1
            self._whole.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._show_whole()

    def _shrink_to(self, height: int, tries: int) -> None:
        if self.minimumHeight() > height and tries > 0:
            QTimer.singleShot(0, lambda: self._shrink_to(height, tries - 1))
            return
        self.resize(self.width(), max(height, self.minimumHeight()))

    def _page(self, tab):
        """What the tab widget holds for `tab`: its scrolling page (widgets.Scrolled), or the tab."""
        return self.pages.get(tab, tab)

    def tab_widgets(self) -> dict:
        return {"scenery": self.scenery, "forest": self.forest, "heatmap": self.heatmap, "decks": self.decks, "debug": self.debug, "about": self.about}

    def show_tab(self, key: str) -> bool:
        tab = self.tab_widgets().get(OLD_TAB_KEYS.get(key, key))
        if tab is None or isinstance(tab, NoDebugTab) or self.tabs.indexOf(self._page(tab)) < 0:
            return False
        self.tabs.setCurrentWidget(self._page(tab))
        return True

    def tab_key(self) -> str:
        current = self.tabs.currentWidget()
        return next((k for k, tab in self.tab_widgets().items() if self._page(tab) is current), "")

    def news_targets(self) -> dict:
        """Every setting a note can point at: key -> (its tab, the widget, its name)."""
        return {key: (tab, widget, name) for tab in (self.scenery, self.forest, self.heatmap, self.decks)
                for key, (widget, name) in tab.news_targets().items()}

    def show_news(self, focus: str) -> None:
        """Go where a note's button points (news.opens): a tab ("scenery", "forest", "heatmap",
        "decks", "about"), or a setting (news_targets), shown tagged NEW."""
        if not focus or self.show_tab(focus):
            return
        target = self.news_targets().get(focus)
        if target is None:
            return
        tab, widget, _name = target
        self.tabs.setCurrentWidget(self._page(tab))
        if hasattr(tab, "reveal"):
            tab.reveal(widget)
        if focus not in getattr(tab, "new_tab_keys", ()):  # (a new tab's NEW is on its name)
            whats_new.tag(tab, widget)
        if tab in self.pages:
            self.pages[tab].ensureWidgetVisible(widget)
        widget.setFocus()

    def _preset_chosen(self, *_args) -> None:
        """Picking a preset fills the five settings it stands for, under Customize."""
        key = self.scenery.preset.currentData()
        if key != presets.CUSTOM:
            self.custom.set_look(presets.apply(key, self.custom.look()))
        self._changed()

    def _day(self):
        """The day presets are offered for (the debug date may have moved it; None while
        debugging with no date: every seasonal preset, see seasons.offer_day)."""
        return offer_day(dict(self._current(), **self.debug.values()))

    def _real_sky_toggled(self, on: bool) -> None:
        """The real sky sets weather and time to Automatic; turning it off gives the
        preset back its own weather and hour (a clear day, for a mix of your own)."""
        if on:
            self.custom.set_look({"weather": "auto", "time_of_day": "auto"})
        else:
            spec = presets.by_key().get(self.scenery.preset.currentData())
            self.custom.set_look({"weather": spec.weather if spec else "clear", "time_of_day": spec.time if spec else "day"})
        self._changed()

    def _sync(self) -> None:
        """Put every tab back in line: the picker's scenery follows the five settings under
        Customize, and the Debug tab's date and edition decide what is offered."""
        day = self._day()
        self.scenery.offer(day, self.custom.look(), debug_edition(dict(self._current(), **self.debug.values())))
        self.about.show_news(dict(self._current(), **self.debug.values()))  # (the About tab's What's new, for that edition too)
        self.scenery.sync()
        self.forest.sync()
        key = self.scenery.preset.currentData()
        if key == presets.CUSTOM:  # (your own mix: the heatmap matches its environment's scenery)
            env = self.custom.look().get("environment")
            key = next((p.key for p in presets.FOREST_PRESETS if p.environment == env), presets.FOREST_PRESETS[0].key)
        self.heatmap.set_scenery(key, dict(self._current(), **self.scenery.values(), **self.debug.values()))
        self.heatmap.trees_kept(self.decks.since_on.isChecked() and self.decks.keep_trees.isChecked())
        self.heatmap.sync()
        self.decks.sync()
        self.debug.sync()

    def _changed(self, *_args) -> None:
        self._sync()
        self._debounce.start()

    def values(self) -> dict:
        # keep only current options, so settings from older versions don't linger
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        cfg = {k: v for k, v in self.opened.items() if k in known and k not in OUTSIDE_KEYS}
        cfg.update({k: v for k, v in self._current().items() if k in OUTSIDE_KEYS})
        for tab in (self.scenery, self.forest, self.heatmap, self.debug):
            cfg.update(tab.values())
        cfg.update(self.decks.values(self._current()))
        # anything still at its default stays unset, so a better default in a later
        # version still reaches people who never changed it
        return {k: v for k, v in cfg.items() if known.get(k, object()) != v}

    def _current(self) -> dict:
        return mw.addonManager.getConfig(self.module) or {}

    def changeEvent(self, event) -> None:
        """Back in the dialog: a deck may have been left out from its gear menu meanwhile."""
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow() and hasattr(self, "decks"):
            self.decks.reload(self._current())
        super().changeEvent(event)

    def apply(self) -> None:
        was_active = self.isActiveWindow()  # (before the redraw: it may take the focus)
        mw.addonManager.writeConfig(self.module, self.values())
        self.on_change()
        # redrawing may have brought or ended a holiday's week (the debug date moved), which
        # changes the look: show it, so the next change here doesn't write the old one back
        look = {k: self._current().get(k) for k in presets.LOOK}
        if look != self.custom.look():
            self.custom.offer(offer_day(self._current()))
            self.custom.set_look(look)
            self._sync()
        # refreshing a deck screen hands focus back to the webview, which would pull it
        # out of this dialog mid-edit. Only then: a change saved as you click elsewhere (a
        # city typed, then Anki's window clicked) leaves the focus where you put it
        if was_active:
            QTimer.singleShot(0, self._keep_focus)

    def _keep_focus(self) -> None:
        if self.isVisible() and not self.isActiveWindow() and mw.isActiveWindow():
            focused = self.focusWidget()
            self.raise_(); self.activateWindow()
            if focused:
                focused.setFocus()

    def _restore_confirmed(self, known: dict) -> bool:
        box = follow_direction(QMessageBox(self))
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tx(RESTORE_TITLE))
        box.setText(tx(RESTORE_QUESTION))
        box.setInformativeText(restore_note(known))
        restore = box.addButton(tx(RESTORE_TITLE), QMessageBox.ButtonRole.AcceptRole)
        keep = box.addButton(QMessageBox.StandardButton.Cancel)
        keep.setText(t("settings.dialog.cancel"))
        mirror(box)
        box.setDefaultButton(keep)
        box.setEscapeButton(keep)
        box.exec()
        return box.clickedButton() is restore

    def restore_defaults(self) -> None:
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        if not self._restore_confirmed(known):
            return
        self._debounce.stop()
        self._reverting = False  # closing must not write the pre-click config back
        # the kept settings as the dialog has them, a change not saved yet included (values()
        # leaves out what is at its default)
        mw.addonManager.writeConfig(self.module, {k: v for k, v in self.values().items() if k in DATA_KEYS})
        self.on_change()
        self.close()
        # the next dialog's Cancel goes back to how this one found things, as any change's would
        self.reopen(self.module, self.on_change, self.on_phone,
                    carry={"original": self.original, "phone_was": self.forest.phone_was})

    def _release(self, *_args) -> None:
        """Remember the tab it was left on, then let go of the Decks tab's tree days: the
        dialog's objects hold on to each other, so Python frees them only now and then, and
        until it did each dialog opened kept a whole collection's worth (MBs on a big one)."""
        global _last_tab
        _last_tab = self.tab_key()
        self.decks.days = None
        # (Anki's hooks aren't lists, `in` fails on them; their remove() lets a missing one pass)
        if hasattr(gui_hooks, "theme_did_change"):
            gui_hooks.theme_did_change.remove(self._theme_changed)

    def _theme_changed(self) -> None:
        """Anki's theme switched while the dialog is open. Its colours are set as it is built
        (the borders, help lines and links, the heatmap's strips, Busier days in dark mode only),
        so it opens again in its place, on the same tab: the changes kept, and Cancel still
        going back to how the first dialog found things, as after Restore defaults. It does so
        once Anki has run the hook's other callbacks: closing and opening while it is still going
        through them (its live list) would skip the one after this and run the new dialog's."""
        if not self._theme_pending:
            self._theme_pending = True
            QTimer.singleShot(0, self._reopen_in_theme)

    def _reopen_in_theme(self) -> None:
        if not self.isVisible():  # (closed meanwhile)
            return
        if self._debounce.isActive():  # (a change not saved yet)
            self._debounce.stop()
            self.apply()
        self._reverting = False  # closing must not write the pre-switch config back
        geometry = self.saveGeometry()
        self.close()
        self.reopen(self.module, self.on_change, self.on_phone,
                    carry={"original": self.original, "phone_was": self.forest.phone_was, "geometry": geometry})

    def accept(self) -> None:
        self._debounce.stop()
        self.apply()
        super().accept()

    def reject(self) -> None:
        """Cancel - and also what Anki does to this window at shutdown, so the settings
        of someone who quits with it open are put back the way Cancel would."""
        self._debounce.stop()
        if self._reverting:
            known = mw.addonManager.addonConfigDefaults(self.module) or {}
            cfg = {k: v for k, v in self.original.items() if k not in OUTSIDE_KEYS}
            cfg.update({k: v for k, v in self._current().items() if k in OUTSIDE_KEYS})
            # a deck left out or brought back from its gear menu meanwhile stays that way; only
            # what was changed here is undone
            self.decks.reload(self._current())
            if self.decks.changed_outside:
                cfg["excluded_decks"] = self.decks.cancelled()
            mw.addonManager.writeConfig(self.module, {k: v for k, v in cfg.items()
                                                      if k in known and known.get(k) != v})
            self.forest.put_phone_back()
            self.on_change()
        super().reject()

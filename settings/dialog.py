"""The settings dialog itself: its tabs, and saving. Every change is saved and redrawn
immediately, so the forest behind the dialog doubles as the preview; Cancel puts
everything back. The tabs each live in a file of their own."""

from __future__ import annotations

from aqt import mw
from aqt.qt import QDialog, QDialogButtonBox, QEvent, QTabWidget, QTimer, QVBoxLayout

from .. import presets
from ..state import debug_available, today
from .about import AboutTab
from .fine_tuning import FineTuningTab
from .general import GeneralTab
from .history import HistoryTab
from .scenery_picker import SceneryPicker

DIALOG_MIN_WIDTH = 460
# the Debug tab's timeline buttons need more room than the dialog's usual width
DEBUG_MIN_WIDTH = 760
# the dialog saves this long after the last change, so dragging a slider is one redraw
APPLY_DEBOUNCE_MS = 250
# a new city is looked up in the background; check back for a problem after this long
CITY_RECHECK_MS = 4000
# choices about your study data and your phone rather than the forest's look: Restore defaults keeps them
DATA_KEYS = ("excluded_decks", "ignore_before", "keep_suspended", "phone_forest")


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


def debug_tab(cfg: dict):
    """The Debug tab while debug is on and this copy has it (state.debug_available); NoDebugTab otherwise."""
    if not debug_available(cfg):
        return NoDebugTab()
    from .debug import DebugTab
    return DebugTab(cfg)


class SettingsDialog(QDialog):
    def __init__(self, module: str, on_change, reopen, parent=None):
        super().__init__(parent or mw)
        self.module = module
        self.on_change = on_change
        self.reopen = reopen
        self.original = dict(mw.addonManager.getConfig(module) or {})
        cfg = self.original
        self.setWindowTitle("Memory Forest settings")
        self.setMinimumWidth(DIALOG_MIN_WIDTH)

        self.general = GeneralTab(cfg)
        self.fine = FineTuningTab(cfg)
        self.history = HistoryTab(cfg)
        # the made-up test forest and the event switches are a developer's tool: their tab is
        # only there while debug is on (its values are still kept, so they wait for next time)
        self.debug = debug_tab(cfg)
        shown = [(self.general, "General"), (self.fine, "Fine-tuning"), (self.history, "History")]
        if not isinstance(self.debug, NoDebugTab):
            self.setMinimumWidth(DEBUG_MIN_WIDTH)
            shown.append((self.debug, "Debug"))
        tabs = QTabWidget()
        for widget, name in shown + [(AboutTab(), "About")]:
            tabs.addTab(widget, name)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Done")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._debounce = QTimer(self); self._debounce.setSingleShot(True); self._debounce.setInterval(APPLY_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.apply)
        self.general.preset.currentIndexChanged.connect(self._preset_chosen)
        self.general.preset.open_picker = self._open_picker
        self.general.real_sky.toggled.connect(self._real_sky_toggled)
        for tab in (self.general, self.fine, self.history, self.debug):
            tab.connect(self._changed)
        # the dialog's own timer, so a closed (and deleted) dialog is never called back
        self._city_check = QTimer(self); self._city_check.setSingleShot(True); self._city_check.setInterval(CITY_RECHECK_MS)
        self._city_check.timeout.connect(self._sync)
        self.finished.connect(self._release)
        self.general.city.editingFinished.connect(self._city_check.start)
        self._reverting = True  # Cancel and shutdown put the old config back; Restore defaults must not
        self._sync()
        # lay the tabs out once before the dialog is first shown, so the General tab can measure
        # the room its longest help needs, and the dialog opens that big
        self.layout().activate()
        self.adjustSize()

    def _preset_chosen(self, *_args) -> None:
        """Picking a preset fills the five settings it stands for, on the Fine-tuning tab."""
        key = self.general.preset.currentData()
        if key != presets.CUSTOM:
            self.fine.set_look(presets.apply(key, self.fine.look()))
        self._changed()

    def _open_picker(self) -> None:
        """The scenery picker; what it picks is chosen in the Scenery box, which fills in the
        five settings as choosing from a list would."""
        box = self.general.preset
        picker = SceneryPicker(self, self.general.scenery_choices(), box.currentData(), self._day())
        accepted = picker.exec() == QDialog.DialogCode.Accepted
        picker.deleteLater()  # a child of the dialog: kept, every picker opened stays until it closes
        if accepted:
            i = box.findData(picker.current)
            if i >= 0:
                box.setCurrentIndex(i)

    def _day(self):
        """The day the scenery is chosen for (the debug date may have moved it)."""
        return today(dict(self._current(), **self.debug.values()))

    def _real_sky_toggled(self, on: bool) -> None:
        """The real sky sets weather and time to Automatic; turning it off gives the
        preset back its own weather and hour (a clear day, for a mix of your own)."""
        if on:
            self.fine.set_look({"weather": "auto", "time_of_day": "auto"})
        else:
            spec = presets.by_key().get(self.general.preset.currentData())
            self.fine.set_look({"weather": spec.weather if spec else "clear", "time_of_day": spec.time if spec else "day"})
        self._changed()

    def _sync(self) -> None:
        """Put every tab back in line with the others: the General tab's preset follows the
        five settings on Fine-tuning, whichever tab they were changed on."""
        day = self._day()
        self.general.offer(day, self.fine.look())
        self.fine.offer(day)
        self.general.sync(self.fine.look())
        self.fine.sync()
        self.history.sync()
        self.debug.sync()

    def _changed(self, *_args) -> None:
        self._sync()
        self._debounce.start()

    def values(self) -> dict:
        # keep only current options, so settings from older versions don't linger
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        cfg = {k: v for k, v in self.original.items() if k in known}
        for tab in (self.fine, self.general, self.debug):
            cfg.update(tab.values())
        cfg.update(self.history.values(self._current()))
        # anything still at its default stays unset, so a better default in a later
        # version still reaches people who never changed it
        return {k: v for k, v in cfg.items() if known.get(k, object()) != v}

    def _current(self) -> dict:
        return mw.addonManager.getConfig(self.module) or {}

    def changeEvent(self, event) -> None:
        """Back in the dialog: a deck may have been left out from its gear menu meanwhile."""
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow() and hasattr(self, "history"):
            self.history.reload(self._current())
        super().changeEvent(event)

    def apply(self) -> None:
        mw.addonManager.writeConfig(self.module, self.values())
        self.on_change()
        # redrawing may have brought or ended a holiday's week (the debug date moved), which
        # changes the look: show it, so the next change here doesn't write the old one back
        look = {k: self._current().get(k) for k in presets.LOOK}
        if look != self.fine.look():
            self.fine.offer(today(self._current()))
            self.fine.set_look(look)
            self._sync()
        # refreshing a deck screen hands focus back to the webview, which would pull it
        # out of this dialog mid-edit
        QTimer.singleShot(0, self._keep_focus)

    def _keep_focus(self) -> None:
        if self.isVisible() and not self.isActiveWindow():
            focused = self.focusWidget()
            self.raise_(); self.activateWindow()
            if focused:
                focused.setFocus()

    def restore_defaults(self) -> None:
        self._debounce.stop()
        self._reverting = False  # closing must not write the pre-click config back
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        current = self._current()
        mw.addonManager.writeConfig(self.module, {k: current[k] for k in DATA_KEYS
                                                  if k in current and known.get(k) != current[k]})
        self.on_change()
        self.close()
        self.reopen(self.module, self.on_change)

    def _release(self, *_args) -> None:
        """Let go of the History tab's tree days as the dialog closes: the dialog's objects
        hold on to each other, so Python frees them only now and then, and until it did each
        dialog opened kept a whole collection's worth (MBs on a big one)."""
        self.history.days = None

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
            cfg = dict(self.original)
            # a deck left out or brought back from its gear menu meanwhile stays that way
            current = self._current()
            self.history.reload(current)
            if self.history.changed_outside:
                cfg["excluded_decks"] = current.get("excluded_decks") or []
            mw.addonManager.writeConfig(self.module, {k: v for k, v in cfg.items()
                                                      if k in known and known.get(k) != v})
            self.on_change()
        super().reject()

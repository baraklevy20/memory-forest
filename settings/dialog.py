"""The settings dialog itself: its tabs, and saving. Every change is saved and redrawn
immediately, so the forest behind the dialog doubles as the preview; Cancel puts
everything back. The tabs each live in a file of their own."""

from __future__ import annotations

from aqt import mw
from aqt.qt import QDialog, QDialogButtonBox, QTabWidget, QTimer, QVBoxLayout

from .. import presets
from .about import AboutTab
from .fine_tuning import FineTuningTab
from .general import GeneralTab
from .history import HistoryTab

DIALOG_MIN_WIDTH = 460
# the dialog saves this long after the last change, so dragging a slider is one redraw
APPLY_DEBOUNCE_MS = 250
# a new city is looked up in the background; check back for a problem after this long
CITY_RECHECK_MS = 4000


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
        tabs = QTabWidget()
        for widget, name in ((self.general, "General"), (self.fine, "Fine-tuning"), (self.history, "History"), (AboutTab(), "About")):
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
        self.general.real_sky.toggled.connect(self._real_sky_toggled)
        for tab in (self.general, self.fine, self.history):
            tab.connect(self._changed)
        self.general.city.editingFinished.connect(lambda: QTimer.singleShot(CITY_RECHECK_MS, self._sync))
        self._reverting = True  # Cancel and shutdown put the old config back; Restore defaults must not
        self._sync()

    def _preset_chosen(self, *_args) -> None:
        """Picking a preset fills the five settings it stands for, on the Fine-tuning tab."""
        key = self.general.preset.currentData()
        if key != presets.CUSTOM:
            self.fine.set_look(presets.apply(key, self.fine.look()))
        self._changed()

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
        self.general.sync(self.fine.look())
        self.fine.sync()
        self.history.sync()

    def _changed(self, *_args) -> None:
        self._sync()
        self._debounce.start()

    def values(self) -> dict:
        # keep only current options, so settings from older versions don't linger
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        cfg = {k: v for k, v in self.original.items() if k in known}
        for tab in (self.fine, self.general, self.history):
            cfg.update(tab.values())
        # anything still at its default stays unset, so a better default in a later
        # version still reaches people who never changed it
        return {k: v for k, v in cfg.items() if known.get(k, object()) != v}

    def apply(self) -> None:
        mw.addonManager.writeConfig(self.module, self.values())
        self.on_change()
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
        mw.addonManager.writeConfig(self.module, {})
        self.on_change()
        self.close()
        self.reopen(self.module, self.on_change)

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
            mw.addonManager.writeConfig(self.module, {k: v for k, v in self.original.items()
                                                      if k in known and known.get(k) != v})
            self.on_change()
        super().reject()

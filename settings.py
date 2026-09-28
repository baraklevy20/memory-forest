"""The forest's settings dialog. Every change is saved and redrawn immediately, so the
forest behind the dialog doubles as the preview; Cancel puts everything back.

Four tabs: General (a preset, the real sky, animation, the planting message), Fine-tuning
(the five settings a preset fills in, and the rarer ones), History (which decks and days
the forest grows from), and About."""

from __future__ import annotations

import datetime as _dt

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    Qt,
    QTabWidget,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import (
    MAX_WIDTH_DEFAULT,
    MAX_WIDTH_MAX,
    MAX_WIDTH_MIN,
    OFF_VALUES,
    TEST_TREES_DEFAULT,
    TEST_TREES_MAX,
    presets,
)
from .scene import ENVIRONMENTS, LANDMARKS, LANDSCAPES, TIME_LABELS, WEATHER_LABELS

DAILY_OPTION = (presets.DAILY, "Surprise me daily")
ENV_OPTIONS = [DAILY_OPTION] + list(ENVIRONMENTS.items())
LANDSCAPE_OPTIONS = [DAILY_OPTION] + list(LANDSCAPES.items())
LANDMARK_OPTIONS = [DAILY_OPTION] + list(LANDMARKS.items())
WEATHER_OPTIONS = [("auto", "Live weather"), DAILY_OPTION] + list(WEATHER_LABELS.items())
TIME_OPTIONS = [("auto", "Follows your clock"), DAILY_OPTION] + list(TIME_LABELS.items())
DIALOG_MIN_WIDTH = 460
WIDTH_STEP = 50
TREES_STEP, TREES_PAGE = 10, 250
# room inside a group's frame, and between its title and the frame (the title is a label
# of its own, because native styles such as macOS's set it flush on the frame)
GROUP_MARGINS = (12, 10, 12, 10)
GROUP_TITLE_GAP = 6
# the dialog saves this long after the last change, so dragging a slider is one redraw
APPLY_DEBOUNCE_MS = 250
# a new city is looked up in the background; check back for a problem after this long
CITY_RECHECK_MS = 4000
DECK_OPTIONS = [("highlight", "The main forest, with that deck's trees lit"), ("own", "Their own forest, grown from that deck"), ("off", "No forest")]

DECK_ROLE = Qt.ItemDataRole.UserRole
DATE_FORMAT = "d MMMM yyyy"
DECKS_NOTE = "Unticked decks are left out of the forest. Tick them again anytime to bring them back."
SINCE_NOTE = "The forest starts over from this day. Untick it anytime to bring the rest back."

ABOUT = """<b>This is your forest.</b><br><br>
One tree for every day you have learned new cards: today's is the seedling at the front,
and the oldest stands at the back. Trees grow as those cards settle into memory, and take
on a few yellow leaves when some of them slip. Days of reviews alone plant no tree,
but they keep yours healthy.<br><br>
Real weather comes from <a href="https://open-meteo.com/">Open-Meteo</a>."""


def _combo(options, value, fallback=None) -> QComboBox:
    """A dropdown on `value`. A value it doesn't offer (a hand edit, or one from an older
    version) shows `fallback` instead of whatever happens to be first."""
    box = QComboBox()
    for key, label in options:
        box.addItem(label, key)
    i = box.findData(value)
    if i < 0 and fallback is not None:
        i = box.findData(fallback)
    box.setCurrentIndex(max(i, 0))
    return box


def _group(title: str, layout) -> QWidget:
    """A titled group: the title, a little room, then `layout` inside a frame."""
    layout.setContentsMargins(*GROUP_MARGINS)
    frame = QGroupBox()
    frame.setLayout(layout)
    group = QWidget()
    v = QVBoxLayout(group)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(GROUP_TITLE_GAP)
    v.addWidget(QLabel(title))
    v.addWidget(frame)
    return group


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray; font-size: 11px;")
    return label


def _set(box: QComboBox, value) -> None:
    """Point a combo at a value without it announcing a change."""
    box.blockSignals(True)
    i = box.findData(value)
    if i >= 0:
        box.setCurrentIndex(i)
    box.blockSignals(False)


class SettingsDialog(QDialog):
    def __init__(self, module: str, on_change, parent=None):
        super().__init__(parent or mw)
        self.module = module
        self.on_change = on_change
        self.original = dict(mw.addonManager.getConfig(module) or {})
        cfg = self.original
        base = presets.FOREST_PRESETS[0]
        self.setWindowTitle("Memory Forest settings")
        self.setMinimumWidth(DIALOG_MIN_WIDTH)

        # --- General: the settings most people ever touch
        self.preset = _combo(presets.options(), presets.match(cfg))
        self.preset_note = _hint("")
        self.real_sky = QCheckBox("Follow the real weather and time of day")
        self.real_sky.setChecked(presets.follows_real_sky(cfg))
        self.city = QLineEdit(cfg.get("city", ""))
        self.city.setPlaceholderText("Your city, e.g. Berlin")
        self.animations = QCheckBox("Animate the forest (clouds, rain, animals)")
        self.animations.setChecked(cfg.get("animations", True) not in OFF_VALUES)
        self.planting = QCheckBox("Show a message when today's tree is planted")
        self.planting.setChecked(bool(cfg.get("planting_tooltip", True)))
        general = QWidget(); lf = QFormLayout(general)
        self.general_form = lf
        lf.addRow("Preset", self.preset)
        lf.addRow("", self.preset_note)
        lf.addRow("", self.real_sky)
        lf.addRow("City", self.city)
        self.city_status = _hint("")
        self.city_status.setStyleSheet("color: #c0392b; font-size: 11px;")
        lf.addRow("", self.city_status)
        lf.addRow("", _hint("Live weather for your city, from Open-Meteo. Without a city, only the "
                            "time of day follows your clock; the weather stays the preset's."))
        lf.addRow("", self.animations)
        lf.addRow("", self.planting)

        # --- Fine-tuning: the five settings a preset stands for, and the rarer ones
        self.environment = _combo(ENV_OPTIONS, cfg.get("environment", base.environment), base.environment)
        self.landscape = _combo(LANDSCAPE_OPTIONS, cfg.get("landscape", base.landscape), base.landscape)
        self.landmark = _combo(LANDMARK_OPTIONS, cfg.get("landmark", base.landmark), base.landmark)
        self.weather = _combo(WEATHER_OPTIONS, cfg.get("weather", base.weather), base.weather)
        self.time = _combo(TIME_OPTIONS, cfg.get("time_of_day", base.time), base.time)
        self.deck_mode = _combo(DECK_OPTIONS, cfg.get("deck_forest_mode", "highlight"), "highlight")
        self.max_width = QSpinBox(); self.max_width.setRange(MAX_WIDTH_MIN, MAX_WIDTH_MAX); self.max_width.setSingleStep(WIDTH_STEP); self.max_width.setSuffix(" px")
        try:
            self.max_width.setValue(int(cfg.get("max_width", MAX_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            self.max_width.setValue(MAX_WIDTH_DEFAULT)
        fine = QWidget(); fv = QVBoxLayout(fine)
        # the scene a preset stands for, apart from how and where the forest is shown
        ff = QFormLayout()
        ff.addRow("Environment", self.environment)
        ff.addRow("Landscape", self.landscape)
        ff.addRow("Landmark", self.landmark)
        ff.addRow("Weather", self.weather)
        ff.addRow("Time of day", self.time)
        df = QFormLayout()
        df.addRow("Deck screens", self.deck_mode)
        df.addRow("Maximum width", self.max_width)
        fv.addWidget(_group("Scene", ff))
        fv.addWidget(_group("Display", df))

        # the made-up test forest is a developer's tool: only there while debug is on
        self.debug = bool(cfg.get("debug", False))
        self.test = QCheckBox("Show a made-up test forest instead of mine")
        self.test.setChecked(bool(cfg.get("test_forest", False)))
        self.trees = QSlider(Qt.Orientation.Horizontal); self.trees.setRange(0, TEST_TREES_MAX); self.trees.setSingleStep(TREES_STEP); self.trees.setPageStep(TREES_PAGE)
        self.trees_box = QSpinBox(); self.trees_box.setRange(0, TEST_TREES_MAX); self.trees_box.setSingleStep(TREES_STEP); self.trees_box.setSuffix(" trees")
        try:
            n = max(0, min(TEST_TREES_MAX, int(cfg.get("test_trees", TEST_TREES_DEFAULT))))
        except (TypeError, ValueError):
            n = TEST_TREES_DEFAULT
        self.trees.setValue(n); self.trees_box.setValue(n)
        self.trees.valueChanged.connect(self.trees_box.setValue); self.trees_box.valueChanged.connect(self.trees.setValue)
        if self.debug:
            dv = QVBoxLayout()
            row = QHBoxLayout(); row.addWidget(self.trees); row.addWidget(self.trees_box)
            dv.addWidget(self.test); dv.addLayout(row)
            fv.addWidget(_group("Debug", dv))
        fv.addStretch(1)

        # --- History: which decks and days the forest grows from
        self.excluded = set()
        for did in cfg.get("excluded_decks") or []:
            try:
                self.excluded.add(int(did))
            except (TypeError, ValueError):
                pass
        self.decks = QTreeWidget()
        self.decks.setHeaderHidden(True)
        self._fill_decks()
        since = None
        try:
            since = _dt.date.fromisoformat(str(cfg.get("ignore_before") or ""))
        except ValueError:
            pass
        self.since_on = QCheckBox("Leave out everything before")
        self.since_on.setChecked(since is not None)
        self.since = QDateEdit()
        self.since.setCalendarPopup(True)
        self.since.setDisplayFormat(DATE_FORMAT)
        self.since.setMaximumDate(QDate.currentDate())
        self.since.setDate(QDate(since.year, since.month, since.day) if since else QDate.currentDate())
        deck_box = QVBoxLayout(); deck_box.addWidget(self.decks); deck_box.addWidget(_hint(DECKS_NOTE))
        sv = QVBoxLayout()
        since_row = QHBoxLayout(); since_row.addWidget(self.since_on); since_row.addWidget(self.since); since_row.addStretch(1)
        sv.addLayout(since_row); sv.addWidget(_hint(SINCE_NOTE))
        history = QWidget(); hv = QVBoxLayout(history)
        hv.addWidget(_group("Decks", deck_box), 1)
        hv.addWidget(_group("Start date", sv))

        # --- About
        about = QWidget(); av = QVBoxLayout(about)
        text = QLabel(ABOUT); text.setWordWrap(True); text.setTextFormat(Qt.TextFormat.RichText); text.setOpenExternalLinks(True)
        av.addWidget(text); av.addStretch(1)

        tabs = QTabWidget()
        for widget, name in ((general, "General"), (fine, "Fine-tuning"), (history, "History"), (about, "About")):
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
        self.preset.currentIndexChanged.connect(self._preset_chosen)
        self.real_sky.toggled.connect(self._real_sky_toggled)
        for box in (self.environment, self.landscape, self.landmark, self.weather, self.time, self.deck_mode):
            box.currentIndexChanged.connect(self._changed)
        for box in (self.animations, self.planting, self.test):
            box.toggled.connect(self._changed)
        self.trees_box.valueChanged.connect(self._changed)
        self.city.editingFinished.connect(self._changed)
        self.city.editingFinished.connect(lambda: QTimer.singleShot(CITY_RECHECK_MS, self._sync))
        self.max_width.valueChanged.connect(self._changed)
        self.decks.itemChanged.connect(self._deck_toggled)
        self.since_on.toggled.connect(self._changed)
        self.since.dateChanged.connect(self._changed)
        self._reverting = True  # Cancel and shutdown put the old config back; Restore defaults must not
        self._sync()

    def _fill_decks(self) -> None:
        """The deck tree, one checkbox a deck; filtered decks only borrow cards, so they
        are not in it."""
        items: dict = {}
        for deck in mw.col.decks.all_names_and_ids(include_filtered=False):
            parent, _sep, leaf = deck.name.rpartition("::")
            item = QTreeWidgetItem([leaf])
            item.setData(0, DECK_ROLE, deck.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            (items[parent] if parent in items else self.decks.invisibleRootItem()).addChild(item)
            items[deck.name] = item
        self._paint_decks()

    def _paint_decks(self) -> None:
        """Tick every deck that counts. Under an unticked one, its subdecks are unticked
        and greyed out, but each keeps its own choice for when the parent comes back."""
        def paint(item, parent_off: bool) -> None:
            off = parent_off or item.data(0, DECK_ROLE) in self.excluded
            item.setCheckState(0, Qt.CheckState.Unchecked if off else Qt.CheckState.Checked)
            item.setDisabled(parent_off)
            for i in range(item.childCount()):
                paint(item.child(i), off)
        self.decks.blockSignals(True)
        root = self.decks.invisibleRootItem()
        for i in range(root.childCount()):
            paint(root.child(i), False)
        self.decks.blockSignals(False)

    def _deck_toggled(self, item, _column) -> None:
        did = item.data(0, DECK_ROLE)
        if item.checkState(0) == Qt.CheckState.Checked:
            self.excluded.discard(did)
        else:
            self.excluded.add(did)
        self._paint_decks()
        self._changed()

    def _look_values(self) -> dict:
        return {"environment": self.environment.currentData(), "landscape": self.landscape.currentData(),
                "landmark": self.landmark.currentData(), "weather": self.weather.currentData(),
                "time_of_day": self.time.currentData()}

    def _preset_chosen(self, *_args) -> None:
        """Picking a preset fills the five settings it stands for, on the Fine-tuning tab."""
        key = self.preset.currentData()
        if key != presets.CUSTOM:
            values = presets.apply(key, self._look_values())
            for box, field in ((self.environment, "environment"), (self.landscape, "landscape"),
                               (self.landmark, "landmark"), (self.weather, "weather"), (self.time, "time_of_day")):
                _set(box, values[field])
        self._changed()

    def _real_sky_toggled(self, on: bool) -> None:
        """The real sky sets weather and time to Automatic; turning it off gives the
        preset back its own weather and hour (a clear day, for a mix of your own)."""
        if on:
            _set(self.weather, "auto"); _set(self.time, "auto")
        else:
            spec = presets.by_key().get(self.preset.currentData())
            _set(self.weather, spec.weather if spec else "clear")
            _set(self.time, spec.time if spec else "day")
        self._changed()

    def _sync(self) -> None:
        """Put the preset dropdown, its note and the real-sky box back in line with the
        five settings, whichever tab they were changed on."""
        values = self._look_values()
        key = presets.match(values)
        _set(self.preset, key)
        spec = presets.by_key().get(key)
        self.preset_note.setText(spec.note if spec else "Your own mix, from the Fine-tuning tab. Pick a preset to start from one.")
        self.real_sky.blockSignals(True)
        self.real_sky.setChecked(presets.follows_real_sky(values))
        self.real_sky.blockSignals(False)
        self.city.setEnabled(values["weather"] == "auto")
        # the last lookup of this city, if it went wrong
        from . import city_problem
        problem = city_problem(self.city.text()) if values["weather"] == "auto" else ""
        self.city_status.setText("" if not problem else
                                 "Couldn't find this city. Check the spelling, or try its English name." if problem.startswith("city not found")
                                 else "Couldn't reach the weather service; trying again soon.")
        if hasattr(self.general_form, "setRowVisible"):  # Qt 6.4+: the row takes no space while hidden
            self.general_form.setRowVisible(self.city_status, bool(problem))
        else:
            self.city_status.setVisible(bool(problem))
        self.trees.setEnabled(self.test.isChecked()); self.trees_box.setEnabled(self.test.isChecked())
        self.since.setEnabled(self.since_on.isChecked())

    def _changed(self, *_args) -> None:
        self._sync()
        self._debounce.start()

    def values(self) -> dict:
        # keep only current options, so settings from older versions don't linger
        known = mw.addonManager.addonConfigDefaults(self.module) or {}
        cfg = {k: v for k, v in self.original.items() if k in known}
        cfg.update(self._look_values())
        cfg.update({
            "city": self.city.text().strip(),
            "animations": self.animations.isChecked(),
            "planting_tooltip": self.planting.isChecked(),
            "deck_forest_mode": self.deck_mode.currentData(),
            "max_width": self.max_width.value(),
            # only decks that still exist, so a deleted one doesn't linger
            "excluded_decks": sorted(self.excluded & {d.id for d in mw.col.decks.all_names_and_ids(include_filtered=False)}),
            "ignore_before": self.since.date().toString("yyyy-MM-dd") if self.since_on.isChecked() else "",
            "test_forest": self.test.isChecked(),
            "test_trees": self.trees_box.value(),
        })
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
        open_settings(self.module, self.on_change)

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


_open: SettingsDialog | None = None


def open_settings(module: str, on_change) -> None:
    global _open
    if _open is not None and _open.isVisible():
        _open.raise_(); _open.activateWindow()
        return
    _open = SettingsDialog(module, on_change)
    _open.setWindowModality(Qt.WindowModality.NonModal)
    _open.show()

"""
Memory Forest - a passive forest that grows from your study history.

Each day you learn new cards plants one tree below the deck list. Trees grow as
those cards settle into long-term memory, and yellow a little when some of them are
forgotten. Nothing to click: the forest just grows.

This file only connects the add-on to Anki. The panel and its redraws are in panel.py,
what it is drawn from in payload.py, clicks and the deck menu in actions.py, the
planting message in planting.py, the forest for your phone in phone.py, and the config
and saved state in state.py.
"""

from __future__ import annotations

from aqt import gui_hooks, mw

from . import events_state
from .actions import on_deck_options_menu, on_js_message, open_settings, settings_changed
from .panel import on_deck_browser, on_overview
from .phone import publish as publish_for_phone
from .phone import remember_setting
from .planting import on_answer

mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css)")

gui_hooks.deck_browser_will_render_content.append(on_deck_browser)
gui_hooks.overview_will_render_content.append(on_overview)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_menu)
# no new asteroid strike until a sync has brought in the reviews from your other devices
# (these come first, so the forest for your phone below goes by them too)
gui_hooks.sync_will_start.append(events_state.sync_started)
gui_hooks.sync_did_finish.append(events_state.sync_finished)
# the forest for your phone: written before each sync, and again after one brings reviews in
gui_hooks.sync_will_start.append(publish_for_phone)
gui_hooks.sync_did_finish.append(publish_for_phone)
mw.addonManager.setConfigAction(__name__, open_settings)
mw.addonManager.setConfigUpdatedAction(__name__, lambda _cfg: settings_changed())
remember_setting()  # so that only turning the phone setting off removes its deck

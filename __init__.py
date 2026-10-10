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

from . import events_state, live_weather, news, payload
from .actions import on_deck_options_menu, on_js_message, open_settings, settings_changed
from .panel import on_deck_browser, on_overview, refresh
from .phone import after_sync as publish_after_sync
from .phone import publish as publish_for_phone
from .planting import on_answer

mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css)")

news.started()  # (before the first forest saves anything)
gui_hooks.deck_browser_will_render_content.append(on_deck_browser)
gui_hooks.overview_will_render_content.append(on_overview)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_menu)
live_weather.redraw_with(refresh)  # new weather in: the forest redrawn with it
# no asteroid strike you haven't seen until a sync has brought in the reviews from your other devices
# (these come first, so the forest for your phone below goes by them too)
gui_hooks.sync_will_start.append(events_state.sync_started)
gui_hooks.sync_did_finish.append(events_state.sync_finished)
gui_hooks.sync_did_finish.append(payload.after_sync)  # before the forest for your phone is written
# a collection opened in place of the one before (a .colpkg imported, a backup restored) has
# its path, so nothing read from the old one may be kept for it
gui_hooks.collection_did_load.append(payload.collection_loaded)
# the forest for your phone: written before each sync, and again after one brings reviews in
# (and the phone setting, as another computer may have left it)
gui_hooks.sync_will_start.append(publish_for_phone)
gui_hooks.sync_did_finish.append(publish_after_sync)
mw.addonManager.setConfigAction(__name__, open_settings)
mw.addonManager.setConfigUpdatedAction(__name__, lambda _cfg: settings_changed())

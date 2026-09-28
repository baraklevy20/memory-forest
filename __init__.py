"""
Memory Forest - a passive forest that grows from your study history.

Each day you learn new cards plants one tree below the deck list. Trees grow as
those cards settle into long-term memory, and yellow a little when some of them are
forgotten. Nothing to click: the forest just grows.

This file only connects the add-on to Anki. The panel and its redraws are in panel.py,
what it is drawn from in payload.py, clicks and the deck menu in actions.py, the
planting message in planting.py, and the config and saved state in state.py.
"""

from __future__ import annotations

from aqt import gui_hooks, mw

from .actions import on_deck_options_menu, on_js_message, open_settings
from .panel import on_deck_browser, on_overview, refresh
from .planting import on_answer

mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css)")

gui_hooks.deck_browser_will_render_content.append(on_deck_browser)
gui_hooks.overview_will_render_content.append(on_overview)
gui_hooks.reviewer_did_answer_card.append(on_answer)
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_menu)
mw.addonManager.setConfigAction(__name__, open_settings)
mw.addonManager.setConfigUpdatedAction(__name__, lambda _cfg: refresh())

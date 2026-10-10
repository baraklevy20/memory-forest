# Settings dialog guidelines

Read this before adding, moving or rewording anything in the settings dialog (`settings/`).
It comes from a review of desktop settings-dialog practice (Apple HIG, Microsoft's Windows
guidelines, GNOME and KDE HIGs, Nielsen Norman Group) against this dialog, in October 2026.

## Where things go

| Tab | Holds |
| --- | --- |
| **Scenery** | How the forest looks: the scenery picker, the real sky and its city, and Customize (the five settings a scenery stands for, opened from a link under the tiles and shown in their place). The Patreon banner stays at the top. |
| **Forest** | How it behaves and where it shows: Nature, Where it shows, Motion and messages, On your phone. |
| **Decks** | Which study counts: the decks, the start date, suspended cards. |
| **About** | Not settings: version, what's new, how it works, thanks, credits. |
| Debug | Only while debug is on; never ships. |

- Put a new setting in the tab and group whose name already says it holds it. If none
  does, name a new group for what it holds. Never add a catch-all like "Extras",
  "Advanced", "Other" or "General".
- Keep settings that depend on each other on one tab. A control on one tab must never
  silently change a control on another (this is why Customize lives on the Scenery tab).
- Tab and group names are short, specific nouns in sentence case. Keep four tabs (plus
  Debug). Before adding a fifth, try a named group, or a panel that takes another's place
  like Customize.
- Put the setting most people change first. Rare ones go lower down, or behind a link to
  a panel (progressive disclosure, never more than two levels).

## Size

- The dialog must fit a 1280 × 720 screen (a 1920 × 1080 laptop at 150%): about 672 pt of
  room, title bar included. Check `dialog.minimumSizeHint()` for every tab after a change.
- Make room without growing the tab: show a panel in another's place (Customize in the
  tiles' place) rather than unfolding it below, and put a long group's fields in two
  columns when each holds a word or two.
- A swapped panel counts only while in view, and the dialog resizes to it (as a Mac's
  Settings window does to each pane) with `widgets.resize_with`, which keeps any room the
  user added. Never leave a shorter panel padded out to the taller one's height.
- The scenery picker gives back rows first: `fit_screen` drops it from 2½ rows to as few as
  1½, half a row at a time, on a short screen. Nothing else shrinks to fit, so a new setting
  on a tall tab needs room found elsewhere.
- The picker's search sits on the Scenery group's title row, and shows only when there are
  more than `SEARCH_FROM` (12) sceneries.

## How it behaves

- Every change applies at once: the forest behind the dialog is the preview (debounced in
  `dialog.apply`). A text field applies when focus leaves it, not on each key.
- Cancel puts back everything as the dialog found it: the config, the phone deck, and even
  Restore defaults (`carry` hands the original settings to the reopened dialog). Anything
  new with a side effect outside the config must be put back on Cancel too
  (see `ForestTab.put_phone_back`).
- Restore defaults resets the look and behaviour, and keeps the study data (`DATA_KEYS`).
  A new setting about the user's data belongs in `DATA_KEYS`, and in `RESTORE_NOTE`'s list
  of what is kept. Otherwise add it to the note's list of what is reset.
- A button that asks before it acts ends in "…" (Restore defaults…). Ask first only for
  what Cancel can't undo, or for a change that sweeps across several tabs at once (Restore
  defaults: its question says what it resets and keeps, and that Cancel undoes it). Make the
  safe button the default.
- While Anki is open, the dialog reopens on the tab it was left on (kept in memory, not in
  the config or a file); after Anki restarts it opens on Scenery. It always opens with the
  tiles in view, not Customize.
- Enter means Done. A button inside a tab sets `setAutoDefault(False)`.

## Choosing a control

| The choice | Use |
| --- | --- |
| On or off, where off is the obvious opposite | `QCheckBox`, with a positive label that describes the ticked state |
| 2 to 5 options | `widgets.Choice`: radio buttons, side by side, or `vertical=True` when the labels are long |
| More than 5 options | `widgets.combo` (a dropdown) |
| A number with a unit | `QSpinBox` with a suffix (" px") |
| A visual choice | Pictures (the scenery picker, Nature's icon buttons) |

- A row of icon buttons that act as one choice (Nature) subclasses `widgets.Choice` and
  overrides `make_button`, rather than handling its own button group.
- A one-of-many choice always has one chosen: clicking the chosen option again keeps it
  (radio buttons and `QButtonGroup` do this; a custom checkable button such as a scenery
  tile overrides `nextCheckState`).
- Lay labelled rows out with `widgets.form()`, never a bare `QFormLayout`: macOS's centres
  itself and shrinks its fields.
- A control that only matters while another is on stays visible and disabled, like the
  city while the real sky is off. Hide a control only when the user can't turn it on.

## Words

- Sentence case, no full stop on labels. Phrase everything positively ("Show…", "Keep…"),
  never "Don't…" or "Disable…". Write plainly, from the user's side ("Your forest",
  "No forest"), and keep parallel rows parallel.
- A label is short. Any explanation goes on a `widgets.hint()` line under the control, in
  full sentences, only where it is needed, never as placeholder text.
- Name things by what users see (Scenery, Customize, Decks), never by how the code is built.

## Readability

- Help text uses `hint()` (12 px, `palette.HINT`). Errors use `error_style()`
  (`palette.ERROR`). Both pairs pass WCAG's 4.5:1 on Anki's light and dark windows. Never
  hard-code `gray` or a red: Anki's FG_SUBTLE and a fixed red both fall below 4.5:1 in one
  of the themes.
- Check a new colour in both themes; the dialog follows Anki's theme, not the system's.

## Decided

- Anki's native look: its own controls, with colours from its theme (`palette.color`).
  A custom skin (new colours and a pixel font) has been explored but not chosen; don't
  restyle the dialog until the maintainer picks one. If a pixel font is ever used, Pixelify
  Sans needs its ligatures off ("fi" reads as "A").
- The Patreon banner stays as it is: large, at the top of the Scenery tab. A one-line
  version was proposed twice and declined. Word it as "new scenery arrives in Plus first and
  comes to this version too", never as the free version being behind.
- The scenery is chosen from picture tiles: a click picks, Enter in the search picks the
  first match. The picker's group has no label inside it.
- "Decks" names the tab that also holds the start date and suspended cards: the deck list
  is its main content and the reason people open it.

## Pictures

- A new or changed preset needs its tile: `npm run thumbs -- <key>` writes
  `settings/scenery/<key>.png` (the tests fail while a preset lacks one), and
  `python3 dev/tile_gifs.py <key>` its moving one.
- Nature's icons come from `npm run nature-icons` (`settings/nature/*.png`).

## Qt and Anki

- Never show a widget before it has a parent: set its visibility after it is in a layout.
  Otherwise it flashes up as a window of its own and steals focus.
- Text that is clicked (a link such as "Customize … ›" or "‹ Sceneries") is a
  `widgets.Link`, a `QLabel`. Anki's style keeps a `QToolButton`'s text small whatever its
  own style sheet says. A test
  harness without Anki's style won't show this, so check new controls in Anki itself.
- A tab with wrapped help subclasses `widgets.Tab`, so the dialog makes room for the text
  and grows when it gets longer.
- A new setting a release note can point at goes in its tab's `news_targets()` (key ->
  widget, name). If it sits in a panel that isn't always shown, the tab's `reveal()` must show it.
- For a focus or layout bug that only shows by hand, add a temporary trace (for example
  `QGuiApplication.focusWindowChanged`, or the tab's sizes) and read it before guessing at
  a fix.
- To render the real dialog without a window on screen, use Anki's own Python with the
  cocoa platform, `WA_DontShowOnScreen` and
  `QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM=1`. The macOS style crashes on the
  offscreen platform. `tests/fake_anki.py` with the real `aqt.qt` swapped in gives it a
  collection. Pass config overrides to the harness, never by editing `config.json`.
- Supported Anki goes back to 2.1.45 (Qt5). After a change, run
  `python3 dev/old_anki.py --check --all` and look at the dialog in both themes.
- Every user-visible change gets its line in `release_notes.json` (then `npm run notes`).
  Update the README and `docs/ankiweb.html` where they name a tab.

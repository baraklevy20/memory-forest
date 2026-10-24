# Translating Memory Forest

Memory Forest follows your Anki's language. So far it supports German, Spanish, French, Brazilian
Portuguese, Japanese, Chinese (Simplified), Arabic and Hebrew.

I want to be fully transparent: I don't speak most of these languages, so every translation was
made with AI (Claude). It uses Anki's own words for things like decks and reviews, but no native
speaker has read it yet, and it's probably bad in places. Think of it as a decent start.

If something reads wrong or just isn't how people say it, please tell me. A single word or a whole
screen, every fix helps.

## Fixing a translation

The easiest way: find your language's review issue ([the `translation` label](../../issues?q=is%3Aissue+label%3Atranslation)),
and comment with what you saw, where, and what it should say. A screenshot helps. All it takes is a
GitHub account.

Or open a [translation correction](../../issues/new?template=translation-correction.yml) issue.

Or change it yourself in a pull request:

1. Your language's file is `locales/<language>.json` (`de.json`, `pt-BR.json`, `zh-CN.json`...).
   Each wording has an id that never changes, and its text:
   ```json
   "heatmap.n_reviews": {"text": {"one": "{n} Wiederholung", "other": "{n} Wiederholungen"}, "en": "..."}
   ```
   The English of every id is in `locales/en.json`. Grep the id in the code to see where it shows.
2. Change the `"text"`. Keep every `{placeholder}` and HTML tag (`<b>`, `<a href="{url}">`) as they
   are; move them wherever the sentence needs them. A plural has one text per form your language
   uses (`one`, `two`, `few`, `many`, `other`, `zero`, as CLDR names them).
3. Run `npm run strings -- check`, which catches a lost placeholder, a missing plural form or a typo
   in an id (CI runs it too). A wording you add that wasn't translated before needs only its
   `"text"`: `npm run strings` fills in the `"en"` it was translated from.
4. To see it, run the add-on from your clone (DEVELOPMENT.md) and set Anki to your language, or
   turn on `debug` in the add-on's config and pick the language in the settings' Debug tab.

Please use Anki's own words for Anki's things, as your language's Anki says them (they are in
[Anki's translations](https://github.com/ankitects/anki-core-i18n)), and keep labels short: the
settings dialog is tight.

## A new language

Ask for it with a [new language](../../issues/new?template=new-language.yml) issue, or add it:
copy any language's file to `locales/<your tag>.json` (the tag Anki uses for your language), replace
each `"text"`, and run `npm run strings` and `npm run strings -- check`. If your language counts in
plural forms other than English's, add its rule to `PLURAL_RULE` in `i18n.py`; if it reads right to
left, add it to `RTL` there too.

The release notes stay in English: every update ships before its notes could be translated.

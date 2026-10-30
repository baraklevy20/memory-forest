"""The words in the reader's language: Anki's own interface language, its translations from
locales/<lang>.json, and the plural forms, numbers and dates that go with them.

Every wording has an id, which never changes: `t("caption.click_to_see_their_cards")`. Its English
is in locales/en.json, and each language's file gives its translation of that id, with the English
it was translated from: an English wording changed since is still shown, and dev/strings.py lists
it to translate again. A wording a language lacks shows in English, so a language half done reads
half in English rather than not at all. Plurals are one id with a form for each number,
`tn("heatmap.n_reviews", n)`. A constant read before the language is known holds its id, marked
`N_("...")`, and is shown with `tx(CONSTANT)`. Placeholders are `{name}`, filled from the keywords;
`tn`'s {n} is the number as the language writes it ("3.581" in German).

A scenery's words have ids of their own, from its .json (its label and note): env.<key>,
landscape.<key>, landmark.<key>, preset.<key> and preset.<key>.note, heatmap_style.<key> and
heatmap_style.<key>.tip, their English read from the .json itself. The release notes stay English:
an update ships before its notes could be translated.

The page is sent only the words its scripts use (page_strings, from locales/catalog.json, which
dev/strings.py writes), the phone card the same in its synced note. Two made-up languages test it
all without a translator: en-XA ("[Ŷöûŕ ƒöŕéšţ ····]", longer, to show the English left in and what
clips) and en-XB (the same, right to left).

Nothing here imports aqt, so it also runs in the tests and the dev scripts.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re

try:
    from . import catalog as files
except ImportError:  # the tests and dev scripts import these files as top-level modules
    import catalog as files

HERE = os.path.dirname(os.path.abspath(__file__))
LOCALES = os.path.join(HERE, "locales")
ENGLISH = os.path.join(LOCALES, "en.json")
CATALOG = os.path.join(LOCALES, "catalog.json")
# the made-up languages (Debug tab, Language): longer English with accents, and the same right to left
PSEUDO, PSEUDO_RTL = "en-XA", "en-XB"
RTL = ("ar", "fa", "he", "ug", "ur", "yi", PSEUDO_RTL)
# the files under locales/ that are not a language
NOT_LANGUAGES = ("en.json", "catalog.json")

# the plural forms each language has, as CLDR names them, and which one a whole number takes;
# web/i18n.js has the same table (a Chromium as old as Anki 2.1.45's has older plural data)
PLURALS = {
    "one_other": lambda n: "one" if n == 1 else "other",
    "zero_one_other": lambda n: "one" if n in (0, 1) else "other",
    "other": lambda n: "other",
    "one_two_other": lambda n: "one" if n == 1 else "two" if n == 2 else "other",
    "slavic": lambda n: ("one" if n % 10 == 1 and n % 100 != 11 else
                         "few" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "many"),
    "polish": lambda n: ("one" if n == 1 else
                         "few" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "many"),
    "czech": lambda n: "one" if n == 1 else "few" if 2 <= n <= 4 else "other",
    "arabic": lambda n: ("zero" if n == 0 else "one" if n == 1 else "two" if n == 2 else
                         "few" if 3 <= n % 100 <= 10 else "many" if 11 <= n % 100 <= 99 else "other"),
    # Croatian, Serbian and Bosnian
    "bcs": lambda n: ("one" if n % 10 == 1 and n % 100 != 11 else
                      "few" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "other"),
    "romanian": lambda n: "one" if n == 1 else "few" if n == 0 or 2 <= n % 100 <= 19 else "other",
    "lithuanian": lambda n: ("one" if n % 10 == 1 and not 11 <= n % 100 <= 19 else
                             "few" if n % 10 >= 2 and not 11 <= n % 100 <= 19 else "other"),
    "latvian": lambda n: ("zero" if n % 10 == 0 or 11 <= n % 100 <= 19 else
                          "one" if n % 10 == 1 and n % 100 != 11 else "other"),
    "slovenian": lambda n: "one" if n % 100 == 1 else "two" if n % 100 == 2 else "few" if n % 100 in (3, 4) else "other",
    "irish": lambda n: "one" if n == 1 else "two" if n == 2 else "few" if 3 <= n <= 6 else "many" if 7 <= n <= 10 else "other",
    "welsh": lambda n: {0: "zero", 1: "one", 2: "two", 3: "few", 6: "many"}.get(n, "other"),
}
PLURAL_RULE = {
    "fr": "zero_one_other", "pt": "zero_one_other",
    "ja": "other", "zh": "other", "ko": "other", "th": "other", "vi": "other", "id": "other",
    "he": "one_two_other",
    "ru": "slavic", "uk": "slavic", "be": "slavic", "pl": "polish", "cs": "czech", "sk": "czech",
    "ar": "arabic", "hr": "bcs", "sr": "bcs", "bs": "bcs", "ro": "romanian", "lt": "lithuanian",
    "lv": "latvian", "sl": "slovenian", "ga": "irish", "cy": "welsh",
    "pt-PT": "one_other",  # (Brazil's Portuguese counts 0 as one, Portugal's doesn't)
}
# the forms a translation of a plural needs, per rule
PLURAL_FORMS = {
    "one_other": ("one", "other"), "zero_one_other": ("one", "other"), "other": ("other",),
    "one_two_other": ("one", "two", "other"), "slavic": ("one", "few", "many"),
    "polish": ("one", "few", "many"), "czech": ("one", "few", "other"),
    "arabic": ("zero", "one", "two", "few", "many", "other"),
    "bcs": ("one", "few", "other"), "romanian": ("one", "few", "other"), "lithuanian": ("one", "few", "other"),
    "latvian": ("zero", "one", "other"), "slovenian": ("one", "two", "few", "other"),
    "irish": ("one", "two", "few", "many", "other"), "welsh": ("zero", "one", "two", "few", "many", "other"),
}
# how a language groups a number's thousands (for Python's own numbers; the page uses Intl)
GROUPING = {"de": ".", "es": ".", "it": ".", "nl": ".", "pt": ".", "da": ".", "tr": ".", "id": ".",
            "fr": " ", "ru": " ", "uk": " ", "pl": " ", "cs": " ", "sk": " ",
            "sv": " ", "nb": " ", "fi": " "}

# the languages that write a decimal comma (the rest a point)
DECIMAL = dict.fromkeys(("de", "es", "it", "nl", "pt", "da", "tr", "id", "fr", "ru", "uk", "pl", "cs", "sk", "sv", "nb", "fi", "hr", "sr", "bs", "ro", "lt", "lv", "sl", "el", "hu", "be"), ",")
GROUPING.update({k: "\u00a0" for k in ("hr", "sr", "bs", "lt", "lv", "sl", "hu", "be") if k not in GROUPING})
GROUPING.update({"ro": ".", "el": "."})

_override = None  # the Debug tab's language, while debug is on ("" for Anki's)
_lang = None      # the language in use, once read
_table = None     # its words: id -> text (a string, or a plural's forms)
_english = None   # id -> English
_translations = {}  # tag -> its file's translations, once read
_web_ids = None   # the ids a page script uses, from the catalog


def anki_lang() -> str:
    """Anki's interface language as a BCP 47 tag ("de", "zh-CN", "pt-BR", "he"): current_lang
    (currentLang before about 2.1.42), "en" if it can't say."""
    try:
        import anki.lang as lang
        tag = getattr(lang, "current_lang", None) or getattr(lang, "currentLang", None)
    except Exception:
        tag = None
    return str(tag or "en").replace("_", "-")


def set_override(tag: str | None) -> None:
    """The Debug tab's Language: this one rather than Anki's ("" or None: Anki's)."""
    global _override, _lang, _table
    if (tag or None) != _override:
        _override, _lang, _table = tag or None, None, None
        _translations.clear()


def lang() -> str:
    """The language the add-on speaks: Anki's (or the Debug tab's), as a tag."""
    global _lang
    if _lang is None:
        _lang = _override or anki_lang()
    return _lang


def base(tag: str) -> str:
    return tag.split("-")[0].lower()


def candidates(tag: str) -> list:
    """The files a tag reads, most particular first: "zh-CN" reads zh-CN.json, then zh.json."""
    parts = tag.split("-")
    return ["-".join(parts[:i]) for i in range(len(parts), 0, -1)]


def available() -> list:
    """The languages there are translations for, as tags ("de", "he"), English first."""
    names = sorted(n[:-5] for n in os.listdir(LOCALES) if n.endswith(".json") and n not in NOT_LANGUAGES) \
        if os.path.isdir(LOCALES) else []
    return ["en"] + names


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def scenery_english(web: str | None = None) -> dict:
    """id -> English for the scenery this copy has, read from each one's .json."""
    web = web or files.WEB
    out = {}
    for kind, prefix in (("envs", "env"), ("landscapes", "landscape"), ("landmarks", "landmark")):
        folder = os.path.join(web, kind)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            if not name.endswith(".json"):
                continue
            spec, key = _read(os.path.join(folder, name)), name[:-5]
            if spec.get("label"):
                out[f"{prefix}.{key}"] = spec["label"]
            preset = spec.get("preset")
            if isinstance(preset, dict) and preset.get("label"):
                pk = preset.get("key", key)
                out[f"preset.{pk}"] = preset["label"]
                if preset.get("note"):
                    out[f"preset.{pk}.note"] = preset["note"]
    # the Plus sceneries the base edition's picker shows locked
    plus = os.path.join(HERE, "settings", "plus.json")
    if os.path.exists(plus):
        try:
            with open(plus, encoding="utf-8") as f:
                for spec in json.load(f):
                    out.setdefault(f"preset.{spec['key']}", spec["label"])
                    if spec.get("note"):
                        out.setdefault(f"preset.{spec['key']}.note", spec["note"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    # (and the tile styles still in the works, in web/drafts/heatmap/ where this copy has them: never collected)
    for folder in (os.path.join(web, "heatmap"), os.path.join(web, "drafts", "heatmap")):
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            if name.endswith(".json"):
                spec, key = _read(os.path.join(folder, name)), name[:-5]
                if spec.get("label"):
                    out.setdefault(f"heatmap_style.{key}", spec["label"])
                if spec.get("tip"):
                    out.setdefault(f"heatmap_style.{key}.tip", spec["tip"])
    return out


def english() -> dict:
    """id -> English: locales/en.json, and the scenery's words."""
    global _english
    if _english is None:
        _english = dict(scenery_english(), **_read(ENGLISH))
    return _english


def catalog() -> dict:
    """id -> {"web": whether a page script uses it, "where": the files that do}: locales/catalog.json,
    as dev/strings.py writes it."""
    return _read(CATALOG)


def web_ids() -> set:
    """The ids a page script uses (the catalog's "web" ones). Read once."""
    global _web_ids
    if _web_ids is None:
        _web_ids = {k for k, e in catalog().items() if e.get("web")}
    return _web_ids


def translations(tag: str) -> dict:
    """id -> {"text": the translation, "en": the English it was translated from}, as a language's
    file keeps them: its own over its base language's ("pt-BR" over "pt"). Read once a language."""
    if tag not in _translations:
        out = {}
        for name in reversed(candidates(tag)):
            if name != "en":  # (English is en.json)
                out.update(_read(os.path.join(LOCALES, f"{name}.json")))
        _translations[tag] = {k: v for k, v in out.items() if isinstance(v, dict) and v.get("text")}
    return _translations[tag]


def table_for(tag: str) -> dict:
    """id -> the words a language shows: its translations over the English; the made-up languages
    made from the English."""
    en = english()
    if tag in (PSEUDO, PSEUDO_RTL):
        return {k: pseudo_entry(v, rtl=tag == PSEUDO_RTL) for k, v in en.items()}
    return dict(en, **{k: v["text"] for k, v in translations(tag).items()})


def table() -> dict:
    global _table
    if _table is None:
        _table = table_for(lang())
    return _table


def translated() -> bool:
    """Whether the add-on has words in its language (English counts): dates and numbers follow the
    language only then, so a sentence never reads half in one language and half in another."""
    tag = lang()
    return base(tag) == "en" or tag in (PSEUDO, PSEUDO_RTL) or bool(translations(tag))


def format_lang() -> str:
    """The tag dates and numbers are written in: the language's own where its words are translated
    (and every English: en-GB writes "17 Oct 2026"), else en-US, as the English words around them."""
    tag = lang()
    if tag in (PSEUDO, PSEUDO_RTL) or tag == "en":
        return "en-US"
    return tag if translated() else "en-US"


def direction() -> str:
    """"rtl" for a right-to-left language the words are translated into, else "ltr"."""
    tag = lang()
    return "rtl" if (tag in RTL or base(tag) in RTL) and translated() else "ltr"


def plural_rule(tag: str | None = None) -> str:
    """The plural rule of a language (PLURALS); with no tag, of the words in use: English's where
    the reader's language has no translations."""
    if tag is None:
        tag = lang() if translated() else "en"
    if tag in (PSEUDO, PSEUDO_RTL):
        return "one_other"
    return PLURAL_RULE.get(tag) or PLURAL_RULE.get(base(tag), "one_other")


def num(n) -> str:
    """A number as the language writes it: 3,581 or 3.581."""
    if isinstance(n, float) and not n.is_integer():
        return str(n).replace(".", DECIMAL.get(base(format_lang()), "."))
    text = f"{int(n):,}"
    sep = GROUPING.get(base(format_lang()), ",")
    return text.replace(",", sep) if sep != "," else text


def dec(x: float, digits: int = 1) -> str:
    """A number with this many decimals, as the language writes it: 1,234.5 or 1.234,5."""
    group, point = GROUPING.get(base(format_lang()), ","), DECIMAL.get(base(format_lang()), ".")
    return f"{x:,.{digits}f}".replace(",", "\0").replace(".", point).replace("\0", group)


def _fill(text: str, values: dict) -> str:
    if not values:
        return text
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def t(key: str, **values) -> str:
    """The wording `key` in the reader's language, its {placeholders} filled (the id itself, where
    en.json has no such wording: dev/strings.py check finds those)."""
    found = table().get(key, key)
    return _fill(found if isinstance(found, str) else found.get("other", key), values)


def tn(key: str, n, **values) -> str:
    """The plural `key`, in the form the reader's language gives `n` ("{n} trees"); {n} is filled
    with the number as the language writes it (another placeholder can give it as it is)."""
    values["n"] = num(n)
    found = table().get(key, key)
    if isinstance(found, dict):
        # (a wording the language lacks is English, and takes English's forms: never "21 tree")
        own = key in translations(lang()) or lang() in (PSEUDO, PSEUDO_RTL)
        # (rounded half up, as web/i18n.js's Math.round does, so the page and Qt pick alike)
        form = PLURALS[plural_rule() if own else "one_other"](abs(math.floor(n + 0.5)))
        found = found.get(form) or found.get("other") or key
    return _fill(found, values)


def N_(key: str) -> str:
    """Marks a constant's wording, to show where it is shown rather than where it is written (a
    module's constant, read before the language is known): gives `key` back; show it with tx()."""
    return key


def tx(key: str, **values) -> str:
    """The wording of an id found at run time: a constant's (N_), or a scenery's."""
    return t(key, **values)


def scenery(kind: str, key: str, field: str = "") -> str:
    """A scenery's word: scenery("env", "aurora"), scenery("preset", "aurora", "note")."""
    return t(f"{kind}.{key}" + (f".{field}" if field else ""))


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")


def month(m: int, short: bool = False) -> str:
    """A month's name (1-12): "October", or "Oct"."""
    return t(f"month_short.{MONTHS[m - 1][:3]}") if short else t(f"month.{MONTHS[m - 1]}")


def day_month(d: _dt.date, short: bool = False) -> str:
    """"17 October", or "17 Oct", in the reader's language."""
    return t("date.day_month", day=d.day, month=month(d.month, short))


def day_month_year(d: _dt.date, short: bool = False) -> str:
    """"17 October 2026", or "17 Oct 2026", in the reader's language."""
    return t("date.day_month_year", day=d.day, month=month(d.month, short), year=d.year)


def month_year(d: _dt.date) -> str:
    """"October 2026"."""
    return t("date.month_year", month=month(d.month), year=d.year)


def page_strings() -> dict:
    """What the page (and the phone card) are sent: the language, its direction, how its dates and
    plurals go, and the words its scripts use (web/i18n.js), in the language or else in English."""
    web, en = web_ids(), english()
    # (the English the page has already, in web/strings_en.js)
    words = {k: v for k, v in table().items() if k in web and v != en.get(k)}
    return {"lang": lang(), "format": format_lang(), "dir": direction(), "plural": plural_rule(), "strings": words}


# ---------- the made-up languages ----------

_ACCENTS = dict(zip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    "åƀçđéƒĝĥîĵķļɱñöþǫŕšţûṽŵẋýžÅƁÇĐÉƑĜĤÎĴĶĻṀÑÖÞǪŔŠŢÛṼŴẊÝŽ"))
# what stays as it is: a placeholder, an HTML tag or entity
_KEEP = re.compile(r"(\{\w+\}|<[^>]+>|&\w+;)")


def pseudo(text: str, rtl: bool = False) -> str:
    """English made to look foreign and a third longer, in brackets, its placeholders and tags kept:
    a wording the code forgot to translate shows up as plain English beside it."""
    parts = _KEEP.split(text)
    # (right to left, en-XB: each word's letters forced right to left, U+202E to U+202C, so they act as
    # Hebrew's or Arabic's would round the numbers, dates and punctuation among them; left Latin, the
    # words kept their own order, and a line read as English set flush right, "[·· ŧŕééš 608]")
    word = (lambda s: re.sub(r"[^\W\d_]+", lambda m: "\u202e" + m.group() + "\u202c", s)) if rtl else (lambda s: s)
    out = "".join(p if i % 2 else word("".join(_ACCENTS.get(c, c) for c in p)) for i, p in enumerate(parts))
    letters = sum(len(p) for p in parts[::2])
    return f"[{out} {'·' * max(1, letters // 3)}]"


def pseudo_entry(en, rtl: bool = False):
    return {k: pseudo(v, rtl) for k, v in en.items()} if isinstance(en, dict) else pseudo(en, rtl)

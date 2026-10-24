"""The words in the reader's language (i18n.py), and the catalog and translations dev/strings.py keeps."""

import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import i18n

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ADDON, "dev"))
import strings

ENGLISH = {"x.your_forest": "Your forest", "x.day_day": "Day {day}",
           "x.n_days": {"one": "{n} day", "other": "{n} days"}, "x.n_trees": {"one": "{n} tree", "other": "{n} trees"}}


class Speaking(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_override, None)
        patch = mock.patch.object(i18n, "_english", dict(i18n.english(), **ENGLISH))
        patch.start()
        self.addCleanup(patch.stop)

    def use(self, tag, words=None):
        """A language, with these translations (id -> text) over the English."""
        i18n.set_override(tag)
        if words is not None:
            i18n._table = dict(i18n.english(), **words)
            patch = mock.patch.object(i18n, "translations", return_value={k: {"text": v} for k, v in words.items()})
            patch.start()
            self.addCleanup(patch.stop)

    def test_english_by_id(self):
        self.use("en")
        self.assertEqual(i18n.t("x.your_forest"), "Your forest")
        self.assertEqual(i18n.t("x.day_day", day=3), "Day 3")
        self.assertEqual(i18n.tn("x.n_trees", 1), "1 tree")
        self.assertEqual(i18n.tn("x.n_trees", 3581), "3,581 trees")
        self.assertEqual(i18n.t("x.not_there"), "x.not_there")
        self.assertEqual(i18n.day_month_year(_dt.date(2026, 10, 17)), "17 October 2026")
        self.assertEqual(i18n.day_month(_dt.date(2026, 10, 17), short=True), "17 Oct")
        self.assertEqual(i18n.direction(), "ltr")

    def test_a_translation_and_its_plural_forms(self):
        self.use("he", {"x.your_forest": "היער שלך", "x.n_days": {"one": "יום אחד", "two": "יומיים", "other": "{n} ימים"}})
        self.assertEqual(i18n.t("x.your_forest"), "היער שלך")
        self.assertEqual(i18n.t("x.day_day", day=2), "Day 2")  # (not translated: the English)
        self.assertEqual([i18n.tn("x.n_days", n) for n in (1, 2, 60)], ["יום אחד", "יומיים", "60 ימים"])
        self.assertEqual(i18n.direction(), "rtl")
        self.assertEqual(i18n.format_lang(), "he")

    def test_an_untranslated_language_stays_english_throughout(self):
        """Dates and numbers follow a language only where its words are translated."""
        self.use("fr", {})
        self.assertEqual(i18n.format_lang(), "en-US")
        self.assertEqual(i18n.num(3581), "3,581")
        self.assertEqual(i18n.plural_rule(), "one_other")
        self.assertEqual(i18n.page_strings()["dir"], "ltr")

    def test_english_variants_date_their_own_way(self):
        self.use("en-GB")
        self.assertEqual(i18n.format_lang(), "en-GB")
        self.use("en")
        self.assertEqual(i18n.format_lang(), "en-US")

    def test_german_numbers(self):
        self.use("de", {"x.your_forest": "Dein Wald"})
        self.assertEqual(i18n.num(3581), "3.581")
        self.assertEqual(i18n.tn("x.n_trees", 3581), "3.581 trees")

    def test_a_regional_language_falls_back_to_its_base(self):
        self.assertEqual(i18n.candidates("zh-Hant-TW"), ["zh-Hant-TW", "zh-Hant", "zh"])

    def test_the_page_gets_only_its_own_words_that_are_not_english(self):
        cat = {"x.your_forest": {"web": True}, "x.day_day": {"web": True}, "x.n_days": {"web": False}}
        self.use("de", {"x.your_forest": "Dein Wald", "x.n_days": {"one": "{n} Tag", "other": "{n} Tage"}})
        with mock.patch.object(i18n, "catalog", return_value=cat):
            self.assertEqual(i18n.page_strings()["strings"], {"x.your_forest": "Dein Wald"})

    def test_a_sceneries_words_come_from_its_json(self):
        en = i18n.scenery_english()
        self.assertEqual(en["env.natural"], "Natural")
        self.assertIn("preset.aurora", en)
        self.assertIn("heatmap_style.flat", en)

    def test_pseudo_keeps_placeholders_and_tags(self):
        text = i18n.pseudo("Day <b>{day}</b> of your streak &amp; more")
        self.assertIn("<b>{day}</b>", text)
        self.assertIn("&amp;", text)
        self.assertTrue(text.startswith("[Đåý"))
        self.assertGreater(len(text), len("Day <b>{day}</b> of your streak &amp; more"))

    def test_pseudo_rtl_is_right_to_left(self):
        self.use(i18n.PSEUDO_RTL)
        self.assertEqual(i18n.direction(), "rtl")
        self.assertTrue(i18n.t("x.your_forest").startswith("[Ýöûŕ"))

    def test_anki_lang_reads_either_name(self):
        fake = mock.Mock(spec=["currentLang"], currentLang="pt_BR")
        with mock.patch.dict(sys.modules, {"anki": mock.Mock(lang=fake), "anki.lang": fake}):
            self.assertEqual(i18n.anki_lang(), "pt-BR")

    def test_plurals_for_each_rule(self):
        self.assertEqual([i18n.PLURALS["slavic"](n) for n in (1, 2, 5, 11, 21, 22, 112)],
                         ["one", "few", "many", "many", "one", "few", "many"])
        self.assertEqual([i18n.PLURALS["arabic"](n) for n in (0, 1, 2, 3, 11, 100)],
                         ["zero", "one", "two", "few", "many", "other"])
        for rule, forms in i18n.PLURAL_FORMS.items():
            self.assertTrue({i18n.PLURALS[rule](n) for n in range(200)} <= set(forms), rule)


class Strings(unittest.TestCase):
    """dev/strings.py: the catalog is up to date, and every translation fits it."""

    CAT = {k: {"web": True, "where": ["web/x.js:1"]} for k in ENGLISH}

    def setUp(self):
        patch = mock.patch.object(i18n, "_english", dict(ENGLISH))
        patch.start()
        self.addCleanup(patch.stop)

    def test_catalog_and_translations_check(self):
        run = subprocess.run([sys.executable, os.path.join(ADDON, "dev", "strings.py"), "check"],
                             capture_output=True, text=True, cwd=ADDON)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_problems_are_found(self):
        good = {"x.day_day": {"text": "Tag {day}"}, "x.n_days": {"text": {"one": "{n} Tag", "other": "{n} Tage"}}}
        self.assertEqual(strings.problems("de", good, self.CAT), [])
        # a lost placeholder, Hebrew's missing "two", an id the code no longer has
        bad = strings.problems("he", {"x.day_day": {"text": "יום"}, "x.n_days": {"text": {"one": "x", "other": "{n} y"}},
                                      "x.gone": {"text": "z"}}, self.CAT)
        self.assertEqual(len(bad), 3, bad)

    def test_a_form_may_leave_out_its_number(self):
        ok = {"x.n_days": {"text": {"one": "יום אחד", "two": "יומיים", "other": "{n} ימים"}}}
        self.assertEqual(strings.problems("he", ok, self.CAT), [])

    def test_a_translation_added_by_hand_is_stamped_and_a_changed_english_found(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(i18n, "LOCALES", tmp):
            with open(os.path.join(tmp, "he.json"), "w", encoding="utf-8") as f:
                json.dump({"x.day_day": {"text": "יום {day}"}}, f)
            strings.stamp()
            self.assertEqual(strings._table("he")["x.day_day"], {"text": "יום {day}", "en": "Day {day}"})
            # the English changes: the old translation still shows, and check lists it again
            with mock.patch.object(i18n, "_english", dict(ENGLISH, **{"x.day_day": "Day {day} of the streak"})):
                self.assertEqual(strings.outdated(strings._table("he")), ["x.day_day"])

if __name__ == "__main__":
    unittest.main()

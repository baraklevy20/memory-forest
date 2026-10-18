"""What fails the real-Anki check (e2e/old_anki.py --check): a problem or an error the check add-on
reported, a failure the add-on only logged, or a traceback anywhere in Anki's output."""

from __future__ import annotations

import ast
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401

E2E = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "e2e")
sys.path.insert(0, E2E)
import old_anki

TB = "Traceback (most recent call last):\n  File \"x.py\", line 1, in f\nValueError: boom"
CLEAN = {"anki": "26.09.3", "qt": "6", "steps": ["deck list"], "problems": [], "errors": []}


class UnhandledTests(unittest.TestCase):
    def test_a_traceback_in_anki_s_output_is_found(self):
        found = old_anki.unhandled(f"starting\n{TB}\nmore output\n")
        self.assertEqual(found, [TB])

    def test_one_the_add_on_logged_is_left_to_logged(self):
        self.assertEqual(old_anki.unhandled(f"[anki_forest] could not render the forest:\n{TB}\n"), [])

    def test_a_chained_one_is_one_traceback(self):
        text = f"{TB}\n\nDuring handling of the above exception, another exception occurred:\n\n{TB}\n"
        self.assertEqual(len(old_anki.unhandled(text)), 1)

    def test_a_clean_run_has_none(self):
        self.assertEqual(old_anki.unhandled("Starting Anki 26.09.3...\nqt.webenginecontext: GL Type: disabled\n"), [])


class CheckVerdictTests(unittest.TestCase):
    def verdict(self, report, log=""):
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as results, \
                mock.patch.object(old_anki, "BASE", base), mock.patch.object(old_anki, "RESULTS", results), \
                mock.patch.object(old_anki, "install", return_value="memory_forest"), \
                mock.patch.object(old_anki, "executable", return_value=sys.executable), \
                mock.patch.object(old_anki, "run_check", return_value=(report, log, True)), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            return old_anki.check("26.09.3", "/Anki.app", None), out.getvalue()

    def test_a_clean_report_passes(self):
        self.assertTrue(self.verdict(CLEAN)[0])

    def test_a_problem_or_an_error_fails(self):
        self.assertFalse(self.verdict(dict(CLEAN, problems=["the forest never built"]))[0])
        self.assertFalse(self.verdict(dict(CLEAN, errors=["settings:\n" + TB]))[0])

    def test_a_failure_the_add_on_only_logged_fails(self):
        ok, out = self.verdict(CLEAN, f"[anki_forest] could not handle x:\n{TB}\n\n")
        self.assertFalse(ok)
        self.assertIn("LOGGED", out)

    def test_any_other_traceback_in_anki_s_output_fails(self):
        ok, out = self.verdict(CLEAN, f"{TB}\n")
        self.assertFalse(ok)
        self.assertIn("TRACEBACK", out)

    def test_no_report_at_all_fails(self):
        self.assertFalse(self.verdict(None)[0])


class CheckAddonTests(unittest.TestCase):
    """e2e/old_anki_check.py runs only inside Anki: read here, not run."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(E2E, "old_anki_check.py"), encoding="utf-8") as f:
            cls.source = f.read()
        cls.tree = ast.parse(cls.source)
        cls.functions = {n.name for n in ast.walk(cls.tree) if isinstance(n, ast.FunctionDef)}

    def test_errors_anywhere_are_kept_for_the_report(self):
        self.assertIn("sys.excepthook = _caught", self.source)  # a Qt slot's or a hook's error
        self.assertIn("sys.stderr = Stderr(sys.stderr)", self.source)  # one printed
        self.assertIn("canaries", self.functions)  # and each proven to be caught, in every Anki it runs in

    def test_the_real_ui_steps_are_all_run(self):
        steps = {n.args[0].value for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "step" and n.args and isinstance(n.args[0], ast.Constant)}
        for name in ("settings", "change scenery", "phone", "deck screen", "finished deck", "settings from the cog, cancelled",
                     "settings closed with Esc", "settings across a theme switch", "gear menu leaves a deck out and back",
                     "page messages", "planting on the first answer", "errors in slots fail the check"):
            self.assertIn(name, steps)


if __name__ == "__main__":
    unittest.main()

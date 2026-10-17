"""Shared median behavior for card strength, study pace, and daily review counts."""

import builtins
import runpy
import unittest
from pathlib import Path
from unittest import mock

from numeric import median


class MedianTests(unittest.TestCase):
    def test_odd_even_single_and_zero_values(self):
        for values, expected in (([9, 1, 3], 3), ([9, 0, 2, 1], 1.5), ([0], 0), ([-5, -1, 0], -1)):
            with self.subTest(values=values):
                self.assertEqual(median(values), expected)

    def test_does_not_mutate_input_and_accepts_iterators(self):
        values = [4.5, 1.5, 3.0]
        self.assertEqual(median(iter(values)), 3.0)
        self.assertEqual(values, [4.5, 1.5, 3.0])

    def test_uses_standard_library_when_available(self):
        from statistics import median as standard_median
        self.assertIs(median, standard_median)

    def test_fallback_when_statistics_is_not_bundled(self):
        original_import = builtins.__import__

        def without_statistics(name, *args, **kwargs):
            if name == "statistics":
                raise ImportError("not bundled")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=without_statistics):
            fallback = runpy.run_path(str(Path(__file__).resolve().parents[1] / "numeric.py"))["median"]
        for values in ([9, 1, 3], [9, 0, 2, 1], [0], [-5, -1, 0]):
            with self.subTest(values=values):
                self.assertEqual(fallback(values), median(values))

"""Compatibility checks must launch offscreen and never reactivate desktop apps."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "e2e"))
import old_anki


class BackgroundRunnerTests(unittest.TestCase):
    def test_checks_are_offscreen_unless_show_is_explicit(self):
        for show in (False, True):
            with self.subTest(show=show), tempfile.TemporaryDirectory() as base, \
                    mock.patch.dict(os.environ, {"MEMORY_FOREST_SHOW": "1"} if show else {}, clear=True), \
                    mock.patch.object(old_anki, "BASE", base), mock.patch.object(old_anki, "no_first_run"), \
                    mock.patch.object(old_anki.subprocess, "Popen") as launch, \
                    mock.patch.object(old_anki.subprocess, "run") as run, mock.patch.object(old_anki.time, "sleep"):
                launch.return_value.poll.side_effect = [None, 0, 0]
                old_anki.run_check("/tmp/Anki", "memory_forest")
                env = launch.call_args.kwargs["env"]
                if show:
                    self.assertNotIn("QT_QPA_PLATFORM", env)
                else:
                    self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
                    self.assertEqual(env["QT_STYLE_OVERRIDE"], "Fusion")
                    self.assertIn("--disable-renderer-backgrounding", env["QTWEBENGINE_CHROMIUM_FLAGS"])
                run.assert_not_called()  # no `open` calls to steal/restore focus

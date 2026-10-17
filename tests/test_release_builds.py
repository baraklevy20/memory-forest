"""Build commands package without launching Anki; releases retain their compatibility gate."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401

DEV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev")
if not os.path.isfile(os.path.join(DEV, "release.py")):
    raise unittest.SkipTest("release tooling is private")
sys.path.insert(0, DEV)
import release


class BuildChecksTests(unittest.TestCase):
    def test_plus_only_checks_when_explicitly_requested(self):
        for flags, expected in (([], False), (["--anki-check"], True), (["--no-anki-check"], False)):
            with self.subTest(flags=flags), mock.patch.object(sys, "argv", ["release.py", "--plus", *flags, "/tmp/plus.ankiaddon"]), \
                    mock.patch.object(release, "git", return_value=json.dumps({"human_version": "1.3.0"})), \
                    mock.patch.object(release, "build_plus") as build:
                release.main()
                self.assertEqual(build.call_args.args, ("/tmp/plus.ankiaddon", False, expected))

    def test_base_builds_skip_checks_but_release_dry_runs_keep_them(self):
        with tempfile.TemporaryDirectory() as repo:
            os.mkdir(os.path.join(repo, ".git"))
            with open(os.path.join(repo, "manifest.json"), "w") as f:
                json.dump({"human_version": "1.3.0"}, f)

            def git(_repo, *args):
                if args == ("tag", "--list", "v*"):
                    return "v1.2.0"
                if args[0] == "rev-parse":
                    return "abc123"
                return ""

            for flags, expected in ((["--base"], False), (["--base", "--anki-check"], True), (["--dry-run"], True)):
                with self.subTest(flags=flags), mock.patch.object(sys, "argv", ["release.py", *flags, repo]), \
                        mock.patch.object(release, "git", side_effect=git), \
                        mock.patch.object(release, "build", return_value=("description", "notes")) as build, \
                        mock.patch.object(release, "check_old_ankis") as check, contextlib.redirect_stdout(io.StringIO()):
                    release.main()
                    build.assert_called_once()
                    self.assertEqual(check.called, expected)

"""dev/package.py on Windows, where a path says \\ and esbuild's .bin entry can't be run."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import package


class WindowsTests(unittest.TestCase):
    def test_a_zip_name_uses_slashes_whatever_the_system_writes(self):
        real = os.path.relpath
        with mock.patch.object(package.os, "sep", "\\"), \
                mock.patch.object(package.os.path, "relpath", lambda p, s: real(p, s).replace("/", "\\")):
            names = [name for _path, name in package.files()]
        self.assertIn("web/util.js", names)
        self.assertFalse([n for n in names if "\\" in n])

    def test_on_windows_it_runs_esbuilds_own_exe(self):
        with tempfile.TemporaryDirectory() as modules:
            folder = os.path.join(modules, "@esbuild", "win32-x64")
            os.makedirs(folder)
            exe = os.path.join(folder, "esbuild.exe")
            open(exe, "w").close()
            with mock.patch.object(package.os, "name", "nt"):
                self.assertEqual(package.esbuild_program(modules), exe)

    def test_elsewhere_it_runs_the_bin_entry(self):
        with mock.patch.object(package.os, "name", "posix"):
            self.assertEqual(package.esbuild_program(), package.ESBUILD)


if __name__ == "__main__":
    unittest.main()

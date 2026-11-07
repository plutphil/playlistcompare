from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from file_actions import open_path


class FileActionTests(unittest.TestCase):
    @patch("file_actions.sys.platform", "win32")
    @patch("file_actions.os.startfile", create=True)
    def test_windows_open(self, startfile):
        with tempfile.TemporaryDirectory() as directory:
            open_path(directory)
            startfile.assert_called_once_with(str(Path(directory).absolute()))

    @patch("file_actions.subprocess.Popen")
    def test_linux_and_mac_open(self, popen):
        with tempfile.TemporaryDirectory(prefix="audio search ") as directory:
            for platform, command in (("linux", "xdg-open"), ("darwin", "open")):
                with patch("file_actions.sys.platform", platform):
                    open_path(directory)
                popen.assert_called_with([command, str(Path(directory).absolute())])

    def test_missing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                open_path(Path(directory) / "missing")


if __name__ == "__main__":
    unittest.main()
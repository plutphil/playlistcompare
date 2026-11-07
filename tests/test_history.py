from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from history import History


class HistoryTests(unittest.TestCase):
    def test_persistence_and_recent_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "history.json"
            history = History(path)
            history.remember("first", "First", "/music")
            history.remember("second", "Second", "/other")
            history.remember("first", "Updated", "/new")
            entries = History(path).entries
            self.assertEqual([entry["url"] for entry in entries], ["first", "second"])
            self.assertEqual(entries[0]["name"], "Updated")
            self.assertEqual(entries[0]["folder"], "/new")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_invalid_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            for content in ("invalid json", "{}", '[{}, null, {"url": 1}]'):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(History(path).entries, [])

    def test_history_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            history = History(Path(directory) / "history.json")
            for index in range(35):
                history.remember(str(index), "Playlist", "/music")
            self.assertEqual(len(history.entries), 30)
            self.assertEqual(history.entries[0]["url"], "34")

    @patch("history.sys.platform", "win32")
    def test_windows_appdata_location(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"APPDATA": directory, "XDG_CONFIG_HOME": "ignored"}):
                history = History()
            self.assertEqual(history.path, Path(directory) / "playlistcompare" / "history.json")

    @patch("history.sys.platform", "win32")
    def test_windows_appdata_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {}, clear=True), patch("history.Path.home", return_value=Path(directory)):
                history = History()
            self.assertEqual(history.path, Path(directory) / "AppData" / "Roaming" / "playlistcompare" / "history.json")

    @patch("history.sys.platform", "linux")
    def test_linux_xdg_location(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": directory}):
                history = History()
            self.assertEqual(history.path, Path(directory) / "playlistcompare" / "history.json")


if __name__ == "__main__":
    unittest.main()
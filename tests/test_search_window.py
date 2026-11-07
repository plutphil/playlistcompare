from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from search_window import SearchWindow
from tracks import Track, local_files


class ImmediateThread:
    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


class SearchWindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.root.destroy)
        self.folder = Path(self.directory.name)
        self.source = self.folder / "Artist - My Song.mp3"
        self.other = self.folder / "Other - My Song.mp3"
        self.source.touch()
        self.other.touch()
        self.deleted = Mock()
        self.files = local_files(self.folder)
        self.search = SearchWindow(self.root, self.folder, Track("Artist", "My Song"), self.files, self.deleted)
        self.search.window.withdraw()

    def select_first(self):
        self.search.tree.selection_set("0")
        self.search.update_actions()

    def test_all_results_and_artist_ranking(self):
        self.assertEqual(len(self.search.tree.get_children()), 2)
        self.assertEqual(self.search.results[0].path, self.source.name)
        self.assertEqual(self.search.tree.item("0", "values")[:3], ("120", "100", "20"))
        self.assertEqual(self.search.status.get(), "2 results / 2 audio files")
        self.search.artist.set("Other")
        self.search.search()
        self.assertEqual(self.search.results[0].path, self.other.name)

    @patch("search_window.open_path")
    def test_open_file_and_folder(self, open_path):
        self.search.open_file()
        open_path.assert_not_called()
        self.select_first()
        self.search.open_file()
        open_path.assert_called_with(self.source)
        self.search.open_folder()
        open_path.assert_called_with(self.folder)

    @patch("search_window.messagebox.askyesno", return_value=False)
    def test_delete_cancel(self, confirm):
        self.select_first()
        self.search.delete_file()
        self.assertTrue(self.source.exists())
        self.assertEqual(len(self.search.results), 2)
        self.deleted.assert_not_called()
        self.assertEqual(confirm.call_args.kwargs["default"], "no")

    @patch("search_window.messagebox.askyesno", return_value=True)
    def test_confirmed_delete_updates_index_and_results(self, confirm):
        self.select_first()
        self.search.delete_file()
        self.assertFalse(self.source.exists())
        self.assertTrue(self.other.exists())
        self.assertEqual(len(self.files), 1)
        self.assertEqual(self.search.results[0].path, self.other.name)
        self.deleted.assert_called_once_with()

    @patch("search_window.messagebox.showerror")
    @patch("search_window.messagebox.askyesno", return_value=True)
    @patch("search_window.Path.unlink", side_effect=PermissionError("Access denied"))
    def test_delete_failure_keeps_results(self, unlink, confirm, showerror):
        self.select_first()
        self.search.delete_file()
        self.assertEqual(len(self.files), 2)
        self.deleted.assert_not_called()
        showerror.assert_called_once()

    @patch("search_window.messagebox.showerror")
    @patch("search_window.open_path", side_effect=FileNotFoundError("Gone"))
    def test_open_failure(self, open_path, showerror):
        self.select_first()
        self.search.open_file()
        showerror.assert_called_once()

    @patch("search_window.Thread", ImmediateThread)
    def test_standalone_folder_scan(self):
        search = SearchWindow(self.root, self.folder, Track("", "My Song"))
        self.assertEqual(len(search.results), 2)
        self.assertEqual(len(search.files), 2)
        self.assertEqual(str(search.search_button.cget("state")), "normal")
        search.close()

    @patch("search_window.Thread", ImmediateThread)
    @patch("search_window.local_files", side_effect=PermissionError("Access denied"))
    @patch("search_window.messagebox.showerror")
    def test_folder_scan_failure(self, showerror, scan):
        search = SearchWindow(self.root, self.folder)
        self.assertEqual(search.status.get(), "Scan failed.")
        showerror.assert_called_once()
        search.close()


if __name__ == "__main__":
    unittest.main()
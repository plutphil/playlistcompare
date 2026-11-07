from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from app import PlaylistApp
from history import History
from providers import Playlist
from tracks import Track


class ImmediateThread:
    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.root.destroy)
        self.history = History(Path(self.directory.name) / "history.json")
        self.app = PlaylistApp(self.root, self.history)

    def test_combobox_restores_previous_url_and_folder(self):
        self.history.remember("https://youtube.com/playlist?list=abc", "Favorites", "/music")
        self.app.refresh_history()
        self.app.playlists.current(0)
        self.app.playlists.event_generate("<<ComboboxSelected>>")
        self.assertEqual(self.app.url.get(), "https://youtube.com/playlist?list=abc")
        self.assertEqual(self.app.folder.get(), "/music")

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_load_results_and_history(self, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song"), Track("Other", "Missing")], 1)
        (Path(self.directory.name) / "Artist - Song.mp3").touch()
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        rows = [self.app.tree.item(item, "values") for item in self.app.tree.get_children()]
        self.assertEqual(rows[0], ("FOUND", "Artist", "Song", "Artist - Song.mp3"))
        self.assertEqual(rows[1][0], "MISSING")
        self.assertEqual(self.app.status.get(), "1 found, 1 missing, 1 unavailable")
        self.assertFalse(self.app.busy)
        self.assertEqual(self.history.entries[0]["url"], self.app.url.get())
        self.assertIn("Favorites", self.app.playlists.cget("values")[0])
        self.assertEqual(str(self.app.export_button.cget("state")), "normal")

    @patch("app.filedialog.asksaveasfilename")
    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_export_uses_loaded_folder_and_only_found_tracks(self, load, save):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song"), Track("Other", "Missing")])
        source = Path(self.directory.name) / "Artist - Song.mp3"
        source.touch()
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        self.app.folder.set("different-folder")
        destination = Path(self.directory.name) / "set.m3u8"
        save.return_value = str(destination)
        self.app.export_button.invoke()
        self.assertEqual(destination.read_text().splitlines(),
                         ["#EXTM3U", "#EXTINF:-1,Artist - Song", "Artist - Song.mp3"])
        self.assertEqual(save.call_args.kwargs["initialdir"], self.directory.name)
        self.assertEqual(self.app.status.get(), "Exported 1 tracks to set.m3u8.")

    @patch("app.filedialog.asksaveasfilename", return_value="")
    @patch("app.write_playlist")
    def test_export_cancel_does_not_write(self, write, save):
        self.app.export_entries = [(Track("Artist", "Song"), Path(self.directory.name) / "Song.mp3")]
        self.app.export_folder = Path(self.directory.name)
        self.app.export()
        write.assert_not_called()

    @patch("app.messagebox.showerror")
    @patch("app.filedialog.asksaveasfilename")
    def test_export_reports_errors(self, save, showerror):
        self.app.export_entries = [(Track("Artist", "Song"), Path(self.directory.name) / "missing.mp3")]
        self.app.export_folder = Path(self.directory.name)
        save.return_value = str(Path(self.directory.name) / "set.m3u8")
        self.app.export()
        showerror.assert_called_once()
        self.assertFalse(Path(save.return_value).exists())

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_export_disabled_without_found_tracks(self, load):
        self.assertEqual(str(self.app.export_button.cget("state")), "disabled")
        load.return_value = Playlist("Favorites", [Track("Artist", "Missing")])
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        self.assertEqual(str(self.app.export_button.cget("state")), "disabled")

    def test_export_disabled_while_busy(self):
        self.app.export_entries = [(Track("Artist", "Song"), Path(self.directory.name) / "Song.mp3")]
        self.app.set_busy(True)
        self.assertEqual(str(self.app.export_button.cget("state")), "disabled")
        self.app.set_busy(False)
        self.assertEqual(str(self.app.export_button.cget("state")), "normal")

    @patch("app.messagebox.showerror")
    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist", side_effect=RuntimeError("Network error"))
    def test_load_failure_restores_controls(self, load, showerror):
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        self.assertFalse(self.app.busy)
        self.assertEqual(str(self.app.playlists.cget("state")), "normal")
        self.assertEqual(self.history.entries, [])
        self.assertEqual(self.app.status.get(), "Load failed.")
        showerror.assert_called_once()

    @patch("app.messagebox.showerror")
    @patch("app.load_playlist")
    def test_invalid_input_does_not_load(self, load, showerror):
        self.app.load()
        load.assert_not_called()
        showerror.assert_called_once()

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    @patch("search_window.messagebox.askyesno", return_value=True)
    def test_search_delete_refreshes_main_match_and_export(self, confirm, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "My Song")])
        folder = Path(self.directory.name)
        preferred = folder / "01 Artist - My Song.mp3"
        alternative = folder / "02 Other - My Song.mp3"
        preferred.touch()
        alternative.touch()
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        self.app.tree.selection_set("0")
        self.app.folder.set("changed-folder")
        self.app.search_button.invoke()
        search = self.app.search_window
        self.assertEqual(search.title.get(), "My Song")
        self.assertEqual(search.artist.get(), "Artist")
        self.assertEqual(search.folder, folder)
        search.tree.selection_set("0")
        search.delete_file()
        self.assertFalse(preferred.exists())
        self.assertEqual(self.app.tree.item("0", "values")[-1], alternative.name)
        self.assertEqual(self.app.export_entries[0][1], alternative)
        search.tree.selection_set("0")
        search.delete_file()
        self.assertEqual(self.app.tree.item("0", "values")[0], "MISSING")
        self.assertEqual(self.app.export_entries, [])
        self.assertEqual(str(self.app.export_button.cget("state")), "disabled")
        self.app.close_search()

    @patch("app.SearchWindow")
    def test_search_without_playlist(self, search_window):
        self.app.folder.set(self.directory.name)
        self.app.search_button.invoke()
        search_window.assert_called_once_with(self.root, Path(self.directory.name), None, None, None)
        self.app.search_window = None

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_rescan_updates_matches_without_loading_playlist(self, load):
        playlist = Playlist("Favorites", [Track("Artist", "Song")])
        load.return_value = playlist
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        self.assertEqual(self.app.tree.item("0", "values")[0], "MISSING")
        source = Path(self.directory.name) / "Artist - Song.mp3"
        source.touch()
        self.app.rescan_button.invoke()
        load.assert_called_once_with(self.app.loaded_url, force_reload=False)
        self.assertIs(self.app.loaded_playlist, playlist)
        self.assertEqual(self.app.tree.item("0", "values")[0], "FOUND")
        self.assertEqual(self.app.export_entries, [(playlist.tracks[0], source)])
        source.unlink()
        self.app.rescan_button.invoke()
        self.assertEqual(load.call_count, 1)
        self.assertEqual(self.app.tree.item("0", "values")[0], "MISSING")
        self.assertEqual(self.app.export_entries, [])

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_rescan_uses_selected_folder_and_original_playlist_url(self, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song")])
        original_url = "https://youtube.com/playlist?list=abc"
        self.app.url.set(original_url)
        self.app.folder.set(self.directory.name)
        self.app.load()
        folder = Path(self.directory.name) / "other"
        folder.mkdir()
        source = folder / "Artist - Song.mp3"
        source.touch()
        self.app.url.set("not a playlist URL")
        self.app.folder.set(str(folder))
        self.app.rescan_button.invoke()
        self.assertEqual(load.call_count, 1)
        self.assertEqual(self.app.loaded_url, original_url)
        self.assertEqual(self.app.url.get(), "not a playlist URL")
        self.assertEqual(self.app.export_folder, folder)
        self.assertEqual(self.app.export_entries[0][1], source)
        self.assertEqual(self.history.entries[0]["url"], original_url)
        self.assertEqual(self.history.entries[0]["folder"], str(folder))

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    def test_force_reload_fetches_and_renders_new_playlist(self, load):
        url = "https://youtube.com/playlist?list=abc"
        self.app.url.set(url)
        self.app.folder.set(self.directory.name)
        load.return_value = Playlist("Original", [Track("Artist", "Song")])
        self.app.load()
        load.return_value = Playlist("Updated", [Track("Artist", "New Song")])
        self.app.reload_button.invoke()
        load.assert_called_with(url, force_reload=True)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(self.app.loaded_playlist.name, "Updated")
        self.assertEqual(self.app.tree.item("0", "values")[2], "New Song")

    @patch("app.load_playlist")
    def test_rescan_disabled_without_playlist(self, load):
        self.assertEqual(str(self.app.rescan_button.cget("state")), "disabled")
        self.app.rescan_files()
        load.assert_not_called()

    @patch("app.Thread", ImmediateThread)
    @patch("app.load_playlist")
    @patch("app.messagebox.showerror")
    def test_failed_rescan_preserves_results_and_restores_controls(self, showerror, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song")])
        self.app.url.set("https://youtube.com/playlist?list=abc")
        self.app.folder.set(self.directory.name)
        self.app.load()
        playlist = self.app.loaded_playlist
        with patch("app.local_files", side_effect=OSError("Scan failed")):
            self.app.rescan_button.invoke()
        self.assertIs(self.app.loaded_playlist, playlist)
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.assertFalse(self.app.busy)
        self.assertEqual(str(self.app.rescan_button.cget("state")), "normal")
        self.assertEqual(str(self.app.reload_button.cget("state")), "normal")
        self.assertEqual(load.call_count, 1)
        showerror.assert_called_once()

    @patch("app.Thread")
    def test_refresh_controls_disabled_while_busy(self, thread):
        self.app.loaded_playlist = Playlist("Favorites", [Track("Artist", "Song")])
        self.app.set_busy(True)
        for button in (self.app.rescan_button, self.app.reload_button):
            self.assertEqual(str(button.cget("state")), "disabled")
        self.app.rescan_files()
        self.app.reload_playlist()
        thread.assert_not_called()
        self.app.set_busy(False)
        for button in (self.app.rescan_button, self.app.reload_button):
            self.assertEqual(str(button.cget("state")), "normal")


if __name__ == "__main__":
    unittest.main()
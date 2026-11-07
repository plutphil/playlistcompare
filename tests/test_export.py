import ntpath
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from export import relative_path, write_playlist
from tracks import Track


class ExportTests(unittest.TestCase):
    def test_relative_paths_unicode_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            music = root / "music"
            music.mkdir()
            playlists = root / "playlists"
            playlists.mkdir()
            sources = [music / "Artist - Caf\u00e9.mp3", music / "Other song.flac"]
            for source in sources:
                source.touch()
            destination = playlists / "mix.m3u8"
            entries = [(Track("Artist", "Caf\u00e9"), sources[0]), (Track("Other", "Song"), sources[1])]
            self.assertEqual(write_playlist(destination, entries), 2)
            lines = destination.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["#EXTM3U", "#EXTINF:-1,Artist - Caf\u00e9", "../music/Artist - Caf\u00e9.mp3",
                                     "#EXTINF:-1,Other - Song", "../music/Other song.flac"])
            for relative, source in zip(lines[2::2], sources):
                self.assertEqual((destination.parent / relative).resolve(), source.resolve())
            self.assertEqual(list(playlists.iterdir()), [destination])

    @patch("export.paths", ntpath)
    def test_windows_relative_paths(self):
        self.assertEqual(relative_path(r"C:\Music\Artist - Song.mp3", r"C:\Playlists\set.m3u8"),
                         "../Music/Artist - Song.mp3")
        self.assertEqual(relative_path(r"C:\Music\sub\Song.mp3", r"C:\Music\set.m3u"), "sub/Song.mp3")
        self.assertEqual(relative_path(r"\\server\share\Music\Song.mp3", r"\\server\share\set.m3u8"), "Music/Song.mp3")

    @patch("export.paths", ntpath)
    def test_windows_different_drives(self):
        with self.assertRaisesRegex(ValueError, "same drive"):
            relative_path(r"D:\Music\Song.mp3", r"C:\Playlists\set.m3u8")

    def test_hash_filename_is_not_a_comment(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "#Song.mp3"
            source.touch()
            destination = Path(directory) / "set.m3u"
            write_playlist(destination, [(Track("Artist\nGuest", "Song"), source)])
            self.assertEqual(destination.read_text().splitlines(),
                             ["#EXTM3U", "#EXTINF:-1,Artist Guest - Song", "./#Song.mp3"])

    def test_invalid_export_leaves_existing_playlist_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "set.m3u8"
            destination.write_text("original", encoding="utf-8")
            for entries in ([], [(Track("Artist", "Song"), Path(directory) / "missing.mp3")]):
                with self.assertRaises(ValueError):
                    write_playlist(destination, entries)
                self.assertEqual(destination.read_text(), "original")

    def test_reject_audio_file_destination_and_line_breaks(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "playlist filename"):
                write_playlist(Path(directory) / "song.mp3", [])
            with self.assertRaisesRegex(ValueError, "line breaks"):
                relative_path(str(Path(directory) / "Song\nname.mp3"), str(Path(directory) / "set.m3u8"))


if __name__ == "__main__":
    unittest.main()
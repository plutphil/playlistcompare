from pathlib import Path
import tempfile
import unittest

from tracks import Track, clean, local_files, match_track, search_tracks, youtube_track


class TrackTests(unittest.TestCase):
    def test_artist_in_video_title(self):
        track = youtube_track({"title": "Artist - Song (Official Music Video)", "channel": "Label"})
        self.assertEqual(track, Track("Artist", "Song"))

    def test_channel_fallback(self):
        for channel in ("Artist - Topic", "ArtistVEVO", "Artist"):
            with self.subTest(channel=channel):
                track = youtube_track({"title": "Song [Official Audio]", "channel": channel})
                self.assertEqual(track, Track("Artist", "Song"))

    def test_metadata_and_meaningful_version(self):
        track = youtube_track({"title": "Other - Video", "artist": "Artist", "track": "Song (Club Remix)"})
        self.assertEqual(track, Track("Artist", "Song (Club Remix)"))

    def test_uploader_fallback_and_unicode_separator(self):
        self.assertEqual(youtube_track({"title": "Song", "uploader": "Artist"}), Track("Artist", "Song"))
        self.assertEqual(youtube_track({"title": "Artist \u2013 Song | Official Video"}), Track("Artist", "Song"))

    def test_dots_and_unicode_are_not_truncated(self):
        self.assertEqual(clean("Beyonc\u00e9 - Song Pt. 2"), "beyonce song pt 2")

    def test_title_first_and_artist_ranking(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ("01 Other - My Song (Extended Mix).mp3", "02 Artist - My Song.mp3", "03 Artist - Unrelated.mp3"):
                (folder / name).touch()
            files = local_files(folder)
            results = search_tracks(Track("Artist", "My Song"), files)
            self.assertEqual([result.path for result in results],
                             ["02 Artist - My Song.mp3", "01 Other - My Song (Extended Mix).mp3"])
            self.assertEqual(results[0].artist_score, 20)
            self.assertEqual(results[1].artist_score, 0)
            self.assertEqual(match_track(Track("Wrong channel", "My Song"), files), results[1].path)

    def test_artist_folder_and_duplicate_names(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for artist in ("Other", "Beyonce"):
                (folder / artist).mkdir()
                (folder / artist / "Cafe.mp3").touch()
            files = local_files(folder)
            self.assertEqual(len(files), 2)
            results = search_tracks(Track("Beyonc\u00e9", "Caf\u00e9"), files)
            self.assertEqual([result.path for result in results], ["Beyonce/Cafe.mp3", "Other/Cafe.mp3"])

    def test_version_ranking_and_word_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ("Artist - Song.mp3", "Artist - Song (Club Remix).mp3", "Artist - Songbird.mp3"):
                (folder / name).touch()
            results = search_tracks(Track("Artist", "Song (Club Remix)"), local_files(folder))
            self.assertEqual([result.path for result in results],
                             ["Artist - Song (Club Remix).mp3", "Artist - Song.mp3"])
            self.assertEqual(search_tracks(Track("Artist", ""), local_files(folder)), [])

    def test_recursive_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "nested").mkdir()
            (folder / "nested" / "Artist - Song Pt. 2.MP3").touch()
            (folder / "Title only.flac").touch()
            (folder / "Ignored.txt").touch()
            files = local_files(folder)
            self.assertEqual(len(files), 2)
            self.assertEqual(match_track(Track("Artist", "Song Pt. 2"), files), "nested/Artist - Song Pt. 2.MP3")
            self.assertEqual(match_track(Track("Someone", "Title only"), files), "Title only.flac")
            self.assertIsNone(match_track(Track("Artist", "Missing"), files))

    def test_invalid_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                local_files(Path(directory) / "missing")


if __name__ == "__main__":
    unittest.main()
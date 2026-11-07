import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from providers import Playlist, _providers, load_playlist, provider_for, run_tool
from tracks import Track


class ProviderTests(unittest.TestCase):
    def setUp(self):
        cache = patch.dict("providers._playlist_cache", clear=True)
        cache.start()
        self.addCleanup(cache.stop)

    def test_url_routing(self):
        self.assertEqual(provider_for("https://open.spotify.com/playlist/123"), "spotify")
        for url in ("https://www.youtube.com/playlist?list=123", "https://music.youtube.com/watch?v=abc&list=123", "https://youtu.be/abc?list=123"):
            self.assertEqual(provider_for(url), "youtube")
        for url in ("file:///tmp/playlist", "https://example.com/playlist", "https://youtube.com/watch?v=abc", "https://notyoutube.com/playlist?list=123"):
            with self.assertRaises(ValueError):
                provider_for(url)

    @patch("youtube_provider.run_tool")
    def test_youtube_playlist(self, run):
        run.return_value = json.dumps({"title": "Favorites", "entries": [
            {"title": "Artist - Song (Official Video)", "channel": "Label"},
            {"title": "Another [Lyrics]", "channel": "Singer - Topic"},
            None, {"title": "[Deleted video]"}, {"title": "Hidden", "availability": "private"},
        ]})
        playlist = load_playlist("https://www.youtube.com/playlist?list=123")
        self.assertEqual(playlist.name, "Favorites")
        self.assertEqual(playlist.tracks, [Track("Artist", "Song"), Track("Singer", "Another")])
        self.assertEqual(playlist.skipped, 3)
        self.assertIn("--flat-playlist", run.call_args.args[1])

    @patch("spotify_provider.run_tool")
    def test_spotify_playlist_and_temporary_cleanup(self, run):
        def save(tool, arguments):
            self.assertEqual(tool, "spotdl")
            path = Path(arguments[-1])
            path.write_text(json.dumps([
                {"name": "Song", "artists": [{"name": "Artist"}, "Guest"]},
            ]), encoding="utf-8")
            return ""
        run.side_effect = save
        playlist = load_playlist("https://open.spotify.com/playlist/123")
        self.assertEqual(playlist.tracks, [Track("Artist, Guest", "Song")])
        self.assertFalse(Path(run.call_args.args[1][-1]).exists())

    @patch("youtube_provider.run_tool", return_value='{"entries": []}')
    def test_empty_playlist(self, run):
        with self.assertRaisesRegex(ValueError, "No accessible tracks"):
            load_playlist("https://youtube.com/playlist?list=123")

    @patch("playlist_provider.shutil.which", return_value="/usr/bin/yt-dlp")
    @patch("playlist_provider.subprocess.run")
    def test_tool_failure(self, run, which):
        run.side_effect = subprocess.CalledProcessError(1, "yt-dlp", stderr="Playlist is private")
        with self.assertRaisesRegex(RuntimeError, "Playlist is private"):
            run_tool("yt-dlp", [])

    @patch("playlist_provider.shutil.which", return_value=None)
    @patch("playlist_provider.importlib.util.find_spec", return_value=None)
    def test_missing_dependency(self, find_spec, which):
        with self.assertRaisesRegex(RuntimeError, "pip install yt-dlp"):
            run_tool("yt-dlp", [])

    @patch("playlist_provider.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True)
    @patch("playlist_provider.shutil.which", return_value=r"C:\Program Files\Python\Scripts\yt-dlp.exe")
    @patch("playlist_provider.subprocess.run")
    def test_windows_command_and_utf8(self, run, which):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="Caf\u00e9")
        self.assertEqual(run_tool("yt-dlp", ["--version"]), "Caf\u00e9")
        self.assertEqual(run.call_args.args[0], [which.return_value, "--version"])
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(run.call_args.kwargs["creationflags"], 0x08000000)

    @patch("playlist_provider.shutil.which", return_value=None)
    @patch("playlist_provider.importlib.util.find_spec", return_value=object())
    @patch("playlist_provider.subprocess.run")
    def test_python_module_fallback(self, run, find_spec, which):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="version")
        run_tool("yt-dlp", ["--version"])
        self.assertEqual(run.call_args.args[0], [sys.executable, "-m", "yt_dlp", "--version"])

    @patch("playlist_provider.subprocess.run")
    @patch("playlist_provider.importlib.util.find_spec")
    @patch("playlist_provider.shutil.which", return_value=None)
    @patch("playlist_provider.sys.frozen", True, create=True)
    def test_frozen_provider_dispatch(self, which, find_spec, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="version")
        self.assertEqual(run_tool("yt-dlp", ["--version"]), "version")
        self.assertEqual(run.call_args.args[0], [sys.executable, "--_playlistcompare_provider", "yt-dlp", "--version"])
        find_spec.assert_not_called()

    def test_provider_tool_dispatch(self):
        from playlistcompare import run_provider_tool

        entry_point = unittest.mock.Mock()
        entry_point.name = "yt-dlp"
        entry_point.group = "console_scripts"
        entry_point.load.return_value.return_value = 0
        with patch("playlistcompare.distribution") as get_distribution, patch("playlistcompare.sys.argv", ["app", "unchanged"]):
            get_distribution.return_value.entry_points = [entry_point]
            with self.assertRaises(SystemExit) as result:
                run_provider_tool(["--_playlistcompare_provider", "yt-dlp", "--version"])
            self.assertEqual(sys.argv, ["yt-dlp", "--version"])
        self.assertEqual(result.exception.code, 0)
        get_distribution.assert_called_once_with("yt-dlp")

    def test_unified_cache_and_force_reload_for_both_providers(self):
        for provider, url in (("youtube", "https://youtube.com/playlist?list=abc"),
                              ("spotify", "https://open.spotify.com/playlist/abc")):
            with self.subTest(provider=provider), patch.object(_providers[provider], "load") as load:
                load.return_value = Playlist("Original", [Track("Artist", "Song")])
                first = load_playlist(url)
                first.tracks.clear()
                self.assertEqual(load_playlist(url).tracks, [Track("Artist", "Song")])
                load.assert_called_once_with(url)
                load.return_value = Playlist("Updated", [Track("Artist", "New Song")])
                self.assertEqual(load_playlist(url, force_reload=True).name, "Updated")
                self.assertEqual(load.call_count, 2)
                self.assertEqual(load_playlist(url).name, "Updated")
                self.assertEqual(load.call_count, 2)

    @patch("youtube_provider.run_tool")
    def test_failed_reload_preserves_cache(self, run):
        url = "https://youtube.com/playlist?list=abc"
        run.return_value = '{"title": "Original", "entries": [{"title": "Artist - Song"}]}'
        load_playlist(url)
        run.side_effect = RuntimeError("Network error")
        with self.assertRaisesRegex(RuntimeError, "Network error"):
            load_playlist(url, force_reload=True)
        self.assertEqual(load_playlist(url).name, "Original")

    @patch("youtube_provider.run_tool", side_effect=['{"entries": []}', '{"entries": [{"title": "Artist - Song"}]}'])
    def test_empty_results_are_not_cached(self, run):
        url = "https://youtube.com/playlist?list=abc"
        with self.assertRaises(ValueError):
            load_playlist(url)
        self.assertEqual(len(load_playlist(url).tracks), 1)
        self.assertEqual(run.call_count, 2)

    @patch.object(_providers["youtube"], "load")
    def test_cache_evicts_least_recently_used_url(self, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song")])
        urls = [f"https://youtube.com/playlist?list={index}" for index in range(31)]
        for url in urls[:30]:
            load_playlist(url)
        load_playlist(urls[0])
        load_playlist(urls[30])
        self.assertEqual(load.call_count, 31)
        load_playlist(urls[0])
        self.assertEqual(load.call_count, 31)
        load_playlist(urls[1])
        self.assertEqual(load.call_count, 32)

    @patch.object(_providers["youtube"], "load")
    def test_cache_trims_url_whitespace(self, load):
        load.return_value = Playlist("Favorites", [Track("Artist", "Song")])
        url = "https://youtube.com/playlist?list=abc"
        load_playlist(f"  {url}  ")
        load_playlist(url)
        load.assert_called_once_with(url)


if __name__ == "__main__":
    unittest.main()
import json
from pathlib import Path
import tempfile

from playlist_provider import Playlist, run_tool
from tracks import Track


class SpotifyProvider:
    def load(self, url: str) -> Playlist:
        with tempfile.TemporaryDirectory(prefix="playlistcompare-") as directory:
            path = Path(directory) / "playlist.spotdl"
            run_tool("spotdl", ["save", url, "--save-file", str(path)])
            entries = json.loads(path.read_text(encoding="utf-8"))
        tracks = []
        for entry in entries:
            artists = entry.get("artists", [])
            artist = ", ".join(item.get("name", "") if isinstance(item, dict) else str(item) for item in artists)
            if entry.get("name"):
                tracks.append(Track(artist, entry["name"]))
        return Playlist("Spotify playlist", tracks, len(entries) - len(tracks))
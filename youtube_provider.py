import json

from playlist_provider import Playlist, run_tool
from tracks import youtube_track


class YouTubeProvider:
    def load(self, url: str) -> Playlist:
        output = run_tool("yt-dlp", ["--flat-playlist", "--dump-single-json", "--yes-playlist", "--ignore-errors", "--no-warnings", url])
        data = json.loads(output)
        entries = data.get("entries") or []
        tracks = []
        for entry in entries:
            if not entry or entry.get("availability") in {"private", "needs_auth", "subscriber_only", "premium_only"}:
                continue
            if entry.get("title") in {"[Private video]", "[Deleted video]"}:
                continue
            track = youtube_track(entry)
            if track.title:
                tracks.append(track)
        return Playlist(data.get("title") or "YouTube playlist", tracks, len(entries) - len(tracks))
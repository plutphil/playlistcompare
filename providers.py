from collections import OrderedDict
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

from playlist_provider import Playlist, PlaylistProvider, run_tool
from spotify_provider import SpotifyProvider
from youtube_provider import YouTubeProvider


_providers: dict[str, PlaylistProvider] = {"spotify": SpotifyProvider(), "youtube": YouTubeProvider()}
_playlist_cache: OrderedDict[str, Playlist] = OrderedDict()


def provider_for(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Enter a Spotify or YouTube playlist URL.")
    if host == "open.spotify.com":
        return "spotify"
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        if not parse_qs(parsed.query).get("list"):
            raise ValueError("The YouTube URL must include a playlist (list=...).")
        return "youtube"
    raise ValueError("Only Spotify and YouTube playlist URLs are supported.")


def load_playlist(url: str, *, force_reload: bool = False) -> Playlist:
    url = url.strip()
    provider = _providers[provider_for(url)]
    if not force_reload and url in _playlist_cache:
        _playlist_cache.move_to_end(url)
        return deepcopy(_playlist_cache[url])
    playlist = provider.load(url)
    if not playlist.tracks:
        raise ValueError("No accessible tracks were found in this playlist.")
    _playlist_cache[url] = deepcopy(playlist)
    _playlist_cache.move_to_end(url)
    if len(_playlist_cache) > 30:
        _playlist_cache.popitem(last=False)
    return playlist
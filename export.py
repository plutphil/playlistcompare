from os import path as paths
from pathlib import Path
import tempfile


def relative_path(source, destination):
    try:
        relative = paths.relpath(str(source), paths.dirname(str(destination)))
    except ValueError as error:
        raise ValueError("Save the playlist on the same drive as the audio files to use relative paths.") from error
    relative = relative.replace(paths.sep, "/")
    if "\n" in relative or "\r" in relative:
        raise ValueError("M3U playlists cannot contain filenames with line breaks.")
    return "./" + relative if relative.startswith("#") else relative


def write_playlist(destination, entries):
    destination = Path(destination).expanduser().absolute()
    if destination.suffix.lower() not in {".m3u", ".m3u8"}:
        raise ValueError("Choose an .m3u or .m3u8 playlist filename.")
    lines = ["#EXTM3U"]
    for track, source in entries:
        source = Path(source).absolute()
        if not source.is_file():
            raise ValueError(f"Audio file no longer exists: {source}")
        relative = relative_path(source, destination)
        label = " ".join(f"{track.artist} - {track.title}".splitlines())
        lines.extend((f"#EXTINF:-1,{label}", relative))
    if len(lines) == 1:
        raise ValueError("There are no found tracks to export.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("\n".join(lines) + "\n")
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return (len(lines) - 1) // 2
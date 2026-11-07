from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata


AUDIO = {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aac"}
VIDEO_LABEL = r"(?:official\s+)?(?:music\s+)?(?:video|audio|visuali[sz]er|lyric(?:s|\s+video)?)(?:\s+hd|\s+4k)?|hd|4k|hq"
BRACKET_LABEL = re.compile(rf"\s*[\[(]\s*(?:{VIDEO_LABEL})\s*[\])]", re.I)
TRAILING_LABEL = re.compile(rf"\s*[-|:]\s*(?:{VIDEO_LABEL})\s*$", re.I)


@dataclass(frozen=True)
class Track:
    artist: str
    title: str


@dataclass(frozen=True)
class LocalFile:
    path: str
    name: str
    folder: str


@dataclass(frozen=True)
class SearchResult:
    path: str
    title_score: int
    artist_score: int

    @property
    def score(self):
        return self.title_score + self.artist_score


def clean(value):
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^\w]+|_", " ", value).split())


def refine_title(title):
    title = BRACKET_LABEL.sub("", title or "")
    return TRAILING_LABEL.sub("", title).strip()


def youtube_track(entry):
    title = refine_title(entry.get("track") or entry.get("title", ""))
    artist = entry.get("artist") or ""
    if not artist:
        parts = re.split(r"\s+[-\u2013\u2014]\s+", title, maxsplit=1)
        if len(parts) == 2 and all(parts):
            artist, title = parts
        else:
            artist = entry.get("channel") or entry.get("uploader") or ""
            artist = re.sub(r"\s*-\s*Topic$|VEVO$", "", artist, flags=re.I).strip()
    return Track(artist.strip(), title.strip())


def local_files(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Choose an existing audio folder.")
    files = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO:
            relative = path.relative_to(folder)
            files.append(LocalFile(relative.as_posix(), clean(path.stem), clean(relative.parent.as_posix())))
    return files


def search_tracks(track, files):
    title = clean(refine_title(track.title))
    base = clean(re.sub(r"\([^)]*\)|\[[^]]*\]", "", refine_title(track.title)))
    base = re.split(r"\b(?:feat|ft|featuring)\b", base, maxsplit=1)[0].strip() or title
    words = set(base.split())
    if not words:
        return []
    artist_words = set(clean(track.artist).split())
    results = []
    for file in files:
        name_words = set(file.name.split())
        if not words.issubset(name_words):
            continue
        title_score = 100 if f" {title} " in f" {file.name} " else 85 if set(title.split()).issubset(name_words) else 65
        artist_score = 0
        if artist_words:
            artist_score = round(20 * len(artist_words & (name_words | set(file.folder.split()))) / len(artist_words))
        results.append(SearchResult(file.path, title_score, artist_score))
    return sorted(results, key=lambda result: (-result.score, -result.title_score, result.path.casefold(), result.path))


def match_track(track, files):
    results = search_tracks(track, files)
    return results[0].path if results else None
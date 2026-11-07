# Playlist Compare

Compare Spotify or YouTube playlists with audio files in a local folder.
Only playlist metadata is fetched; no audio or video is downloaded.

## Run

Use Python 3.10 or newer with Tkinter installed. On Linux, Tkinter may need
to be installed separately using your distribution's package manager.

### Linux

```sh
python3 -m pip install -r requirements.txt
python3 playlistcompare.py
```

### Windows

Install Python with the Python launcher and Tcl/Tk support. From PowerShell
in this project's folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe playlistcompare.py
```

An activated environment is not required. The app can run the provider tools
as Python modules if their executables are not on `PATH`. Paths with spaces
and Unicode filenames are supported; provider output uses UTF-8, and provider
processes do not open extra console windows on Windows.

## Packaged Builds

The GitHub Actions **Build packages** workflow builds a standalone Windows
`PlaylistCompare.exe` and an x86_64 Linux AppImage. To publish a GitHub Release,
push a version tag such as `v1.0.0`:

```sh
git tag v1.0.0
git push origin v1.0.0
```

After both builds pass, the workflow creates the release and attaches both
files. To build without publishing, run the workflow from the Actions tab and
download its artifacts. The Windows executable is built on Windows because
PyInstaller does not cross-compile between operating systems. Linux builds
require a compatible system GUI runtime (including Tk dependencies).

## Compare

Paste a Spotify or YouTube playlist URL, choose an audio folder, and load.
YouTube playlist URLs must contain `list=...`; YouTube Music and video URLs
with a playlist parameter are also supported. Playlists must be accessible
without signing in. Private/deleted entries are skipped when present in the
returned metadata. Providers may omit unavailable entries entirely.

**Load** scans the selected audio folder and fetches playlist metadata only
when its URL is not cached. Both Spotify and YouTube metadata are cached in
memory for the 30 most recently used URLs until the app closes. The cache has
no automatic expiry, is keyed by the complete URL (after trimming whitespace),
and is not saved to disk. Failed or empty fetches are not cached.

**Force Reload** bypasses this cache, fetches the URL currently entered, and
rescans the selected folder. A successful fetch replaces its cached metadata;
a failed reload preserves the previous cache and displayed results.

**Rescan Files** scans the folder currently entered and updates matches and
export entries using the already displayed playlist, with no provider requests.
It ignores edits to the URL field and is enabled only after a playlist has
loaded. Scanning and playlist loading run in the background.

The editable playlist combobox stores the last 30 successfully loaded URLs.
Selecting an entry restores its URL and audio folder. History survives restarts
in `$XDG_CONFIG_HOME/playlistcompare/history.json` on Linux, defaulting to
`~/.config/playlistcompare/history.json`. On Windows it uses
`%APPDATA%\playlistcompare\history.json`, falling back to
`%USERPROFILE%\AppData\Roaming\playlistcompare\history.json`.

YouTube titles lose common video labels such as `(Official Music Video)`,
`[Lyrics]`, or `| Official Video`, while version names such as `(Club Remix)`
are kept. Artist metadata takes priority, followed by an `Artist - Title`
split, then the channel/uploader name. Channel suffixes `- Topic` and `VEVO`
are removed. Channel fallback is a heuristic: a label's channel may not be
the actual performer.

Audio matching scans subfolders for MP3, FLAC, M4A, WAV, OGG, OPUS, and AAC.
It searches by title first: all title words must appear in the filename,
ignoring case, punctuation, and accent differences. Track numbers and extra
filename text do not prevent a match. Parenthesized/bracketed version names
and featured artists are optional for candidate discovery; full title matches
rank above base-title matches. Artist words in the filename or containing
folder add a ranking bonus but are never required. Duplicate filenames in
different folders remain separate candidates. Tied scores use path order.
The highest ranked result is used for comparison and export. This is filename
matching, not audio-tag matching or typo correction; inspect ambiguous titles
in the search window before exporting.

## Search Files

Select a playlist row and click **Search Files**, or double-click the row, to
open its ranked results in a separate window. Edit the title and optional
artist, then click **Search** or press Enter. All matching files are shown
with title scores, artist bonuses, and paths relative to the scanned folder.
A title score is 100 for a full title phrase, 85 for all full-title words,
or 65 for base-title words; artist overlap adds up to 20 points. These are
ranking scores, not confidence percentages.

Without a selected row, **Search Files** searches the audio folder currently
entered, even without loading a playlist. Folder scanning runs in the
background. A selected playlist row always searches its originally loaded
folder, regardless of subsequent folder-field edits.

Select a search result to enable these actions:

- **Open** opens the audio file with the default application.
- **Open folder** opens its containing folder in the system file manager.
- **Delete** asks for confirmation with the full file path before permanently
	deleting the file. It does not move files to the recycle bin or trash.

Confirmed deletion removes the candidate from the search index. When searching
the loaded playlist's folder, the main table and export list also refresh:
the next ranked candidate becomes the match, or the track becomes missing.
Folder changes made outside the app require reopening a standalone search or
clicking **Rescan Files** to rebuild the loaded playlist's index. Linux open
actions need `xdg-open`.

## Export For Mixxx

After loading a playlist, click **Export M3U** and choose a save location.
The button is enabled only when local tracks were found and loading has finished.
Import the saved file using Mixxx's playlist import command.

- Only found audio files are exported, in the original playlist order.
- The default is a UTF-8 `.m3u8` playlist; `.m3u` is also available.
- File paths are relative to the saved playlist's directory, not the audio folder.
	For example, a playlist in `playlists/` can reference `../music/Artist - Song.mp3`.
- Paths use forward slashes, with spaces and Unicode names kept intact.
- Changing the folder field after loading does not change the files exported.
- Keep the relative directory layout intact when moving a playlist and its audio.
- On Windows, save the playlist on the same drive or network share as the audio;
	different drives/shares cannot be represented with relative paths.

Export refuses missing/deleted audio files and filenames containing line breaks.
An existing playlist is replaced only after the complete export is written.

## Modules

- `playlistcompare.py`: entry point.
- `app.py`: Tkinter UI and background comparison.
- `providers.py`: unified `load_playlist(url, force_reload=False)` API, URL
	routing, and session metadata cache (`force_reload` is keyword-only).
- `playlist_provider.py`: shared `Playlist` model, `PlaylistProvider.load(url)`
	contract, and subprocess runner.
- `spotify_provider.py`: Spotify (`spotdl`) metadata implementation.
- `youtube_provider.py`: YouTube (`yt-dlp`) metadata implementation.
- `tracks.py`: title refinement and local-file matching.
- `history.py`: persistent playlist history.
- `export.py`: relative-path M3U/M3U8 export for Mixxx.
- `search_window.py`: ranked search results and confirmed file actions.
- `file_actions.py`: platform-specific file/folder opening.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests mock provider commands and need no network access. GUI tests use a real
Tkinter window and skip when no display is available. Windows drive/UNC paths,
configuration locations, and subprocess settings are tested using simulations;
native Windows execution and Mixxx import still need validation on those systems.
from dataclasses import dataclass
import importlib.util
import os
import shutil
import subprocess
import sys
from typing import Protocol

from tracks import Track


@dataclass
class Playlist:
    name: str
    tracks: list[Track]
    skipped: int = 0


class PlaylistProvider(Protocol):
    def load(self, url: str) -> Playlist:
        ...


def run_tool(tool, arguments):
    executable = shutil.which(tool)
    module = tool.replace("-", "_")
    if executable:
        command = [executable]
    elif importlib.util.find_spec(module):
        command = [sys.executable, "-m", module]
    else:
        raise RuntimeError(f"{tool} is not installed. Run: {sys.executable} -m pip install {tool}")
    try:
        result = subprocess.run(
            command + arguments, capture_output=True, encoding="utf-8", errors="replace", check=True, timeout=300,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or str(error)).strip()[-2000:]
        raise RuntimeError(f"{tool} could not load the playlist:\n{details}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{tool} timed out while loading the playlist.") from error
    return result.stdout
import os
from pathlib import Path
import subprocess
import sys


def open_path(path):
    path = Path(path).absolute()
    if not path.exists():
        raise FileNotFoundError(f"Path no longer exists: {path}")
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        command = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([command, str(path)])